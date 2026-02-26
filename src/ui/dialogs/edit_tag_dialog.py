"""Dialog for editing an existing tag"""

import ast
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QTextEdit,
    QDialogButtonBox, QMessageBox, QLabel, QGroupBox
)
from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator
from ...models.data_types import DataType
from ...models.tag import Tag
from ..utils import center_dialog
from ..theme import COLORS


class EditTagDialog(QDialog):
    """Dialog for editing an existing tag"""

    def __init__(self, tag: Tag, tag_service, enip_server, parent=None):
        super().__init__(parent)
        self.original_tag = tag
        self.tag_service = tag_service
        self.enip_server = enip_server

        self.setWindowTitle(f"Edit Tag: {tag.name}")
        self.setFixedSize(500, 450)
        self._setup_ui()
        center_dialog(self, parent)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Current values group (read-only)
        current_group = QGroupBox("Current Tag Properties")
        current_layout = QFormLayout(current_group)
        current_layout.setSpacing(6)

        # Current name (read-only)
        current_name = QLabel(self.original_tag.name)
        current_name.setStyleSheet(f"color: {COLORS['text_secondary']}; font-weight: bold;")
        current_layout.addRow("Tag Name:", current_name)

        # Current type (read-only)
        type_text = self.original_tag.data_type.type_name
        if self.original_tag.is_array and self.original_tag.array_dimensions:
            dims = ','.join(str(d) for d in self.original_tag.array_dimensions)
            type_text += f" [{dims}]"
        current_type = QLabel(type_text)
        current_type.setStyleSheet(f"color: {COLORS['text_secondary']}; font-weight: bold;")
        current_layout.addRow("Data Type:", current_type)

        layout.addWidget(current_group)

        # Editable fields
        form = QFormLayout()
        form.setSpacing(8)

        # New name (optional rename)
        self._new_name_edit = QLineEdit()
        regex = QRegularExpression(r'^[A-Za-z_][A-Za-z0-9_]{0,39}$')
        self._new_name_edit.setValidator(QRegularExpressionValidator(regex))
        self._new_name_edit.setMaxLength(40)
        self._new_name_edit.setPlaceholderText(f"Leave blank to keep '{self.original_tag.name}'")
        self._new_name_edit.textChanged.connect(self._validate_new_name)
        form.addRow("New Name (optional):", self._new_name_edit)

        self._name_status = QLabel("")
        self._name_status.setStyleSheet("font-size: 10px;")
        form.addRow("", self._name_status)

        # Description
        self._desc_edit = QTextEdit()
        self._desc_edit.setMaximumHeight(80)
        self._desc_edit.setPlaceholderText("Optional description...")
        self._desc_edit.setPlainText(self.original_tag.description)
        form.addRow("Description:", self._desc_edit)

        # Current value
        self._value_edit = QLineEdit()
        self._value_edit.setPlaceholderText("Enter new value...")

        # Set current value
        if self.original_tag.is_array:
            if isinstance(self.original_tag.value, list):
                self._value_edit.setText(str(self.original_tag.value))
            else:
                self._value_edit.setText("[]")
            self._value_edit.setToolTip("Arrays shown as list. Edit carefully.")
        elif self.original_tag.data_type == DataType.BOOL:
            self._value_edit.setText("true" if self.original_tag.value else "false")
            self._value_edit.setToolTip("Enter: true/false or 1/0")
        elif self.original_tag.data_type == DataType.STRING:
            self._value_edit.setText(str(self.original_tag.value) if self.original_tag.value else "")
        else:
            self._value_edit.setText(str(self.original_tag.value))

        form.addRow("Value:", self._value_edit)

        # Help text
        help_label = QLabel("Tip: Leave 'New Name' blank to keep the current tag name")
        help_label.setStyleSheet(f"color: {COLORS['text_disabled']}; font-size: 10px;")
        help_label.setWordWrap(True)
        form.addRow("", help_label)

        layout.addLayout(form)
        layout.addStretch()

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setProperty("class", "success")
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate_new_name(self, text):
        """Validate the new name field"""
        if not text:
            self._name_status.setText("")
            self._name_status.setStyleSheet("")
        elif not self._new_name_edit.hasAcceptableInput():
            self._name_status.setText("Invalid name format")
            self._name_status.setStyleSheet(f"color: {COLORS['danger']}; font-size: 10px;")
        elif text == self.original_tag.name:
            self._name_status.setText("Same as current name")
            self._name_status.setStyleSheet(f"color: {COLORS['warning']}; font-size: 10px;")
        else:
            # Check if name already exists
            existing_tag = self.tag_service.get_tag_by_name(text)
            if existing_tag and existing_tag.tag_id != self.original_tag.tag_id:
                self._name_status.setText("Name already exists")
                self._name_status.setStyleSheet(f"color: {COLORS['danger']}; font-size: 10px;")
            else:
                self._name_status.setText("Valid new name")
                self._name_status.setStyleSheet(f"color: {COLORS['success']}; font-size: 10px;")

    def _parse_value(self, value_str: str):
        """Parse value string based on tag's data type"""
        data_type = self.original_tag.data_type

        if self.original_tag.is_array:
            # For arrays, try to parse as Python list
            try:
                parsed = ast.literal_eval(value_str)
                if isinstance(parsed, list):
                    return parsed
                else:
                    raise ValueError("Array value must be a list")
            except (ValueError, SyntaxError) as e:
                raise ValueError(f"Invalid array format: {e}")

        # Parse scalar values
        if data_type == DataType.BOOL:
            return value_str.lower() in ('true', '1', 'yes')
        elif data_type in (DataType.SINT, DataType.INT, DataType.DINT, DataType.LINT,
                           DataType.USINT, DataType.UINT, DataType.UDINT):
            return int(value_str) if value_str else 0
        elif data_type in (DataType.REAL, DataType.LREAL):
            return float(value_str) if value_str else 0.0
        elif data_type == DataType.STRING:
            return value_str
        else:
            return data_type.default_value

    def _on_save(self):
        """Save the edited tag"""
        new_name = self._new_name_edit.text().strip()
        new_description = self._desc_edit.toPlainText().strip()
        new_value_str = self._value_edit.text().strip()

        # Determine final name
        final_name = new_name if new_name else self.original_tag.name

        # Validate new name if changed
        is_renaming = final_name != self.original_tag.name

        if is_renaming:
            # Check name format
            if not self._new_name_edit.hasAcceptableInput():
                QMessageBox.warning(
                    self, "Invalid Name",
                    "New tag name must:\n"
                    "- Start with letter or underscore\n"
                    "- Contain only letters, numbers, underscores\n"
                    "- Be 1-40 characters long"
                )
                return

            # Check for conflicts
            existing_tag = self.tag_service.get_tag_by_name(final_name)
            if existing_tag and existing_tag.tag_id != self.original_tag.tag_id:
                QMessageBox.warning(
                    self, "Name Conflict",
                    f"A tag named '{final_name}' already exists.\n\n"
                    "Please choose a different name."
                )
                return

            # Warn about server restart if running
            if self.enip_server and self.enip_server.is_running:
                reply = QMessageBox.question(
                    self, "Server Restart Required",
                    f"Renaming '{self.original_tag.name}' to '{final_name}' requires restarting the server.\n\n"
                    "The server will be automatically restarted after saving.\n\n"
                    "Continue with rename?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return

        # Parse and validate new value
        try:
            new_value = self._parse_value(new_value_str)
        except ValueError as e:
            QMessageBox.warning(
                self, "Invalid Value",
                f"Invalid value for type {self.original_tag.data_type.type_name}:\n{e}\n\n"
                f"BOOL: true/false, 1/0\n"
                f"INT types: integer number\n"
                f"REAL types: decimal number\n"
                f"STRING: any text\n"
                f"ARRAY: [val1, val2, ...]"
            )
            return

        # Create updated tag
        updated_tag = Tag(
            tag_id=self.original_tag.tag_id,
            name=final_name,
            data_type=self.original_tag.data_type,
            value=new_value,
            description=new_description,
            is_array=self.original_tag.is_array,
            array_dimensions=self.original_tag.array_dimensions,
            udt_type_id=self.original_tag.udt_type_id
        )

        # Save via service
        try:
            success = self.tag_service.update_tag(updated_tag, allow_rename=is_renaming)
            if success:
                self.accept()
            else:
                QMessageBox.critical(
                    self, "Update Failed",
                    "Failed to update tag. Check the logs for details."
                )
        except Exception as e:
            QMessageBox.critical(
                self, "Error",
                f"Failed to update tag: {e}"
            )
