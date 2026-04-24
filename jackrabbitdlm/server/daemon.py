#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jackrabbit DLM Server Daemon

A high-performance, zero-dependency Distributed Lock Manager (DLM) and
volatile state coordinator. Uses non-blocking TCP I/O with select.poll()
for concurrent connection handling.

Architecture:
    - "Blind Vault" design: server never stores plain-text data
    - JSON-over-TCP protocol (newline-delimited)
    - Advisory locking with ownership enforcement
    - Volatile KV store with automatic TTL expiration
    - Disk spillover for large data payloads
    - Automatic garbage collection and memory monitoring

Usage:
    python3 -m jackrabbitdlm.server.daemon [host] [port]
    
    Default: 0.0.0.0:37373

Protocol (JSON over TCP):
    Lock:   {"ID":"...", "FileName":"...", "Action":"Lock", "Expire":"300"}
    Unlock: {"ID":"...", "FileName":"...", "Action":"Unlock"}
    Put:    {"ID":"...", "FileName":"...", "Action":"Put", "DataStore":"...", "Expire":"300"}
    Get:    {"ID":"...", "FileName":"...", "Action":"Get"}
    Erase:  {"ID":"...", "FileName":"...", "Action":"Erase"}

See also:
    - https://en.wikipedia.org/wiki/Distributed_lock_manager
    - https://en.wikipedia.org/wiki/Non-blocking_I/O_(Java)
    - https://en.wikipedia.org/wiki/Select_(Unix)
    - https://en.wikipedia.org/wiki/Time_to_live
    - https://en.wikipedia.org/wiki/Garbage_collection_(computer_science)
    - https://en.wikipedia.org/wiki/Advisory_lock
"""

import sys
import os
import gc
import psutil
import random
import secrets
import time
from datetime import datetime
import socket
import select
import json

from ..common.encoding import dlmEncode, dlmDecode, ShuffleJSON
from .backends.registry import BackendRegistry

# ── Version & Configuration ────────────────────────────────────────────

VERSION = "0.0.0.2.830"

BASE_DIR = os.environ.get("JACKRABBIT_BASE", "/home/JackrabbitDLM")
CONFIG_DIR = os.path.join(BASE_DIR, "Config")
DISK_DIR = os.path.join(BASE_DIR, "Disk")
LOG_DIR = os.path.join(BASE_DIR, "Logs")
QUARANTINE_DIR = os.path.join(BASE_DIR, "Quarantine")

# Performance globals -- initialized once for throughput.
# psutil.Process is expensive; making it global doubled throughput.
_process = psutil.Process(os.getpid())
_total_ram = psutil.virtual_memory().total

# Memory threshold (percentage) for rejecting new data stores
MEMORY_THRESHOLD = 33

# Statistics accumulator
Statistics = {}

# Main lock/data storage
Locker = {}

# Socket read block size
MAX_BLOCK_SIZE = 4096

# Maximum TTL for anonymous (unauthenticated) requests
MAX_TTL = 3543

# Payload size limits
MAX_PAYLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_DATASTORE_SIZE = 16 * 1024       # 16 KB

# Garbage collection tracking
_max_data_hold_size = 0


# ── Utility Functions ──────────────────────────────────────────────────

def _rebuild_dict(d):
    """Defragment a dictionary via JSON round-trip. All keys become strings."""
    if not d:
        return {}
    try:
        return json.loads(json.dumps(d))
    except Exception:
        return {str(k): v for k, v in d.items()}


def _is_number(s):
    """Check if string is numeric."""
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


def _memory_overload_check(threshold_percent=MEMORY_THRESHOLD):
    """Check if process memory exceeds threshold. Returns (overload, percent)."""
    global Statistics
    rss = _process.memory_info().rss
    usage = (rss / _total_ram) * 100

    if usage > Statistics.get('MemoryMax', 0):
        Statistics['MemoryMax'] = usage
    Statistics['MemoryUsage'] = usage

    return usage > threshold_percent, usage


def _sanitize_path(filename):
    """Build disk path for a data store entry."""
    return os.path.join(DISK_DIR, dlmEncode(filename) + ".db")


def _read_identity(name):
    """Read authentication config from Config/{name}.cfg."""
    path = os.path.join(CONFIG_DIR, f"{name}.cfg")
    if not os.path.exists(path):
        return None

    try:
        with open(path, 'r') as f:
            buf = json.loads(f.read().strip())
    except Exception:
        return None

    if not isinstance(buf, dict) or 'Identity' not in buf or len(buf['Identity']) < 1023:
        return None

    if 'MaxSize' not in buf or not _is_number(buf['MaxSize']):
        buf['MaxSize'] = MAX_DATASTORE_SIZE

    return buf


def _write_pid(port):
    """Write PID file for this server instance."""
    path = os.path.join(LOG_DIR, f"{port}.pid")
    with open(path, "w") as f:
        f.write(str(os.getpid()))


def _write_log(msg):
    """Append timestamped log entry."""
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
    line = f'{ts} {msg}\n'
    with open(os.path.join(LOG_DIR, 'JackrabbitDLM.log'), 'a') as f:
        f.write(line)


def _write_error(err, addr, payload):
    """Write error payload to quarantine directory."""
    token = secrets.token_urlsafe(73)
    fname = os.path.join(QUARANTINE_DIR, f"{token}.db")
    _write_log(f"DLMerror/{err}: {addr}/{fname}")
    with open(fname, 'w') as f:
        f.write(json.dumps(payload))


def _read_file(path):
    """Read file contents, return None if not found."""
    if os.path.exists(path):
        with open(path, 'r') as f:
            return f.read().strip()
    return None


def _write_file(path, data):
    """Write data to file."""
    with open(path, 'w') as f:
        f.write(data)


def _status_json(status, id=None, tag=None, data=None):
    """Build encoded JSON status response."""
    res = {"Status": status}
    if id is not None:
        res["ID"] = id
    if tag is not None and data is not None:
        res[tag] = data
    out = dlmEncode(json.dumps(ShuffleJSON(res)))
    return out + '\n'


def _reload_disk_memory():
    """Reload persisted DataStores from disk on startup."""
    global Locker, Statistics

    if not os.path.isdir(DISK_DIR):
        return

    for fname in os.listdir(DISK_DIR):
        path = os.path.join(DISK_DIR, fname)
        if not os.path.isfile(path) or fname.startswith('.'):
            continue

        try:
            data = json.loads(_read_file(path))
        except Exception:
            Statistics['Corruption'] = Statistics.get('Corruption', 0) + 1
            os.remove(path)
            continue

        if time.time() > data['Expire']:
            Statistics['ExpiredData'] = Statistics.get('ExpiredData', 0) + 1
            os.remove(path)
            continue

        Locker[fname] = data
        Statistics['PutNew'] = Statistics.get('PutNew', 0) + 1
        Statistics['DataIn'] = Statistics.get('DataIn', 0) + len(data.get('DataStore', ''))


def _check_identity(data_db, lock_db):
    """Verify identity match between incoming payload and stored lock."""
    has_name_data = 'Name' in data_db
    has_name_lock = 'Name' in lock_db

    if has_name_data != has_name_lock:
        return False

    if has_name_lock:
        if (data_db.get('Name') != lock_db.get('Name') or
                data_db.get('Identity') != lock_db.get('Identity')):
            return False

    return True


# ── Request Processing ─────────────────────────────────────────────────

def process_payload(addr, data):
    """
    Process a client request and return response.
    
    This is the core request handler. It decodes the incoming payload,
    validates it, and dispatches to the appropriate action handler.
    """
    global Statistics, Locker, _max_data_hold_size

    data = "".join(data)
    data = dlmDecode(data.strip()).decode('utf-8')

    try:
        data_db = json.loads(data)
    except Exception:
        Statistics['BadPayload'] = Statistics.get('BadPayload', 0) + 1
        _write_error("Payload", addr, data)
        return _status_json("BadPayload")

    # Validate required fields
    required = ['FileName', 'Action', 'ID', 'Expire']
    if any(k not in data_db for k in required) or not _is_number(data_db['Expire']):
        Statistics['BadPayload'] = Statistics.get('BadPayload', 0) + 1
        _write_error("KeyVerify", addr, json.dumps(data_db))
        return _status_json("BadPayload")

    data_db['Expire'] = float(data_db['Expire'])

    # ── Authentication checks ──────────────────────────────────────────

    # Anonymous DataStore size limit
    if 'DataStore' in data_db and 'Name' not in data_db:
        if data_db['DataStore'] and len(data_db['DataStore']) > MAX_DATASTORE_SIZE:
            Statistics['AuthFailed'] = Statistics.get('AuthFailed', 0) + 1
            _write_error("MaxDataStoreSize", addr, json.dumps(data_db))
            return _status_json("BadPayload")

    # Anonymous TTL limit
    if data_db['Expire'] > MAX_TTL and 'Name' not in data_db:
        Statistics['AuthFailed'] = Statistics.get('AuthFailed', 0) + 1
        _write_error("MaxTTL", addr, json.dumps(data_db))
        return _status_json("BadPayload")

    auth = None
    max_size = MAX_DATASTORE_SIZE

    if 'Name' in data_db:
        auth = _read_identity(data_db['Name'])
        if (auth is None or
                'Identity' not in data_db or
                'Identity' not in auth or
                len(data_db['Identity']) < 1023 or
                data_db['Identity'] != auth['Identity']):
            Statistics['AuthFailed'] = Statistics.get('AuthFailed', 0) + 1
            _write_error("Identity", addr, json.dumps(data_db))
            return _status_json("BadPayload")
        max_size = auth['MaxSize']

    # ── Action dispatch ────────────────────────────────────────────────

    filename = data_db['FileName']
    action = data_db['Action'].lower()

    if action == 'lock':
        return _handle_lock(data_db, filename)
    elif action == 'unlock':
        return _handle_unlock(data_db, filename)
    elif action == 'get':
        return _handle_get(data_db, filename)
    elif action == 'put':
        return _handle_put(data_db, filename, max_size)
    elif action == 'erase':
        return _handle_erase(data_db, filename)
    elif action == 'version':
        return _status_json("Version", f"JackrabbitDLM/{VERSION}")
    else:
        Statistics['BadAction'] = Statistics.get('BadAction', 0) + 1
        return _status_json("BadAction")


def _handle_lock(data_db, filename):
    """Handle Lock action."""
    global Statistics, Locker

    overload, _ = _memory_overload_check()
    if overload:
        Statistics['MemoryOverloadCheck'] = Statistics.get('MemoryOverloadCheck', 0) + 1
        return _status_json("NO")

    # New lock request
    if filename not in Locker or time.time() > Locker[filename]['Expire']:
        lock = {'ID': data_db['ID'], 'Expire': time.time() + data_db['Expire']}
        if 'Name' in data_db:
            lock['Name'] = data_db['Name']
            lock['Identity'] = data_db['Identity']
        Locker[filename] = lock
        Statistics['Lock'] = Statistics.get('Lock', 0) + 1
        return _status_json("Locked", Locker[filename]['ID'])

    # Existing lock - same owner wants to renew
    if Locker[filename]['ID'] == data_db['ID']:
        if not _check_identity(data_db, Locker[filename]):
            Statistics['NotOwner'] = Statistics.get('NotOwner', 0) + 1
            return _status_json("NotOwner")
        Locker[filename]['Expire'] = time.time() + data_db['Expire']
        Statistics['Relock'] = Statistics.get('Relock', 0) + 1
        return _status_json("Locked", Locker[filename]['ID'])

    # Different owner
    Statistics['NotOwner'] = Statistics.get('NotOwner', 0) + 1
    return _status_json("NotOwner")


def _handle_unlock(data_db, filename):
    """Handle Unlock action."""
    global Statistics, Locker

    if filename not in Locker:
        Statistics['UnlockNF'] = Statistics.get('UnlockNF', 0) + 1
        return _status_json("Unlocked")

    if Locker[filename]['ID'] == data_db['ID']:
        if not _check_identity(data_db, Locker[filename]):
            Statistics['NotOwner'] = Statistics.get('NotOwner', 0) + 1
            return _status_json("NotOwner")
        if Locker[filename]['Expire'] > 0:
            Statistics['Unlock'] = Statistics.get('Unlock', 0) + 1
        Locker[filename]['Expire'] = 0
        return _status_json("Unlocked", Locker[filename]['ID'])

    Statistics['NotOwner'] = Statistics.get('NotOwner', 0) + 1
    return _status_json("NotOwner")


def _handle_get(data_db, filename):
    """Handle Get action."""
    global Statistics, Locker

    if filename not in Locker:
        Statistics['GetNF'] = Statistics.get('GetNF', 0) + 1
        return _status_json("NotFound")

    if Locker[filename]['ID'] == data_db['ID'] and time.time() <= Locker[filename]['Expire']:
        if not _check_identity(data_db, Locker[filename]):
            Statistics['NotOwner'] = Statistics.get('NotOwner', 0) + 1
            return _status_json("NotOwner")

        if 'DataStore' in Locker[filename]:
            Statistics['Get'] = Statistics.get('Get', 0) + 1
            Statistics['DataOut'] = Statistics.get('DataOut', 0) + len(Locker[filename]['DataStore'])

            # Disk-spillover data
            if 'Disk' in Locker[filename]:
                try:
                    raw = json.loads(_read_file(_sanitize_path(filename)))
                    return _status_json("Done", Locker[filename]['ID'],
                                        tag="DataStore", data=raw['DataStore'])
                except Exception:
                    Statistics['Corruption'] = Statistics.get('Corruption', 0) + 1
                    return _status_json("Corruption")

            return _status_json("Done", Locker[filename]['ID'],
                                tag="DataStore", data=Locker[filename]['DataStore'])

        Statistics['GetNF'] = Statistics.get('GetNF', 0) + 1
        return _status_json("NoData", Locker[filename]['ID'])

    Statistics['NotOwner'] = Statistics.get('NotOwner', 0) + 1
    return _status_json("NotOwner")


def _handle_put(data_db, filename, max_size):
    """Handle Put action."""
    global Statistics, Locker, _max_data_hold_size

    overload, pct = _memory_overload_check()
    if overload:
        Statistics['MemoryOverloadCheck'] = Statistics.get('MemoryOverloadCheck', 0) + 1
        return _status_json("NO")

    if 'DataStore' not in data_db:
        Statistics['BadPayload'] = Statistics.get('BadPayload', 0) + 1
        return _status_json("BadPayload")

    # Decide whether to spill to disk
    ds_len = len(data_db['DataStore'])
    force_disk = ((ds_len > MAX_DATASTORE_SIZE and data_db['Expire'] > 10) or
                  (ds_len > MAX_DATASTORE_SIZE and pct > (MEMORY_THRESHOLD / 2)) or
                  (ds_len > MAX_DATASTORE_SIZE / 2 and pct > (MEMORY_THRESHOLD * 0.75)))

    # New data store
    if filename not in Locker or time.time() > Locker[filename]['Expire']:
        if ds_len > max_size:
            Statistics['BadPayload'] = Statistics.get('BadPayload', 0) + 1
            return _status_json("BadPayload")

        store = {
            'ID': data_db['ID'],
            'Expire': time.time() + data_db['Expire'],
            'DataStore': data_db['DataStore']
        }
        if force_disk:
            store['FileName'] = filename
            store['Disk'] = True
        Locker[filename] = store

        if 'Name' in data_db:
            Locker[filename]['Name'] = data_db['Name']
            Locker[filename]['Identity'] = data_db['Identity']

        if 'Disk' in store:
            _write_file(_sanitize_path(filename), json.dumps(Locker[filename]))
            Locker[filename]['DataStore'] = "OD"  # On-Disk marker
            Statistics['PutDisk'] = Statistics.get('PutDisk', 0) + 1
        else:
            Statistics['PutMemory'] = Statistics.get('PutMemory', 0) + 1

        Statistics['PutNew'] = Statistics.get('PutNew', 0) + 1
        Statistics['DataIn'] = Statistics.get('DataIn', 0) + ds_len
        return _status_json("Done", Locker[filename]['ID'])

    # Existing data store - verify owner
    if Locker[filename]['ID'] == data_db['ID']:
        if not _check_identity(data_db, Locker[filename]):
            Statistics['NotOwner'] = Statistics.get('NotOwner', 0) + 1
            return _status_json("NotOwner")

        if ds_len > max_size:
            Statistics['BadPayload'] = Statistics.get('BadPayload', 0) + 1
            return _status_json("BadPayload")

        Locker[filename]['DataStore'] = data_db['DataStore']
        if force_disk:
            Locker[filename]['FileName'] = filename
            Locker[filename]['Disk'] = True
        else:
            Locker[filename].pop('Disk', None)
            path = _sanitize_path(filename)
            if os.path.exists(path):
                os.remove(path)

        Locker[filename]['Expire'] = time.time() + data_db['Expire']

        if 'Disk' in Locker[filename]:
            _max_data_hold_size += len(Locker[filename]['DataStore'])
            _write_file(_sanitize_path(filename), json.dumps(Locker[filename]))
            Locker[filename]['DataStore'] = "OD"
            Statistics['PutDisk'] = Statistics.get('PutDisk', 0) + 1
        else:
            Statistics['PutMemory'] = Statistics.get('PutMemory', 0) + 1

        Statistics['DataIn'] = Statistics.get('DataIn', 0) + ds_len
        Statistics['PutUpdate'] = Statistics.get('PutUpdate', 0) + 1
        return _status_json("Done", Locker[filename]['ID'])

    Statistics['NotOwner'] = Statistics.get('NotOwner', 0) + 1
    return _status_json("NotOwner")


def _handle_erase(data_db, filename):
    """Handle Erase action."""
    global Statistics, Locker, _max_data_hold_size

    if filename not in Locker:
        Statistics['EraseNF'] = Statistics.get('EraseNF', 0) + 1
        return _status_json("NotFound")

    if 'DataStore' not in Locker[filename]:
        Locker[filename]['Expire'] = 0
        Statistics['Corruption'] = Statistics.get('Corruption', 0) + 1
        return _status_json("Corruption")

    if Locker[filename]['ID'] == data_db['ID']:
        if not _check_identity(data_db, Locker[filename]):
            Statistics['NotOwner'] = Statistics.get('NotOwner', 0) + 1
            return _status_json("NotOwner")

        Locker[filename]['Expire'] = 0
        _max_data_hold_size += len(Locker[filename]['DataStore'] or '')
        Locker[filename]['DataStore'] = None
        Locker[filename].pop('Disk', None)

        path = _sanitize_path(filename)
        if os.path.exists(path):
            os.remove(path)

        Statistics['Erased'] = Statistics.get('Erased', 0) + 1
        return _status_json("Done", Locker[filename]['ID'])

    Statistics['NotOwner'] = Statistics.get('NotOwner', 0) + 1
    return _status_json("NotOwner")


# ── Main Server Loop ───────────────────────────────────────────────────

def _load_config():
    """Load configuration from YAML file if present."""
    config_path = os.path.join(CONFIG_DIR, "defaults.yaml")
    if os.path.exists(config_path):
        try:
            import yaml
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception:
            pass
    return {}

def main():
    """
    Main server entry point.
    
    Creates the TCP server, handles connections with non-blocking I/O,
    processes requests, manages lock expiration, and logs statistics.
    Optionally uses a pluggable storage backend (Redis, SQLite, Filesystem).
    """
    global Statistics, Locker, _max_data_hold_size

    # Create directories
    for d in [DISK_DIR, LOG_DIR, QUARANTINE_DIR]:
        os.makedirs(d, exist_ok=True)

    host = ''
    port = 37373

    if len(sys.argv) > 1:
        host = sys.argv[1]
    if len(sys.argv) > 2:
        port = int(sys.argv[2])

    # Load configuration and optionally configure storage backend
    config = _load_config()
    backend_name = config.get('backend', 'memory')
    if backend_name != 'memory':
        BackendRegistry.configure({
            'default': backend_name,
            'backends': config.get('backends', {})
        })
        _write_log(f"Using {backend_name} storage backend")
        try:
            backend = BackendRegistry.get()
            _write_log(f"Backend connected: {backend.name}")
        except Exception as e:
            _write_log(f"Backend connection failed: {e}, falling back to memory")
            backend_name = 'memory'

    _write_log(f"Jackrabbit DLM {VERSION}")
    _reload_disk_memory()

    # Per-connection data buffers
    data_store = {}
    data_store_len = {}
    send_buffer = {}

    # Create non-blocking TCP server
    try:
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.setblocking(False)
        server_sock.bind((host, port))
        server_sock.listen(1024)
    except OSError as err:
        msg = str(err)
        if 'Address already in use' in msg:
            msg = f'Another program is using this port: {port}'
        _write_log(msg)
        sys.exit(1)

    _write_pid(port)

    # Event loop with poll()
    poller = select.poll()
    fd_map = {}
    addr_map = {}

    poller.register(server_sock, select.POLLIN)
    fd_map[server_sock.fileno()] = server_sock

    old_hour = -1

    while True:
        events = poller.poll(30000)  # 30 second timeout

        if not events:
            Statistics['Idle'] = Statistics.get('Idle', 0) + 1
            if _max_data_hold_size > MAX_PAYLOAD_SIZE:
                Statistics['ForcedGC'] = Statistics.get('ForcedGC', 0) + 1
                _max_data_hold_size = 0
                gc.collect()

        act_in = 0
        act_out = 0

        for fd, event in events:
            str_fd = str(fd)
            sock = fd_map.get(str_fd)
            if sock is None:
                continue

            # New connection
            if sock is server_sock:
                try:
                    client_sock, client_addr = sock.accept()
                    client_sock.setblocking(False)
                    n_fd = str(client_sock.fileno())
                    poller.register(client_sock, select.POLLIN)
                    fd_map[n_fd] = client_sock
                    addr_map[n_fd] = client_addr[0]
                    data_store[n_fd] = []
                    data_store_len[n_fd] = 0
                    Statistics['Connections'] = Statistics.get('Connections', 0) + 1
                except Exception:
                    continue

            # Read event
            elif event & select.POLLIN:
                act_in += 1
                try:
                    data = sock.recv(MAX_BLOCK_SIZE)
                except Exception:
                    data = None

                if not data:
                    # Connection closed
                    data_store.pop(str_fd, None)
                    data_store_len.pop(str_fd, None)
                    send_buffer.pop(str_fd, None)
                    poller.unregister(sock)
                    fd_map.pop(str_fd, None)
                    addr_map.pop(str_fd, None)
                    sock.close()
                    continue

                # Enforce max payload size
                if data_store_len.get(str_fd, 0) + len(data) > MAX_PAYLOAD_SIZE:
                    _max_data_hold_size += data_store_len.get(str_fd, 0)
                    data_store.pop(str_fd, None)
                    data_store_len.pop(str_fd, None)
                    send_buffer.pop(str_fd, None)
                    poller.unregister(sock)
                    fd_map.pop(str_fd, None)
                    addr_map.pop(str_fd, None)
                    sock.close()
                    Statistics['DataOverrun'] = Statistics.get('DataOverrun', 0) + 1
                    continue

                Statistics['In'] = Statistics.get('In', 0) + 1

                try:
                    data = data.decode('utf-8')
                except Exception:
                    continue

                data_store[str_fd].append(data)
                data_store_len[str_fd] = data_store_len.get(str_fd, 0) + len(data)

                # Complete message received
                if data.endswith('\n'):
                    response = process_payload(addr_map[str_fd], data_store[str_fd])
                    send_buffer[str_fd] = response.encode('utf-8')
                    poller.modify(sock, select.POLLOUT)

            # Write event
            elif event & select.POLLOUT:
                act_out += 1
                if str_fd in send_buffer:
                    try:
                        sent = sock.send(send_buffer[str_fd])
                    except Exception:
                        sent = 0

                    if sent > 0:
                        send_buffer[str_fd] = send_buffer[str_fd][sent:]

                    if not send_buffer[str_fd]:
                        send_buffer.pop(str_fd, None)
                        data_store.pop(str_fd, None)
                        data_store_len.pop(str_fd, None)
                        poller.unregister(sock)
                        fd_map.pop(str_fd, None)
                        addr_map.pop(str_fd, None)
                        sock.close()
                        Statistics['Out'] = Statistics.get('Out', 0) + 1

            # Error/hangup
            elif event & (select.POLLHUP | select.POLLERR):
                Statistics['BadConn'] = Statistics.get('BadConn', 0) + 1
                data_store.pop(str_fd, None)
                data_store_len.pop(str_fd, None)
                send_buffer.pop(str_fd, None)
                poller.unregister(sock)
                fd_map.pop(str_fd, None)
                addr_map.pop(str_fd, None)
                sock.close()

        Statistics['AIn'] = act_in
        Statistics['AOut'] = act_out

        # ── Expire old entries ─────────────────────────────────────────

        Statistics['ALock'] = 0
        Statistics['AData'] = 0
        now = time.time()

        for k in list(Locker):
            if now > Locker[k]['Expire']:
                if 'DataStore' in Locker[k]:
                    if Locker[k]['DataStore'] is not None:
                        if 'Disk' in Locker[k]:
                            path = _sanitize_path(k)
                            if os.path.exists(path):
                                os.remove(path)
                        _max_data_hold_size += len(Locker[k]['DataStore'])
                        Locker[k]['DataStore'] = None
                    Statistics['ExpiredData'] = Statistics.get('ExpiredData', 0) + 1
                else:
                    Statistics['ExpiredLock'] = Statistics.get('ExpiredLock', 0) + 1
                Locker.pop(k, None)

            if k in Locker:
                if 'DataStore' in Locker[k]:
                    Statistics['AData'] += 1
                else:
                    Statistics['ALock'] += 1

        # ── Hourly statistics log ──────────────────────────────────────

        if now - old_hour > 3600 and Statistics:
            old_hour = now
            _memory_overload_check()
            s = ', '.join(f"{k}: {v}" for k, v in sorted(Statistics.items()) if v > 0)
            _write_log(s)

            # Defragment dictionaries
            Locker = _rebuild_dict(Locker)
            data_store = _rebuild_dict(data_store)
            data_store_len = _rebuild_dict(data_store_len)
            send_buffer = _rebuild_dict(send_buffer)
            fd_map = _rebuild_dict(fd_map)
            addr_map = _rebuild_dict(addr_map)
            Statistics = {}

        # ── Forced GC ──────────────────────────────────────────────────

        if _max_data_hold_size > MAX_PAYLOAD_SIZE:
            Statistics['ForcedGC'] = Statistics.get('ForcedGC', 0) + 1
            _max_data_hold_size = 0
            gc.collect(2)


if __name__ == '__main__':
    main()
