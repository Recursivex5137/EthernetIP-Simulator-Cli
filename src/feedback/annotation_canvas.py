"""Canvas for annotating screenshots"""

import math
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox,
    QLabel, QSlider
)
from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QPainter, QPixmap, QPen, QColor, QImage
import logging


class AnnotationCanvas(QWidget):
    """Canvas for drawing annotations on screenshots"""

    def __init__(self, screenshot: QPixmap, parent=None):
        super().__init__(parent)

        self.logger = logging.getLogger(__name__)

        # Store the screenshot QPixmap directly
        self._screenshot = screenshot

        # Overlay for committed annotations
        self._overlay = QPixmap(self._screenshot.size())
        self._overlay.fill(Qt.transparent)

        self._tool = "rectangle"
        self._color = QColor("red")
        self._line_width = 3

        self._start_pos = None
        self._current_pos = None
        self._drawing = False
        self._pen_points = []

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)

        tools = [("Rectangle", "rectangle"), ("Arrow", "arrow"), ("Circle", "circle"), ("Pen", "pen")]
        self._tool_buttons = {}
        for label, tool in tools:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(tool == "rectangle")
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda checked, t=tool: self._set_tool(t))
            toolbar.addWidget(btn)
            self._tool_buttons[tool] = btn

        toolbar.addWidget(QLabel("Color:"))
        self._color_combo = QComboBox()
        self._color_combo.addItems(["red", "blue", "green", "yellow", "black", "white"])
        self._color_combo.currentTextChanged.connect(self._set_color)
        self._color_combo.setFixedWidth(80)
        toolbar.addWidget(self._color_combo)

        toolbar.addWidget(QLabel("Width:"))
        self._width_slider = QSlider(Qt.Horizontal)
        self._width_slider.setRange(1, 10)
        self._width_slider.setValue(3)
        self._width_slider.setFixedWidth(80)
        self._width_slider.valueChanged.connect(self._set_width)
        toolbar.addWidget(self._width_slider)

        clear_btn = QPushButton("Clear All")
        clear_btn.setProperty("class", "danger")
        clear_btn.setFixedHeight(28)
        clear_btn.clicked.connect(self.clear_annotations)
        toolbar.addWidget(clear_btn)

        toolbar.addStretch()

        layout.addLayout(toolbar)

        # Canvas area
        self._canvas = _DrawingArea(self)
        layout.addWidget(self._canvas, stretch=1)

    def _set_tool(self, tool):
        self._tool = tool
        for t, btn in self._tool_buttons.items():
            btn.setChecked(t == tool)

    def _set_color(self, color_name):
        self._color = QColor(color_name)

    def _set_width(self, width):
        self._line_width = width

    def clear_annotations(self):
        self._overlay = QPixmap(self._screenshot.size())
        self._overlay.fill(Qt.transparent)
        self._canvas.update()
        self.logger.info("Annotations cleared")

    def get_annotated_image(self) -> QPixmap:
        """Get final image with annotations as QPixmap"""
        result = QPixmap(self._screenshot.size())
        painter = QPainter(result)
        painter.drawPixmap(0, 0, self._screenshot)
        painter.drawPixmap(0, 0, self._overlay)
        painter.end()
        return result


class _DrawingArea(QWidget):
    """Internal widget that handles painting and mouse events"""

    def __init__(self, parent_canvas: AnnotationCanvas):
        super().__init__(parent_canvas)
        self._canvas = parent_canvas
        self.setMouseTracking(True)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Scale screenshot to fit widget
        widget_size = self.size()
        scaled = self._canvas._screenshot.scaled(
            widget_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self._scale_x = scaled.width() / self._canvas._screenshot.width() if self._canvas._screenshot.width() > 0 else 1
        self._scale_y = scaled.height() / self._canvas._screenshot.height() if self._canvas._screenshot.height() > 0 else 1

        # Draw screenshot
        offset_x = (widget_size.width() - scaled.width()) // 2
        offset_y = (widget_size.height() - scaled.height()) // 2
        self._offset = QPoint(offset_x, offset_y)

        painter.drawPixmap(self._offset, scaled)

        # Draw overlay
        scaled_overlay = self._canvas._overlay.scaled(
            scaled.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        painter.drawPixmap(self._offset, scaled_overlay)

        # Draw in-progress shape
        if self._canvas._drawing and self._canvas._start_pos and self._canvas._current_pos:
            pen = QPen(self._canvas._color, self._canvas._line_width)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)

            s = self._canvas._start_pos
            c = self._canvas._current_pos

            if self._canvas._tool == "rectangle":
                painter.drawRect(QRect(s, c))
            elif self._canvas._tool == "circle":
                painter.drawEllipse(QRect(s, c))
            elif self._canvas._tool == "arrow":
                painter.drawLine(s, c)

        painter.end()

    def _widget_to_image(self, pos):
        """Convert widget coordinates to image coordinates"""
        x = int((pos.x() - self._offset.x()) / self._scale_x) if hasattr(self, '_scale_x') else pos.x()
        y = int((pos.y() - self._offset.y()) / self._scale_y) if hasattr(self, '_scale_y') else pos.y()
        return QPoint(x, y)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._canvas._start_pos = event.position().toPoint()
            self._canvas._current_pos = event.position().toPoint()
            self._canvas._drawing = True
            self._canvas._pen_points = [event.position().toPoint()]

    def mouseMoveEvent(self, event):
        if self._canvas._drawing:
            self._canvas._current_pos = event.position().toPoint()

            if self._canvas._tool == "pen":
                self._canvas._pen_points.append(event.position().toPoint())
                # Commit pen strokes immediately to overlay
                if len(self._canvas._pen_points) >= 2:
                    p1 = self._widget_to_image(self._canvas._pen_points[-2])
                    p2 = self._widget_to_image(self._canvas._pen_points[-1])
                    painter = QPainter(self._canvas._overlay)
                    painter.setRenderHint(QPainter.Antialiasing)
                    pen = QPen(self._canvas._color, self._canvas._line_width)
                    pen.setCapStyle(Qt.RoundCap)
                    painter.setPen(pen)
                    painter.drawLine(p1, p2)
                    painter.end()

            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._canvas._drawing:
            self._canvas._drawing = False

            if self._canvas._tool == "pen":
                self._canvas._pen_points = []
                self.update()
                return

            # Commit shape to overlay
            s = self._widget_to_image(self._canvas._start_pos)
            e = self._widget_to_image(event.position().toPoint())

            painter = QPainter(self._canvas._overlay)
            painter.setRenderHint(QPainter.Antialiasing)
            pen = QPen(self._canvas._color, self._canvas._line_width)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)

            if self._canvas._tool == "rectangle":
                painter.drawRect(QRect(s, e))
            elif self._canvas._tool == "circle":
                painter.drawEllipse(QRect(s, e))
            elif self._canvas._tool == "arrow":
                painter.drawLine(s, e)
                # Draw arrowhead
                angle = math.atan2(e.y() - s.y(), e.x() - s.x())
                arrow_length = 15
                arrow_angle = math.pi / 6
                p1x = int(e.x() - arrow_length * math.cos(angle - arrow_angle))
                p1y = int(e.y() - arrow_length * math.sin(angle - arrow_angle))
                p2x = int(e.x() - arrow_length * math.cos(angle + arrow_angle))
                p2y = int(e.y() - arrow_length * math.sin(angle + arrow_angle))
                painter.drawLine(e, QPoint(p1x, p1y))
                painter.drawLine(e, QPoint(p2x, p2y))

            painter.end()
            self._canvas._start_pos = None
            self._canvas._current_pos = None
            self.update()
