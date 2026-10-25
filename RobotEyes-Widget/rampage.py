# -*- coding: utf-8 -*-
"""
Teljes kepernyos "randalirozas" - csak ezek hasznaljak az egesz kijelzot.
  bounce : pattog ide-oda a kijelzon
  swarm  : megsokszorozodik -> szanaszet repulnek -> sorba allnak -> korbe-korbe
           mennek -> a kor kozepebe gyulnek -> ujra osszeallnak
  chaos  : a ket szem kulon-kulon, gyorsan, osszevissza cikazik
  sink   : egy iranyba (lefele) indul, egyre gyorsabban, kiesik alul, bejon felul
Minden koordinata a kijelzo bal felso sarkahoz kepest, eszkozfuggetlen pixelben.

Simasag: minden mozgas sebesseggel bir, a celpontokat rugo (kritikusan csillapitott)
koveti, igy fazisvaltaskor sincs hirtelen megallas/ugras. Falnak utkozeskor a szem
zselészeruen lapul es visszarug; a pislogas fokozatos.
"""
import math
import random

KINDS = ["bounce", "swarm", "chaos", "sink", "dvd", "atom"]

CYAN = (0, 255, 255)

PAIR_DX = 25.0          # a ket szem kozeppontja +-25 canvas-egysegre van a par kozepetol
HALF_W_PAIR = 25 + 17   # canvas-egyseg
HALF_W_ONE = 17
HALF_H = 24

JELLY_K = (2 * math.pi * 3.2) ** 2      # zsele rugo merevsege (~3.2 Hz)
JELLY_C = 2 * 0.22 * math.sqrt(JELLY_K)  # alulcsillapitott -> rezeg kicsit
BLINK_LEN = 0.22


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def easeOutBack(t):
    t = max(0.0, min(1.0, t))
    c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


class Body:
    """Egy mozgo targy (szempar vagy egy szem): pozicio, sebesseg, zsele-deformacio, pislogas."""
    def __init__(self, x, y):
        self.x = x; self.y = y
        self.vx = 0.0; self.vy = 0.0
        self.qx = 0.0; self.qy = 0.0      # zsele kiterese (x: vizszintes lapulas, y: fuggoleges)
        self.qvx = 0.0; self.qvy = 0.0
        self.scale = 1.0
        self.stretch = 0.0                # mozgasiranyu nyulas (zuhanasnal)
        self.blinkT = -1.0
        self.nextBlink = random.uniform(1.0, 4.0)
        self.dirx = 0.0; self.diry = 0.0; self.spd = 0.0; self.target = 0.0
        self.color = CYAN
        self.alpha = 1.0
        self.single = False               # True: egyetlen szem (nem par) - atom elektronjai/magja
        self.depth = 0.0

    # kritikusan csillapitott rugo a celpont fele (lendulettel)
    def seek(self, tx, ty, dt, w):
        n = 2 if w * dt > 0.25 else 1
        h = dt / n
        for _ in range(n):
            ax = w * w * (tx - self.x) - 2 * w * self.vx
            ay = w * w * (ty - self.y) - 2 * w * self.vy
            self.vx += ax * h; self.vy += ay * h
            self.x += self.vx * h; self.y += self.vy * h

    def settled(self, tx, ty, eps=1.5):
        return abs(tx - self.x) < eps and abs(ty - self.y) < eps and abs(self.vx) + abs(self.vy) < 25

    def kick(self, axis, amount):
        if axis == "x": self.qvx += amount
        else: self.qvy += amount

    def jelly(self, dt):
        for _ in range(2):
            h = dt / 2
            self.qvx += (-JELLY_K * self.qx - JELLY_C * self.qvx) * h; self.qx += self.qvx * h
            self.qvy += (-JELLY_K * self.qy - JELLY_C * self.qvy) * h; self.qy += self.qvy * h

    def blink(self, dt):
        if self.blinkT >= 0:
            self.blinkT += dt
            if self.blinkT > BLINK_LEN: self.blinkT = -1.0
        else:
            self.nextBlink -= dt
            if self.nextBlink <= 0:
                self.blinkT = 0.0; self.nextBlink = random.uniform(2.0, 5.0)

    def closeAmt(self):
        if self.blinkT < 0: return 0.0
        u = self.blinkT / BLINK_LEN
        return min(1.0, (u / 0.4) if u < 0.4 else (1 - u) / 0.6 * 1.0)

    def sxsy(self):
        qx = max(-0.6, min(0.6, self.qx)); qy = max(-0.6, min(0.6, self.qy))
        sx = 1 - 0.35 * qx + 0.18 * qy - 0.4 * self.stretch
        sy = 1 - 0.35 * qy + 0.18 * qx + self.stretch
        return sx * self.scale, sy * self.scale


class Rampage:
    def __init__(self, kind, W, H, home, S, mini):
        self.kind = kind
        self.W = W; self.H = H
        self.hx, self.hy = home
        self.S = S
        self.mini = mini
        self.t = 0.0
        self.phase = 0
        self.phaseT = 0.0
        self.done = False
        self.halfW = (HALF_W_ONE if mini else HALF_W_PAIR) * S
        self.halfH = HALF_H * S
        self.bodies = [Body(self.hx, self.hy)]
        self.freeEyes = False      # chaos: a szemek kulon testek
        self.fx = []               # UJ: extra rajzelemek (pixel-reszecskek, villanas)
        getattr(self, "_init_" + kind)()

    # ----------------------------------------------------------- kozos
    def _next(self):
        self.phase += 1; self.phaseT = 0.0

    def _randDir(self):
        a = random.uniform(0, 2 * math.pi)
        if abs(math.sin(a)) < 0.3 or abs(math.cos(a)) < 0.3: a += 0.6
        return math.cos(a), math.sin(a)

    def _cruise(self, b, dt, hw=None, hh=None):
        """Iranyitott repules allando (felfuto) sebesseggel + rugalmas visszapattanas a falrol."""
        hw = self.halfW if hw is None else hw; hh = self.halfH if hh is None else hh
        b.spd += (b.target - b.spd) * min(1.0, dt * 2.5)
        tvx = b.dirx * b.spd; tvy = b.diry * b.spd
        # a tenyleges sebesseg puhan koveti a celsebesseget (fazisvaltasbol jovo lendulet elolvad)
        kk = min(1.0, dt * 6)
        b.vx += (tvx - b.vx) * kk; b.vy += (tvy - b.vy) * kk
        b.x += b.vx * dt; b.y += b.vy * dt
        if b.x < hw:
            b.x = hw; b.dirx = abs(b.dirx); b.vx = abs(b.vx); b.kick("x", 7 * min(1, b.spd / 600))
        elif b.x > self.W - hw:
            b.x = self.W - hw; b.dirx = -abs(b.dirx); b.vx = -abs(b.vx); b.kick("x", 7 * min(1, b.spd / 600))
        if b.y < hh:
            b.y = hh; b.diry = abs(b.diry); b.vy = abs(b.vy); b.kick("y", 7 * min(1, b.spd / 600))
        elif b.y > self.H - hh:
            b.y = self.H - hh; b.diry = -abs(b.diry); b.vy = -abs(b.vy); b.kick("y", 7 * min(1, b.spd / 600))

    def update(self, dt):
        if self.done: return
        dt = min(dt, 0.05)
        self.t += dt; self.phaseT += dt
        for b in self.bodies:
            b.blink(dt); b.jelly(dt)
        getattr(self, "_upd_" + self.kind)(dt)

    # ----------------------------------------------------------- 1) pattogas
    def _init_bounce(self):
        b = self.bodies[0]
        b.dirx, b.diry = self._randDir()
        b.target = max(self.W, self.H) * random.uniform(0.5, 0.65)

    def _upd_bounce(self, dt):
        b = self.bodies[0]
        if self.phase == 0:
            if self.phaseT > 6.5: b.target = 0.0          # a vegen lelassul
            self._cruise(b, dt)
            if self.phaseT > 7.3: self._next()
        else:
            b.seek(self.hx, self.hy, dt, 6.0)
            if b.settled(self.hx, self.hy) or self.phaseT > 3.0:
                self.done = True

    # ----------------------------------------------------------- 2) sokszorozodas
    def _init_swarm(self):
        n = 10 if self.mini else 8
        self.bodies = [Body(self.hx, self.hy) for _ in range(n)]
        base = max(self.W, self.H)
        for i, b in enumerate(self.bodies):
            b.dirx, b.diry = self._randDir()
            b.target = base * random.uniform(0.35, 0.6)
            b.scale = 0.0
            b.delay = i * 0.06
        self.cx = self.W / 2; self.cy = self.H / 2
        self.R = min(self.W, self.H) * 0.32
        self.angle = 0.0; self.omega = 0.0
        self.mergeV = 0.0

    def _circlePos(self, i, r):
        n = len(self.bodies)
        a = self.angle + 2 * math.pi * i / n - math.pi / 2
        return self.cx + math.cos(a) * r, self.cy + math.sin(a) * r

    def _upd_swarm(self, dt):
        B = self.bodies; n = len(B)
        if self.phase == 0:      # kipattannak es szetrepulnek
            for b in B:
                tt = self.phaseT - b.delay
                if tt < 0: continue
                b.scale = easeOutBack(tt / 0.45)
                self._cruise(b, dt)
            if self.phaseT > 4.0: self._next()
        elif self.phase == 1:    # sorba allnak (lendulettel erkeznek)
            for i, b in enumerate(B):
                b.seek(self.W * (i + 1) / (n + 1), self.H / 2, dt, 4.2)
            if self.phaseT > 2.0: self._next()
        elif self.phase == 2:    # korre rendezodnek
            for i, b in enumerate(B):
                tx, ty = self._circlePos(i, self.R)
                b.seek(tx, ty, dt, 4.5)
            if self.phaseT > 1.5: self._next()
        elif self.phase == 3:    # korbe-korbe, puhan gyorsulva
            self.omega += (3.0 - self.omega) * min(1.0, dt * 0.55)
            self.angle += self.omega * dt
            for i, b in enumerate(B):
                tx, ty = self._circlePos(i, self.R)
                b.seek(tx, ty, dt, 12.0)
            if self.phaseT > 4.5: self._next()
        elif self.phase == 4:    # spiralban a kor kozepebe
            self.angle += self.omega * dt
            r = self.R * (1 - ease(self.phaseT / 1.3))
            for i, b in enumerate(B):
                tx, ty = self._circlePos(i, r)
                b.seek(tx, ty, dt, 12.0)
                b.scale = 1.0 - 0.25 * ease(self.phaseT / 1.3)
            if self.phaseT > 1.35:
                m = Body(self.cx, self.cy); m.scale = 0.75
                self.bodies = [m]
                self._next()
        elif self.phase == 5:    # ujra osszeall: zseles "pukk"
            m = self.bodies[0]
            k = (2 * math.pi * 2.6) ** 2; c = 2 * 0.25 * math.sqrt(k)
            if self.phaseT <= dt: self.mergeV = 9.0
            self.mergeV += (-k * (m.scale - 1.0) - c * self.mergeV) * dt
            m.scale += self.mergeV * dt
            if self.phaseT > 1.0: m.scale += (1.0 - m.scale) * 0.3
            if self.phaseT > 1.2: m.scale = 1.0; self._next()
        else:
            b = self.bodies[0]
            b.seek(self.hx, self.hy, dt, 5.0)
            if b.settled(self.hx, self.hy) or self.phaseT > 3.0:
                self.done = True

    # ----------------------------------------------------------- 3) cikazas
    def _init_chaos(self):
        self.freeEyes = True
        n = 1 if self.mini else 2
        d = 0 if self.mini else PAIR_DX * self.S
        self.bodies = []
        for i in range(n):
            ox = -d if i == 0 else d
            b = Body(self.hx + ox, self.hy)
            b.homeX = self.hx + ox; b.homeY = self.hy
            b.tx = b.x; b.ty = b.y; b.nextJump = 0.05 * i
            b.ftx = b.x; b.fty = b.y          # puhan mozgo (szurt) celpont
            self.bodies.append(b)

    def _upd_chaos(self, dt):
        mW = HALF_W_ONE * self.S; mH = self.halfH
        if self.phase == 0:
            for b in self.bodies:
                b.nextJump -= dt
                if b.nextJump <= 0:
                    b.tx = random.uniform(mW, self.W - mW); b.ty = random.uniform(mH, self.H - mH)
                    b.nextJump = random.uniform(0.18, 0.34)
                kf = 1 - math.exp(-dt / 0.07)
                b.ftx += (b.tx - b.ftx) * kf; b.fty += (b.ty - b.fty) * kf
                b.seek(b.ftx, b.fty, dt, 11.0)
            if self.phaseT > 5.5: self._next()
        else:
            ok = True
            for b in self.bodies:
                b.seek(b.homeX, b.homeY, dt, 7.0)
                ok = ok and b.settled(b.homeX, b.homeY)
            if ok or self.phaseT > 3.0: self.done = True

    # ----------------------------------------------------------- 4) gyorsulo zuhanas
    def _init_sink(self):
        self.cycle = 0; self.sinkPhase = 0
        self.trip = self.H + 2 * self.halfH
        self.v0 = self.trip / 1.4
        self.travelled = 0.0
        self.landing = False

    def _upd_sink(self, dt):
        b = self.bodies[0]
        if self.landing:
            # egyenletes lassulas pont a helyere, utana zseles "huppanas"
            if self.landV > 0:
                self.landV = max(0.0, self.landV - self.landA * dt)
                b.y += self.landV * dt; b.vy = self.landV
                b.stretch += (min(0.45, self.landV / self.v0 * 0.06) - b.stretch) * min(1, dt * 8)
                if b.y >= self.hy or self.landV <= 0:
                    b.y = self.hy; self.landV = 0.0; self.phaseT = 0.0
                    b.kick("y", 9); b.stretch = 0.0
            elif self.phaseT > 0.6:
                self.done = True
            return
        u = self.cycle + min(1.0, self.travelled / self.trip)        # folyamatos haladas
        factor = max(0.18, 1.0 - 0.35 * u)
        v = self.v0 / factor * ease(self.t / 0.35 + 0.15)            # puha indulas
        dy = v * dt
        b.y += dy; b.vy = v; self.travelled += dy
        b.stretch += (min(0.45, (1 / factor - 1) * 0.12) - b.stretch) * min(1, dt * 6)
        if self.sinkPhase == 0:
            if b.y >= self.H + self.halfH * (1 + b.stretch):
                b.y = -self.halfH * (1 + b.stretch); self.sinkPhase = 1
                if self.cycle >= 8:
                    # utolso kor: innen egyenletesen lassul a helyeig
                    dist = max(1.0, self.hy - b.y)
                    self.landing = True; self.landV = v; self.landA = v * v / (2 * dist)
        else:
            if b.y >= self.hy:
                self.sinkPhase = 0; self.cycle += 1; self.travelled = 0.0

    # ----------------------------------------------------------- 5) DVD-logo pattogas
    DVD_COLORS = [(0, 255, 255), (255, 60, 200), (255, 230, 40), (90, 255, 90),
                  (255, 140, 30), (160, 110, 255), (255, 70, 70), (80, 160, 255)]

    def _init_dvd(self):
        b = self.bodies[0]
        a = random.choice((0.6, 2.5, 3.8, 5.4)) + random.uniform(-0.12, 0.12)   # kb. atlos
        b.dirx, b.diry = math.cos(a), math.sin(a)
        b.target = min(self.W, self.H) * 0.42
        b.colorFrom = CYAN; b.colorTo = CYAN; b.colorT = 1.0
        self.cornerPop = 0.0; self.popV = 0.0

    def _dvdNewColor(self, b):
        opts = [c for c in self.DVD_COLORS if c != b.colorTo]
        b.colorFrom = b.color; b.colorTo = random.choice(opts); b.colorT = 0.0

    def _upd_dvd(self, dt):
        b = self.bodies[0]
        if self.phase == 0:
            if self.phaseT > 11.0: b.target = 0.0
            bx, by = b.dirx, b.diry
            self._cruise(b, dt)
            hitX = (b.dirx != bx); hitY = (b.diry != by)
            if hitX or hitY:
                self._dvdNewColor(b)
                if hitX and hitY:                 # sarokba talalt! -> orom-pukk
                    self.popV += 5.0
            # puha szinatmenet (0.12 mp)
            b.colorT = min(1.0, b.colorT + dt / 0.12)
            b.color = tuple(int(b.colorFrom[k] + (b.colorTo[k] - b.colorFrom[k]) * b.colorT) for k in range(3))
            if self.phaseT > 11.8: self._next()
        else:
            b.seek(self.hx, self.hy, dt, 6.0)
            # visszafele visszaszinezodik ciankekre
            k = min(1.0, dt * 3)
            b.color = tuple(int(b.color[j] + (CYAN[j] - b.color[j]) * k) for j in range(3))
            if (b.settled(self.hx, self.hy) and self.phaseT > 0.6) or self.phaseT > 3.0:
                b.color = CYAN; self.done = True
        # sarok-pukk rugo
        kk = (2 * math.pi * 3.0) ** 2; cc = 2 * 0.25 * math.sqrt(kk)
        self.popV += (-kk * self.cornerPop - cc * self.popV) * dt
        self.cornerPop += self.popV * dt
        b.scale = 1.0 + max(-0.3, min(0.6, self.cornerPop))

    # ----------------------------------------------------------- 6) atom
    # Szetvalnak a szemek -> 3 egymasra dontott elektronpalya 3D-ben forog -> nagy szem a magban
    # -> minden osszetomorodik -> felrobban, a pixelek szetrepulnek -> visszaall a szempar
    def _init_atom(self):
        self.cx = self.W / 2; self.cy = self.H / 2
        self.R = min(self.W, self.H) * 0.34
        self.focal = self.R * 2.4
        self.core = self.bodies[0]                 # az eredeti par lesz a mag
        self.rings = []
        perRing = 6 if self.mini else 7
        for i, (start, phi, omega) in enumerate(((1.0, 0.0, 1.5), (3.2, math.radians(60), -1.25),
                                                 (5.4, math.radians(120), 1.8))):
            ring = {"start": start, "phi": phi, "incl": math.radians(72), "omega": omega,
                    "angle": random.uniform(0, 6.28), "spin": 0.0, "bodies": []}
            for j in range(perRing):
                e = Body(self.hx, self.hy); e.single = True; e.scale = 0.0
                e.spawn = start + j * 0.13; e.slot = j; e.alive = False
                ring["bodies"].append(e)
            self.rings.append(ring)
        self.ringR = 1.0
        self.nucleus = None
        self.exploded = False
        self.particles = []
        self.flashT = -1.0
        self.reform = None
        self.shake = 0.0

    def _ringPoint(self, ring, j, rFactor):
        n = len(ring["bodies"])
        th = ring["angle"] + 2 * math.pi * j / n
        x = self.R * rFactor * math.cos(th); y = self.R * rFactor * math.sin(th)
        ci, si = math.cos(ring["incl"]), math.sin(ring["incl"])
        y2, z = y * ci, y * si
        cp, sp = math.cos(ring["phi"]), math.sin(ring["phi"])
        X = x * cp - y2 * sp; Y = x * sp + y2 * cp
        persp = self.focal / (self.focal + z)
        return self.cx + X * persp, self.cy + Y * persp, z, persp

    def _upd_atom(self, dt):
        t = self.t
        core = self.core
        T_NUC, T_COLLAPSE, T_BOOM = 7.6, 11.0, 12.6

        if not self.exploded:
            # a mag (eredeti szempar) a kepernyo kozepere repul
            core.seek(self.cx, self.cy, dt, 4.0)
            if t < T_NUC:
                core.scale += (0.7 - core.scale) * min(1, dt * 3)

            # nagy szem a kozepen
            if t >= T_NUC and self.nucleus is None:
                n = Body(self.cx, self.cy); n.single = True; n.scale = 0.0
                n.born = t; self.nucleus = n; self.bodies_nucleus = n
            if self.nucleus is not None:
                n = self.nucleus
                n.blink(dt); n.jelly(dt)
                tt = t - n.born
                big = 3.0 * easeOutBack(tt / 0.7)
                core.scale = max(0.0, 0.7 * (1 - tt / 0.35))    # a kis par "beleolvad"
                if t < T_COLLAPSE:
                    n.scale = big
                else:
                    c = ease((t - T_COLLAPSE) / (T_BOOM - T_COLLAPSE))
                    n.scale = 3.0 * (1 - 0.8 * c)
                    w = int(255 * c)
                    n.color = (min(255, w + 40), 255, 255)              # felfeher izzas
                    self.shake = 14 * self.S * c * c
                n.x = self.cx + random.uniform(-1, 1) * self.shake
                n.y = self.cy + random.uniform(-1, 1) * self.shake

            # elektronpalyak
            if t >= T_COLLAPSE:
                self.ringR = 1 - ease((t - T_COLLAPSE) / 1.2)
            for ring in self.rings:
                spinTarget = ring["omega"] * (1 + 2.5 * (1 - self.ringR))
                ring["spin"] += (spinTarget - ring["spin"]) * min(1, dt * 1.2)
                ring["angle"] += ring["spin"] * dt
                ring["phi"] += 0.12 * dt
                for e in ring["bodies"]:
                    if t < e.spawn: continue
                    if not e.alive:
                        e.alive = True; e.x, e.y = core.x, core.y
                    tx, ty, z, persp = self._ringPoint(ring, e.slot, self.ringR)
                    e.seek(tx, ty, dt, 6.5 if t - e.spawn < 1.5 else 14.0)
                    e.depth = z
                    grow = easeOutBack((t - e.spawn) / 0.5)
                    shrink = 1.0 if t < T_COLLAPSE else max(0.0, self.ringR * 1.1)
                    e.scale = 0.55 * persp * grow * shrink
                    e.alpha = 0.55 + 0.45 * max(0.0, min(1.0, (1 - z / self.R) / 2))
                    e.blink(dt); e.jelly(dt)

            if t >= T_BOOM:
                self._boom()
        else:
            self._updParticles(dt)
            # a vegen a szempar puhan visszaall a helyen
            tb = t - self.boomT
            if tb > 1.7:
                if self.reform is None:
                    r = Body(self.hx, self.hy); r.scale = 0.0; self.reform = r
                self.reform.scale = easeOutBack((tb - 1.7) / 0.6)
                self.reform.blink(dt); self.reform.jelly(dt)
            if tb > 2.6 and not self.particles:
                self.reform.scale = 1.0; self.done = True
            elif tb > 4.0:
                self.done = True

    def _boom(self):
        self.exploded = True; self.boomT = self.t
        n = self.nucleus
        cx, cy = n.x, n.y
        w = 26 * self.S * n.scale; h = 40 * self.S * n.scale
        count = 380 if self.mini else 560
        base = max(self.W, self.H)
        palette = [(0, 255, 255)] * 6 + [(220, 255, 255)] * 3 + [(255, 255, 255), (120, 200, 255), (255, 230, 120)]
        for _ in range(count):
            # a pixelek a (osszetomorodott) szem teruleterol indulnak
            px = cx + random.uniform(-0.5, 0.5) * w
            py = cy + random.uniform(-0.5, 0.5) * h
            ang = math.atan2(py - cy, px - cx) + random.uniform(-0.6, 0.6)
            spd = base * (0.15 + 0.85 * random.random() ** 1.7) * 0.9
            self.particles.append({
                "x": px, "y": py, "vx": math.cos(ang) * spd, "vy": math.sin(ang) * spd,
                "size": random.uniform(2.5, 6.5) * self.S / 1.8,
                "life": random.uniform(1.3, 2.6), "age": 0.0,
                "color": random.choice(palette), "spin": random.uniform(-8, 8), "rot": 0.0})
        self.flashT = 0.0
        self.flashX, self.flashY = cx, cy

    def _updParticles(self, dt):
        alive = []
        drag = math.exp(-1.7 * dt)
        g = 260 * self.S / 1.8
        for p in self.particles:
            p["age"] += dt
            if p["age"] >= p["life"]: continue
            p["vx"] *= drag; p["vy"] = p["vy"] * drag + g * dt
            p["x"] += p["vx"] * dt; p["y"] += p["vy"] * dt
            p["rot"] += p["spin"] * dt
            alive.append(p)
        self.particles = alive
        if self.flashT >= 0:
            self.flashT += dt
            if self.flashT > 0.7: self.flashT = -1.0

    def _atomEyes(self):
        out = []
        if not self.exploded:
            items = []
            for ring in self.rings:
                for e in ring["bodies"]:
                    if e.alive and e.scale > 0.01:
                        items.append((e.depth, e))
            core = self.core
            if core.scale > 0.01:
                items.append((0.5, core))
            if self.nucleus is not None and self.nucleus.scale > 0.01:
                items.append((0.0, self.nucleus))
            items.sort(key=lambda it: -it[0])            # tavolabbi elobb (moge kerul)
            for _, b in items:
                out.extend(self._bodyEyes(b))
        elif self.reform is not None:
            out.extend(self._bodyEyes(self.reform))
        return out

    def extras(self, layer="front"):
        """Extra rajzelemek.
        layer='back' : ('orbit', [(x,y)...], alfa)  - halvany elektronpalyak a szemek mogott
        layer='front': ('px', x, y, meret, forgas, szin, alfa), ('flash', x, y, sugar, alfa)"""
        fx = []
        fn = getattr(self, "_fx_" + self.kind, None)        # UJ: a rampage_extra animacioi
        if fn is not None:
            return fn(layer)
        if self.kind != "atom":
            return fx
        if layer == "back":
            if self.exploded: return fx
            for ring in self.rings:
                a = 0.28 * ease((self.t - ring["start"] + 0.3) / 0.8) * max(0.0, self.ringR)
                if a <= 0.01: continue
                saved = ring["angle"]; pts = []
                n = len(ring["bodies"])
                for k in range(73):
                    ring["angle"] = 2 * math.pi * k / 72 - 2 * math.pi * 0 / n
                    x, y, z, pr = self._ringPoint(ring, 0, self.ringR)
                    pts.append((x, y))
                ring["angle"] = saved
                fx.append(("orbit", pts, a))
            return fx
        if not self.exploded:
            return fx
        if self.flashT >= 0:
            u = self.flashT / 0.7
            fx.append(("flash", self.flashX, self.flashY, max(self.W, self.H) * 0.75 * ease(u), (1 - u) ** 2))
        for p in self.particles:
            a = 1.0 - (p["age"] / p["life"]) ** 2
            fx.append(("px", p["x"], p["y"], p["size"], p["rot"], p["color"], a))
        return fx

    # ----------------------------------------------------------- kirajzolando szemek
    def _bodyEyes(self, b):
        sx, sy = b.sxsy()
        c = b.closeAmt()
        if self.mini or b.single:
            return [(b.x, b.y, sx, sy, True, c, b.color, b.alpha)]
        d = PAIR_DX * self.S * sx
        return [(b.x - d, b.y, sx, sy, True, c, b.color, b.alpha),
                (b.x + d, b.y, sx, sy, False, c, b.color, b.alpha)]

    def eyes(self):
        """Lista: (cx, cy, scaleX, scaleY, isLeft, closeAmt, szin(r,g,b), alfa[, forma][, forgas]) - kijelzo-pixelben."""
        fn = getattr(self, "_eyes_" + self.kind, None)      # UJ: a rampage_extra animacioi
        if fn is not None:
            return fn()
        if self.kind == "atom":
            return self._atomEyes()
        out = []
        if self.freeEyes:
            for i, b in enumerate(self.bodies):
                sx, sy = b.sxsy()
                out.append((b.x, b.y, sx, sy, i == 0, b.closeAmt(), b.color, b.alpha))
            return out
        for b in self.bodies:
            if b.scale <= 0.01: continue
            out.extend(self._bodyEyes(b))
        return out


# UJ: tovabbi animaciok (fekete lyuk, kigyo, matrix, kaleidoszkop, pingpong, olvadas, szel, hiperugras)
import rampage_extra as _extra  # noqa: E402
_extra.install(Rampage)

# UJ: szetesos animaciok (homokora, porra valas, uvegtores, gravitacio, vizcsepp, magnes)
import rampage_extra2 as _extra2  # noqa: E402
_extra2.install(Rampage)
