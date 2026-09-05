"""
video_analyzer.py
Превращает чужую жизнь в числа.
Движение. Свет. Цвет. Резкость бытия.
"""

import cv2
import numpy as np
from dataclasses import dataclass, field


@dataclass
class FrameData:
    """Данные одного кадра чужой жизни."""
    brightness: float = 0.0        # 0.0 (тьма) — 1.0 (свет)
    movement: float = 0.0          # 0.0 (покой) — 1.0 (хаос)
    dominant_color: str = "neutral" # red/green/blue/neutral
    color_values: tuple = (0, 0, 0) # BGR средние
    sudden_change: bool = False     # резкий скачок
    complexity: float = 0.0        # визуальная сложность сцены
    is_night: bool = False


class VideoAnalyzer:
    """Извлекает музыкальные параметры из видеопотока."""

    def __init__(self):
        self.prev_gray = None
        self.movement_history: list[float] = []
        self.brightness_history: list[float] = []

    def analyze(self, frame: np.ndarray) -> FrameData:
        """Анализ одного кадра → FrameData."""
        data = FrameData()

        # Перевод в ч/б для анализа
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # ── Яркость → тональность (день/ночь) ──
        data.brightness = float(np.mean(gray)) / 255.0
        data.is_night = data.brightness < 0.35

        # ── Движение → ритм и интенсивность ──
        if self.prev_gray is not None:
            diff = cv2.absdiff(self.prev_gray, gray)
            data.movement = float(np.mean(diff)) / 255.0
        else:
            data.movement = 0.0
        self.prev_gray = gray.copy()

        # ── Резкие изменения → акценты ──
        self.movement_history.append(data.movement)
        if len(self.movement_history) > 10:
            self.movement_history.pop(0)
        avg_movement = np.mean(self.movement_history) if self.movement_history else 0
        data.sudden_change = data.movement > avg_movement * 2.5 and data.movement > 0.08

        # ── Доминантный цвет → гамма ──
        avg_b, avg_g, avg_r = frame.mean(axis=(0, 1))
        data.color_values = (avg_b, avg_g, avg_r)
        r, g, b = avg_r / 255.0, avg_g / 255.0, avg_b / 255.0

        if r > g and r > b and r > 0.3:
            data.dominant_color = "red"       # → фригийский лад
        elif g > r and g > b and g > 0.3:
            data.dominant_color = "green"     # → дорийский лад
        elif b > r and b > g and b > 0.3:
            data.dominant_color = "blue"      # → лидийский лад
        else:
            data.dominant_color = "neutral"   # → ионийский лад

        # ── Сложность сцены → количество слоёв ──
        edges = cv2.Canny(gray, 50, 150)
        data.complexity = float(np.sum(edges > 0)) / (frame.shape[0] * frame.shape[1])

        return data

    def reset(self):
        self.prev_gray = None
        self.movement_history.clear()
        self.brightness_history.clear()