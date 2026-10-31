# -*- coding: utf-8 -*-
"""Düşmanlar, yardımcılar, büyüler (mermiler) ve dalga yöneticisi."""
import math
import random

import pygame

from config import (SCREEN_W, SCREEN_H, GROUND_Y, TOWER_X, TOWER_TOP, WALL_X, ENEMY_STOP_X, WIZARD_POS)
from .fx import draw_glow, Bolt

STAFF_TIP = (WIZARD_POS[0] + 26, WIZARD_POS[1] - 44)

# ======================================================================
#                               DÜŞMANLAR
# ======================================================================
ENEMY_TYPES = {
    #           can  hız  hasar altın yarıçap uçan  zırh
    "goblin":  (30, 78, 6, 5, 18, False, 0.0),
    "iskelet": (55, 55, 9, 8, 20, False, 0.0),
    "hayalet": (42, 62, 8, 10, 20, True, 0.0),
    "dev":     (190, 30, 22, 22, 34, False, 0.35),
    "boss":    (950, 22, 40, 150, 62, False, 0.2),
    "yarasa":  (14, 125, 4, 3, 12, True, 0.0),
    "saman":   (50, 46, 5, 12, 19, False, 0.0),
}
ENEMY_TR = {"goblin": "Goblin", "iskelet": "İskelet", "hayalet": "Hayalet", "dev": "Kalkanlı Dev",
            "boss": "GÖLGE LORDU", "yarasa": "Yarasa", "saman": "Goblin Şaman"}


class Enemy:
    def __init__(self, kind, wave):
        hp, spd, dmg, gold, r, fly, armor = ENEMY_TYPES[kind]
        mult = 1 + 0.13 * (wave - 1)
        self.kind = kind
        self.max_hp = self.hp = hp * mult
        self.speed = spd * random.uniform(0.9, 1.1)
        self.dmg = dmg * (1 + 0.06 * (wave - 1))
        self.gold = gold
        self.r = r
        self.flying = fly
        self.armor = armor
        self.x = SCREEN_W + random.uniform(20, 140)
        self.base_y = random.uniform(200, 440) if fly else GROUND_Y - r
        self.y = self.base_y
        self.t = random.uniform(0, 10)
        self.slow = 0.0
        self.stun = 0.0
        self.flash = 0.0
        self.atk_cd = 0.6
        self.spawn_cd = 5.0
        self.heal_cd = 1.0
        self.alive = True
        self.locked = False

    def stop_x(self, world):
        if not self.flying and world.golem and world.golem.alive:
            return WALL_X + 34 + self.r
        return ENEMY_STOP_X + self.r + (40 if self.flying else 0)

    def update(self, dt, world):
        self.t += dt
        self.flash = max(0.0, self.flash - dt * 5)
        self.slow = max(0.0, self.slow - dt)
        if self.stun > 0:
            self.stun -= dt
            return
        spd = self.speed * (0.4 if self.slow > 0 else 1.0)
        sx = self.stop_x(world)
        if self.x > sx:
            self.x = max(sx, self.x - spd * dt)
        else:
            self.atk_cd -= dt * (0.5 if self.slow > 0 else 1.0)
            if self.atk_cd <= 0:
                self.atk_cd = 1.1
                if not self.flying and world.golem and world.golem.alive and self.x > WALL_X:
                    world.golem.damage(self.dmg, world)
                else:
                    world.damage_tower(self.dmg, self.x - self.r, self.y)
        if self.flying:
            target_y = TOWER_TOP + 30 if self.x <= sx + 5 else self.base_y
            self.base_y += (target_y - self.base_y) * min(1, dt * 0.8)
            amp, fr = (40, 5) if self.kind == "yarasa" else (22, 3)
            self.y = self.base_y + math.sin(self.t * fr) * amp
        if self.kind == "saman":
            self.heal_cd -= dt
            if self.heal_cd <= 0:
                self.heal_cd = 1.0
                for o in world.enemies:
                    if o is not self and o.alive and o.hp < o.max_hp and math.hypot(o.x - self.x, o.y - self.y) < 150:
                        o.hp = min(o.max_hp, o.hp + 10 + 2 * world.wave)
                        world.fx.text(o.x, o.y - o.r - 30, "+", (110, 255, 140), 22)
                        world.fx.burst(o.x, o.y, (90, 230, 120), 6, 90, 0.5, 3, -60)
        if self.kind == "boss":
            self.spawn_cd -= dt
            if self.spawn_cd <= 0:
                self.spawn_cd = 6.0
                for _ in range(2):
                    e = Enemy("goblin", world.wave)
                    e.x = self.x + random.uniform(-20, 40)
                    world.enemies.append(e)
                world.fx.burst(self.x, self.y, (170, 60, 255), 30, 200)

    def hit(self, dmg, world, color=(255, 230, 120), show=True, crit=False):
        if not self.alive:
            return
        real = dmg * (1 - self.armor) * (1.8 if crit else 1.0)
        self.hp -= real
        self.flash = 1.0
        if crit:
            world.fx.text(self.x, self.y - self.r - 40, f"KRİTİK {int(real)}!", (255, 240, 90), 30)
        elif show:
            world.fx.text(self.x, self.y - self.r - 26, str(int(real)), color, 20 if real < 50 else 28)
        if self.hp <= 0:
            self.alive = False
            world.on_kill(self)

    # ---------------- çizim ----------------
    def draw(self, s):
        x, y, r = int(self.x), int(self.y), self.r
        bob = int(math.sin(self.t * 10) * 2) if not self.flying and self.stun <= 0 else 0
        y += bob
        pygame.draw.ellipse(s, (10, 10, 18), (x - r, GROUND_Y - 6, r * 2, 10))   # gölge
        k = self.kind
        if k == "goblin":
            pygame.draw.ellipse(s, (70, 140, 55), (x - r, y - r * 0.6, r * 2, r * 1.6))
            pygame.draw.circle(s, (95, 170, 70), (x - 4, y - r), int(r * 0.75))
            pygame.draw.polygon(s, (95, 170, 70), [(x - 14, y - r - 4), (x - 30, y - r - 14), (x - 12, y - r + 6)])
            pygame.draw.polygon(s, (95, 170, 70), [(x + 6, y - r - 6), (x + 18, y - r - 18), (x + 10, y - r + 2)])
            pygame.draw.circle(s, (255, 60, 40), (x - 10, y - r - 2), 3)
            pygame.draw.circle(s, (255, 60, 40), (x, y - r - 2), 3)
            pygame.draw.line(s, (120, 80, 40), (x - r, y), (x - r - 12, y - 22), 5)
            pygame.draw.circle(s, (100, 70, 40), (x - r - 13, y - 24), 6)
        elif k == "iskelet":
            pygame.draw.line(s, (220, 220, 210), (x, y - 8), (x, y + r - 6), 4)
            for i in range(3):
                pygame.draw.line(s, (220, 220, 210), (x - 10, y - 4 + i * 7), (x + 10, y - 4 + i * 7), 3)
            leg = int(math.sin(self.t * 10) * 7)
            pygame.draw.line(s, (220, 220, 210), (x, y + r - 6), (x - 7 + leg, y + r + 2), 3)
            pygame.draw.line(s, (220, 220, 210), (x, y + r - 6), (x + 7 - leg, y + r + 2), 3)
            pygame.draw.circle(s, (235, 235, 225), (x, y - r + 2), 12)
            pygame.draw.circle(s, (20, 20, 30), (x - 5, y - r + 1), 4)
            pygame.draw.circle(s, (20, 20, 30), (x + 4, y - r + 1), 4)
            pygame.draw.line(s, (170, 170, 160), (x - 14, y), (x - 28, y - 18), 3)
        elif k == "hayalet":
            g = pygame.Surface((r * 3, r * 3), pygame.SRCALPHA)
            c = (190, 220, 255, 170)
            pygame.draw.circle(g, c, (int(r * 1.5), r), r)
            pygame.draw.rect(g, c, (int(r * 0.5), r, r * 2, r))
            for i in range(4):
                pygame.draw.circle(g, c, (int(r * 0.5 + r * 0.25 + i * r * 0.5), r * 2), int(r * 0.27))
            pygame.draw.circle(g, (20, 20, 50, 230), (int(r * 1.15), int(r * 0.9)), 4)
            pygame.draw.circle(g, (20, 20, 50, 230), (int(r * 1.75), int(r * 0.9)), 4)
            pygame.draw.ellipse(g, (20, 20, 50, 200), (int(r * 1.3), int(r * 1.3), 8, 10))
            s.blit(g, (x - int(r * 1.5), y - r))
            draw_glow(s, (x, y), r * 2, (25, 35, 60))
        elif k == "dev":
            pygame.draw.ellipse(s, (120, 90, 120), (x - r, y - r, r * 2, r * 2))
            pygame.draw.circle(s, (140, 110, 140), (x + 4, y - r - 6), 16)
            pygame.draw.circle(s, (255, 200, 40), (x - 2, y - r - 8), 3)
            pygame.draw.circle(s, (255, 200, 40), (x + 8, y - r - 8), 3)
            pygame.draw.polygon(s, (140, 110, 140), [(x - 6, y - r - 18), (x - 2, y - r - 30), (x + 2, y - r - 18)])
            # tahta kalkan
            pygame.draw.rect(s, (130, 85, 40), (x - r - 12, y - r + 6, 18, r * 2 - 4), border_radius=4)
            pygame.draw.rect(s, (90, 60, 30), (x - r - 12, y - r + 6, 18, r * 2 - 4), 3, border_radius=4)
            pygame.draw.circle(s, (180, 180, 190), (x - r - 3, y), 4)
        elif k == "boss":
            draw_glow(s, (x, y), int(r * 2.4), (60, 15, 90))
            pygame.draw.ellipse(s, (45, 25, 70), (x - r, y - r, r * 2, r * 2))
            pygame.draw.circle(s, (65, 35, 95), (x, y - r + 4), int(r * 0.55))
            for i in range(5):
                bx = x - 26 + i * 13
                pygame.draw.polygon(s, (230, 190, 40), [(bx - 6, y - r - 22), (bx, y - r - 40 - (i % 2) * 8), (bx + 6, y - r - 22)])
            pygame.draw.rect(s, (230, 190, 40), (x - 32, y - r - 24, 64, 8))
            for ex in (-12, 12):
                draw_glow(s, (x + ex, y - r + 2), 16, (255, 40, 80))
                pygame.draw.circle(s, (255, 220, 230), (x + ex, y - r + 2), 4)
            pygame.draw.arc(s, (120, 70, 170), (x - r - 20, y - r - 10, r * 2 + 40, r * 2 + 40), 1.2, 2.2, 5)
        elif k == "yarasa":
            flap = math.sin(self.t * 22) * 10
            pygame.draw.polygon(s, (60, 40, 80), [(x, y), (x - 22, y - 6 - flap), (x - 14, y + 4), (x - 8, y + 2)])
            pygame.draw.polygon(s, (60, 40, 80), [(x, y), (x + 22, y - 6 - flap), (x + 14, y + 4), (x + 8, y + 2)])
            pygame.draw.circle(s, (80, 55, 105), (x, y), 8)
            pygame.draw.polygon(s, (80, 55, 105), [(x - 6, y - 5), (x - 4, y - 13), (x - 1, y - 6)])
            pygame.draw.polygon(s, (80, 55, 105), [(x + 6, y - 5), (x + 4, y - 13), (x + 1, y - 6)])
            pygame.draw.circle(s, (255, 70, 70), (x - 3, y - 1), 2)
            pygame.draw.circle(s, (255, 70, 70), (x + 3, y - 1), 2)
        elif k == "saman":
            draw_glow(s, (x, y), 46 + int(math.sin(self.t * 4) * 6), (15, 60, 25))
            pygame.draw.polygon(s, (110, 70, 40), [(x - r, y + r - 4), (x + r, y + r - 4), (x + 6, y - r + 6), (x - 6, y - r + 6)])
            pygame.draw.circle(s, (95, 170, 70), (x, y - r + 2), 12)
            pygame.draw.polygon(s, (230, 230, 220), [(x - 12, y - r - 4), (x, y - r - 22), (x + 12, y - r - 4)])
            pygame.draw.circle(s, (255, 230, 60), (x - 4, y - r + 1), 2)
            pygame.draw.circle(s, (255, 230, 60), (x + 4, y - r + 1), 2)
            pygame.draw.line(s, (130, 90, 50), (x - r - 6, y + r), (x - r - 6, y - r - 16), 3)
            draw_glow(s, (x - r - 6, y - r - 18), 16, (60, 220, 100))
        # efektler
        if self.slow > 0:
            draw_glow(s, (x, y), r * 2, (20, 60, 110))
            for i in range(3):
                a = self.t * 2 + i * 2.1
                pygame.draw.circle(s, (180, 230, 255), (int(x + math.cos(a) * r), int(y + math.sin(a) * r)), 3)
        if self.stun > 0:
            for i in range(3):
                a = self.t * 6 + i * 2.1
                pygame.draw.circle(s, (255, 255, 120), (int(x + math.cos(a) * 16), int(y - r - 14 + math.sin(a) * 5)), 3)
        if self.flash > 0:
            draw_glow(s, (x, y), int(r * 1.6), (int(140 * self.flash),) * 3)
        if self.hp < self.max_hp and k != "boss":
            w = max(30, r * 2)
            px, py = x - w // 2, y - r - 20
            pygame.draw.rect(s, (20, 10, 16), (px - 1, py - 1, w + 2, 7), border_radius=3)
            pygame.draw.rect(s, (235, 70, 80), (px, py, int(w * max(0, self.hp) / self.max_hp), 5), border_radius=3)


# ======================================================================
#                          MERMİLER / BÜYÜLER
# ======================================================================
class Fireball:
    def __init__(self, x, y, tx, ty, charge, target=None):
        self.x, self.y, self.tx, self.ty = x, y, tx, ty
        self.charge = charge
        self.target = target
        self.crit = charge >= 0.97
        d = max(1.0, math.hypot(tx - x, ty - y))
        sp = 950
        self.vx, self.vy = (tx - x) / d * sp, (ty - y) / d * sp
        self.alive = True
        self.size = 10 + 16 * charge

    def update(self, dt, world):
        if self.target is not None and self.target.alive:   # hedefe kilitli: yumuşak yönelme
            self.tx, self.ty = self.target.x, self.target.y
            d = max(1.0, math.hypot(self.tx - self.x, self.ty - self.y))
            sp = math.hypot(self.vx, self.vy)
            k = min(1.0, dt * 9)
            self.vx += ((self.tx - self.x) / d * sp - self.vx) * k
            self.vy += ((self.ty - self.y) / d * sp - self.vy) * k
        self.x += self.vx * dt
        self.y += self.vy * dt
        world.fx.trail(self.x, self.y, (255, 140, 40), self.size * 0.5, 0.35)
        reached = (self.tx - self.x) * self.vx + (self.ty - self.y) * self.vy <= 0
        hit = any(math.hypot(e.x - self.x, e.y - self.y) < e.r + self.size for e in world.enemies if e.alive)
        if reached or hit or self.y > GROUND_Y or self.x > SCREEN_W + 50:
            self.explode(world)

    def explode(self, world):
        self.alive = False
        rad = 55 + 70 * self.charge
        dmg = 22 + 60 * self.charge + world.spell_bonus * 0.5
        world.explosion(self.x, min(self.y, GROUND_Y), rad, dmg, (255, 140, 40), crit=self.crit)

    def draw(self, s):
        draw_glow(s, (int(self.x), int(self.y)), int(self.size * 3), (255, 120, 30))
        pygame.draw.circle(s, (255, 240, 180), (int(self.x), int(self.y)), int(self.size * 0.6))


class IceShard:
    def __init__(self, x, y, tx, ty):
        self.x, self.y = x, y
        d = max(1.0, math.hypot(tx - x, ty - y))
        sp = 1150
        self.vx, self.vy = (tx - x) / d * sp, (ty - y) / d * sp
        self.ang = math.atan2(self.vy, self.vx)
        self.alive = True

    def update(self, dt, world):
        self.x += self.vx * dt
        self.y += self.vy * dt
        if random.random() < 0.6:
            world.fx.trail(self.x, self.y, (120, 200, 255), 3, 0.25, 10)
        for e in world.enemies:
            if e.alive and math.hypot(e.x - self.x, e.y - self.y) < e.r + 8:
                e.slow = 2.2
                e.hit(9 + world.ice_bonus, world, (160, 220, 255))
                world.fx.burst(self.x, self.y, (150, 220, 255), 8, 160, 0.35, 3, 200)
                world.sfx.play("hit", 0.4)
                self.alive = False
                return
        if not (-50 < self.x < SCREEN_W + 50 and -50 < self.y < SCREEN_H + 50):
            self.alive = False

    def draw(self, s):
        c, sn = math.cos(self.ang), math.sin(self.ang)
        p1 = (self.x + c * 16, self.y + sn * 16)
        p2 = (self.x - c * 10 - sn * 5, self.y - sn * 10 + c * 5)
        p3 = (self.x - c * 10 + sn * 5, self.y - sn * 10 - c * 5)
        draw_glow(s, (int(self.x), int(self.y)), 22, (40, 110, 200))
        pygame.draw.polygon(s, (210, 245, 255), [p1, p2, p3])


class Meteor:
    def __init__(self, tx, delay):
        self.tx = tx
        self.y = -60 - delay * 900
        self.x = tx - (GROUND_Y - 10 - self.y) * 0.3   # çapraz düşüp tam hedefe insin
        self.alive = True

    def update(self, dt, world):
        self.y += 1450 * dt
        self.x += 1450 * 0.3 * dt
        if self.y > -20:
            world.fx.trail(self.x, self.y, (255, 110, 30), 9, 0.45, 20)
        if self.y >= GROUND_Y - 10:
            self.alive = False
            world.explosion(self.x, GROUND_Y - 10, 85, 75 + world.spell_bonus, (255, 100, 30), big=True)

    def draw(self, s):
        if self.y > -40:
            draw_glow(s, (int(self.x), int(self.y)), 48, (255, 90, 20))
            pygame.draw.circle(s, (120, 60, 40), (int(self.x), int(self.y)), 14)
            pygame.draw.circle(s, (255, 200, 120), (int(self.x) - 3, int(self.y) - 3), 6)


class Homing:
    """Yardımcıların attığı mermi (çırak = mor ışık, elf = ok)."""

    def __init__(self, x, y, target, dmg, kind):
        self.x, self.y, self.target, self.dmg, self.kind = x, y, target, dmg, kind
        self.alive = True
        self.speed = 700 if kind == "bolt" else 900
        self.ang = 0.0

    def update(self, dt, world):
        t = self.target
        if not t.alive:
            alive = [e for e in world.enemies if e.alive]
            if not alive:
                self.alive = False
                return
            t = self.target = min(alive, key=lambda e: math.hypot(e.x - self.x, e.y - self.y))
        dx, dy = t.x - self.x, t.y - self.y
        d = math.hypot(dx, dy)
        self.ang = math.atan2(dy, dx)
        if d < t.r + 6:
            t.hit(self.dmg, world, (220, 160, 255) if self.kind == "bolt" else (200, 255, 160), show=False)
            world.fx.burst(self.x, self.y, (190, 110, 255) if self.kind == "bolt" else (180, 255, 140), 6, 120, 0.3, 3)
            self.alive = False
            return
        self.x += dx / d * self.speed * dt
        self.y += dy / d * self.speed * dt
        if self.kind == "bolt":
            world.fx.trail(self.x, self.y, (170, 90, 255), 4, 0.25, 8)

    def draw(self, s):
        if self.kind == "bolt":
            draw_glow(s, (int(self.x), int(self.y)), 20, (150, 70, 255))
        else:
            c, sn = math.cos(self.ang), math.sin(self.ang)
            pygame.draw.line(s, (230, 210, 160), (self.x - c * 16, self.y - sn * 16), (self.x + c * 6, self.y + sn * 6), 3)
            pygame.draw.circle(s, (200, 255, 160), (int(self.x + c * 7), int(self.y + sn * 7)), 3)


# ======================================================================
#                              YARDIMCILAR
# ======================================================================
APPRENTICE_SLOTS = [(78, GROUND_Y - 22), (40, GROUND_Y - 22), (86, 452)]
ELF_SLOTS = [(122, TOWER_TOP - 22), (218, TOWER_TOP - 22)]


class Apprentice:
    def __init__(self, idx):
        self.x, self.y = APPRENTICE_SLOTS[idx]
        self.cd = random.uniform(0.2, 1.0)
        self.t = random.uniform(0, 6)

    def update(self, dt, world):
        self.t += dt
        self.cd -= dt
        if self.cd <= 0:
            alive = [e for e in world.enemies if e.alive and e.x < SCREEN_W - 10]
            if alive:
                tgt = min(alive, key=lambda e: e.x)
                world.projectiles.append(Homing(self.x + 12, self.y - 30, tgt, 12 + 2 * world.wave ** 0.5, "bolt"))
                self.cd = 1.5
            else:
                self.cd = 0.3

    def draw(self, s):
        x, y = int(self.x), int(self.y + math.sin(self.t * 2) * 2)
        pygame.draw.polygon(s, (40, 90, 160), [(x - 13, y + 20), (x + 13, y + 20), (x, y - 14)])
        pygame.draw.circle(s, (240, 200, 170), (x, y - 16), 8)
        pygame.draw.polygon(s, (40, 90, 160), [(x - 11, y - 20), (x + 11, y - 20), (x + 2, y - 42)])
        pygame.draw.line(s, (120, 80, 40), (x + 12, y + 20), (x + 12, y - 28), 3)
        draw_glow(s, (x + 12, y - 30), 14, (130, 60, 230))


class Elf:
    def __init__(self, idx):
        self.x, self.y = ELF_SLOTS[idx]
        self.cd = random.uniform(0.2, 0.8)
        self.t = 0.0

    def update(self, dt, world):
        self.t += dt
        self.cd -= dt
        if self.cd <= 0:
            alive = [e for e in world.enemies if e.alive and e.x < SCREEN_W - 10]
            if alive:
                fly = [e for e in alive if e.flying]
                tgt = min(fly or alive, key=lambda e: e.x)
                world.projectiles.append(Homing(self.x + 10, self.y - 10, tgt, 10 + 2 * world.wave ** 0.5, "arrow"))
                world.sfx.play("arrow", 0.25)
                self.cd = 0.85
            else:
                self.cd = 0.3

    def draw(self, s):
        x, y = int(self.x), int(self.y)
        pygame.draw.rect(s, (50, 130, 60), (x - 7, y - 8, 14, 22), border_radius=4)
        pygame.draw.circle(s, (240, 210, 180), (x, y - 14), 7)
        pygame.draw.polygon(s, (240, 210, 180), [(x - 6, y - 16), (x - 14, y - 22), (x - 5, y - 12)])
        pygame.draw.polygon(s, (60, 150, 70), [(x - 8, y - 18), (x + 8, y - 18), (x + 4, y - 28)])
        pygame.draw.arc(s, (150, 100, 50), (x + 2, y - 22, 18, 30), -1.4, 1.4, 3)


class Golem:
    def __init__(self):
        self.max_hp = self.hp = 260
        self.x, self.y = WALL_X, GROUND_Y
        self.alive = True
        self.flash = 0.0
        self.t = 0.0

    def damage(self, dmg, world):
        self.hp -= dmg
        self.flash = 1.0
        world.fx.burst(self.x + 20, self.y - 60, (160, 150, 130), 6, 150, 0.4, 4, 500, glow=False)
        world.sfx.play("hit", 0.5)
        if self.hp <= 0:
            self.alive = False
            world.fx.burst(self.x, self.y - 60, (150, 140, 120), 45, 320, 1.0, 7, 600, glow=False)
            world.fx.add_shake(8)
            world.fx.text(self.x, self.y - 150, "Golem yıkıldı!", (255, 120, 120), 26)

    def update(self, dt, world):
        self.t += dt
        self.flash = max(0.0, self.flash - dt * 4)

    def draw(self, s):
        if not self.alive:
            return
        x, y = int(self.x), int(self.y)
        c = (120, 115, 105) if self.flash <= 0 else (200, 190, 180)
        pygame.draw.ellipse(s, (10, 10, 18), (x - 40, y - 6, 80, 12))
        pygame.draw.rect(s, c, (x - 30, y - 95, 60, 70), border_radius=12)
        pygame.draw.rect(s, c, (x - 26, y - 30, 20, 30), border_radius=4)
        pygame.draw.rect(s, c, (x + 6, y - 30, 20, 30), border_radius=4)
        pygame.draw.circle(s, c, (x, y - 108), 20)
        pygame.draw.rect(s, c, (x - 46, y - 90, 18, 52), border_radius=8)
        pygame.draw.rect(s, c, (x + 28, y - 90, 18, 52), border_radius=8)
        for (a, b) in [((-18, -80), (-4, -60)), ((8, -70), (20, -50)), ((-10, -45), (5, -40))]:
            pygame.draw.line(s, (80, 75, 70), (x + a[0], y + a[1]), (x + b[0], y + b[1]), 2)
        glow_c = (40, 200, 120)
        draw_glow(s, (x - 7, y - 110), 10, glow_c)
        draw_glow(s, (x + 7, y - 110), 10, glow_c)
        draw_glow(s, (x, y - 70), 18, (20, 120, 70))
        w = 70
        pygame.draw.rect(s, (30, 30, 30), (x - w // 2, y - 140, w, 6))
        pygame.draw.rect(s, (90, 200, 120), (x - w // 2, y - 140, int(w * max(0, self.hp) / self.max_hp), 6))


class Fairy:
    def __init__(self, idx):
        self.idx = idx
        self.t = idx * 3.1
        self.x, self.y = TOWER_X, TOWER_TOP

    def update(self, dt, world):
        self.t += dt
        self.x = TOWER_X + math.cos(self.t * 1.3) * 95
        self.y = TOWER_TOP + 80 + math.sin(self.t * 2.1) * 50
        if world.tower_hp < world.tower_max:
            world.tower_hp = min(world.tower_max, world.tower_hp + 3.2 * dt)
            if random.random() < dt * 6:
                world.fx.trail(self.x, self.y, (120, 255, 160), 4, 0.6, 20)

    def draw(self, s):
        x, y = int(self.x), int(self.y)
        draw_glow(s, (x, y), 26, (60, 160, 90))
        flap = abs(math.sin(self.t * 25)) * 8
        pygame.draw.ellipse(s, (200, 255, 230), (x - 12, y - 6 - flap / 2, 10, 6 + flap))
        pygame.draw.ellipse(s, (200, 255, 230), (x + 2, y - 6 - flap / 2, 10, 6 + flap))
        pygame.draw.circle(s, (255, 250, 220), (x, y), 5)


# ======================================================================
#                              DALGALAR
# ======================================================================
def build_wave(n):
    """n. dalganın düşman listesi."""
    q = []
    count = 5 + int(n * 2.2)
    for i in range(count):
        roll = random.random()
        if n >= 2 and roll < 0.08:
            q += ["yarasa"] * 3          # sürü halinde gelir
        elif n >= 3 and roll < 0.15:
            q.append("saman")
        elif n >= 4 and roll < 0.25 + 0.01 * n:
            q.append("dev")
        elif n >= 3 and roll < 0.35:
            q.append("hayalet")
        elif n >= 2 and roll < 0.6:
            q.append("iskelet")
        else:
            q.append("goblin")
    if n % 5 == 0:
        q.append("boss")
    return q


# ======================================================================
#                     RUH KÜRELERİ (imleçle toplanır)
# ======================================================================
class Orb:
    def __init__(self, x, y, kind):
        self.x, self.y, self.kind = x, y, kind
        self.vx, self.vy = random.uniform(-90, 90), random.uniform(-320, -200)
        self.life = 9.0
        self.t = random.uniform(0, 6)
        self.alive = True
        self.floor = GROUND_Y - 40 - random.uniform(0, 40)

    @property
    def color(self):
        return (90, 150, 255) if self.kind == "mana" else (255, 200, 70)

    def update(self, dt, world):
        self.t += dt
        self.life -= dt
        if self.life <= 0:
            self.alive = False
            return
        cur = world.inp.cursor if world.inp.present else None
        if cur and math.hypot(cur[0] - self.x, cur[1] - self.y) < 110:      # mıknatıs
            dx, dy = cur[0] - self.x, cur[1] - self.y
            d = max(1.0, math.hypot(dx, dy))
            self.x += dx / d * 900 * dt
            self.y += dy / d * 900 * dt
            if d < 26:
                world.collect_orb(self)
            return
        self.vy += 700 * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        if self.y > self.floor:
            self.y = self.floor
            self.vy = 0
            self.vx *= 0.9
        if self.vy == 0:
            self.y = self.floor + math.sin(self.t * 4) * 5

    def draw(self, s):
        x, y = int(self.x), int(self.y)
        blink = self.life > 2 or int(self.life * 8) % 2 == 0
        if not blink:
            return
        c = self.color
        draw_glow(s, (x, y), 30, (c[0] // 3, c[1] // 3, c[2] // 3))
        pygame.draw.circle(s, c, (x, y), 9)
        pygame.draw.circle(s, (255, 255, 255), (x - 3, y - 3), 3)
