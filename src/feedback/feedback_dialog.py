"""Feedback submission dialog"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QComboBox,
    QTextEdit, QPushButton, QMessageBox, QLabel
)
import logging
from .annotation_canvas import AnnotationCanvas
from .screenshot_manager import ScreenshotManager


class FeedbackDialog(QDialog):
    """Dialog for submitting feedback with annotated screenshot"""

    def __init__(self, screenshot_path: str, feedback_service, parent=None):
        super().__init__(parent)

        self.screenshot_path = screenshot_path
        self.feedback_service = feedback_service
        self.screenshot_manager = ScreenshotManager()
        self.logger = logging.getLogger(__name__)

        self.setWindowTitle("Submit Feedback - F12 Screenshot Tool")
        self.setMinimumSize(1000, 800)
        self.setModal(True)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Header
        header = QLabel("Annotate Screenshot & Submit Feedback")
        header.setStyleSheet("font-size: 16px; font-weight: bold; padding: 4px;")
        layout.addWidget(header)

        # Load screenshot
        screenshot = self.screenshot_manager.get_screenshot(self.screenshot_path)
        if screenshot is None:
            QMessageBox.critical(self, "Error", "Failed to load screenshot")
            self.reject()
            return

        # Annotation canvas
        self._annotation_canvas = AnnotationCanvas(screenshot, self)
        layout.addWidget(self._annotation_canvas, stretch=1)

        # Feedback form
        form = QFormLayout()
        form.setSpacing(6)

        # Category
        self._category_combo = QComboBox()
        self._category_combo.addItems([
            "UI Issue", "Feature Request", "Bug",
            "Enhancement", "Performance", "Other"
        ])
        form.addRow("Category:", self._category_combo)

        # Priority
        self._priority_combo = QComboBox()
        self._priority_combo.addItems(["Low", "Medium", "High", "Critical"])
        self._priority_combo.setCurrentText("Medium")
        form.addRow("Priority:", self._priority_combo)

        # Description
        self._description_edit = QTextEdit()
        self._description_edit.setMaximumHeight(100)
        self._description_edit.setPlaceholderText("Describe the issue or suggestion...")
        form.addRow("Description:", self._description_edit)

        layout.addLayout(form)

        # Help text
        help_label = QLabel("Tip: Use the annotation tools above to highlight areas of interest.")
        help_label.setStyleSheet("color: gray; font-size: 10px; padding: 2px;")
        layout.addWidget(help_label)

        # Buttons
        button_row = QHBoxLayout()
        button_row.addStretch()

        submit_btn = QPushButton("Submit Feedback")
        submit_btn.setProperty("class", "success")
        submit_btn.setMinimumHeight(36)
        submit_btn.setMinimumWidth(160)
        submit_btn.clicked.connect(self._submit_feedback)
        button_row.addWidget(submit_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumHeight(36)
        cancel_btn.setMinimumWidth(100)
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)

        layout.addLayout(button_row)

    def _submit_feedback(self):
        """Submit feedback to service"""
        try:
            description = self._description_edit.toPlainText().strip()

            if not description:
                QMessageBox.warning(
                    self, "Missing Information",
                    "Please provide a description of your feedback."
                )
                return

            # Get annotated image
            annotated_image = self._annotation_canvas.get_annotated_image()

            # Save annotated screenshot
            annotated_path = self.screenshot_path.replace(".png", "_annotated.png")
            annotated_image.save(annotated_path)

            self.logger.info(f"Annotated screenshot saved: {annotated_path}")

            # Build feedback data
            feedback_data = {
                'category': self._category_combo.currentText(),
                'priority': self._priority_combo.currentText(),
                'description': description,
                'screenshot_path': annotated_path,
                'original_screenshot_path': self.screenshot_path
            }

            # Save to database via service
            self.feedback_service.create_feedback(**feedback_data)

            self.logger.info(
                f"Feedback submitted: {feedback_data['category']} - {feedback_data['priority']}"
            )

            QMessageBox.information(
                self, "Feedback Submitted",
                f"Your {feedback_data['category'].lower()} feedback has been submitted.\n\n"
                f"Priority: {feedback_data['priority']}\n"
                f"Screenshot saved with annotations."
            )

            self.accept()

        except Exception as e:
            self.logger.error(f"Failed to submit feedback: {e}", exc_info=True)
            QMessageBox.critical(
                self, "Error",
                f"Failed to submit feedback:\n{str(e)}"
            )
