# -*- coding: utf-8 -*-
"""
Görüntü işleme ayrı bir thread'de çalışır; oyun 60 FPS akarken kamera + tanıma kendi hızında döner.
Oyun her karede en son HandState'i okur (kilitli paylaşım).
"""
import os
import threading
import time
from dataclasses import dataclass

import cv2

from config import CAM_W, CAM_H, PREVIEW_W, PREVIEW_H, GESTURE_WINDOW, GESTURE_MIN_VOTES
from .gestures import VoteFilter, NONE, GESTURE_TR
from .classic_engine import ClassicEngine


@dataclass
class HandState:
    cam_ok: bool = True
    ready: bool = False
    status: str = "Kamera açılıyor..."
    present: bool = False
    gesture: str = NONE          # filtrelenmiş (kararlı) işaret
    raw_gesture: str = NONE
    fingers: int = 0             # filtrelenmiş parmak sayısı
    palm: tuple = None           # normalize
    tip: tuple = None            # normalize
    engine: str = ""
    proc_ms: float = 0.0
    cam_fps: float = 0.0
    seq: int = 0
    preview: bytes = None        # RGB, PREVIEW_W x PREVIEW_H
    debug: bytes = None          # RGB, PREVIEW_W x PREVIEW_H
    big_preview: bytes = None    # RGB, 2x boyut (debug ekranı için)
    big_debug: bytes = None
    info: tuple = ()
    classic: bool = False        # klasik motorda nişan bölgesi ROI kutusudur


class VisionWorker(threading.Thread):
    def __init__(self, cam_index=0):
        super().__init__(daemon=True)
        self.cam_index = cam_index
        self.lock = threading.Lock()
        self.state = HandState()
        self.running = True
        self.mp_engine = None
        self.mp_error = None
        self.classic = ClassicEngine()
        self.engine_key = "mediapipe"
        self._toggle = False
        self._calib = False
        self.want_big = False
        self.gfilter = VoteFilter(GESTURE_WINDOW, GESTURE_MIN_VOTES, NONE)
        self.cfilter = VoteFilter(GESTURE_WINDOW, GESTURE_MIN_VOTES, 0)

    # ---- oyundan çağrılanlar ----
    def get_state(self):
        with self.lock:
            return self.state

    def toggle_engine(self):
        self._toggle = True

    def calibrate(self):
        self._calib = True

    def stop(self):
        self.running = False

    # ---- iç ----
    def _set(self, st):
        with self.lock:
            self.state = st

    def _open_camera(self):
        backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY] if os.name == "nt" else [cv2.CAP_ANY]
        for b in backends:
            cap = cv2.VideoCapture(self.cam_index, b)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_W)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_H)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                ok, _ = cap.read()
                if ok:
                    return cap
            cap.release()
        return None

    def run(self):
        self._set(HandState(status="El tanıma modeli yükleniyor..."))
        try:
            from .mediapipe_engine import MediaPipeEngine
            self.mp_engine = MediaPipeEngine()
        except Exception as e:  # mediapipe kurulu değilse klasik motorla devam
            self.mp_error = f"{type(e).__name__}: {e}"
            print("[Uyarı] MediaPipe açılamadı, klasik motor kullanılacak ->", self.mp_error)
            self.engine_key = "classic"

        self._set(HandState(status="Kamera açılıyor..."))
        cap = self._open_camera()
        if cap is None:
            self._set(HandState(cam_ok=False, status="Kamera açılamadı! Fare modunda oynayabilirsin (M)."))
            return

        seq, fails = 0, 0
        fps_t, fps_n, cam_fps = time.perf_counter(), 0, 0.0
        while self.running:
            ok, frame = cap.read()
            if not ok:
                fails += 1
                if fails > 90:
                    self._set(HandState(cam_ok=False, status="Kameradan görüntü gelmiyor."))
                time.sleep(0.01)
                continue
            fails = 0
            frame = cv2.flip(frame, 1)   # ayna görüntü: elini sağa götürünce imleç de sağa gider
            if frame.shape[1] != CAM_W:
                frame = cv2.resize(frame, (CAM_W, CAM_H))

            if self._toggle:
                self._toggle = False
                if self.mp_engine is not None:
                    self.engine_key = "classic" if self.engine_key == "mediapipe" else "mediapipe"
                    self.gfilter.reset(NONE)
                    self.cfilter.reset(0)
            if self._calib:
                self._calib = False
                self.classic.calibrate(frame)

            t0 = time.perf_counter()
            eng = self.mp_engine if self.engine_key == "mediapipe" else self.classic
            try:
                r = eng.process(frame)
            except Exception as e:
                print("[Hata] işleme:", e)
                continue
            proc_ms = (time.perf_counter() - t0) * 1000

            gesture = self.gfilter.push(r.gesture if r.present else NONE)
            fingers = self.cfilter.push(r.fingers if r.present else 0)

            fps_n += 1
            now = time.perf_counter()
            if now - fps_t >= 0.5:
                cam_fps = fps_n / (now - fps_t)
                fps_t, fps_n = now, 0

            prev = cv2.cvtColor(cv2.resize(r.overlay, (PREVIEW_W, PREVIEW_H)), cv2.COLOR_BGR2RGB)
            dbg = cv2.cvtColor(cv2.resize(r.debug, (PREVIEW_W, PREVIEW_H)), cv2.COLOR_BGR2RGB)
            big_p = big_d = None
            if self.want_big:
                big_p = cv2.cvtColor(cv2.resize(r.overlay, (PREVIEW_W * 2, PREVIEW_H * 2)), cv2.COLOR_BGR2RGB).tobytes()
                big_d = cv2.cvtColor(cv2.resize(r.debug, (PREVIEW_W * 2, PREVIEW_H * 2)), cv2.COLOR_BGR2RGB).tobytes()
            seq += 1
            info = list(r.info) + [f"Kararli isaret: {GESTURE_TR[gesture]}"]
            self._set(HandState(
                cam_ok=True, ready=True, status="", present=r.present and gesture != NONE,
                gesture=gesture, raw_gesture=r.gesture, fingers=fingers,
                palm=r.palm, tip=r.tip, engine=eng.name, proc_ms=proc_ms, cam_fps=cam_fps,
                seq=seq, preview=prev.tobytes(), debug=dbg.tobytes(),
                big_preview=big_p, big_debug=big_d, info=tuple(info),
                classic=self.engine_key == "classic"))
        cap.release()
