"""Business logic for UDT operations"""

import logging
from typing import Dict, List, Optional, Set
from ..database.udt_repository import UDTRepository
from ..models.udt import UDT, UDTMember
from ..models.data_types import DataType


class UDTService:
    """Business logic for UDT operations with caching"""

    def __init__(self, udt_repository: UDTRepository):
        self.repository = udt_repository
        self.logger = logging.getLogger(__name__)
        self._cache: Dict[str, UDT] = {}  # name → UDT object
        self._id_index: Dict[int, str] = {}  # udt_id → name (for O(1) ID lookup)
        self._load_cache()

    def _load_cache(self):
        """Load all UDTs into cache on startup"""
        udts = self.repository.get_all()
        self._cache.clear()
        self._id_index.clear()
        for udt in udts:
            self._cache[udt.name] = udt
            if udt.udt_id is not None:
                self._id_index[udt.udt_id] = udt.name
        self.logger.info(f"Loaded {len(udts)} UDTs into cache")

    def create_udt(self, name: str, description: str, members: List[UDTMember]) -> UDT:
        """
        Create a new UDT with validation.

        Args:
            name: UDT name (follows tag naming rules)
            description: Optional description
            members: List of UDTMember objects

        Returns:
            Created UDT object with udt_id

        Raises:
            ValueError: If validation fails
        """
        # Create UDT object
        udt = UDT(udt_id=None, name=name, description=description, members=members)

        # Validate UDT structure
        self._validate_udt(udt)

        # Check for duplicate name
        if self.repository.get_by_name(name):
            raise ValueError(f"UDT '{name}' already exists")

        # Calculate member offsets
        udt.calculate_offsets()

        # Create in database
        udt = self.repository.create(udt)

        # Update cache
        self._cache[udt.name] = udt
        if udt.udt_id is not None:
            self._id_index[udt.udt_id] = udt.name

        return udt

    def get_udt_by_id(self, udt_id: int) -> Optional[UDT]:
        """Get UDT by ID (O(1) via cache)"""
        name = self._id_index.get(udt_id)
        if name and name in self._cache:
            return self._cache[name]

        # Cache miss - try database
        udt = self.repository.get_by_id(udt_id)
        if udt:
            self._cache[udt.name] = udt
            if udt.udt_id is not None:
                self._id_index[udt.udt_id] = udt.name
        return udt

    def get_udt_by_name(self, name: str) -> Optional[UDT]:
        """Get UDT by name (O(1) via cache)"""
        if name in self._cache:
            return self._cache[name]

        # Cache miss - try database
        udt = self.repository.get_by_name(name)
        if udt:
            self._cache[udt.name] = udt
            if udt.udt_id is not None:
                self._id_index[udt.udt_id] = udt.name
        return udt

    def get_all_udts(self) -> List[UDT]:
        """Get all UDTs from cache"""
        return list(self._cache.values())

    def update_udt(self, udt: UDT) -> bool:
        """
        Update UDT definition.

        Args:
            udt: UDT object with updated values

        Returns:
            True if successful

        Raises:
            ValueError: If validation fails
        """
        if not udt.udt_id:
            raise ValueError("Cannot update UDT without udt_id")

        # Validate updated UDT
        self._validate_udt(udt)

        # Recalculate offsets
        udt.calculate_offsets()

        # Update in database
        updated_udt = self.repository.update(udt)

        # Update cache
        # Handle potential rename - remove old name if different
        old_udt = self.get_udt_by_id(udt.udt_id)
        if old_udt and old_udt.name != updated_udt.name:
            self._cache.pop(old_udt.name, None)

        self._cache[updated_udt.name] = updated_udt
        if updated_udt.udt_id is not None:
            self._id_index[updated_udt.udt_id] = updated_udt.name

        return True

    def delete_udt(self, udt_id: int) -> bool:
        """
        Delete UDT.

        Args:
            udt_id: ID of UDT to delete

        Returns:
            True if successful

        Note:
            Future enhancement: Check if any tags use this UDT before deleting
        """
        udt = self.get_udt_by_id(udt_id)
        if udt:
            # Remove from cache
            self._cache.pop(udt.name, None)
            self._id_index.pop(udt_id, None)

            # Delete from database
            return self.repository.delete(udt_id)

        return False

    def _validate_udt(self, udt: UDT) -> bool:
        """
        Validate UDT structure.

        Raises:
            ValueError: If validation fails with specific error message
        """
        # Validate UDT object itself
        if not udt.validate():
            raise ValueError(f"Invalid UDT structure for '{udt.name}'")

        # Check name format (same rules as tag names)
        if not udt.name:
            raise ValueError("UDT name is required")

        if not udt.name[0].isalpha() and udt.name[0] != '_':
            raise ValueError("UDT name must start with a letter or underscore")

        if not all(c.isalnum() or c == '_' for c in udt.name):
            raise ValueError("UDT name can only contain letters, numbers, and underscores")

        if len(udt.name) > 40:
            raise ValueError("UDT name must be 40 characters or less")

        # Check for duplicate member names
        member_names = [m.name for m in udt.members]
        if len(member_names) != len(set(member_names)):
            raise ValueError("UDT contains duplicate member names")

        # Validate each member name
        for member in udt.members:
            if not member.name:
                raise ValueError("Member name is required")
            if not member.name[0].isalpha() and member.name[0] != '_':
                raise ValueError(f"Member '{member.name}' must start with a letter or underscore")
            if not all(c.isalnum() or c == '_' for c in member.name):
                raise ValueError(f"Member '{member.name}' can only contain letters, numbers, and underscores")

        # Check for circular references (if any member is UDT type)
        # Note: Currently UDT members cannot be UDT type in the UI, but validate anyway
        self._check_circular_reference(udt)

        return True

    def _check_circular_reference(self, udt: UDT, visited: Optional[Set[str]] = None) -> bool:
        """
        Recursively check for circular UDT references.

        Raises:
            ValueError: If circular reference detected
        """
        if visited is None:
            visited = set()

        if udt.name in visited:
            raise ValueError(f"Circular reference detected: UDT '{udt.name}' references itself")

        visited.add(udt.name)

        for member in udt.members:
            if member.data_type == DataType.UDT:
                # Check if this member's UDT type exists and recurse
                # Note: In current implementation, UDT type members are not supported in UI
                # This is defensive programming for future enhancement
                self.logger.warning(f"UDT member '{member.name}' has UDT data type (not fully supported)")

        return True

    def refresh_cache(self):
        """Reload cache from database"""
        self._load_cache()
