# -*- coding: utf-8 -*-
"""
Ses efektleri ve arka plan müziği numpy ile SENTEZLENİR (hiç ses dosyası gerekmez).
N tuşu ile ses + müzik açılıp kapatılır.
"""
import numpy as np
import pygame

SR = 22050


def _t(dur):
    return np.arange(int(SR * dur)) / SR


def _env(n, attack=0.01, decay=4.0):
    t = np.linspace(0, 1, n)
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    return a * np.exp(-decay * t)


def _lowpass(x, k):
    k = max(1, int(k))
    return np.convolve(x, np.ones(k) / k, mode="same")


def _sweep(f0, f1, dur, kind="sine"):
    n = int(SR * dur)
    f = np.linspace(f0, f1, n)
    ph = 2 * np.pi * np.cumsum(f) / SR
    if kind == "square":
        return np.sign(np.sin(ph))
    if kind == "saw":
        return 2 * ((ph / (2 * np.pi)) % 1.0) - 1
    if kind == "tri":
        return 2 * np.abs(2 * ((ph / (2 * np.pi)) % 1.0) - 1) - 1
    return np.sin(ph)


def _tone(f, dur, kind="sine"):
    return _sweep(f, f, dur, kind)


def _noise(dur):
    return np.random.uniform(-1, 1, int(SR * dur))


def _echo(x, delays=(0.06, 0.11, 0.17), gain=0.35):
    """Basit yankı (reverb hissi)."""
    out = np.concatenate([x, np.zeros(int(SR * (max(delays) + 0.05)))])
    for i, d in enumerate(delays):
        k = int(SR * d)
        out[k:k + len(x)] += x * gain * (0.75 ** i)
    return out


def _seq(notes, step, kind="sine", decay=6.0):
    parts = []
    for f in notes:
        x = _tone(f, step, kind)
        parts.append(x * _env(len(x), 0.005, decay))
    return np.concatenate(parts)


def _note(n):
    """MIDI nota -> frekans"""
    return 440.0 * 2 ** ((n - 69) / 12)


class Sfx:
    def __init__(self):
        self.ok = False
        self.enabled = True
        self.sounds = {}
        self.music = None
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(SR, -16, 2, 512)
            pygame.mixer.set_num_channels(32)
            self.channels = pygame.mixer.get_init()[2]
            self._build()
            self.ok = True
        except Exception as e:
            print("[Ses] devre dışı:", e)

    # ------------------------------------------------------------------ sesler
    def _build(self):
        S = {}
        n = _noise(0.45)
        S["fire"] = _echo((_lowpass(n, 6) * 0.8 + _sweep(320, 90, 0.45) * 0.5) * _env(len(n), 0.03, 5))
        x = _sweep(1900, 800, 0.16) * 0.6 + _sweep(2600, 1200, 0.16) * 0.3
        S["ice"] = _echo(x * _env(len(x), 0.005, 6), gain=0.25)
        n = _noise(0.9)
        S["boom"] = _echo((_lowpass(n, 30) * 2.2 + _sweep(110, 35, 0.9) * 0.7) * _env(len(n), 0.005, 5))
        n = _noise(0.07)
        S["hit"] = _lowpass(n, 3) * _env(len(n), 0.001, 8) * 0.7
        x = np.concatenate([_tone(988, 0.06), _tone(1319, 0.12)]) * 0.35
        S["coin"] = x * _env(len(x), 0.005, 3)
        n = _noise(1.3)
        crack = (np.random.rand(len(n)) > 0.995).astype(float) * 3
        S["thunder"] = (_lowpass(n, 40) * 2.5 + _lowpass(crack, 4)) * _env(len(n), 0.002, 3.2)
        x = _sweep(140, 90, 0.2, "square") * 0.35
        S["hurt"] = x * _env(len(x), 0.005, 6)
        S["rune"] = _echo(_seq([523, 659, 784, 1047], 0.08, "tri", 3) * 0.45)
        x = _tone(110, 0.9, "saw") * 0.18 + _tone(165, 0.9, "saw") * 0.14 + _tone(220, 0.9) * 0.2
        S["wave"] = _echo(_lowpass(x, 8) * _env(len(x), 0.08, 2.2))
        x = _sweep(300, 120, 0.35, "square") * 0.22
        S["fail"] = x * _env(len(x), 0.01, 4)
        x = _sweep(400, 900, 0.3) * 0.3 + _sweep(600, 1350, 0.3) * 0.15
        S["shield"] = _echo(x * _env(len(x), 0.03, 3))
        S["buy"] = _echo(_seq([659, 784, 988, 1319], 0.07, "tri", 4) * 0.4)
        x = _sweep(1200, 600, 0.1) * 0.25
        S["arrow"] = x * _env(len(x), 0.002, 8)
        # --- yeni sesler
        x = _sweep(120, 420, 0.8, "saw") * 0.12 + _sweep(240, 840, 0.8) * 0.12
        S["charge"] = _lowpass(x, 6) * np.clip(_t(0.8) * 4, 0, 1) * np.exp(-_t(0.8) * 1.2)
        x = _sweep(700, 200, 0.12, "square") * 0.18 + _lowpass(_noise(0.12), 4) * 0.25
        S["death"] = x * _env(len(x), 0.002, 7)
        n = _noise(0.5)
        S["death_big"] = _echo((_sweep(220, 50, 0.5, "saw") * 0.35 + _lowpass(n, 12) * 0.6) * _env(len(n), 0.005, 4))
        S["combo"] = _echo(_seq([784, 988, 1175, 1568], 0.06, "square", 5) * 0.18)
        n = _noise(1.4)
        roar = _sweep(90, 60, 1.4, "saw") * 0.5 + _lowpass(n, 25) * 1.2
        S["boss"] = _echo(_lowpass(roar, 10) * _env(len(n), 0.15, 2.0) * (1 + 0.3 * np.sin(_t(1.4) * 2 * np.pi * 9)))
        fan = _seq([_note(n) for n in (60, 64, 67, 72)], 0.11, "tri", 3) * 0.4
        last = _tone(_note(76), 0.5, "tri") * 0.35 + _tone(_note(72), 0.5) * 0.2
        S["clear"] = _echo(np.concatenate([fan, last * _env(len(last), 0.01, 2.5)]))
        down = _seq([_note(n) for n in (69, 65, 62, 57)], 0.22, "saw", 2.5) * 0.2
        S["gameover"] = _echo(_lowpass(down, 10), gain=0.45)
        S["orb"] = _echo(_seq([1568, 2093], 0.06, "sine", 5) * 0.3, gain=0.3)
        x = _tone(1760, 0.05) * 0.25
        S["select"] = x * _env(len(x), 0.002, 6)
        n = _noise(0.6)
        S["start"] = _echo(_lowpass(n, 8) * np.sin(np.linspace(0, np.pi, len(n))) * 0.5 + _sweep(200, 800, 0.6) * 0.15)
        for k, v in S.items():
            self.sounds[k] = self._mk(v)

    def _music(self):
        """16 sn'lik döngü: Am - F - C - G pad + arpej + yumuşak davul."""
        bar = 4.0
        chords = [(57, 60, 64), (53, 57, 60), (48, 52, 55), (55, 59, 62)]
        total = int(SR * bar * len(chords))
        out = np.zeros(total)
        t = _t(bar)
        for ci, ch in enumerate(chords):
            start = int(ci * bar * SR)
            pad = np.zeros(len(t))
            for nn in ch:
                f = _note(nn)
                pad += _tone(f, bar, "saw") * 0.06 + _tone(f * 1.003, bar, "saw") * 0.05 + _tone(f / 2, bar) * 0.05
            pad = _lowpass(pad, 18)
            fade = np.minimum(1, np.minimum(t / 0.6, (bar - t) / 0.6))
            out[start:start + len(t)] += pad * fade
            # arpej (8'lik)
            arp = [ch[0] + 12, ch[1] + 12, ch[2] + 12, ch[1] + 12] * 2
            step = bar / 8
            for i, nn in enumerate(arp):
                x = _tone(_note(nn), step, "tri") * 0.07
                x *= _env(len(x), 0.005, 5)
                k = start + int(i * step * SR)
                out[k:k + len(x)] += x
            # davul: her vuruşta kalın bas
            for b in range(4):
                x = _sweep(90, 40, 0.25) * 0.25 * _env(int(SR * 0.25), 0.002, 8)
                k = start + int(b * SR)
                out[k:k + len(x)] += x
        return out

    def _mk(self, arr):
        a = (np.clip(arr, -1, 1) * 32767 * 0.6).astype(np.int16)
        if self.channels == 2:
            a = np.column_stack([a, a])
        return pygame.sndarray.make_sound(np.ascontiguousarray(a))

    # ------------------------------------------------------------------ API
    def start_music(self):
        if not self.ok:
            return
        try:
            if self.music is None:
                self.music = self._mk(self._music() * 1.6)
            self.music.play(loops=-1)
            self.music.set_volume(0.45 if self.enabled else 0.0)
        except Exception as e:
            print("[Müzik] başlatılamadı:", e)

    def toggle(self):
        self.enabled = not self.enabled
        if self.music is not None:
            self.music.set_volume(0.45 if self.enabled else 0.0)
        return self.enabled

    def play(self, name, vol=1.0):
        if self.ok and self.enabled and name in self.sounds:
            s = self.sounds[name]
            s.set_volume(vol)
            s.play()
