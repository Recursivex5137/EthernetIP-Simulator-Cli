"""Dialog for configuring server settings"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox,
    QDialogButtonBox, QMessageBox, QLabel, QHBoxLayout, QPushButton
)
from ...services.network_service import NetworkService
from ..utils import center_dialog
from ..theme import COLORS


class ServerConfigDialog(QDialog):
    """Dialog for configuring Ethernet/IP server address and port"""

    def __init__(self, config_service, enip_server, parent=None):
        super().__init__(parent)
        self.config_service = config_service
        self.enip_server = enip_server
        self.network_service = NetworkService()

        self.setWindowTitle("Server Configuration")
        self.setFixedSize(450, 300)
        self._setup_ui()
        center_dialog(self, parent)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Title
        title = QLabel("Ethernet/IP Server Configuration")
        title.setStyleSheet("font-size: 14px; font-weight: bold; padding: 4px;")
        layout.addWidget(title)

        # Info label
        info_label = QLabel("Select your network connection (Ethernet, WiFi, VPN, etc.)")
        info_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px; padding: 2px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        form = QFormLayout()
        form.setSpacing(6)

        # IP Address - ComboBox with Refresh button
        ip_layout = QHBoxLayout()
        ip_layout.setSpacing(4)

        self._address_combo = QComboBox()
        self._address_combo.setEditable(True)
        self._address_combo.setMinimumHeight(32)
        self._address_combo.setToolTip("Select network interface: WiFi, Ethernet, VPN, or use 0.0.0.0 for all")
        # Add custom styling to make dropdown button more visible
        self._address_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {COLORS['bg_input']};
                border: 2px solid {COLORS['border']};
                border-radius: 4px;
                padding: 4px 8px;
                padding-right: 30px;
                color: {COLORS['text_primary']};
                font-size: 12px;
                font-weight: bold;
            }}
            QComboBox:hover {{
                border-color: {COLORS['border_focus']};
            }}
            QComboBox:focus {{
                border-color: {COLORS['accent']};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 25px;
                background: {COLORS['accent']};
                border-top-right-radius: 3px;
                border-bottom-right-radius: 3px;
            }}
            QComboBox::drop-down:hover {{
                background: {COLORS['accent_hover']};
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid {COLORS['text_primary']};
                width: 0px;
                height: 0px;
                margin-right: 8px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {COLORS['bg_secondary']};
                border: 2px solid {COLORS['border']};
                selection-background-color: {COLORS['accent']};
                selection-color: {COLORS['text_primary']};
                color: {COLORS['text_primary']};
                padding: 4px;
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 28px;
                padding: 4px 8px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {COLORS['accent_hover']};
            }}
        """)
        self._populate_interfaces()
        ip_layout.addWidget(self._address_combo, stretch=1)

        self._refresh_btn = QPushButton("↻ Refresh")
        self._refresh_btn.setMinimumHeight(32)
        self._refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['bg_tertiary']};
                border: 2px solid {COLORS['border']};
                border-radius: 4px;
                padding: 4px 12px;
                color: {COLORS['text_primary']};
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {COLORS['accent']};
                border-color: {COLORS['accent']};
            }}
            QPushButton:pressed {{
                background-color: {COLORS['accent_pressed']};
            }}
        """)
        self._refresh_btn.setToolTip("Refresh network interfaces list")
        self._refresh_btn.clicked.connect(self._populate_interfaces)
        ip_layout.addWidget(self._refresh_btn)

        form.addRow("Network Interface:", ip_layout)

        help_ip = QLabel("Shows all available connections (WiFi, Ethernet, VPN). Use 0.0.0.0 for all interfaces.")
        help_ip.setStyleSheet(f"color: {COLORS['text_disabled']}; font-size: 10px;")
        help_ip.setWordWrap(True)
        form.addRow("", help_ip)

        # Port
        self._port_edit = QLineEdit(str(self.enip_server.port))
        self._port_edit.setPlaceholderText("44818")
        form.addRow("Port:", self._port_edit)

        help_port = QLabel("Valid range: 1024-65535 (Default: 44818)")
        help_port.setStyleSheet(f"color: {COLORS['text_disabled']}; font-size: 10px;")
        form.addRow("", help_port)

        layout.addLayout(form)

        # Warning note
        note = QLabel("Changes take effect when the server is restarted")
        note.setStyleSheet(f"color: {COLORS['warning']}; font-size: 11px; font-weight: bold; padding: 8px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        layout.addStretch()

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setProperty("class", "success")
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate_interfaces(self):
        """Populate the IP address dropdown with available network interfaces"""
        current_ip = self._address_combo.currentText() if hasattr(self, '_address_combo') else self.enip_server.address

        self._address_combo.clear()

        interfaces = self.network_service.get_available_interfaces()

        for iface in interfaces:
            ip = iface['ip']
            name = iface['name']
            display_text = f"{ip} - {name}"
            self._address_combo.addItem(display_text, ip)

        # Try to select the current IP
        for i in range(self._address_combo.count()):
            if self._address_combo.itemData(i) == current_ip:
                self._address_combo.setCurrentIndex(i)
                break
        else:
            # If current IP not found, set it as custom text
            self._address_combo.setCurrentText(current_ip)

    def _on_save(self):
        """Save configuration"""
        # Get IP from combo box (either selected item data or custom text)
        current_data = self._address_combo.currentData()
        if current_data:
            address = current_data
        else:
            address = self._address_combo.currentText().strip()

        port_str = self._port_edit.text().strip()

        try:
            port = int(port_str)
        except ValueError:
            QMessageBox.warning(self, "Invalid Port", "Port must be a valid number")
            return

        # Pre-validate IP is available (if not 0.0.0.0)
        if address != "0.0.0.0":
            is_valid, error_msg = self.network_service.validate_ip_available(address)
            if not is_valid:
                QMessageBox.warning(
                    self, "Invalid IP Address",
                    f"{error_msg}\n\nPlease select an available interface or use 0.0.0.0 to bind to all interfaces."
                )
                return

        success, message = self.config_service.set_server_config(address, port)

        if success:
            self.enip_server.address = address
            self.enip_server.port = port
            self.accept()
        else:
            QMessageBox.warning(self, "Validation Error", message)
