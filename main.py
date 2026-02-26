"""
EthernetIP Virtual PLC Simulator
Main entry point with automatic dependency installation
"""

import sys
import subprocess
import importlib.util


REQUIRED_PACKAGES = {
    'cpppo': 'cpppo>=4.0.0',
    'PySide6': 'PySide6>=6.6.0',
}


def check_package_installed(package_name):
    """Check if a package is installed"""
    spec = importlib.util.find_spec(package_name)
    return spec is not None


def check_and_install_dependencies():
    """Auto-install missing packages on first run"""
    missing = []

    for module_name, package_spec in REQUIRED_PACKAGES.items():
        if not check_package_installed(module_name):
            missing.append(package_spec)

    if missing:
        try:
            subprocess.check_call(
                [sys.executable, '-m', 'pip', 'install'] + missing
            )
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to install dependencies: {e}")
            print(f"Please try: pip install {' '.join(missing)}")
            input("\nPress Enter to exit...")
            sys.exit(1)


def main():
    """Main application entry point"""
    check_and_install_dependencies()

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

    except ImportError as e:
        print(f"ERROR: Import Error - {e}")
        print("Please try running: pip install -r requirements.txt")
        input("\nPress Enter to exit...")
        sys.exit(1)

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
        sys.exit(1)


if __name__ == '__main__':
    main()
