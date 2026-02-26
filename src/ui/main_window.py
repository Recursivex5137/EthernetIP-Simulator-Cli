"""Main application window"""

import atexit
import logging
from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QStatusBar, QMessageBox,
    QTabWidget, QWidget, QHBoxLayout
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QShortcut, QKeySequence
from .tag_panel import TagManagementPanel
from .server_panel import ServerPanel
from .log_viewer_panel import LogViewerPanel
from .log_handler import QtLogHandler


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()

        # Initialize custom log handler FIRST
        self.log_handler = QtLogHandler()
        self.log_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )

        # Configure logging: console errors-only, Qt Log Viewer gets INFO+
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.ERROR)
        console_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        self.log_handler.setLevel(logging.INFO)

        logging.basicConfig(
            level=logging.INFO,
            handlers=[console_handler, self.log_handler]
        )
        self.logger = logging.getLogger(__name__)

        self.setWindowTitle("EthernetIP Virtual PLC Simulator")
        self.resize(1400, 800)

        self._init_services()
        self._validate_startup_ip()
        self._create_menu_bar()
        self._create_central_widget()
        self._create_status_bar()
        self._init_feedback_shortcut()
        self._init_undo_shortcuts()
        self._init_tab_shortcuts()

        self.logger.info("Application initialized successfully")

    def _init_services(self):
        """Initialize all services and dependencies"""
        from ..database.db_manager import DBManager
        from ..database.tag_repository import TagRepository
        from ..database.udt_repository import UDTRepository
        from ..database.config_repository import ConfigRepository
        from ..services.tag_service import TagService
        from ..services.udt_service import UDTService
        from ..services.config_service import ConfigService
        from ..server.enip_server import EthernetIPServer
        from ..server.tag_provider import TagProvider

        self.db_manager = DBManager('data/tags.db')
        self.tag_repository = TagRepository(self.db_manager)
        self.udt_repository = UDTRepository(self.db_manager)

        self.config_repository = ConfigRepository(self.db_manager)
        self.config_service = ConfigService(self.config_repository)

        self.tag_service = TagService(self.tag_repository)
        self.udt_service = UDTService(self.udt_repository)

        server_address = self.config_service.get_server_address()
        server_port = self.config_service.get_server_port()

        self.tag_provider = TagProvider(self.tag_service, self.udt_service)
        self.enip_server = EthernetIPServer(
            self.tag_provider,
            address=server_address,
            port=server_port,
            udt_service=self.udt_service,
        )

        # Ensure server socket is released even on abnormal exit (terminal close, etc.)
        atexit.register(self._atexit_cleanup)

        self.logger.info(f"Services initialized (Server: {server_address}:{server_port})")

    def _validate_startup_ip(self):
        """Validate saved IP and auto-switch to valid interface if necessary"""
        from ..services.network_service import NetworkService

        saved_ip = self.enip_server.address

        # 0.0.0.0 is always valid
        if saved_ip == "0.0.0.0":
            return

        network_service = NetworkService()
        is_valid, error_msg = network_service.validate_ip_available(saved_ip)

        if not is_valid:
            # Get a valid primary interface
            primary_ip = network_service.get_primary_interface()

            if primary_ip and primary_ip != saved_ip:
                self.logger.warning(f"Saved IP {saved_ip} not available, switching to {primary_ip}")

                # Update configuration
                success, _ = self.config_service.set_server_config(
                    primary_ip,
                    self.config_service.get_server_port()
                )

                if success:
                    self.enip_server.address = primary_ip

                    # Show info dialog to user
                    QMessageBox.information(
                        self, "Network Configuration Updated",
                        f"The previously configured IP ({saved_ip}) is no longer available.\n\n"
                        f"Automatically switched to: {primary_ip}\n\n"
                        f"You can change this in Settings (F8)."
                    )
            else:
                # No valid interface found, show warning
                self.logger.error(f"No valid network interface found. Saved IP {saved_ip} is not available.")
                QMessageBox.warning(
                    self, "Network Configuration Issue",
                    f"The configured IP address ({saved_ip}) is not available,\n"
                    f"and no alternative network interfaces were detected.\n\n"
                    f"Please configure the network settings before starting the server (F8)."
                )

    def _create_menu_bar(self):
        """Create menu bar"""
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("&File")
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Server menu
        server_menu = menu_bar.addMenu("&Server")
        self._start_action = QAction("&Start Server", self)
        self._start_action.setShortcut(QKeySequence("F5"))
        self._start_action.triggered.connect(lambda: self.server_panel.on_start())
        server_menu.addAction(self._start_action)

        self._stop_action = QAction("S&top Server", self)
        self._stop_action.setShortcut(QKeySequence("F6"))
        self._stop_action.setEnabled(False)
        self._stop_action.triggered.connect(lambda: self.server_panel.on_stop())
        server_menu.addAction(self._stop_action)

        server_menu.addSeparator()

        settings_action = QAction("Se&ttings...", self)
        settings_action.setShortcut(QKeySequence("F8"))
        settings_action.triggered.connect(lambda: self.server_panel.on_settings())
        server_menu.addAction(settings_action)

        # Help menu
        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _create_central_widget(self):
        """Create main layout with tabs"""
        # Create tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(False)
        self.tab_widget.setTabPosition(QTabWidget.North)

        # Tab 1: Simulator (existing layout)
        simulator_tab = QWidget()
        simulator_layout = QHBoxLayout(simulator_tab)
        simulator_layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)

        self.tag_panel = TagManagementPanel(self.tag_service, self.udt_service, self.enip_server, self)
        self.server_panel = ServerPanel(self.enip_server, self.config_service, self)

        # Connect server panel signals to menu state
        self.server_panel.server_started.connect(self._on_server_started)
        self.server_panel.server_stopped.connect(self._on_server_stopped)

        splitter.addWidget(self.tag_panel)
        splitter.addWidget(self.server_panel)
        splitter.setSizes([980, 420])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)

        simulator_layout.addWidget(splitter)

        # Tab 2: Log Viewer
        self.log_viewer = LogViewerPanel(self.log_handler, self)

        # Add tabs
        self.tab_widget.addTab(simulator_tab, "Simulator")
        self.tab_widget.addTab(self.log_viewer, "Logs")

        # Set default tab to Simulator
        self.tab_widget.setCurrentIndex(0)

        self.setCentralWidget(self.tab_widget)

    def _create_status_bar(self):
        """Create status bar"""
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready - Press F12 for feedback/screenshot")

    def _init_feedback_shortcut(self):
        """Set up F12 hotkey for feedback"""
        from ..database.feedback_repository import FeedbackRepository
        from ..feedback.feedback_service import FeedbackService

        self.feedback_repository = FeedbackRepository(self.db_manager)
        self.feedback_service = FeedbackService(self.feedback_repository)

        shortcut = QShortcut(QKeySequence("F12"), self)
        shortcut.activated.connect(self._open_feedback_dialog)

        self.logger.info("Feedback system initialized (Press F12 to submit feedback)")

    def _init_undo_shortcuts(self):
        """Set up Ctrl+Z / Ctrl+Y for tag value undo/redo, Ctrl+E for edit, Ctrl+U for UDTs"""
        undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        undo_shortcut.activated.connect(lambda: self.tag_panel.perform_undo())

        redo_shortcut = QShortcut(QKeySequence("Ctrl+Y"), self)
        redo_shortcut.activated.connect(lambda: self.tag_panel.perform_redo())

        edit_shortcut = QShortcut(QKeySequence("Ctrl+E"), self)
        edit_shortcut.activated.connect(lambda: self.tag_panel._on_edit_tag())

        udt_shortcut = QShortcut(QKeySequence("Ctrl+U"), self)
        udt_shortcut.activated.connect(lambda: self.tag_panel._on_manage_udts())

    def _init_tab_shortcuts(self):
        """Set up Ctrl+1/2 for tab switching"""
        tab1_shortcut = QShortcut(QKeySequence("Ctrl+1"), self)
        tab1_shortcut.activated.connect(lambda: self.tab_widget.setCurrentIndex(0))

        tab2_shortcut = QShortcut(QKeySequence("Ctrl+2"), self)
        tab2_shortcut.activated.connect(lambda: self.tab_widget.setCurrentIndex(1))

    def _open_feedback_dialog(self):
        """Open feedback dialog with screenshot"""
        try:
            from ..feedback.screenshot_manager import ScreenshotManager
            from ..feedback.feedback_dialog import FeedbackDialog

            self.logger.info("F12 pressed - Opening feedback dialog")

            screenshot_manager = ScreenshotManager()
            screenshot, filepath = screenshot_manager.capture_window(self)

            self.logger.info(f"Screenshot captured: {filepath}")

            dialog = FeedbackDialog(filepath, self.feedback_service, self)
            dialog.exec()

        except Exception as e:
            self.logger.error(f"Failed to open feedback dialog: {e}", exc_info=True)
            QMessageBox.critical(
                self, "Feedback Error",
                f"Failed to open feedback dialog:\n{str(e)}"
            )

    def request_server_restart(self):
        """Request server restart after tag list changes."""
        if hasattr(self, 'server_panel'):
            self.server_panel.request_restart()

    def set_status(self, message: str, timeout_ms: int = 5000):
        """Update status bar message"""
        if hasattr(self, '_status_bar') and self._status_bar:
            self._status_bar.showMessage(message, timeout_ms)
        self.logger.debug("Status: %s", message)

    def _on_server_started(self):
        """Update menu and disable tag editing when server starts"""
        self._start_action.setEnabled(False)
        self._stop_action.setEnabled(True)
        self.tag_panel.set_tag_editing_enabled(False)
        self.set_status("Server running")

    def _on_server_stopped(self):
        """Update menu and re-enable tag editing when server stops"""
        self._start_action.setEnabled(True)
        self._stop_action.setEnabled(False)
        self.tag_panel.set_tag_editing_enabled(True)
        self.set_status("Server stopped")

    def _show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self, "About",
            "EthernetIP Virtual PLC Simulator\n\n"
            "Emulates an EthernetIP/CIP protocol server for\n"
            "testing with Studio 5000, RSLogix, and SCADA systems.\n\n"
            "Built with PySide6 (Qt6) and cpppo."
        )

    def _atexit_cleanup(self):
        """Last-resort cleanup registered via atexit.

        Ensures the server socket is released even when closeEvent does not
        fire (e.g. terminal closed, sys.exit called directly).
        """
        try:
            if hasattr(self, 'enip_server') and self.enip_server.is_running:
                self.enip_server.stop()
        except Exception:
            pass

    def closeEvent(self, event):
        """Proper cleanup on close"""
        self.logger.info("Application closing")

        # Stop refresh timer
        if hasattr(self, 'tag_panel'):
            self.tag_panel.stop_refresh()

        # Stop server
        if hasattr(self, 'enip_server') and self.enip_server.is_running:
            self.logger.info("Stopping server...")
            self.enip_server.stop()

        # Close database
        if hasattr(self, 'db_manager') and self.db_manager:
            self.db_manager.close()

        # Remove Qt log handler from root logger to prevent signals to destroyed widgets
        logging.getLogger().removeHandler(self.log_handler)

        event.accept()
