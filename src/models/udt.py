"""UDT (User Defined Type) data models"""

from dataclasses import dataclass, field
from typing import List, Any, Optional
from .data_types import DataType


@dataclass
class UDTMember:
    """Member of a User Defined Type"""
    name: str
    data_type: DataType
    offset: int = 0
    is_array: bool = False
    array_dimensions: Optional[List[int]] = None
    default_value: Any = None

    def __post_init__(self):
        if self.default_value is None:
            if self.is_array and self.array_dimensions:
                total_elements = 1
                for dim in self.array_dimensions:
                    total_elements *= dim
                self.default_value = [self.data_type.default_value] * total_elements
            else:
                self.default_value = self.data_type.default_value

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'name': self.name,
            'data_type': self.data_type.type_name,
            'offset': self.offset,
            'is_array': self.is_array,
            'array_dimensions': self.array_dimensions,
            'default_value': self.default_value
        }

    @staticmethod
    def from_dict(data: dict) -> 'UDTMember':
        """Create from dictionary"""
        return UDTMember(
            name=data['name'],
            data_type=DataType[data['data_type']],
            offset=data.get('offset', 0),
            is_array=data.get('is_array', False),
            array_dimensions=data.get('array_dimensions'),
            default_value=data.get('default_value')
        )


@dataclass
class UDT:
    """User Defined Type definition"""
    udt_id: Optional[int]
    name: str
    description: str
    members: List[UDTMember] = field(default_factory=list)

    @property
    def size_bytes(self) -> int:
        """Calculate total size of UDT in bytes"""
        if not self.members:
            return 0
        last_member = self.members[-1]
        member_size = last_member.data_type.size_bytes
        if last_member.is_array and last_member.array_dimensions:
            for dim in last_member.array_dimensions:
                member_size *= dim
        return last_member.offset + member_size

    def add_member(self, member: UDTMember):
        """Add a member to the UDT"""
        # Calculate offset for new member
        if self.members:
            last_member = self.members[-1]
            last_size = last_member.data_type.size_bytes
            if last_member.is_array and last_member.array_dimensions:
                for dim in last_member.array_dimensions:
                    last_size *= dim
            member.offset = last_member.offset + last_size
        else:
            member.offset = 0

        self.members.append(member)

    def remove_member(self, name: str) -> bool:
        """Remove a member by name"""
        for i, member in enumerate(self.members):
            if member.name == name:
                self.members.pop(i)
                # Recalculate offsets for remaining members
                self.calculate_offsets()
                return True
        return False

    def calculate_offsets(self):
        """Calculate byte offsets for each member"""
        current_offset = 0
        for member in self.members:
            member.offset = current_offset
            size = member.data_type.size_bytes
            if member.is_array and member.array_dimensions:
                for dim in member.array_dimensions:
                    size *= dim
            current_offset += size

    def validate(self) -> bool:
        """Validate UDT definition"""
        if not self.name:
            return False
        if not self.name[0].isalpha() and self.name[0] != '_':
            return False
        if not all(c.isalnum() or c == '_' for c in self.name):
            return False

        # Check for duplicate member names
        member_names = [m.name for m in self.members]
        if len(member_names) != len(set(member_names)):
            return False

        # Check for circular references (UDT containing itself)
        # This would require checking nested UDTs, simplified for now

        return True

    def to_dict(self) -> dict:
        """Export UDT definition to dictionary"""
        return {
            'udt_id': self.udt_id,
            'name': self.name,
            'description': self.description,
            'members': [m.to_dict() for m in self.members],
            'size_bytes': self.size_bytes
        }

    def to_json(self) -> dict:
        """Export UDT definition to JSON-serializable dict"""
        return {
            'name': self.name,
            'description': self.description,
            'members': [m.to_dict() for m in self.members]
        }

    @staticmethod
    def from_dict(data: dict) -> 'UDT':
        """Create UDT from dictionary"""
        members = [UDTMember.from_dict(m) for m in data.get('members', [])]
        return UDT(
            udt_id=data.get('udt_id'),
            name=data['name'],
            description=data.get('description', ''),
            members=members
        )

    def __str__(self):
        return f"UDT({self.name}, {len(self.members)} members, {self.size_bytes} bytes)"

    def __repr__(self):
        return self.__str__()
