# -*- coding: utf-8 -*-
"""
KLASİK GÖRÜNTÜ İŞLEME MOTORU (derin öğrenme yok)

Boru hattı:
 1) ROI (ilgi bölgesi) seçimi
 2) Gauss bulanıklaştırma (gürültü azaltma)
 3) Ten rengi segmentasyonu:
      - varsayılan: YCrCb uzayında eşikleme
      - kalibrasyon sonrası: HSV histogram geri izdüşümü (back projection)
 4) Haar Cascade ile yüz tespiti -> yüz bölgesi maskeden silinir
 5) Morfolojik açma / kapama (gürültü + delik temizleme)
 6) En büyük kontur = el
 7) Konveks gövde (convex hull) + konvekslik kusurları (convexity defects)
 8) Kosinüs teoremi ile parmak arası açı -> açı < eşik ise parmak boşluğu
 9) Parmak sayısı = boşluk + 1 (boşluk yoksa uç noktası / eşdeğer yarıçap oranı ile 0 / 1 ayrımı)
"""
import math

import cv2
import numpy as np

from config import (YCRCB_LOW, YCRCB_HIGH, CLASSIC_ROI, CLASSIC_MIN_AREA,
                    DEFECT_MAX_ANGLE, DEFECT_MIN_DEPTH)
from .gestures import EngineResult, gesture_from_count, GESTURE_TR


class ClassicEngine:
    name = "Klasik (Ten rengi + Konveks gövde)"

    def __init__(self):
        self.kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        self.hist = None
        self.faces = []
        self.frame_i = 0
        try:
            path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self.face = cv2.CascadeClassifier(path)
            if self.face.empty():
                self.face = None
        except Exception:
            self.face = None

    # ---------- yardımcılar ----------
    @staticmethod
    def _roi_px(w, h):
        x0, y0, x1, y1 = CLASSIC_ROI
        return int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)

    def calibration_box(self, w, h):
        x0, y0, x1, y1 = self._roi_px(w, h)
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        s = int(min(x1 - x0, y1 - y0) * 0.18)
        return cx - s, cy - s, cx + s, cy + s

    def calibrate(self, bgr):
        """ROI ortasındaki kareden ten rengi histogramı çıkar (elini kutuya koyup C'ye bas)."""
        h, w = bgr.shape[:2]
        x0, y0, x1, y1 = self.calibration_box(w, h)
        hsv = cv2.cvtColor(bgr[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [30, 32], [0, 180, 0, 256])
        cv2.normalize(hist, hist, 0, 255, cv2.NORM_MINMAX)
        self.hist = hist

    def reset_calibration(self):
        self.hist = None

    # ---------- ana işlem ----------
    def process(self, bgr):
        self.frame_i += 1
        h, w = bgr.shape[:2]
        x0, y0, x1, y1 = self._roi_px(w, h)
        overlay = bgr.copy()
        roi = bgr[y0:y1, x0:x1]
        rh, rw = roi.shape[:2]

        # 2) Gauss bulanıklaştırma
        blur = cv2.GaussianBlur(roi, (7, 7), 0)

        # 3) Ten rengi segmentasyonu
        if self.hist is not None:
            hsv = cv2.cvtColor(blur, cv2.COLOR_BGR2HSV)
            bp = cv2.calcBackProject([hsv], [0, 1], self.hist, [0, 180, 0, 256], 1)
            disc = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
            bp = cv2.filter2D(bp, -1, disc)
            _, mask = cv2.threshold(bp, 50, 255, cv2.THRESH_BINARY)
            method = "HSV geri izdusum (kalibre)"
        else:
            ycc = cv2.cvtColor(blur, cv2.COLOR_BGR2YCrCb)
            mask = cv2.inRange(ycc, np.array(YCRCB_LOW, np.uint8), np.array(YCRCB_HIGH, np.uint8))
            method = "YCrCb esikleme"

        # 4) Yüzü maskeden çıkar (her 4 karede bir tespit, arada son sonuç kullanılır)
        if self.face is not None and self.frame_i % 4 == 1:
            small = cv2.cvtColor(cv2.resize(bgr, (w // 2, h // 2)), cv2.COLOR_BGR2GRAY)
            self.faces = [(fx * 2, fy * 2, fw * 2, fh * 2)
                          for fx, fy, fw, fh in self.face.detectMultiScale(small, 1.2, 5, minSize=(40, 40))]
        for fx, fy, fw, fh in self.faces:
            pad = int(fw * 0.25)
            ax0, ay0 = max(fx - pad, x0), max(fy - pad, y0)
            ax1, ay1 = min(fx + fw + pad, x1), min(fy + int(fh * 1.6), y1)   # boyun dahil
            if ax1 > ax0 and ay1 > ay0:
                mask[ay0 - y0:ay1 - y0, ax0 - x0:ax1 - x0] = 0
            cv2.rectangle(overlay, (fx, fy), (fx + fw, fy + fh), (0, 0, 255), 1)

        # 5) Morfoloji
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self.kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self.kernel, iterations=2)
        mask = cv2.dilate(mask, self.kernel, iterations=1)

        dbg = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        r = EngineResult(overlay=overlay)
        cv2.rectangle(overlay, (x0, y0), (x1, y1), (0, 255, 255), 2)
        if self.hist is None:
            bx0, by0, bx1, by1 = self.calibration_box(w, h)
            cv2.rectangle(overlay, (bx0, by0), (bx1, by1), (255, 0, 255), 1)

        # 6) En büyük kontur
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnt = max(contours, key=cv2.contourArea) if contours else None
        if cnt is None or cv2.contourArea(cnt) < CLASSIC_MIN_AREA * rw * rh:
            r.info = [method, "El bulunamadi"]
            r.debug = self._finish_debug(dbg, w, h, r.info)
            return r

        area = cv2.contourArea(cnt)
        bx, by, bw, bh = cv2.boundingRect(cnt)
        M = cv2.moments(cnt)
        cx, cy = M["m10"] / (M["m00"] + 1e-6), M["m01"] / (M["m00"] + 1e-6)

        # 7) Konveks gövde + kusurlar
        hull_pts = cv2.convexHull(cnt)
        gaps = []
        try:
            hull_idx = cv2.convexHull(cnt, returnPoints=False)
            defects = cv2.convexityDefects(cnt, hull_idx)
        except cv2.error:
            defects = None
        pts = cnt.reshape(-1, 2)
        if defects is not None:
            for s, e, f, depth in defects.reshape(-1, 4):
                start, end, far = tuple(int(v) for v in pts[s]), tuple(int(v) for v in pts[e]), tuple(int(v) for v in pts[f])
                a = math.dist(end, start)
                b = math.dist(far, start)
                c = math.dist(end, far)
                if b * c == 0:
                    continue
                # 8) Kosinüs teoremi: parmaklar arası açı
                ang = math.degrees(math.acos(max(-1, min(1, (b * b + c * c - a * a) / (2 * b * c)))))
                if ang < DEFECT_MAX_ANGLE and depth / 256.0 > DEFECT_MIN_DEPTH * bh and far[1] < cy + bh * 0.25:
                    gaps.append((start, end, far))

        # 9) Parmak sayısı
        top = tuple(int(v) for v in pts[pts[:, 1].argmin()])
        eq_r = math.sqrt(area / math.pi)
        if gaps:
            fingers = min(len(gaps) + 1, 5)
        else:
            fingers = 1 if math.dist(top, (cx, cy)) > 1.75 * eq_r else 0

        r.present = True
        r.fingers = fingers
        r.gesture = gesture_from_count(fingers)
        r.palm = ((cx + x0) / w, (cy + y0) / h)
        r.tip = ((top[0] + x0) / w, (top[1] + y0) / h)

        # Çizimler (debug + kamera)
        cv2.drawContours(dbg, [cnt], -1, (0, 255, 0), 2)
        cv2.drawContours(dbg, [hull_pts], -1, (255, 160, 0), 2)
        for s, e, f in gaps:
            cv2.circle(dbg, f, 7, (0, 0, 255), -1)
            cv2.line(dbg, s, f, (0, 200, 255), 1)
            cv2.line(dbg, e, f, (0, 200, 255), 1)
        cv2.circle(dbg, (int(cx), int(cy)), 6, (255, 0, 255), -1)
        cv2.circle(dbg, top, 6, (0, 255, 255), -1)

        off = np.array([[x0, y0]])
        cv2.drawContours(overlay, [cnt + off], -1, (0, 255, 0), 2)
        cv2.drawContours(overlay, [hull_pts + off], -1, (255, 160, 0), 1)
        for s, e, f in gaps:
            cv2.circle(overlay, (f[0] + x0, f[1] + y0), 5, (0, 0, 255), -1)

        r.info = [method, f"Kusur(bosluk): {len(gaps)}", f"Parmak: {fingers}",
                  f"Ham isaret: {GESTURE_TR[r.gesture]}"]
        r.debug = self._finish_debug(dbg, w, h, r.info)
        return r

    @staticmethod
    def _finish_debug(dbg_roi, w, h, info):
        out = np.zeros((h, w, 3), np.uint8)
        rh, rw = dbg_roi.shape[:2]
        s = min(w / rw, h / rh)
        res = cv2.resize(dbg_roi, (int(rw * s), int(rh * s)))
        oy, ox = (h - res.shape[0]) // 2, (w - res.shape[1]) // 2
        out[oy:oy + res.shape[0], ox:ox + res.shape[1]] = res
        y = 28
        tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
        for line in info:
            cv2.putText(out, line.translate(tr), (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4)
            cv2.putText(out, line.translate(tr), (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            y += 24
        return out
