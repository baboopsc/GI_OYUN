# -*- coding: utf-8 -*-
"""Parçacıklar, ışıma (glow) sprite'ları, uçan yazılar, şimşek çizimi."""
import math
import random

import pygame

_glow_cache = {}


def glow(radius, color):
    """Merkezi parlak, dışa doğru sönen daire. BLEND_RGB_ADD ile çizilir."""
    radius = max(2, int(radius))
    key = (radius, color)
    s = _glow_cache.get(key)
    if s is None:
        s = pygame.Surface((radius * 2, radius * 2))
        s.fill((0, 0, 0))
        for i in range(radius, 0, -1):
            k = (1 - i / radius) ** 1.8
            pygame.draw.circle(s, (int(color[0] * k), int(color[1] * k), int(color[2] * k)), (radius, radius), i)
        _glow_cache[key] = s
    return s


def draw_glow(surf, pos, radius, color):
    g = glow(radius, color)
    surf.blit(g, (pos[0] - g.get_width() // 2, pos[1] - g.get_height() // 2), special_flags=pygame.BLEND_RGB_ADD)


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "color", "size", "grav", "drag", "glow")

    def __init__(self, x, y, vx, vy, life, color, size, grav=0.0, drag=0.0, glow=True):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life = self.max_life = life
        self.color, self.size, self.grav, self.drag, self.glow = color, size, grav, drag, glow


class FloatText:
    __slots__ = ("x", "y", "text", "color", "life", "size")

    def __init__(self, x, y, text, color, size=22, life=0.9):
        self.x, self.y, self.text, self.color, self.size, self.life = x, y, text, color, size, life


class Bolt:
    """Zikzaklı şimşek çizgisi."""

    def __init__(self, x0, y0, x1, y1, life=0.35):
        self.life = self.max_life = life
        self.points = [(x0, y0)]
        n = 12
        for i in range(1, n):
            t = i / n
            self.points.append((x0 + (x1 - x0) * t + random.uniform(-28, 28), y0 + (y1 - y0) * t))
        self.points.append((x1, y1))


class FX:
    def __init__(self):
        self.parts = []
        self.texts = []
        self.bolts = []
        self.shake = 0.0
        self.flash = 0.0
        self.flash_color = (255, 255, 255)

    def burst(self, x, y, color, n=20, speed=260, life=0.6, size=5, grav=300, glow=True):
        for _ in range(n):
            a = random.uniform(0, 2 * math.pi)
            s = random.uniform(0.25, 1) * speed
            self.parts.append(Particle(x, y, math.cos(a) * s, math.sin(a) * s,
                                       random.uniform(0.5, 1) * life, color, random.uniform(0.6, 1.2) * size,
                                       grav, 1.5, glow))

    def trail(self, x, y, color, size=6, life=0.35, spread=30):
        self.parts.append(Particle(x, y, random.uniform(-spread, spread), random.uniform(-spread, spread),
                                   life, color, size, -40, 2.0, True))

    def text(self, x, y, text, color, size=22):
        self.texts.append(FloatText(x, y, text, color, size))

    def add_shake(self, v):
        self.shake = max(self.shake, v)

    def add_flash(self, v, color=(255, 255, 255)):
        self.flash = max(self.flash, v)
        self.flash_color = color

    def update(self, dt):
        for p in self.parts:
            p.life -= dt
            p.vy += p.grav * dt
            k = max(0.0, 1 - p.drag * dt)
            p.vx *= k
            p.vy *= k
            p.x += p.vx * dt
            p.y += p.vy * dt
        self.parts = [p for p in self.parts if p.life > 0]
        if len(self.parts) > 900:
            self.parts = self.parts[-900:]
        for t in self.texts:
            t.life -= dt
            t.y -= 45 * dt
        self.texts = [t for t in self.texts if t.life > 0]
        for b in self.bolts:
            b.life -= dt
        self.bolts = [b for b in self.bolts if b.life > 0]
        self.shake = max(0.0, self.shake - dt * 30)
        self.flash = max(0.0, self.flash - dt * 2.5)

    def draw(self, surf, font_cache):
        for p in self.parts:
            k = p.life / p.max_life
            r = max(1, int(p.size * (0.4 + 0.6 * k)))
            c = (int(p.color[0] * k), int(p.color[1] * k), int(p.color[2] * k))
            if p.glow:
                draw_glow(surf, (int(p.x), int(p.y)), r * 3, c)
            else:
                pygame.draw.circle(surf, p.color, (int(p.x), int(p.y)), r)
        for b in self.bolts:
            k = b.life / b.max_life
            w = max(1, int(6 * k))
            pygame.draw.lines(surf, (150, 180, 255), False, b.points, w + 4)
            pygame.draw.lines(surf, (255, 255, 255), False, b.points, w)
            for p in b.points[::3]:
                draw_glow(surf, (int(p[0]), int(p[1])), 30, (int(90 * k), int(110 * k), int(220 * k)))
        for t in self.texts:
            f = font_cache(t.size)
            img = f.render(t.text, True, t.color)
            img.set_alpha(int(255 * min(1, t.life * 2)))
            surf.blit(img, (t.x - img.get_width() // 2, t.y))
