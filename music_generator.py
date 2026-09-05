"""Голос Паноптикума. Звук живёт, только пока жив видеопоток."""

import time
import numpy as np
import sounddevice as sd
import threading


class MusicGenerator:
    SCALES = {"warm":[0,2,4,7,9],"cool":[0,3,5,7,10],
              "nature":[0,2,3,5,7,9,10],"neutral":[0,2,4,5,7,9,11]}
    NIGHT = [0,1,3,5,6,8,10]

    def __init__(self, sr=44100):
        self.sr = sr
        self.running = False
        self.muted = False
        self.recording = False
        self.rec_chunks = []
        self.stream = None
        self.lock = threading.Lock()
        self.data = None
        self.last_update = 0.0
        self.pp = [0.0]*6
        self.ap = 0.0
        self.astep = 0
        self.lp = 0.0
        self.bp = 0.0
        self.ad = 0.0
        self.vol = 0.85
        self._start()

    def _start(self):
        try:
            self.stream = sd.OutputStream(samplerate=self.sr, channels=2,
                dtype="float32", blocksize=2048, callback=self._cb, latency="high")
            self.stream.start()
            self.running = True
        except Exception as e:
            print("audio error:", e)

    def _cb(self, out, frames, ti, st):
        try:
            if self.muted or self.data is None:
                out[:] = 0
                return
            with self.lock:
                d = self.data

            # если кадры перестали приходить — звук затухает в тишину
            age = time.time() - self.last_update
            if age < 0.5:
                alive = 1.0
            else:
                alive = max(0.0, 1.0 - (age - 0.5) / 1.2)
            if alive <= 0.0:
                out[:] = 0
                return

            t = np.arange(frames, dtype=np.float64) / self.sr
            L = np.zeros(frames, dtype=np.float64)
            R = np.zeros(frames, dtype=np.float64)
            sc = self.NIGHT if d.is_night else self.SCALES.get(d.dominant_color, self.SCALES["neutral"])
            rm = 36 + int(d.brightness * 24)

            # пэд
            pv = 0.16 + d.stillness_duration * 0.025
            degs = [0,2,4] if len(sc) >= 5 else [0,1,2]
            for i, dg in enumerate(degs):
                n = rm + sc[dg % len(sc)]
                fr = 440.0 * (2.0 ** ((n-69)/12.0))
                det = 1.0 + np.sin(self.lp*0.3+i)*0.003
                w1 = np.sin(2*np.pi*fr*det*(t+self.pp[i]))
                w2 = np.sin(2*np.pi*fr*1.002*(t+self.pp[i]))
                pd = (w1+w2)*0.5*pv
                pn = 0.3 + 0.4*(i/max(len(degs)-1,1))
                L += pd*(1-pn); R += pd*pn
                self.pp[i] += frames/self.sr

            # бас
            bf = 440.0*(2.0**((rm-12-69)/12.0))
            bs = np.sin(2*np.pi*bf*(t+self.bp)) * (0.10+d.movement*0.06)
            L += bs; R += bs
            self.bp += frames/self.sr

            # арпеджио + хэт от движения
            if d.movement > 0.04:
                spn = max(int(self.sr/(2.0+d.movement*12.0)), 100)
                for i in range(frames):
                    if int((self.ap+i)/spn) > int((self.ap+i-1)/spn):
                        self.astep = (self.astep+1) % len(sc)
                an = rm+12+sc[self.astep % len(sc)]
                af = 440.0*(2.0**((an-69)/12.0))
                ae = np.exp(-t*(3.0+d.movement*8.0))
                av = min(d.movement*0.5, 0.22)
                aw = 2*np.abs(2*((t+self.ap/self.sr)*af % 1)-1)-1
                arp = aw*ae*av
                apn = 0.3+d.complexity*0.4
                L += arp*(1-apn); R += arp*apn
                hat = np.random.randn(frames)*np.exp(-t*30)*min(d.movement*0.18, 0.07)
                L += hat*0.6; R += hat
                self.ap += frames

            # акцент на резких событиях
            if d.sudden_change: self.ad = 1.0
            if self.ad > 0.01:
                acf = 440.0*(2.0**((rm+24-69)/12.0))
                ace = np.exp(-t*15.0)*self.ad
                L += np.sin(2*np.pi*acf*t)*ace*0.15
                R += np.random.randn(frames)*ace*0.05
                self.ad *= 0.85

            # шиммер от плотности сцены
            if d.complexity > 0.15:
                sf = 440.0*(2.0**((rm+19-69)/12.0))
                sh = np.sin(2*np.pi*sf*t)*d.complexity*0.05
                lm = np.sin(2*np.pi*0.5*(t+self.lp))*0.5+0.5
                L += sh*lm; R += sh*(1-lm)

            self.lp += frames/self.sr

            gain = 1.7 * self.vol * alive
            out[:,0] = np.tanh(L*gain).astype(np.float32)
            out[:,1] = np.tanh(R*gain).astype(np.float32)

            if self.recording:
                self.rec_chunks.append(np.stack([L*gain, R*gain], axis=1).astype(np.float32))
        except Exception:
            out[:] = 0

    def update(self, fd):
        with self.lock:
            self.data = fd
            self.last_update = time.time()

    def set_muted(self, m): self.muted = m
    def set_volume(self, v): self.vol = max(0.0, min(1.0, v))
    def set_recording(self, on): self.recording = on

    def fetch_recording(self):
        if not self.rec_chunks: return None
        arr = np.concatenate(self.rec_chunks)
        self.rec_chunks = []
        return arr

    def stop(self):
        self.running = False
        if self.stream:
            try: self.stream.stop(); self.stream.close()
            except Exception: pass