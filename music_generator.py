"""
music_generator.py
Превращает числа в звук.
Чужие шаги становятся ритмом.
Чужие закаты становятся тональностью.
"""

import numpy as np
import sounddevice as sd
import threading
import time
from collections import deque


class MusicGenerator:
    """Генеративный эмбиент из данных чужих жизней."""

    # Гаммы для разных состояний
    SCALES = {
        "red":     [0, 1, 4, 5, 7, 8, 11],      # Фригийский (тревога)
        "green":   [0, 2, 3, 5, 7, 9, 10],       # Дорийский (меланхолия)
        "blue":    [0, 2, 4, 6, 7, 9, 11],       # Лидийский (мечта)
        "neutral": [0, 2, 4, 5, 7, 9, 11],       # Ионийский (покой)
    }
    MINOR_SCALE = [0, 2, 3, 5, 7, 8, 10]          # Ночь

    # Тембры для цветов
    TIMBRES = {
        "red":     {"waveform": "sawtooth", "filter": 800},
        "green":   {"waveform": "sine",     "filter": 1200},
        "blue":    {"waveform": "triangle", "filter": 2000},
        "neutral": {"waveform": "sine",     "filter": 1500},
    }

    def __init__(self, sample_rate: int = 44100, base_freq: float = 110.0):
        self.sample_rate = sample_rate
        self.base_freq = base_freq
        self.stream = None
        self.running = False
        self.phase = 0.0
        self.current_frame_data = None
        self.note_queue = deque()
        self.lock = threading.Lock()
        self._start_stream()

    def _start_stream(self):
        """Запуск аудио-потока."""
        self.stream = sd.OutputStream(
            samplerate=self.sample_rate,
            channels=2,
            dtype="float32",
            blocksize=1024,
            callback=self._audio_callback
        )
        self.stream.start()
        self.running = True

    def _audio_callback(self, outdata, frames, time_info, status):
        """Генерация аудио в реальном времени."""
        if self.current_frame_data is None:
            outdata[:] = 0
            return

        data = self.current_frame_data
        t = np.arange(frames) / self.sample_rate
        audio = np.zeros((frames, 2), dtype=np.float32)

        # ── Пэд (фоновый слой) на основе яркости и цвета ──
        if data.is_night:
            scale = self.MINOR_SCALE
        else:
            scale = self.SCALES.get(data.dominant_color, self.SCALES["neutral"])

        # Аккорд из гаммы
        root_semitone = int(data.brightness * 12) % 12
        chord_semitones = [
            root_semitone,
            root_semitone + scale[2 % len(scale)],
            root_semitone + scale[4 % len(scale)],
        ]

        pad_volume = 0.15 + data.movement * 0.1
        timbre = self.TIMBRES.get(data.dominant_color, self.TIMBRES["neutral"])

        for semi in chord_semitones:
            freq = self.base_freq * (2 ** (semi / 12.0))
            wave = self._generate_wave(t, freq, timbre["waveform"])
            # Простой lowpass через экспоненциальное сглаживание
            wave = np.cumsum(wave) * (1.0 / (self.sample_rate * 0.001))
            wave = wave / (np.max(np.abs(wave)) + 1e-6)
            audio[:, 0] += wave * pad_volume * 0.33
            audio[:, 1] += wave * pad_volume * 0.33

        # ── Арпеджио на основе движения ──
        if data.movement > 0.03:
            arp_speed = max(1, int(1.0 / (data.movement * 5 + 0.01)))
            arp_note_idx = int((self.phase * arp_speed) % len(scale))
            arp_semitone = scale[arp_note_idx % len(scale)] + int(data.brightness * 12)
            arp_freq = self.base_freq * 2 * (2 ** (arp_semitone / 12.0))

            arp_env = np.exp(-t * 8)  # быстрое затухание
            arp_wave = np.sin(2 * np.pi * arp_freq * t) * arp_env
            arp_volume = data.movement * 0.3
            audio[:, 0] += arp_wave * arp_volume
            audio[:, 1] += arp_wave * arp_volume * 0.7  # панорама

        # ── Акцент при резком изменении ──
        if data.sudden_change:
            accent_freq = self.base_freq * 4
            accent_env = np.exp(-t * 20)
            accent = np.sin(2 * np.pi * accent_freq * t) * accent_env * 0.2
            audio[:, 0] += accent
            audio[:, 1] += accent

        # ── Сложность → дополнительные обертона ──
        if data.complexity > 0.05:
            overtone_freq = self.base_freq * 3
            overtone = np.sin(2 * np.pi * overtone_freq * t) * 0.05 * data.complexity
            audio += overtone

        self.phase += frames / self.sample_rate
        outdata[:] = np.clip(audio, -1.0, 1.0)

    def _generate_wave(self, t, freq, waveform):
        """Генерация волны определённой формы."""
        if waveform == "sine":
            return np.sin(2 * np.pi * freq * t)
        elif waveform == "triangle":
            return 2 * np.abs(2 * (t * freq - np.floor(t * freq + 0.5))) - 1
        elif waveform == "sawtooth":
            return 2 * (t * freq - np.floor(t * freq + 0.5))
        elif waveform == "square":
            return np.sign(np.sin(2 * np.pi * freq * t))
        return np.sin(2 * np.pi * freq * t)

    def update_data(self, frame_data):
        """Обновление данных из видео-анализатора."""
        with self.lock:
            self.current_frame_data = frame_data

    def stop(self):
        """Остановка генератора."""
        self.running = False
        if self.stream:
            self.stream.stop()
            self.stream.close()