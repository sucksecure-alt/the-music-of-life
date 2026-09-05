"""
main.py
PANOPTICON SYMPHONY
Они не знают, что играют.
"""

import sys
import json
import time
import threading
import subprocess
import os
import cv2
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QComboBox, QSlider,
    QGridLayout, QFrame, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap, QFont, QPalette, QColor

from video_analyzer import VideoAnalyzer
from music_generator import MusicGenerator


class CameraThread(QThread):
    """Поток загрузки камеры."""
    frame_ready = pyqtSignal(np.ndarray)
    status_update = pyqtSignal(str)

    def __init__(self, url, camera_type="mjpeg"):
        super().__init__()
        self.url = url
        self.camera_type = camera_type
        self.running = True
        self.cap = None

    def _get_youtube_hls(self, url):
        """Извлечение HLS-потока из YouTube через yt-dlp."""
        try:
            result = subprocess.run(
                ["yt-dlp", "-g", "--no-playlist", url],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split("\n")[0]
        except Exception:
            pass
        return None

    def run(self):
        stream_url = self.url

        if self.camera_type == "youtube_hls":
            self.status_update.emit("Resolving stream...")
            stream_url = self._get_youtube_hls(self.url)
            if not stream_url:
                self.status_update.emit("Stream unavailable")
                return

        self.status_update.emit("Connecting...")
        self.cap = cv2.VideoCapture(stream_url)

        if not self.cap.isOpened():
            self.status_update.emit("Connection failed")
            return

        self.status_update.emit("LIVE")
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(1)
                self.cap.release()
                self.cap = cv2.VideoCapture(stream_url)
                continue
            self.frame_ready.emit(frame)
            time.sleep(0.033)  # ~30 FPS

        self.cap.release()

    def stop(self):
        self.running = False
        self.wait(2000)


class PanopticonWindow(QMainWindow):
    """Главное окно Паноптикума."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PANOPTICON SYMPHONY")
        self.setMinimumSize(1100, 750)
        self.setStyleSheet(self._dark_style())

        self.cameras = []
        self.camera_threads = []
        self.analyzers = []
        self.music_gen = MusicGenerator()
        self.active_camera_idx = 0
        self.is_recording = False
        self.recorded_chunks = []

        self._load_cameras()
        self._init_ui()
        self._start_active_camera()

    def _load_cameras(self):
        """Загрузка базы камер."""
        json_path = os.path.join(os.path.dirname(__file__), "camera_sources.json")
        try:
            with open(json_path, "r") as f:
                data = json.load(f)
            self.cameras = data.get("cameras", [])
        except Exception as e:
            self.cameras = []

    def _init_ui(self):
        """Инициализация интерфейса."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(15, 15, 15, 15)

        # ── Заголовок ──
        title = QLabel("◉ PANOPTICON SYMPHONY")
        title.setFont(QFont("Courier New", 24, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #ff4444;")
        layout.addWidget(title)

        subtitle = QLabel("they do not know they are playing")
        subtitle.setFont(QFont("Courier New", 10))
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #666;")
        layout.addWidget(subtitle)

        # ── Видео-зона ──
        video_frame = QFrame()
        video_frame.setStyleSheet("""
            QFrame {
                background: #0a0a0a;
                border: 1px solid #333;
                border-radius: 4px;
            }
        """)
        video_layout = QVBoxLayout(video_frame)

        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(640, 360)
        self.video_label.setText("SIGNAL LOST")
        self.video_label.setStyleSheet("color: #333; font-size: 18px; font-family: Courier;")
        video_layout.addWidget(self.video_label)

        layout.addWidget(video_frame)

        # ── Панель параметров ──
        params_frame = QFrame()
        params_frame.setStyleSheet("QFrame { background: #111; border-radius: 4px; }")
        params_layout = QHBoxLayout(params_frame)

        # Параметры музыки (обновляются в реальном времени)
        self.param_labels = {}
        param_names = [
            ("movement", "MOVEMENT"),
            ("brightness", "LIGHT"),
            ("color", "SPECTRUM"),
            ("complexity", "DENSITY"),
            ("mood", "MOOD"),
        ]
        for key, label_text in param_names:
            lbl = QLabel(f"{label_text}\n---")
            lbl.setFont(QFont("Courier New", 9))
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color: #0f0; padding: 5px;")
            params_layout.addWidget(lbl)
            self.param_labels[key] = lbl

        layout.addWidget(params_frame)

        # ── Кнопки управления ──
        controls = QHBoxLayout()

        self.camera_selector = QComboBox()
        for cam in self.cameras:
            self.camera_selector.addItem(f"📹 {cam['city']} — {cam['name']}")
        self.camera_selector.currentIndexChanged.connect(self._on_camera_change)
        self.camera_selector.setStyleSheet("QComboBox { background: #1a1a1a; color: #fff; padding: 5px; }")
        controls.addWidget(self.camera_selector)

        btn_random = QPushButton("🎲 RANDOM")
        btn_random.clicked.connect(self._random_camera)
        controls.addWidget(btn_random)

        btn_mute = QPushButton("🔇 SILENCE")
        btn_mute.setCheckable(True)
        btn_mute.clicked.connect(self._toggle_mute)
        controls.addWidget(btn_mute)

        btn_record = QPushButton("⏺ RECORD")
        btn_record.setCheckable(True)
        btn_record.clicked.connect(self._toggle_record)
        controls.addWidget(btn_record)

        btn_next = QPushButton("▶ NEXT SOUL")
        btn_next.clicked.connect(self._next_camera)
        controls.addWidget(btn_next)

        layout.addLayout(controls)

        # ── Статусная строка ──
        self.status_label = QLabel("INITIALIZING PANOPTICON...")
        self.status_label.setFont(QFont("Courier New", 8))
        self.status_label.setStyleSheet("color: #555;")
        layout.addWidget(self.status_label)

        # ── Таймер обновления параметров ──
        self.ui_timer = QTimer()
        self.ui_timer.timeout.connect(self._update_params_display)
        self.ui_timer.start(200)

    def _start_active_camera(self):
        """Запуск активной камеры."""
        # Остановка старых потоков
        for t in self.camera_threads:
            t.stop()

        if not self.cameras:
            self.status_label.setText("NO CAMERAS FOUND")
            return

        cam = self.cameras[self.active_camera_idx]
        analyzer = VideoAnalyzer()
        self.analyzers = [analyzer]

        thread = CameraThread(cam["url"], cam.get("type", "mjpeg"))
        thread.frame_ready.connect(self._on_frame)
        thread.status_update.connect(self._on_status)
        thread.start()
        self.camera_threads = [thread]

        self.status_label.setText(f"CONNECTED: {cam['city']} / {cam['name']}")

    def _on_frame(self, frame):
        """Обработка кадра."""
        # Отображение видео
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        scaled = qimg.scaled(self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.video_label.setPixmap(QPixmap.fromImage(scaled))

        # Анализ → музыка
        if self.analyzers:
            data = self.analyzers[0].analyze(frame)
            self.music_gen.update_data(data)
            self._current_data = data

    def _on_status(self, msg):
        self.status_label.setText(msg)

    def _on_camera_change(self, index):
        self.active_camera_idx = index
        self._start_active_camera()

    def _random_camera(self):
        import random
        idx = random.randint(0, len(self.cameras) - 1)
        self.camera_selector.setCurrentIndex(idx)

    def _next_camera(self):
        idx = (self.active_camera_idx + 1) % len(self.cameras)
        self.camera_selector.setCurrentIndex(idx)

    def _toggle_mute(self):
        if self.music_gen.running:
            self.music_gen.stop()
        else:
            self.music_gen = MusicGenerator()
            if hasattr(self, '_current_data'):
                self.music_gen.update_data(self._current_data)

    def _toggle_record(self):
        self.is_recording = not self.is_recording
        if self.is_recording:
            self.recorded_chunks = []
            self.status_label.setText("RECORDING THE SYMPHONY...")
        else:
            self._save_recording()

    def _save_recording(self):
        """Сохранение записи как WAV."""
        path, _ = QFileDialog.getSaveFileName(self, "Save Symphony", "panopticon.wav", "WAV (*.wav)")
        if path and self.recorded_chunks:
            import soundfile as sf
            audio = np.concatenate(self.recorded_chunks)
            sf.write(path, audio, self.music_gen.sample_rate)
            self.status_label.setText(f"SAVED: {path}")

    def _update_params_display(self):
        """Обновление панели параметров."""
        data = getattr(self, '_current_data', None)
        if not data:
            return

        colors = {"red": "🔴", "green": "🟢", "blue": "🔵", "neutral": "⚪"}
        mood = "DARK" if data.is_night else "LIGHT"
        if data.sudden_change:
            mood = "⚡ SHOCK"

        self.param_labels["movement"].setText(f"MOVEMENT\n{'█' * int(data.movement * 10)}{'░' * (10 - int(data.movement * 10))}")
        self.param_labels["brightness"].setText(f"LIGHT\n{data.brightness:.2f}")
        self.param_labels["color"].setText(f"SPECTRUM\n{colors.get(data.dominant_color, '⚪')} {data.dominant_color.upper()}")
        self.param_labels["complexity"].setText(f"DENSITY\n{data.complexity:.3f}")
        self.param_labels["mood"].setText(f"MOOD\n{mood}")

    def _dark_style(self):
        return """
            QMainWindow { background: #0d0d0d; }
            QWidget { background: #0d0d0d; color: #ccc; }
            QPushButton {
                background: #1a1a1a;
                color: #ff4444;
                border: 1px solid #333;
                padding: 8px 16px;
                font-family: Courier New;
                font-size: 11px;
                border-radius: 3px;
            }
            QPushButton:hover { background: #2a2a2a; border-color: #ff4444; }
            QPushButton:checked { background: #ff4444; color: #000; }
            QComboBox {
                background: #1a1a1a;
                color: #ccc;
                border: 1px solid #333;
                padding: 5px;
                font-family: Courier New;
            }
        """

    def closeEvent(self, event):
        for t in self.camera_threads:
            t.stop()
        self.music_gen.stop()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = PanopticonWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()