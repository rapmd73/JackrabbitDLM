#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jackrabbit DLM Client Library

The Locker class provides a Python client for the Jackrabbit DLM server.
It handles TCP communication, automatic retries, and pluggable
encoding/decoding for data transport.

Usage:
    from jackrabbitdlm import Locker
    
    lock = Locker("my_resource", Retry=7, RetrySleep=1)
    if lock.Lock(expire=30) == 'locked':
        try:
            # Critical section
            lock.Put(data="hello", expire=60)
            result = lock.Get()
        finally:
            lock.Unlock()

See also:
    - https://en.wikipedia.org/wiki/Distributed_lock_manager
    - https://en.wikipedia.org/wiki/Advisory_lock
    - https://en.wikipedia.org/wiki/Client-server_model
"""

import os
import time
import random
import socket
import json
import secrets

from ..common.encoding import dlmEncode, dlmDecode, ShuffleJSON


class Locker:
    """
    Client for the Jackrabbit Distributed Lock Manager.
    
    Provides advisory locking and shared volatile state via JSON-over-TCP.
    Supports custom encoder/decoder functions for encryption or compression.
    
    Args:
        filename: Resource name to lock/store data against
        Retry: Max retry attempts on failure (default: 7)
        RetrySleep: Seconds between retries (default: 1)
        Timeout: Socket timeout in seconds (default: 300)
        ID: Explicit client ID (default: auto-generated)
        Host: Server hostname (default: 127.0.0.1)
        Port: Server port (default: 37373)
        Encoder: Custom encoding function (default: dlmEncode)
        Decoder: Custom decoding function (default: dlmDecode)
        name: Optional auth name for identity-verified operations
        identity: Optional identity string for auth
    """

    VERSION = "0.0.0.1.580"
    VALID_RESPONSES = ['badpayload', 'locked', 'unlocked', 'notowner', 'notfound', 'version', 'no']

    def __init__(self, filename, Retry=7, RetrySleep=1, Timeout=300,
                 ID=None, Host='', Port=37373, Encoder=None, Decoder=None,
                 name=None, identity=None):
        self.encoder = Encoder if Encoder else dlmEncode
        self.decoder = Decoder if Decoder else dlmDecode

        self.ID = ID if ID is not None else self._generate_id()
        self.name = name
        self.identity = identity
        self.filename = filename
        self.retryLimit = Retry
        self.retrysleep = RetrySleep
        self.timeout = Timeout
        self.port = Port
        self.host = Host if Host else '127.0.0.1'
        self.Error = None

    def _generate_id(self):
        """Generate a cryptographically random client ID."""
        random.seed(time.time())
        length = random.randrange(37, 73)
        return secrets.token_urlsafe(length)

    def _build_auth_payload(self, payload):
        """Add name/identity to payload if configured."""
        if self.name or self.identity:
            payload['Name'] = self.name
            payload['Identity'] = self.identity
        return payload

    def talk(self, msg, casefold=True):
        """
        Send a message to the server and wait for response.
        
        NOT thread-safe. Opens a new TCP connection per call.
        
        Args:
            msg: Message to send (will be encoded)
            casefold: If True, lowercase the response
            
        Returns:
            Decoded response string, or None on error
        """
        self.Error = None
        try:
            payload = self.encoder(msg)
            conn = socket.create_connection((self.host, self.port), timeout=self.timeout)
            sfn = conn.makefile('rw', buffering=1)
            sfn.write(payload + '\n')
            sfn.flush()
            response = sfn.readline()
            sfn.close()
            conn.close()

            buf = self.decoder(response.strip())
            if buf:
                result = buf.strip()
                return result.lower() if casefold else result
            return None

        except (socket.timeout, OSError) as err:
            self.Error = str(err)
            return None

    def _retry(self, action, expire, casefold=True):
        """Send an action with automatic retries until valid response."""
        payload = {"ID": self.ID, "FileName": self.filename,
                   "Action": action, "Expire": str(expire)}
        self._build_auth_payload(payload)
        outbuf = json.dumps(ShuffleJSON(payload))

        retry = 0
        while True:
            buf = self.talk(outbuf, casefold)
            if buf is None:
                if retry > self.retryLimit:
                    return 'failure'
                retry += 1
                time.sleep(self.retrysleep)
            elif len(buf) > 0:
                try:
                    data = json.loads(buf)
                    key = 'status' if casefold else 'Status'
                    buf = data[key]
                except Exception:
                    buf = None
                if casefold and buf is not None:
                    buf = buf.lower()
                if buf is not None and buf in self.VALID_RESPONSES:
                    return buf
                time.sleep(self.retrysleep)
            else:
                time.sleep(self.retrysleep)

    def _retry_data(self, action, expire, data):
        """Send an action with data payload and automatic retries."""
        payload = {"ID": self.ID, "FileName": self.filename,
                   "Action": action, "Expire": str(expire), "DataStore": data}
        self._build_auth_payload(payload)
        outbuf = json.dumps(ShuffleJSON(payload))

        retry = 0
        while True:
            buf = self.talk(outbuf, casefold=False)
            if buf is None:
                if retry > self.retryLimit:
                    return 'failure'
                retry += 1
                time.sleep(self.retrysleep)
            elif len(buf) > 0:
                return buf
            else:
                time.sleep(self.retrysleep)

    # ── Public API ─────────────────────────────────────────────────────

    def Lock(self, expire=300):
        """
        Acquire an advisory lock. Retries automatically on failure.
        
        Args:
            expire: Lock TTL in seconds (default: 300)
        
        Returns:
            'locked', 'notowner', 'failure', or other status string
        """
        return self._retry("Lock", expire, casefold=True)

    def Unlock(self):
        """Release the advisory lock."""
        return self._retry("Unlock", 0)

    def IsLocked(self, expire=300):
        """
        Check lock status. Single-pass, no retry loop.
        Acquires the lock if it's free.
        
        Args:
            expire: Lock TTL if acquired (default: 300)
        
        Returns:
            Status string or 'failure'/'None' on error
        """
        payload = {"ID": self.ID, "FileName": self.filename,
                   "Action": "Lock", "Expire": str(expire)}
        self._build_auth_payload(payload)
        outbuf = json.dumps(payload)

        buf = self.talk(outbuf, casefold=True)
        if buf is None:
            return 'failure'
        try:
            data = json.loads(buf)
        except Exception:
            return None
        return data.get('status', None)

    def Put(self, expire, data):
        """
        Store data associated with this resource.
        
        Args:
            expire: Data TTL in seconds
            data: String data to store (will be encoded)
        
        Returns:
            Server response string
        """
        return self._retry_data("Put", expire, self.encoder(data))

    def Get(self):
        """
        Retrieve stored data for this resource.
        
        Returns:
            dict with server response, DataStore decoded if present.
            None on failure.
        """
        data = self._retry_data("Get", 0, None)
        try:
            jdata = json.loads(data)
        except Exception:
            return None

        if jdata is not None and 'DataStore' in jdata:
            jdata['DataStore'] = self.decoder(jdata['DataStore'])
            if isinstance(jdata['DataStore'], bytes):
                jdata['DataStore'] = jdata['DataStore'].decode('utf-8')
        return jdata

    def Erase(self):
        """Erase stored data for this resource."""
        return self._retry_data("Erase", 0, None)

    def Version(self):
        """
        Get server and client version string.
        
        Returns:
            String like 'JackrabbitDLM/0.0.0.2.830:0.0.0.1.580'
        """
        data = self._retry_data("Version", 0, None)
        sv = 'Error'
        try:
            data = json.loads(data)
        except Exception:
            pass
        if isinstance(data, dict) and 'ID' in data:
            sv = data['ID']
        return f"{sv}:{self.VERSION}"

    def IsDLM(self):
        """Check if a Jackrabbit DLM server is running and reachable."""
        v = self.Version()
        return 'JackrabbitDLM' in v
