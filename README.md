# EthernetIP Simulator

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-green.svg)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/UI-PySide6%20(Qt6)-orange.svg)](https://doc.qt.io/qtforpython/)

A virtual PLC simulator that implements the **EthernetIP/CIP protocol**, allowing **Studio 5000**, **RSLogix**, and other SCADA systems to connect for testing and development -- **no physical hardware required**.

Built for automation engineers, integrators, and developers who need a quick way to test EthernetIP communications without a real PLC.

---

## Quick Start

**Option A -- Run from source:**

```bash
git clone https://github.com/imdtouch/EthernetIP-Simulator.git
cd EthernetIP-Simulator
python main.py
```

Dependencies install automatically on first run. If that fails, run `pip install -r requirements.txt` manually.

**Option B -- Run the pre-built executable (Windows):**

Download `EthernetIP_Simulator.exe` from this repository and run it directly. No Python installation needed.

---

## Features

- **Virtual PLC Server** -- Simulates an EthernetIP device on port 44818 that accepts connections from SCADA software
- **Tag Management** -- Create, edit, and delete tags with inline editing, undo/redo, and context menus
- **All Standard Data Types** -- BOOL, SINT, INT, DINT, LINT, USINT, UINT, UDINT, REAL, LREAL, STRING
- **Arrays** -- Single and multi-dimensional array support
- **User Defined Types (UDTs)** -- Define complex data structures with custom members
- **Modern Dark UI** -- Built with PySide6 (Qt6) with a dark industrial theme
- **Persistent Storage** -- Tags persist between sessions via SQLite
- **Auto-Install** -- Dependencies are installed automatically on first run

## Requirements

- **Python 3.8+** (not needed if using the `.exe`)
- **Windows 10/11** (recommended) or Linux
- Internet connection for initial dependency installation

## How to Use

### 1. Create Tags

1. Click **"Add Tag"** in the Tag Management panel
2. Set the tag name, data type, and optional initial value
3. Click **"Create Tag"**

Tag names must start with a letter or underscore and contain only alphanumeric characters and underscores (standard PLC naming rules).

### 2. Start the Server

1. Click **"Start Server"** in the Server Control panel
2. The status indicator turns green when the server is running
3. Note the IP address and port (default: **44818**)

### 3. Connect from Studio 5000 / RSLogix

1. Open your Studio 5000 project
2. In **I/O Configuration**, add a new **Ethernet Module**
3. Set the **IP Address** to the one shown in the simulator's Server Control panel
4. Set **Port** to `44818` and **Slot** to `0`
5. Download to the PLC and browse **Controller Tags** -- your simulator tags will appear
6. You can now read and write tag values between Studio 5000 and the simulator

### Editing Tags

- **Double-click** a value cell to edit inline
- **BOOL tags** toggle on double-click
- **Ctrl+Z** / **Ctrl+Y** to undo/redo value changes
- **Right-click** for context menu (Copy Name, Copy Value, Delete)

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+Q | Exit application |
| F12 | Capture screenshot & submit feedback |
| Ctrl+Z | Undo tag value edit |
| Ctrl+Y | Redo tag value edit |

## Supported Data Types

| Type | Description | Range / Size |
|--------|---------------------------|--------------------------------------|
| BOOL | Boolean | True / False |
| SINT | Short Integer (8-bit) | -128 to 127 |
| INT | Integer (16-bit) | -32,768 to 32,767 |
| DINT | Double Integer (32-bit) | -2,147,483,648 to 2,147,483,647 |
| LINT | Long Integer (64-bit) | 64-bit signed |
| USINT | Unsigned Short Integer | 0 to 255 |
| UINT | Unsigned Integer | 0 to 65,535 |
| UDINT | Unsigned Double Integer | 0 to 4,294,967,295 |
| REAL | 32-bit Float | IEEE 754 single precision |
| LREAL | 64-bit Float | IEEE 754 double precision |
| STRING | Character String | Up to 82 characters |

## Project Structure

```
EthernetIP-Simulator/
├── main.py                       # Entry point (auto-installs dependencies)
├── requirements.txt              # Python dependencies
├── EthernetIP_Simulator.exe      # Pre-built Windows executable
│
├── src/
│   ├── models/                   # Data models (Tag, UDT, DataType)
│   ├── database/                 # SQLite persistence (thread-safe)
│   ├── services/                 # Business logic with caching
│   ├── server/                   # EthernetIP/CIP server (cpppo)
│   ├── ui/                       # PySide6 interface & dialogs
│   └── feedback/                 # Screenshot annotation system
│
├── build/                        # PyInstaller build scripts
└── data/                         # Runtime data (created automatically)
```

## Architecture

The codebase follows a layered architecture:

| Layer | Responsibility |
|------------|--------------------------------------------------------|
| **Models** | Data structures (Tag, UDT, DataType enums) |
| **Database** | SQLite persistence with thread-safe, lock-protected cursors |
| **Services** | Business logic with O(1) cached tag lookups |
| **Server** | EthernetIP/CIP communication via cpppo (thread-safe) |
| **UI** | PySide6 dark-themed interface |

## Troubleshooting

### Application won't start
- Verify Python 3.8+ is installed: `python --version`
- Try manual dependency install: `pip install -r requirements.txt`

### Server won't start
- Check if port 44818 is already in use by another application
- Verify your firewall allows traffic on port 44818
- On Windows, see `WINDOWS_SOCKET_GUIDE.md` for port management tips

### Studio 5000 can't connect
- Confirm the server status shows "Running" (green indicator)
- Make sure the IP address in Studio 5000 matches what the simulator displays
- If testing on the same machine, try `127.0.0.1`
- Check that both machines are on the same network

### Tags not appearing in Studio 5000
- Create tags **before** starting the server
- After adding new tags, restart the server
- In Studio 5000, re-download the configuration

## Contributing

Contributions are welcome! To contribute:

1. Fork this repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m "Add my feature"`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

For bugs or feature requests, please [open an issue](../../issues).

## License

This project is licensed under the [MIT License](LICENSE).

## Version History

### v2.0.0 (Current)
- Complete UI rewrite from CustomTkinter to PySide6 (Qt6)
- Dark industrial theme with sortable, resizable columns
- Right-click context menus and inline tag value editing
- Undo/redo support (Ctrl+Z / Ctrl+Y)
- F12 screenshot annotation and feedback system
- Thread-safe database and server operations
- O(1) tag lookup via secondary cache index
- Removed 6 unused dependencies for a leaner install

### v1.0.0
- Initial release with EthernetIP server, tag management, array support, and CustomTkinter UI
