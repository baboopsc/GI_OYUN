# -*- coding: utf-8 -*-
"""
Oyunun ana döngüsü: durumlar (MENÜ / OYUN / DÜKKÂN / BİTTİ), el işaretlerinin büyülere çevrilmesi,
nişan yardımı, kombo sistemi, ruh küreleri ve tüm arayüz.
"""
import math
import random

import pygame

from config import *
from vision.gestures import NONE, FIST, OPEN, POINT, VICTORY, OTHER, GESTURE_TR, OneEuro2D
from vision.rune import RuneRecognizer
from . import ui
from .fx import FX, draw_glow, Bolt
from .sfx import Sfx
from .scene import build_background, build_tower, draw_tower, draw_wizard
from .world import (Enemy, Fireball, IceShard, Meteor, Apprentice, Elf, Golem, Fairy, Orb, build_wave,
                    STAFF_TIP, APPRENTICE_SLOTS, ELF_SLOTS, ENEMY_TR)

MENU, PLAY, SHOP, OVER = "menu", "play", "shop", "over"

SHOP_ITEMS = [
    # (parmak, isim, açıklama, temel fiyat, fiyat artışı)
    (1, "Çırak Büyücü", "Kendi kendine mor ışık atar", 50, 30),
    (2, "Elf Okçu", "Hızlı ok atar, önce uçanları vurur", 60, 35),
    (3, "Taş Golem", "Kulenin önünde canlı duvar olur", 80, 0),
    (4, "Şifacı Peri", "Kuleyi sürekli onarır", 70, 40),
    (5, "Kule Güçlendir", "+40 can, tam onarım ve büyü gücü", 45, 25),
]

# Büyü çubuğu: (el ikonu, ad, mana, renk, tetikleyen işaret, rün ipucu)
SPELLS = [
    ("fist", "ATEŞ TOPU", COST_FIREBALL, ui.FIRE, FIST, None),
    ("v", "BUZ OKU", COST_ICE, ui.ICE, VICTORY, None),
    ("open", "KALKAN", 0, ui.SHIELD, OPEN, None),
    ("point", "METEOR", COST_METEOR, (255, 120, 50), POINT, "daire"),
    ("point", "YILDIRIM", COST_LIGHTNING, (200, 210, 255), POINT, "simsek"),
]

GESTURE_ICON = {FIST: "fist", OPEN: "open", VICTORY: "v", POINT: "point"}


def fmt(n):
    return f"{int(n):,}".replace(",", ".")


class Inp:
    __slots__ = ("present", "gesture", "fingers", "cursor", "tip")

    def __init__(self):
        self.present = False
        self.gesture = NONE
        self.fingers = 0
        self.cursor = (SCREEN_W * 0.6, SCREEN_H * 0.5)
        self.tip = self.cursor


class Game:
    def __init__(self, screen, vision):
        self.screen = screen
        self.canvas = pygame.Surface((SCREEN_W, SCREEN_H))
        self.vision = vision
        self.clock = pygame.time.Clock()
        self.sfx = Sfx()
        self.fx = FX()
        self.bg = build_background()
        self.tower_img = build_tower()
        self.runes = RuneRecognizer()
        self.cur_filter = OneEuro2D(EURO_MINCUTOFF, EURO_BETA)
        self.tip_filter = OneEuro2D(EURO_MINCUTOFF, EURO_BETA)
        self.inp = Inp()
        self.mouse_mode = False
        self.debug = False
        self.paused = False
        self.t = 0.0
        self.game_fps = 0.0
        self.prev_surf = self.dbg_surf = self.big_prev = self.big_dbg = None
        self.last_seq = -1
        self.last_seen = -10.0
        self.state = MENU
        self.fade = 0.35
        self.hold_val = None
        self.hold_t = 0.0
        self.hold_used = False
        self.best = 0
        # dükkân önizleme figürleri
        self.preview_allies = [Apprentice(0), Elf(0), Golem(), Fairy(0)]
        self.sfx.start_music()
        self.reset()

    # ================================================================== durum
    def reset(self):
        self.wave = 0
        self.enemies, self.projectiles, self.orbs = [], [], []
        self.apprentices, self.elves, self.fairies = [], [], []
        self.golem = None
        self.tower_max = self.tower_hp = TOWER_HP
        self.hp_trail = 1.0
        self.mana = MANA_MAX
        self.gold = START_GOLD
        self.disp_gold = float(START_GOLD)
        self.score = 0
        self.disp_score = 0.0
        self.kills = 0
        self.queue = []
        self.wave_total = 1
        self.wave_killed = 0
        self.spawn_t = 0.0
        self.spell_bonus = 0
        self.ice_bonus = 0
        self.upgrades = 0
        self.charge = 0.0
        self.open_t = 0.0
        self.ice_cd = 0.0
        self.shield = False
        self.rune_pts = []
        self.rune_still = 0.0
        self.prev_g = NONE
        self.target = None
        self.combo = 0
        self.combo_t = 0.0
        self.best_combo = 0
        self.play_time = 0.0
        self.banner = ("", "", 0.0)
        self.wave_bonus = 0
        self.msg = ("", 0.0, ui.TEXT)
        self.hurt = 0.0
        self.casting = None   # son yapılan büyü (büyü çubuğu vurgusu)
        self.cast_t = 0.0

    def set_state(self, s):
        self.state = s
        self.fade = 0.35
        self.hold_val = None

    def start_wave(self):
        for o in self.orbs:          # yerde kalan küreler otomatik toplanır
            self.collect_orb(o, quiet=True)
        self.orbs = []
        self.wave += 1
        self.queue = build_wave(self.wave)
        self.wave_total = len(self.queue)
        self.wave_killed = 0
        self.spawn_t = 1.4
        boss = self.wave % 5 == 0
        self.banner = (f"DALGA {self.wave}", "Gölge Lordu yaklaşıyor!" if boss else
                       f"{self.wave_total} düşman geliyor", 2.6)
        self.mana = MANA_MAX
        if self.golem and self.golem.alive:
            self.golem.hp = self.golem.max_hp
        self.sfx.play("wave", 0.6)
        self.set_state(PLAY)

    def show_msg(self, s, color=ui.TEXT, dur=1.6):
        self.msg = (s, dur, color)

    # ---- world arayüzü (entity'ler bunları çağırır) ----
    def damage_tower(self, dmg, x, y):
        if self.shield:
            self.fx.burst(x, y, (200, 230, 255), 6, 160, 0.3, 3, 0)
            self.mana = max(0, self.mana - dmg * 0.3)
            return
        self.tower_hp -= dmg
        self.hurt = 0.5
        self.fx.add_shake(5)
        self.fx.burst(x, y, (255, 80, 60), 8, 180, 0.4, 4, 400)
        self.fx.text(TOWER_X, TOWER_TOP - 20, f"-{int(dmg)}", (255, 90, 90), 24)
        self.sfx.play("hurt", 0.5)

    def on_kill(self, e):
        self.combo = self.combo + 1 if self.combo_t > 0 else 1
        self.combo_t = 2.6
        self.best_combo = max(self.best_combo, self.combo)
        mult = 1 + 0.1 * min(self.combo - 1, 20)
        gold = int(round(e.gold * mult))
        self.gold += gold
        self.score += int((e.gold * 10 + self.wave * 2) * mult)
        self.kills += 1
        self.wave_killed += 1
        col = {"goblin": (110, 220, 90), "iskelet": (240, 240, 230), "hayalet": (180, 220, 255),
               "dev": (200, 150, 200), "boss": (210, 120, 255), "yarasa": (150, 110, 190),
               "saman": (120, 240, 140)}[e.kind]
        self.fx.burst(e.x, e.y, col, 40 if e.kind == "boss" else 16, 260, 0.7, 5)
        self.fx.text(e.x, e.y - e.r - 46, f"+{gold}", ui.GOLD, 20)
        self.sfx.play("death_big" if e.kind in ("dev", "boss") else "death", 0.45)
        self.sfx.play("coin", 0.2)
        r = random.random()
        if e.kind == "boss":
            for _ in range(6):
                self.orbs.append(Orb(e.x, e.y, "gold"))
            self.fx.add_shake(14)
            self.fx.add_flash(0.6, (200, 120, 255))
            self.show_msg("GÖLGE LORDU YENİLDİ!", (220, 150, 255), 2.5)
        elif r < 0.2:
            self.orbs.append(Orb(e.x, e.y, "mana"))
        elif r < 0.3:
            self.orbs.append(Orb(e.x, e.y, "gold"))
        if self.combo in (5, 10, 15, 20, 30):
            self.sfx.play("combo", 0.55)
            self.fx.text(SCREEN_W // 2, 140, f"KOMBO x{self.combo}!", (255, 200, 90), 34)

    def collect_orb(self, o, quiet=False):
        o.alive = False
        if o.kind == "mana":
            self.mana = min(MANA_MAX, self.mana + 22)
            if not quiet:
                self.fx.text(o.x, o.y - 20, "+22 MANA", (130, 180, 255), 20)
        else:
            g = 8 + self.wave
            self.gold += g
            if not quiet:
                self.fx.text(o.x, o.y - 20, f"+{g}", ui.GOLD, 20)
        if not quiet:
            self.fx.burst(o.x, o.y, o.color, 12, 160, 0.4, 4, 0)
            self.sfx.play("orb", 0.5)

    def explosion(self, x, y, rad, dmg, color, big=False, crit=False):
        for e in self.enemies:
            if e.alive:
                d = math.hypot(e.x - x, e.y - y) - e.r
                if d < rad:
                    e.hit(dmg * (1 - 0.45 * max(0, d) / rad), self, crit=crit)
        self.fx.burst(x, y, color, 34 if big else 24, 330 if big else 260, 0.7, 6, 350)
        self.fx.burst(x, y, (255, 240, 200), 10, 120, 0.3, 8, 0)
        self.fx.add_shake(10 if (big or crit) else 6)
        self.sfx.play("boom", 0.55 if big else 0.45)

    # ================================================================== girdi
    def read_input(self, dt):
        st = self.vision.get_state()
        inp = self.inp
        if self.mouse_mode or not st.cam_ok:
            mx, my = pygame.mouse.get_pos()
            b = pygame.mouse.get_pressed()
            k = pygame.key.get_pressed()
            inp.present = True
            inp.cursor = inp.tip = (mx, my)
            if b[0]:
                g = FIST
            elif b[2]:
                g = VICTORY
            elif k[pygame.K_SPACE]:
                g = OPEN
            elif b[1] or k[pygame.K_LSHIFT] or k[pygame.K_RSHIFT]:
                g = POINT
            else:
                g = OTHER
            inp.gesture = g
            inp.fingers = -1
            return st

        if st.seq != self.last_seq:
            self.last_seq = st.seq
            if st.preview:
                self.prev_surf = pygame.image.frombuffer(st.preview, (PREVIEW_W, PREVIEW_H), "RGB").copy()
                self.dbg_surf = pygame.image.frombuffer(st.debug, (PREVIEW_W, PREVIEW_H), "RGB").copy()
            if st.big_preview:
                self.big_prev = pygame.image.frombuffer(st.big_preview, (PREVIEW_W * 2, PREVIEW_H * 2), "RGB").copy()
                self.big_dbg = pygame.image.frombuffer(st.big_debug, (PREVIEW_W * 2, PREVIEW_H * 2), "RGB").copy()

        if st.present and st.palm:
            self.last_seen = self.t
            inp.present = True
            inp.gesture = st.gesture
            inp.fingers = st.fingers
            reg = CLASSIC_ROI if st.classic else AIM_REGION
            inp.cursor = self.cur_filter(self._map(st.palm, reg), dt)
            inp.tip = self.tip_filter(self._map(st.tip or st.palm, reg), dt)
        elif self.t - self.last_seen > HAND_LOST_GRACE:
            # el kısa süre kaybolursa (bulanıklık vb.) son işaret korunur -> akıcılık
            inp.present = False
            inp.gesture = NONE
        return st

    @staticmethod
    def _map(p, region=AIM_REGION):
        x0, y0, x1, y1 = region
        pad = 0.06
        x0, x1 = x0 + (x1 - x0) * pad, x1 - (x1 - x0) * pad
        y0, y1 = y0 + (y1 - y0) * pad, y1 - (y1 - y0) * pad
        x = (p[0] - x0) / (x1 - x0)
        y = (p[1] - y0) / (y1 - y0)
        return (min(max(x, 0), 1) * SCREEN_W, min(max(y, 0), 1) * SCREEN_H)

    # ---- "tut ve seç" ----
    def hold(self, value, dt):
        if value != self.hold_val:
            self.hold_val, self.hold_t, self.hold_used = value, 0.0, False
            return False
        if value is None or self.hold_used:
            return False
        self.hold_t += dt
        if self.hold_t >= HOLD_TO_SELECT:
            self.hold_used = True
            self.sfx.play("select", 0.5)
            return True
        return False

    def hold_progress(self, value):
        if self.hold_val != value or self.hold_used:
            return 0.0
        return min(1.0, self.hold_t / HOLD_TO_SELECT)

    # ================================================================== büyüler
    def mark_cast(self, name):
        self.casting = name
        self.cast_t = 0.35

    def try_rune(self, final):
        """final=True: parmak indirildi. False: parmak durdu (otomatik deneme)."""
        pts = self.rune_pts
        if len(pts) < RUNE_MIN_POINTS:
            if final:
                self.rune_pts = []
            return
        length = sum(math.dist(pts[i - 1], pts[i]) for i in range(1, len(pts)))
        if length < RUNE_MIN_LENGTH:
            if final:
                self.rune_pts = []
            return
        name, score = self.runes.recognize(pts)
        if name is None or score < RUNE_MIN_SCORE:
            if final:
                self.rune_pts = []
                self.show_msg(f"Rün tanınamadı  •  benzerlik %{int(max(score, 0) * 100)}", (255, 150, 150))
                self.sfx.play("fail", 0.5)
            return
        self.rune_pts = []
        cost = COST_METEOR if name == "daire" else COST_LIGHTNING
        if self.mana < cost:
            self.show_msg(f"Yetersiz mana  •  {cost} gerekli", (130, 170, 255))
            self.sfx.play("fail", 0.5)
            return
        self.mana -= cost
        self.sfx.play("rune", 0.6)
        alive = [e for e in self.enemies if e.alive]
        if name == "daire":
            self.mark_cast("METEOR")
            self.show_msg(f"METEOR YAĞMURU  •  benzerlik %{int(score * 100)}", (255, 170, 80), 2.0)
            targets = [e.x for e in sorted(alive, key=lambda e: -e.hp)[:6]]
            while len(targets) < 9:
                targets.append(random.uniform(420, SCREEN_W - 60))
            for i, tx in enumerate(targets):
                self.projectiles.append(Meteor(tx, i * 0.12))
        else:
            self.mark_cast("YILDIRIM")
            self.show_msg(f"YILDIRIM  •  benzerlik %{int(score * 100)}", (190, 210, 255), 2.0)
            self.fx.add_flash(0.7, (200, 210, 255))
            self.fx.add_shake(10)
            self.sfx.play("thunder", 0.8)
            for e in sorted(alive, key=lambda e: -e.hp)[:6]:
                self.fx.bolts.append(Bolt(e.x + random.uniform(-80, 80), -10, e.x, e.y))
                e.stun = 1.4
                e.hit(95 + self.spell_bonus, self, (200, 220, 255))
                self.fx.burst(e.x, e.y, (170, 200, 255), 14, 220, 0.5, 4)

    def update_target(self):
        """Nişan yardımı: imlece en yakın düşmana kilitlen."""
        self.target = None
        if not self.inp.present or self.inp.gesture == POINT:
            return
        cx, cy = self.inp.cursor
        best, bd = None, AIM_ASSIST_RADIUS
        for e in self.enemies:
            if e.alive and e.x < SCREEN_W - 5:
                d = math.hypot(e.x - cx, e.y - cy) - e.r
                if d < bd:
                    best, bd = e, d
        self.target = best

    def aim_point(self):
        if self.target is not None and self.target.alive:
            return self.target.x, self.target.y
        return self.inp.cursor

    def do_spells(self, dt):
        g = self.inp.gesture
        # ✊ Yumruk: şarj -> herhangi bir açılışta fırlat
        if g == FIST:
            if self.prev_g != FIST:
                self.sfx.play("charge", 0.35)
            self.charge = min(1.0, self.charge + dt / FIST_CHARGE_TIME)
            if random.random() < 0.5:
                self.fx.trail(STAFF_TIP[0] + random.uniform(-20, 20), STAFF_TIP[1] + random.uniform(-20, 20),
                              (255, 130, 30), 4, 0.3, 40)
        elif self.prev_g == FIST and g != NONE:
            if self.charge >= 0.08:
                if self.mana >= COST_FIREBALL:
                    self.mana -= COST_FIREBALL
                    tx, ty = self.aim_point()
                    self.projectiles.append(Fireball(STAFF_TIP[0], STAFF_TIP[1], tx, ty, self.charge, self.target))
                    self.sfx.play("fire", 0.5 + 0.4 * self.charge)
                    self.mark_cast("ATEŞ TOPU")
                else:
                    self.show_msg("Yetersiz mana!", (130, 170, 255), 0.8)
            self.charge = 0.0
        elif g == NONE:
            self.charge = 0.0

        # ✋ Açık el: kısa süre tutunca kalkan
        self.open_t = self.open_t + dt if g == OPEN else 0.0
        was = self.shield
        self.shield = self.open_t >= SHIELD_HOLD_TIME and self.mana > 1
        if self.shield:
            self.mana = max(0.0, self.mana - SHIELD_DRAIN * dt)
            if not was:
                self.sfx.play("shield", 0.5)

        # ✌ V işareti: buz okları
        self.ice_cd -= dt
        if g == VICTORY and self.ice_cd <= 0:
            if self.mana >= COST_ICE:
                self.mana -= COST_ICE
                tx, ty = self.aim_point()
                self.projectiles.append(IceShard(STAFF_TIP[0], STAFF_TIP[1], tx, ty))
                self.sfx.play("ice", 0.35)
                self.mark_cast("BUZ OKU")
            self.ice_cd = ICE_INTERVAL

        # ☝ İşaret parmağı: rün çiz (parmak durursa veya inerse tanı)
        if g == POINT:
            tip = self.inp.tip
            if not self.rune_pts or math.dist(self.rune_pts[-1], tip) > 5:
                self.rune_pts.append(tip)
                self.rune_still = 0.0
                if len(self.rune_pts) > 400:
                    self.rune_pts.pop(0)
            else:
                self.rune_still += dt
                if self.rune_still >= RUNE_DWELL_TIME:
                    self.rune_still = -1.0          # aynı duruşta tekrar denemesin
                    self.try_rune(final=False)
        elif self.prev_g == POINT:
            self.try_rune(final=True)
        self.prev_g = g

    # ================================================================== güncelleme
    def update_play(self, dt):
        self.play_time += dt
        if self.queue:
            self.spawn_t -= dt
            if self.spawn_t <= 0:
                kind = self.queue.pop(0)
                self.enemies.append(Enemy(kind, self.wave))
                if kind == "boss":
                    self.sfx.play("boss", 0.8)
                    self.fx.add_shake(8)
                fast = kind == "yarasa" and self.queue and self.queue[0] == "yarasa"
                self.spawn_t = 0.18 if fast else max(0.4, 1.45 - 0.08 * self.wave) * random.uniform(0.7, 1.3)
        self.mana = min(MANA_MAX, self.mana + MANA_REGEN * dt * (0.25 if self.shield else 1))
        self.update_target()
        self.do_spells(dt)
        for e in self.enemies:
            e.update(dt, self)
        for p in self.projectiles:
            p.update(dt, self)
        for o in self.orbs:
            o.update(dt, self)
        for a in self.apprentices + self.elves + self.fairies:
            a.update(dt, self)
        if self.golem:
            self.golem.update(dt, self)
        self.enemies = [e for e in self.enemies if e.alive]
        self.projectiles = [p for p in self.projectiles if p.alive]
        self.orbs = [o for o in self.orbs if o.alive]
        if self.combo_t > 0:
            self.combo_t -= dt
            if self.combo_t <= 0:
                self.combo = 0

        if self.tower_hp <= 0:
            self.tower_hp = 0
            self.best = max(self.best, self.score)
            self.set_state(OVER)
            self.fx.add_shake(20)
            self.fx.burst(TOWER_X, TOWER_TOP + 100, (150, 140, 160), 80, 400, 1.4, 8, 500, glow=False)
            self.sfx.play("boom", 1.0)
            self.sfx.play("gameover", 0.7)
            return
        if not self.queue and not self.enemies:
            self.wave_bonus = 20 + 6 * self.wave
            self.gold += self.wave_bonus
            self.projectiles = []
            self.rune_pts = []
            self.charge = 0
            self.shield = False
            self.combo = 0
            self.combo_t = 0
            self.set_state(SHOP)
            self.sfx.play("clear", 0.6)

    # ---- dükkân ----
    def item_price(self, idx):
        n, name, desc, base, inc = SHOP_ITEMS[idx]
        owned = [len(self.apprentices), len(self.elves), 0, len(self.fairies), self.upgrades][idx]
        return base + inc * owned

    def item_owned(self, idx):
        return [len(self.apprentices), len(self.elves), int(bool(self.golem and self.golem.alive)),
                len(self.fairies), self.upgrades][idx]

    def item_max(self, idx):
        return [len(APPRENTICE_SLOTS), len(ELF_SLOTS), 1, 2, 0][idx]

    def item_status(self, idx):
        mx = self.item_max(idx)
        if mx and self.item_owned(idx) >= mx:
            return "MAKS" if idx != 2 else "AYAKTA"
        if self.gold < self.item_price(idx):
            return "ALTIN YOK"
        return None

    def buy(self, idx):
        st = self.item_status(idx)
        if st:
            self.show_msg({"MAKS": "Bu yardımcıdan en fazla sayıda var", "AYAKTA": "Golem zaten ayakta",
                           "ALTIN YOK": "Yeterli altın yok!"}[st], (255, 140, 140))
            self.sfx.play("fail", 0.5)
            return
        self.gold -= self.item_price(idx)
        if idx == 0:
            self.apprentices.append(Apprentice(len(self.apprentices)))
        elif idx == 1:
            self.elves.append(Elf(len(self.elves)))
        elif idx == 2:
            self.golem = Golem()
        elif idx == 3:
            self.fairies.append(Fairy(len(self.fairies)))
        else:
            self.upgrades += 1
            self.tower_max += 40
            self.tower_hp = self.tower_max
            self.spell_bonus += 12
            self.ice_bonus += 3
        self.show_msg(f"{SHOP_ITEMS[idx][1]} alındı!", ui.GREEN)
        self.sfx.play("buy", 0.6)
        self.fx.burst(self.card_center(idx)[0], 260, ui.GOLD, 30, 300, 0.8, 5)

    def update_shop(self, dt):
        val = None
        if not self.mouse_mode and self.inp.present:
            g = self.inp.gesture
            val = {FIST: 0, POINT: 1, VICTORY: 2}.get(g, self.inp.fingers)
        if self.hold(val, dt):
            if val == 0:
                self.start_wave()
            elif val is not None and 1 <= val <= 5:
                self.buy(val - 1)

    def update(self, dt):
        self.t += dt
        if self.state == PLAY and not self.paused:
            self.update_play(dt)
        elif self.state == SHOP:
            self.update_shop(dt)
            for a in self.fairies + self.preview_allies:
                if a is not self.preview_allies[2]:
                    a.t += dt
        elif self.state in (MENU, OVER):
            val = OPEN if self.inp.present and self.inp.gesture == OPEN else None
            if self.hold(val, dt) and val == OPEN:
                self.begin()
        if not self.paused:
            self.fx.update(dt)
        # yumuşak animasyonlu göstergeler
        ratio = self.tower_hp / self.tower_max
        self.hp_trail = ratio if self.hp_trail < ratio else self.hp_trail - (self.hp_trail - ratio) * min(1, dt * 2.5)
        self.disp_gold += (self.gold - self.disp_gold) * min(1, dt * 8)
        self.disp_score += (self.score - self.disp_score) * min(1, dt * 6)
        self.fade = max(0.0, self.fade - dt)
        self.hurt = max(0.0, self.hurt - dt)
        self.cast_t = max(0.0, self.cast_t - dt)
        if self.banner[2] > 0:
            self.banner = (self.banner[0], self.banner[1], self.banner[2] - dt)
        if self.msg[1] > 0:
            self.msg = (self.msg[0], self.msg[1] - dt, self.msg[2])

    def begin(self):
        self.reset()
        self.sfx.play("start", 0.6)
        self.start_wave()

    # ================================================================== olaylar
    def handle_event(self, ev):
        if ev.type == pygame.QUIT:
            return False
        if ev.type == pygame.KEYDOWN:
            k = ev.key
            if k == pygame.K_ESCAPE:
                return False
            if k == pygame.K_TAB:
                self.debug = not self.debug
                self.vision.want_big = self.debug
            elif k == pygame.K_e:
                self.vision.toggle_engine()
                self.show_msg("Tanıma motoru değiştiriliyor...", (200, 230, 255))
            elif k == pygame.K_c:
                self.vision.calibrate()
                self.show_msg("Ten rengi kalibre edildi (klasik motor)", (255, 180, 255))
            elif k == pygame.K_m:
                self.mouse_mode = not self.mouse_mode
                self.show_msg("Fare modu " + ("AÇIK" if self.mouse_mode else "KAPALI"), (255, 255, 160))
            elif k == pygame.K_n:
                on = self.sfx.toggle()
                self.show_msg("Ses ve müzik " + ("AÇIK" if on else "KAPALI"), (200, 230, 255))
            elif k == pygame.K_p and self.state == PLAY:
                self.paused = not self.paused
            elif k == pygame.K_F11:
                pygame.display.toggle_fullscreen()
            elif k in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.state in (MENU, OVER):
                    self.begin()
                elif self.state == SHOP:
                    self.start_wave()
            elif self.state == SHOP and pygame.K_1 <= k <= pygame.K_5:
                self.buy(k - pygame.K_1)
        return True

    # ================================================================== çizim: dünya
    def draw_world(self, s):
        s.blit(self.bg, (0, 0))
        draw_tower(s, self.tower_img, self.t, self.tower_hp / self.tower_max)
        g = self.inp.gesture
        orb = {FIST: (255, 120, 30), VICTORY: (60, 150, 255), OPEN: (200, 220, 255),
               POINT: (190, 90, 255)}.get(g, (130, 80, 230))
        draw_wizard(s, self.t, orb, self.charge)
        if self.golem:
            self.golem.draw(s)
        for a in self.apprentices + self.elves:
            a.draw(s)
        for e in sorted(self.enemies, key=lambda e: e.flying):
            e.draw(s)
        for o in self.orbs:
            o.draw(s)
        for f in self.fairies:
            f.draw(s)
        for p in self.projectiles:
            p.draw(s)
        if self.shield:
            r = 150 + int(math.sin(self.t * 8) * 4)
            sh = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(sh, (120, 180, 255, 45), (r, r), r)
            pygame.draw.circle(sh, (190, 225, 255, 160), (r, r), r, 4)
            for i in range(6):
                a = self.t * 1.5 + i * math.pi / 3
                pygame.draw.circle(sh, (230, 245, 255, 200),
                                   (int(r + math.cos(a) * (r - 6)), int(r + math.sin(a) * (r - 6))), 4)
            s.blit(sh, (TOWER_X - r + 30, TOWER_TOP + 140 - r))
        self.fx.draw(s, lambda size: ui.font(size))

    def draw_cursor(self, s):
        inp = self.inp
        if self.rune_pts and len(self.rune_pts) > 1:
            pygame.draw.lines(s, (110, 45, 190), False, self.rune_pts, 12)
            pygame.draw.lines(s, (240, 210, 255), False, self.rune_pts, 4)
            for p in self.rune_pts[::4]:
                draw_glow(s, (int(p[0]), int(p[1])), 18, (90, 40, 150))
        # hedef kilidi
        tg = self.target
        if tg is not None and tg.alive:
            r = tg.r + 14 + int(math.sin(self.t * 8) * 3)
            col = ui.FIRE if inp.gesture == FIST else (ui.ICE if inp.gesture == VICTORY else (255, 235, 140))
            for i in range(4):
                a = self.t * 2 + i * math.pi / 2
                rect = pygame.Rect(int(tg.x - r), int(tg.y - r), r * 2, r * 2)
                pygame.draw.arc(s, col, rect, a, a + 0.7, 3)
        if not inp.present:
            return
        x, y = int(inp.cursor[0]), int(inp.cursor[1])
        g = inp.gesture
        col = {FIST: ui.FIRE, VICTORY: ui.ICE, OPEN: ui.SHIELD, POINT: ui.ARCANE}.get(g, (255, 255, 255))
        if g == POINT:
            tx, ty = int(inp.tip[0]), int(inp.tip[1])
            draw_glow(s, (tx, ty), 28, (150, 80, 255))
            pygame.draw.circle(s, (255, 255, 255), (tx, ty), 6)
            if self.rune_still > 0.05:
                ui.ring(s, (tx, ty), 16, min(1, self.rune_still / RUNE_DWELL_TIME), ui.ARCANE, 3)
            return
        if tg is not None and tg.alive:                       # imleçten hedefe ince çizgi
            pygame.draw.line(s, (*col,), (x, y), (int(tg.x), int(tg.y)), 1)
        pygame.draw.circle(s, col, (x, y), 20, 2)
        pygame.draw.circle(s, col, (x, y), 3)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            pygame.draw.line(s, col, (x + dx * 12, y + dy * 12), (x + dx * 28, y + dy * 28), 2)
        if self.charge > 0:
            ui.ring(s, (x, y), 30, self.charge, ui.FIRE, 5, bg=(60, 30, 20))
            draw_glow(s, (x, y), int(10 + 30 * self.charge), (120, 50, 10))
        if g == OPEN and not self.shield and self.state == PLAY:
            ui.ring(s, (x, y), 30, min(1.0, self.open_t / SHIELD_HOLD_TIME), ui.SHIELD, 3)

    # ================================================================== çizim: HUD
    def draw_hud(self, s, st):
        W, H = SCREEN_W, SCREEN_H
        # --- sol üst: kule & mana
        ui.panel(s, (16, 12, 344, 88))
        ui.icon_heart(s, (40, 36), 22)
        ui.text(s, "KULE", (58, 24), 15, ui.MUTED, heading=True, shadow=False)
        ui.text(s, f"{int(self.tower_hp)} / {self.tower_max}", (344, 24), 15, ui.TEXT, anchor="topright", shadow=False)
        ui.bar(s, (58, 44, 286, 12), self.tower_hp / self.tower_max, ui.HP, trail=self.hp_trail)
        ui.icon_drop(s, (40, 76), 22)
        ui.text(s, "MANA", (58, 64), 15, ui.MUTED, heading=True, shadow=False)
        ui.text(s, f"{int(self.mana)}", (344, 64), 15, ui.TEXT, anchor="topright", shadow=False)
        ui.bar(s, (58, 84 - 0, 286, 9), self.mana / MANA_MAX, ui.MANA,
               ticks=(COST_LIGHTNING / MANA_MAX, COST_METEOR / MANA_MAX))

        # --- orta üst: dalga
        if self.state != MENU:
            ui.panel(s, (W // 2 - 150, 12, 300, 64))
            ui.text(s, f"DALGA {self.wave}", (W // 2, 18), 26, (255, 228, 150), anchor="midtop", heading=True)
            prog = self.wave_killed / max(1, self.wave_total)
            ui.bar(s, (W // 2 - 120, 54, 240, 8), prog, ui.ARCANE, radius=4)
            left = len(self.queue) + len(self.enemies)
            ui.icon_skull(s, (W // 2 + 104, 32), 18)
            ui.text(s, str(left), (W // 2 + 118, 24), 16, ui.TEXT, shadow=False)

        # --- sağ üst: altın & skor
        ui.panel(s, (W - 260, 12, 244, 64))
        ui.icon_coin(s, (W - 234, 34), 24)
        ui.text(s, fmt(self.disp_gold), (W - 214, 18), 26, ui.GOLD, heading=True)
        ui.text(s, "SKOR", (W - 236, 50), 14, ui.MUTED, heading=True, shadow=False)
        ui.text(s, fmt(self.disp_score), (W - 30, 48), 17, ui.TEXT, anchor="topright", shadow=False)

        # --- sağ: kamera paneli
        self.draw_camera_panel(s, st, W - 260, 84)

        # --- kombo
        if self.combo >= 2 and self.state == PLAY:
            pulse = 1 + 0.08 * max(0, self.combo_t - 2.3) / 0.3
            size = int((30 + min(self.combo, 20)) * pulse)
            col = (255, 230, 120) if self.combo < 10 else (255, 140, 80)
            ui.text(s, f"x{self.combo} KOMBO", (W // 2, 84), size, col, anchor="midtop", heading=True)
            ui.bar(s, (W // 2 - 60, 88 + size, 120, 5), self.combo_t / 2.6, col, radius=3)

        # --- boss barı
        boss = next((e for e in self.enemies if e.kind == "boss"), None)
        if boss:
            ui.panel(s, (W // 2 - 230, 150, 460, 46), border=(150, 70, 200))
            ui.text(s, "GÖLGE LORDU", (W // 2, 154), 16, (220, 170, 255), anchor="midtop", heading=True)
            ui.bar(s, (W // 2 - 210, 176, 420, 12), boss.hp / boss.max_hp, (180, 70, 255), radius=6)

        if self.state == PLAY:
            self.draw_spellbar(s)            # alt orta: büyü çubuğu
            self.draw_gesture_panel(s, st)   # sol alt: algılanan işaret

        if not self.inp.present and self.state == PLAY and st.cam_ok and not self.mouse_mode:
            ui.panel(s, (W // 2 - 170, 262, 340, 44), border=(200, 80, 90))
            ui.text(s, "Elini kameraya göster!", (W // 2, 272), 20, (255, 150, 150), anchor="midtop")

    def draw_camera_panel(self, s, st, x, y):
        w = PREVIEW_W + 20
        h = PREVIEW_H + 66
        ui.panel(s, (x, y, w, h))
        ok = st.cam_ok and st.ready and not self.mouse_mode
        dot = ui.GREEN if (ok and st.present) else ((255, 200, 80) if ok else (240, 80, 80))
        pygame.draw.circle(s, dot, (x + 18, y + 17), 5)
        title = "FARE MODU" if self.mouse_mode else "KAMERA"
        ui.text(s, title, (x + 30, y + 8), 14, ui.MUTED, heading=True, shadow=False)
        eng = "" if self.mouse_mode else ("MediaPipe" if "MediaPipe" in (st.engine or "") else
                                          ("Klasik" if st.engine else ""))
        if eng:
            ui.chip(s, eng, (x + w - 10, y + 7), 12, ui.TEXT, (60, 46, 100), anchor="topright")
        px, py = x + 10, y + 30
        if self.prev_surf and not self.mouse_mode and st.cam_ok:
            s.blit(self.prev_surf, (px, py))
            pygame.draw.rect(s, (0, 0, 0), (px, py, PREVIEW_W, PREVIEW_H), 2)
        else:
            pygame.draw.rect(s, (8, 6, 16), (px, py, PREVIEW_W, PREVIEW_H), border_radius=6)
            msg = "Fare ile oynuyorsun" if self.mouse_mode else (st.status or "Kamera bekleniyor")
            ui.text(s, msg, (px + PREVIEW_W // 2, py + PREVIEW_H // 2), 14, ui.MUTED, anchor="center")
        fy = py + PREVIEW_H + 8
        r = ui.chip(s, f"{st.proc_ms:.0f} ms", (px, fy), 12, ui.TEXT)
        r = ui.chip(s, f"Kamera {st.cam_fps:.0f}", (r.right + 6, fy), 12, ui.TEXT)
        ui.chip(s, f"Oyun {self.game_fps:.0f}", (r.right + 6, fy), 12, ui.TEXT)

    def draw_spellbar(self, s):
        sw, sh, gap = 92, 88, 10
        total = sw * 5 + gap * 4
        x0, y0 = SCREEN_W // 2 - total // 2, SCREEN_H - sh - 14
        g = self.inp.gesture
        for i, (icon, name, cost, col, trig, rune) in enumerate(SPELLS):
            x = x0 + i * (sw + gap)
            active = (g == trig) or (self.casting == name and self.cast_t > 0)
            if trig == POINT and g == POINT:
                active = True
            afford = self.mana >= cost
            border = col if active else ui.BORDER
            ui.panel(s, (x, y0, sw, sh), alpha=215, border=border, glow=(col[0] // 6, col[1] // 6, col[2] // 6) if active else None)
            # ateş topu şarj dolumu / kalkan dolumu
            fill = 0.0
            if trig == FIST:
                fill = self.charge
            elif trig == OPEN:
                fill = 1.0 if self.shield else min(1.0, self.open_t / SHIELD_HOLD_TIME)
            if fill > 0:
                fh = int((sh - 6) * fill)
                fs = pygame.Surface((sw - 6, fh), pygame.SRCALPHA)
                fs.fill((*col, 60))
                s.blit(fs, (x + 3, y0 + sh - 3 - fh))
            icol = col if (active or afford) else (90, 86, 110)
            ui.hand(s, icon, (x + sw // 2 - (8 if rune else 0), y0 + 34), 40, icol)
            if rune == "daire":
                pygame.draw.circle(s, icol, (x + sw - 22, y0 + 22), 9, 2)
            elif rune == "simsek":
                pygame.draw.lines(s, icol, False, [(x + sw - 30, y0 + 14), (x + sw - 16, y0 + 16),
                                                   (x + sw - 28, y0 + 28), (x + sw - 14, y0 + 30)], 2)
            ui.text(s, name, (x + sw // 2, y0 + 62), 13, ui.TEXT if afford else ui.MUTED, anchor="midtop",
                    heading=True, shadow=False)
            ctext = f"{cost}" if cost else "/sn"
            pygame.draw.circle(s, (30, 40, 90) if afford else (70, 30, 40), (x + 14, y0 + 14), 11)
            ui.text(s, ctext if cost else "~", (x + 14, y0 + 14), 11, ui.TEXT, anchor="center", shadow=False)

    def draw_gesture_panel(self, s, st):
        x, y, w, h = 16, SCREEN_H - 102, 258, 88
        ui.panel(s, (x, y, w, h))
        g = self.inp.gesture
        cx, cy = x + 46, y + h // 2
        pygame.draw.circle(s, (40, 32, 70), (cx, cy), 32)
        col = {FIST: ui.FIRE, VICTORY: ui.ICE, OPEN: ui.SHIELD, POINT: ui.ARCANE}.get(g, ui.MUTED)
        if g in GESTURE_ICON:
            ui.hand(s, GESTURE_ICON[g], (cx, cy + 4), 44, col)
        else:
            ui.text(s, "?", (cx, cy), 30, ui.MUTED, anchor="center", heading=True)
        pygame.draw.circle(s, col, (cx, cy), 32, 2)
        ui.text(s, "ALGILANAN İŞARET", (x + 90, y + 14), 12, ui.MUTED, heading=True, shadow=False)
        name = "Fare modu" if self.mouse_mode else GESTURE_TR.get(g, g)
        ui.text(s, name, (x + 90, y + 30), 21, ui.TEXT, heading=True)
        tg = self.target
        if self.state == PLAY and tg is not None and tg.alive:
            ui.text(s, f"Hedef: {ENEMY_TR[tg.kind]}", (x + 90, y + 60), 14, (255, 220, 140), shadow=False)
        elif not self.mouse_mode and st.cam_ok:
            ui.text(s, f"{st.fingers} parmak" if self.inp.present else "El aranıyor...", (x + 90, y + 60), 14,
                    ui.MUTED, shadow=False)

    # ================================================================== çizim: ekranlar
    def card_center(self, i):
        cw, gap = 214, 18
        x0 = SCREEN_W // 2 - (cw * 5 + gap * 4) // 2
        return x0 + i * (cw + gap) + cw // 2, 0

    def draw_menu(self, s, st):
        W, H = SCREEN_W, SCREEN_H
        ui.overlay(s, 150)
        ui.vignette(s)
        cx = W // 2
        draw_glow(s, (cx, 110), 190, (55, 22, 95))
        ui.text(s, "RÜN KULESİ", (cx, 48), 92, (240, 214, 255), anchor="midtop", heading=True)
        ui.text(s, "El işaretleriyle büyü yap  •  kuleni dalgalara karşı koru", (cx, 154), 22, ui.MUTED,
                anchor="midtop", shadow=False)
        cards = [("fist", "ATEŞ TOPU", "Yumruk tut, eli aç", ui.FIRE, None),
                 ("v", "BUZ OKU", "V işaretini tut", ui.ICE, None),
                 ("open", "KALKAN", "Açık eli tut", ui.SHIELD, None),
                 ("point", "METEOR", "Parmakla daire çiz", (255, 130, 60), "daire"),
                 ("point", "YILDIRIM", "Parmakla zikzak çiz", (200, 210, 255), "simsek")]
        cw, ch, gap = 196, 176, 16
        x0 = cx - (cw * 5 + gap * 4) // 2
        for i, (ic, name, how, col, rune) in enumerate(cards):
            x = x0 + i * (cw + gap)
            y = 206 + int(math.sin(self.t * 2 + i * 0.7) * 3)
            ui.panel(s, (x, y, cw, ch), alpha=210)
            pygame.draw.rect(s, col, (x + 16, y + 2, cw - 32, 3), border_radius=2)
            ui.hand(s, ic, (x + cw // 2 - (10 if rune else 0), y + 62), 64, col)
            if rune == "daire":
                pygame.draw.circle(s, col, (x + cw - 40, y + 40), 14, 3)
            elif rune == "simsek":
                pygame.draw.lines(s, col, False, [(x + cw - 54, y + 26), (x + cw - 30, y + 30),
                                                  (x + cw - 52, y + 50), (x + cw - 28, y + 54)], 3)
            ui.text(s, name, (x + cw // 2, y + 110), 20, ui.TEXT, anchor="midtop", heading=True)
            ui.text(s, how, (x + cw // 2, y + 140), 15, ui.MUTED, anchor="midtop", shadow=False)
        # başlat halkası
        ry = 486
        prog = self.hold_progress(OPEN)
        draw_glow(s, (cx, ry), 70 + int(prog * 30), (20, 70, 40))
        pygame.draw.circle(s, (24, 20, 44), (cx, ry), 46)
        ui.ring(s, (cx, ry), 50, prog, ui.GREEN, 7)
        ui.hand(s, "open", (cx, ry + 6), 54, ui.GREEN if self.inp.present and self.inp.gesture == OPEN else ui.TEXT)
        ui.text(s, "Başlamak için AÇIK ELİ TUT", (cx, 548), 24, ui.GREEN, anchor="midtop", heading=True)
        ui.text(s, "ya da ENTER", (cx, 580), 15, ui.MUTED, anchor="midtop", shadow=False)
        # durum
        if self.mouse_mode:
            status, col = "Fare modu açık", (255, 230, 150)
        elif not st.cam_ok:
            status, col = st.status, (255, 140, 140)
        elif not st.ready:
            status, col = st.status, (255, 220, 140)
        else:
            status, col = ("El algılandı  •  " + GESTURE_TR.get(self.inp.gesture, "")) if self.inp.present else \
                "Kamera hazır  •  elini göster", ui.GREEN
        ui.chip(s, status, (cx, 612), 15, col, (30, 26, 54), anchor="midtop")
        keys = ["TAB  Debug", "E  Motor", "C  Kalibrasyon", "M  Fare", "N  Ses", "P  Duraklat", "F11  Tam ekran", "ESC  Çıkış"]
        total = sum(ui.font(13).size(k)[0] + 22 for k in keys)
        kx = cx - total // 2
        for k in keys:
            r = ui.chip(s, k, (kx, 668), 13, ui.MUTED, (26, 22, 46))
            kx = r.right + 6

    def draw_over(self, s):
        W, H = SCREEN_W, SCREEN_H
        ui.overlay(s, 175)
        ui.vignette(s)
        cx = W // 2
        pw, ph = 600, 440
        px, py = cx - pw // 2, 120
        ui.panel(s, (px, py, pw, ph), alpha=225, border=(200, 70, 90))
        ui.text(s, "KULE YIKILDI", (cx, py + 24), 54, (255, 110, 120), anchor="midtop", heading=True)
        ui.text(s, "Rün Kulesi düştü... ama büyü bitmedi.", (cx, py + 88), 17, ui.MUTED, anchor="midtop",
                shadow=False)
        m, sec = divmod(int(self.play_time), 60)
        stats = [("SKOR", fmt(self.score), ui.GOLD), ("DALGA", str(self.wave), (255, 228, 150)),
                 ("ÖLDÜRME", str(self.kills), ui.TEXT), ("EN İYİ KOMBO", f"x{self.best_combo}", ui.FIRE),
                 ("SÜRE", f"{m}:{sec:02d}", ui.TEXT), ("REKOR", fmt(self.best), ui.GREEN)]
        for i, (k, v, c) in enumerate(stats):
            col, row = i % 3, i // 3
            bx, by = px + 30 + col * 184, py + 130 + row * 96
            ui.panel(s, (bx, by, 170, 82), alpha=160, border=(70, 60, 110), radius=10)
            ui.text(s, k, (bx + 85, by + 12), 13, ui.MUTED, anchor="midtop", heading=True, shadow=False)
            ui.text(s, v, (bx + 85, by + 34), 28, c, anchor="midtop", heading=True)
        ry = py + ph - 64
        ui.ring(s, (cx - 150, ry), 30, self.hold_progress(OPEN), ui.GREEN, 6)
        ui.hand(s, "open", (cx - 150, ry + 4), 34, ui.TEXT)
        ui.text(s, "Açık eli tut  →  yeniden başla", (cx - 105, ry - 14), 21, ui.GREEN, heading=True)
        ui.text(s, "ya da ENTER", (cx - 105, ry + 12), 14, ui.MUTED, shadow=False)

    def draw_shop(self, s):
        W, H = SCREEN_W, SCREEN_H
        ui.overlay(s, 180)
        ui.vignette(s)
        cx = W // 2
        ui.text(s, f"DALGA {self.wave} TAMAMLANDI", (cx, 34), 42, (255, 228, 150), anchor="midtop", heading=True)
        r = ui.chip(s, f"Dalga bonusu  +{self.wave_bonus}", (cx - 8, 92), 16, ui.GOLD, (50, 40, 20), anchor="topright")
        ui.chip(s, f"Altın  {fmt(self.gold)}", (cx + 8, 92), 16, ui.GOLD, (50, 40, 20))
        hint = "1-5 tuşları ile satın al  •  ENTER sonraki dalga" if self.mouse_mode else \
            "Parmak sayısını göster ve TUT  →  satın al"
        ui.text(s, hint, (cx, 128), 17, ui.MUTED, anchor="midtop", shadow=False)
        cw, ch, gap = 214, 318, 18
        x0 = cx - (cw * 5 + gap * 4) // 2
        for i, (n, name, desc, base, inc) in enumerate(SHOP_ITEMS):
            sel = self.hold_val == n and not self.mouse_mode
            status = self.item_status(i)
            x, y = x0 + i * (cw + gap), 166 - (10 if sel else 0)
            ui.panel(s, (x, y, cw, ch), alpha=220, border=ui.GOLD if sel else ui.BORDER,
                     glow=(60, 45, 10) if sel else None)
            # portre alanı
            pygame.draw.rect(s, (26, 20, 48), (x + 10, y + 10, cw - 20, 150), border_radius=10)
            pcx, pby = x + cw // 2, y + 150
            if i < 4:
                a = self.preview_allies[i]
                if i == 0:
                    a.x, a.y = pcx - 10, pby - 40
                elif i == 1:
                    a.x, a.y = pcx - 6, pby - 50
                elif i == 2:
                    a.x, a.y = pcx, pby + 2
                else:
                    a.x, a.y = pcx + math.cos(self.t * 2) * 30, pby - 70 + math.sin(self.t * 3) * 14
                a.draw(s)
            else:
                ui.icon_tower(s, (pcx, pby - 64), 90)
            # el ikonu (kaç parmak)
            pygame.draw.circle(s, (40, 32, 70), (x + 30, y + 32), 20)
            ui.hand(s, f"n{n}", (x + 30, y + 35), 28, ui.GOLD if sel else ui.TEXT)
            ui.text(s, str(n), (x + 30, y + 54), 12, ui.MUTED, anchor="midtop", shadow=False)
            ui.text(s, name, (x + cw // 2, y + 170), 21, ui.TEXT, anchor="midtop", heading=True)
            # açıklama (satır kaydırma)
            words, line, ly = desc.split(), "", y + 200
            for wd in words:
                if ui.font(14).size((line + " " + wd).strip())[0] > cw - 24:
                    ui.text(s, line, (x + cw // 2, ly), 14, ui.MUTED, anchor="midtop", shadow=False)
                    line, ly = wd, ly + 19
                else:
                    line = (line + " " + wd).strip()
            ui.text(s, line, (x + cw // 2, ly), 14, ui.MUTED, anchor="midtop", shadow=False)
            # sahip olunan
            mx = self.item_max(i)
            owned = self.item_owned(i)
            if mx:
                for k in range(mx):
                    px_ = x + cw // 2 - (mx - 1) * 9 + k * 18
                    pygame.draw.circle(s, ui.GREEN if k < owned else (60, 54, 90), (px_, y + 254), 6)
            else:
                ui.text(s, f"Seviye {owned}", (x + cw // 2, y + 246), 14, ui.GREEN, anchor="midtop", shadow=False)
            # fiyat
            if status in (None, "ALTIN YOK"):
                ui.icon_coin(s, (x + cw // 2 - 34, y + 284), 18)
                ui.text(s, str(self.item_price(i)), (x + cw // 2 - 20, y + 272), 20,
                        ui.GOLD if status is None else (230, 110, 110), heading=True)
            else:
                ui.chip(s, status, (x + cw // 2, y + 272), 14, ui.GREEN, (30, 60, 40), anchor="midtop")
            if sel:
                pr = self.hold_progress(n)
                pygame.draw.rect(s, (60, 50, 20), (x + 14, y + ch - 10, cw - 28, 5), border_radius=3)
                pygame.draw.rect(s, ui.GOLD, (x + 14, y + ch - 10, int((cw - 28) * pr), 5), border_radius=3)
        # sonraki dalga
        ry = 560
        prog = self.hold_progress(0)
        draw_glow(s, (cx, ry), 60 + int(prog * 30), (70, 30, 10))
        pygame.draw.circle(s, (34, 22, 30), (cx, ry), 38)
        ui.ring(s, (cx, ry), 42, prog, ui.FIRE, 6)
        ui.hand(s, "fist", (cx, ry + 4), 42, ui.FIRE if self.hold_val == 0 else ui.TEXT)
        ui.text(s, "YUMRUĞU TUT  →  SONRAKİ DALGA", (cx, 610), 22, ui.FIRE, anchor="midtop", heading=True)
        if self.inp.present and not self.mouse_mode and self.hold_val is not None:
            v = "Yumruk" if self.hold_val == 0 else f"{self.hold_val} parmak"
            ui.chip(s, f"Algılanan: {v}", (cx, 646), 14, ui.ICE, (26, 30, 56), anchor="midtop")

    def draw_debug(self, s, st):
        ui.overlay(s, 215)
        W = SCREEN_W
        ui.text(s, "GÖRÜNTÜ İŞLEME — CANLI BORU HATTI", (W // 2, 18), 28, (255, 228, 150), anchor="midtop",
                heading=True)
        pw, ph = PREVIEW_W * 2, PREVIEW_H * 2
        x1, x2, y = 60, W - 60 - pw, 66
        for x, title, img in ((x1, "Kamera + tespit", self.big_prev), (x2, "Maske / iskelet", self.big_dbg)):
            ui.panel(s, (x - 10, y - 10, pw + 20, ph + 46), alpha=200)
            if img:
                s.blit(img, (x, y))
            ui.text(s, title, (x, y + ph + 8), 16, ui.MUTED, heading=True, shadow=False)
        lines = [f"Motor: {st.engine}",
                 f"İşleme süresi: {st.proc_ms:.1f} ms   •   Kamera: {st.cam_fps:.1f} FPS   •   Oyun: {self.game_fps:.0f} FPS",
                 f"Ham: {GESTURE_TR.get(st.raw_gesture, '-')}  →  Kararlı (oylama {GESTURE_MIN_VOTES}/{GESTURE_WINDOW}): "
                 f"{GESTURE_TR.get(st.gesture, '-')}   •   Parmak: {st.fingers}"] + list(st.info)
        if self.vision.mp_error:
            lines.append("MediaPipe hatası: " + self.vision.mp_error[:90])
        ty = y + ph + 52
        ui.panel(s, (x1 - 10, ty - 8, W - 100, 22 * len(lines) + 16), alpha=170)
        for i, l in enumerate(lines):
            ui.text(s, l, (x1, ty + i * 22), 15, ui.TEXT, shadow=False)
        ui.text(s, "TAB kapat   •   E motor değiştir   •   C ten rengi kalibrasyonu (eli mor kutuya koy)",
                (W // 2, SCREEN_H - 28), 15, (220, 210, 140), anchor="midtop", shadow=False)

    def draw_banner(self, s):
        title, sub, t = self.banner
        if t <= 0:
            return
        k = min(1.0, (2.6 - t) / 0.25) if t > 2.35 else min(1.0, t / 0.4)
        y = int(232 - (1 - k) * 40)
        a = int(255 * k)
        ui.text(s, title, (SCREEN_W // 2, y), 70, (255, 224, 150), anchor="midtop", heading=True, alpha=a)
        ui.text(s, sub, (SCREEN_W // 2, y + 78), 20, (220, 200, 255), anchor="midtop", alpha=a)

    def draw_toast(self, s):
        m, t, c = self.msg
        if t <= 0:
            return
        a = int(255 * min(1, t * 3))
        y = 208 if self.state == PLAY else 676
        img = ui.text_surf(m, 18, c)
        w = img.get_width() + 40
        ui.panel(s, (SCREEN_W // 2 - w // 2, y, w, 36), alpha=210, border=c)
        ui.text(s, m, (SCREEN_W // 2, y + 18), 18, c, anchor="center", alpha=a)

    def draw(self, st):
        s = self.canvas
        self.draw_world(s)
        if self.state == PLAY:
            self.draw_cursor(s)
        if self.state in (PLAY, SHOP):
            self.draw_hud(s, st)
            self.draw_banner(s)
        if self.state == MENU:
            self.draw_menu(s, st)
        elif self.state == OVER:
            self.draw_over(s)
        elif self.state == SHOP:
            self.draw_shop(s)
            self.draw_camera_panel(s, st, SCREEN_W - 262, SCREEN_H - PREVIEW_H - 68)  # elini görebilmen için
        self.draw_toast(s)
        if self.paused:
            ui.overlay(s, 120)
            ui.panel(s, (SCREEN_W // 2 - 180, 280, 360, 110), alpha=230)
            ui.text(s, "DURAKLATILDI", (SCREEN_W // 2, 298), 36, (255, 240, 170), anchor="midtop", heading=True)
            ui.text(s, "P ile devam et", (SCREEN_W // 2, 346), 16, ui.MUTED, anchor="midtop", shadow=False)
        if self.debug:
            self.draw_debug(s, st)
        if self.hurt > 0:
            ui.overlay(s, int(self.hurt * 120) // 10 * 10, (120, 0, 10))
        if self.fx.flash > 0:
            ui.overlay(s, int(150 * min(1, self.fx.flash)) // 10 * 10, self.fx.flash_color)
        if self.fade > 0:
            ui.overlay(s, int(255 * self.fade / 0.35) // 15 * 15, (0, 0, 0))
        ox = oy = 0
        if self.fx.shake > 0:
            ox = int(random.uniform(-1, 1) * self.fx.shake)
            oy = int(random.uniform(-1, 1) * self.fx.shake)
        if ox or oy:
            self.screen.fill((0, 0, 0))
        self.screen.blit(s, (ox, oy))
        pygame.display.flip()

    # ================================================================== ana döngü
    def step(self, dt):
        st = self.read_input(dt)
        self.update(dt)
        self.draw(st)

    def run(self):
        running = True
        while running:
            dt = min(self.clock.tick(FPS) / 1000.0, 1 / 20)
            self.game_fps = self.clock.get_fps()
            for ev in pygame.event.get():
                if not self.handle_event(ev):
                    running = False
            self.step(dt)
