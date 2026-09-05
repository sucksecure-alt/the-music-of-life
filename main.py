"""PANOPTICON SYMPHONY v1.1 — генеративный эмбиент из публичных видеопотоков."""

import sys, os, json, time, random, wave, socket, traceback
import urllib.request
from urllib.parse import urlparse
import ssl
import numpy as np
import cv2

_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode = ssl.CERT_NONE

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QComboBox, QSlider, QFrame,
    QProgressBar, QSizePolicy, QFileDialog, QInputDialog)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QColor, QPainter, QPen

from video_analyzer import VideoAnalyzer, FrameData
from music_generator import MusicGenerator

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "panopticon_crash.log")

def log(*a):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.ctime() + " " + " ".join(str(x) for x in a) + "\n")
    except Exception:
        pass

def _excepthook(t, v, tb):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.ctime() + "\n")
            traceback.print_exception(t, v, tb, file=f)
    except Exception:
        pass
sys.excepthook = _excepthook


class CameraWorker(QThread):
    frame_ready = pyqtSignal(np.ndarray)
    status_changed = pyqtSignal(str)
    gave_up = pyqtSignal()

    def __init__(self, url, max_tries=1, timeout=5):
        super().__init__()
        self.url = url
        self.max_tries = max_tries
        self.timeout = timeout
        self._running = True

    def run(self):
        try:
            if self.url.startswith("rtsp://"):
                self._run_cv2()
            else:
                self._run_mjpeg()
        except Exception as e:
            log("node:", self.url, e)
        if self._running:
            self.gave_up.emit()

    def _run_mjpeg(self):
        for tr in range(self.max_tries):
            if not self._running:
                return
            self.status_changed.emit("ЧИТАЮ ПОТОК...")
            try:
                req = urllib.request.Request(self.url, headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
                resp = urllib.request.urlopen(req, timeout=self.timeout, context=_SSL)
            except Exception as e:
                log("open:", self.url, e)
                time.sleep(0.4)
                continue
            buf = b""
            last_data = time.time()
            got_jpeg = False
            while self._running:
                try:
                    chunk = resp.read(65536)
                except (socket.timeout, TimeoutError, OSError):
                    if time.time() - last_data > 8:
                        break
                    continue
                except Exception:
                    break
                if not chunk:
                    break
                last_data = time.time()
                buf += chunk
                while True:
                    s = buf.find(b"\xff\xd8")
                    if s == -1:
                        buf = buf[-4:] if len(buf) > 4 else buf
                        break
                    e = buf.find(b"\xff\xd9", s)
                    if e == -1:
                        break
                    jpg = buf[s:e + 2]
                    buf = buf[e + 2:]
                    frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                    if frame is not None:
                        got_jpeg = True
                        self.frame_ready.emit(frame)
                if len(buf) > 16 * 1024 * 1024:
                    buf = buf[-2 * 1024 * 1024:]
                if got_jpeg and time.time() - last_data > 10:
                    break
            try:
                resp.close()
            except Exception:
                pass

    def _run_cv2(self):
        self.status_changed.emit("ЧИТАЮ ПОТОК...")
        try:
            cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 8000)
            cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 8000)
        except Exception:
            return
        if not cap.isOpened():
            try: cap.release()
            except Exception: pass
            return
        fail = 0
        while self._running:
            try:
                ret, frame = cap.read()
            except Exception:
                break
            if not ret:
                fail += 1
                if fail > 60:
                    break
                time.sleep(0.1)
                continue
            fail = 0
            self.frame_ready.emit(frame)
            time.sleep(0.03)
        try: cap.release()
        except Exception: pass

    def stop(self):
        self._running = False


class WaveformWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.vals = [0.0] * 100
        self.setMinimumHeight(50)
        self.setMaximumHeight(60)

    def push(self, v):
        self.vals.append(max(0.0, min(1.0, v)))
        if len(self.vals) > 100:
            self.vals.pop(0)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor(13, 13, 13))
        pen = QPen(QColor(255, 50, 50)); pen.setWidth(2); p.setPen(pen)
        s = w / max(len(self.vals) - 1, 1); m = h / 2
        for i in range(1, len(self.vals)):
            p.drawLine(int((i-1)*s), int(m - self.vals[i-1]*m*0.9),
                       int(i*s), int(m - self.vals[i]*m*0.9))
        p.setPen(QPen(QColor(255, 50, 50, 60)))
        for i in range(1, len(self.vals)):
            p.drawLine(int((i-1)*s), int(m + self.vals[i-1]*m*0.5),
                       int(i*s), int(m + self.vals[i]*m*0.5))
        p.end()


class PanopticonWindow(QMainWindow):
    FLAGS = {"JP":"\U0001f1ef\U0001f1f5","US":"\U0001f1fa\U0001f1f8","DE":"\U0001f1e9\U0001f1ea",
             "FI":"\U0001f1eb\U0001f1ee","SE":"\U0001f1f8\U0001f1ea","NO":"\U0001f1f3\U0001f1f4",
             "CH":"\U0001f1e8\U0001f1ed","CZ":"\U0001f1e8\U0001f1ff","NL":"\U0001f1f3\U0001f1f1",
             "AT":"\U0001f1e6\U0001f1f9"}

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ПАНОПТИКОН СИМФОНИЯ")
        self.setMinimumSize(1200, 800)
        self._closing = False
        self.cameras = []
        self.worker = None
        self.graveyard = []
        self.analyzer = VideoAnalyzer()
        self.music = MusicGenerator()
        self.current_data = FrameData()
        self._origin = 0
        self._attempt = 0
        self._idx = 0
        self._live_shown = False
        self._fps = 0.0
        self._res = ""
        self._last_t = 0.0

        cfg = os.path.join(os.path.dirname(os.path.abspath(__file__)), "camera_sources.json")
        try:
            with open(cfg, "r", encoding="utf-8") as fj:
                self.cameras = json.load(fj).get("cameras", [])
        except Exception as e:
            log("camera list:", e)

        self._build_ui()
        self._apply_style()
        self.timer = QTimer()
        self.timer.timeout.connect(self._tick)
        self.timer.start(100)
        if self.cameras:
            self._connect(0)

    def _build_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        root = QVBoxLayout(central); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        top = QFrame(objectName="topBar"); top.setFixedHeight(50)
        tl = QHBoxLayout(top); tl.setContentsMargins(20,0,20,0)
        tl.addWidget(QLabel("◉ PANOPTICON SYMPHONY", objectName="logo"))
        tl.addStretch()
        self.node_label = QLabel("---", objectName="node")
        tl.addWidget(self.node_label)
        self.status_label = QLabel("ЗАПУСК...", objectName="status")
        tl.addWidget(self.status_label)
        root.addWidget(top)

        ct = QHBoxLayout(); ct.setContentsMargins(12,12,12,12); ct.setSpacing(12)

        vf = QFrame(objectName="videoContainer"); vl = QVBoxLayout(vf)
        vl.setContentsMargins(2,2,2,2)
        self.video_label = QLabel("НЕТ СИГНАЛА", objectName="videoFeed")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setMinimumSize(640, 400)
        self.video_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        vl.addWidget(self.video_label)
        self.desc_label = QLabel("", objectName="description")
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.desc_label.setWordWrap(True)
        vl.addWidget(self.desc_label)
        ct.addWidget(vf, stretch=3)

        rp = QVBoxLayout(); rp.setSpacing(10)

        sf = QFrame(objectName="panel"); sl = QVBoxLayout(sf)
        sl.addWidget(QLabel("ВЫБОР УЗЛА", objectName="panelTitle"))
        self.cc = QComboBox()
        for cam in self.cameras:
            fl = self.FLAGS.get(cam.get("country",""), "\U0001f4f9")
            self.cc.addItem(f"{fl} {cam['city']} — {cam['name']}")
        self.cc.currentIndexChanged.connect(self._on_cam)
        sl.addWidget(self.cc)
        br = QHBoxLayout()
        b1 = QPushButton("\U0001f3b2 СЛУЧАЙНО"); b1.clicked.connect(self._random); br.addWidget(b1)
        b2 = QPushButton("▶ ДАЛЕЕ"); b2.clicked.connect(self._next); br.addWidget(b2)
        sl.addLayout(br)
        br2 = QHBoxLayout()
        b3 = QPushButton("＋ ДОБАВИТЬ"); b3.clicked.connect(self._add_cam); br2.addWidget(b3)
        b4 = QPushButton("⇪ ИМПОРТ СПИСКА"); b4.clicked.connect(self._import_cams); br2.addWidget(b4)
        sl.addLayout(br2)
        rp.addWidget(sf)

        pf = QFrame(objectName="panel"); pl = QVBoxLayout(pf)
        pl.addWidget(QLabel("АНАЛИЗ СИГНАЛА", objectName="panelTitle"))
        self.pw = {}
        for k, lb, co in [("movement","ДВИЖЕНИЕ","#ff5050"),("brightness","СВЕТ","#ffdc64"),
                          ("complexity","ПЛОТНОСТЬ","#64c8ff"),("color","СПЕКТР","#b4ffb4")]:
            row = QHBoxLayout()
            nl = QLabel(lb, objectName="paramName"); nl.setFixedWidth(90); row.addWidget(nl)
            bar = QProgressBar(); bar.setRange(0,100); bar.setValue(0)
            bar.setTextVisible(False); bar.setFixedHeight(14)
            bar.setStyleSheet(f"QProgressBar{{background:#1a1a1a;border:1px solid #333;border-radius:3px;}}"
                              f"QProgressBar::chunk{{background:{co};border-radius:2px;}}")
            row.addWidget(bar)
            vv = QLabel("0.00", objectName="paramVal"); vv.setFixedWidth(45)
            vv.setAlignment(Qt.AlignmentFlag.AlignRight); row.addWidget(vv)
            pl.addLayout(row); self.pw[k] = (bar, vv)
        self.ml = QLabel("НАСТРОЕНИЕ: ---", objectName="mood")
        self.ml.setAlignment(Qt.AlignmentFlag.AlignCenter); pl.addWidget(self.ml)
        self.scl = QLabel("ЛАД: ---", objectName="scale")
        self.scl.setAlignment(Qt.AlignmentFlag.AlignCenter); pl.addWidget(self.scl)
        rp.addWidget(pf)

        wf = QFrame(objectName="panel"); wl = QVBoxLayout(wf)
        wl.addWidget(QLabel("ВОЛНА", objectName="panelTitle"))
        self.wv = WaveformWidget(); wl.addWidget(self.wv); rp.addWidget(wf)

        vlf = QFrame(objectName="panel"); vll = QVBoxLayout(vlf)
        vll.addWidget(QLabel("ГРОМКОСТЬ", objectName="panelTitle"))
        self.vs = QSlider(Qt.Orientation.Horizontal); self.vs.setRange(0,100); self.vs.setValue(85)
        self.vs.valueChanged.connect(lambda v: self.music.set_volume(v/100.0))
        vll.addWidget(self.vs); rp.addWidget(vlf)

        af = QFrame(objectName="panel"); al = QVBoxLayout(af); abr = QHBoxLayout()
        self.bm = QPushButton("\U0001f50a ЗВУК ВКЛ"); self.bm.setCheckable(True)
        self.bm.clicked.connect(self._mute); abr.addWidget(self.bm)
        self.brec = QPushButton("⏺ ЗАПИСЬ"); self.brec.setCheckable(True)
        self.brec.clicked.connect(self._rec); abr.addWidget(self.brec)
        al.addLayout(abr); rp.addWidget(af); rp.addStretch()

        rw = QWidget(); rw.setLayout(rp); rw.setFixedWidth(340); ct.addWidget(rw)
        root.addLayout(ct)

        bot = QFrame(objectName="bottomBar"); bot.setFixedHeight(30)
        bl = QHBoxLayout(bot); bl.setContentsMargins(20,0,20,0)
        self.bt = QLabel("panopticon symphony v1.1 · генеративный эмбиент из публичных видеопотоков",
                         objectName="bottomText")
        bl.addWidget(self.bt); bl.addStretch()
        bl.addWidget(QLabel(f"узлов в базе: {len(self.cameras)}", objectName="bottomText"))
        root.addWidget(bot)

    def _apply_style(self):
        self.setStyleSheet(
            "QMainWindow{background:#0a0a0a;}"
            "QWidget{color:#ccc;font-family:Menlo;}"
            "#topBar{background:#111;border-bottom:1px solid #222;}"
            "#logo{color:#ff3333;font-size:16px;font-weight:bold;}"
            "#status{color:#0f0;font-size:11px;}"
            "#node{color:#666;font-size:10px;padding-right:14px;}"
            "#videoContainer{background:#000;border:1px solid #1a1a1a;border-radius:6px;}"
            "#videoFeed{color:#333;font-size:24px;font-weight:bold;}"
            "#description{color:#555;font-size:10px;padding:4px;}"
            "#panel{background:#111;border:1px solid #1a1a1a;border-radius:6px;padding:8px;}"
            "#panelTitle{color:#ff3333;font-size:9px;font-weight:bold;letter-spacing:3px;}"
            "#paramName{color:#888;font-size:10px;}#paramVal{color:#fff;font-size:10px;}"
            "#mood{color:#ff9944;font-size:11px;padding-top:6px;}#scale{color:#888;font-size:9px;}"
            "QComboBox{background:#1a1a1a;color:#ccc;border:1px solid #333;border-radius:4px;padding:6px;font-size:11px;}"
            "QComboBox::drop-down{border:none;}"
            "QComboBox QAbstractItemView{background:#1a1a1a;color:#ccc;selection-background-color:#333;}"
            "QPushButton{background:#1a1a1a;color:#ff4444;border:1px solid #333;border-radius:4px;padding:8px 12px;font-size:11px;font-weight:bold;}"
            "QPushButton:hover{background:#252525;border-color:#ff4444;}"
            "QPushButton:checked{background:#ff4444;color:#000;}"
            "QSlider::groove:horizontal{height:6px;background:#1a1a1a;border-radius:3px;}"
            "QSlider::handle:horizontal{width:14px;height:14px;margin:-4px 0;background:#ff4444;border-radius:7px;}"
            "QSlider::sub-page:horizontal{background:#ff4444;border-radius:3px;}"
            "#bottomBar{background:#0d0d0d;border-top:1px solid #1a1a1a;}"
            "#bottomText{color:#444;font-size:9px;}")

    # ── камеры ──
    def _kill_worker(self):
        if self.worker is not None:
            self.worker._running = False
            self.graveyard.append(self.worker)
            self.worker = None

    def _connect(self, idx, tries=1):
        try:
            self._kill_worker()
            if not self.cameras or idx < 0 or idx >= len(self.cameras):
                return
            self._idx = idx
            self._live_shown = False
            self._fps = 0.0
            self._res = ""
            cam = self.cameras[idx]
            self.analyzer.reset()
            host = urlparse(cam["url"]).hostname or ""
            self.desc_label.setText(f"{cam.get('description','')} · {host}")
            self.video_label.clear()
            self.video_label.setText("ПОИСК СИГНАЛА...")
            self.status_label.setText("ПОДКЛЮЧЕНИЕ...")
            self.status_label.setStyleSheet("color:#ff9900;")
            self.worker = CameraWorker(cam["url"], max_tries=tries)
            self.worker.frame_ready.connect(self._on_frame)
            self.worker.status_changed.connect(self._on_status)
            self.worker.gave_up.connect(self._on_gave_up)
            self.worker.start()
        except Exception as e:
            log("connect:", e)

    def _on_cam(self, idx):
        if 0 <= idx < len(self.cameras):
            self._origin = idx
            self._attempt = 1
            self._connect(idx, tries=2)

    def _on_gave_up(self):
        try:
            if self._closing or self.sender() is not self.worker:
                return
            n = len(self.cameras)
            if n == 0:
                self._all_dead(); return
            if self._attempt < n:
                idx = (self._origin + self._attempt) % n
                self._attempt += 1
                self.cc.blockSignals(True)
                self.cc.setCurrentIndex(idx)
                self.cc.blockSignals(False)
                self._connect(idx, tries=1)
            else:
                self._all_dead()
        except Exception as e:
            log("gave_up:", e)

    def _all_dead(self):
        self.status_label.setText("ВСЕ УЗЛЫ НЕДОСТУПНЫ")
        self.status_label.setStyleSheet("color:#ff0000;")
        self.video_label.setText("СЕТЬ НЕ ПУСКАЕТ")
        self.desc_label.setText("ни один узел не ответил. 1) переключи vpn (вкл/выкл) и нажми ДАЛЕЕ. "
                                "2) запусти python3 netcheck.py в терминале — он покажет живые узлы. "
                                "3) добавь свои камеры (＋ / ⇪), например выгрузку из camover.")

    def _add_cam(self):
        url, ok = QInputDialog.getText(self, "ДОБАВИТЬ УЗЕЛ",
            "URL потока (mjpeg / rtsp):", text="http://")
        if ok and url.strip() and url.strip() != "http://":
            self.cameras.append({"city": "CUSTOM", "name": f"узел {len(self.cameras)+1}",
                                 "url": url.strip(), "country": "??",
                                 "description": "пользовательский узел"})
            self.cc.blockSignals(True)
            self.cc.addItem(f"\U0001f4f9 CUSTOM — узел {len(self.cameras)}")
            self.cc.setCurrentIndex(len(self.cameras) - 1)
            self.cc.blockSignals(False)
            self._origin = len(self.cameras) - 1
            self._attempt = 1
            self._connect(self._origin, tries=2)

    def _import_cams(self):
        path, _ = QFileDialog.getOpenFileName(self, "ИМПОРТ СПИСКА КАМЕР", "",
                                              "Text (*.txt *.json);;All (*)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            added = 0
            if path.endswith(".json"):
                for c in json.loads(content).get("cameras", []):
                    if c.get("url"):
                        self.cameras.append(c)
                        self.cc.addItem(f"\U0001f4f9 {c.get('city','?')} — {c.get('name','?')}")
                        added += 1
            else:
                for line in content.splitlines():
                    u = line.strip()
                    if u.startswith(("http://", "https://", "rtsp://")):
                        self.cameras.append({"city": "IMPORT", "name": f"узел {len(self.cameras)+1}",
                                             "url": u, "country": "??", "description": "импортированный узел"})
                        self.cc.addItem(f"\U0001f4f9 IMPORT — узел {len(self.cameras)}")
                        added += 1
            self.bt.setText(f"импортировано узлов: {added}")
        except Exception as e:
            self.bt.setText(f"ошибка импорта: {e}")

    def _random(self):
        if self.cameras:
            self.cc.setCurrentIndex(random.randint(0, len(self.cameras)-1))

    def _next(self):
        if self.cameras:
            self.cc.setCurrentIndex((self.cc.currentIndex()+1) % len(self.cameras))

    # ── кадры ──
    def _on_frame(self, frame):
        try:
            if self._closing or self.sender() is not self.worker:
                return
            now = time.time()
            if self._last_t > 0:
                dt = now - self._last_t
                if dt > 0:
                    self._fps = 0.9 * self._fps + 0.1 * (1.0 / dt)
            self._last_t = now

            d = self.analyzer.analyze(frame)
            self.current_data = d
            self.music.update(d)

            h, w, _ = frame.shape
            self._res = f"{w}×{h}"
            if not self._live_shown:
                self._live_shown = True
                self.status_label.setText("◉ В ЭФИРЕ")
                self.status_label.setStyleSheet("color:#00ff00;")

            rgb = np.ascontiguousarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            qimg = QImage(rgb.data, w, h, w*3, QImage.Format.Format_RGB888).copy()
            self.video_label.setPixmap(QPixmap.fromImage(
                qimg.scaled(self.video_label.size(),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)))
        except Exception as e:
            log("frame:", e)

    def _on_status(self, msg):
        try:
            self.status_label.setText(msg)
            if "НЕДОСТУПНЫ" in msg:
                self.status_label.setStyleSheet("color:#ff0000;")
            else:
                self.status_label.setStyleSheet("color:#ff9900;")
        except Exception:
            pass

    # ── кнопки ─
    def _mute(self):
        m = self.bm.isChecked()
        self.music.set_muted(m)
        self.bm.setText("\U0001f507 ТИШИНА" if m else "\U0001f50a ЗВУК ВКЛ")

    def _rec(self):
        if self.brec.isChecked():
            self.music.set_recording(True)
            self.brec.setText("⏹ СТОП")
            self.bt.setText("идёт запись симфонии...")
            self.bt.setStyleSheet("color:#ff4444;")
        else:
            self.music.set_recording(False)
            self.brec.setText("⏺ ЗАПИСЬ")
            self.bt.setText("panopticon symphony v1.1 · генеративный эмбиент из публичных видеопотоков")
            self.bt.setStyleSheet("color:#444;")
            arr = self.music.fetch_recording()
            if arr is not None and len(arr) > 0:
                path, _ = QFileDialog.getSaveFileName(self, "Сохранить симфонию",
                                                      "panopticon.wav", "WAV (*.wav)")
                if path:
                    try:
                        d16 = (np.clip(arr, -1, 1) * 32767).astype(np.int16)
                        with wave.open(path, "wb") as wf:
                            wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(44100)
                            wf.writeframes(d16.tobytes())
                        self.bt.setText(f"сохранено: {os.path.basename(path)}")
                    except Exception as e:
                        self.bt.setText(f"ошибка записи: {e}")

    # ── тик ──
    def _tick(self):
        try:
            self.graveyard = [w for w in self.graveyard if w.isRunning()]
            n = len(self.cameras)
            if self._live_shown:
                self.node_label.setText(f"УЗЕЛ {self._idx+1}/{n} · {self._res} · {self._fps:.0f} FPS")
            else:
                self.node_label.setText(f"УЗЕЛ {self._idx+1}/{n}")
            d = self.current_data
            for k, a in [("movement", d.movement), ("brightness", d.brightness), ("complexity", d.complexity)]:
                if k in self.pw:
                    self.pw[k][0].setValue(int(a*100)); self.pw[k][1].setText(f"{a:.2f}")
            if "color" in self.pw:
                r, g, b = d.color_rgb
                self.pw["color"][0].setValue(int((r+g+b)/3*100))
                self.pw["color"][1].setText({"warm":"тёпл","cool":"хол","nature":"прир","neutral":"нейт"}.get(d.dominant_color,"нейт"))
            if d.sudden_change: mood = "⚡ СБОЙ"
            elif d.is_night: mood = "\U0001f319 НОКТЮРН"
            elif d.movement > 0.3: mood = "\U0001f525 ПУЛЬС"
            elif d.movement < 0.05: mood = "\U0001f9ca ПОКОЙ"
            else: mood = "\U0001f30a ПОТОК"
            self.ml.setText(f"НАСТРОЕНИЕ: {mood}")
            sn = {"warm":"ПЕНТАТОНИКА МАЖ","cool":"ПЕНТАТОНИКА МИН","nature":"ДОРИЙСКИЙ","neutral":"ИОНИЙСКИЙ"}
            sc = sn.get(d.dominant_color, "ИОНИЙСКИЙ")
            if d.is_night: sc = "ЛОКРИЙСКИЙ"
            self.scl.setText(f"ЛАД: {sc}")
            self.wv.push(d.movement*2 + d.brightness*0.3)
        except Exception as e:
            log("tick:", e)

    def closeEvent(self, e):
        self._closing = True
        try:
            self.timer.stop()
            self._kill_worker()
            for w in self.graveyard:
                w.wait(1000)
            self.music.stop()
        except Exception:
            pass
        e.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Паноптикон Симфония")
    w = PanopticonWindow()
    w.show()
    sys.exit(app.exec())