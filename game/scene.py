# -*- coding: utf-8 -*-
"""Arka plan, kule ve büyücü çizimi (hepsi kodla çizilir, hazır görsel yok)."""
import math
import random

import pygame

from config import SCREEN_W, SCREEN_H, GROUND_Y, TOWER_X, TOWER_W, TOWER_TOP, WIZARD_POS
from .fx import draw_glow


def build_background():
    s = pygame.Surface((SCREEN_W, SCREEN_H))
    # gökyüzü gradyanı
    top, bot = (12, 10, 38), (70, 40, 90)
    for y in range(GROUND_Y):
        k = y / GROUND_Y
        pygame.draw.line(s, [int(top[i] + (bot[i] - top[i]) * k) for i in range(3)], (0, y), (SCREEN_W, y))
    rnd = random.Random(7)
    for _ in range(170):
        x, y = rnd.randrange(SCREEN_W), rnd.randrange(GROUND_Y - 150)
        b = rnd.randint(120, 255)
        s.set_at((x, y), (b, b, b))
        if rnd.random() < 0.08:
            pygame.draw.circle(s, (b, b, b), (x, y), 1)
    # ay
    draw_glow(s, (1040, 120), 150, (70, 60, 90))
    pygame.draw.circle(s, (245, 240, 220), (1040, 120), 46)
    pygame.draw.circle(s, (215, 210, 190), (1025, 108), 9)
    pygame.draw.circle(s, (220, 215, 195), (1055, 135), 6)
    # uzak dağlar
    for layer, (col, base, amp) in enumerate([((40, 30, 70), 470, 90), ((30, 24, 55), 520, 60)]):
        pts = [(0, GROUND_Y)]
        for x in range(0, SCREEN_W + 40, 40):
            y = base - amp * (0.5 + 0.5 * math.sin(x * 0.006 + layer * 2)) * (0.6 + 0.4 * rnd.random())
            pts.append((x, y))
        pts.append((SCREEN_W, GROUND_Y))
        pygame.draw.polygon(s, col, pts)
    # ağaç siluetleri
    for i in range(14):
        x = 420 + i * 63 + rnd.randint(-15, 15)
        h = rnd.randint(50, 95)
        pygame.draw.polygon(s, (20, 18, 40), [(x - 18, GROUND_Y - 8), (x + 18, GROUND_Y - 8), (x, GROUND_Y - 8 - h)])
    # zemin
    pygame.draw.rect(s, (32, 48, 36), (0, GROUND_Y, SCREEN_W, SCREEN_H - GROUND_Y))
    pygame.draw.rect(s, (48, 72, 48), (0, GROUND_Y, SCREEN_W, 8))
    for _ in range(160):
        x = rnd.randrange(SCREEN_W)
        y = rnd.randrange(GROUND_Y + 10, SCREEN_H)
        pygame.draw.line(s, (40, 60, 42), (x, y), (x + 3, y - 4), 1)
    return s


def build_tower():
    w, h = TOWER_W + 40, GROUND_Y - TOWER_TOP + 40
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    x0 = 20
    pygame.draw.rect(s, (88, 84, 98), (x0, 40, TOWER_W, h - 40))
    for row in range(0, h - 40, 18):
        off = 0 if (row // 18) % 2 == 0 else 15
        for col in range(-15 + off, TOWER_W, 30):
            bx = x0 + max(col, 0)
            bw = min(30 if col >= 0 else 30 + col, x0 + TOWER_W - bx)
            if bw > 2:
                pygame.draw.rect(s, (70, 66, 80), (bx, 40 + row, bw, 18), 1)
    for i in range(5):
        pygame.draw.rect(s, (98, 94, 108), (x0 - 6 + i * 27, 18, 18, 26))
    pygame.draw.rect(s, (98, 94, 108), (x0 - 8, 36, TOWER_W + 16, 12))
    # kapı ve pencereler
    pygame.draw.rect(s, (45, 30, 25), (x0 + TOWER_W // 2 - 20, h - 62, 40, 62), border_top_left_radius=20,
                     border_top_right_radius=20)
    for wy in (120, 200):
        pygame.draw.rect(s, (255, 200, 90), (x0 + TOWER_W // 2 - 9, wy, 18, 28), border_top_left_radius=9,
                         border_top_right_radius=9)
    # bayrak
    pygame.draw.line(s, (60, 50, 40), (x0 + 6, 18), (x0 + 6, 0), 3)
    pygame.draw.polygon(s, (140, 50, 200), [(x0 + 7, 0), (x0 + 30, 5), (x0 + 7, 11)])
    # balkon (3. çırak için)
    return s


def draw_tower(surf, tower_img, t, hp_ratio):
    x = TOWER_X - TOWER_W // 2 - 20
    surf.blit(tower_img, (x, TOWER_TOP - 40))
    for wy in (120, 200):
        draw_glow(surf, (TOWER_X, TOWER_TOP - 40 + wy + 14), 34, (60, 40, 10))
    pygame.draw.rect(surf, (90, 60, 35), (55, 474, 60, 8))   # balkon
    if hp_ratio < 0.5:   # hasarlı kule: dumanlı çatlaklar
        for i in range(3):
            pygame.draw.line(surf, (40, 35, 45), (TOWER_X - 40 + i * 30, TOWER_TOP + 60 + i * 50),
                             (TOWER_X - 25 + i * 30, TOWER_TOP + 100 + i * 50), 3)


def draw_wizard(surf, t, orb_color, casting=0.0):
    x, y = WIZARD_POS
    y += int(math.sin(t * 2) * 2)
    # cüppe
    pygame.draw.polygon(surf, (70, 40, 140), [(x - 22, y + 30), (x + 22, y + 30), (x + 6, y - 22), (x - 6, y - 22)])
    pygame.draw.polygon(surf, (95, 60, 170), [(x - 4, y + 30), (x + 4, y + 30), (x + 2, y - 18), (x - 2, y - 18)])
    # sakal ve yüz
    pygame.draw.circle(surf, (240, 205, 175), (x, y - 28), 10)
    pygame.draw.polygon(surf, (230, 230, 235), [(x - 9, y - 26), (x + 9, y - 26), (x, y - 2)])
    pygame.draw.circle(surf, (30, 30, 50), (x - 4, y - 30), 2)
    pygame.draw.circle(surf, (30, 30, 50), (x + 4, y - 30), 2)
    # şapka
    pygame.draw.ellipse(surf, (60, 35, 125), (x - 22, y - 42, 44, 10))
    tip_x = x - 14 + int(math.sin(t * 1.5) * 3)
    pygame.draw.polygon(surf, (70, 40, 140), [(x - 13, y - 38), (x + 13, y - 38), (tip_x, y - 82)])
    pygame.draw.circle(surf, (255, 230, 90), (x + 1, y - 54), 3)
    # asa
    sx, sy = x + 26, y - 44
    pygame.draw.line(surf, (120, 80, 40), (x + 22, y + 30), (sx, sy), 4)
    pygame.draw.circle(surf, (20, 20, 20), (sx, sy), 7)
    draw_glow(surf, (sx, sy), int(26 + 30 * casting), orb_color)
    pygame.draw.circle(surf, (255, 255, 255), (sx, sy), 4)
