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
# or
./.venv/bin/python sim_cli.py tags import --file examples/tags-sample.yaml
# or
./.venv/bin/python sim_cli.py tags import --file examples/tags-sample.xml
```

Start simulator:

```bash
./.venv/bin/python sim_cli.py serve --host 0.0.0.0 --port 44818
```

## Docker Deployment

Build image:

```bash
docker build -t ethernetip-simulator-cli:latest .
```

Run container:

```bash
mkdir -p data-docker
docker run -d --name ethernetip-simulator-cli \
  --restart unless-stopped \
  -p 44818:44818/tcp -p 44818:44818/udp \
  -v "$(pwd)/data-docker:/data" \
  ethernetip-simulator-cli:latest
```

Seed tags in Docker-managed DB:

```bash
docker run --rm \
  -v "$(pwd)/data-docker:/data" \
  -v "$(pwd)/examples:/app/examples:ro" \
  ethernetip-simulator-cli:latest \
  --db-path /data/tags.db tags import --file /app/examples/tags-sample.json
```

Use `tags-sample.yaml` or `tags-sample.xml` the same way.

Compose alternative:

```bash
docker compose up -d --build
docker compose logs -f
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
python sim_cli.py tags import --file examples/tags-sample.yaml
python sim_cli.py tags import --file examples/tags-sample.xml
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

`sim_cli.py tags import --file <file>` supports:
1. `JSON` (`.json`): top-level list, or object with `tags` list
2. `YAML` (`.yaml` / `.yml`): top-level list, or object with `tags` list
3. `XML` (`.xml`): root `<tags>` containing `<tag>` entries

Each tag object supports:
- `name` (required)
- `type` or `data_type` (required, e.g. `BOOL`, `DINT`, `REAL`, `STRING`)
- `value` (optional)
- `description` (optional)
- `array_dimensions` (optional, list of positive integers)
- `is_array` (optional, bool)
- `udt_type_id` (optional, for UDT tags)

For XML:
- Array dimensions can be provided as nested elements:
  `<array_dimensions><dim>3</dim></array_dimensions>`
- Array values can be provided as nested items:
  `<value><item>40.0</item><item>35.0</item></value>`

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
├── Dockerfile
├── docker-compose.yml
├── sim_cli.py
├── requirements-headless.txt
├── deploy/
│   ├── setup-headless.sh
│   └── ethernetip-simulator-cli.service
├── examples/
│   ├── tags-sample.json
│   ├── tags-sample.yaml
│   └── tags-sample.xml
└── src/
```

## License

MIT License. See [LICENSE](LICENSE).
