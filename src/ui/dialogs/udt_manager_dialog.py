"""Dialog for creating and managing UDTs"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
                                QTextEdit, QTableWidget, QTableWidgetItem, QPushButton,
                                QLabel, QListWidget, QDialogButtonBox, QMessageBox, QHeaderView)
from PySide6.QtCore import QRegularExpression, Qt
from PySide6.QtGui import QRegularExpressionValidator
from ...services.udt_service import UDTService
from ...models.udt import UDT, UDTMember
from .add_member_dialog import AddMemberDialog
from ..utils import center_dialog
from ..theme import COLORS


class UDTManagerDialog(QDialog):
    """Dialog for creating and managing User Defined Types"""

    def __init__(self, udt_service: UDTService, parent=None):
        super().__init__(parent)
        self.udt_service = udt_service
        self.current_members: list[UDTMember] = []
        self.current_udt_id = None  # Track if editing existing UDT

        self.setWindowTitle("Manage UDTs")
        self.setFixedSize(750, 650)
        self._setup_ui()
        center_dialog(self, parent)
        self._load_existing_udts()

    def _setup_ui(self):
        """Set up the dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Form section for UDT name and description
        form = QFormLayout()
        form.setSpacing(6)

        # UDT Name with validation
        self._name_edit = QLineEdit()
        regex = QRegularExpression(r'^[A-Za-z_][A-Za-z0-9_]{0,39}$')
        self._name_edit.setValidator(QRegularExpressionValidator(regex))
        self._name_edit.setMaxLength(40)
        self._name_edit.setPlaceholderText("e.g., TemperatureReading")
        form.addRow("UDT Name:", self._name_edit)

        # Description
        self._desc_edit = QTextEdit()
        self._desc_edit.setMaximumHeight(60)
        self._desc_edit.setPlaceholderText("Optional description...")
        form.addRow("Description:", self._desc_edit)

        layout.addLayout(form)

        # Members section
        members_label = QLabel("Members:")
        members_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        layout.addWidget(members_label)

        # Members table
        self._members_table = QTableWidget(0, 4)
        self._members_table.setHorizontalHeaderLabels(["Name", "Type", "Array", "Dimensions"])
        self._members_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._members_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._members_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._members_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._members_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._members_table.setMaximumHeight(200)
        layout.addWidget(self._members_table)

        # Member management buttons
        member_btn_layout = QHBoxLayout()
        add_member_btn = QPushButton("Add Member")
        add_member_btn.setProperty("class", "success")
        add_member_btn.clicked.connect(self._on_add_member)

        edit_member_btn = QPushButton("Edit Member")
        edit_member_btn.clicked.connect(self._on_edit_member)

        remove_member_btn = QPushButton("Remove Member")
        remove_member_btn.setProperty("class", "danger")
        remove_member_btn.clicked.connect(self._on_remove_member)

        member_btn_layout.addWidget(add_member_btn)
        member_btn_layout.addWidget(edit_member_btn)
        member_btn_layout.addWidget(remove_member_btn)
        member_btn_layout.addStretch()
        layout.addLayout(member_btn_layout)

        # Existing UDTs section
        existing_label = QLabel("Existing UDTs:")
        existing_label.setStyleSheet("font-weight: bold; font-size: 11px; margin-top: 10px;")
        layout.addWidget(existing_label)

        self._udt_list = QListWidget()
        self._udt_list.setMaximumHeight(120)
        self._udt_list.itemDoubleClicked.connect(self._on_load_udt)
        layout.addWidget(self._udt_list)

        # UDT management buttons
        udt_btn_layout = QHBoxLayout()
        load_btn = QPushButton("Load Selected")
        load_btn.clicked.connect(self._on_load_udt)

        delete_btn = QPushButton("Delete Selected")
        delete_btn.setProperty("class", "danger")
        delete_btn.clicked.connect(self._on_delete_udt)

        clear_btn = QPushButton("Clear Form")
        clear_btn.clicked.connect(self._clear_form)

        udt_btn_layout.addWidget(load_btn)
        udt_btn_layout.addWidget(delete_btn)
        udt_btn_layout.addWidget(clear_btn)
        udt_btn_layout.addStretch()
        layout.addLayout(udt_btn_layout)

        layout.addStretch()

        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Create UDT")
        buttons.button(QDialogButtonBox.Ok).setProperty("class", "success")
        buttons.accepted.connect(self._on_create)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_existing_udts(self):
        """Load existing UDTs into the list"""
        self._udt_list.clear()
        udts = self.udt_service.get_all_udts()
        for udt in udts:
            member_count = len(udt.members)
            item_text = f"{udt.name} ({member_count} member{'s' if member_count != 1 else ''})"
            self._udt_list.addItem(item_text)

    def _refresh_members_table(self):
        """Refresh the members table display"""
        self._members_table.setRowCount(0)

        for member in self.current_members:
            row = self._members_table.rowCount()
            self._members_table.insertRow(row)

            # Name
            self._members_table.setItem(row, 0, QTableWidgetItem(member.name))

            # Type
            self._members_table.setItem(row, 1, QTableWidgetItem(member.data_type.type_name))

            # Array
            array_text = "Yes" if member.is_array else "No"
            self._members_table.setItem(row, 2, QTableWidgetItem(array_text))

            # Dimensions
            if member.is_array and member.array_dimensions:
                dim_text = ','.join(str(d) for d in member.array_dimensions)
                self._members_table.setItem(row, 3, QTableWidgetItem(dim_text))
            else:
                self._members_table.setItem(row, 3, QTableWidgetItem(""))

    def _on_add_member(self):
        """Open dialog to add a UDT member"""
        dialog = AddMemberDialog(parent=self)
        if dialog.exec():
            member = dialog.get_member()
            self.current_members.append(member)
            self._refresh_members_table()

    def _on_edit_member(self):
        """Edit selected member"""
        selected_rows = self._members_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select a member to edit")
            return

        row = selected_rows[0].row()
        member = self.current_members[row]

        dialog = AddMemberDialog(member=member, parent=self)
        if dialog.exec():
            updated_member = dialog.get_member()
            self.current_members[row] = updated_member
            self._refresh_members_table()

    def _on_remove_member(self):
        """Remove selected member"""
        selected_rows = self._members_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select a member to remove")
            return

        row = selected_rows[0].row()
        member_name = self.current_members[row].name

        reply = QMessageBox.question(
            self, "Confirm Removal",
            f"Remove member '{member_name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            del self.current_members[row]
            self._refresh_members_table()

    def _on_load_udt(self):
        """Load selected UDT for editing"""
        selected_items = self._udt_list.selectedItems()
        if not selected_items:
            return

        # Extract UDT name from list item text (format: "Name (N members)")
        item_text = selected_items[0].text()
        udt_name = item_text.split(' (')[0]

        udt = self.udt_service.get_udt_by_name(udt_name)
        if not udt:
            QMessageBox.warning(self, "Error", f"UDT '{udt_name}' not found")
            return

        # Populate form
        self._name_edit.setText(udt.name)
        self._desc_edit.setPlainText(udt.description)
        self.current_members = udt.members.copy()
        self.current_udt_id = udt.udt_id
        self._refresh_members_table()

        # Change button text to indicate update
        button_box = self.findChild(QDialogButtonBox)
        if button_box:
            button_box.button(QDialogButtonBox.Ok).setText("Update UDT")

    def _on_delete_udt(self):
        """Delete selected UDT"""
        selected_items = self._udt_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a UDT to delete")
            return

        # Extract UDT name
        item_text = selected_items[0].text()
        udt_name = item_text.split(' (')[0]

        reply = QMessageBox.question(
            self, "Confirm Deletion",
            f"Delete UDT '{udt_name}'?\n\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            udt = self.udt_service.get_udt_by_name(udt_name)
            if udt and udt.udt_id:
                if self.udt_service.delete_udt(udt.udt_id):
                    self._load_existing_udts()
                    QMessageBox.information(self, "Success", f"UDT '{udt_name}' deleted")
                else:
                    QMessageBox.critical(self, "Error", f"Failed to delete UDT '{udt_name}'")

    def _clear_form(self):
        """Clear the form for creating a new UDT"""
        self._name_edit.clear()
        self._desc_edit.clear()
        self.current_members.clear()
        self.current_udt_id = None
        self._refresh_members_table()

        # Reset button text
        button_box = self.findChild(QDialogButtonBox)
        if button_box:
            button_box.button(QDialogButtonBox.Ok).setText("Create UDT")

    def _on_create(self):
        """Create or update UDT"""
        name = self._name_edit.text().strip()
        description = self._desc_edit.toPlainText().strip()

        if not name:
            QMessageBox.warning(self, "Error", "UDT name is required")
            return

        if not self._name_edit.hasAcceptableInput():
            QMessageBox.warning(
                self, "Error",
                "Invalid UDT name. Must start with letter/underscore, "
                "contain only alphanumeric characters and underscores."
            )
            return

        if not self.current_members:
            QMessageBox.warning(self, "Error", "At least one member is required")
            return

        try:
            if self.current_udt_id:
                # Update existing UDT
                udt = UDT(
                    udt_id=self.current_udt_id,
                    name=name,
                    description=description,
                    members=self.current_members.copy()
                )
                self.udt_service.update_udt(udt)
                QMessageBox.information(self, "Success", f"UDT '{name}' updated successfully")
            else:
                # Create new UDT
                self.udt_service.create_udt(name, description, self.current_members.copy())
                QMessageBox.information(self, "Success", f"UDT '{name}' created successfully")

            self.accept()

        except ValueError as e:
            QMessageBox.warning(self, "Validation Error", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save UDT: {e}")
