#!/usr/bin/env python3
"""Headless CLI for EthernetIP Simulator."""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from src.database.config_repository import ConfigRepository
from src.database.db_manager import DBManager
from src.database.tag_repository import TagRepository
from src.database.udt_repository import UDTRepository
from src.models.data_types import DataType
from src.server.enip_server import EthernetIPServer
from src.server.tag_provider import TagProvider
from src.services.config_service import ConfigService
from src.services.tag_service import TagService
from src.services.udt_service import UDTService

LOGGER = logging.getLogger("sim_cli")


@dataclass
class AppContext:
    db_manager: DBManager
    tag_service: TagService
    udt_service: UDTService
    config_service: ConfigService


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def build_context(db_path: str) -> AppContext:
    db_manager = DBManager(db_path)
    tag_repository = TagRepository(db_manager)
    udt_repository = UDTRepository(db_manager)
    config_repository = ConfigRepository(db_manager)

    return AppContext(
        db_manager=db_manager,
        tag_service=TagService(tag_repository),
        udt_service=UDTService(udt_repository),
        config_service=ConfigService(config_repository),
    )


def parse_data_type(raw: str) -> DataType:
    try:
        return DataType[raw.strip().upper()]
    except KeyError as exc:
        allowed = ", ".join(dt.name for dt in DataType)
        raise ValueError(f"Unsupported data type '{raw}'. Allowed: {allowed}") from exc


def parse_bool(raw: Any) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        if raw in (0, 1):
            return bool(raw)
        raise ValueError("BOOL only accepts 0/1 or true/false")
    if isinstance(raw, str):
        value = raw.strip().lower()
        if value in {"1", "true", "t", "yes", "y", "on"}:
            return True
        if value in {"0", "false", "f", "no", "n", "off"}:
            return False
    raise ValueError(f"Invalid BOOL value: {raw!r}")


def parse_scalar_value(data_type: DataType, raw: Any) -> Any:
    if data_type == DataType.BOOL:
        return parse_bool(raw)
    if data_type in {
        DataType.SINT,
        DataType.INT,
        DataType.DINT,
        DataType.LINT,
        DataType.USINT,
        DataType.UINT,
        DataType.UDINT,
    }:
        if isinstance(raw, int) and not isinstance(raw, bool):
            return data_type.clamp_value(raw)
        if isinstance(raw, str):
            return data_type.clamp_value(int(raw, 0))
        raise ValueError(f"{data_type.name} expects an integer, got {type(raw).__name__}")
    if data_type in {DataType.REAL, DataType.LREAL}:
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            return float(raw)
        if isinstance(raw, str):
            return float(raw)
        raise ValueError(f"{data_type.name} expects a float, got {type(raw).__name__}")
    if data_type == DataType.STRING:
        text = str(raw)
        if len(text) > 82:
            raise ValueError("STRING length must be <= 82 characters")
        return text
    if data_type == DataType.UDT:
        if isinstance(raw, dict):
            return raw
        raise ValueError("UDT value must be a JSON object")
    return raw


def parse_dimensions(raw_dims: Optional[list[int]]) -> Optional[list[int]]:
    if not raw_dims:
        return None
    dims = []
    for dim in raw_dims:
        if dim <= 0:
            raise ValueError("Array dimensions must be positive integers")
        dims.append(dim)
    return dims


def total_elements(dimensions: Optional[list[int]]) -> Optional[int]:
    if not dimensions:
        return None
    total = 1
    for dim in dimensions:
        total *= dim
    return total


def parse_value_for_tag(
    data_type: DataType,
    raw_value: Any,
    is_array: bool,
    dimensions: Optional[list[int]],
) -> Any:
    if raw_value is None:
        return None

    if is_array:
        if isinstance(raw_value, str):
            parsed = json.loads(raw_value)
        else:
            parsed = raw_value
        if not isinstance(parsed, list):
            raise ValueError("Array tag value must be a JSON list")
        values = [parse_scalar_value(data_type, item) for item in parsed]
        expected = total_elements(dimensions)
        if expected is not None and len(values) != expected:
            raise ValueError(
                f"Array element count mismatch: expected {expected}, got {len(values)}"
            )
        return values

    return parse_scalar_value(data_type, raw_value)


def serialize_tag(tag: Any) -> dict[str, Any]:
    return {
        "tag_id": tag.tag_id,
        "name": tag.name,
        "data_type": tag.data_type.name,
        "value": tag.value,
        "description": tag.description,
        "is_array": tag.is_array,
        "array_dimensions": tag.array_dimensions,
        "udt_type_id": tag.udt_type_id,
    }


def load_tag_specs(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("tags"), list):
        return payload["tags"]
    raise ValueError("Tag file must be a JSON array or an object with a 'tags' list")


def apply_tag_spec(
    tag_service: TagService,
    spec: dict[str, Any],
    replace_existing: bool,
) -> str:
    name = spec["name"]
    data_type = parse_data_type(spec.get("data_type", spec.get("type", "")))

    dims_raw = spec.get("array_dimensions", spec.get("dimensions"))
    dims = parse_dimensions(dims_raw)
    is_array = bool(spec.get("is_array", False)) or bool(dims)

    value = parse_value_for_tag(
        data_type=data_type,
        raw_value=spec.get("value"),
        is_array=is_array,
        dimensions=dims,
    )

    description = spec.get("description", "")
    udt_type_id = spec.get("udt_type_id")

    existing = tag_service.get_tag_by_name(name)
    if existing is None:
        tag_service.create_tag(
            name=name,
            data_type=data_type,
            value=value,
            description=description,
            is_array=is_array,
            array_dimensions=dims,
            udt_type_id=udt_type_id,
        )
        return "created"

    if not replace_existing:
        return "skipped"

    requires_recreate = (
        existing.data_type != data_type
        or existing.is_array != is_array
        or existing.array_dimensions != dims
        or existing.udt_type_id != udt_type_id
    )

    if requires_recreate:
        tag_service.delete_tag(existing.tag_id)
        tag_service.create_tag(
            name=name,
            data_type=data_type,
            value=value,
            description=description,
            is_array=is_array,
            array_dimensions=dims,
            udt_type_id=udt_type_id,
        )
        return "recreated"

    if value is not None:
        existing.value = value
    existing.description = description
    tag_service.update_tag(existing, allow_rename=False)
    return "updated"


def cmd_tags_list(args: argparse.Namespace) -> int:
    ctx = build_context(args.db_path)
    try:
        tags = sorted(ctx.tag_service.get_all_tags(), key=lambda tag: tag.name.lower())
        if args.format == "json":
            print(json.dumps([serialize_tag(tag) for tag in tags], indent=2))
            return 0

        if not tags:
            print("No tags found.")
            return 0

        for tag in tags:
            value_repr = json.dumps(tag.value) if isinstance(tag.value, (dict, list)) else repr(tag.value)
            dims = f" dims={tag.array_dimensions}" if tag.array_dimensions else ""
            print(
                f"{tag.name:<30} {tag.data_type.name:<7} "
                f"{'array' if tag.is_array else 'scalar':<6}{dims} value={value_repr}"
            )
        return 0
    finally:
        ctx.db_manager.close()


def cmd_tags_add(args: argparse.Namespace) -> int:
    ctx = build_context(args.db_path)
    try:
        data_type = parse_data_type(args.data_type)
        dims = parse_dimensions(args.array_dim)
        is_array = bool(dims)

        value = parse_value_for_tag(
            data_type=data_type,
            raw_value=args.value,
            is_array=is_array,
            dimensions=dims,
        )

        tag = ctx.tag_service.create_tag(
            name=args.name,
            data_type=data_type,
            value=value,
            description=args.description or "",
            is_array=is_array,
            array_dimensions=dims,
            udt_type_id=args.udt_type_id,
        )
        print(f"Created tag {tag.name} ({tag.data_type.name})")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    finally:
        ctx.db_manager.close()


def cmd_tags_set(args: argparse.Namespace) -> int:
    ctx = build_context(args.db_path)
    try:
        tag = ctx.tag_service.get_tag_by_name(args.name)
        if tag is None:
            print(f"ERROR: Tag not found: {args.name}", file=sys.stderr)
            return 2

        value = parse_value_for_tag(
            data_type=tag.data_type,
            raw_value=args.value,
            is_array=tag.is_array,
            dimensions=tag.array_dimensions,
        )
        ok = ctx.tag_service.update_tag_value(args.name, value)
        if not ok:
            print(f"ERROR: Failed to update tag: {args.name}", file=sys.stderr)
            return 2

        print(f"Updated tag {args.name}")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    finally:
        ctx.db_manager.close()


def cmd_tags_delete(args: argparse.Namespace) -> int:
    ctx = build_context(args.db_path)
    try:
        tag = ctx.tag_service.get_tag_by_name(args.name)
        if tag is None:
            print(f"ERROR: Tag not found: {args.name}", file=sys.stderr)
            return 2
        ok = ctx.tag_service.delete_tag(tag.tag_id)
        if not ok:
            print(f"ERROR: Failed to delete tag: {args.name}", file=sys.stderr)
            return 2
        print(f"Deleted tag {args.name}")
        return 0
    finally:
        ctx.db_manager.close()


def cmd_tags_import(args: argparse.Namespace) -> int:
    ctx = build_context(args.db_path)
    try:
        specs = load_tag_specs(Path(args.file))
        created = updated = recreated = skipped = 0

        for idx, spec in enumerate(specs, start=1):
            try:
                action = apply_tag_spec(ctx.tag_service, spec, args.replace_existing)
                if action == "created":
                    created += 1
                elif action == "updated":
                    updated += 1
                elif action == "recreated":
                    recreated += 1
                else:
                    skipped += 1
            except Exception as exc:
                print(f"ERROR: spec #{idx} ({spec.get('name', '<unnamed>')}): {exc}", file=sys.stderr)
                return 2

        print(
            f"Import complete. created={created} updated={updated} "
            f"recreated={recreated} skipped={skipped}"
        )
        return 0
    finally:
        ctx.db_manager.close()


def cmd_serve(args: argparse.Namespace) -> int:
    ctx = build_context(args.db_path)
    server: Optional[EthernetIPServer] = None

    stop_event = threading.Event()

    def _signal_handler(signum: int, _frame: Any) -> None:
        LOGGER.info("Received signal %s, stopping server...", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    try:
        if args.seed_file:
            specs = load_tag_specs(Path(args.seed_file))
            for spec in specs:
                apply_tag_spec(ctx.tag_service, spec, args.replace_existing)

        host = args.host if args.host else ctx.config_service.get_server_address()
        port = args.port if args.port is not None else ctx.config_service.get_server_port()

        ip_valid, ip_error = ctx.config_service.validate_ip(host)
        if not ip_valid:
            print(f"ERROR: {ip_error}", file=sys.stderr)
            return 2

        port_valid, port_error = ctx.config_service.validate_port(port)
        if not port_valid:
            print(f"ERROR: {port_error}", file=sys.stderr)
            return 2

        # Persist the chosen host/port so CLI and GUI stay aligned.
        ctx.config_service.set_server_config(host, port)

        tag_provider = TagProvider(ctx.tag_service, ctx.udt_service)
        server = EthernetIPServer(
            tag_provider=tag_provider,
            address=host,
            port=port,
            udt_service=ctx.udt_service,
        )

        LOGGER.info("Starting EthernetIP server on %s:%s", host, port)
        server.start()

        deadline = time.time() + args.ready_timeout
        while time.time() < deadline:
            err, err_code = server.get_last_error()
            if err:
                print(f"ERROR: server failed to start: {err} (errno={err_code})", file=sys.stderr)
                return 2
            if server.tags_ready:
                break
            time.sleep(0.1)

        if not server.tags_ready:
            print("ERROR: server did not become ready in time", file=sys.stderr)
            return 2

        print(
            f"Server running at {host}:{port} with "
            f"{len(ctx.tag_service.get_all_tags())} tag(s). Press Ctrl+C to stop."
        )

        last_status_log = time.monotonic()
        while not stop_event.wait(timeout=0.5):
            if args.status_interval <= 0:
                continue
            now = time.monotonic()
            if now - last_status_log >= args.status_interval:
                live_count = len(server.read_all_tag_values())
                LOGGER.info("server=running tags=%d", live_count)
                last_status_log = now

        return 0
    except KeyboardInterrupt:
        stop_event.set()
        print("Interrupted, shutting down...")
        return 130
    finally:
        if server and server.is_running:
            try:
                snap_count = server.snapshot_live_values()
                LOGGER.info("Persisted %d tag value(s) before shutdown", snap_count)
                server.stop()
                print("Server stopped.")
            except Exception as exc:
                LOGGER.error("Error during server shutdown: %s", exc, exc_info=True)
        ctx.db_manager.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="EthernetIP Simulator CLI (headless mode)",
    )
    parser.add_argument(
        "--db-path",
        default="data/tags.db",
        help="SQLite DB path (default: data/tags.db)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser("serve", help="Start EthernetIP server in foreground")
    serve.add_argument("--host", help="Bind host/IP (default: saved config or 0.0.0.0)")
    serve.add_argument("--port", type=int, help="Bind port (default: saved config or 44818)")
    serve.add_argument(
        "--seed-file",
        help="Optional JSON file with tags to import before server start",
    )
    serve.add_argument(
        "--replace-existing",
        action="store_true",
        help="When used with --seed-file, replace matching existing tags",
    )
    serve.add_argument(
        "--ready-timeout",
        type=float,
        default=5.0,
        help="Seconds to wait for server startup (default: 5)",
    )
    serve.add_argument(
        "--status-interval",
        type=float,
        default=15.0,
        help="Emit periodic status logs every N seconds (0 to disable)",
    )
    serve.set_defaults(func=cmd_serve)

    tags = subparsers.add_parser("tags", help="Manage tags from CLI")
    tags_sub = tags.add_subparsers(dest="tags_command", required=True)

    tags_list = tags_sub.add_parser("list", help="List all tags")
    tags_list.add_argument(
        "--format",
        choices=("table", "json"),
        default="table",
        help="Output format",
    )
    tags_list.set_defaults(func=cmd_tags_list)

    tags_add = tags_sub.add_parser("add", help="Add a new tag")
    tags_add.add_argument("--name", required=True, help="Tag name")
    tags_add.add_argument("--type", dest="data_type", required=True, help="Data type (e.g. DINT, REAL, STRING)")
    tags_add.add_argument(
        "--value",
        help="Initial value (for arrays, provide JSON list)",
    )
    tags_add.add_argument(
        "--array-dim",
        type=int,
        action="append",
        help="Array dimensions. Repeat for multi-dimensional arrays.",
    )
    tags_add.add_argument("--description", help="Optional description")
    tags_add.add_argument("--udt-type-id", type=int, help="UDT ID when --type UDT")
    tags_add.set_defaults(func=cmd_tags_add)

    tags_set = tags_sub.add_parser("set", help="Set an existing tag value")
    tags_set.add_argument("--name", required=True, help="Tag name")
    tags_set.add_argument(
        "--value",
        required=True,
        help="New value (for arrays, provide JSON list)",
    )
    tags_set.set_defaults(func=cmd_tags_set)

    tags_delete = tags_sub.add_parser("delete", help="Delete a tag")
    tags_delete.add_argument("--name", required=True, help="Tag name")
    tags_delete.set_defaults(func=cmd_tags_delete)

    tags_import = tags_sub.add_parser("import", help="Import tags from JSON")
    tags_import.add_argument("--file", required=True, help="Path to JSON file")
    tags_import.add_argument(
        "--replace-existing",
        action="store_true",
        help="Replace existing tags if names collide",
    )
    tags_import.set_defaults(func=cmd_tags_import)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    configure_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
