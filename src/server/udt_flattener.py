"""Flatten/unflatten UDT dict values to/from SINT byte arrays for cpppo storage."""

import struct
import logging
from typing import Any, List, Optional

from ..models.data_types import DataType

# struct format strings keyed by DataType type_name (little-endian)
_PACK_FMT = {
    "BOOL":  "b",
    "SINT":  "b",
    "INT":   "<h",
    "DINT":  "<i",
    "LINT":  "<q",
    "USINT": "B",
    "UINT":  "<H",
    "UDINT": "<I",
    "REAL":  "<f",
    "LREAL": "<d",
}


class UDTFlattener:
    """Converts between UDT dict representation and flat SINT byte arrays."""

    def __init__(self, udt_service):
        self.udt_service = udt_service
        self.logger = logging.getLogger(__name__)

    def get_flat_size(self, tag) -> int:
        """Total SINT byte count for one or more UDT instances."""
        udt_def = self._get_udt_def(tag)
        if not udt_def:
            return 0
        instance_size = udt_def.size_bytes
        if tag.is_array and isinstance(tag.value, list):
            return instance_size * len(tag.value)
        return instance_size

    def flatten_udt_value(self, tag) -> Optional[List[int]]:
        """Dict (or list-of-dicts) -> flat SINT byte list for cpppo."""
        udt_def = self._get_udt_def(tag)
        if not udt_def:
            return None

        if tag.is_array and isinstance(tag.value, list):
            result = []
            for instance in tag.value:
                result.extend(self._flatten_one(udt_def, instance))
            return result
        elif isinstance(tag.value, dict):
            return self._flatten_one(udt_def, tag.value)
        return None

    def unflatten_udt_value(self, flat_bytes, tag) -> Any:
        """Flat SINT byte list -> dict (or list-of-dicts) for UI/DB."""
        udt_def = self._get_udt_def(tag)
        if not udt_def:
            return tag.value

        instance_size = udt_def.size_bytes
        if instance_size == 0:
            return tag.value

        raw = bytes(b & 0xFF for b in flat_bytes)

        if tag.is_array and isinstance(tag.value, list):
            count = len(tag.value)
            result = []
            for i in range(count):
                start = i * instance_size
                end = start + instance_size
                chunk = raw[start:end] if end <= len(raw) else raw[start:].ljust(instance_size, b'\x00')
                result.append(self._unflatten_one(udt_def, chunk, tag.value[i]))
            return result
        elif isinstance(tag.value, dict):
            chunk = raw[:instance_size].ljust(instance_size, b'\x00')
            return self._unflatten_one(udt_def, chunk, tag.value)
        return tag.value

    # ── cpppo STRUCT_typed helpers ────────────────────────────────

    def build_cpppo_udt_type(self, udt_def, array_size=1):
        """Build a cpppo STRUCT_typed type definition dict for a UDT.

        Follows the same pattern as LOGIX_STRING_UDT_TYPE in enip_server.py.
        """
        internal_tags = {}
        attributes = []

        for member in udt_def.members:
            attributes.append(member.name)
            tag_info = {
                "offset": member.offset,
                "data_type": member.data_type.type_name,
                "tag_type": "atomic",
            }
            if member.is_array and member.array_dimensions:
                total_elems = 1
                for dim in member.array_dimensions:
                    total_elems *= dim
                tag_info["array"] = total_elems
            internal_tags[member.name] = tag_info

        structure_handle = 0x1000 + (udt_def.udt_id or 0)

        return {
            "name": udt_def.name,
            "data_type": {
                "name": udt_def.name,
                "template": {
                    "structure_handle": structure_handle,
                    "structure_size": udt_def.size_bytes,
                },
                "attributes": attributes,
                "internal_tags": internal_tags,
            },
            "dimensions": [array_size],
        }

    def dict_to_record(self, udt_def, instance_dict, parser_instance):
        """Convert a Python dict to a cpppo STRUCT_typed dotdict record."""
        from cpppo.dotdict import dotdict

        record_data = {}
        for member in udt_def.members:
            value = instance_dict.get(member.name, member.default_value)
            if member.is_array and isinstance(value, list):
                record_data[member.name] = list(value)
            else:
                if member.data_type == DataType.BOOL:
                    record_data[member.name] = 1 if value else 0
                elif member.data_type.python_type == int:
                    record_data[member.name] = int(value) if value is not None else 0
                elif member.data_type.python_type == float:
                    record_data[member.name] = float(value) if value is not None else 0.0
                else:
                    record_data[member.name] = value

        record = dotdict(record_data)
        record['data.input'] = b''
        parser_instance.produce(record)
        return record

    def record_to_dict(self, udt_def, record):
        """Convert a cpppo STRUCT_typed dotdict record back to a Python dict."""
        result = {}
        for member in udt_def.members:
            try:
                value = getattr(record, member.name, member.default_value)
                if member.data_type == DataType.BOOL:
                    if member.is_array and isinstance(value, (list, tuple)):
                        result[member.name] = [bool(v) for v in value]
                    else:
                        result[member.name] = bool(value)
                elif member.is_array and isinstance(value, (list, tuple)):
                    result[member.name] = [member.data_type.python_type(v) for v in value]
                else:
                    result[member.name] = member.data_type.python_type(value) if value is not None else member.default_value
            except Exception:
                result[member.name] = member.default_value
        return result

    # ── Internal helpers ──────────────────────────────────────────

    def _get_udt_def(self, tag):
        if not tag.udt_type_id:
            return None
        return self.udt_service.get_udt_by_id(tag.udt_type_id)

    def _flatten_one(self, udt_def, instance_dict):
        """Flatten a single UDT instance dict into a byte list."""
        buf = bytearray(udt_def.size_bytes)
        if not isinstance(instance_dict, dict):
            return list(buf)

        for member in udt_def.members:
            fmt = _PACK_FMT.get(member.data_type.type_name)
            if not fmt:
                continue

            value = instance_dict.get(member.name, member.default_value)
            offset = member.offset

            if member.is_array and isinstance(value, list):
                elem_size = member.data_type.size_bytes
                for j, elem in enumerate(value):
                    pos = offset + j * elem_size
                    if pos + elem_size <= len(buf):
                        self._pack_into(buf, fmt, pos, elem, member.data_type)
            else:
                if offset + member.data_type.size_bytes <= len(buf):
                    self._pack_into(buf, fmt, offset, value, member.data_type)

        return list(buf)

    def _unflatten_one(self, udt_def, raw_bytes, template_dict):
        """Unflatten raw bytes into a UDT dict, using template_dict for structure."""
        result = {}
        for member in udt_def.members:
            fmt = _PACK_FMT.get(member.data_type.type_name)
            if not fmt:
                result[member.name] = template_dict.get(member.name, member.default_value)
                continue

            offset = member.offset
            elem_size = member.data_type.size_bytes

            if member.is_array and member.array_dimensions:
                total_elems = 1
                for dim in member.array_dimensions:
                    total_elems *= dim
                arr = []
                for j in range(total_elems):
                    pos = offset + j * elem_size
                    if pos + elem_size <= len(raw_bytes):
                        arr.append(self._unpack_from(raw_bytes, fmt, pos, member.data_type))
                    else:
                        arr.append(member.data_type.default_value)
                result[member.name] = arr
            else:
                if offset + elem_size <= len(raw_bytes):
                    result[member.name] = self._unpack_from(raw_bytes, fmt, offset, member.data_type)
                else:
                    result[member.name] = template_dict.get(member.name, member.default_value)

        return result

    @staticmethod
    def _pack_into(buf, fmt, offset, value, data_type):
        try:
            if data_type == DataType.BOOL:
                value = 1 if value else 0
            elif data_type.python_type == int:
                value = int(value)
            elif data_type.python_type == float:
                value = float(value)
            struct.pack_into(fmt, buf, offset, value)
        except (struct.error, ValueError, TypeError):
            pass

    @staticmethod
    def _unpack_from(raw_bytes, fmt, offset, data_type):
        try:
            val = struct.unpack_from(fmt, raw_bytes, offset)[0]
            if data_type == DataType.BOOL:
                return bool(val)
            return val
        except (struct.error, ValueError):
            return data_type.default_value
