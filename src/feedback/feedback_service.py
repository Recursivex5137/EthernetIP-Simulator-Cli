"""Feedback business logic"""

from typing import List, Optional, Dict
from datetime import datetime
import logging


class FeedbackService:
    """Service for managing feedback"""

    def __init__(self, feedback_repository):
        self.repository = feedback_repository
        self.logger = logging.getLogger(__name__)

    def create_feedback(self, category: str, priority: str, description: str,
                       screenshot_path: str, original_screenshot_path: str) -> dict:
        """Create new feedback entry"""
        try:
            feedback_data = {
                'category': category,
                'priority': priority,
                'description': description,
                'screenshot_path': screenshot_path,
                'original_screenshot_path': original_screenshot_path,
                'status': 'open',
                'created_at': datetime.now().isoformat()
            }

            feedback = self.repository.create(feedback_data)
            self.logger.info(f"Feedback created: ID={feedback.get('feedback_id')}, Category={category}")
            return feedback

        except Exception as e:
            self.logger.error(f"Failed to create feedback: {e}")
            raise
