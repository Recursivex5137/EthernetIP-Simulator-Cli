"""Simple undo/redo stack for tag value edits"""

from collections import deque
from dataclasses import dataclass
from typing import Any, Optional
import logging


@dataclass
class TagEdit:
    """Record of a tag value change"""
    tag_id: int
    old_value: Any
    new_value: Any
    elem_index: Optional[int] = None


@dataclass
class UDTMemberEdit:
    """Record of a UDT member value change"""
    tag_id: int
    member_name: str
    old_value: Any
    new_value: Any
    array_index: Optional[int] = None  # For arrays of UDTs


class UndoManager:
    """Manages undo/redo history for tag edits"""

    MAX_HISTORY = 50

    def __init__(self):
        self._undo_stack: deque[TagEdit] = deque(maxlen=self.MAX_HISTORY)
        self._redo_stack: deque[TagEdit] = deque()
        self.logger = logging.getLogger(__name__)

    def push(self, edit: TagEdit):
        """Record a new edit (clears redo stack)"""
        self._undo_stack.append(edit)
        self._redo_stack.clear()

    def undo(self) -> Optional[TagEdit]:
        """Pop the last edit and return it (caller applies the old_value)"""
        if not self._undo_stack:
            return None
        edit = self._undo_stack.pop()
        self._redo_stack.append(edit)
        self.logger.debug("Undo: tag_id=%s, restoring %s", edit.tag_id, edit.old_value)
        return edit

    def redo(self) -> Optional[TagEdit]:
        """Re-apply the last undone edit (caller applies the new_value)"""
        if not self._redo_stack:
            return None
        edit = self._redo_stack.pop()
        self._undo_stack.append(edit)
        self.logger.debug("Redo: tag_id=%s, applying %s", edit.tag_id, edit.new_value)
        return edit

    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    def clear(self):
        """Clear all history"""
        self._undo_stack.clear()
        self._redo_stack.clear()
