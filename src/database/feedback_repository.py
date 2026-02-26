"""Database repository for feedback CRUD operations"""

from typing import List, Optional, Dict
from .db_manager import DBManager
import logging


class FeedbackRepository:
    """Database operations for feedback"""

    ALLOWED_COLUMNS = frozenset({
        'category', 'priority', 'description', 'screenshot_path',
        'original_screenshot_path', 'status', 'resolved_at', 'notes'
    })

    def __init__(self, db_manager: DBManager):
        self.db = db_manager
        self.logger = logging.getLogger(__name__)

    def create(self, feedback_data: Dict) -> Dict:
        """Insert new feedback into database"""
        try:
            with self.db.get_cursor() as cursor:
                cursor.execute('''
                    INSERT INTO feedback (category, priority, description,
                                        screenshot_path, original_screenshot_path, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    feedback_data['category'],
                    feedback_data['priority'],
                    feedback_data['description'],
                    feedback_data['screenshot_path'],
                    feedback_data['original_screenshot_path'],
                    feedback_data.get('status', 'open'),
                    feedback_data.get('created_at')
                ))
                feedback_data['feedback_id'] = cursor.lastrowid
            return feedback_data
        except Exception as e:
            self.logger.error(f"Failed to create feedback: {e}")
            raise

    def get_by_status(self, status: str) -> List[Dict]:
        """Retrieve feedback by status"""
        try:
            with self.db.get_cursor() as cursor:
                cursor.execute('SELECT * FROM feedback WHERE status = ? ORDER BY created_at DESC', (status,))
                rows = cursor.fetchall()
            return [self._row_to_dict(row) for row in rows]
        except Exception as e:
            self.logger.error(f"Failed to get feedback by status: {e}")
            return []

    def get_by_category(self, category: str) -> List[Dict]:
        """Retrieve feedback by category"""
        try:
            with self.db.get_cursor() as cursor:
                cursor.execute('SELECT * FROM feedback WHERE category = ? ORDER BY created_at DESC', (category,))
                rows = cursor.fetchall()
            return [self._row_to_dict(row) for row in rows]
        except Exception as e:
            self.logger.error(f"Failed to get feedback by category: {e}")
            return []

    def _row_to_dict(self, row) -> Dict:
        """Convert database row to dictionary"""
        if not row:
            return None

        return {
            'feedback_id': row['feedback_id'],
            'category': row['category'],
            'priority': row['priority'],
            'description': row['description'],
            'screenshot_path': row['screenshot_path'],
            'original_screenshot_path': row['original_screenshot_path'],
            'status': row['status'],
            'created_at': row['created_at'],
            'resolved_at': row['resolved_at'],
            'notes': row['notes']
        }
