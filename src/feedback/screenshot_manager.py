"""Screenshot capture and management"""

from PySide6.QtGui import QPixmap, QGuiApplication
import os
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional
import logging


class ScreenshotManager:
    """Manages screenshot capture and storage"""

    def __init__(self, storage_dir: str = "data/feedback/screenshots"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)

    def capture_window(self, window) -> Tuple[QPixmap, str]:
        """
        Capture screenshot of a specific window.

        Args:
            window: QWidget window to capture

        Returns:
            Tuple of (QPixmap, filepath)
        """
        try:
            # Capture screenshot using Qt native grab()
            screenshot = window.grab()

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            filepath = self.storage_dir / filename

            # Save screenshot
            screenshot.save(str(filepath), "PNG")

            self.logger.info(f"Screenshot saved: {filepath}")
            return screenshot, str(filepath)

        except Exception as e:
            self.logger.error(f"Failed to capture screenshot: {e}")
            raise

    def capture_full_screen(self) -> Tuple[QPixmap, str]:
        """Capture full screen screenshot"""
        try:
            # Capture screenshot using Qt native screen capture
            screen = QGuiApplication.primaryScreen()
            screenshot = screen.grabWindow(0)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"fullscreen_{timestamp}.png"
            filepath = self.storage_dir / filename

            screenshot.save(str(filepath), "PNG")

            self.logger.info(f"Full screen screenshot saved: {filepath}")
            return screenshot, str(filepath)

        except Exception as e:
            self.logger.error(f"Failed to capture full screen: {e}")
            raise

    def get_screenshot(self, filepath: str) -> Optional[QPixmap]:
        """Load a screenshot from filepath"""
        try:
            if os.path.exists(filepath):
                pixmap = QPixmap(filepath)
                if pixmap.isNull():
                    self.logger.warning(f"Failed to load screenshot: {filepath}")
                    return None
                return pixmap
            else:
                self.logger.warning(f"Screenshot not found: {filepath}")
                return None
        except Exception as e:
            self.logger.error(f"Failed to load screenshot: {e}")
            return None
