"""Tag management panel UI"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeView, QPushButton,
    QLineEdit, QLabel, QMenu, QApplication, QHeaderView, QMessageBox
)
from PySide6.QtCore import Qt, QTimer, QSortFilterProxyModel
from PySide6.QtGui import QStandardItemModel, QStandardItem, QAction
from .theme import COLORS
from .undo_manager import UndoManager, TagEdit, UDTMemberEdit
from .tag_tree_helpers import (
    ROLE_TAG_ID, ROLE_ELEM_INDEX, ROLE_MEMBER_NAME, ROLE_UDT_ARRAY_INDEX,
    ROLE_BIT_INDEX,
    MAX_ARRAY_DISPLAY,
    format_display_value, apply_bool_styling,
    lookup_member_data_type, lookup_member_type_name,
    create_truncation_row,
    resolve_udt_member_value, resolve_udt_member_array_element,
)
from ..models.data_types import DataType, INTEGER_TYPES


class TagManagementPanel(QWidget):
    """Panel for managing tags (add, edit, delete)"""

    # Re-export role constants as class attributes for external access
    ROLE_TAG_ID = ROLE_TAG_ID
    ROLE_ELEM_INDEX = ROLE_ELEM_INDEX
    ROLE_MEMBER_NAME = ROLE_MEMBER_NAME
    ROLE_UDT_ARRAY_INDEX = ROLE_UDT_ARRAY_INDEX
    ROLE_BIT_INDEX = ROLE_BIT_INDEX

    def __init__(self, tag_service, udt_service, enip_server=None, main_window=None, parent=None):
        super().__init__(parent)
        self.tag_service = tag_service
        self.udt_service = udt_service
        self.enip_server = enip_server
        self.main_window = main_window
        self._inline_editing = False
        self._active_editor = None
        self._refresh_timer = None
        self._refresh_running = False
        self.undo_manager = UndoManager()

        self._setup_ui()
        self._load_tags()
        self._start_auto_refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)

        # Header
        header = QLabel("Tag Management")
        header.setStyleSheet("font-size: 16px; font-weight: bold; padding: 4px;")
        layout.addWidget(header)

        # Search bar
        search_layout = QHBoxLayout()
        search_layout.setSpacing(6)
        self._search_entry = QLineEdit()
        self._search_entry.setPlaceholderText("Search tags...")
        self._search_entry.textChanged.connect(self._on_search)
        search_layout.addWidget(self._search_entry)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._load_tags)
        search_layout.addWidget(refresh_btn)
        layout.addLayout(search_layout)

        # Tree view with model
        self._model = QStandardItemModel()
        self._model.setHorizontalHeaderLabels(["Tag Name", "Type", "Value", "Description"])

        self._proxy_model = QSortFilterProxyModel()
        self._proxy_model.setSourceModel(self._model)
        self._proxy_model.setRecursiveFilteringEnabled(True)
        self._proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._proxy_model.setFilterKeyColumn(0)

        self._tree = QTreeView()
        self._tree.setModel(self._proxy_model)
        self._tree.setAlternatingRowColors(True)
        self._tree.setEditTriggers(QTreeView.NoEditTriggers)
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)
        self._tree.doubleClicked.connect(self._on_double_click)
        self._tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._tree.setAnimated(True)
        self._tree.setIndentation(20)

        # Column sizing
        header_view = self._tree.header()
        header_view.setSectionResizeMode(0, QHeaderView.Interactive)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(2, QHeaderView.Interactive)
        header_view.setSectionResizeMode(3, QHeaderView.Stretch)
        header_view.resizeSection(0, 220)
        header_view.resizeSection(2, 140)

        layout.addWidget(self._tree)

        # Count label
        self._count_label = QLabel("Tags: 0")
        layout.addWidget(self._count_label)

        # Buttons
        btn_layout = QHBoxLayout()
        self._add_btn = QPushButton("Add Tag")
        self._add_btn.setProperty("class", "success")
        self._add_btn.clicked.connect(self._on_add_tag)
        btn_layout.addWidget(self._add_btn)

        self._edit_btn = QPushButton("Edit")
        self._edit_btn.setProperty("class", "primary")
        self._edit_btn.clicked.connect(self._on_edit_tag)
        btn_layout.addWidget(self._edit_btn)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setProperty("class", "danger")
        self._delete_btn.clicked.connect(self._on_delete_tag)
        btn_layout.addWidget(self._delete_btn)

        udt_btn = QPushButton("Manage UDTs")
        udt_btn.setProperty("class", "primary")
        udt_btn.clicked.connect(self._on_manage_udts)
        btn_layout.addWidget(udt_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def set_tag_editing_enabled(self, enabled: bool):
        """Enable or disable the Add/Edit/Delete buttons (e.g. while server is running)."""
        self._add_btn.setEnabled(enabled)
        self._edit_btn.setEnabled(enabled)
        self._delete_btn.setEnabled(enabled)

    # ── Tree building ──────────────────────────────────────────────

    def _insert_tag_row(self, tag):
        """Insert a single tag into the model"""
        name_item = QStandardItem(tag.name)
        name_item.setData(tag.tag_id, ROLE_TAG_ID)
        name_item.setEditable(False)

        type_item = QStandardItem(tag.data_type.type_name)
        type_item.setEditable(False)

        desc_item = QStandardItem(tag.description[:200] if tag.description else "")
        desc_item.setEditable(False)

        if not tag.is_array:
            is_udt = tag.data_type == DataType.UDT
            if is_udt and isinstance(tag.value, dict):
                value_text = f"{{UDT: {len(tag.value)} members}}"
            else:
                value_text = format_display_value(tag.value, tag.data_type)

            value_item = QStandardItem(value_text)
            value_item.setEditable(False)
            apply_bool_styling(value_item, tag.value, tag.data_type)
            self._model.appendRow([name_item, type_item, value_item, desc_item])

            if is_udt:
                self._add_udt_member_children(name_item, tag, parent_index=None)
            elif tag.data_type in INTEGER_TYPES:
                self._add_bit_children(name_item, tag)
            return

        # Array tag
        size = len(tag.value) if isinstance(tag.value, list) else 0
        if tag.data_type == DataType.UDT:
            value_item = QStandardItem(f"[{size} UDT instances]")
        else:
            value_item = QStandardItem(f"{{{size}}}")
        value_item.setEditable(False)
        self._model.appendRow([name_item, type_item, value_item, desc_item])

        values = tag.value if isinstance(tag.value, list) else []
        display_count = min(len(values), MAX_ARRAY_DISPLAY)
        is_udt = tag.data_type == DataType.UDT

        for i in range(display_count):
            elem_name = QStandardItem(f"[{i}]")
            elem_name.setData(tag.tag_id, ROLE_TAG_ID)
            elem_name.setData(i, ROLE_ELEM_INDEX)
            elem_name.setEditable(False)

            elem_type = QStandardItem(tag.data_type.type_name)
            elem_type.setEditable(False)

            elem_display = format_display_value(values[i], tag.data_type, is_udt_instance=is_udt)
            elem_value = QStandardItem(elem_display)
            elem_value.setEditable(False)
            apply_bool_styling(elem_value, values[i], tag.data_type)

            elem_desc = QStandardItem("")
            elem_desc.setEditable(False)
            name_item.appendRow([elem_name, elem_type, elem_value, elem_desc])

            if is_udt:
                self._add_udt_member_children(elem_name, tag, parent_index=i)
            elif tag.data_type in INTEGER_TYPES:
                self._add_bit_children(elem_name, tag, elem_index=i)

        trunc = create_truncation_row(len(values), MAX_ARRAY_DISPLAY)
        if trunc:
            name_item.appendRow(trunc)

    def _add_udt_member_children(self, parent_item, tag, parent_index=None):
        """Add child rows for UDT members."""
        if tag.data_type != DataType.UDT:
            return

        if parent_index is not None and isinstance(tag.value, list):
            if parent_index >= len(tag.value):
                return
            instance_dict = tag.value[parent_index]
        else:
            instance_dict = tag.value

        if not isinstance(instance_dict, dict):
            return

        for member_name, member_value in instance_dict.items():
            member_type = lookup_member_type_name(self.udt_service, tag, member_name)

            child_name = QStandardItem(f".{member_name}")
            child_name.setData(tag.tag_id, ROLE_TAG_ID)
            child_name.setData(member_name, ROLE_MEMBER_NAME)
            if parent_index is not None:
                child_name.setData(parent_index, ROLE_ELEM_INDEX)
            child_name.setEditable(False)

            child_type = QStandardItem(member_type)
            child_type.setEditable(False)

            child_value_text = format_display_value(member_value, member_type)
            child_value = QStandardItem(child_value_text)
            child_value.setEditable(False)

            if member_type == "BOOL" and not isinstance(member_value, list):
                apply_bool_styling(child_value, member_value, "BOOL")

            parent_item.appendRow([child_name, child_type, child_value, QStandardItem("")])

            if isinstance(member_value, list):
                self._add_array_member_children(
                    child_name, tag, member_name, member_value, member_type, parent_index)

    def _add_array_member_children(self, parent_item, tag, member_name,
                                    member_values, member_type_name, udt_array_index=None):
        """Add child rows for array elements within a UDT member."""
        display_count = min(len(member_values), MAX_ARRAY_DISPLAY)

        for i in range(display_count):
            elem_name = QStandardItem(f"[{i}]")
            elem_name.setData(tag.tag_id, ROLE_TAG_ID)
            elem_name.setData(member_name, ROLE_MEMBER_NAME)
            elem_name.setData(i, ROLE_ELEM_INDEX)
            if udt_array_index is not None:
                elem_name.setData(udt_array_index, ROLE_UDT_ARRAY_INDEX)
            elem_name.setEditable(False)

            elem_type = QStandardItem(member_type_name)
            elem_type.setEditable(False)

            elem_val = member_values[i]
            elem_value = QStandardItem(format_display_value(elem_val, member_type_name))
            elem_value.setEditable(False)
            apply_bool_styling(elem_value, elem_val, member_type_name)

            parent_item.appendRow([elem_name, elem_type, elem_value, QStandardItem("")])

        trunc = create_truncation_row(len(member_values), MAX_ARRAY_DISPLAY)
        if trunc:
            parent_item.appendRow(trunc)

    def _add_bit_children(self, parent_item, tag, elem_index=None):
        """Add child rows for individual bits of an integer tag value."""
        num_bits = tag.data_type.size_bytes * 8
        if elem_index is not None and isinstance(tag.value, list):
            int_val = tag.value[elem_index] if 0 <= elem_index < len(tag.value) else 0
        else:
            int_val = tag.value if isinstance(tag.value, int) else 0

        for bit in range(num_bits):
            bit_val = bool((int_val >> bit) & 1)

            bit_name = QStandardItem(f".{bit}")
            bit_name.setData(tag.tag_id, ROLE_TAG_ID)
            bit_name.setData(bit, ROLE_BIT_INDEX)
            if elem_index is not None:
                bit_name.setData(elem_index, ROLE_ELEM_INDEX)
            bit_name.setEditable(False)

            bit_type = QStandardItem("BOOL")
            bit_type.setEditable(False)

            bit_value = QStandardItem(str(bit_val))
            bit_value.setEditable(False)
            apply_bool_styling(bit_value, bit_val, DataType.BOOL)

            bit_desc = QStandardItem("")
            bit_desc.setEditable(False)

            parent_item.appendRow([bit_name, bit_type, bit_value, bit_desc])

    # ── Load / refresh ─────────────────────────────────────────────

    def _load_tags(self):
        """Load all tags into tree view"""
        self._model.removeRows(0, self._model.rowCount())
        tags = self.tag_service.get_all_tags()
        for tag in tags:
            self._insert_tag_row(tag)
        self._count_label.setText(f"Tags: {len(tags)}")
        if self.main_window:
            self.main_window.set_status(f"Loaded {len(tags)} tags")

    def _start_auto_refresh(self):
        """Start cancellable auto-refresh timer"""
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_values)
        self._refresh_timer.start(500)

    def stop_refresh(self):
        """Stop the refresh timer (called by MainWindow.closeEvent)"""
        if self._refresh_timer:
            self._refresh_timer.stop()

    def _get_live_value(self, tag, live_cache):
        """Get live value from cache if available, otherwise from tag's stored value"""
        if live_cache and tag.name in live_cache:
            return live_cache[tag.name]
        return tag.value

    def _refresh_values(self):
        """Update displayed values in-place without rebuilding the tree"""
        if self._refresh_running or self._inline_editing:
            return
        self._refresh_running = True
        try:
            live_cache = {}
            if self.enip_server and self.enip_server.tags_ready:
                live_cache = self.enip_server.read_all_tag_values()
            self._refresh_item_recursive(self._model.invisibleRootItem(), live_cache)
        finally:
            self._refresh_running = False

    def _refresh_item_recursive(self, parent_item, live_cache):
        is_array_parent = (parent_item is not self._model.invisibleRootItem())

        for row in range(parent_item.rowCount()):
            name_item = parent_item.child(row, 0)
            if not name_item:
                continue

            tag_id = name_item.data(ROLE_TAG_ID)
            if tag_id is None:
                continue

            elem_index = name_item.data(ROLE_ELEM_INDEX)
            if is_array_parent and elem_index is None:
                elem_index = 0  # PySide6 quirk: stored int(0) returns None

            tag = self.tag_service.get_tag_by_id(tag_id)
            if not tag:
                continue

            value_item = parent_item.child(row, 2)
            if not value_item:
                continue

            member_name = name_item.data(ROLE_MEMBER_NAME)
            live = self._get_live_value(tag, live_cache)

            # Bit row: extract bit from parent integer value
            bit_index = name_item.data(ROLE_BIT_INDEX)
            if bit_index is not None:
                if tag.is_array and isinstance(live, list) and elem_index is not None:
                    int_val = live[elem_index] if 0 <= elem_index < len(live) else 0
                else:
                    int_val = live if isinstance(live, int) else 0
                bit_val = bool((int_val >> bit_index) & 1)
                new_text = str(bit_val)
                if value_item.text() != new_text:
                    value_item.setText(new_text)
                apply_bool_styling(value_item, bit_val, DataType.BOOL)
                continue

            if member_name and elem_index is not None:
                udt_idx = name_item.data(ROLE_UDT_ARRAY_INDEX)
                if udt_idx is not None:
                    # Case B: Array element within a UDT member (e.g., [5] under .ArrayMember)
                    val, found = resolve_udt_member_array_element(
                        live, member_name, elem_index, udt_idx)
                    if found:
                        dt = lookup_member_data_type(self.udt_service, tag, member_name)
                        new_text = format_display_value(val, dt)
                        if value_item.text() != new_text:
                            value_item.setText(new_text)
                        apply_bool_styling(value_item, val, dt)
                else:
                    # Case A: Scalar member under UDT array element (e.g., .Status under [0])
                    val = resolve_udt_member_value(live, member_name, udt_array_index=elem_index)
                    if val is not None:
                        dt = lookup_member_data_type(self.udt_service, tag, member_name)
                        new_text = format_display_value(val, dt)
                        if value_item.text() != new_text:
                            value_item.setText(new_text)
                        apply_bool_styling(value_item, val, dt)

            elif member_name:
                val = resolve_udt_member_value(live, member_name, udt_array_index=elem_index)
                if val is not None:
                    dt = lookup_member_data_type(self.udt_service, tag, member_name)
                    new_text = format_display_value(val, dt)
                    if value_item.text() != new_text:
                        value_item.setText(new_text)
                    apply_bool_styling(value_item, val, dt)

            elif elem_index is not None and is_array_parent:
                if isinstance(live, list) and 0 <= elem_index < len(live):
                    is_udt = (tag.data_type == DataType.UDT)
                    new_text = format_display_value(
                        live[elem_index], tag.data_type, is_udt_instance=is_udt)
                    if value_item.text() != new_text:
                        value_item.setText(new_text)
                    apply_bool_styling(value_item, live[elem_index], tag.data_type)

            elif tag.is_array:
                size = len(tag.value) if isinstance(tag.value, list) else 0
                new_text = f"{{{size}}}"
                if value_item.text() != new_text:
                    value_item.setText(new_text)

            else:
                new_text = format_display_value(live, tag.data_type)
                if value_item.text() != new_text:
                    value_item.setText(new_text)
                apply_bool_styling(value_item, live, tag.data_type)

            self._refresh_item_recursive(name_item, live_cache)

    # ── Search ─────────────────────────────────────────────────────

    def _on_search(self, text):
        self._proxy_model.setFilterFixedString(text)

    # ── Dialogs ────────────────────────────────────────────────────

    def _on_add_tag(self):
        from .dialogs.add_tag_dialog import AddTagDialog
        dialog = AddTagDialog(self.tag_service, self.udt_service, self)
        if dialog.exec():
            self._load_tags()

    def _on_edit_tag(self):
        indexes = self._tree.selectionModel().selectedRows()
        if not indexes:
            QMessageBox.warning(self, "No Selection", "Please select a tag to edit.")
            return

        proxy_index = indexes[0]
        source_index = self._proxy_model.mapToSource(proxy_index)
        col0_index = source_index.sibling(source_index.row(), 0)
        name_item = self._model.itemFromIndex(col0_index)
        if not name_item:
            return

        tag_id = name_item.data(ROLE_TAG_ID)
        if tag_id is None:
            QMessageBox.warning(self, "Invalid Selection",
                                "Cannot edit array element. Please select the parent tag.")
            return

        tag = self.tag_service.get_tag_by_id(tag_id)
        if not tag:
            QMessageBox.warning(self, "Error", "Tag not found.")
            return

        from .dialogs.edit_tag_dialog import EditTagDialog
        dialog = EditTagDialog(tag, self.tag_service, self.enip_server, self)
        if dialog.exec():
            self._load_tags()

    def _on_manage_udts(self):
        from .dialogs.udt_manager_dialog import UDTManagerDialog
        dialog = UDTManagerDialog(self.udt_service, self)
        if dialog.exec():
            self._load_tags()
            if self.main_window:
                self.main_window.set_status("UDT changes saved")

    # ── Double-click / inline editing ──────────────────────────────

    def _on_double_click(self, proxy_index):
        source_index = self._proxy_model.mapToSource(proxy_index)
        col0_index = source_index.sibling(source_index.row(), 0)
        name_item = self._model.itemFromIndex(col0_index)
        if not name_item:
            return

        tag_id = name_item.data(ROLE_TAG_ID)
        if tag_id is None:
            return

        tag = self.tag_service.get_tag_by_id(tag_id)
        if not tag:
            return

        # Bit row: toggle the individual bit
        bit_index = name_item.data(ROLE_BIT_INDEX)
        if bit_index is not None:
            elem_index = name_item.data(ROLE_ELEM_INDEX)
            self._toggle_bit(tag, bit_index, elem_index, col0_index)
            return

        member_name = name_item.data(ROLE_MEMBER_NAME)
        udt_array_index_from_role = name_item.data(ROLE_UDT_ARRAY_INDEX)
        member_elem_index = None

        if member_name and udt_array_index_from_role is not None:
            # Member array element row: e.g. [0] under .Bead_Type
            # ROLE_UDT_ARRAY_INDEX = which UDT in the parent array
            # ROLE_ELEM_INDEX = which element within the member array
            parent_array_index = udt_array_index_from_role
            member_elem_index = name_item.data(ROLE_ELEM_INDEX)
            if member_elem_index is None:
                member_elem_index = 0  # PySide6 quirk: stored int(0) returns None
        elif member_name:
            # Member row: e.g. .Bead_Type under [5]
            # ROLE_ELEM_INDEX = which UDT in the parent array
            parent_array_index = name_item.data(ROLE_ELEM_INDEX)
        else:
            parent_array_index = None

        # UDT member row or member array element row
        if member_name:
            member_dt = lookup_member_data_type(self.udt_service, tag, member_name)
            if source_index.column() != 2:
                proxy_index = proxy_index.sibling(proxy_index.row(), 2)

            # Array member row (.Bead_Type where value is a list): expand/collapse
            if member_elem_index is None and parent_array_index is not None:
                if isinstance(tag.value, list) and isinstance(tag.value[parent_array_index].get(member_name), list):
                    proxy_col0 = proxy_index.sibling(proxy_index.row(), 0)
                    if not self._tree.isExpanded(proxy_col0):
                        self._tree.expand(proxy_col0)
                    else:
                        self._tree.collapse(proxy_col0)
                    return

            if member_dt == DataType.BOOL:
                self._toggle_udt_member_bool(tag, member_name, parent_array_index, col0_index, member_elem_index)
            else:
                self._show_udt_member_editor(proxy_index, tag, member_name, member_dt, parent_array_index, member_elem_index)
            return

        # UDT parent row: expand/collapse
        if tag.data_type == DataType.UDT:
            proxy_col0 = proxy_index.sibling(proxy_index.row(), 0)
            if not self._tree.isExpanded(proxy_col0):
                self._tree.expand(proxy_col0)
            return

        # Detect array element via tree structure (PySide6 data() quirk for int(0))
        is_child_item = (name_item.parent() is not None
                         and name_item.parent() is not self._model.invisibleRootItem())
        elem_index = name_item.data(ROLE_ELEM_INDEX)
        if is_child_item and elem_index is None:
            elem_index = 0

        # Array parent: expand/collapse
        if tag.is_array and not is_child_item:
            proxy_col0 = proxy_index.sibling(proxy_index.row(), 0)
            if not self._tree.isExpanded(proxy_col0):
                self._tree.expand(proxy_col0)
            if self.main_window:
                self.main_window.set_status(
                    "Expand the array and double-click individual elements to edit")
            return

        if source_index.column() != 2:
            proxy_index = proxy_index.sibling(proxy_index.row(), 2)

        if tag.data_type == DataType.BOOL:
            self._toggle_bool(tag, elem_index, col0_index)
        else:
            self._show_inline_editor(proxy_index, tag, elem_index)

    def _toggle_bool(self, tag, elem_index, col0_index):
        saved_value = tag.value if not tag.is_array else list(tag.value)
        try:
            if tag.is_array:
                if not isinstance(tag.value, list) or elem_index is None:
                    return
                if not (0 <= elem_index < len(tag.value)):
                    return
                old_val = bool(tag.value[elem_index])
                new_val = not old_val
                tag.value[elem_index] = new_val
                self.undo_manager.push(TagEdit(tag.tag_id, old_val, new_val, elem_index))
                self.tag_service.update_tag(tag)
                if self.enip_server:
                    self.enip_server.write_tag_value(tag.name, tag.value, is_array=True)
            else:
                old_val = bool(tag.value)
                new_val = not old_val
                tag.value = new_val
                self.undo_manager.push(TagEdit(tag.tag_id, old_val, new_val))
                self.tag_service.update_tag(tag)
                if self.enip_server:
                    self.enip_server.write_tag_value(tag.name, new_val)

            val2_index = col0_index.sibling(col0_index.row(), 2)
            value_item = self._model.itemFromIndex(val2_index)
            if value_item:
                value_item.setText(str(bool(new_val)))
                apply_bool_styling(value_item, new_val, tag.data_type)
        except Exception as e:
            tag.value = saved_value
            if self.main_window:
                self.main_window.set_status(f"Failed to toggle: {e}")

    def _xor_bit_twos_complement(self, data_type, old_int, bit_index):
        """Toggle a bit using proper two's complement for signed types."""
        num_bits = data_type.size_bytes * 8
        mask = (1 << num_bits) - 1
        # Work in unsigned space
        unsigned = old_int & mask
        unsigned ^= (1 << bit_index)
        # Convert back to signed if this is a signed type
        if data_type.min_value is not None and data_type.min_value < 0:
            if unsigned >= (1 << (num_bits - 1)):
                return unsigned - (1 << num_bits)
        return unsigned

    def _toggle_bit(self, tag, bit_index, elem_index, col0_index):
        """Toggle a single bit within an integer tag value."""
        saved_value = tag.value if not tag.is_array else list(tag.value)
        try:
            if tag.is_array and isinstance(tag.value, list) and elem_index is not None:
                old_int = int(tag.value[elem_index])
                new_int = self._xor_bit_twos_complement(tag.data_type, old_int, bit_index)
                tag.value[elem_index] = new_int
                self.undo_manager.push(TagEdit(tag.tag_id, old_int, new_int, elem_index))
                self.tag_service.update_tag(tag)
                if self.enip_server:
                    self.enip_server.write_tag_value(tag.name, tag.value, is_array=True)
            else:
                old_int = int(tag.value) if isinstance(tag.value, int) else 0
                new_int = self._xor_bit_twos_complement(tag.data_type, old_int, bit_index)
                tag.value = new_int
                self.undo_manager.push(TagEdit(tag.tag_id, old_int, new_int))
                self.tag_service.update_tag(tag)
                if self.enip_server:
                    self.enip_server.write_tag_value(tag.name, new_int)

            # Update the bit row's value cell
            val2_index = col0_index.sibling(col0_index.row(), 2)
            value_item = self._model.itemFromIndex(val2_index)
            if value_item:
                bit_val = bool((new_int >> bit_index) & 1)
                value_item.setText(str(bit_val))
                apply_bool_styling(value_item, bit_val, DataType.BOOL)

            if self.main_window:
                self.main_window.set_status(
                    f"Toggled {tag.name}.{bit_index} → {new_int}")
        except Exception as e:
            tag.value = saved_value
            if self.main_window:
                self.main_window.set_status(f"Failed to toggle bit: {e}")

    def _close_active_editor(self):
        if self._active_editor is not None:
            self._active_editor.deleteLater()
            self._active_editor = None
        self._inline_editing = False

    def _show_inline_editor(self, proxy_index, tag, elem_index):
        rect = self._tree.visualRect(proxy_index)
        if not rect.isValid():
            return

        self._close_active_editor()
        self._inline_editing = True

        editor = QLineEdit(self._tree.viewport())
        editor.setGeometry(rect)
        self._active_editor = editor

        if elem_index is not None:
            current_val = tag.value[elem_index] if isinstance(tag.value, list) and 0 <= elem_index < len(tag.value) else ""
        else:
            current_val = tag.value

        editor.setText(str(current_val))
        editor.selectAll()
        editor.show()
        editor.setFocus()

        committed = [False]

        def finish_editing():
            editor.deleteLater()
            self._active_editor = None
            self._inline_editing = False

        def commit():
            if committed[0]:
                return
            committed[0] = True
            val_str = editor.text().strip()
            finish_editing()

            saved_value = tag.value if not tag.is_array else list(tag.value)
            try:
                if tag.data_type in (DataType.REAL, DataType.LREAL):
                    val = float(val_str)
                elif tag.data_type == DataType.STRING:
                    val = val_str
                else:
                    val = int(val_str)
                val = tag.data_type.clamp_value(val)

                if elem_index is not None:
                    if isinstance(tag.value, list) and 0 <= elem_index < len(tag.value):
                        old_val = tag.value[elem_index]
                        tag.value[elem_index] = val
                        self.undo_manager.push(TagEdit(tag.tag_id, old_val, val, elem_index))
                        self.tag_service.update_tag(tag)
                        if self.enip_server:
                            self.enip_server.write_tag_value(tag.name, tag.value, is_array=True)
                else:
                    old_val = tag.value
                    tag.value = val
                    self.undo_manager.push(TagEdit(tag.tag_id, old_val, val))
                    self.tag_service.update_tag(tag)
                    if self.enip_server:
                        self.enip_server.write_tag_value(tag.name, val)
            except (ValueError, TypeError):
                tag.value = saved_value

        def cancel():
            if committed[0]:
                return
            committed[0] = True
            finish_editing()

        def on_key_press(event):
            if event.key() == Qt.Key_Escape:
                cancel()
            else:
                QLineEdit.keyPressEvent(editor, event)

        editor.keyPressEvent = on_key_press
        editor.returnPressed.connect(commit)
        editor.editingFinished.connect(commit)

    def _show_udt_member_editor(self, proxy_index, tag, member_name,
                                 member_data_type, parent_array_index, member_elem_index=None):
        """Inline editor for a UDT member value or a specific element within a member array.

        Args:
            member_elem_index: If set, edit tag.value[parent_array_index][member_name][member_elem_index]
                               instead of the whole member.
        """
        source_index = self._proxy_model.mapToSource(proxy_index)
        value_item = self._model.itemFromIndex(source_index)
        if not value_item:
            return

        if parent_array_index is not None:
            current_value = tag.value[parent_array_index].get(member_name, 0)
        else:
            current_value = tag.value.get(member_name, 0)

        # For member array element rows, drill into the specific element
        if member_elem_index is not None and isinstance(current_value, list):
            current_value = current_value[member_elem_index]

        saved_value = current_value

        rect = self._tree.visualRect(proxy_index)
        self._close_active_editor()
        self._inline_editing = True

        editor = QLineEdit(self._tree.viewport())
        editor.setGeometry(rect)
        self._active_editor = editor
        editor.setText(str(current_value))
        editor.selectAll()
        editor.show()
        editor.setFocus()

        committed = [False]

        def finish_editing():
            editor.deleteLater()
            self._active_editor = None
            self._inline_editing = False

        def commit():
            if committed[0]:
                return
            committed[0] = True

            try:
                value_str = editor.text().strip()
                if member_data_type in (DataType.REAL, DataType.LREAL):
                    new_val = float(value_str)
                elif member_data_type == DataType.STRING:
                    new_val = value_str
                else:
                    new_val = int(value_str)
                new_val = member_data_type.clamp_value(new_val)

                if member_elem_index is not None:
                    # Update a specific element within a member array
                    if parent_array_index is not None:
                        tag.value[parent_array_index][member_name][member_elem_index] = new_val
                    else:
                        tag.value[member_name][member_elem_index] = new_val
                else:
                    # Update the whole member (scalar member)
                    if parent_array_index is not None:
                        tag.value[parent_array_index][member_name] = new_val
                    else:
                        tag.value[member_name] = new_val

                self.undo_manager.push(UDTMemberEdit(
                    tag_id=tag.tag_id,
                    member_name=member_name,
                    old_value=saved_value,
                    new_value=new_val,
                    array_index=parent_array_index
                ))
                self.tag_service.update_tag(tag)
                value_item.setText(str(new_val))

                if self.main_window:
                    idx_str = f"[{member_elem_index}]" if member_elem_index is not None else ""
                    self.main_window.set_status(f"Updated {tag.name}.{member_name}{idx_str} = {new_val}")
            except ValueError:
                # Rollback: restore original value
                if member_elem_index is not None:
                    if parent_array_index is not None:
                        tag.value[parent_array_index][member_name][member_elem_index] = saved_value
                    else:
                        tag.value[member_name][member_elem_index] = saved_value
                else:
                    if parent_array_index is not None:
                        tag.value[parent_array_index][member_name] = saved_value
                    else:
                        tag.value[member_name] = saved_value
                QMessageBox.warning(self, "Invalid Value",
                                    f"Could not parse '{editor.text()}' as {member_data_type.type_name}")
            finally:
                finish_editing()

        def cancel():
            if committed[0]:
                return
            committed[0] = True
            finish_editing()

        def on_key_press(event):
            if event.key() == Qt.Key_Escape:
                cancel()
            else:
                QLineEdit.keyPressEvent(editor, event)

        editor.keyPressEvent = on_key_press
        editor.returnPressed.connect(commit)
        editor.editingFinished.connect(commit)

    def _toggle_udt_member_bool(self, tag, member_name, parent_array_index, col0_index, member_elem_index=None):
        """Toggle a BOOL member value, or a specific element within a BOOL array member."""
        if parent_array_index is not None:
            member_val = tag.value[parent_array_index].get(member_name, False)
        else:
            member_val = tag.value.get(member_name, False)

        if member_elem_index is not None and isinstance(member_val, list):
            # Toggle specific element within a BOOL array member
            old_val = member_val[member_elem_index]
            new_val = not old_val
            member_val[member_elem_index] = new_val
        else:
            # Toggle the whole scalar BOOL member
            old_val = member_val
            new_val = not old_val
            if parent_array_index is not None:
                tag.value[parent_array_index][member_name] = new_val
            else:
                tag.value[member_name] = new_val

        self.undo_manager.push(UDTMemberEdit(
            tag_id=tag.tag_id,
            member_name=member_name,
            old_value=old_val,
            new_value=new_val,
            array_index=parent_array_index
        ))
        self.tag_service.update_tag(tag)

        value_col_index = col0_index.sibling(col0_index.row(), 2)
        value_item = self._model.itemFromIndex(value_col_index)
        if value_item:
            value_item.setText(str(new_val))
            apply_bool_styling(value_item, new_val, "BOOL")

        if self.main_window:
            idx_str = f"[{member_elem_index}]" if member_elem_index is not None else ""
            self.main_window.set_status(f"Toggled {tag.name}.{member_name}{idx_str} -> {new_val}")

    # ── Context menu ───────────────────────────────────────────────

    def _show_context_menu(self, position):
        index = self._tree.indexAt(position)
        if not index.isValid():
            return

        source_index = self._proxy_model.mapToSource(index)
        col0_index = source_index.sibling(source_index.row(), 0)
        name_item = self._model.itemFromIndex(col0_index)
        if not name_item:
            return

        menu = QMenu(self)
        tag_id = name_item.data(ROLE_TAG_ID)

        if tag_id is not None:
            edit_action = QAction("Edit Tag...", self)
            edit_action.triggered.connect(self._on_edit_tag)
            menu.addAction(edit_action)
            menu.addSeparator()

        copy_name = QAction("Copy Tag Name", self)
        copy_name.triggered.connect(lambda: QApplication.clipboard().setText(name_item.text()))
        menu.addAction(copy_name)

        col2_index = source_index.sibling(source_index.row(), 2)
        value_item = self._model.itemFromIndex(col2_index)
        if value_item:
            copy_value = QAction("Copy Value", self)
            copy_value.triggered.connect(
                lambda: QApplication.clipboard().setText(value_item.text()))
            menu.addAction(copy_value)

        menu.addSeparator()

        if tag_id is not None:
            delete_action = QAction("Delete Tag", self)
            delete_action.triggered.connect(
                lambda: self._delete_tag_by_id(tag_id, name_item.text()))
            menu.addAction(delete_action)

        menu.exec(self._tree.viewport().mapToGlobal(position))

    # ── Delete ─────────────────────────────────────────────────────

    def _on_delete_tag(self):
        indexes = self._tree.selectionModel().selectedRows()
        if not indexes:
            if self.main_window:
                self.main_window.set_status("No tag selected to delete")
            return

        source_index = self._proxy_model.mapToSource(indexes[0])
        col0_index = source_index.sibling(source_index.row(), 0)
        name_item = self._model.itemFromIndex(col0_index)
        if not name_item:
            return

        tag_id = name_item.data(ROLE_TAG_ID)
        if tag_id is None:
            return
        self._delete_tag_by_id(tag_id, name_item.text())

    def _delete_tag_by_id(self, tag_id, tag_name):
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete tag '{tag_name}'?\n\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                self.tag_service.delete_tag(tag_id)
                self._load_tags()
                if self.main_window:
                    self.main_window.set_status(f"Tag '{tag_name}' deleted")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete tag: {e}")

    # ── Undo / redo ────────────────────────────────────────────────

    def perform_undo(self):
        edit = self.undo_manager.undo()
        if not edit:
            return
        if isinstance(edit, UDTMemberEdit):
            self._apply_udt_member_edit_value(
                edit.tag_id, edit.member_name, edit.old_value, edit.array_index)
        else:
            self._apply_edit_value(edit.tag_id, edit.old_value, edit.elem_index)
        if self.main_window:
            self.main_window.set_status("Undo: value restored")

    def perform_redo(self):
        edit = self.undo_manager.redo()
        if not edit:
            return
        if isinstance(edit, UDTMemberEdit):
            self._apply_udt_member_edit_value(
                edit.tag_id, edit.member_name, edit.new_value, edit.array_index)
        else:
            self._apply_edit_value(edit.tag_id, edit.new_value, edit.elem_index)
        if self.main_window:
            self.main_window.set_status("Redo: value re-applied")

    def _apply_edit_value(self, tag_id, value, elem_index):
        tag = self.tag_service.get_tag_by_id(tag_id)
        if not tag:
            return
        if elem_index is not None:
            if isinstance(tag.value, list) and 0 <= elem_index < len(tag.value):
                tag.value[elem_index] = value
                self.tag_service.update_tag(tag)
                if self.enip_server:
                    self.enip_server.write_tag_value(tag.name, tag.value, is_array=True)
        else:
            tag.value = value
            self.tag_service.update_tag(tag)
            if self.enip_server:
                self.enip_server.write_tag_value(tag.name, value)

    def _apply_udt_member_edit_value(self, tag_id, member_name, value, array_index):
        tag = self.tag_service.get_tag_by_id(tag_id)
        if not tag or tag.data_type != DataType.UDT:
            return
        if array_index is not None:
            if isinstance(tag.value, list) and 0 <= array_index < len(tag.value):
                if isinstance(tag.value[array_index], dict):
                    tag.value[array_index][member_name] = value
                    self.tag_service.update_tag(tag)
                    self._load_tags()
        else:
            if isinstance(tag.value, dict):
                tag.value[member_name] = value
                self.tag_service.update_tag(tag)
                self._load_tags()
