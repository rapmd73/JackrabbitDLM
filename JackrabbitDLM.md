## Section 1 - Non-Technical Description

This program acts as a central coordinator for managing access to shared resources and storing associated information. It listens for requests from users, processes these requests to either grant or revoke access to resources, and stores or retrieves data linked to those resources. The program keeps track of who has access to what and for how long, ensuring that only authorized users can perform specific actions. It also maintains a record of its own operational statistics and logs important events for monitoring.

## Section 2 - Technical Analysis

The Python script `JackrabbitDLM` implements a distributed lock manager (DLM) and a simple key-value store. It operates as a server, listening on a specified network port for incoming client connections. The server is configured to bind to an empty host string (meaning all available network interfaces) and a default port of 37373, though these can be overridden by command-line arguments.

The program initializes several global variables: `Version` stores the software version, `BaseDirectory` and `LogDirectory` define file system paths, `Statistics` is a dictionary to track operational metrics, and `Locker` is a dictionary that serves as the primary data structure for managing locks and data.

Two utility functions are defined: `WritePID(port)` writes the process ID to a file named `<port>.pid` in the `LogDirectory`, and `WriteLog(msg)` appends a timestamped log message to `JackrabbitDLM.log` within the `LogDirectory`. The `jsonStatus` function is a helper to construct JSON-formatted responses, including a status message, an optional ID, and potentially a tag and data payload.

The core logic resides in the `ProcessPayload(data)` function. This function takes a string `data` as input, which is expected to be a JSON payload. It first attempts to parse the JSON. If parsing fails, it increments the `BadPayload` statistic and returns an error. If parsing succeeds, it checks for the presence of required keys: `FileName`, `Action`, `ID`, and `Expire`. If any are missing, it again returns a `BadPayload` error.

The `ProcessPayload` function then handles different `Action` types (case-insensitive):

*   **`lock`**: If the `FileName` is not in `Locker`, a new lock is created with the provided `ID` and an expiration time calculated by adding `Expire` (converted to float) to the current time. If the lock exists and has expired, it's updated with the new `ID` and expiration. If the existing lock's owner matches the `ID` from the payload, the expiration time is reset. Otherwise, a `NotOwner` status is returned.
*   **`unlock`**: If the `FileName` exists in `Locker` and the `ID` matches the lock owner, the lock's expiration is set to 0, effectively marking it for removal. If the `FileName` does not exist or the `ID` does not match, appropriate statistics are updated, and an `Unlocked` or `NotOwner` status is returned.
*   **`get`**: If the `FileName` exists and the `ID` matches the owner, it attempts to return the associated `DataStore` value. If `DataStore` is not present, a `NoData` status is returned. Otherwise, `NotFound` or `NotOwner` statuses are returned.
*   **`put`**: This action is used to store or update data. If the `FileName` does not exist, a new entry is created in `Locker` with the `ID`, `Expire` time, and `DataStore` value. If the `FileName` exists and the `ID` matches the owner, the `Expire` time and `DataStore` are updated. Otherwise, a `NotOwner` status is returned.
*   **`erase`**: If the `FileName` exists and the `ID` matches the owner, the `Expire` time is set to 0 and `DataStore` is set to `None`, marking the entry for cleanup. Otherwise, `NotFound` or `NotOwner` statuses are returned.

If the `Action` is not recognized, a `BadAction` status is returned.

The `main()` function orchestrates the server's operation. It logs the version, parses optional host and port arguments from `sys.argv`, and calls `WritePID`. It then sets up a TCP socket, binds it to the specified host and port, and begins listening for incoming connections. The `select.select` function is used in a `while True` loop to monitor sockets for readability and writability, with a timeout of 30 seconds.

When new connections arrive (`fds is lockerSocket`), they are accepted, set to non-blocking, added to the `inputs` list (which tracks active sockets), and a corresponding entry is created in the `dataStore` dictionary to buffer incoming data.

When data is received on an existing socket (`fds is not lockerSocket`), it's appended to the buffer in `dataStore`. If the received data ends with a newline character (`\n`), the accumulated data is processed by `ProcessPayload`, and the resulting JSON response is stored in the `queue` dictionary, keyed by the client socket.

If a socket is ready for writing (`outfds`), the program sends the queued response from `queue[fds]` to the client. After sending, the response is removed from the queue, and the connection might be closed if an error occurs during sending.

Periodically, the program iterates through the `Locker` dictionary to clean up expired locks and data. Entries whose `Expire` time is in the past are removed. Statistics for active locks (`ALock`) and active data entries (`AData`) are updated.

Every hour, or when the hour changes, the current `Statistics` dictionary is logged, and the `Statistics` dictionary is reset. `gc.collect()` is called to trigger garbage collection for memory management. The program continues to loop indefinitely, handling network events and managing locks/data.