# -*- coding: utf-8 -*-
"""
Szetesos animaciok (2. csomag) - az olvadas mintajara: a szem valodi pixelekre esik szet,
fizikaval mozognak, majd pontosan visszaallnak.

  sand    : homokora - vekony sugarban lepereg, valodi kupac (lecsuszik ha meredek),
            a kepernyo megfordul, a homok visszapereg a szembe
  dust    : Thanos-csettintes - az egyik szeletol hamuva porlad, a szel elfujja;
            csend, majd visszafele (visszajatszva) ujraepul
  glass   : uvegtores - repedesek, szilankok, forogva leesnek, pattognak (csillanas),
            majd visszatekeres
  gravity : a gravitacio korbefordul (le, jobbra, fel, balra, le), minden falnal kupac;
            a vegen sulytalansag, aztan osszeall
  water   : a szem csepp lesz, a vizfelszinbe csapodik, hullamok + frocskolo cseppek;
            a vegen vizoszlop szokik fel es szemme all ossze
  magnet  : szetszorodik, lebeg, majd az egerkurzor magneskent vonzza (vasreszelek-tuk)
"""
import math
import random

import rampage as R
from rampage_extra import P, clamp

EXTRA2_KINDS = ["sand", "dust", "glass", "gravity", "water", "magnet"]
ASH = (105, 96, 92)


# ---------------------------------------------------------------- kupac (szemcse-fizika)
class Heap:
    """Szemcse-kupac egy fal mentén. A gravitacio iranya: 'down', 'up', 'left', 'right'.
    Ha egy oszlop 2 szemcsevel magasabb a szomszedjanal, a szemcse lecsuszik (rezsuszog)."""

    def __init__(self, wall, W, H, g):
        self.wall = wall; self.W = W; self.H = H; self.g = g
        length = W if wall in ("down", "up") else H
        self.n = int(length / g) + 1
        self.h = [0] * self.n

    def along_height(self, x, y):
        w = self.wall
        if w == "down": return x, self.H - y
        if w == "up": return x, y
        if w == "right": return y, self.W - x
        return y, x

    def pos(self, a, ht):
        w = self.wall
        if w == "down": return a, self.H - ht
        if w == "up": return a, ht
        if w == "right": return self.W - ht, a
        return ht, a

    def touching(self, x, y):
        a, ht = self.along_height(x, y)
        c = clamp(int(a / self.g), 0, self.n - 1)
        return ht <= (self.h[c] + 0.5) * self.g

    def settle(self, x, y):
        a, _ = self.along_height(x, y)
        c = clamp(int(a / self.g), 0, self.n - 1)
        h = self.h
        for _ in range(40):
            l = h[c - 1] if c > 0 else 10 ** 9
            r = h[c + 1] if c < self.n - 1 else 10 ** 9
            lo = min(l, r)
            if h[c] - lo >= 2:
                if l == r: c += random.choice((-1, 1))
                else: c = c - 1 if l < r else c + 1
            else:
                break
        h[c] += 1
        return self.pos((c + 0.5) * self.g, (h[c] - 0.5) * self.g)


GVEC = {"down": (0, 1), "up": (0, -1), "right": (1, 0), "left": (-1, 0)}


class ExtraAnims2:
    # ================= kozos =================
    def _grainSize(self):
        return self.parts[0].size / 1.08 if self.parts else 4.0

    def _fallStep(self, p, gx, gy, G, dt, drag=0.4):
        p.vx += gx * G * dt; p.vy += gy * G * dt
        k = math.exp(-drag * dt)
        p.vx *= k; p.vy *= k
        p.x += p.vx * dt; p.y += p.vy * dt
        p.x = clamp(p.x, 1, self.W - 1); p.y = clamp(p.y, 1, self.H - 1)

    def _settleTo(self, p, heap):
        p.state = 2
        p.d, p.ang = heap.settle(p.x, p.y)       # d,ang = a kupacbeli celpont (x, y)
        p.vx *= 0.3; p.vy *= 0.3

    def _slideSettled(self, p, dt):
        # puha becsuszas a kupacbeli helyere
        p.seek(p.d, p.ang, dt, 16.0)

    # ================= 1) HOMOKORA =================
    def _init_sand(self):
        self.parts = self._homeParticles(self.hx, self.hy)
        self.ff = 0.0
        if not self.parts: self.done = True; return
        g = self._grainSize()
        self.heap = Heap("down", self.W, self.H, g)
        self.streamX = self.hx
        self.eyeBottom = max(p.y for p in self.parts)
        order = sorted(self.parts, key=lambda p: (-p.y, abs(p.x - self.hx)))
        rate = clamp(len(order) / 2.4, 120, 400)
        for i, p in enumerate(order):
            p.delay = 0.3 + i / rate; p.state = 0
        self.rot = 0.0

    def _upd_sand(self, dt):
        u = self.u; G = 1900 * u
        if self.phase == 0:                                  # lepereg
            allSettled = True
            for p in self.parts:
                if p.state == 0:
                    allSettled = False
                    if self.phaseT >= p.delay:
                        p.state = 1; p.vx = 0; p.vy = 60 * u
                    else:
                        p.x += math.sin(self.t * 30 + p.ph) * 0.05 * u   # pereg-remeg
                elif p.state == 1:
                    allSettled = False
                    # a sugar kozepe fele huzodik (vekony homoksugar)
                    p.vx += ((self.streamX - p.x) * 14 + random.uniform(-30, 30) * u - p.vx) * min(1, dt * 10)
                    p.vy += G * dt
                    p.x += p.vx * dt; p.y += p.vy * dt
                    if p.y > self.eyeBottom + 4 * u and self.heap.touching(p.x, p.y):
                        self._settleTo(p, self.heap)
                else:
                    self._slideSettled(p, dt)
            if allSettled and self.phaseT > 1.0:
                self._next()
                for p in self.parts:
                    p.x, p.y = p.d, p.ang
                    p.vx = p.vy = 0
                self.flip0 = [(p.x, p.y) for p in self.parts]
        elif self.phase == 1:                                # szunet
            for p in self.parts: self._slideSettled(p, dt)
            if self.phaseT > 0.8:
                self._next()
                self.flip0 = [(p.x, p.y) for p in self.parts]
        elif self.phase == 2:                                # a kepernyo megfordul
            k = R.ease(self.phaseT / 1.3)
            a = math.pi * k
            ca, sa = math.cos(a), math.sin(a)
            cx, cy = self.hx, self.H / 2          # a szem fuggolegese korul fordul -> a kupac a szem fole kerul
            for p, (x0, y0) in zip(self.parts, self.flip0):
                dx, dy = x0 - cx, y0 - cy
                p.x = clamp(cx + dx * ca - dy * sa, 2, self.W - 2); p.y = cy + dx * sa + dy * ca
            self.rot = a
            if self.phaseT > 1.4:
                # a homok visszapereg: legalso szemcse elobb, a szem alulrol felfele toltodik
                grains = sorted(self.parts, key=lambda p: -p.y)
                targets = sorted([(p.hx, p.hy) for p in self.parts], key=lambda t: -t[1])
                rate = clamp(len(grains) / 2.6, 120, 400)
                for i, (p, tgt) in enumerate(zip(grains, targets)):
                    p.hx, p.hy = tgt
                    p.delay = i / rate; p.state = 3; p.vx = p.vy = 0
                self._next()
        else:                                                # visszapereg a szembe
            for p in self.parts:
                if self.phaseT < p.delay: continue
                if p.state == 3:
                    # szabadeses a cel fole, majd puhan a helyere
                    p.vx += ((p.hx - p.x) * 10 - p.vx) * min(1, dt * 8)
                    p.vy += G * dt
                    p.x += p.vx * dt; p.y += p.vy * dt
                    if p.y >= p.hy - 12 * u or p.y > self.H:
                        p.state = 4
                    elif p.y > p.hy:
                        p.state = 4
                else:
                    p.seek(p.hx, p.hy, dt, 12.0)
            self._updFinalFade(dt, self.parts)
            if self.phaseT > 9.0: self.done = True

    def _eyes_sand(self):
        return self._finalEyes()

    def _fx_sand(self, layer):
        if layer == "back": return []
        return self._pxFx(self.parts)

    # ================= 2) PORRA VALAS (Thanos) =================
    def _init_dust(self):
        u = self.u
        self.parts = self._homeParticles(self.hx, self.hy)
        self.ff = 0.0
        if not self.parts: self.done = True; return
        xs = [p.x for p in self.parts]; mn, mx = min(xs), max(xs); w = max(1.0, mx - mn)
        self.dir = random.choice((-1, 1))
        for p in self.parts:
            frac = (p.x - mn) / w if self.dir > 0 else (mx - p.x) / w
            p.delay = 0.35 + frac * 1.5 + random.uniform(0, 0.4)
            p.state = 0; p.w = 0.0          # w = hamu-szinezodes 0..1
        self.rec = []; self.recPos = 0.0
        self.REC_LEN = 3.6

    def _upd_dust(self, dt):
        u = self.u; t = self.t
        if self.phase == 0:                                  # porlad, a szel elfujja (rogzitve)
            for p in self.parts:
                if p.state == 0:
                    if self.phaseT >= p.delay:
                        p.state = 1
                        p.vx = self.dir * random.uniform(40, 150) * u; p.vy = -random.uniform(20, 100) * u
                    else:
                        p.w = max(p.w, clamp((self.phaseT - p.delay + 0.35) / 0.35, 0, 1) * 0.5)
                    continue
                age = self.phaseT - p.delay
                p.w = min(1.0, p.w + dt / 0.5)
                p.vx += (self.dir * 300 * u - p.vx) * dt * 0.7 + math.sin(p.y * 0.02 / u + t * 3 + p.ph) * 160 * u * dt
                p.vy += (math.cos(p.x * 0.015 / u + t * 2.4 + p.ph) * 110 * u - 30 * u - p.vy) * dt * 1.2
                p.x += p.vx * dt; p.y += p.vy * dt
                p.a = clamp(1 - age / 2.2, 0, 1) ** 1.3
            self.rec.append([(p.x, p.y, p.w, p.a) for p in self.parts])
            if self.phaseT >= self.REC_LEN:
                self._next()
        elif self.phase == 1:                                # csend
            for p in self.parts: p.a = 0.0
            if self.phaseT > 1.3:
                self.recPos = len(self.rec) - 1.0
                self._next()
        elif self.phase == 2:                                # visszafele fujodik
            self.recPos -= dt * 60 * 1.25
            i = int(clamp(self.recPos, 0, len(self.rec) - 1))
            for p, (x, y, w, a) in zip(self.parts, self.rec[i]):
                p.x, p.y, p.w, p.a = x, y, w, a
            if self.recPos <= 0:
                for p in self.parts:
                    p.x, p.y = p.hx, p.hy; p.vx = p.vy = 0; p.w = 0; p.a = 1
                self._next()
        else:
            self._updFinalFade(dt, self.parts)
            if self.phaseT > 1.0: self.done = True

    def _eyes_dust(self):
        return self._finalEyes()

    def _fx_dust(self, layer):
        if layer == "back": return []
        out = []
        for p in self.parts:
            if p.a <= 0.01: continue
            k = p.w
            c = tuple(int(p.color[j] + (ASH[j] - p.color[j]) * k) for j in range(3))
            out.append(("px", p.x, p.y, p.size * (1 - 0.35 * k), 0.0, c, p.a))
        return out

    # ================= 3) UVEGTORES =================
    def _init_glass(self):
        u = self.u
        self.parts = self._homeParticles(self.hx, self.hy)
        self.ff = 0.0
        if not self.parts: self.done = True; return
        self.cracks = []
        self.shards = []
        S = self.S
        eyeW, eyeH = 26 * S, 40 * S
        for ex, ey in self._eyeCenters(self.hx, self.hy):
            ix = ex + random.uniform(-0.25, 0.25) * eyeW; iy = ey + random.uniform(-0.25, 0.2) * eyeH
            # repedesek: cikcakkos sugarak a becsapodasi pontbol
            for k in range(8):
                a = k * math.pi / 4 + random.uniform(-0.3, 0.3)
                pts = [(ix, iy)]; x, y = ix, iy
                for _ in range(30):
                    a += random.uniform(-0.45, 0.45)
                    x += math.cos(a) * 6 * u; y += math.sin(a) * 6 * u
                    pts.append((x, y))
                    if abs(x - ex) > eyeW / 2 or abs(y - ey) > eyeH / 2: break
                self.cracks.append(pts)
            # szilankok magjai (a becsapodas kornyeken surubb)
            seeds = []
            for _ in range(11):
                r = (random.random() ** 1.4) * eyeH * 0.6; a = random.uniform(0, 2 * math.pi)
                seeds.append((ix + math.cos(a) * r, iy + math.sin(a) * r))
            for sx, sy in seeds:
                self.shards.append({"seed": (sx, sy), "imp": (ix, iy), "pix": []})
        for p in self.parts:
            best = min(self.shards, key=lambda s: (s["seed"][0] - p.x) ** 2 + (s["seed"][1] - p.y) ** 2)
            best["pix"].append(p)
        self.shards = [s for s in self.shards if s["pix"]]
        for s in self.shards:
            cx = sum(p.x for p in s["pix"]) / len(s["pix"]); cy = sum(p.y for p in s["pix"]) / len(s["pix"])
            s["cx"], s["cy"], s["ang"] = cx, cy, 0.0
            s["off"] = [(p.x - cx, p.y - cy) for p in s["pix"]]
            s["r"] = max(math.hypot(ox, oy) for ox, oy in s["off"]) + self._grainSize() * 0.6
            ix, iy = s["imp"]
            dx, dy = cx - ix, cy - iy; d = math.hypot(dx, dy) or 1.0
            sp = random.uniform(120, 420) * u
            s["vx"] = dx / d * sp + random.uniform(-60, 60) * u
            s["vy"] = dy / d * sp - random.uniform(150, 380) * u
            s["w"] = random.uniform(-7, 7)
            s["shade"] = random.uniform(0.78, 1.0)
            s["sleep"] = False
        self.glints = []
        self.rec = []; self.recPos = 0.0

    def _placeShards(self):
        for s in self.shards:
            ca, sa = math.cos(s["ang"]), math.sin(s["ang"])
            for p, (ox, oy) in zip(s["pix"], s["off"]):
                p.x = s["cx"] + ox * ca - oy * sa; p.y = s["cy"] + ox * sa + oy * ca

    def _upd_glass(self, dt):
        u = self.u; G = 2000 * u
        for gl in self.glints: gl[2] += dt
        self.glints = [gl for gl in self.glints if gl[2] < 0.3]
        if self.phase == 0:                                  # repedesek futnak vegig
            if self.phaseT > 0.9: self._next()
        elif self.phase == 1:                                # szettorik, leesik, pattog (rogzitve)
            floor = self.H - 3 * u
            for s in self.shards:
                if s["sleep"]: continue
                s["vy"] += G * dt
                s["cx"] += s["vx"] * dt; s["cy"] += s["vy"] * dt; s["ang"] += s["w"] * dt
                r = s["r"]
                if s["cy"] + r * 0.55 > floor and s["vy"] > 0:
                    s["cy"] = floor - r * 0.55
                    if s["vy"] > 180 * u:
                        self.glints.append([s["cx"] + random.uniform(-r, r) * 0.5, floor - 2 * u, 0.0])
                    s["vy"] = -s["vy"] * 0.42; s["vx"] *= 0.72; s["w"] *= 0.6
                    if abs(s["vy"]) < 60 * u:
                        s["vy"] = 0; s["vx"] *= 0.9
                        if abs(s["vx"]) < 10 * u: s["sleep"] = True
                if s["cx"] < r or s["cx"] > self.W - r:
                    s["vx"] = -s["vx"] * 0.5; s["cx"] = clamp(s["cx"], r, self.W - r)
            self._placeShards()
            self.rec.append([(s["cx"], s["cy"], s["ang"]) for s in self.shards])
            if self.phaseT > 3.6:
                self._next()
        elif self.phase == 2:                                # kis szunet
            if self.phaseT > 0.7:
                self.recPos = len(self.rec) - 1.0; self._next()
        elif self.phase == 3:                                # visszatekeres
            self.recPos -= dt * 60 * 1.7
            i = int(clamp(self.recPos, 0, len(self.rec) - 1))
            for s, (cx, cy, a) in zip(self.shards, self.rec[i]):
                s["cx"], s["cy"], s["ang"] = cx, cy, a
            self._placeShards()
            if self.recPos <= 0:
                for p in self.parts: p.x, p.y = p.hx, p.hy; p.vx = p.vy = 0
                self._next()
        elif self.phase == 4:                                # a repedesek "beforrnak"
            if self.phaseT > 0.5: self._next()
        else:
            self._updFinalFade(dt, self.parts)
            if self.phaseT > 1.0: self.done = True

    def _eyes_glass(self):
        return self._finalEyes()

    def _fx_glass(self, layer):
        if layer == "back": return []
        out = []
        u = self.u
        if self.phase in (0, 4):
            # ep szem + repedesek
            if self.phase == 0 or self.ff <= 0:
                for p in self.parts:
                    out.append(("px", p.x, p.y, p.size, 0.0, p.color, p.a))
            frac = R.ease(self.phaseT / 0.7) if self.phase == 0 else 1 - R.ease(self.phaseT / 0.5)
            for pts in self.cracks:
                n = max(2, int(len(pts) * frac))
                for (x0, y0), (x1, y1) in zip(pts[:n - 1], pts[1:n]):
                    out.append(("line", x0, y0, x1, y1, 1.6 * u, (235, 255, 255), 0.95 * (frac if self.phase == 4 else 1)))
            return out
        for s in self.shards:
            c = tuple(int(v * s["shade"]) for v in R.CYAN)
            for p in s["pix"]:
                if p.a > 0.01:
                    out.append(("px", p.x, p.y, p.size, s["ang"], c, p.a))
        for x, y, age in self.glints:
            k = age / 0.3
            out.append(("flash", x, y, 34 * u * (0.4 + k), (1 - k) * 0.9))
            L = 14 * u * (1 - k)
            out.append(("line", x - L, y, x + L, y, 1.5 * u, (255, 255, 255), 1 - k))
            out.append(("line", x, y - L, x, y + L, 1.5 * u, (255, 255, 255), 1 - k))
        return out

    # ================= 5) GRAVITACIO-FORDITAS =================
    G_SEQ = [("down", 2.6), ("right", 2.2), ("up", 2.2), ("left", 2.2), ("down", 2.0)]

    def _init_gravity(self):
        self.parts = self._homeParticles(self.hx, self.hy)
        self.ff = 0.0
        if not self.parts: self.done = True; return
        self.gi = 0
        self._newGravity()

    def _newGravity(self):
        wall = self.G_SEQ[self.gi][0]
        self.heap = Heap(wall, self.W, self.H, self._grainSize())
        self.gvec = GVEC[wall]
        for p in self.parts:
            p.state = 1
            p.vx += random.uniform(-20, 20) * self.u; p.vy += random.uniform(-20, 20) * self.u

    def _upd_gravity(self, dt):
        u = self.u; G = 1800 * u
        if self.phase == 0:
            gx, gy = self.gvec
            for p in self.parts:
                if p.state == 1:
                    self._fallStep(p, gx, gy, G, dt)
                    if self.heap.touching(p.x, p.y):
                        self._settleTo(p, self.heap)
                else:
                    self._slideSettled(p, dt)
            if self.phaseT > self.G_SEQ[self.gi][1]:
                self.gi += 1; self.phaseT = 0.0
                if self.gi < len(self.G_SEQ):
                    self._newGravity()
                else:
                    self._next()
                    for p in self.parts:                     # sulytalansag: lassu lebeges
                        p.state = 5
                        p.vx = random.uniform(-70, 70) * u; p.vy = -random.uniform(40, 160) * u
        elif self.phase == 1:
            k = math.exp(-0.6 * dt)
            for p in self.parts:
                p.vx *= k; p.vy *= k
                p.vx += math.sin(self.t * 1.3 + p.ph) * 12 * u * dt
                p.x += p.vx * dt; p.y += p.vy * dt
            if self.phaseT > 1.8:
                for p in self.parts: p.w = random.uniform(2.6, 3.6); p.delay = random.uniform(0, 0.5)
                self._next()
        else:
            for p in self.parts:
                if self.phaseT >= p.delay: p.seek(p.hx, p.hy, dt, p.w)
            self._updFinalFade(dt, self.parts)
            if self.phaseT > 6.0: self.done = True

    def _eyes_gravity(self):
        return self._finalEyes()

    def _fx_gravity(self, layer):
        if layer == "back":
            if self.phase != 0: return []
            # halvany nyil a gravitacio iranyaba
            gx, gy = self.gvec; u = self.u
            cx, cy = self.W / 2, self.H / 2
            a = 0.18 * clamp(self.phaseT / 0.3, 0, 1) * clamp((self.G_SEQ[self.gi][1] - self.phaseT) / 0.4, 0, 1) if self.gi < len(self.G_SEQ) else 0
            if a <= 0.01: return []
            L = 70 * u
            x1, y1 = cx + gx * L, cy + gy * L
            px, py = -gy, gx
            return [("line", cx - gx * L, cy - gy * L, x1, y1, 6 * u, R.CYAN, a),
                    ("line", x1, y1, x1 - gx * 26 * u + px * 22 * u, y1 - gy * 26 * u + py * 22 * u, 6 * u, R.CYAN, a),
                    ("line", x1, y1, x1 - gx * 26 * u - px * 22 * u, y1 - gy * 26 * u - py * 22 * u, 6 * u, R.CYAN, a)]
        return self._pxFx(self.parts)

    # ================= 6) VIZCSEPP-FELSZIN =================
    def _init_water(self):
        u = self.u
        self.parts = self._homeParticles(self.hx, self.hy)
        self.ff = 0.0
        if not self.parts: self.done = True; return
        self.dxw = 8 * u
        self.nw = int(self.W / self.dxw) + 2
        self.wh = [0.0] * self.nw; self.wv = [0.0] * self.nw
        self.surf0 = self.H - 120 * u
        self.waterA = 0.0
        n = len(self.parts)
        self.ballR = math.sqrt(n) * self._grainSize() * 0.62
        for p in self.parts:
            a = random.uniform(0, 2 * math.pi); r = self.ballR * math.sqrt(random.random())
            p.d, p.ang = math.cos(a) * r, math.sin(a) * r      # helye a cseppben
        self.ballX, self.ballY, self.ballV = self.hx, self.hy, 0.0
        self.jetX = clamp(self.hx, 60 * u, self.W - 60 * u)

    def _surfY(self, x):
        i = clamp(x / self.dxw, 0, self.nw - 1.001)
        i0 = int(i); f = i - i0
        return self.surf0 - (self.wh[i0] * (1 - f) + self.wh[i0 + 1] * f)

    def _splash(self, x, amount, width):
        c = x / self.dxw
        for i in range(max(0, int(c - width * 3)), min(self.nw, int(c + width * 3) + 1)):
            self.wv[i] -= amount * math.exp(-((i - c) / width) ** 2)

    def _waveStep(self, dt):
        n = self.nw; h = self.wh; v = self.wv
        sub = 4; hdt = dt / sub
        for _ in range(sub):
            for i in range(n):
                l = h[i - 1] if i > 0 else h[i]; r = h[i + 1] if i < n - 1 else h[i]
                v[i] += (2600 * (l + r - 2 * h[i]) - 22 * h[i]) * hdt
            damp = math.exp(-1.5 * hdt)
            for i in range(n):
                v[i] *= damp; h[i] += v[i] * hdt

    def _upd_water(self, dt):
        u = self.u; G = 1900 * u
        self._waveStep(dt)
        if self.phase in (0, 1, 2, 3): self.waterA = min(1.0, self.waterA + dt / 0.6)
        if self.phase == 0:                                  # csepp lesz
            for p in self.parts:
                p.seek(self.ballX + p.d, self.ballY + p.ang, dt, 7.0)
            if self.phaseT > 0.9: self._next()
        elif self.phase == 1:                                # leesik
            self.ballV += G * dt; self.ballY += self.ballV * dt
            for p in self.parts:
                p.x = self.ballX + p.d; p.y = self.ballY + p.ang * (1 + min(0.4, self.ballV / (6000 * u)))
            if self.ballY + self.ballR >= self._surfY(self.ballX) or self.ballY > self.H:
                self._splash(self.ballX, 520 * u, 2.4)
                for p in self.parts:
                    if random.random() < 0.42:
                        p.state = 1                          # frocskolo csepp
                        p.vx = random.uniform(-450, 450) * u
                        p.vy = -random.uniform(500, 1150) * u
                    else:
                        p.state = 2                          # elmerul
                        p.vx = random.uniform(-60, 60) * u; p.vy = random.uniform(60, 200) * u
                self._next()
        elif self.phase == 2:                                # frocskoles, hullamok
            alive = 0
            for p in self.parts:
                if p.state == 1:
                    p.vy += G * dt; p.x += p.vx * dt; p.y += p.vy * dt
                    p.x = clamp(p.x, 2, self.W - 2)
                    if p.vy > 0 and p.y >= self._surfY(p.x):
                        self._splash(p.x, min(180 * u, p.vy * 0.12), 1.2)
                        p.state = 3; p.a = 0.0
                    else:
                        alive += 1
                elif p.state == 2:
                    p.x += p.vx * dt; p.y += p.vy * dt; p.vy *= math.exp(-2 * dt)
                    p.a = max(0.0, p.a - dt / 0.45)
                    if p.a <= 0: p.state = 3
                    else: alive += 1
            if alive == 0 and self.phaseT > 1.2:
                self._next()
        elif self.phase == 3:                                # nyugodo hullamok
            if self.phaseT > 1.3:
                # vizoszlop: alulrol felfele toltodik a szem
                order = sorted(self.parts, key=lambda p: -p.hy)
                for i, p in enumerate(order):
                    p.delay = i / 380.0; p.state = 4; p.a = 0.0
                self._next()
        elif self.phase == 4:                                # vizoszlop felszokik
            sY = self._surfY(self.jetX)
            # a felszin kiemelkedik az oszlop alatt
            self._splash(self.jetX, -90 * u * dt, 1.5) if self.phaseT < 1.0 else None
            for p in self.parts:
                if p.state == 4:
                    if self.phaseT >= p.delay:
                        p.state = 5; p.a = 1.0
                        p.x = self.jetX + random.uniform(-8, 8) * u; p.y = sY
                        rise = max(20 * u, sY - p.hy)
                        p.vy = -math.sqrt(2 * G * rise) * 1.02
                        T = abs(p.vy) / G
                        p.vx = (p.hx - p.x) / T
                elif p.state == 5:
                    p.vy += G * dt; p.x += p.vx * dt; p.y += p.vy * dt
                    if p.vy >= 0 or abs(p.y - p.hy) < 3 * u: p.state = 6
                elif p.state == 6:
                    p.seek(p.hx, p.hy, dt, 11.0)
            if all(p.state == 6 for p in self.parts):
                self.waterA = max(0.0, self.waterA - dt / 0.8)
                self._updFinalFade(dt, self.parts)
            if self.phaseT > 8.0: self.done = True

    def _eyes_water(self):
        return self._finalEyes()

    def _fx_water(self, layer):
        u = self.u
        if layer == "back":
            if self.waterA <= 0.01: return []
            pts = [(i * self.dxw, self.surf0 - self.wh[i]) for i in range(self.nw)]
            body = pts + [(self.W + 2, self.H + 2), (-2, self.H + 2)]
            return [("poly", body, (0, 160, 220), 0.16 * self.waterA),
                    ("pline", pts, 2.6 * u, R.CYAN, 0.75 * self.waterA)]
        return self._pxFx(self.parts)

    # ================= 7) MAGNES (egerkurzor) =================
    def _init_magnet(self):
        u = self.u
        self.parts = self._homeParticles(self.hx, self.hy)
        self.ff = 0.0
        for p in self.parts:
            p.d = random.uniform(30 * u, self.W - 30 * u); p.ang = random.uniform(30 * u, self.H - 30 * u)
            p.w = (random.random() ** 0.6) * 85 * u + 8 * u      # egyensulyi tavolsag a kurzortol
            a = random.uniform(0, 2 * math.pi); sp = random.uniform(300, 900) * u
            p.vx, p.vy = math.cos(a) * sp, math.sin(a) * sp

    def _cursor(self):
        fn = getattr(self, "cursorFn", None)
        if fn is None: return self.W / 2, self.H / 2
        try:
            return fn()
        except Exception:
            return self.W / 2, self.H / 2

    def _upd_magnet(self, dt):
        u = self.u; t = self.t
        if self.phase == 0:                                  # szetszorodik
            for p in self.parts:
                p.seek(p.d, p.ang, dt, 2.3)
            if self.phaseT > 1.6: self._next()
        elif self.phase == 1:                                # lebeg
            for p in self.parts:
                tx = p.d + math.sin(t * 1.4 + p.ph) * 10 * u; ty = p.ang + math.cos(t * 1.1 + p.ph) * 10 * u
                p.seek(tx, ty, dt, 2.0)
            if self.phaseT > 1.4: self._next()
        elif self.phase == 2:                                # a kurzor vonzza
            cx, cy = self._cursor()
            ramp = R.ease(self.phaseT / 2.0)
            for p in self.parts:
                dx, dy = p.x - cx, p.y - cy; d = math.hypot(dx, dy) or 1.0
                tx = cx + dx / d * p.w; ty = cy + dy / d * p.w
                # kis orveny a kurzor korul
                tx += -dy / d * 18 * u * math.sin(t * 2 + p.ph); ty += dx / d * 18 * u * math.sin(t * 2 + p.ph)
                w = 0.6 + 2.6 * ramp
                p.seek(tx, ty, dt, w)
            if self.phaseT > 7.0:
                for p in self.parts: p.w = random.uniform(2.8, 3.8); p.delay = random.uniform(0, 0.4)
                self._next()
        else:                                                # haza
            for p in self.parts:
                if self.phaseT >= p.delay: p.seek(p.hx, p.hy, dt, p.w)
            self._updFinalFade(dt, self.parts)
            if self.phaseT > 6.0: self.done = True

    def _eyes_magnet(self):
        return self._finalEyes()

    def _fx_magnet(self, layer):
        if layer == "back": return []
        if self.phase in (0, 3):
            return self._pxFx(self.parts)
        cx, cy = self._cursor()
        out = []
        for p in self.parts:
            # vasreszelek: a terhez igazodo kis tuk
            dx, dy = cx - p.x, cy - p.y; d = math.hypot(dx, dy) or 1.0
            L = p.size * 1.6
            ux, uy = dx / d * L, dy / d * L
            out.append(("line", p.x - ux, p.y - uy, p.x + ux, p.y + uy, p.size * 0.7, p.color, p.a))
        return out


def install(cls):
    for name, val in ExtraAnims2.__dict__.items():
        if name.startswith("__"): continue
        if not hasattr(cls, name):
            setattr(cls, name, val)
    for k in EXTRA2_KINDS:
        if k not in R.KINDS:
            R.KINDS.append(k)
