# -*- coding: utf-8 -*-
"""
Simitas a normal (ablakos) modhoz.

A MiniFace logika fix utemben lep (LOGIC_DT), a kirajzolas viszont 60 fps-sel megy:
  - ket logikai kep kozott linearis interpolacio
  - utana egy kis exponencialis simitas (lekerekiti a hirtelen ugrasokat, pl. cikazas)
  - nagy ugrasnal (pl. le-fel tunesnel a "korbeeres") nincs simitas, ott ugrik
  - pislogas / kacsintas: a szem fokozatosan lapul ossze, nem egybol vonal
  - szovegek (ido, idojaras, uzenetek) be- es kiusztatva jelennek meg
"""
import copy
import math

import miniface as mf

LOGIC_DT = 0.045          # mp - kb. az eredeti ESP32 tempoja
POS_TAU = 0.035           # mp - pozicio-simitas idoallandoja
TELEPORT = 45.0           # canvas-egyseg - e folott nincs simitas (ugras)
CLOSE_SPEED = 1 / 0.07    # pislogas: osszecsukodas sebessege (1/mp)
OPEN_SPEED = 1 / 0.11     # pislogas: kinyilas sebessege
TEXT_FADE = 1 / 0.22      # szoveg be/ki usztatas

POS_KEYS = ("e1cx", "e1cy", "e2cx", "e2cy")
SCALE_KEYS = ("eye1Scale", "eye2Scale")


def _lerp(a, b, t):
    return a + (b - a) * t


def _approach(v, target, rate, dt):
    step = rate * dt
    if v < target: return min(target, v + step)
    return max(target, v - step)


class Smoother:
    def __init__(self):
        self.prev = None
        self.cur = None
        self.tCur = 0.0
        self.disp = {}
        self.close = [0.0, 0.0]
        self.infoA = 0.0; self.lastInfo = None
        self.bottomA = 0.0; self.lastBottom = None
        self.lastT = None

    def push(self, f, t):
        self.prev = self.cur if self.cur is not None else f
        self.cur = f
        self.tCur = t

    def reset(self):
        self.disp.clear()

    def get(self, t):
        cur, prev = self.cur, self.prev
        if cur is None:
            return None
        dt = 0.0 if self.lastT is None else max(0.0, min(0.1, t - self.lastT))
        self.lastT = t
        a = max(0.0, min(1.0, (t - self.tCur) / LOGIC_DT))
        out = copy.copy(cur)

        # --- pozicio: interpolacio + simitas ---
        k = 1.0 - math.exp(-dt / POS_TAU) if dt > 0 else 1.0
        for key in POS_KEYS:
            pv, cv = getattr(prev, key), getattr(cur, key)
            v = cv if abs(cv - pv) > TELEPORT else _lerp(pv, cv, a)
            d = self.disp.get(key)
            if d is None or abs(v - d) > TELEPORT:
                d = v
            else:
                d += (v - d) * k
            self.disp[key] = d
            setattr(out, key, d)
        out.e1x = out.e1cx - mf.EYE_W / 2; out.e1y = out.e1cy - mf.EYE_H / 2
        out.e2x = out.e2cx - mf.EYE_W / 2; out.e2y = out.e2cy - mf.EYE_H / 2

        for key in SCALE_KEYS:
            setattr(out, key, _lerp(getattr(prev, key), getattr(cur, key), a))

        out.eye1Shape = mf.lerpShape(prev.eye1Shape, cur.eye1Shape, a)
        out.eye2Shape = mf.lerpShape(prev.eye2Shape, cur.eye2Shape, a)

        if cur.feedBall is not None and prev.feedBall is not None:
            out.feedBall = (_lerp(prev.feedBall[0], cur.feedBall[0], a),
                            _lerp(prev.feedBall[1], cur.feedBall[1], a))
        if cur.particles and prev.particles and len(cur.particles) == len(prev.particles):
            out.particles = [(_lerp(p[0], c[0], a), _lerp(p[1], c[1], a))
                             for p, c in zip(prev.particles, cur.particles)]

        # --- puha pislogas ---
        for i, closed in enumerate((cur.eye1Closed, cur.eye2Closed)):
            self.close[i] = _approach(self.close[i], 1.0 if closed else 0.0,
                                      CLOSE_SPEED if closed else OPEN_SPEED, dt)
        out.eye1CloseAmt, out.eye2CloseAmt = self.close

        # --- szovegek usztatasa ---
        if cur.info is not None: self.lastInfo = cur.info
        self.infoA = _approach(self.infoA, 1.0 if cur.info is not None else 0.0, TEXT_FADE, dt)
        out.info = self.lastInfo if self.infoA > 0 else None
        out.infoAlpha = self.infoA

        if cur.bottom: self.lastBottom = cur.bottom
        self.bottomA = _approach(self.bottomA, 1.0 if cur.bottom else 0.0, TEXT_FADE, dt)
        out.bottom = self.lastBottom if self.bottomA > 0 else None
        out.bottomAlpha = self.bottomA
        return out
