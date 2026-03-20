# JackrabbitDLM: High-Performance Lightweight Distributed Lock Manager

**JackrabbitDLM** is a professional-grade, zero-dependency Distributed Lock Manager (DLM) and volatile state coordinator, engineered for high-concurrency environments where coordinating distributed resources requires speed, simplicity, absolute data privacy, and a minimal footprint.

As a high-performance alternative to heavy-duty coordinators like Redis, Etcd, or ZooKeeper, JackrabbitDLM utilizes a **"Blind Vault"** architecture and standard JSON-over-TCP protocol to provide **advisory locking** and **shared state management** while acting as a neutral arbiter that never sees or stores your raw data in plain text.

## 🚀 Key Features

*   **High Contention Resilience:** Built to handle "lock fighting" where multiple nodes compete for the same resource simultaneously.
*   **Fully Customizable Serialization:** **User-replaceable Encoders and Decoders** allow you to implement your own compression, encryption, or serialization formats.
*   **Zero Dependencies:** Runs on standard Python 3.x libraries. No external database or complex configuration required.
*   **Volatile KV Store:** Integrated "Put/Get" functionality to share state, counters, or configurations across a network.
*   **Production-Grade Stability:** Includes 1MB payload protections, automatic server-side Garbage Collection, and detailed hourly performance analytics.

## 🔐 Customizable Encoding & Decoding

One of JackrabbitDLM's most powerful features is the ability to swap the data transport layer. While it includes a high-speed, table-based default encoder, you can inject your own functions to handle specific needs like **AES encryption, Zlib compression, or MsgPack serialization.**

### Using a Custom Encoder/Decoder

Simply pass your functions into the `Locker` constructor:

```python
import base64
from JackrabbitDLM import Locker

# Define a custom Base64 encoder/decoder
def my_encoder(data):
    return base64.b64encode(data.encode()).decode()

def my_decoder(data):
    return base64.b64decode(data.encode()).decode()

# Initialize with custom logic
mem = Locker("SecureState", Encoder=my_encoder, Decoder=my_decoder)

# Data is now automatically processed by your custom functions during Put/Get

mem.Put(data="Sensitive Information", expire=60)
```

## 🛠 Usage & Implementation

### 1. Launch the Server

The server manages the state and enforces lock ownership.

```bash
python3 JackrabbitDLM [host] [port]
```

*Default port: 37373. Includes memory exhaustion protection (Max 1MB per payload).*

### 2. Implementation Styles

The Python library supports different operational modes depending on your performance needs:

#### **A. Patient Locking (Automatic Retries)**

Ideal for background workers. The library handles the "wait" for you.

```python
lock = Locker("Worker_01", Retry=7, RetrySleep=1)
if lock.Lock(expire=30) == 'locked':
    try:
        # Critical Section
    finally:
        lock.Unlock()
```

#### **B. Aggressive Polling (Non-Blocking)**

Ideal for high-speed loops. Check the lock and move on immediately if the resource is busy.

```python
# No retries, single-pass check
if lock.IsLocked(expire=10) == 'locked':
    # Do work
    lock.Unlock()
```

#### **C. Shared State (Atomic Put/Get)**

Manage a global counter or state string across multiple distributed PIDs.

```python
# Get current state
state = mem.Get()
count = int(state['DataStore']) if 'DataStore' in state else 0

# Increment and update
mem.Put(data=str(count + 1), expire=60)
```

## 📊 Reliability & Monitoring

The server automatically generates a `JackrabbitDLM.log` with hourly statistics to help you tune your distributed system:
*   **ALock / AData:** Current active locks and memory objects.
*   **NotOwner:** Collision detection (when a node tries to hijack a lock it doesn't own).
*   **DataOverrun:** Blocks attempts to send payloads larger than 1MB.
*   **ForcedGC:** Logs when the server triggers internal garbage collection to keep the memory footprint lean.

## 📡 Protocol Specification

For implementation in **Go, Rust, or Node.js**, communicate via TCP using newline-delimited JSON:

| Action | Payload Requirement |
| :--- | :--- |
| **Lock** | `{ "ID": "...", "FileName": "...", "Action": "Lock", "Expire": "300" }` |
| **Put** | `{ "ID": "...", "FileName": "...", "Action": "Put", "DataStore": "...", "Expire": "300" }` |
| **Get** | `{ "ID": "...", "FileName": "...", "Action": "Get" }` |

## 📊 Distributed Lock Manager (DLM) Comparison

| Product | Architecture | Data Visibility (Server-Side) | Serialization | Why Jackrabbit DLM is Superior |
| :--- | :--- | :--- | :--- | :--- |
| **Jackrabbit DLM** | **Lightweight TCP** | **ZERO Visibility (Blind)** | **User-Swappable** | **Privacy & Stealth:** Data is never plain-text. User-swappable encoders allow for AES-256 or custom logic. The server is a "Blind Vault" by design. |
| **Redis (Redlock)** | KV Store | **Full Visibility** (Plain Text) | Fixed | **No Data Exposure:** Redis logs your data in plain text. Jackrabbit ensures a server compromise reveals nothing but encoded blobs. |
| **ZooKeeper** | Distributed Tree | **Full Visibility** (Plain Text) | Fixed | **Ultra-Lightweight:** No JVM required. Jackrabbit is a single-file script with built-in anti-hijacking and ownership protections. |
| **Etcd** | Distributed KV | **High Visibility** | Fixed GRPC | **Customizable Transport:** Etcd is a binary "black box." Jackrabbit lets you swap your own encryption logic in 2 lines of code. |
| **PostgreSQL** | Relational DB | **Full Visibility** | SQL Literals | **Performance:** DB locks are slow and leave plain-text traces in logs. Jackrabbit is volatile, memory-resident, and strictly private. |

## 🛡️ Security & Guardrails

JackrabbitDLM is built to withstand both buggy clients and malicious environments:
*   **Ownership Enforcement:** Prevents "hijacking." Only the `ID` that created a lock can release or modify it.
*   **1MB Payload Limit:** Prevents memory exhaustion and "leaching" attacks on the server.
*   **Self-Healing TTL:** All locks and data have a mandatory Time-To-Live. If a client crashes, the resource is automatically freed.
*   **Collision Logging:** The server logs `NotOwner` errors when a process attempts unauthorized access, serving as a built-in IDS.

## 🤝 Community & Support
*   **Wiki:** [Jackrabbit DLM Wiki](https://github.com/rapmd73/JackrabbitDLM/wiki)
*   **Developer:** [Rose Heart (rapmd73)](https://github.com/rapmd73)
*   **Discord Support:** [Join the Jackrabbit Ecosystem](https://discord.gg/6m44mV9)
*   **Patreon:** [Support Development](https://www.patreon.com/RD3277)

