# -*- coding: utf-8 -*-
"""
Havaya çizilen rünleri tanıma: $1 Unistroke Recognizer (Wobbrock, Wilson, Li - 2007)

Adımlar:
 1) Yeniden örnekleme  : çizgiyi eşit aralıklı N noktaya indir
 2) Döndürme           : merkezden ilk noktaya olan açıyı 0'a getir (başlangıç noktasından bağımsızlık)
 3) Ölçekleme          : sabit boyutlu kareye sığdır (boyuttan bağımsızlık)
 4) Öteleme            : ağırlık merkezini orijine taşı (konumdan bağımsızlık)
 5) Eşleştirme         : altın oran araması ile en iyi açıda şablonlarla ortalama nokta mesafesi
"""
import math

N_POINTS = 64
SQUARE = 250.0
HALF_DIAG = 0.5 * math.sqrt(2 * SQUARE * SQUARE)
ANGLE_RANGE = math.radians(45.0)
ANGLE_PREC = math.radians(2.0)
PHI = 0.5 * (-1.0 + math.sqrt(5.0))

RUNE_TR = {"daire": "Daire  →  METEOR YAĞMURU", "simsek": "Zikzak  →  YILDIRIM"}


def path_length(pts):
    return sum(math.dist(pts[i - 1], pts[i]) for i in range(1, len(pts)))


def resample(pts, n=N_POINTS):
    pts = [tuple(p) for p in pts]
    interval = path_length(pts) / (n - 1)
    if interval <= 0:
        return [pts[0]] * n
    D = 0.0
    out = [pts[0]]
    i = 1
    while i < len(pts):
        d = math.dist(pts[i - 1], pts[i])
        if D + d >= interval and d > 0:
            t = (interval - D) / d
            q = (pts[i - 1][0] + t * (pts[i][0] - pts[i - 1][0]),
                 pts[i - 1][1] + t * (pts[i][1] - pts[i - 1][1]))
            out.append(q)
            pts.insert(i, q)
            D = 0.0
        else:
            D += d
        i += 1
    while len(out) < n:
        out.append(pts[-1])
    return out[:n]


def centroid(pts):
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def rotate_by(pts, ang):
    c = centroid(pts)
    cos, sin = math.cos(ang), math.sin(ang)
    return [((p[0] - c[0]) * cos - (p[1] - c[1]) * sin + c[0],
             (p[0] - c[0]) * sin + (p[1] - c[1]) * cos + c[1]) for p in pts]


def indicative_angle(pts):
    c = centroid(pts)
    return math.atan2(c[1] - pts[0][1], c[0] - pts[0][0])


def scale_to_square(pts, size=SQUARE):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    w = max(max(xs) - min(xs), 1e-6)
    h = max(max(ys) - min(ys), 1e-6)
    return [(p[0] * size / w, p[1] * size / h) for p in pts]


def translate_to_origin(pts):
    c = centroid(pts)
    return [(p[0] - c[0], p[1] - c[1]) for p in pts]


def normalize(pts):
    p = resample(pts)
    p = rotate_by(p, -indicative_angle(p))
    p = scale_to_square(p)
    return translate_to_origin(p)


def path_distance(a, b):
    return sum(math.dist(a[i], b[i]) for i in range(len(a))) / len(a)


def distance_at_angle(pts, tmpl, ang):
    return path_distance(rotate_by(pts, ang), tmpl)


def distance_at_best_angle(pts, tmpl):
    a, b = -ANGLE_RANGE, ANGLE_RANGE
    x1 = PHI * a + (1 - PHI) * b
    f1 = distance_at_angle(pts, tmpl, x1)
    x2 = (1 - PHI) * a + PHI * b
    f2 = distance_at_angle(pts, tmpl, x2)
    while abs(b - a) > ANGLE_PREC:
        if f1 < f2:
            b, x2, f2 = x2, x1, f1
            x1 = PHI * a + (1 - PHI) * b
            f1 = distance_at_angle(pts, tmpl, x1)
        else:
            a, x1, f1 = x1, x2, f2
            x2 = (1 - PHI) * a + PHI * b
            f2 = distance_at_angle(pts, tmpl, x2)
    return min(f1, f2)


def _poly(points, steps=40):
    """Köşe noktalarından yoğun bir çizgi üret (şablon için)."""
    out = []
    for i in range(len(points) - 1):
        a, b = points[i], points[i + 1]
        for k in range(steps):
            t = k / steps
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    out.append(points[-1])
    return out


def _circle(cw=True, start=-90):
    pts = []
    for k in range(0, 361, 6):
        a = math.radians(start + (k if cw else -k))
        pts.append((100 + 100 * math.cos(a), 100 + 100 * math.sin(a)))
    return pts


class RuneRecognizer:
    def __init__(self):
        self.templates = []
        # Daire: saat yönü ve tersi
        for cw in (True, False):
            self.add("daire", _circle(cw))
        # Şimşek / zikzak: Z, ters Z, W ve dikey şimşek
        zig_variants = [
            [(0, 0), (100, 0), (0, 100), (100, 100)],                       # Z
            [(0, 0), (25, 100), (50, 0), (75, 100), (100, 0)],              # W
            [(0, 100), (25, 0), (50, 100), (75, 0), (100, 100)],            # M
            [(60, 0), (20, 50), (80, 50), (40, 100)],                        # dikey şimşek
            [(0, 0), (35, 100), (65, 0), (100, 100)],                        # N tipi
        ]
        for v in zig_variants:
            self.add("simsek", _poly(v))
            self.add("simsek", _poly(list(reversed(v))))

    def add(self, name, pts):
        self.templates.append((name, normalize(pts)))

    def recognize(self, pts):
        """Dönüş: (isim, skor 0-1). Az nokta varsa (None, 0)."""
        if len(pts) < 8:
            return None, 0.0
        cand = normalize(pts)
        best, best_d = None, float("inf")
        for name, tmpl in self.templates:
            d = distance_at_best_angle(cand, tmpl)
            if d < best_d:
                best, best_d = name, d
        score = 1.0 - best_d / HALF_DIAG
        return best, score
