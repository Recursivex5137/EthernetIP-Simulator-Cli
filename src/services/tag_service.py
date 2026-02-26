"""Business logic for tag operations"""

import logging
from typing import Dict, List, Optional
from ..database.tag_repository import TagRepository
from ..models.tag import Tag
from ..models.data_types import DataType


class TagService:
    """Business logic for tag operations"""

    def __init__(self, tag_repository: TagRepository):
        self.repository = tag_repository
        self.logger = logging.getLogger(__name__)
        self._cache: Dict[str, Tag] = {}
        self._id_index: Dict[int, str] = {}
        self._load_cache()

    def _load_cache(self):
        """Load all tags into cache on startup"""
        tags = self.repository.get_all()
        self._cache.clear()
        self._id_index.clear()
        for tag in tags:
            self._cache[tag.name] = tag
            if tag.tag_id is not None:
                self._id_index[tag.tag_id] = tag.name

    def create_tag(self, name: str, data_type: DataType, **kwargs) -> Tag:
        """Create a new tag"""
        is_array = kwargs.get('is_array', False)
        if 'value' not in kwargs:
            initial_value = None if is_array else data_type.default_value
        else:
            initial_value = kwargs['value']

        tag = Tag(
            tag_id=None,
            name=name,
            data_type=data_type,
            value=initial_value,
            description=kwargs.get('description', ''),
            is_array=is_array,
            array_dimensions=kwargs.get('array_dimensions'),
            udt_type_id=kwargs.get('udt_type_id')
        )

        if not tag.validate_name():
            raise ValueError(f"Invalid tag name: {name}. Must start with letter/underscore, contain only alphanumeric and underscores, and be <= 40 chars.")

        if self.repository.get_by_name(name):
            raise ValueError(f"Tag already exists: {name}")

        if not tag.validate_value():
            raise ValueError(f"Invalid value for data type {data_type.type_name}")

        tag = self.repository.create(tag)
        self._cache[tag.name] = tag
        if tag.tag_id is not None:
            self._id_index[tag.tag_id] = tag.name
        return tag

    def get_tag_by_id(self, tag_id: int) -> Optional[Tag]:
        """Get tag by ID (O(1) via secondary index)"""
        name = self._id_index.get(tag_id)
        if name and name in self._cache:
            return self._cache[name]
        tag = self.repository.get_by_id(tag_id)
        if tag:
            self._cache[tag.name] = tag
            if tag.tag_id is not None:
                self._id_index[tag.tag_id] = tag.name
        return tag

    def get_tag_by_name(self, name: str) -> Optional[Tag]:
        """Get tag by name (cached)"""
        if name in self._cache:
            return self._cache[name]
        tag = self.repository.get_by_name(name)
        if tag:
            self._cache[name] = tag
            if tag.tag_id is not None:
                self._id_index[tag.tag_id] = tag.name
        return tag

    def get_all_tags(self) -> List[Tag]:
        """Get all tags"""
        return list(self._cache.values())

    def update_tag(self, tag: Tag, allow_rename: bool = False) -> bool:
        """
        Update an existing tag.

        Args:
            tag: Tag object with updated values
            allow_rename: If True, allows changing the tag name

        Returns:
            True if successful, False otherwise
        """
        if not tag.tag_id:
            self.logger.error("Cannot update tag without tag_id")
            return False

        # Validate value
        if not tag.validate_value():
            self.logger.error(f"Invalid value for tag {tag.name}: {tag.value}")
            return False

        # If renaming, validate new name
        old_name = None
        if allow_rename:
            old_tag = self.get_tag_by_id(tag.tag_id)
            if old_tag and old_tag.name != tag.name:
                # Validate new name format
                if not tag.validate_name():
                    self.logger.error(f"Invalid tag name format: {tag.name}")
                    return False

                # Check new name doesn't conflict with another tag
                existing_tag = self.get_tag_by_name(tag.name)
                if existing_tag and existing_tag.tag_id != tag.tag_id:
                    self.logger.error(f"Tag name '{tag.name}' already exists")
                    return False

                # Remember old name to remove from cache
                old_name = old_tag.name

        # Update in database
        updated_tag = self.repository.update_full(tag, allow_rename=allow_rename)

        # Update cache
        if old_name and old_name != updated_tag.name:
            # Remove old name from cache
            self._cache.pop(old_name, None)

        # Add/update with new name
        self._cache[updated_tag.name] = updated_tag
        if updated_tag.tag_id is not None:
            self._id_index[updated_tag.tag_id] = updated_tag.name

        if old_name and old_name != updated_tag.name:
            self.logger.debug("Renamed tag: %s -> %s", old_name, updated_tag.name)
        else:
            self.logger.debug("Updated tag: %s", updated_tag.name)

        return True

    def update_tag_value(self, tag_name: str, new_value) -> bool:
        """Update tag value (called by server when external write occurs)"""
        tag = self.get_tag_by_name(tag_name)
        if not tag:
            return False

        # Clamp values to valid range instead of rejecting
        if tag.is_array and isinstance(new_value, list):
            new_value = [tag.data_type.clamp_value(v) for v in new_value]
        elif tag.data_type != tag.data_type.UDT:
            new_value = tag.data_type.clamp_value(new_value)

        old_value = tag.value
        tag.value = new_value

        if not tag.validate_value():
            tag.value = old_value
            return False

        self.repository.update(tag)
        self._cache[tag.name] = tag
        return True

    def delete_tag(self, tag_id: int) -> bool:
        """Delete a tag"""
        tag = self.get_tag_by_id(tag_id)
        if tag:
            self._cache.pop(tag.name, None)
            self._id_index.pop(tag.tag_id, None)
            return self.repository.delete(tag_id)
        return False

    def refresh_cache(self):
        """Reload cache from database"""
        self._load_cache()
