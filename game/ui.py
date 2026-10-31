# -*- coding: utf-8 -*-
"""
Arayüz kiti: cam efektli paneller, barlar, ikonlar, el piktogramları, önbellekli yazı.
Her şey kodla çizilir; sık kullanılan yüzeyler önbelleğe alınır (akıcılık için).
"""
import math

import pygame

# ---- Renk paleti ----
TEXT = (238, 236, 248)
MUTED = (150, 146, 178)
GOLD = (255, 204, 92)
HP = (232, 72, 88)
MANA = (84, 146, 255)
FIRE = (255, 140, 50)
ICE = (120, 200, 255)
SHIELD = (200, 225, 255)
ARCANE = (186, 110, 255)
GREEN = (110, 230, 150)
PANEL = (16, 13, 32)
BORDER = (92, 78, 150)

_fonts = {}
_text_cache = {}
_panel_cache = {}


def font(size, heading=False):
    key = (size, heading)
    f = _fonts.get(key)
    if f is None:
        names = "bahnschrift,segoeuisemibold,segoeui,arial,dejavusans" if heading else "segoeui,arial,dejavusans"
        f = pygame.font.SysFont(names, size, bold=not heading)
        _fonts[key] = f
    return f


def text_surf(s, size, color=TEXT, heading=False):
    key = (s, size, color, heading)
    img = _text_cache.get(key)
    if img is None:
        if len(_text_cache) > 600:
            _text_cache.clear()
        img = font(size, heading).render(s, True, color)
        _text_cache[key] = img
    return img


def text(surf, s, pos, size=20, color=TEXT, anchor="topleft", heading=False, shadow=True, alpha=255):
    img = text_surf(s, size, color, heading)
    r = img.get_rect(**{anchor: (int(pos[0]), int(pos[1]))})
    if shadow:
        sh = text_surf(s, size, (0, 0, 0), heading)
        if alpha < 255:
            sh = sh.copy()
            sh.set_alpha(int(alpha * 0.7))
        surf.blit(sh, (r.x + 2, r.y + 2))
    if alpha < 255:
        img = img.copy()
        img.set_alpha(int(alpha))
    surf.blit(img, r)
    return r


def panel(surf, rect, alpha=200, border=BORDER, radius=14, color=PANEL, glow=None):
    x, y, w, h = [int(v) for v in rect]
    key = (w, h, alpha, border, radius, color)
    s = _panel_cache.get(key)
    if s is None:
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(s, (*color, alpha), (0, 0, w, h), border_radius=radius)
        # üst parlama
        hh = min(h // 2, 24)
        hl = pygame.Surface((w, hh), pygame.SRCALPHA)
        pygame.draw.rect(hl, (255, 255, 255, 12), (0, 0, w, hh), border_top_left_radius=radius,
                         border_top_right_radius=radius)
        s.blit(hl, (0, 0))
        if border:
            pygame.draw.rect(s, (*border, 230), (0, 0, w, h), 2, border_radius=radius)
            pygame.draw.line(s, (255, 255, 255, 40), (radius, 2), (w - radius, 2), 1)
        _panel_cache[key] = s
    if glow:
        from .fx import draw_glow
        draw_glow(surf, (x + w // 2, y + h // 2), max(w, h) // 2 + 20, glow)
    surf.blit(s, (x, y))


def overlay(surf, alpha=170, color=(4, 3, 12)):
    alpha = max(0, min(255, int(alpha)))
    if alpha == 0:
        return
    key = ("ov", surf.get_size(), alpha, color)
    s = _panel_cache.get(key)
    if s is None:
        s = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        s.fill((*color, alpha))
        _panel_cache[key] = s
    surf.blit(s, (0, 0))


def vignette(surf):
    key = ("vig", surf.get_size())
    s = _panel_cache.get(key)
    if s is None:
        w, h = surf.get_size()
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(60):
            a = int(110 * (1 - i / 60) ** 2)
            pygame.draw.rect(s, (0, 0, 0, a), (i * 2, i * 2, w - i * 4, h - i * 4), 2, border_radius=40)
        _panel_cache[key] = s
    surf.blit(s, (0, 0))


def bar(surf, rect, ratio, color, trail=None, ticks=(), radius=7, bg=(34, 28, 56)):
    x, y, w, h = [int(v) for v in rect]
    pygame.draw.rect(surf, bg, (x, y, w, h), border_radius=radius)
    if trail is not None and trail > ratio:
        pygame.draw.rect(surf, (255, 240, 220), (x, y, int(w * min(1, trail)), h), border_radius=radius)
    fw = int(w * max(0.0, min(1.0, ratio)))
    if fw > 0:
        pygame.draw.rect(surf, color, (x, y, fw, h), border_radius=radius)
        light = tuple(min(255, c + 60) for c in color)
        pygame.draw.rect(surf, light, (x + 2, y + 2, max(0, fw - 4), max(1, h // 3)), border_radius=radius)
    for t in ticks:
        tx = x + int(w * t)
        pygame.draw.line(surf, (255, 255, 255), (tx, y + 2), (tx, y + h - 3), 2)
    pygame.draw.rect(surf, (0, 0, 0), (x, y, w, h), 2, border_radius=radius)


def chip(surf, s, pos, size=14, color=TEXT, bg=(40, 32, 70), anchor="topleft"):
    img = text_surf(s, size, color)
    w, h = img.get_width() + 16, img.get_height() + 4
    r = pygame.Rect(0, 0, w, h)
    setattr(r, anchor, (int(pos[0]), int(pos[1])))
    pygame.draw.rect(surf, bg, r, border_radius=h // 2)
    surf.blit(img, (r.x + 8, r.y + 2))
    return r


def ring(surf, center, radius, prog, color, width=6, bg=(50, 44, 80)):
    x, y = int(center[0]), int(center[1])
    pygame.draw.circle(surf, bg, (x, y), radius, width)
    if prog > 0:
        rect = pygame.Rect(x - radius, y - radius, radius * 2, radius * 2)
        pygame.draw.arc(surf, color, rect, math.pi / 2, math.pi / 2 + prog * 2 * math.pi, width + 1)


# ------------------------------------------------------------------ ikonlar
def icon_heart(surf, c, s, color=HP):
    x, y = int(c[0]), int(c[1])
    r = max(2, int(s * 0.28))
    pygame.draw.circle(surf, color, (x - r + 1, y - r // 2), r)
    pygame.draw.circle(surf, color, (x + r - 1, y - r // 2), r)
    pygame.draw.polygon(surf, color, [(x - 2 * r + 1, y - r // 3), (x + 2 * r - 1, y - r // 3), (x, y + int(s * 0.45))])
    pygame.draw.circle(surf, (255, 200, 210), (x - r, y - r), max(1, r // 3))


def icon_drop(surf, c, s, color=MANA):
    x, y = int(c[0]), int(c[1])
    r = max(2, int(s * 0.32))
    pygame.draw.circle(surf, color, (x, y + r // 2), r)
    pygame.draw.polygon(surf, color, [(x - r, y + r // 2), (x + r, y + r // 2), (x, y - int(s * 0.5))])
    pygame.draw.circle(surf, (210, 230, 255), (x - r // 3, y + r // 3), max(1, r // 3))


def icon_coin(surf, c, s):
    x, y = int(c[0]), int(c[1])
    r = max(3, int(s * 0.45))
    pygame.draw.circle(surf, (190, 130, 30), (x, y), r)
    pygame.draw.circle(surf, GOLD, (x, y), r - 2)
    pygame.draw.circle(surf, (225, 165, 50), (x, y), int(r * 0.6), 2)
    pygame.draw.circle(surf, (255, 245, 200), (x - r // 3, y - r // 3), max(1, r // 4))


def icon_skull(surf, c, s, color=(230, 228, 240)):
    x, y = int(c[0]), int(c[1])
    r = int(s * 0.38)
    pygame.draw.circle(surf, color, (x, y - 2), r)
    pygame.draw.rect(surf, color, (x - r // 2, y + r // 2 - 2, r, r // 2 + 2))
    pygame.draw.circle(surf, (20, 18, 30), (x - r // 2 + 1, y - 2), max(1, r // 3))
    pygame.draw.circle(surf, (20, 18, 30), (x + r // 2 - 1, y - 2), max(1, r // 3))


def icon_star(surf, c, s, color=GOLD):
    x, y = c
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = s * 0.5 if i % 2 == 0 else s * 0.22
        pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr))
    pygame.draw.polygon(surf, color, pts)


def icon_meteor(surf, c, s):
    x, y = int(c[0]), int(c[1])
    for i in range(3):
        pygame.draw.line(surf, (255, 150 - i * 30, 40), (x - s * 0.45 + i * 5, y - s * 0.45 - i * 3),
                         (x, y), max(2, int(s * 0.12)))
    pygame.draw.circle(surf, (255, 120, 40), (x + 2, y + 2), int(s * 0.24))
    pygame.draw.circle(surf, (255, 220, 150), (x, y), int(s * 0.12))


def icon_bolt(surf, c, s, color=(220, 230, 255)):
    x, y = c
    pts = [(x + s * 0.1, y - s * 0.5), (x - s * 0.25, y + s * 0.05), (x, y + s * 0.05),
           (x - s * 0.12, y + s * 0.5), (x + s * 0.28, y - s * 0.08), (x + s * 0.02, y - s * 0.08)]
    pygame.draw.polygon(surf, color, pts)


def icon_tower(surf, c, s, color=(150, 145, 170)):
    x, y = int(c[0]), int(c[1])
    w, h = int(s * 0.5), int(s * 0.7)
    pygame.draw.rect(surf, color, (x - w // 2, y - h // 2 + 6, w, h))
    for i in range(3):
        pygame.draw.rect(surf, color, (x - w // 2 - 3 + i * (w // 2), y - h // 2 - 2, w // 3 + 1, 10))
    pygame.draw.rect(surf, (60, 45, 40), (x - 6, y + h // 2 - 8, 12, 14), border_top_left_radius=6,
                     border_top_right_radius=6)
    pygame.draw.polygon(surf, ARCANE, [(x, y - h // 2 - 22), (x + 16, y - h // 2 - 16), (x, y - h // 2 - 10)])
    pygame.draw.line(surf, (90, 80, 70), (x, y - h // 2 - 22), (x, y - h // 2 - 2), 2)


# ------------------------------------------------------------------ el piktogramları
def _rrect(surf, color, cx, cy, w, h, angle=0.0):
    """Döndürülebilir yuvarlatılmış çubuk (parmak)."""
    if angle == 0:
        pygame.draw.rect(surf, color, (int(cx - w / 2), int(cy - h / 2), int(w), int(h)), border_radius=int(w / 2))
        return
    ca, sa = math.cos(angle), math.sin(angle)
    hx, hy = -sa * h / 2, ca * h / 2   # uzun eksen
    p1 = (cx - hx, cy - hy)
    p2 = (cx + hx, cy + hy)
    pygame.draw.line(surf, color, p1, p2, int(w))
    pygame.draw.circle(surf, color, (int(p1[0]), int(p1[1])), int(w / 2))
    pygame.draw.circle(surf, color, (int(p2[0]), int(p2[1])), int(w / 2))


def hand(surf, kind, c, s, color=TEXT):
    """kind: 'open' | 'fist' | 'v' | 'point' | 'n1'..'n5' (parmak sayısı)"""
    x, y = c
    fw = s * 0.15             # parmak genişliği
    px = [-0.21, -0.07, 0.07, 0.21]
    ext = {"open": [1, 1, 1, 1, 1], "fist": [0, 0, 0, 0, 0], "v": [0, 1, 1, 0, 0], "point": [0, 1, 0, 0, 0],
           "n1": [0, 1, 0, 0, 0], "n2": [0, 1, 1, 0, 0], "n3": [0, 1, 1, 1, 0], "n4": [0, 1, 1, 1, 1],
           "n5": [1, 1, 1, 1, 1]}[kind]
    # avuç
    pw, ph = s * 0.58, s * 0.46
    pygame.draw.rect(surf, color, (int(x - pw / 2), int(y - ph * 0.15), int(pw), int(ph)), border_radius=int(s * 0.14))
    # parmaklar (işaret, orta, yüzük, serçe)
    lens = [0.36, 0.40, 0.37, 0.30]
    for i in range(4):
        fx = x + px[i] * s
        if ext[i + 1]:
            L = lens[i] * s
            _rrect(surf, color, fx, y - ph * 0.15 - L / 2 + fw * 0.4, fw, L + fw * 0.6)
        else:
            _rrect(surf, color, fx, y - ph * 0.12, fw, fw * 1.4)
            pygame.draw.line(surf, (0, 0, 0), (fx - fw / 2 + 1, y - ph * 0.05), (fx + fw / 2 - 1, y - ph * 0.05), 1)
    # başparmak
    if ext[0]:
        _rrect(surf, color, x - pw / 2 - s * 0.06, y + ph * 0.05, fw, s * 0.34, angle=-0.75)
    else:
        _rrect(surf, color, x - pw * 0.15, y + ph * 0.22, fw * 0.95, s * 0.30, angle=1.35)
