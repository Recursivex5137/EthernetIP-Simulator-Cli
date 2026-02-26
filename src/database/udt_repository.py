"""Repository for UDT (User Defined Type) database operations"""

import logging
import json
from typing import List, Optional
from .db_manager import DBManager
from ..models.udt import UDT


class UDTRepository:
    """Data access layer for UDT definitions"""

    def __init__(self, db_manager: DBManager):
        self.db = db_manager
        self.logger = logging.getLogger(__name__)

    def create(self, udt: UDT) -> UDT:
        """Create a new UDT definition in the database"""
        try:
            definition_json = json.dumps(udt.to_json())

            with self.db.get_cursor() as cursor:
                cursor.execute('''
                    INSERT INTO udts (name, description, definition_json)
                    VALUES (?, ?, ?)
                ''', (udt.name, udt.description, definition_json))

                udt.udt_id = cursor.lastrowid

            self.logger.info(f"Created UDT: {udt.name} (ID: {udt.udt_id})")
            return udt

        except Exception as e:
            self.logger.error(f"Failed to create UDT '{udt.name}': {e}")
            raise

    def get_by_id(self, udt_id: int) -> Optional[UDT]:
        """Retrieve UDT by ID"""
        try:
            with self.db.get_cursor() as cursor:
                cursor.execute('SELECT * FROM udts WHERE udt_id = ?', (udt_id,))
                row = cursor.fetchone()

            return self._row_to_udt(row) if row else None

        except Exception as e:
            self.logger.error(f"Failed to get UDT by ID {udt_id}: {e}")
            return None

    def get_by_name(self, name: str) -> Optional[UDT]:
        """Retrieve UDT by name (for duplicate check)"""
        try:
            with self.db.get_cursor() as cursor:
                cursor.execute('SELECT * FROM udts WHERE name = ?', (name,))
                row = cursor.fetchone()

            return self._row_to_udt(row) if row else None

        except Exception as e:
            self.logger.error(f"Failed to get UDT by name '{name}': {e}")
            return None

    def get_all(self) -> List[UDT]:
        """Get all UDT definitions, ordered by name"""
        try:
            with self.db.get_cursor() as cursor:
                cursor.execute('SELECT * FROM udts ORDER BY name')
                rows = cursor.fetchall()

            return [self._row_to_udt(row) for row in rows if row]

        except Exception as e:
            self.logger.error(f"Failed to get all UDTs: {e}")
            return []

    def update(self, udt: UDT) -> UDT:
        """Update an existing UDT definition"""
        try:
            definition_json = json.dumps(udt.to_json())

            with self.db.get_cursor() as cursor:
                cursor.execute('''
                    UPDATE udts
                    SET definition_json = ?, description = ?, name = ?
                    WHERE udt_id = ?
                ''', (definition_json, udt.description, udt.name, udt.udt_id))

            self.logger.info(f"Updated UDT: {udt.name} (ID: {udt.udt_id})")
            return udt

        except Exception as e:
            self.logger.error(f"Failed to update UDT '{udt.name}': {e}")
            raise

    def delete(self, udt_id: int) -> bool:
        """Delete a UDT definition"""
        try:
            with self.db.get_cursor() as cursor:
                cursor.execute('DELETE FROM udts WHERE udt_id = ?', (udt_id,))
                success = cursor.rowcount > 0

            if success:
                self.logger.info(f"Deleted UDT with ID: {udt_id}")
            else:
                self.logger.warning(f"No UDT found with ID: {udt_id}")

            return success

        except Exception as e:
            self.logger.error(f"Failed to delete UDT {udt_id}: {e}")
            return False

    def _row_to_udt(self, row) -> Optional[UDT]:
        """Convert database row to UDT object"""
        if not row:
            return None

        try:
            definition_dict = json.loads(row['definition_json'])
            udt = UDT.from_dict(definition_dict)
            udt.udt_id = row['udt_id']
            return udt

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            self.logger.warning(f"Failed to deserialize UDT '{row.get('name', 'unknown')}': {e}")
            return None
