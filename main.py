"""Native Qt dashboard. Run with: python main.py"""
import csv
import math
import sys
import time
from collections import OrderedDict, deque
from pathlib import Path
import shiboken6

from PySide6.QtCore import Qt, QTimer, QPointF, QRectF, QUrl, QStandardPaths
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QFont, QPixmap, QLinearGradient
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkDiskCache
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QFrame,
    QVBoxLayout, QHBoxLayout, QGridLayout, QComboBox, QDoubleSpinBox,
    QFileDialog, QMessageBox, QAbstractSpinBox, QScrollArea,
)

from simulation import Simulation

BG = "#0b1018"
PANEL = "#121b27"
TEXT = "#edf3fa"
MUTED = "#8b9bb0"
CYAN = "#43ddc1"
BLUE = "#7daeff"


def label(text, size=12, color=TEXT, bold=False):
    result = QLabel(text)
    result.setStyleSheet(f"color: {color}; font-size: {size}px; font-weight: {700 if bold else 400};")
    return result


def panel():
    widget = QFrame()
    widget.setObjectName("panel")
    return widget


class Metric(QFrame):
    def __init__(self, title, unit, accent=TEXT):
        super().__init__()
        self.setObjectName("panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 15, 18, 15)
        self.accent = accent
        layout.addWidget(label(title.upper(), 10, MUTED, True))
        row = QHBoxLayout()
        self.value = label("—", 29, accent, True)
        row.addWidget(self.value)
        row.addWidget(label(unit, 12, MUTED), alignment=Qt.AlignmentFlag.AlignBottom)
        row.addStretch()
        layout.addLayout(row)
        notes = {"Depth": "↓  Below surface", "Heading": "↗  True heading / yaw",
                 "Roll": "↔  Lateral attitude", "Pitch": "↕  Longitudinal attitude",
                 "Battery": "▰  Simulated supply"}
        layout.addWidget(label(notes[title], 10, MUTED))


class BrandMark(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(42, 42)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(CYAN), 1.5))
        p.drawRoundedRect(QRectF(1, 1, 39, 39), 10, 10)
        for y, width in [(14, 22), (21, 16), (28, 10)]:
            p.drawLine(QPointF(21 - width / 2, y), QPointF(21 + width / 2, y))


class AttitudeView(QWidget):
    """Native artificial horizon; all indicated angles come from the simulation."""
    def __init__(self):
        super().__init__()
        self.roll = self.pitch = self.yaw = 0.0
        self.setMinimumSize(175, 180)

    def set_state(self, state):
        self.roll, self.pitch, self.yaw = state.roll, state.pitch, state.yaw
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        radius = min(self.width() / 2 - 14, self.height() / 2 - 24)
        center = QPointF(self.width() / 2, self.height() / 2 - 10)
        p.translate(center)
        clip = QPainterPath()
        clip.addEllipse(QPointF(0, 0), radius, radius)
        p.save()
        p.setClipPath(clip)
        p.rotate(-self.roll)
        p.translate(0, self.pitch * 2)
        p.fillRect(QRectF(-200, -300, 400, 300), QColor("#1e435d"))
        p.fillRect(QRectF(-200, 0, 400, 300), QColor("#172f36"))
        p.setPen(QPen(QColor("#a5c6d5"), 1.5))
        p.drawLine(QPointF(-200, 0), QPointF(200, 0))
        p.setPen(QPen(QColor("#6e8f9f"), 1))
        for y in [-40, -20, 20, 40]:
            width = 20 if abs(y) == 20 else 32
            p.drawLine(QPointF(-width, y), QPointF(width, y))
        p.restore()
        p.setPen(QPen(QColor("#35465a"), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(0, 0), radius, radius)
        p.setPen(QPen(QColor(CYAN), 3))
        p.drawLine(QPointF(-40, 0), QPointF(-13, 0))
        p.drawLine(QPointF(13, 0), QPointF(40, 0))
        p.drawLine(QPointF(0, -5), QPointF(0, 5))
        p.setFont(QFont("DejaVu Sans", 9))
        p.setPen(QColor(TEXT))
        p.drawText(QRectF(-80, radius + 8, 160, 22), Qt.AlignmentFlag.AlignCenter,
                   f"HDG  {self.yaw:05.1f}°")


class DepthPlot(QWidget):
    def __init__(self):
        super().__init__()
        self.samples = deque(maxlen=1200)  # 120 seconds at 10 Hz
        self.target = None
        self.setMinimumHeight(180)

    def add(self, elapsed, depth, target):
        self.samples.append((elapsed, depth))
        self.target = target
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        box = QRectF(48, 14, max(1, self.width() - 66), max(1, self.height() - 48))
        values = [d for _, d in self.samples] + ([self.target] if self.target is not None else [])
        max_depth = max(5.0, math.ceil(max(values, default=2) + 1))
        p.setFont(QFont("Sans Serif", 9))
        for i in range(5):
            y = box.top() + box.height() * i / 4
            p.setPen(QColor("#24344a"))
            p.drawLine(QPointF(box.left(), y), QPointF(box.right(), y))
            p.setPen(QColor(MUTED))
            p.drawText(QRectF(0, y - 9, 40, 18), Qt.AlignmentFlag.AlignRight,
                       f"{max_depth * i / 4:.1f} m")
        end = self.samples[-1][0] if self.samples else 0
        start = max(0.0, end - 120)
        span = 120.0
        for i in range(5):
            x = box.left() + box.width() * i / 4
            p.drawText(QRectF(x - 22, box.bottom() + 10, 48, 20),
                       Qt.AlignmentFlag.AlignCenter, f"{start + span * i / 4:.0f}s")
        if self.target is not None:
            y = box.top() + self.target / max_depth * box.height()
            p.setPen(QPen(QColor(BLUE), 1, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(box.left(), y), QPointF(box.right(), y))
        if not self.samples:
            return
        points = [QPointF(box.left() + (t - start) / span * box.width(),
                         box.top() + d / max_depth * box.height())
                  for t, d in self.samples if t >= start]
        path = QPainterPath(points[0])
        for point in points[1:]:
            path.lineTo(point)
        area = QPainterPath(path)
        area.lineTo(points[-1].x(), box.bottom())
        area.lineTo(points[0].x(), box.bottom())
        area.closeSubpath()
        gradient = QLinearGradient(0, box.top(), 0, box.bottom())
        gradient.setColorAt(0, QColor(67, 221, 193, 65))
        gradient.setColorAt(1, QColor(67, 221, 193, 0))
        p.fillPath(area, gradient)
        p.setPen(QPen(QColor(CYAN), 2.5))
        p.drawPath(path)
        p.setBrush(QColor(CYAN))
        p.drawEllipse(points[-1], 4, 4)


class MapView(QWidget):
    """Coastal OSM basemap with explicitly simulated marine navigation overlays."""
    LAT = 17.7000
    LON = 83.3400

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(220)
        self.zoom = 14
        self.east = self.north = 0.0
        self.yaw = 35.0
        self.depth = 2.0
        self.track = deque(maxlen=1200)
        self.tiles = OrderedDict()
        self.pending = set()
        self.failed = {}
        self.network = QNetworkAccessManager(self)
        cache = QNetworkDiskCache(self)
        cache.setCacheDirectory(QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.CacheLocation) + "/osm")
        cache.setMaximumCacheSize(50 * 1024 * 1024)
        self.network.setCache(cache)
        self.network.finished.connect(self.tile_finished)

    def tile_xy(self, lat, lon):
        n = 2 ** self.zoom
        lat = math.radians(max(-85.0, min(85.0, lat)))
        return ((lon + 180) / 360 * n,
                (1 - math.asinh(math.tan(lat)) / math.pi) / 2 * n)

    def request_tile(self, key):
        if key in self.pending or time.monotonic() - self.failed.get(key, -1e9) < 30:
            return
        self.pending.add(key)
        z, x, y = key
        request = QNetworkRequest(QUrl(f"https://tile.openstreetmap.org/{z}/{x}/{y}.png"))
        request.setRawHeader(b"User-Agent", b"CoratiaROVAssessment/1.0 (native desktop educational simulator)")
        request.setAttribute(QNetworkRequest.Attribute.CacheLoadControlAttribute,
                             QNetworkRequest.CacheLoadControl.PreferCache)
        request.setTransferTimeout(8000)
        reply = self.network.get(request)
        reply.setProperty("tile_key", key)

    def tile_finished(self, reply):
        key = tuple(reply.property("tile_key"))
        self.pending.discard(key)
        pixmap = QPixmap()
        if reply.error() == reply.NetworkError.NoError and pixmap.loadFromData(reply.readAll()):
            self.tiles[key] = pixmap
            while len(self.tiles) > 80:
                self.tiles.popitem(last=False)
        else:
            self.failed[key] = time.monotonic()
        reply.deleteLater()
        self.update()

    def set_position(self, state):
        self.north, self.east, self.yaw = state.north, state.east, state.yaw
        self.depth = state.depth
        if not self.track or math.hypot(self.north - self.track[-1][0],
                                        self.east - self.track[-1][1]) >= 1.0:
            self.track.append((self.north, self.east))
        self.update()

    def change_zoom(self, delta):
        self.zoom = max(12, min(18, self.zoom + delta))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#16283a"))
        lat = self.LAT + self.north / 111320
        lon = self.LON + self.east / (111320 * math.cos(math.radians(self.LAT)))
        cx, cy = self.tile_xy(lat, lon)
        left, top = cx * 256 - self.width() / 2, cy * 256 - self.height() / 2
        loaded = 0
        for x in range(math.floor(left / 256), math.floor((left + self.width()) / 256) + 1):
            for y in range(math.floor(top / 256), math.floor((top + self.height()) / 256) + 1):
                if not 0 <= y < 2 ** self.zoom:
                    continue
                key = (self.zoom, x % 2 ** self.zoom, y)
                rect = QRectF(x * 256 - left, y * 256 - top, 256, 256)
                if key in self.tiles:
                    p.drawPixmap(rect.toRect(), self.tiles[key])
                    loaded += 1
                else:
                    p.setPen(QColor("#223b50"))
                    p.drawRect(rect)
                    self.request_tile(key)
        # Mute street-map colors so the water mission overlays remain legible.
        p.fillRect(self.rect(), QColor(7, 23, 39, 178))
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        sx, sy = self.tile_xy(self.LAT, self.LON)
        origin = QPointF(sx * 256 - left, sy * 256 - top)
        meters_per_pixel = 156543.03392 * math.cos(math.radians(lat)) / 2 ** self.zoom
        to_screen = lambda north, east: QPointF(origin.x() + east / meters_per_pixel,
                                                origin.y() - north / meters_per_pixel)
        # Local metre grid and range rings are references, not surveyed seabed data.
        spacing_m = next(v for v in (50, 100, 250, 500, 1000, 2500, 5000)
                         if v / meters_per_pixel >= 45)
        spacing = spacing_m / meters_per_pixel
        p.setPen(QPen(QColor(113, 191, 202, 24), 1))
        x = origin.x() % spacing
        while x < self.width():
            p.drawLine(QPointF(x, 0), QPointF(x, self.height()))
            x += spacing
        y = origin.y() % spacing
        while y < self.height():
            p.drawLine(QPointF(0, y), QPointF(self.width(), y))
            y += spacing
        p.setFont(QFont("DejaVu Sans", 8))
        for distance in (250, 500, 1000):
            radius = distance / meters_per_pixel
            p.setPen(QPen(QColor(67, 221, 193, 85), 1, Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(origin, radius, radius)
            if 40 < radius < self.width() / 2:
                p.setPen(QColor("#99c9ca"))
                p.drawText(origin + QPointF(radius * 0.707 + 5, -radius * 0.707 - 5),
                           f"{distance} m")
        if len(self.track) > 1:
            trail = QPainterPath(to_screen(*self.track[0]))
            for north, east in self.track:
                trail.lineTo(to_screen(north, east))
            p.setPen(QPen(QColor(CYAN), 2))
            p.drawPath(trail)
        p.setPen(QPen(QColor("#b1c9dc"), 1))
        p.drawLine(origin + QPointF(-5, 0), origin + QPointF(5, 0))
        p.drawLine(origin + QPointF(0, -5), origin + QPointF(0, 5))
        p.drawText(origin + QPointF(-75, 30), "LAUNCH ORIGIN")
        p.save()
        p.translate(self.width() / 2, self.height() / 2)
        p.setPen(QPen(QColor(CYAN), 1.5))
        p.setBrush(QColor(20, 139, 145, 45))
        p.drawEllipse(QPointF(0, 0), 24, 24)
        p.rotate(self.yaw)
        pointer = QPainterPath(QPointF(0, -15))
        pointer.lineTo(10, 12)
        pointer.lineTo(0, 7)
        pointer.lineTo(-10, 12)
        pointer.closeSubpath()
        p.setBrush(QColor(CYAN))
        p.drawPath(pointer)
        p.restore()
        cx_pixel, cy_pixel = self.width() / 2, self.height() / 2
        p.fillRect(QRectF(cx_pixel + 34, cy_pixel - 24, 142, 47), QColor(9, 22, 35, 235))
        p.setPen(QColor(CYAN))
        p.drawText(QPointF(cx_pixel + 44, cy_pixel - 7), "ROV-01  /  SIM")
        p.setPen(QColor(TEXT))
        p.drawText(QPointF(cx_pixel + 44, cy_pixel + 11), f"{self.depth:.1f} m  •  {self.yaw:05.1f}°")
        p.fillRect(QRectF(12, 12, 238, 45), QColor(9, 22, 35, 235))
        p.setPen(QColor(TEXT))
        p.drawText(24, 31, "BAY OF BENGAL  /  COASTAL SECTOR")
        p.setPen(QColor("#94b0c4"))
        p.drawText(24, 47, "Simulated navigation • OSM basemap")
        # North-up orientation and scale stay meaningful at every zoom level.
        p.setPen(QPen(QColor(TEXT), 1.5))
        nx = self.width() - 30
        p.drawLine(QPointF(nx, 38), QPointF(nx, 65))
        p.drawLine(QPointF(nx, 38), QPointF(nx - 4, 45))
        p.drawLine(QPointF(nx, 38), QPointF(nx + 4, 45))
        p.drawText(QPointF(nx - 4, 29), "N")
        scale_m = spacing_m
        scale_px = scale_m / meters_per_pixel
        base_y = self.height() - 43
        p.drawLine(QPointF(18, base_y), QPointF(18 + scale_px, base_y))
        for x in (18, 18 + scale_px):
            p.drawLine(QPointF(x, base_y - 4), QPointF(x, base_y + 4))
        p.drawText(QPointF(18, base_y - 9), f"{scale_m} m")
        p.drawText(QPointF(self.width() - 190, base_y),
                   f"FROM LAUNCH  {math.hypot(self.north, self.east):.0f} m")
        p.setFont(QFont("Sans Serif", 9))
        p.fillRect(0, self.height() - 27, self.width(), 27, QColor(10, 18, 30, 235))
        p.setPen(QColor(TEXT))
        p.drawText(10, self.height() - 9, "© OpenStreetMap contributors • openstreetmap.org/copyright")
        if not loaded:
            p.fillRect(12, 64, 320, 26, QColor(BG))
            p.setPen(QColor(MUTED))
            message = "Map unavailable • connect to the internet" if self.failed else "Loading OpenStreetMap…"
            p.drawText(22, 82, message)


class Dashboard(QMainWindow):
    KEYS = {Qt.Key.Key_W, Qt.Key.Key_S, Qt.Key.Key_A, Qt.Key.Key_D,
            Qt.Key.Key_R, Qt.Key.Key_F, Qt.Key.Key_Q, Qt.Key.Key_E}

    def __init__(self):
        super().__init__()
        self.sim = Simulation()
        self.pressed = set()
        self.last_operator_event = -math.inf
        self.csv_file = self.csv_writer = None
        self.setWindowTitle("ABYSS • ROV Telemetry Ground Station")
        self.resize(1400, 920)
        self.setMinimumSize(1100, 780)
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(28, 22, 28, 16)
        outer.setSpacing(16)
        header = QHBoxLayout()
        header.addWidget(BrandMark())
        header.addSpacing(8)
        titles = QVBoxLayout()
        titles.setSpacing(3)
        titles.addWidget(label("CORATIA  /  ABYSS", 18, TEXT, True))
        titles.addWidget(label("ROV OPERATIONS PLATFORM", 9, MUTED, True))
        header.addLayout(titles)
        header.addStretch()
        header.addWidget(label("●  SIMULATOR ONLINE", 10, CYAN, True))
        self.clock_label = label("00:00", 18, MUTED)
        header.addSpacing(24)
        header.addWidget(self.clock_label)
        outer.addLayout(header)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background: #263142;")
        outer.addWidget(divider)
        mission_row = QHBoxLayout()
        mission_titles = QVBoxLayout()
        mission_titles.setSpacing(3)
        mission_titles.addWidget(label("Mission overview", 25, TEXT, True))
        mission_titles.addWidget(label("ROV-01  /  Bay of Bengal · Visakhapatnam offshore", 11, MUTED))
        mission_row.addLayout(mission_titles)
        mission_row.addStretch()
        mission_row.addWidget(label("LOCAL SIMULATION   •   LIVE TELEMETRY", 10, MUTED))
        outer.addLayout(mission_row)

        metrics = QHBoxLayout()
        metrics.setSpacing(12)
        self.cards = {}
        for name, unit, color in [("Depth", "m", CYAN), ("Heading", "°", BLUE),
                                  ("Roll", "°", TEXT), ("Pitch", "°", TEXT),
                                  ("Battery", "V", "#a5df9d")]:
            self.cards[name] = Metric(name, unit, color)
            metrics.addWidget(self.cards[name])
        outer.addLayout(metrics)

        body = QHBoxLayout()
        body.setSpacing(16)
        left = QVBoxLayout()
        left.setSpacing(16)
        plot_panel = panel()
        plot_layout = QVBoxLayout(plot_panel)
        plot_layout.setContentsMargins(18, 16, 18, 12)
        plot_header = QHBoxLayout()
        plot_header.addWidget(label("Depth history", 14, TEXT, True))
        plot_header.addStretch()
        plot_header.addWidget(label("● Depth   ┄ Target", 10, CYAN))
        plot_layout.addLayout(plot_header)
        self.plot = DepthPlot()
        plot_layout.addWidget(self.plot)
        map_panel = panel()
        map_layout = QVBoxLayout(map_panel)
        map_layout.setContentsMargins(18, 14, 18, 12)
        map_header = QHBoxLayout()
        map_header.addWidget(label("Marine navigation", 14, TEXT, True))
        map_header.addStretch()
        map_header.addWidget(label("NORTH UP  /  LIVE TRACK", 10, MUTED))
        for text, delta in [("−", -1), ("+", 1)]:
            button = QPushButton(text)
            button.setMinimumHeight(32)
            button.setFixedSize(30, 28)
            button.setStyleSheet("padding: 0; font-size: 16px;")
            button.clicked.connect(lambda checked=False, d=delta: self.map.change_zoom(d))
            map_header.addWidget(button)
        map_layout.addLayout(map_header)
        self.map = MapView()
        map_layout.addWidget(self.map, 1)
        self.coordinates = label("", 11, MUTED)
        self.coordinates.setFixedHeight(18)
        map_layout.addWidget(self.coordinates)
        left.addWidget(map_panel, 6)
        lower = QHBoxLayout()
        lower.setSpacing(16)
        lower.addWidget(plot_panel, 7)
        attitude_panel = panel()
        attitude_layout = QVBoxLayout(attitude_panel)
        attitude_layout.setContentsMargins(16, 16, 16, 10)
        attitude_layout.addWidget(label("Vehicle attitude", 14, TEXT, True))
        self.attitude = AttitudeView()
        attitude_layout.addWidget(self.attitude)
        lower.addWidget(attitude_panel, 3)
        left.addLayout(lower, 4)
        body.addLayout(left, 7)

        controls = panel()
        controls.setMinimumWidth(300)
        side = QVBoxLayout(controls)
        side.setContentsMargins(18, 16, 18, 16)
        side.setSpacing(6)
        side.addWidget(label("Command center", 16, TEXT, True))
        self.armed_label = label("● DISARMED", 13, "#ffbd78", True)
        side.addWidget(self.armed_label)
        self.arm_button = QPushButton("ARM VEHICLE")
        self.arm_button.setObjectName("arm")
        self.arm_button.setMinimumHeight(42)
        self.arm_button.clicked.connect(self.toggle_arm)
        self.arm_button.setToolTip("Enable thrusters, or immediately disarm if already armed")
        side.addWidget(self.arm_button)
        stop = QPushButton("DISARM  /  EMERGENCY STOP  [Esc]")
        stop.setObjectName("stop")
        stop.setMinimumHeight(32)
        stop.clicked.connect(self.disarm)
        side.addWidget(stop)
        side.addWidget(label("CONTROL MODE", 10, MUTED, True))
        self.mode = QComboBox()
        self.mode.setMinimumHeight(34)
        self.mode.addItems(Simulation.MODES)
        self.mode.currentTextChanged.connect(self.change_mode)
        side.addWidget(self.mode)
        targets = QGridLayout()
        targets.setVerticalSpacing(8)
        self.depth_target = QDoubleSpinBox()
        self.depth_target.setRange(0, 100)
        self.depth_target.setValue(2)
        self.depth_target.setSuffix(" m")
        self.depth_target.setToolTip("Depth Hold target: 0–100 metres below the surface")
        self.heading_target = QDoubleSpinBox()
        self.heading_target.setRange(0, 359.9)
        self.heading_target.setValue(35)
        self.heading_target.setSuffix(" °")
        self.heading_target.setToolTip("Heading Hold target: degrees clockwise from north")
        for row, (name, field) in enumerate([("Target depth", self.depth_target),
                                             ("Target heading", self.heading_target)]):
            field.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.PlusMinus)
            field.setMinimumHeight(30)
            targets.addWidget(label(name, 12, MUTED), row, 0)
            targets.addWidget(field, row, 1)
        self.depth_target.valueChanged.connect(self.set_depth_target)
        self.heading_target.valueChanged.connect(self.set_heading_target)
        side.addLayout(targets)
        self.depth_target.setEnabled(False)
        self.heading_target.setEnabled(False)
        side.addWidget(label("MANUAL CONTROL", 10, MUTED, True))
        side.addWidget(label("Hold a key or a direction to apply thrust", 10, MUTED))
        grid = QGridLayout()
        grid.setSpacing(6)
        self.manual_buttons = []
        buttons = [("W  Forward", Qt.Key.Key_W), ("S  Reverse", Qt.Key.Key_S),
                   ("A  Left", Qt.Key.Key_A), ("D  Right", Qt.Key.Key_D),
                   ("R  Ascend", Qt.Key.Key_R), ("F  Descend", Qt.Key.Key_F),
                   ("Q  Turn left", Qt.Key.Key_Q), ("E  Turn right", Qt.Key.Key_E)]
        for index, (text, key) in enumerate(buttons):
            button = QPushButton(text)
            button.setMinimumHeight(32)
            button.setStyleSheet("padding: 6px 8px; text-align: left;")
            button.setToolTip("Press and hold to move; release to request zero thrust")
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.pressed.connect(lambda k=key: self.pressed.add(k))
            button.released.connect(lambda k=key: self.release_control(k))
            self.manual_buttons.append(button)
            grid.addWidget(button, index // 2, index % 2)
        side.addLayout(grid)
        self.thrust_label = label("Surge +0.00   Sway +0.00\nHeave +0.00   Yaw +0.00", 11, CYAN)
        self.thrust_label.setStyleSheet("font-family: 'DejaVu Sans Mono'; font-size: 10px; color: #8b9bb0; padding: 8px; background: #0d141e; border-radius: 6px;")
        side.addWidget(self.thrust_label)
        side.addStretch()
        self.safety_label = label("Thrust inhibited • vehicle disarmed", 11, "#ffbd78")
        self.safety_label.setWordWrap(True)
        side.addWidget(self.safety_label)
        self.log_button = QPushButton("↓  Start CSV recording")
        self.log_button.clicked.connect(self.toggle_logging)
        side.addWidget(self.log_button)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedWidth(332)
        scroll.setWidget(controls)
        body.addWidget(scroll)
        outer.addLayout(body, 1)
        footer = QHBoxLayout()
        footer.addWidget(label("●  50 Hz physics   /   10 Hz telemetry", 10, MUTED))
        footer.addStretch()
        footer.addWidget(label("SIMULATOR ONLY  •  No hardware connection", 10, MUTED))
        outer.addLayout(footer)

        QApplication.instance().installEventFilter(self)
        self.physics_timer = QTimer(self)
        self.physics_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.physics_timer.timeout.connect(self.advance)
        self.physics_timer.start(20)
        self.last_tick = time.monotonic()
        self.accumulator = 0.0
        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self.refresh)
        self.ui_timer.start(100)
        self.refresh()

    def set_depth_target(self, value):
        self.sim.target_depth = value

    def set_heading_target(self, value):
        self.sim.target_heading = value

    def release_control(self, key):
        self.pressed.discard(key)
        self.send_controls()  # Release does not wait for the next physics tick.

    def send_controls(self):
        self.last_operator_event = time.monotonic()
        k = self.pressed
        axis = lambda positive, negative: float(positive in k) - float(negative in k)
        self.sim.operator_input(axis(Qt.Key.Key_W, Qt.Key.Key_S),
                                axis(Qt.Key.Key_D, Qt.Key.Key_A),
                                axis(Qt.Key.Key_F, Qt.Key.Key_R),
                                axis(Qt.Key.Key_E, Qt.Key.Key_Q))

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.ApplicationDeactivate:
            self.pressed.clear()
            self.send_controls()
        if event.type() in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            if event.key() == Qt.Key.Key_Escape:
                self.disarm()
                return True
            if event.key() in self.KEYS:
                if event.isAutoRepeat():
                    return True
                if event.type() == QEvent.Type.KeyRelease:
                    self.release_control(event.key())
                    return True
                # Editing numeric targets never accidentally commands movement.
                focus = QApplication.focusWidget()
                if any(field is focus or (focus and field.isAncestorOf(focus))
                       for field in (self.depth_target, self.heading_target)):
                    return False
                if self.sim.state.mode == "Manual" and self.isActiveWindow():
                    self.pressed.add(event.key())
                    return True
        return super().eventFilter(obj, event)

    def toggle_arm(self):
        self.pressed.clear()
        self.sim.arm(not self.sim.state.armed)
        self.refresh()

    def disarm(self):
        self.pressed.clear()
        self.sim.arm(False)
        self.refresh()

    def change_mode(self, mode):
        self.pressed.clear()
        self.sim.set_mode(mode)
        self.depth_target.setEnabled(mode == "Depth Hold")
        self.heading_target.setEnabled(mode == "Heading Hold")
        for button in self.manual_buttons:
            button.setEnabled(mode == "Manual")
        self.refresh()

    def advance(self):
        now = time.monotonic()
        wall_dt = now - self.last_tick
        self.last_tick = now
        # A stalled event loop must never extend a stale Manual command.
        if wall_dt >= 1.0:
            self.pressed.clear()
            self.sim.last_input = -math.inf
        if self.pressed:
            self.send_controls()
        elif now - self.last_operator_event >= 1.0:
            self.sim.last_input = -math.inf
        self.accumulator += min(wall_dt, 0.1)
        while self.accumulator >= 0.02:
            self.sim.step(0.02)
            self.accumulator -= 0.02

    def refresh(self):
        s = self.sim.state
        for name, value in [("Depth", s.depth), ("Heading", s.yaw), ("Roll", s.roll),
                             ("Pitch", s.pitch), ("Battery", s.voltage)]:
            self.cards[name].value.setText(f"{value:.2f}" if name == "Battery" else f"{value:.1f}")
        self.clock_label.setText(f"{int(s.elapsed) // 60:02}:{int(s.elapsed) % 60:02}")
        self.armed_label.setText("● ARMED  /  " + s.mode.upper() if s.armed else "● DISARMED  /  " + s.mode.upper())
        self.armed_label.setStyleSheet(f"background: transparent; color: {CYAN if s.armed else '#ffbd78'}; font-size: 12px; font-weight: 700;")
        self.arm_button.setText("DISARM VEHICLE" if s.armed else "ARM VEHICLE")
        self.plot.add(s.elapsed, s.depth, self.sim.target_depth if s.mode == "Depth Hold" else None)
        self.map.set_position(s)
        self.attitude.set_state(s)
        lat = self.map.LAT + s.north / 111320
        lon = self.map.LON + s.east / (111320 * math.cos(math.radians(self.map.LAT)))
        self.coordinates.setText(f"{lat:.6f}° N   {lon:.6f}° E   /   Estimated from simulated motion")
        a, b, c, d = self.sim.thrust
        self.thrust_label.setText(f"Surge {a:+.2f}   Sway {b:+.2f}\nHeave {c:+.2f}   Yaw {d:+.2f}")
        self.safety_label.setText("Thrust inhibited • vehicle disarmed" if not s.armed else
                                  "Manual input idle • thrust zero" if self.sim.watchdog else
                                  "Manual watchdog active • 1 s timeout" if s.mode == "Manual" else
                                  f"{s.mode} controller active")
        if self.csv_writer:
            try:
                self.csv_writer.writerow([f"{s.elapsed:.2f}", s.armed, s.mode,
                                          s.roll, s.pitch, s.yaw, s.depth, s.voltage,
                                          s.north, s.east, *self.sim.thrust])
            except OSError as error:
                self.stop_logging()
                QMessageBox.warning(self, "Recording stopped", str(error))

    def stop_logging(self):
        if self.csv_file:
            try:
                self.csv_file.close()
            except OSError:
                pass
        self.csv_file = self.csv_writer = None
        self.log_button.setText("↓  Start CSV recording")

    def toggle_logging(self):
        if self.csv_file:
            self.stop_logging()
            return
        self.pressed.clear()
        self.send_controls()
        filename, _ = QFileDialog.getSaveFileName(self, "Save telemetry", "telemetry.csv", "CSV files (*.csv)")
        if not filename:
            return
        try:
            self.csv_file = open(filename, "w", newline="", encoding="utf-8")
            self.csv_writer = csv.writer(self.csv_file)
            self.csv_writer.writerow(["time_s", "armed", "mode", "roll_deg", "pitch_deg", "yaw_deg",
                                      "depth_m", "voltage_v", "north_m", "east_m",
                                      "surge", "sway", "heave", "yaw_thrust"])
            self.log_button.setText("■  Stop CSV recording")
        except OSError as error:
            self.stop_logging()
            QMessageBox.warning(self, "Cannot record", str(error))

    def closeEvent(self, event):
        self.sim.arm(False)
        self.stop_logging()
        super().closeEvent(event)


STYLE = """
QMainWindow, QWidget { background: #0b1018; color: #edf3fa; font-family: 'DejaVu Sans', 'Segoe UI', sans-serif; }
QFrame#panel { background: #121b27; border: 1px solid #263244; border-radius: 10px; }
QFrame#panel QLabel { background: transparent; border: none; }
QPushButton { background: #1a2737; border: 1px solid #334257; border-radius: 6px; padding: 8px; font-size: 11px; font-weight: 500; }
QPushButton:hover { background: #24374b; border-color: #708ca9; }
QPushButton:pressed { background: #19534e; border-color: #43ddc1; }
QPushButton:focus, QComboBox:focus, QDoubleSpinBox:focus { border: 1px solid #43ddc1; }
QPushButton:disabled { color: #64748b; background: #111b28; border-color: #263244; }
QPushButton#arm { background: #43ddc1; color: #092721; font-weight: bold; border: none; font-size: 12px; }
QPushButton#arm:hover { background: #78ead5; }
QPushButton#stop { color: #f0aaa9; border-color: #624147; background: #2b2029; font-size: 10px; }
QPushButton#stop:hover { background: #50303a; border-color: #ec9290; }
QComboBox, QDoubleSpinBox { background: #0d1520; border: 1px solid #334257; border-radius: 5px; padding: 5px 8px; font-size: 12px; }
QComboBox:disabled, QDoubleSpinBox:disabled { color: #627087; border-color: #243043; }
QComboBox QAbstractItemView { background: #182537; selection-background-color: #23635b; padding: 5px; }
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: #101925; width: 6px; margin: 0; }
QScrollBar::handle:vertical { background: #3c4d63; border-radius: 3px; min-height: 32px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QToolTip { color: #edf3fa; background: #1a2737; border: 1px solid #3c4d63; padding: 6px; }
"""


def main():
    from PySide6 import __version__ as qt_binding_version
    binding_parts = tuple(map(int, qt_binding_version.split(".")[:2]))
    if sys.version_info < (3, 12) and binding_parts >= (6, 12):
        print("This installed Qt binding crashes with Python 3.10 during drawing.\n"
              "Use the repaired Python 3.12 environment: ./run.sh\n"
              "Or install requirements.txt in a fresh environment for your Python version.",
              file=sys.stderr)
        sys.exit(2)
    app = QApplication(sys.argv)
    app.setApplicationName("AbyssROV")
    app.setOrganizationName("CoratiaAssessment")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = Dashboard()
    window.show()
    # Optional reproducible screenshot for local review; no sample telemetry injection.
    if "--screenshot" in sys.argv:
        QTimer.singleShot(5000, lambda: (window.grab().save(str(Path(__file__).with_name("dashboard.png"))), app.quit()))
    exit_code = app.exec()
    # Destroy Qt objects while Python callbacks and modules are still alive.
    # Remove callbacks before Qt begins tearing down its widget hierarchy.
    app.removeEventFilter(window)
    window.physics_timer.stop()
    window.ui_timer.stop()
    window.close()
    shiboken6.delete(window)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
