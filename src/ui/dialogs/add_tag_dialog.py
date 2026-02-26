"""Dialog for adding a new tag"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox,
    QCheckBox, QTextEdit, QDialogButtonBox, QMessageBox, QLabel
)
from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator
from ...models.data_types import DataType
from ..utils import center_dialog
from ..theme import COLORS


class AddTagDialog(QDialog):
    """Dialog for adding a new tag"""

    def __init__(self, tag_service, udt_service, parent=None):
        super().__init__(parent)
        self.tag_service = tag_service
        self.udt_service = udt_service

        self.setWindowTitle("Add New Tag")
        self.setFixedSize(450, 480)
        self._setup_ui()
        center_dialog(self, parent)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        form = QFormLayout()
        form.setSpacing(6)

        # Tag name with real-time validation
        self._name_edit = QLineEdit()
        regex = QRegularExpression(r'^[A-Za-z_][A-Za-z0-9_]{0,39}$')
        self._name_edit.setValidator(QRegularExpressionValidator(regex))
        self._name_edit.setMaxLength(40)
        self._name_edit.setPlaceholderText("e.g., My_Tag_Name")
        self._name_edit.textChanged.connect(self._validate_name)
        form.addRow("Tag Name:", self._name_edit)

        self._name_status = QLabel("")
        self._name_status.setStyleSheet("font-size: 10px;")
        form.addRow("", self._name_status)

        # Data type
        self._type_combo = QComboBox()
        types = [dt.type_name for dt in DataType]
        self._type_combo.addItems(types)
        self._type_combo.setCurrentText("DINT")
        self._type_combo.currentTextChanged.connect(self._on_type_changed)
        form.addRow("Data Type:", self._type_combo)

        # UDT selection (hidden by default)
        self._udt_label = QLabel("UDT Type:")
        self._udt_combo = QComboBox()
        self._populate_udt_combo()
        self._udt_label.setVisible(False)
        self._udt_combo.setVisible(False)
        form.addRow(self._udt_label, self._udt_combo)

        # Description
        self._desc_edit = QTextEdit()
        self._desc_edit.setMaximumHeight(60)
        self._desc_edit.setPlaceholderText("Optional description...")
        form.addRow("Description:", self._desc_edit)

        # Array controls
        self._array_check = QCheckBox("Array")
        self._array_check.toggled.connect(self._on_array_toggle)
        form.addRow("", self._array_check)

        self._dim_label = QLabel("Dimensions:")
        self._dim_edit = QLineEdit()
        self._dim_edit.setPlaceholderText("e.g., 10 or 5,10")
        self._dim_label.setVisible(False)
        self._dim_edit.setVisible(False)
        form.addRow(self._dim_label, self._dim_edit)

        # Initial value
        self._value_edit = QLineEdit("0")
        form.addRow("Initial Value:", self._value_edit)

        # Help text
        help_label = QLabel("Tag names: start with letter/underscore, alphanumeric + underscores, max 40 chars")
        help_label.setStyleSheet(f"color: {COLORS['text_disabled']}; font-size: 10px;")
        help_label.setWordWrap(True)
        form.addRow("", help_label)

        layout.addLayout(form)
        layout.addStretch()

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Create Tag")
        buttons.button(QDialogButtonBox.Ok).setProperty("class", "success")
        buttons.accepted.connect(self._on_create)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate_name(self, text):
        if not text:
            self._name_status.setText("")
        elif self._name_edit.hasAcceptableInput():
            self._name_status.setText("Valid")
            self._name_status.setStyleSheet(f"color: {COLORS['success']}; font-size: 10px;")
        else:
            self._name_status.setText("Invalid name")
            self._name_status.setStyleSheet(f"color: {COLORS['danger']}; font-size: 10px;")

    def _on_array_toggle(self, checked):
        self._dim_label.setVisible(checked)
        self._dim_edit.setVisible(checked)

    def _populate_udt_combo(self):
        """Populate UDT dropdown with available UDT definitions"""
        self._udt_combo.clear()
        udts = self.udt_service.get_all_udts()

        if not udts:
            self._udt_combo.addItem("<No UDTs defined>")
            self._udt_combo.setEnabled(False)
        else:
            for udt in sorted(udts, key=lambda u: u.name):
                self._udt_combo.addItem(udt.name)
            self._udt_combo.setEnabled(True)

    def _on_type_changed(self, type_name):
        """Show/hide UDT selector and value field based on type"""
        is_udt = type_name == "UDT"

        # Show UDT selector only for UDT type
        self._udt_label.setVisible(is_udt)
        self._udt_combo.setVisible(is_udt)

        # Disable value input for UDT (uses member defaults)
        if is_udt:
            self._value_edit.setEnabled(False)
            self._value_edit.setPlaceholderText("Default values from UDT members")
            self._value_edit.clear()
        else:
            self._value_edit.setEnabled(True)
            self._value_edit.setPlaceholderText("Initial value (optional)")
            if not self._value_edit.text():
                self._value_edit.setText("0")

    def _create_udt_instance(self, udt):
        """
        Create a UDT instance as a dict of member_name → default_value.

        Args:
            udt: UDT definition

        Returns:
            Dict of {member_name: default_value}
        """
        instance = {}
        for member in udt.members:
            if member.data_type == DataType.UDT:
                # Nested UDT (future enhancement - recursively create instance)
                # For now, set to None or empty dict
                instance[member.name] = None
            else:
                instance[member.name] = member.default_value

        return instance

    def _on_create(self):
        """Create the tag"""
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Tag name is required")
            return

        type_name = self._type_combo.currentText()
        try:
            data_type = DataType[type_name]
        except KeyError:
            QMessageBox.warning(self, "Error", f"Invalid data type: {type_name}")
            return

        # Handle array dimensions
        is_array = self._array_check.isChecked()
        array_dimensions = None

        if is_array:
            dim_str = self._dim_edit.text().strip()
            if not dim_str:
                QMessageBox.warning(self, "Error", "Array dimensions are required when Array is checked")
                return
            try:
                array_dimensions = [int(d.strip()) for d in dim_str.split(',')]
                if any(d <= 0 for d in array_dimensions):
                    raise ValueError("Dimensions must be positive")
            except ValueError as e:
                QMessageBox.warning(
                    self, "Error",
                    f"Invalid array dimensions: {e}\n\n"
                    f"Format: comma-separated positive integers\n"
                    f"Examples: 10 or 5,10 or 2,3,4"
                )
                return

        # UDT-specific handling
        udt_type_id = None
        value = None

        if data_type == DataType.UDT:
            if self._udt_combo.currentText() == "<No UDTs defined>":
                QMessageBox.warning(self, "Error", "No UDT definitions available. Create a UDT first.")
                return

            selected_udt_name = self._udt_combo.currentText()
            selected_udt = self.udt_service.get_udt_by_name(selected_udt_name)

            if not selected_udt:
                QMessageBox.critical(self, "Error", f"UDT '{selected_udt_name}' not found")
                return

            udt_type_id = selected_udt.udt_id

            # Generate UDT instance value(s)
            if is_array:
                # Create array of UDT instances
                total_elements = 1
                for dim in array_dimensions:
                    total_elements *= dim

                value = [self._create_udt_instance(selected_udt) for _ in range(total_elements)]
            else:
                # Single UDT instance
                value = self._create_udt_instance(selected_udt)

        else:
            # Non-UDT type: parse initial value
            value_str = self._value_edit.text().strip()
            try:
                if data_type == DataType.BOOL:
                    value = value_str.lower() in ('true', '1', 'yes')
                elif data_type in (DataType.SINT, DataType.INT, DataType.DINT, DataType.LINT,
                                   DataType.USINT, DataType.UINT, DataType.UDINT):
                    value = int(value_str) if value_str else 0
                elif data_type in (DataType.REAL, DataType.LREAL):
                    value = float(value_str) if value_str else 0.0
                elif data_type == DataType.STRING:
                    value = value_str
                else:
                    value = data_type.default_value
            except ValueError:
                QMessageBox.warning(
                    self, "Error",
                    f"Invalid value for type {type_name}.\n\n"
                    f"BOOL: true/false, 1/0\n"
                    f"INT types: integer number\n"
                    f"REAL types: decimal number\n"
                    f"STRING: any text"
                )
                return

            # For non-UDT arrays, let tag service handle array initialization
            if is_array:
                value = None

        # Create tag
        try:
            self.tag_service.create_tag(
                name=name,
                data_type=data_type,
                value=value,
                description=self._desc_edit.toPlainText().strip(),
                is_array=is_array,
                array_dimensions=array_dimensions,
                udt_type_id=udt_type_id
            )
            self.accept()

        except ValueError as e:
            QMessageBox.warning(self, "Validation Error", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create tag: {e}")
