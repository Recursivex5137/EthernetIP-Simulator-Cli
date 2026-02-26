# Windows Socket & Port Management Guide

Learnings from debugging WinError 10048 on industrial protocol servers (EthernetIP, Modbus TCP, raw Ethernet). Applies to any Python application binding TCP/UDP server sockets on Windows.

## Common Ports

| Protocol       | Default Port | Transport |
|---------------|-------------|-----------|
| EthernetIP/CIP | 44818       | TCP + UDP |
| Modbus TCP     | 502         | TCP       |
| OPC UA         | 4840        | TCP       |
| PROFINET       | 34962-34964 | TCP + UDP |

---

## Problem: WinError 10048 (WSAEADDRINUSE)

`[WinError 10048] Only one usage of each socket address (protocol/network address/port) is normally permitted`

This occurs when `bind()` is called on a port that is already in use. On Windows, this is harder to resolve than Linux due to fundamental differences in socket option behavior.

---

## Key Difference: SO_REUSEADDR on Windows vs Linux

| Behavior | Linux | Windows |
|----------|-------|---------|
| Bind to TIME_WAIT port | Allowed with SO_REUSEADDR | **NOT allowed** |
| Bind while another socket is LISTENING | Blocked | **Allowed** with SO_REUSEADDR (port hijacking!) |
| Default TIME_WAIT duration | 60s | 120s |

**Critical**: On Windows, `SO_REUSEADDR` does the opposite of what you expect. It does NOT help with reusing a port after a crash. It DOES allow a second process to hijack your port silently.

### Implications for Port Availability Checks

A bind-based port check with `SO_REUSEADDR` on Windows will **always report the port as free**, even when another process is actively listening. This makes it useless as a pre-check.

```python
# BAD on Windows - always returns True
def is_port_available_WRONG(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', port))  # succeeds even if port is in use!
    s.close()
    return True

# BETTER on Windows - connect-based check
def is_port_available(port):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(('127.0.0.1', port))
        s.close()
        return False  # something is listening
    except (ConnectionRefusedError, OSError, socket.timeout):
        return True   # nothing listening
```

**Caveat**: The connect-based check has a blind spot — it cannot detect ports held in TIME_WAIT or by a crashed process whose socket is bound but not listening. For full reliability, handle bind failures with retries (see below).

---

## Root Causes of Port Lock on Windows

### 1. Zombie Processes (most common)

When a Python app is killed (terminal closed, Task Manager, Ctrl+C not handled), daemon threads holding sockets are killed without cleanup. The OS may hold the port for **minutes**.

**Detection**:
```powershell
# Find what holds a port
Get-NetTCPConnection -LocalPort 44818
Get-NetUDPEndpoint -LocalPort 44818

# Or with netstat
netstat -ano -p TCP | findstr :44818
```

**Fix**: Kill the zombie process on startup.
```python
import os, subprocess, sys

def kill_port_holder(port):
    if sys.platform != 'win32':
        return
    my_pid = os.getpid()
    result = subprocess.run(
        ['netstat', '-ano', '-p', 'TCP'],
        capture_output=True, text=True, timeout=5,
    )
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        if not parts[1].endswith(f':{port}'):
            continue
        try:
            pid = int(parts[-1])
        except ValueError:
            continue
        if pid == my_pid or pid == 0:
            continue
        subprocess.run(['taskkill', '/F', '/PID', str(pid)],
                       capture_output=True, timeout=5)
```

### 2. Hung Daemon Threads (in-process)

Libraries like `cpppo` spawn daemon threads for client connections and UDP handlers. When the main server socket is closed, these threads may hang in `select()`, `recv()`, or `accept()`, keeping their socket FDs alive.

**Fix**: Force-kill threads with `ctypes` to make them release sockets.
```python
import ctypes, threading

def force_kill_daemon_threads(exclude_thread=None):
    targets = [
        t for t in threading.enumerate()
        if t.daemon and t.is_alive()
        and t != threading.current_thread()
        and t != exclude_thread
    ]
    for thread in targets:
        ctypes.pythonapi.PyThreadState_SetAsyncExc(
            ctypes.c_ulong(thread.ident),
            ctypes.py_object(SystemExit),
        )
    for thread in targets:
        thread.join(timeout=1.0)
```

### 3. TIME_WAIT State (OS-level)

After a TCP connection is closed, Windows holds the port in TIME_WAIT for ~120 seconds. Unlike Linux, `SO_REUSEADDR` does NOT bypass this.

**Fix**: Force garbage collection to close lingering socket objects, then poll until the port is free.
```python
import gc, time

def wait_for_port_release(port, timeout=5.0):
    gc.collect()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_port_available(port):
            return True
        time.sleep(0.25)
    return False
```

---

## Recommended Server Stop Sequence (Windows)

```
1. Signal the server to stop (event flag, control dict, etc.)
2. Wait briefly for graceful shutdown (2s)
3. Force-kill any lingering daemon threads (ctypes SystemExit injection)
4. Wait for server thread to finish (it can now close sockets since sub-threads are dead)
5. gc.collect() to release any orphaned socket objects
6. Poll until port is confirmed free (up to 5s)
```

---

## Recommended Server Start Sequence (Windows)

```
1. Kill any zombie process holding the port (netstat + taskkill)
2. Start the server thread
3. If bind fails with 10048:
   a. Kill zombie processes again
   b. Wait 2 seconds
   c. Retry (up to 3 attempts)
```

---

## Prevention: atexit Handler

Always register an `atexit` handler to stop the server on exit. This covers cases where the window is closed or `sys.exit()` is called without triggering UI cleanup.

```python
import atexit

def init_server(server):
    def cleanup():
        try:
            if server.is_running:
                server.stop()
        except Exception:
            pass
    atexit.register(cleanup)
```

---

## Protocol-Specific Notes

### EthernetIP (port 44818)
- `cpppo` binds **both TCP and UDP** to port 44818
- The UDP handler thread is the most common cause of hanging — it blocks in `select.select()` indefinitely
- Both sockets must be released before the port is free

### Modbus TCP (port 502)
- Port 502 is a privileged port on some systems — may need admin rights
- `pymodbus` and `pyModbusTCP` typically only use TCP
- Simpler cleanup since there's no UDP component

### General
- Always use `daemon=True` for server threads so they don't block process exit
- But remember: daemon threads are killed without running `finally` blocks on process exit
- The combination of daemon threads + atexit handler gives the best of both worlds

---

## Diagnostic Commands (PowerShell)

```powershell
# What's using a specific port?
Get-NetTCPConnection -LocalPort 44818 | Format-Table LocalAddress,LocalPort,State,OwningProcess
Get-NetUDPEndpoint -LocalPort 44818 | Format-Table LocalAddress,LocalPort,OwningProcess

# What process is that PID?
Get-Process -Id <PID> | Format-Table Name,Id,Path

# Kill it
Stop-Process -Id <PID> -Force

# Check TIME_WAIT duration (registry)
Get-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters' -Name TcpTimedWaitDelay -ErrorAction SilentlyContinue

# Reduce TIME_WAIT to 30 seconds (requires admin + reboot)
Set-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters' -Name TcpTimedWaitDelay -Value 30 -Type DWord
```
