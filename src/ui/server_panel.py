"""EthernetIP server control panel UI"""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QGridLayout, QLabel,
    QPushButton, QTextBrowser, QMessageBox
)
from PySide6.QtCore import Signal, QTimer, Qt
from .theme import COLORS


class ServerPanel(QWidget):
    """Panel for EthernetIP server control"""

    server_started = Signal()
    server_stopped = Signal()

    def __init__(self, enip_server, config_service, main_window=None, parent=None):
        super().__init__(parent)
        self.enip_server = enip_server
        self.config_service = config_service
        self.main_window = main_window
        self._startup_timer = None
        self._startup_poll_count = 0
        self._restarting = False
        self.logger = logging.getLogger(__name__)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # Header
        header = QLabel("Server Control")
        header.setStyleSheet("font-size: 16px; font-weight: bold; padding: 4px;")
        layout.addWidget(header)

        # Status group
        status_group = QGroupBox("Status")
        status_layout = QGridLayout(status_group)
        status_layout.addWidget(QLabel("Status:"), 0, 0)

        # Status label with indicator
        status_container = QWidget()
        status_container_layout = QGridLayout(status_container)
        status_container_layout.setContentsMargins(0, 0, 0, 0)
        status_container_layout.setSpacing(6)

        self._status_indicator = QLabel("●")
        self._status_indicator.setStyleSheet(f"color: {COLORS['danger']}; font-size: 16px;")
        status_container_layout.addWidget(self._status_indicator, 0, 0)

        self._status_label = QLabel("Stopped")
        self._status_label.setStyleSheet(f"color: {COLORS['danger']}; font-weight: bold; font-size: 14px;")
        self._status_label.setToolTip("Server status")
        status_container_layout.addWidget(self._status_label, 0, 1)

        status_layout.addWidget(status_container, 0, 1)
        layout.addWidget(status_group)

        # Connection info group
        info_group = QGroupBox("Connection Info")
        info_layout = QGridLayout(info_group)

        info_layout.addWidget(QLabel("IP Address:"), 0, 0)
        self._ip_label = QLabel(self.enip_server.address)
        self._ip_label.setStyleSheet("font-weight: bold;")
        self._ip_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._ip_label.setToolTip("Network interface to bind to - Click Settings to change")
        info_layout.addWidget(self._ip_label, 0, 1)

        info_layout.addWidget(QLabel("Port:"), 1, 0)
        self._port_label = QLabel(str(self.enip_server.port))
        self._port_label.setStyleSheet("font-weight: bold;")
        self._port_label.setToolTip("EthernetIP server port")
        info_layout.addWidget(self._port_label, 1, 1)

        info_layout.addWidget(QLabel("Slot:"), 2, 0)
        slot_label = QLabel("0")
        slot_label.setStyleSheet("font-weight: bold;")
        info_layout.addWidget(slot_label, 2, 1)

        layout.addWidget(info_group)

        # Control buttons
        self._start_btn = QPushButton("Start Server")
        self._start_btn.setProperty("class", "success")
        self._start_btn.setMinimumHeight(36)
        self._start_btn.setToolTip("Start the EthernetIP server (binds to configured IP:Port) - F5")
        self._start_btn.clicked.connect(self.on_start)
        layout.addWidget(self._start_btn)

        self._stop_btn = QPushButton("Stop Server")
        self._stop_btn.setProperty("class", "danger")
        self._stop_btn.setMinimumHeight(36)
        self._stop_btn.setEnabled(False)
        self._stop_btn.setToolTip("Stop the server and release network port - F6")
        self._stop_btn.clicked.connect(self.on_stop)
        layout.addWidget(self._stop_btn)

        self._settings_btn = QPushButton("Settings...")
        self._settings_btn.setMinimumHeight(36)
        self._settings_btn.setToolTip("Configure network interface and port settings - F8")
        self._settings_btn.clicked.connect(self.on_settings)
        layout.addWidget(self._settings_btn)

        # Instructions group
        instructions_group = QGroupBox("Studio 5000 Connection")
        inst_layout = QVBoxLayout(instructions_group)

        self._instructions = QTextBrowser()
        self._instructions.setOpenExternalLinks(False)
        self._update_instructions_text()
        inst_layout.addWidget(self._instructions)

        layout.addWidget(instructions_group, stretch=1)

    def _update_instructions_text(self):
        """Update instruction text with current server info"""
        ip = self.enip_server.address
        port = self.enip_server.port
        self._instructions.setHtml(f"""
        <p style="color: {COLORS['text_secondary']};">
        <b>To connect from Studio 5000:</b><br><br>
        1. Add a new Ethernet Module in your I/O Configuration<br><br>
        2. Set IP Address to: <b style="color: {COLORS['text_primary']};">{ip}</b><br><br>
        3. Set Port to: <b style="color: {COLORS['text_primary']};">{port}</b><br><br>
        4. Set Slot to: <b style="color: {COLORS['text_primary']};">0</b><br><br>
        5. Click OK and Download<br><br>
        6. Your simulator tags will appear in the Controller Tags folder<br><br>
        <i style="color: {COLORS['warning']};">Note: Make sure the simulator server is running before attempting to connect.</i>
        </p>
        """)

    def on_start(self):
        """Start the server"""
        # Pre-validate IP address is available
        if self.enip_server.address != "0.0.0.0":
            from ..services.network_service import NetworkService
            network_service = NetworkService()

            is_valid, error_msg = network_service.validate_ip_available(self.enip_server.address)
            if not is_valid:
                reply = QMessageBox.warning(
                    self, "Invalid Network Configuration",
                    f"{error_msg}\n\nPlease configure a valid IP address in Settings.",
                    QMessageBox.Ok
                )
                self.on_settings()  # Open settings directly
                return

        try:
            self._start_btn.setEnabled(False)
            self._stop_btn.setEnabled(False)
            self._status_label.setText("Starting...")
            self._status_label.setStyleSheet(f"color: {COLORS['warning']}; font-weight: bold; font-size: 14px;")
            self._status_label.setToolTip("Server is starting...")
            self._status_indicator.setStyleSheet(f"color: {COLORS['warning']}; font-size: 16px;")

            self.enip_server.start()

            # Poll until ready (stop old timer first to prevent stacking)
            self._stop_startup_timer()
            self._startup_poll_count = 0
            self._startup_timer = QTimer(self)
            self._startup_timer.timeout.connect(self._check_server_ready)
            self._startup_timer.start(200)

        except Exception as e:
            self._start_btn.setEnabled(True)
            self._status_label.setText("Failed")
            self._status_label.setStyleSheet(f"color: {COLORS['danger']}; font-weight: bold; font-size: 14px;")
            QMessageBox.critical(self, "Error", f"Failed to start server: {e}")

    def _check_server_ready(self):
        """Poll server readiness"""
        self._startup_poll_count += 1

        if self.enip_server.tags_ready:
            self._startup_timer.stop()
            self._startup_poll_count = 0
            self._status_label.setText("Running")
            self._status_label.setStyleSheet(f"color: {COLORS['success']}; font-weight: bold; font-size: 14px;")
            self._status_label.setToolTip("Server running normally")
            self._status_indicator.setStyleSheet(f"color: {COLORS['success']}; font-size: 16px;")
            self._stop_btn.setEnabled(True)
            self.server_started.emit()
        elif not self.enip_server.is_running or self._startup_poll_count > 50:
            # 50 polls * 200ms = 10s timeout
            self._startup_timer.stop()
            self._startup_poll_count = 0
            self._status_label.setText("Failed")
            self._status_label.setStyleSheet(f"color: {COLORS['danger']}; font-weight: bold; font-size: 14px;")
            self._status_indicator.setStyleSheet(f"color: {COLORS['danger']}; font-size: 16px;")
            self._start_btn.setEnabled(True)

            # Get detailed error information
            error_msg, error_code = self.enip_server.get_last_error()
            self._status_label.setToolTip(f"Last error: {error_msg}" if error_msg else "Server failed to start")

            # Map error codes to user-friendly messages
            if error_code == 10049:  # WSAEADDRNOTAVAIL
                user_msg = (
                    f"Cannot bind to {self.enip_server.address}: Address not available on this machine.\n\n"
                    "Please select an available network interface in Settings."
                )
            elif error_code == 10048:  # WSAEADDRINUSE
                user_msg = (
                    f"Port {self.enip_server.port} is already in use.\n\n"
                    "Another application may be using this port."
                )
            elif error_msg:
                user_msg = f"Server failed to start:\n{error_msg}"
            else:
                user_msg = "Server failed to start (timeout)"

            # Show error dialog with Settings button
            self._show_error_dialog(user_msg)

            if self.main_window:
                self.main_window.set_status("Server failed to start")

    def _show_error_dialog(self, message: str):
        """
        Show error dialog with actionable guidance.

        Args:
            message: Error message to display
        """
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle("Server Start Failed")
        msg_box.setText(message)
        msg_box.setInformativeText("Click 'Settings' to configure network settings.")

        settings_btn = msg_box.addButton("Settings", QMessageBox.ActionRole)
        msg_box.addButton(QMessageBox.Close)

        msg_box.exec()

        # If user clicked Settings, open the config dialog
        if msg_box.clickedButton() == settings_btn:
            self.on_settings()

    def on_stop(self):
        """Stop the server"""
        try:
            self.enip_server.snapshot_live_values()
            self.enip_server.stop()
            self._status_label.setText("Stopped")
            self._status_label.setStyleSheet(f"color: {COLORS['danger']}; font-weight: bold; font-size: 14px;")
            self._status_label.setToolTip("Server stopped")
            self._status_indicator.setStyleSheet(f"color: {COLORS['danger']}; font-size: 16px;")
            self._start_btn.setEnabled(True)
            self._stop_btn.setEnabled(False)
            self.server_stopped.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to stop server: {e}")

    def _stop_startup_timer(self):
        """Stop any existing startup poll timer to prevent stacking."""
        if self._startup_timer is not None:
            self._startup_timer.stop()
            self._startup_timer.deleteLater()
            self._startup_timer = None

    def request_restart(self):
        """Restart the server to pick up tag list changes.

        Only restarts if the server is currently running.
        Guards against concurrent restart calls.
        """
        if not self.enip_server.is_running or self._restarting:
            return

        self._restarting = True
        self._stop_startup_timer()
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(False)
        self._status_label.setText("Restarting...")
        self._status_label.setStyleSheet(
            f"color: {COLORS['warning']}; font-weight: bold; font-size: 14px;"
        )

        # Snapshot live values and stop
        self.enip_server.snapshot_live_values()
        self.enip_server.stop()

        # Wait longer for socket cleanup (3 seconds instead of 1.5)
        # Use exponential backoff retry instead of single attempt
        QTimer.singleShot(3000, lambda: self._complete_restart(attempt=1, max_attempts=3))

    def _complete_restart(self, attempt=1, max_attempts=3):
        """Complete the restart after delay, with exponential backoff retry"""
        try:
            # Verify old thread is actually dead
            if (self.enip_server.server_thread is not None
                    and self.enip_server.server_thread.is_alive()):
                if attempt < max_attempts:
                    retry_delay = 1500 * attempt  # 1.5s, 3s, 4.5s...
                    self.logger.warning(f"Old thread still alive, retry {attempt + 1}/{max_attempts} in {retry_delay}ms")
                    QTimer.singleShot(retry_delay, lambda: self._complete_restart(attempt + 1, max_attempts))
                    return
                else:
                    self._restart_failed("Old server thread did not exit")
                    return

            # Try to start the server
            self.enip_server.start()

            # Start polling for readiness
            self._stop_startup_timer()
            self._startup_poll_count = 0
            self._startup_timer = QTimer(self)
            self._startup_timer.timeout.connect(self._check_restart_ready)
            self._startup_timer.start(300)

        except OSError as e:
            # Port still in use - retry with exponential backoff
            if "still in use" in str(e) and attempt < max_attempts:
                retry_delay = 2000 * attempt  # 2s, 4s, 6s...
                self.logger.warning(f"Port still in use, retry {attempt + 1}/{max_attempts} in {retry_delay}ms")
                self._status_label.setText(f"Retrying... ({attempt}/{max_attempts})")
                QTimer.singleShot(retry_delay, lambda: self._complete_restart(attempt + 1, max_attempts))
            else:
                # Final failure or non-port error
                self.logger.error(f"Restart failed after {attempt} attempts: {e}")
                self._restart_failed(
                    f"Could not restart server after {attempt} attempts.\n\n"
                    f"Error: {str(e)}\n\n"
                    "Please wait 10 seconds and try again, or restart the application."
                )
        except Exception as e:
            self.logger.error(f"Unexpected restart error: {e}", exc_info=True)
            self._restart_failed(f"Unexpected error during restart: {str(e)}")

    def _check_restart_ready(self):
        """Poll server readiness during restart (with retry on port failure)."""
        self._startup_poll_count += 1

        if self.enip_server.tags_ready:
            self._stop_startup_timer()
            self._startup_poll_count = 0
            self._restarting = False
            self._status_label.setText("Running")
            self._status_label.setStyleSheet(
                f"color: {COLORS['success']}; font-weight: bold; font-size: 14px;"
            )
            self._stop_btn.setEnabled(True)
            self.server_started.emit()
        elif not self.enip_server.is_running or self._startup_poll_count > 20:
            # Server thread died (likely port conflict) or 6s timeout
            self._stop_startup_timer()
            self._startup_poll_count = 0
            self._restart_failed("Server failed to start (port may still be in use)")

    def _restart_failed(self, reason):
        """Handle restart failure - reset UI state."""
        self._restarting = False
        self._status_label.setText("Restart Failed")
        self._status_label.setStyleSheet(
            f"color: {COLORS['danger']}; font-weight: bold; font-size: 14px;"
        )
        self._start_btn.setEnabled(True)
        if self.main_window:
            self.main_window.set_status(reason)

    def on_settings(self):
        """Open server configuration dialog"""
        if self.enip_server.is_running:
            QMessageBox.warning(
                self, "Server Running",
                "Stop the server before changing settings."
            )
            return

        from .dialogs.server_config_dialog import ServerConfigDialog
        dialog = ServerConfigDialog(self.config_service, self.enip_server, self)
        if dialog.exec():
            self._refresh_display()

    def _refresh_display(self):
        """Refresh display with current configuration (no widget destruction)"""
        self._ip_label.setText(self.enip_server.address)
        self._port_label.setText(str(self.enip_server.port))
        self._update_instructions_text()
