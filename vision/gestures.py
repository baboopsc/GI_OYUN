# -*- coding: utf-8 -*-
"""
El işareti sınıflandırma + zamansal filtreler.

- fingers_from_landmarks : 21 MediaPipe eklem noktasından hangi parmakların açık olduğunu bulur
                           (döndürmeden bağımsız, mesafe tabanlı kural)
- classify               : açık parmak kombinasyonundan işaret etiketi üretir
- VoteFilter             : son N karede çoğunluk oylaması (yanlış algılamayı bastırır)
- OneEuro2D              : One Euro filtresi (Casiez 2012) ile imleç titremesini yumuşatma
"""
import math
from collections import deque, Counter
from dataclasses import dataclass, field
from typing import Optional, List, Tuple

NONE, FIST, OPEN, POINT, VICTORY, OTHER = "YOK", "YUMRUK", "ACIK", "ISARET", "ZAFER", "DIGER"

GESTURE_TR = {
    NONE: "El görünmüyor",
    FIST: "Yumruk",
    OPEN: "Açık el",
    POINT: "İşaret parmağı",
    VICTORY: "V işareti",
    OTHER: "Diğer",
}

FINGER_NAMES = ["Başparmak", "İşaret", "Orta", "Yüzük", "Serçe"]

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12), (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20), (0, 17),
]


@dataclass
class EngineResult:
    present: bool = False
    gesture: str = NONE
    fingers: int = 0
    palm: Optional[Tuple[float, float]] = None   # normalize (0-1)
    tip: Optional[Tuple[float, float]] = None    # işaret parmağı ucu, normalize
    overlay: object = None                       # çizimli kamera görüntüsü (BGR)
    debug: object = None                         # debug görüntüsü (BGR)
    info: List[str] = field(default_factory=list)


def _d(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def fingers_from_landmarks(lm):
    """lm: 21 adet (x, y). Dönüş: [başparmak, işaret, orta, yüzük, serçe] -> True = açık"""
    wrist = lm[0]
    palm = _d(lm[0], lm[9]) + 1e-6           # avuç boyu: ölçek normalizasyonu
    states = []
    # Başparmak: ucu işaret parmağı köküne (5) uzak ve serçe köküne (17) göre dışarıda olmalı
    thumb = (_d(lm[4], lm[5]) > 0.62 * palm) and (_d(lm[4], lm[17]) > _d(lm[3], lm[17]) * 1.03)
    states.append(thumb)
    # Diğer parmaklar: uç bilekten, orta eklemden (PIP) daha uzaksa ve kökten yeterince uzaksa açık
    for tip, pip, mcp in ((8, 6, 5), (12, 10, 9), (16, 14, 13), (20, 18, 17)):
        ext = (_d(lm[tip], wrist) > _d(lm[pip], wrist) * 1.08) and (_d(lm[tip], lm[mcp]) > 0.48 * palm)
        states.append(ext)
    return states


def classify(f):
    """Parmak durumlarından işaret etiketi."""
    t, i, m, r, p = f
    if not i and not m and not r and not p:
        return FIST
    if i and not m and not r and not p:
        return POINT
    if i and m and not r and not p:
        return VICTORY
    if i and m and r and p:
        return OPEN
    return OTHER


def gesture_from_count(n):
    """Klasik yöntem sadece parmak sayısını bulur; sayıyı işarete çeviriyoruz."""
    if n <= 0:
        return FIST
    if n == 1:
        return POINT
    if n == 2:
        return VICTORY
    if n >= 4:
        return OPEN
    return OTHER


class VoteFilter:
    """Son `window` karede çoğunluk oylaması. Yeterli oy yoksa önceki kararlı değer korunur."""

    def __init__(self, window, min_votes, initial):
        self.buf = deque(maxlen=window)
        self.min_votes = min_votes
        self.stable = initial

    def push(self, value):
        self.buf.append(value)
        val, cnt = Counter(self.buf).most_common(1)[0]
        if cnt >= self.min_votes:
            self.stable = val
        return self.stable

    def reset(self, initial):
        self.buf.clear()
        self.stable = initial


class _OneEuro1D:
    def __init__(self, mincutoff, beta, dcutoff=1.0):
        self.mincutoff, self.beta, self.dcutoff = mincutoff, beta, dcutoff
        self.x = None
        self.dx = 0.0

    @staticmethod
    def _alpha(cutoff, dt):
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def __call__(self, x, dt):
        if self.x is None:
            self.x = x
            return x
        dt = max(dt, 1e-3)
        dx = (x - self.x) / dt
        a_d = self._alpha(self.dcutoff, dt)
        self.dx = a_d * dx + (1 - a_d) * self.dx
        cutoff = self.mincutoff + self.beta * abs(self.dx)   # hızlı harekette daha az yumuşatma
        a = self._alpha(cutoff, dt)
        self.x = a * x + (1 - a) * self.x
        return self.x


class OneEuro2D:
    def __init__(self, mincutoff, beta):
        self.fx = _OneEuro1D(mincutoff, beta)
        self.fy = _OneEuro1D(mincutoff, beta)

    def __call__(self, p, dt):
        return (self.fx(p[0], dt), self.fy(p[1], dt))

    def reset(self):
        self.fx.x = None
        self.fy.x = None
