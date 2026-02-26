"""Database repository for tag CRUD operations"""

import pickle
import json
import logging
from typing import Any, List, Optional
from .db_manager import DBManager
from ..models.tag import Tag
from ..models.data_types import DataType


class TagRepository:
    """Database operations for tags"""

    def __init__(self, db_manager: DBManager):
        self.db = db_manager
        self.logger = logging.getLogger(__name__)

    def create(self, tag: Tag) -> Tag:
        """Insert new tag into database"""
        with self.db.get_cursor() as cursor:
            cursor.execute('''
                INSERT INTO tags (name, data_type, value_blob, description,
                                is_array, array_dimensions, udt_type_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                tag.name,
                tag.data_type.type_name,
                pickle.dumps(tag.value),
                tag.description,
                1 if tag.is_array else 0,
                json.dumps(tag.array_dimensions) if tag.array_dimensions else None,
                tag.udt_type_id
            ))
            tag.tag_id = cursor.lastrowid
        return tag

    def get_by_id(self, tag_id: int) -> Optional[Tag]:
        """Retrieve tag by ID"""
        with self.db.get_cursor() as cursor:
            cursor.execute('SELECT * FROM tags WHERE tag_id = ?', (tag_id,))
            row = cursor.fetchone()
        return self._row_to_tag(row) if row else None

    def get_by_name(self, name: str) -> Optional[Tag]:
        """Retrieve tag by name"""
        with self.db.get_cursor() as cursor:
            cursor.execute('SELECT * FROM tags WHERE name = ?', (name,))
            row = cursor.fetchone()
        return self._row_to_tag(row) if row else None

    def get_all(self) -> List[Tag]:
        """Retrieve all tags"""
        with self.db.get_cursor() as cursor:
            cursor.execute('SELECT * FROM tags ORDER BY name')
            rows = cursor.fetchall()
        return [self._row_to_tag(row) for row in rows]

    def update(self, tag: Tag) -> Tag:
        """Update existing tag"""
        with self.db.get_cursor() as cursor:
            cursor.execute('''
                UPDATE tags
                SET value_blob = ?, description = ?, updated_at = CURRENT_TIMESTAMP
                WHERE tag_id = ?
            ''', (pickle.dumps(tag.value), tag.description, tag.tag_id))
        return tag

    def update_full(self, tag: Tag, allow_rename: bool = False) -> Tag:
        """
        Update all editable tag fields including name (if allow_rename=True).

        Args:
            tag: Tag object with updated values
            allow_rename: If True, allows changing the tag name

        Returns:
            Updated tag object

        Raises:
            ValueError: If name conflict or validation fails
        """
        with self.db.get_cursor() as cursor:
            if allow_rename:
                # Full update including name
                cursor.execute('''
                    UPDATE tags
                    SET name = ?,
                        value_blob = ?,
                        description = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE tag_id = ?
                ''', (tag.name, pickle.dumps(tag.value), tag.description, tag.tag_id))
            else:
                # Update without name change (same as update())
                cursor.execute('''
                    UPDATE tags
                    SET value_blob = ?,
                        description = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE tag_id = ?
                ''', (pickle.dumps(tag.value), tag.description, tag.tag_id))
        return tag

    def delete(self, tag_id: int) -> bool:
        """Delete tag by ID"""
        with self.db.get_cursor() as cursor:
            cursor.execute('DELETE FROM tags WHERE tag_id = ?', (tag_id,))
            return cursor.rowcount > 0

    def _row_to_tag(self, row) -> Tag:
        """Convert database row to Tag object"""
        try:
            # Safely deserialize pickled value
            value = None
            if row['value_blob']:
                try:
                    value = pickle.loads(row['value_blob'])
                except (pickle.UnpicklingError, EOFError, ValueError, TypeError) as e:
                    self.logger.warning(f"Corrupted pickle for tag '{row['name']}': {e}")
                    data_type = DataType[row['data_type']]
                    value = data_type.default_value

            return Tag(
                tag_id=row['tag_id'],
                name=row['name'],
                data_type=DataType[row['data_type']],
                value=value,
                description=row['description'] or '',
                is_array=bool(row['is_array']),
                array_dimensions=json.loads(row['array_dimensions']) if row['array_dimensions'] else None,
                udt_type_id=row['udt_type_id'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
        except Exception as e:
            self.logger.error(f"Error converting row to tag: {e}")
            raise
