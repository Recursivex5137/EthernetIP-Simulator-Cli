"""Shared UI utility functions"""

from PySide6.QtWidgets import QDialog, QWidget, QStatusBar


def center_dialog(dialog: QDialog, parent: QWidget = None):
    """Center a dialog on its parent or screen, ensuring it stays visible."""
    if parent:
        parent_geo = parent.geometry()
        x = parent_geo.x() + (parent_geo.width() - dialog.width()) // 2
        y = parent_geo.y() + (parent_geo.height() - dialog.height()) // 2
    else:
        screen_geo = dialog.screen().availableGeometry()
        x = (screen_geo.width() - dialog.width()) // 2
        y = (screen_geo.height() - dialog.height()) // 2

    # Clamp to screen bounds
    screen_geo = dialog.screen().availableGeometry()
    x = max(screen_geo.x(), min(x, screen_geo.right() - dialog.width()))
    y = max(screen_geo.y(), min(y, screen_geo.bottom() - dialog.height()))
    dialog.move(x, y)


def show_toast(status_bar: QStatusBar, message: str, timeout_ms: int = 5000):
    """Show a temporary message in the status bar."""
    status_bar.showMessage(message, timeout_ms)
