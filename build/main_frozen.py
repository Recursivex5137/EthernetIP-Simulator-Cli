"""
EthernetIP Virtual PLC Simulator - Frozen Executable Entry Point
Simplified main without dependency checking (all dependencies are bundled)
"""

import sys
import logging


def main():
    """Main application entry point for frozen executable"""
    try:
        from PySide6.QtWidgets import QApplication
        from src.ui.main_window import MainWindow
        from src.ui.theme import DARK_STYLESHEET

        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        app.setStyleSheet(DARK_STYLESHEET)

        window = MainWindow()
        window.show()
        sys.exit(app.exec())

    except Exception as e:
        # Try to show error dialog if possible
        try:
            from PySide6.QtWidgets import QMessageBox
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle("Error")
            msg.setText(f"Application failed to start:\n\n{e}")
            msg.exec()
        except:
            # Fallback to console error if Qt isn't available
            print(f"FATAL ERROR: {e}")
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
