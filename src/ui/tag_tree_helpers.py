"""Shared helpers for tag tree building, refresh, and value formatting."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QBrush, QColor
from .theme import COLORS
from ..models.data_types import DataType

# Data roles for QStandardItem.data() / .setData()
ROLE_TAG_ID = Qt.UserRole
ROLE_ELEM_INDEX = Qt.UserRole + 1
ROLE_MEMBER_NAME = Qt.UserRole + 2
ROLE_UDT_ARRAY_INDEX = Qt.UserRole + 3
ROLE_BIT_INDEX = Qt.UserRole + 4

# Display limit for array children (performance guard)
MAX_ARRAY_DISPLAY = 200


def _type_name(data_type):
    """Accept DataType enum or string, return type_name string."""
    if isinstance(data_type, DataType):
        return data_type.type_name
    return str(data_type)


def format_display_value(value, data_type, *, is_udt_instance=False, max_len=50):
    """
    Format a single value for tree display.

    Args:
        value: The raw value to format.
        data_type: DataType enum member or type_name string.
        is_udt_instance: If True and value is a dict, show "{N members}".
        max_len: Truncation length for string display.
    """
    if is_udt_instance:
        if isinstance(value, dict):
            return f"{{{len(value)} members}}"
        return f"{{invalid: {type(value).__name__}}}"

    if isinstance(value, list):
        return f"{{{len(value)}}}"

    dt = _type_name(data_type)
    if dt == "BOOL":
        return str(bool(value))
    if dt in ("REAL", "LREAL") and isinstance(value, float):
        return f"{value:.6f}".rstrip('0').rstrip('.')
    return str(value)[:max_len]


def apply_bool_styling(value_item, value, data_type):
    """Apply BOOL on/off color styling. No-op for non-BOOL types."""
    if _type_name(data_type) != "BOOL":
        return
    if value:
        value_item.setBackground(QBrush(QColor(COLORS['bool_on_bg'])))
        value_item.setForeground(QBrush(QColor(COLORS['bool_on_fg'])))
    else:
        value_item.setBackground(QBrush(QColor(COLORS['bool_off_bg'])))
        value_item.setForeground(QBrush(QColor(COLORS['bool_off_fg'])))


def lookup_member_data_type(udt_service, tag, member_name):
    """
    Look up the DataType for a named UDT member.

    Returns DataType.DINT as fallback if not found.
    """
    if tag.udt_type_id:
        udt_def = udt_service.get_udt_by_id(tag.udt_type_id)
        if udt_def:
            for m in udt_def.members:
                if m.name == member_name:
                    return m.data_type
    return DataType.DINT


def lookup_member_type_name(udt_service, tag, member_name):
    """Look up the type_name string for a named UDT member."""
    return lookup_member_data_type(udt_service, tag, member_name).type_name


def resolve_udt_member_value(live_value, member_name, udt_array_index=None):
    """
    Navigate UDT value structure to extract a member's current value.

    For scalar UDT:  live_value[member_name]
    For array UDT:   live_value[udt_array_index][member_name]

    Returns the member value, or None if not resolvable.
    """
    if udt_array_index is not None and isinstance(live_value, list):
        if 0 <= udt_array_index < len(live_value) and isinstance(live_value[udt_array_index], dict):
            return live_value[udt_array_index].get(member_name)
    elif isinstance(live_value, dict):
        return live_value.get(member_name)
    return None


def resolve_udt_member_array_element(live_value, member_name, elem_index, udt_array_index=None):
    """
    Navigate to a specific array element within a UDT member.

    For scalar UDT:  live_value[member_name][elem_index]
    For array UDT:   live_value[udt_array_index][member_name][elem_index]

    Returns (element_value, found: bool).
    """
    member_array = resolve_udt_member_value(live_value, member_name, udt_array_index)
    if isinstance(member_array, list) and 0 <= elem_index < len(member_array):
        return member_array[elem_index], True
    return None, False


def create_truncation_row(total_count, displayed_count):
    """
    Create the '... N more elements' placeholder row.

    Returns list of 4 QStandardItems, or None if no truncation needed.
    """
    if total_count <= displayed_count:
        return None
    more_item = QStandardItem(f"... {total_count - displayed_count} more elements")
    more_item.setEditable(False)
    more_item.setForeground(QBrush(QColor(COLORS['text_disabled'])))
    return [more_item, QStandardItem(""), QStandardItem(""), QStandardItem("")]
