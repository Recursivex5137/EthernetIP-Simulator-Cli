"""Dialog for adding/editing UDT members"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox,
                                QCheckBox, QLabel, QDialogButtonBox, QMessageBox)
from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator
from ...models.data_types import DataType
from ...models.udt import UDTMember
from ..utils import center_dialog


class AddMemberDialog(QDialog):
    """Dialog for adding a single UDT member"""

    def __init__(self, member: UDTMember = None, parent=None):
        super().__init__(parent)
        self.member = member  # If editing existing member
        self.member_name = ""
        self.member_type = DataType.DINT
        self.is_array = False
        self.array_dimensions = None

        title = "Edit UDT Member" if member else "Add UDT Member"
        self.setWindowTitle(title)
        self.setFixedSize(450, 280)
        self._setup_ui()
        center_dialog(self, parent)

        # Populate fields if editing
        if member:
            self._populate_fields()

    def _setup_ui(self):
        """Set up the dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Form section
        form = QFormLayout()
        form.setSpacing(6)

        # Member name with validation
        self._name_edit = QLineEdit()
        regex = QRegularExpression(r'^[A-Za-z_][A-Za-z0-9_]{0,39}$')
        self._name_edit.setValidator(QRegularExpressionValidator(regex))
        self._name_edit.setMaxLength(40)
        self._name_edit.setPlaceholderText("e.g., Temperature")
        form.addRow("Member Name:", self._name_edit)

        # Data type dropdown (exclude UDT for now - future enhancement)
        self._type_combo = QComboBox()
        types = [dt.type_name for dt in DataType if dt != DataType.UDT]
        self._type_combo.addItems(types)
        form.addRow("Data Type:", self._type_combo)

        # Array checkbox
        self._array_check = QCheckBox()
        self._array_check.stateChanged.connect(self._on_array_changed)
        form.addRow("Array:", self._array_check)

        # Dimensions (hidden by default)
        self._dim_label = QLabel("Dimensions:")
        self._dim_edit = QLineEdit()
        self._dim_edit.setPlaceholderText("e.g., 10 or 5,10 for 2D")
        self._dim_label.setVisible(False)
        self._dim_edit.setVisible(False)
        form.addRow(self._dim_label, self._dim_edit)

        # Help text
        help_label = QLabel("Member names: start with letter/underscore, alphanumeric only")
        help_label.setStyleSheet("color: #888; font-size: 10px;")
        help_label.setWordWrap(True)
        form.addRow("", help_label)

        layout.addLayout(form)
        layout.addStretch()

        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok_text = "Update" if self.member else "Add Member"
        buttons.button(QDialogButtonBox.Ok).setText(ok_text)
        buttons.button(QDialogButtonBox.Ok).setProperty("class", "success")
        buttons.accepted.connect(self._on_add)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate_fields(self):
        """Populate fields when editing existing member"""
        if not self.member:
            return

        self._name_edit.setText(self.member.name)
        self._type_combo.setCurrentText(self.member.data_type.type_name)
        self._array_check.setChecked(self.member.is_array)

        if self.member.is_array and self.member.array_dimensions:
            dim_str = ','.join(str(d) for d in self.member.array_dimensions)
            self._dim_edit.setText(dim_str)

    def _on_array_changed(self, state):
        """Show/hide dimension fields based on array checkbox"""
        is_checked = self._array_check.isChecked()
        self._dim_label.setVisible(is_checked)
        self._dim_edit.setVisible(is_checked)

    def _on_add(self):
        """Validate and accept"""
        name = self._name_edit.text().strip()

        if not name:
            QMessageBox.warning(self, "Error", "Member name is required")
            return

        if not self._name_edit.hasAcceptableInput():
            QMessageBox.warning(
                self, "Error",
                "Invalid member name. Must start with letter/underscore, "
                "contain only alphanumeric characters and underscores."
            )
            return

        # Store results for retrieval
        self.member_name = name
        self.member_type = DataType[self._type_combo.currentText()]
        self.is_array = self._array_check.isChecked()

        if self.is_array:
            dim_str = self._dim_edit.text().strip()
            if not dim_str:
                QMessageBox.warning(self, "Error", "Array dimensions are required when Array is checked")
                return

            try:
                self.array_dimensions = [int(d.strip()) for d in dim_str.split(',')]
                if any(d <= 0 for d in self.array_dimensions):
                    raise ValueError("Dimensions must be positive")
            except ValueError as e:
                QMessageBox.warning(
                    self, "Error",
                    f"Invalid array dimensions: {e}\nEnter comma-separated positive integers (e.g., 10 or 5,10)"
                )
                return
        else:
            self.array_dimensions = None

        self.accept()

    def get_member(self) -> UDTMember:
        """Retrieve the created/edited member"""
        return UDTMember(
            name=self.member_name,
            data_type=self.member_type,
            is_array=self.is_array,
            array_dimensions=self.array_dimensions
        )
