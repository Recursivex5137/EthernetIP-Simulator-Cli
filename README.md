# EthernetIP Simulator CLI

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-green.svg)](https://www.python.org/)
[![Mode-CLI%20Only-orange](https://img.shields.io/badge/Mode-CLI%20Only-orange)](#current-direction)

CLI-first EthernetIP/CIP virtual PLC simulator for edge/lab network testing.

This repository is a fork of the upstream simulator with a different direction:
- Headless CLI operation is the primary product.
- TUI is a future aspiration, not implemented yet.
- GUI workflows are not the focus of this fork.

## Current Direction

Current state:
- Supported: CLI (`sim_cli.py`)
- Not shipped yet: TUI
- Legacy code still exists from upstream, but this fork targets CLI deployment and automation.

## Quick Start

```bash
git clone git@github.com:Recursivex5137/EthernetIP-Simulator-Cli.git
cd EthernetIP-Simulator-Cli
./deploy/setup-headless.sh
```

Optional seed:

```bash
./.venv/bin/python sim_cli.py tags import --file examples/tags-sample.json
```

Start simulator:

```bash
./.venv/bin/python sim_cli.py serve --host 0.0.0.0 --port 44818
```

## CLI Commands

```bash
# Help
python sim_cli.py --help
python sim_cli.py tags --help

# List tags
python sim_cli.py tags list

# Add scalar tag
python sim_cli.py tags add --name BatchCount --type DINT --value 0

# Add array tag
python sim_cli.py tags add --name BeanPercentages --type REAL --array-dim 3 --value "[40.0,35.0,25.0]"

# Update existing tag
python sim_cli.py tags set --name BatchCount --value 42

# Delete tag
python sim_cli.py tags delete --name BatchCount

# Import tag definitions
python sim_cli.py tags import --file examples/tags-sample.json
```

## Serve Mode

```bash
python sim_cli.py serve --host 0.0.0.0 --port 44818 --status-interval 10
```

Behavior:
- Foreground process (Ctrl+C to stop)
- Live tag values are snapshotted back to SQLite at shutdown
- Uses default DB path `data/tags.db` unless `--db-path` is provided

## Systemd Deployment

Service template:
- `deploy/ethernetip-simulator-cli.service`

Typical install:

```bash
sudo mkdir -p /var/lib/ethernetip-simulator
sudo cp deploy/ethernetip-simulator-cli.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ethernetip-simulator-cli
sudo systemctl status ethernetip-simulator-cli --no-pager
```

Edit `User`, `Group`, and `WorkingDirectory` in the service file before enabling it.

## Tag Import Format

`sim_cli.py tags import --file tags.json` accepts:
1. A top-level JSON list of tag objects, or
2. A JSON object with a `tags` list.

Each tag object supports:
- `name` (required)
- `type` or `data_type` (required, e.g. `BOOL`, `DINT`, `REAL`, `STRING`)
- `value` (optional)
- `description` (optional)
- `array_dimensions` (optional, list of positive integers)
- `is_array` (optional, bool)
- `udt_type_id` (optional, for UDT tags)

## TUI Roadmap (Aspirational)

Planned (not implemented):
- Live tag table in terminal
- Interactive tag edit workflow
- Server status panel
- Read/write activity stream

This section is roadmap only. Current deliverable remains CLI.

## Project Layout

```text
EthernetIP-Simulator-Cli/
├── sim_cli.py
├── requirements-headless.txt
├── deploy/
│   ├── setup-headless.sh
│   └── ethernetip-simulator-cli.service
├── examples/
│   └── tags-sample.json
└── src/
```

## License

MIT License. See [LICENSE](LICENSE).
