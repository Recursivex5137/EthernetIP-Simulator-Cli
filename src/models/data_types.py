"""EthernetIP/CIP data type definitions matching Studio 5000 standard types"""

from enum import Enum


class DataType(Enum):
    """EthernetIP/CIP data types"""
    BOOL = ("BOOL", 0xC1, 1, bool)        # Boolean
    SINT = ("SINT", 0xC2, 1, int)         # Short Int (-128 to 127)
    INT = ("INT", 0xC3, 2, int)           # Integer (-32768 to 32767)
    DINT = ("DINT", 0xC4, 4, int)         # Double Int
    LINT = ("LINT", 0xC5, 8, int)         # Long Int
    USINT = ("USINT", 0xC6, 1, int)       # Unsigned Short Int (0 to 255)
    UINT = ("UINT", 0xC7, 2, int)         # Unsigned Int (0 to 65535)
    UDINT = ("UDINT", 0xC8, 4, int)       # Unsigned Double Int
    REAL = ("REAL", 0xCA, 4, float)       # 32-bit Float
    LREAL = ("LREAL", 0xCB, 8, float)     # 64-bit Float
    STRING = ("STRING", 0xD0, 88, str)    # String (82 chars + header)
    UDT = ("UDT", 0xA0, 0, object)        # User Defined Type

    def __init__(self, type_name, cip_code, size_bytes, python_type):
        self.type_name = type_name
        self.cip_code = cip_code
        self.size_bytes = size_bytes
        self.python_type = python_type

    @property
    def default_value(self):
        """Get default value for this type"""
        if self == DataType.BOOL:
            return False
        elif self in (DataType.SINT, DataType.INT, DataType.DINT, DataType.LINT,
                      DataType.USINT, DataType.UINT, DataType.UDINT):
            return 0
        elif self in (DataType.REAL, DataType.LREAL):
            return 0.0
        elif self == DataType.STRING:
            return ""
        return None

    @property
    def min_value(self):
        """Get minimum value for this type"""
        if self == DataType.SINT:
            return -128
        elif self == DataType.INT:
            return -32768
        elif self == DataType.DINT:
            return -2147483648
        elif self == DataType.LINT:
            return -9223372036854775808
        elif self in (DataType.USINT, DataType.UINT, DataType.UDINT):
            return 0
        return None

    @property
    def max_value(self):
        """Get maximum value for this type"""
        if self == DataType.SINT:
            return 127
        elif self == DataType.INT:
            return 32767
        elif self == DataType.DINT:
            return 2147483647
        elif self == DataType.LINT:
            return 9223372036854775807
        elif self == DataType.USINT:
            return 255
        elif self == DataType.UINT:
            return 65535
        elif self == DataType.UDINT:
            return 4294967295
        return None

    def validate_value(self, value) -> bool:
        """Validate if a value is appropriate for this data type"""
        try:
            if self == DataType.BOOL:
                return isinstance(value, bool) or value in (0, 1)
            elif self in (DataType.SINT, DataType.INT, DataType.DINT, DataType.LINT,
                          DataType.USINT, DataType.UINT, DataType.UDINT):
                if not isinstance(value, int):
                    return False
                if self.min_value is not None and value < self.min_value:
                    return False
                if self.max_value is not None and value > self.max_value:
                    return False
                return True
            elif self in (DataType.REAL, DataType.LREAL):
                return isinstance(value, (int, float))
            elif self == DataType.STRING:
                return isinstance(value, str) and len(value) <= 82
            return True
        except Exception:
            return False

    def clamp_value(self, value):
        """Clamp a value to the valid range for this data type.

        Returns the value unchanged for types without numeric bounds
        (STRING, UDT, REAL, LREAL).
        """
        if self == DataType.BOOL:
            return bool(value)
        if self.min_value is not None and isinstance(value, (int, float)):
            if value < self.min_value:
                return self.min_value
            if value > self.max_value:
                return self.max_value
            if isinstance(value, float) and self in (
                DataType.SINT, DataType.INT, DataType.DINT, DataType.LINT,
                DataType.USINT, DataType.UINT, DataType.UDINT,
            ):
                return int(value)
        return value

    def __str__(self):
        return self.type_name

    def __repr__(self):
        return f"DataType.{self.name}"


# Constant tuple for all integer data types (used for validation and parsing)
INTEGER_TYPES = (
    DataType.SINT, DataType.INT, DataType.DINT, DataType.LINT,
    DataType.USINT, DataType.UINT, DataType.UDINT
)
