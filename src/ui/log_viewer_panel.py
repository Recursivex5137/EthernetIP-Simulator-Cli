"""Log viewer panel for displaying application logs"""

from collections import deque
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QComboBox,
    QLineEdit, QPushButton, QCheckBox, QLabel, QFileDialog, QMessageBox
)
from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor, QFont
from PySide6.QtCore import Qt, QTimer
from .theme import COLORS


class LogViewerPanel(QWidget):
    """Panel for viewing and filtering application logs"""

    MAX_LOG_ENTRIES = 10000  # Maximum number of log entries to keep in memory

    def __init__(self, log_handler, parent=None):
        super().__init__(parent)
        self.log_handler = log_handler
        self.log_buffer = deque(maxlen=self.MAX_LOG_ENTRIES)
        self.filtered_count = 0

        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(300)
        self._filter_timer.timeout.connect(self._apply_filter)

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Toolbar
        toolbar = self._create_toolbar()
        layout.addLayout(toolbar)

        # Log display — maximumBlockCount prevents unbounded memory growth
        self._log_display = QTextEdit()
        self._log_display.setReadOnly(True)
        self._log_display.setLineWrapMode(QTextEdit.NoWrap)
        self._log_display.document().setMaximumBlockCount(self.MAX_LOG_ENTRIES)

        # Set monospace font
        font = QFont("Consolas", 9)
        if not font.exactMatch():
            font = QFont("Courier New", 9)
        self._log_display.setFont(font)

        layout.addWidget(self._log_display, stretch=1)

        # Status bar
        status_layout = QHBoxLayout()
        self._status_label = QLabel("0 messages")
        self._status_label.setStyleSheet(f"color: {COLORS['text_disabled']}; font-size: 10px;")
        status_layout.addWidget(self._status_label)
        status_layout.addStretch()

        layout.addLayout(status_layout)

    def _create_toolbar(self) -> QHBoxLayout:
        """Create the toolbar with controls"""
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        # Level filter
        self._level_filter = QComboBox()
        self._level_filter.addItems(["All", "INFO", "WARNING", "ERROR", "DEBUG"])
        self._level_filter.setCurrentText("All")
        self._level_filter.setToolTip("Filter by log level")
        self._level_filter.currentTextChanged.connect(self._apply_filter)
        toolbar.addWidget(QLabel("Level:"))
        toolbar.addWidget(self._level_filter)

        # Search field
        self._search_field = QLineEdit()
        self._search_field.setPlaceholderText("Filter messages...")
        self._search_field.setToolTip("Search log messages (case-insensitive)")
        self._search_field.textChanged.connect(lambda _: self._filter_timer.start())
        toolbar.addWidget(QLabel("Search:"))
        toolbar.addWidget(self._search_field, stretch=1)

        # Auto-scroll checkbox
        self._autoscroll_check = QCheckBox("Auto-scroll")
        self._autoscroll_check.setChecked(True)
        self._autoscroll_check.setToolTip("Automatically scroll to newest messages")
        toolbar.addWidget(self._autoscroll_check)

        # Clear button
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setToolTip("Clear all log messages")
        self._clear_btn.clicked.connect(self._clear_log)
        toolbar.addWidget(self._clear_btn)

        # Save button
        self._save_btn = QPushButton("Save...")
        self._save_btn.setToolTip("Save logs to file")
        self._save_btn.clicked.connect(self._save_to_file)
        toolbar.addWidget(self._save_btn)

        return toolbar

    def _connect_signals(self):
        """Connect log handler signal"""
        self.log_handler.log_signal.connect(self._append_log)

    def _append_log(self, timestamp: str, level: str, message: str):
        """
        Append a log entry to the display.

        Args:
            timestamp: Formatted timestamp string
            level: Log level (INFO, WARNING, ERROR, DEBUG)
            message: Log message
        """
        # Store in buffer
        log_entry = {
            'timestamp': timestamp,
            'level': level,
            'message': message
        }
        self.log_buffer.append(log_entry)

        # Check if it passes the current filter
        if self._passes_filter(log_entry):
            self._add_to_display(log_entry)
            self.filtered_count += 1

            # Auto-scroll if enabled
            if self._autoscroll_check.isChecked():
                self._log_display.moveCursor(QTextCursor.End)

        # Update status
        self._update_status()

    def _passes_filter(self, log_entry: dict) -> bool:
        """
        Check if a log entry passes the current filter.

        Args:
            log_entry: Log entry dict

        Returns:
            True if entry should be displayed
        """
        # Level filter
        level_filter = self._level_filter.currentText()
        if level_filter != "All" and log_entry['level'] != level_filter:
            return False

        # Search filter
        search_text = self._search_field.text().strip()
        if search_text:
            if search_text.lower() not in log_entry['message'].lower():
                return False

        return True

    def _add_to_display(self, log_entry: dict):
        """
        Add a log entry to the display with color coding.

        Args:
            log_entry: Log entry dict
        """
        # Get color for level
        level = log_entry['level']
        if level == "ERROR":
            color = COLORS['danger']
        elif level == "WARNING":
            color = COLORS['warning']
        elif level == "DEBUG":
            color = COLORS['text_disabled']
        else:  # INFO and others
            color = COLORS['text_primary']

        # Format the log line
        formatted_line = f"[{log_entry['timestamp']}] {level:8s} : {log_entry['message']}"

        # Append with color
        cursor = self._log_display.textCursor()
        cursor.movePosition(QTextCursor.End)

        char_format = QTextCharFormat()
        char_format.setForeground(QColor(color))

        cursor.insertText(formatted_line + "\n", char_format)

    def _apply_filter(self):
        """Re-apply the filter to all log entries"""
        # Clear display
        self._log_display.clear()
        self.filtered_count = 0

        # Re-add all entries that pass the filter
        for log_entry in self.log_buffer:
            if self._passes_filter(log_entry):
                self._add_to_display(log_entry)
                self.filtered_count += 1

        # Update status
        self._update_status()

        # Scroll to end if auto-scroll enabled
        if self._autoscroll_check.isChecked():
            self._log_display.moveCursor(QTextCursor.End)

    def _clear_log(self):
        """Clear all log messages"""
        reply = QMessageBox.question(
            self, "Clear Logs",
            "Are you sure you want to clear all log messages?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self._log_display.clear()
            self.log_buffer.clear()
            self.filtered_count = 0
            self._update_status()

    def _save_to_file(self):
        """Save logs to a text file"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Logs",
            "logs.txt",
            "Text Files (*.txt);;All Files (*)"
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    # Write all logs from buffer
                    for log_entry in self.log_buffer:
                        formatted_line = f"[{log_entry['timestamp']}] {log_entry['level']:8s} : {log_entry['message']}"
                        f.write(formatted_line + "\n")

                QMessageBox.information(
                    self, "Save Successful",
                    f"Logs saved to:\n{file_path}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self, "Save Failed",
                    f"Failed to save logs:\n{str(e)}"
                )

    def _update_status(self):
        """Update the status label with actual buffer size (not an unbounded counter)"""
        total = len(self.log_buffer)
        if total == self.filtered_count:
            status_text = f"{total:,} messages"
        else:
            status_text = f"{total:,} messages ({total - self.filtered_count:,} filtered)"

        self._status_label.setText(status_text)
