"""Application theme constants and QSS stylesheet for dark industrial theme"""

COLORS = {
    'bg_primary': '#1e1e2e',
    'bg_secondary': '#2d2d3f',
    'bg_tertiary': '#383850',
    'bg_input': '#323248',
    'accent': '#4a86c8',
    'accent_hover': '#5a96d8',
    'accent_pressed': '#3a76b8',
    'success': '#4caf50',
    'success_hover': '#5cbf60',
    'danger': '#e74c3c',
    'danger_hover': '#f75c4c',
    'warning': '#f39c12',
    'text_primary': '#e0e0e0',
    'text_secondary': '#a0a0b0',
    'text_disabled': '#606070',
    'border': '#404060',
    'border_focus': '#4a86c8',
    'bool_on_bg': '#1a3a1a',
    'bool_on_fg': '#4caf50',
    'bool_off_bg': '#3a1a1a',
    'bool_off_fg': '#888888',
    'table_row_alt': '#252540',
    'selection': '#3a5a8a',
    'scrollbar': '#505070',
    'scrollbar_hover': '#606080',
}

DARK_STYLESHEET = """
QMainWindow {{
    background-color: {bg_primary};
}}
QWidget {{
    color: {text_primary};
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 12px;
}}
QMenuBar {{
    background-color: {bg_secondary};
    border-bottom: 1px solid {border};
    padding: 2px;
}}
QMenuBar::item {{
    padding: 4px 10px;
    border-radius: 3px;
}}
QMenuBar::item:selected {{
    background-color: {accent};
}}
QMenu {{
    background-color: {bg_secondary};
    border: 1px solid {border};
    padding: 4px;
}}
QMenu::item {{
    padding: 5px 30px 5px 20px;
    border-radius: 3px;
}}
QMenu::item:selected {{
    background-color: {accent};
}}
QMenu::separator {{
    height: 1px;
    background-color: {border};
    margin: 4px 8px;
}}
QStatusBar {{
    background-color: {bg_secondary};
    border-top: 1px solid {border};
    font-size: 11px;
    padding: 2px 8px;
}}
QTreeView, QTableView {{
    background-color: {bg_tertiary};
    alternate-background-color: {table_row_alt};
    border: 1px solid {border};
    border-radius: 4px;
    gridline-color: {border};
    font-size: 13px;
    outline: none;
}}
QTreeView::item, QTableView::item {{
    padding: 4px 6px;
    min-height: 24px;
}}
QTreeView::item:selected, QTableView::item:selected {{
    background-color: {selection};
}}
QTreeView::item:hover, QTableView::item:hover {{
    background-color: {bg_input};
}}
QTreeView::branch {{
    background-color: transparent;
}}
QTreeView::branch:has-children:!has-siblings:closed,
QTreeView::branch:closed:has-children:has-siblings {{
    image: none;
    border-image: none;
}}
QTreeView::branch:open:has-children:!has-siblings,
QTreeView::branch:open:has-children:has-siblings {{
    image: none;
    border-image: none;
}}
QHeaderView::section {{
    background-color: {bg_secondary};
    color: {text_primary};
    border: none;
    border-right: 1px solid {border};
    border-bottom: 1px solid {border};
    padding: 6px 8px;
    font-weight: bold;
    font-size: 12px;
}}
QPushButton {{
    background-color: {accent};
    color: {text_primary};
    border: none;
    border-radius: 4px;
    padding: 7px 18px;
    font-weight: bold;
    font-size: 12px;
    min-height: 28px;
}}
QPushButton:hover {{
    background-color: {accent_hover};
}}
QPushButton:pressed {{
    background-color: {accent_pressed};
}}
QPushButton:disabled {{
    background-color: {bg_tertiary};
    color: {text_disabled};
}}
QPushButton[class="success"] {{
    background-color: {success};
}}
QPushButton[class="success"]:hover {{
    background-color: {success_hover};
}}
QPushButton[class="danger"] {{
    background-color: {danger};
}}
QPushButton[class="danger"]:hover {{
    background-color: {danger_hover};
}}
QLineEdit, QSpinBox {{
    background-color: {bg_input};
    color: {text_primary};
    border: 1px solid {border};
    border-radius: 4px;
    padding: 5px 8px;
    font-size: 12px;
    min-height: 24px;
    selection-background-color: {selection};
}}
QLineEdit:focus, QSpinBox:focus {{
    border: 1px solid {border_focus};
}}
QLineEdit:disabled {{
    color: {text_disabled};
    background-color: {bg_tertiary};
}}
QTextEdit, QPlainTextEdit {{
    background-color: {bg_input};
    color: {text_primary};
    border: 1px solid {border};
    border-radius: 4px;
    padding: 5px 8px;
    font-size: 12px;
    selection-background-color: {selection};
}}
QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {border_focus};
}}
QTextBrowser {{
    background-color: {bg_input};
    color: {text_secondary};
    border: 1px solid {border};
    border-radius: 4px;
    padding: 8px;
    font-size: 12px;
}}
QComboBox {{
    background-color: {bg_input};
    color: {text_primary};
    border: 1px solid {border};
    border-radius: 4px;
    padding: 5px 8px;
    font-size: 12px;
    min-height: 24px;
}}
QComboBox:hover {{
    border: 1px solid {border_focus};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: {bg_secondary};
    color: {text_primary};
    border: 1px solid {border};
    selection-background-color: {accent};
    outline: none;
}}
QCheckBox {{
    spacing: 8px;
    font-size: 12px;
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {border};
    border-radius: 3px;
    background-color: {bg_input};
}}
QCheckBox::indicator:checked {{
    background-color: {accent};
    border-color: {accent};
}}
QGroupBox {{
    border: 1px solid {border};
    border-radius: 6px;
    margin-top: 12px;
    padding: 12px 8px 8px 8px;
    font-weight: bold;
    font-size: 12px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {text_primary};
}}
QSplitter::handle {{
    background-color: {border};
    width: 2px;
}}
QSplitter::handle:hover {{
    background-color: {accent};
}}
QScrollBar:vertical {{
    background-color: {bg_primary};
    width: 10px;
    border: none;
    border-radius: 5px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background-color: {scrollbar};
    min-height: 30px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: {scrollbar_hover};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar:horizontal {{
    background-color: {bg_primary};
    height: 10px;
    border: none;
    border-radius: 5px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background-color: {scrollbar};
    min-width: 30px;
    border-radius: 5px;
}}
QScrollBar::handle:horizontal:hover {{
    background-color: {scrollbar_hover};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}
QDialog {{
    background-color: {bg_primary};
}}
QLabel {{
    background-color: transparent;
}}
QSlider::groove:horizontal {{
    border: 1px solid {border};
    height: 6px;
    background: {bg_tertiary};
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {accent};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QToolBar {{
    background-color: {bg_secondary};
    border: none;
    padding: 2px;
    spacing: 4px;
}}
QToolButton {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 3px;
    padding: 4px 8px;
    font-size: 11px;
}}
QToolButton:hover {{
    background-color: {bg_tertiary};
    border-color: {border};
}}
QToolButton:checked {{
    background-color: {accent};
    border-color: {accent};
}}
QDialogButtonBox QPushButton {{
    min-width: 80px;
}}
QTabWidget::pane {{
    border: 1px solid {border};
    background-color: {bg_primary};
    border-radius: 4px;
    top: -1px;
}}
QTabBar::tab {{
    background-color: {bg_secondary};
    color: {text_secondary};
    border: 1px solid {border};
    border-bottom: none;
    padding: 8px 20px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}}
QTabBar::tab:selected {{
    background-color: {bg_primary};
    color: {text_primary};
    font-weight: bold;
    border-bottom: 1px solid {bg_primary};
}}
QTabBar::tab:hover:!selected {{
    background-color: {bg_tertiary};
}}
QTabBar::tab:first {{
    margin-left: 4px;
}}
""".format(**COLORS)
