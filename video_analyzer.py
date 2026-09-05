"""Глаз Паноптикума. Сглаженный анализ кадра для стабильной музыки."""

import cv2
import numpy as np
from dataclasses import dataclass


@dataclass
class FrameData:
    brightness: float = 0.0
    movement: float = 0.0
    dominant_color: str = "neutral"
    color_rgb: tuple = (0.0, 0.0, 0.0)
    sudden_change: bool = False
    complexity: float = 0.0
    is_night: bool = False
    stillness_duration: float = 0.0


class VideoAnalyzer:
    def __init__(self):
        self.prev_gray = None
        self.movement_history = []
        self.stillness_counter = 0
        self._ema = 0.0

    def analyze(self, frame):
        data = FrameData()
        try:
            if frame is None or frame.size == 0:
                return data
            small = cv2.resize(frame, (320, 240))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

            data.brightness = float(np.mean(gray)) / 255.0
            data.is_night = data.brightness < 0.30

            raw = 0.0
            if self.prev_gray is not None:
                diff = cv2.absdiff(self.prev_gray, gray)
                raw = min(float(np.mean(diff)) / 40.0, 1.0)
            self.prev_gray = gray.copy()
            self._ema = 0.7 * self._ema + 0.3 * raw
            data.movement = self._ema

            self.movement_history.append(raw)
            if len(self.movement_history) > 30:
                self.movement_history.pop(0)
            avg = np.mean(self.movement_history) if self.movement_history else 0
            data.sudden_change = raw > max(avg * 3.0, 0.15)

            if data.movement < 0.02:
                self.stillness_counter += 1
            else:
                self.stillness_counter = 0
            data.stillness_duration = min(self.stillness_counter / 30.0, 10.0)

            ac = small.mean(axis=(0, 1))
            b, g, r = ac / 255.0
            data.color_rgb = (r, g, b)
            w = r - b
            if w > 0.08 and r > 0.3: data.dominant_color = "warm"
            elif w < -0.08 and b > 0.3: data.dominant_color = "cool"
            elif g > r and g > b and g > 0.3: data.dominant_color = "nature"
            else: data.dominant_color = "neutral"

            edges = cv2.Canny(gray, 30, 120)
            data.complexity = min(float(np.sum(edges > 0)) / (320*240) * 5.0, 1.0)
        except Exception as e:
            print("analyze error:", e)
        return data

    def reset(self):
        self.prev_gray = None
        self.movement_history.clear()
        self.stillness_counter = 0
        self._ema = 0.0