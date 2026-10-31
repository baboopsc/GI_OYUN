# -*- coding: utf-8 -*-
"""
MediaPipe Hands motoru: 21 eklem noktası (landmark) çıkarır, kural tabanlı sınıflandırma yapar.
Eski `mp.solutions.hands` API'si varsa onu, yoksa yeni Tasks API'sini (HandLandmarker) kullanır.
"""
import os
import time
import urllib.request

import cv2
import numpy as np

from .gestures import (EngineResult, fingers_from_landmarks, classify, HAND_CONNECTIONS,
                       FINGER_NAMES, GESTURE_TR)

MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
             "hand_landmarker/float16/1/hand_landmarker.task")
MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "models", "hand_landmarker.task")


def _ensure_model():
    if not os.path.exists(MODEL_PATH):
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        print("[MediaPipe] El modeli indiriliyor (ilk çalıştırmada bir kere)...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    return MODEL_PATH


class MediaPipeEngine:
    name = "MediaPipe (21 eklem noktası)"

    def __init__(self):
        import mediapipe as mp
        self.mp = mp
        self.api = None
        self._last_ts = 0
        try:
            self.hands = mp.solutions.hands.Hands(
                static_image_mode=False, max_num_hands=1, model_complexity=0,
                min_detection_confidence=0.6, min_tracking_confidence=0.5)
            self.api = "solutions"
        except Exception:   # yeni sürümlerde mp.solutions yok -> Tasks API
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision
            with open(_ensure_model(), "rb") as f:
                buf = f.read()
            opts = vision.HandLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_buffer=buf),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=1,
                min_hand_detection_confidence=0.6,
                min_hand_presence_confidence=0.5,
                min_tracking_confidence=0.5)
            self.landmarker = vision.HandLandmarker.create_from_options(opts)
            self.api = "tasks"

    def _landmarks(self, rgb):
        if self.api == "solutions":
            rgb.flags.writeable = False
            res = self.hands.process(rgb)
            if res.multi_hand_landmarks:
                return [(p.x, p.y) for p in res.multi_hand_landmarks[0].landmark]
            return None
        ts = max(self._last_ts + 1, int(time.perf_counter() * 1000))
        self._last_ts = ts
        img = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb)
        res = self.landmarker.detect_for_video(img, ts)
        if res.hand_landmarks:
            return [(p.x, p.y) for p in res.hand_landmarks[0]]
        return None

    def process(self, bgr):
        h, w = bgr.shape[:2]
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        lm = self._landmarks(rgb)
        overlay = bgr.copy()
        debug = np.zeros((h, w, 3), np.uint8)
        r = EngineResult(overlay=overlay, debug=debug)
        if lm is None:
            r.info = ["El bulunamadı"]
            cv2.putText(debug, "El yok", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (80, 80, 255), 2)
            return r

        states = fingers_from_landmarks(lm)
        r.present = True
        r.gesture = classify(states)
        r.fingers = sum(states)
        r.palm = ((lm[0][0] + lm[5][0] + lm[9][0] + lm[17][0]) / 4,
                  (lm[0][1] + lm[5][1] + lm[9][1] + lm[17][1]) / 4)
        r.tip = lm[8]

        pts = [(int(x * w), int(y * h)) for x, y in lm]
        # Kamera üstüne iskelet
        for a, b in HAND_CONNECTIONS:
            cv2.line(overlay, pts[a], pts[b], (255, 255, 255), 2, cv2.LINE_AA)
        tips = (4, 8, 12, 16, 20)
        for i, p in enumerate(pts):
            col = (0, 200, 255) if i in tips else (255, 120, 60)
            cv2.circle(overlay, p, 5 if i in tips else 3, col, -1, cv2.LINE_AA)
        cx, cy = int(r.palm[0] * w), int(r.palm[1] * h)
        cv2.circle(overlay, (cx, cy), 9, (0, 255, 0), 2, cv2.LINE_AA)

        # Debug: siyah zemin üzerinde iskelet + parmak durumları
        for a, b in HAND_CONNECTIONS:
            cv2.line(debug, pts[a], pts[b], (90, 220, 90), 2, cv2.LINE_AA)
        for i, t in enumerate(tips):
            col = (60, 255, 60) if states[i] else (60, 60, 255)
            cv2.circle(debug, pts[t], 9, col, -1, cv2.LINE_AA)
        y = 30
        for name, s in zip(FINGER_NAMES, states):
            cv2.putText(debug, f"{_ascii(name)}: {'ACIK' if s else 'kapali'}", (12, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (60, 255, 60) if s else (90, 90, 255), 2)
            y += 26
        r.info = [f"Parmak: {r.fingers}", f"Ham işaret: {GESTURE_TR[r.gesture]}"]
        return r


def _ascii(s):
    """OpenCV putText Türkçe karakter çizemez."""
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    return s.translate(tr)
