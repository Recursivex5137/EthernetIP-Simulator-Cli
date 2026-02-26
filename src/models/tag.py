"""Tag data model representing a PLC tag"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, List
from .data_types import DataType


@dataclass
class Tag:
    """Represents a PLC tag"""
    tag_id: Optional[int]
    name: str
    data_type: DataType
    value: Any
    description: str = ""
    is_array: bool = False
    array_dimensions: Optional[List[int]] = None
    udt_type_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

        # Initialize array if needed
        if self.is_array and self.value is None:
            if self.array_dimensions:
                total_elements = 1
                for dim in self.array_dimensions:
                    total_elements *= dim
                self.value = [self.data_type.default_value] * total_elements
            else:
                self.value = []

        # Set default value if none provided and not an array
        if not self.is_array and self.value is None:
            self.value = self.data_type.default_value

    def validate_name(self) -> bool:
        """Validate tag name follows PLC naming rules"""
        if not self.name:
            return False
        if not self.name[0].isalpha() and self.name[0] != '_':  # Must start with letter or underscore
            return False
        if not all(c.isalnum() or c == '_' for c in self.name):
            return False
        if len(self.name) > 40:  # Studio 5000 limit
            return False
        return True

    def validate_value(self) -> bool:
        """Validate that the current value matches the data type"""
        if self.is_array:
            if not isinstance(self.value, list):
                return False
            # Validate each element in the array
            return all(self.data_type.validate_value(v) for v in self.value)
        else:
            return self.data_type.validate_value(self.value)

    def to_dict(self) -> dict:
        """Convert tag to dictionary for serialization"""
        return {
            'tag_id': self.tag_id,
            'name': self.name,
            'data_type': self.data_type.type_name,
            'value': self.value,
            'description': self.description,
            'is_array': self.is_array,
            'array_dimensions': self.array_dimensions,
            'udt_type_id': self.udt_type_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    @staticmethod
    def from_dict(data: dict) -> 'Tag':
        """Create tag from dictionary"""
        return Tag(
            tag_id=data.get('tag_id'),
            name=data['name'],
            data_type=DataType[data['data_type']],
            value=data.get('value'),
            description=data.get('description', ''),
            is_array=data.get('is_array', False),
            array_dimensions=data.get('array_dimensions'),
            udt_type_id=data.get('udt_type_id'),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else None
        )

    def __str__(self):
        return f"Tag({self.name}, {self.data_type.type_name}, {self.value})"

    def __repr__(self):
        return self.__str__()
