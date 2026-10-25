# -*- coding: utf-8 -*-
"""
Tovabbi teljes kepernyos animaciok (a rampage.Rampage osztalyhoz csatolva, install()).

  blackhole : fekete lyuk beszippantja (spagetti + pixelekre bomlik), majd kikopi, ujraepul
  snake     : kigyo - a szempar a fej, mogotte egyre kisebb szemek; kigyozik, farkat kergeti
  matrix    : zold szem-eso oszlopokban -> a kozepen ora szemparra all ossze -> vissza a helyere
  kaleido   : 6-szoros tukorszimmetrias, forgo, formavalto, szivarvanyos minta
  pong      : pingpong, a szempar a labda; a vegen az egyik uto elhibazza
  melt      : a szem elolvad, a tocsa hullamzik, majd a pixelek visszaszallnak
  wind      : szikrakka bomlik, a szel orvenyekben hordja, majd tolcser -> ujraepul
  hyper     : csillagok fenycsikka nyulnak, a szem kilo, majd a tuloldalrol visszaerkezik

Minden eyes()-elem: (cx, cy, sx, sy, isLeft, closeAmt, (r,g,b), alfa[, shape][, forgas_fok])
Extra rajzelemek (extras(layer)):
  ('px', x, y, meret, forgas, (r,g,b), alfa)       ('line', x0, y0, x1, y1, vastagsag, (r,g,b), alfa)
  ('rrect', x, y, w, h, sugar, (r,g,b), alfa)      ('glow', x, y, rx, ry, (r,g,b), alfa)
  ('blackhole', x, y, r, forgas, alfa)             ('flash', x, y, sugar, alfa)
"""
import math
import random
import colorsys

import rampage as R
import miniface as mf

EXTRA_KINDS = ["blackhole", "snake", "matrix", "kaleido", "pong", "melt", "wind", "hyper"]
GREEN = (40, 255, 90)


def clamp(v, a, b):
    return a if v < a else b if v > b else v


class P:
    """Pixel-reszecske."""
    __slots__ = ("x", "y", "vx", "vy", "hx", "hy", "size", "color", "a", "delay", "state",
                 "d", "ang", "w", "ph", "px", "py")

    def __init__(self, x, y, hx, hy, size, color=R.CYAN):
        self.x = x; self.y = y; self.vx = 0.0; self.vy = 0.0
        self.hx = hx; self.hy = hy; self.size = size; self.color = color
        self.a = 1.0; self.delay = 0.0; self.state = 0
        self.d = 0.0; self.ang = 0.0; self.w = 3.0; self.ph = random.uniform(0, 6.28)
        self.px = x; self.py = y

    def seek(self, tx, ty, dt, w):
        ax = w * w * (tx - self.x) - 2 * w * self.vx
        ay = w * w * (ty - self.y) - 2 * w * self.vy
        self.vx += ax * dt; self.vy += ay * dt
        self.x += self.vx * dt; self.y += self.vy * dt

    def settled(self, eps=1.2):
        return abs(self.hx - self.x) < eps and abs(self.hy - self.y) < eps and abs(self.vx) + abs(self.vy) < 30


class ExtraAnims:
    # ================= kozos segedek =================
    @property
    def u(self):
        return self.S / 1.8

    def _eyeCenters(self, cx, cy, scale=1.0):
        if self.mini:
            return [(cx, cy)]
        d = R.PAIR_DX * self.S * scale
        return [(cx - d, cy), (cx + d, cy)]

    def _eyeGrid(self, cx, cy, scale=1.0, step=None):
        """A szem(ek) "pixelei": racspontok a lekerekitett teglalapon belul."""
        S = self.S * scale
        w, h, r = 26 * S, 40 * S, 10 * S
        g = step or max(2.5, 4.0 * self.u * scale)
        pts = []
        for ex, ey in self._eyeCenters(cx, cy, scale):
            nx = int(w / g); ny = int(h / g)
            for i in range(nx):
                for j in range(ny):
                    x = -w / 2 + (i + 0.5) * w / nx
                    y = -h / 2 + (j + 0.5) * h / ny
                    qx = max(0.0, abs(x) - (w / 2 - r)); qy = max(0.0, abs(y) - (h / 2 - r))
                    if qx * qx + qy * qy <= r * r:
                        pts.append((ex + x, ey + y))
        return pts, g

    def _homeParticles(self, fromX, fromY, color=R.CYAN):
        """Reszecskek a (fromX,fromY)-nal levo szempar pixeleibol; celjuk az otthoni szempar pixelei."""
        src, g = self._eyeGrid(fromX, fromY)
        dst, _ = self._eyeGrid(self.hx, self.hy)
        parts = []
        for (x, y), (hx, hy) in zip(src, dst):
            parts.append(P(x, y, hx, hy, g * 1.08, color))
        return parts

    def _pxFx(self, parts, alphaMul=1.0):
        out = []
        for p in parts:
            a = p.a * alphaMul
            if a > 0.01:
                out.append(("px", p.x, p.y, p.size, 0.0, p.color, a))
        return out

    def _finalEyes(self):
        """A vegso, otthon ujraepult szempar (beusztatva self.ff szerint)."""
        if getattr(self, "ff", 0.0) <= 0.0:
            return []
        b = R.Body(self.hx, self.hy)
        b.alpha = self.ff
        return self._bodyEyes(b)

    def _updFinalFade(self, dt, parts):
        """Ha minden reszecske a helyen van: a szempar beuszik, a reszecskek eltunnek -> kesz."""
        if all(p.settled(2.0) for p in parts):
            self.ff = min(1.0, getattr(self, "ff", 0.0) + dt / 0.3)
            for p in parts:
                p.a = 1.0 - self.ff
            if self.ff >= 1.0:
                self.done = True

    # ================= 1) FEKETE LYUK =================
    def _init_blackhole(self):
        u = self.u
        m = min(self.W, self.H)
        for _ in range(20):
            bx = random.uniform(0.3, 0.7) * self.W; by = random.uniform(0.35, 0.65) * self.H
            if math.hypot(bx - self.hx, by - self.hy) > 0.3 * m: break
        self.bh = (bx, by)
        self.bhR0 = 0.055 * m; self.bhR = 0.0; self.bhSpin = 0.0
        dx, dy = self.hx - bx, self.hy - by
        self.bd0 = math.hypot(dx, dy); self.bd = self.bd0; self.ba = math.atan2(dy, dx)
        self.parts = []; self.ff = 0.0; self.bhShow = 0.0
        self.bodies[0].stretch = 0.0

    def _bhOmega(self, d):
        return 0.9 + 7.0 * (self.bhR0 / max(d, self.bhR0 * 0.4)) ** 1.1

    def _upd_blackhole(self, dt):
        u = self.u; bx, by = self.bh; b = self.bodies[0]
        self.bhSpin += dt * (1.5 + 3.0 * (1 - self.bd / max(1, self.bd0)))
        if self.phase == 0:                          # a lyuk kinyilik
            self.bhR = self.bhR0 * R.easeOutBack(self.phaseT / 1.0)
            self.bhShow = min(1.0, self.phaseT / 0.6)
            if random.random() < 0.25:                         # a szem idegesen remeg
                b.kick("x", random.uniform(-1.5, 1.5) * self.phaseT)
            if self.phaseT > 1.1:
                self._next()
        elif self.phase == 1:                        # spiralban beszippantodik
            if not self.parts:
                prog = 1 - self.bd / self.bd0
                vr = (25 + 700 * prog ** 1.6 + 120 * self.phaseT) * u
                self.bd -= vr * dt
                self.ba += self._bhOmega(self.bd) * dt
                b.x = bx + self.bd * math.cos(self.ba); b.y = by + self.bd * math.sin(self.ba)
                b.stretch = clamp((self.bhR0 * 3.2 / max(self.bd, 1)) ** 1.6 * 0.35, 0, 1.4)
                if self.bd < self.bhR0 * 2.6:
                    # pixelekre bomlik (a celjuk mar az otthoni hely)
                    self.parts = self._homeParticles(b.x, b.y)
                    for p in self.parts:
                        p.d = math.hypot(p.x - bx, p.y - by); p.ang = math.atan2(p.y - by, p.x - bx)
                        p.w = random.uniform(0.8, 1.3)
            else:
                alive = 0
                for p in self.parts:
                    if p.a <= 0: continue
                    p.d -= (180 + 500 * p.w) * u * dt
                    p.ang += self._bhOmega(p.d) * 1.2 * dt
                    p.x = bx + p.d * math.cos(p.ang); p.y = by + p.d * math.sin(p.ang)
                    p.a = clamp((p.d - self.bhR0 * 0.3) / (self.bhR0 * 1.2), 0, 1)
                    if p.a > 0: alive += 1
                if alive == 0:
                    self._next()
        elif self.phase == 2:                        # csend - a lyuk lelegzik
            self.bhR = self.bhR0 * (1 + 0.1 * math.sin(self.phaseT * 9) * min(1, self.phaseT))
            if self.phaseT > 1.1:
                self._next()
                self.flashT = 0.0; self.flashX, self.flashY = bx, by
                for p in self.parts:
                    a = random.uniform(0, 2 * math.pi); sp = random.uniform(500, 1500) * u
                    p.x, p.y = bx, by; p.vx = math.cos(a) * sp; p.vy = math.sin(a) * sp
                    p.a = 1.0; p.delay = random.uniform(0.15, 0.45); p.w = random.uniform(2.6, 3.8)
        else:                                        # kikopi -> ujraepul otthon
            if self.flashT >= 0:
                self.flashT += dt
                if self.flashT > 0.6: self.flashT = -1
            self.bhR = self.bhR0 * (1 - R.ease(self.phaseT / 0.8))
            self.bhShow = 1 - R.ease(self.phaseT / 0.9)
            drag = math.exp(-2.5 * dt)
            for p in self.parts:
                if self.phaseT < p.delay:
                    p.vx *= drag; p.vy *= drag; p.x += p.vx * dt; p.y += p.vy * dt
                else:
                    p.seek(p.hx, p.hy, dt, p.w)
            if self.phaseT > 1.0:
                self._updFinalFade(dt, self.parts)
            if self.phaseT > 6.0:
                self.done = True

    def _eyes_blackhole(self):
        b = self.bodies[0]
        if self.phase >= 1 and self.parts or self.phase >= 2:
            return self._finalEyes()
        bx, by = self.bh
        ang = math.atan2(b.y - by, b.x - bx)
        rot = math.degrees(ang) + 90
        sx = (1 - 0.35 * b.stretch); sy = (1 + b.stretch)
        out = []
        tx, ty = -math.sin(ang), math.cos(ang)     # erintoleges irany
        if self.mini:
            out.append((b.x, b.y, sx, sy, True, b.closeAmt(), R.CYAN, 1.0, None, rot))
        else:
            d = R.PAIR_DX * self.S * sx
            out.append((b.x - tx * d, b.y - ty * d, sx, sy, True, b.closeAmt(), R.CYAN, 1.0, None, rot))
            out.append((b.x + tx * d, b.y + ty * d, sx, sy, False, b.closeAmt(), R.CYAN, 1.0, None, rot))
        return out

    def _fx_blackhole(self, layer):
        bx, by = self.bh
        if layer == "back":
            if self.bhR > 0.5 and self.bhShow > 0.01:
                return [("blackhole", bx, by, self.bhR, self.bhSpin, self.bhShow)]
            return []
        fx = self._pxFx(self.parts)
        if getattr(self, "flashT", -1) >= 0:
            u = self.flashT / 0.6
            fx.append(("flash", self.flashX, self.flashY, max(self.W, self.H) * 0.5 * R.ease(u), (1 - u) ** 2))
        return fx

    # ================= 3) KIGYO =================
    def _init_snake(self):
        u = self.u
        self.nSeg = 12 if self.mini else 16
        self.spacing = 30 * u
        self.heading = math.atan2(self.H / 2 - self.hy, self.W / 2 - self.hx)
        self.path = [(0.0, self.hx, self.hy)]
        self.pathLen = 0.0
        self.circleUntil = -1.0; self.nextCircle = random.uniform(3.5, 5.0)
        self.retract = 1.0; self.homing = False; self.snakeSpeed = 0.0
        self.segEase = 0.0

    def _pathPoint(self, s):
        path = self.path
        if s <= path[0][0]: return path[0][1], path[0][2]
        lo, hi = 0, len(path) - 1
        while lo < hi - 1:
            mid = (lo + hi) // 2
            if path[mid][0] < s: lo = mid
            else: hi = mid
        s0, x0, y0 = path[lo]; s1, x1, y1 = path[hi]
        k = 0 if s1 == s0 else (s - s0) / (s1 - s0)
        return x0 + (x1 - x0) * k, y0 + (y1 - y0) * k

    def _turnToward(self, target, rate, dt):
        diff = (target - self.heading + math.pi) % (2 * math.pi) - math.pi
        self.heading += clamp(diff, -rate * dt, rate * dt)

    def _upd_snake(self, dt):
        u = self.u; b = self.bodies[0]; t = self.t
        if self.phase == 0:
            base = 520 * u * R.ease(t / 0.7)
            self.snakeSpeed = base
            margin = 170 * u
            near = (b.x < margin or b.x > self.W - margin or b.y < margin or b.y > self.H - margin)
            if t >= self.nextCircle and self.circleUntil < 0 and not near:
                self.circleUntil = t + 2.4
            if self.circleUntil > 0 and t < self.circleUntil:
                self.heading += 3.4 * dt                         # a sajat farkat kergeti
            else:
                if self.circleUntil > 0 and t >= self.circleUntil:
                    self.circleUntil = -1.0; self.nextCircle = t + random.uniform(3.0, 4.5)
                self.heading += math.sin(t * 4.2) * 2.4 * dt     # kigyozas
                if near:
                    self._turnToward(math.atan2(self.H / 2 - b.y, self.W / 2 - b.x), 3.2, dt)
            if t > 11.0:
                self._next()
        elif self.phase == 1:                                    # hazater
            dist = math.hypot(self.hx - b.x, self.hy - b.y)
            self._turnToward(math.atan2(self.hy - b.y, self.hx - b.x), 5.0, dt)
            self.snakeSpeed = min(520 * u, max(60 * u, dist * 3.0))
            if dist < 6 * u or self.phaseT > 6.0:
                self._next()
        else:                                                    # felcsavarodik, behuzodik
            self.snakeSpeed = 0.0
            b.seek(self.hx, self.hy, dt, 8.0)
            self.retract = 1 - R.ease(self.phaseT / 1.1)
            if self.phaseT > 1.25:
                self.done = True
            return
        b.x += math.cos(self.heading) * self.snakeSpeed * dt
        b.y += math.sin(self.heading) * self.snakeSpeed * dt
        step = math.hypot(b.x - self.path[-1][1], b.y - self.path[-1][2])
        if step > 0.5:
            self.pathLen += step
            self.path.append((self.pathLen, b.x, b.y))
            keep = self.pathLen - (self.nSeg + 3) * self.spacing
            while len(self.path) > 2 and self.path[1][0] < keep:
                self.path.pop(0)

    def _eyes_snake(self):
        b = self.bodies[0]; out = []
        n = self.nSeg
        for i in range(n, 0, -1):                                # farok elobb, a fej legfelul
            s = self.pathLen - i * self.spacing * self.retract
            x, y = self._pathPoint(s)
            k = i / n
            sc = (0.72 - 0.42 * k) * (0.3 + 0.7 * self.retract) if self.retract < 1 else 0.72 - 0.42 * k
            col = (0, int(255 - 70 * k), int(255 - 40 * k))
            out.append((x, y, sc, sc, i % 2 == 0, 0.0, col, 1.0 - 0.4 * k))
        out.extend(self._bodyEyes(b))
        return out

    # ================= 4) MATRIX =================
    def _init_matrix(self):
        u = self.u
        nCols = clamp(int(self.W / (85 * u)), 8, 22)
        self.mScale = 0.42
        self.mSpace = 40 * self.S * self.mScale * 1.18
        self.cols = []
        for i in range(nCols):
            x = (i + 0.5) * self.W / nCols + random.uniform(-12, 12) * u
            self.cols.append(self._newDrop(x, random.uniform(-self.H * 0.9, -20)))
        self.mEyes = []; self.giant = None; self.ff = 0.0
        self.fadeOrig = 1.0

    def _newDrop(self, x, y):
        return {"x": x, "y": y, "v": random.uniform(330, 780) * self.u, "L": random.randint(5, 9)}

    def _upd_matrix(self, dt):
        u = self.u; b = self.bodies[0]
        if self.phase == 0:                                  # eso
            self.fadeOrig = max(0.0, 1 - self.phaseT / 0.5)
            for c in self.cols:
                c["y"] += c["v"] * dt
                if c["y"] - c["L"] * self.mSpace > self.H:
                    c.update(self._newDrop(c["x"], random.uniform(-self.H * 0.3, -20)))
            if self.phaseT > 6.0:
                # az eso megall: minden lathato szembol test lesz, ami a nagy szempar alakjaba all
                for c in self.cols:
                    for k in range(c["L"] + 1):
                        y = c["y"] - k * self.mSpace
                        if -20 < y < self.H + 20:
                            e = R.Body(c["x"], y); e.single = True; e.scale = self.mScale
                            a = 1.0 if k == 0 else (1 - k / (c["L"] + 1)) ** 1.2
                            e.alpha = a; e.color = (200, 255, 210) if k == 0 else GREEN
                            self.mEyes.append(e)
                self.G = 4.2 if not self.mini else 3.0
                cx, cy = self.W / 2, self.H / 2
                n = max(1, len(self.mEyes))
                area = 2 * 26 * 40 * (self.S * self.G) ** 2 * 0.85
                pts, _ = self._eyeGrid(cx, cy, self.G, step=math.sqrt(area / n))
                random.shuffle(pts)
                for i, e in enumerate(self.mEyes):
                    e.tx, e.ty = pts[i % len(pts)] if pts else (cx, cy)
                    e.delay = random.uniform(0, 0.5)
                self._next()
        elif self.phase == 1:                                # a kozepre aramlanak
            for e in self.mEyes:
                if self.phaseT < e.delay: continue
                e.seek(e.tx, e.ty, dt, 3.6)
                e.alpha += (1 - e.alpha) * min(1, dt * 2)
                e.color = GREEN
            if self.phaseT > 2.3:
                g = R.Body(self.W / 2, self.H / 2); g.scale = self.G; g.alpha = 0.0; g.color = GREEN
                self.giant = g
                self._next()
        elif self.phase == 2:                                # ora szempar: beuszik, pislog, ciankekre valt
            g = self.giant
            g.alpha = min(1.0, g.alpha + dt / 0.4)
            for e in self.mEyes:
                e.alpha = max(0.0, e.alpha - dt / 0.4)
            if 0.7 < self.phaseT and g.blinkT < 0 and not getattr(self, "blinked", False):
                g.blinkT = 0.0; self.blinked = True
            g.blink(dt); g.jelly(dt)
            k = clamp((self.phaseT - 0.6) / 1.0, 0, 1)
            g.color = (int(GREEN[0] * (1 - k)), 255, int(GREEN[2] + (255 - GREEN[2]) * k))
            if self.phaseT > 1.9:
                self.gd0 = math.hypot(self.hx - g.x, self.hy - g.y) or 1.0
                self._next()
        else:                                                # vissza a helyere, kicsire
            g = self.giant
            g.seek(self.hx, self.hy, dt, 3.6)
            d = math.hypot(self.hx - g.x, self.hy - g.y)
            g.scale = 1 + (self.G - 1) * clamp(d / self.gd0, 0, 1) ** 0.8
            if (g.settled(self.hx, self.hy) and abs(g.scale - 1) < 0.02) or self.phaseT > 4.0:
                self.done = True

    def _eyes_matrix(self):
        out = []
        if self.phase == 0:
            b = self.bodies[0]
            if self.fadeOrig > 0:
                for e in self._bodyEyes(b):
                    out.append(e[:6] + (GREEN, self.fadeOrig))
            for c in self.cols:
                for k in range(c["L"], -1, -1):
                    y = c["y"] - k * self.mSpace
                    if y < -40 or y > self.H + 40: continue
                    a = 1.0 if k == 0 else (1 - k / (c["L"] + 1)) ** 1.2
                    col = (200, 255, 210) if k == 0 else GREEN
                    out.append((c["x"], y, self.mScale, self.mScale, True, 0.0, col, a))
            return out
        for e in self.mEyes:
            if e.alpha > 0.01:
                out.append((e.x, e.y, e.scale, e.scale, True, 0.0, e.color, e.alpha))
        if self.giant is not None:
            out.extend(self._bodyEyes(self.giant))
        return out

    # ================= 5) KALEIDOSZKOP =================
    KAL_SHAPES = [mf.SHAPE_DEFS[mf.SHAPE_NORMAL], mf.SHAPE_DEFS[mf.SHAPE_CURIOUS], mf.SHAPE_DEFS[mf.SHAPE_CUTE],
                  mf.SHAPE_DEFS[mf.SHAPE_CIRCLE], mf.SHAPE_DEFS[mf.SHAPE_FOCUSED], mf.SHAPE_DEFS[mf.SHAPE_ANGRY]]

    def _init_kaleido(self):
        self.kRot = 0.0; self.kR = 0.0; self.kHue = random.random()
        self.kRmax = min(self.W, self.H) * 0.3
        self.kAlpha = 0.0
        self.kBlinkT = -1.0; self.kNextBlink = 2.5

    def _upd_kaleido(self, dt):
        b = self.bodies[0]
        self.kRot += dt * (0.5 + 0.35 * math.sin(self.t * 0.6))
        if self.phase == 0:                                  # kozepre
            b.seek(self.W / 2, self.H / 2, dt, 4.0)
            if self.phaseT > 1.1: self._next()
        elif self.phase == 1:                                # kinyilik + jatszik
            b.seek(self.W / 2, self.H / 2, dt, 6.0)
            tt = self.phaseT
            self.kAlpha = min(1.0, tt / 0.4)
            self.kR = self.kRmax * R.easeOutBack(tt / 1.1) * (1 + 0.14 * math.sin(tt * 1.7))
            # kozos pislogas
            if self.kBlinkT >= 0:
                self.kBlinkT += dt
                if self.kBlinkT > 0.3: self.kBlinkT = -1
            elif tt > self.kNextBlink:
                self.kBlinkT = 0.0; self.kNextBlink = tt + 3.2
            if tt > 9.0: self._next(); self.kR0 = self.kR
        elif self.phase == 2:                                # osszecsukodik
            self.kR = self.kR0 * (1 - R.ease(self.phaseT / 0.9))
            self.kAlpha = 1 - R.ease(self.phaseT / 0.9)
            b.seek(self.W / 2, self.H / 2, dt, 6.0)
            if self.phaseT > 0.95: self._next()
        else:                                                # haza
            b.seek(self.hx, self.hy, dt, 4.5)
            if b.settled(self.hx, self.hy) or self.phaseT > 3.0: self.done = True

    def _kalShape(self, tt):
        period = 1.6
        n = len(self.KAL_SHAPES)
        i = int(tt / period) % n
        frac = (tt / period) % 1.0
        bl = R.ease((frac - 0.65) / 0.35)
        return mf.lerpShape(self.KAL_SHAPES[i], self.KAL_SHAPES[(i + 1) % n], bl)

    def _eyes_kaleido(self):
        b = self.bodies[0]; out = []
        cx, cy = self.W / 2, self.H / 2
        if self.phase in (0, 3):
            out.extend(self._bodyEyes(b))
        elif self.phase == 1 and self.phaseT < 0.4:
            out.extend(e[:7] + (1 - self.phaseT / 0.4,) for e in self._bodyEyes(b))
        elif self.phase == 2:
            out.extend(e[:7] + (min(1.0, self.phaseT / 0.9),) for e in self._bodyEyes(b))
        if self.kR > 1 and self.kAlpha > 0.01:
            tt = self.phaseT if self.phase == 1 else 9.0
            shape = self._kalShape(tt)
            close = 0.0
            if self.kBlinkT >= 0:
                u = self.kBlinkT / 0.3
                close = min(1.0, u / 0.4 if u < 0.4 else (1 - u) / 0.6)
            delta = 0.26 + 0.14 * math.sin(self.t * 2.3)
            for ring, (rf, sc, mirror) in enumerate(((1.0, 0.95, True), (0.48, 0.7, False))):
                for k in range(6):
                    base = self.kRot * (1 if ring == 0 else -1.4) + k * math.pi / 3
                    hue = (self.kHue + k / 6 + self.t * 0.12 + ring * 0.08) % 1.0
                    col = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(hue, 0.85, 1.0))
                    angs = ((base - delta, True), (base + delta, False)) if mirror else ((base, True),)
                    for a, isL in angs:
                        x = cx + math.cos(a) * self.kR * rf; y = cy + math.sin(a) * self.kR * rf
                        rot = math.degrees(a) + 90
                        out.append((x, y, sc, sc, isL, close, col, self.kAlpha, shape, rot))
        return out

    # ================= 7) PINGPONG =================
    def _init_pong(self):
        u = self.u
        self.padW = 16 * u; self.padH = 0.2 * self.H
        self.padX = [60 * u, self.W - 60 * u]
        self.padY = [self.H / 2, self.H / 2]; self.padV = [0.0, 0.0]
        self.padA = 0.0
        self.hits = 0; self.missAfter = random.randint(5, 8); self.loser = None
        self.ballV = (0.0, 0.0)
        b = self.bodies[0]; b.scale = 0.8
        self.ballHalfW = (R.HALF_W_ONE if self.mini else R.HALF_W_PAIR) * self.S * 0.8 * 0.85
        self.ballHalfH = R.HALF_H * self.S * 0.8 * 0.85
        self.shy = 0.0

    def _upd_pong(self, dt):
        u = self.u; b = self.bodies[0]
        bw, bh = self.ballHalfW, self.ballHalfH
        if self.phase in (0, 1, 2): self.padA = min(1.0, self.padA + dt / 0.6)
        if self.phase == 0:                                  # kozepre + adogatas
            b.seek(self.W / 2, self.H / 2, dt, 4.0)
            if self.phaseT > 1.2:
                side = 1 if self.hx < self.W / 2 else -1
                a = random.uniform(-0.45, 0.45)
                sp = 680 * u
                b.vx = side * math.cos(a) * sp; b.vy = math.sin(a) * sp
                self._next()
        elif self.phase == 1:                                # meccs
            b.x += b.vx * dt; b.y += b.vy * dt
            if b.y < bh: b.y = bh; b.vy = abs(b.vy); b.kick("y", 5)
            if b.y > self.H - bh: b.y = self.H - bh; b.vy = -abs(b.vy); b.kick("y", 5)
            for i, sgn in ((0, -1), (1, 1)):
                if self.loser == i: continue
                px = self.padX[i]
                towards = (b.vx < 0) if i == 0 else (b.vx > 0)
                edge = b.x - bw if i == 0 else b.x + bw
                if towards and ((i == 0 and edge <= px + self.padW / 2) or (i == 1 and edge >= px - self.padW / 2)):
                    if abs(b.y - self.padY[i]) < self.padH / 2 + bh * 0.6:
                        sp = math.hypot(b.vx, b.vy) * 1.08
                        off = (b.y - self.padY[i]) / (self.padH / 2)
                        a = clamp(off * 0.75, -0.9, 0.9)
                        b.vx = -sgn * math.cos(a) * sp; b.vy = math.sin(a) * sp
                        b.x = px - sgn * (self.padW / 2 + bw)
                        b.kick("x", 7); self.hits += 1
                        if self.hits >= self.missAfter and self.loser is None:
                            self.loser = 1 - i                     # a kovetkezo utes mellemegy
            if b.x < -bw * 2.5 or b.x > self.W + bw * 2.5:
                self.exitSide = 0 if b.x < 0 else 1
                self._next()
        elif self.phase == 2:                                # kint van... csend
            if self.phaseT > 0.9:
                edgeX = -bw * 0.3 if self.exitSide == 0 else self.W + bw * 0.3
                b.x = edgeX - (bw * 1.5 if self.exitSide == 0 else -bw * 1.5)
                b.y = clamp(b.y, bh * 2, self.H - bh * 2); b.vx = b.vy = 0
                self.peekX = edgeX + (bw * 0.6 if self.exitSide == 0 else -bw * 0.6)
                self._next()
        elif self.phase == 3:                                # szegyenlosen visszakukucskal
            self.padA = max(0.0, self.padA - dt / 0.8)
            self.shy = min(0.4, self.shy + dt)
            b.seek(self.peekX, b.y, dt, 3.0)
            if self.phaseT > 1.8: self._next()
        else:                                                # haza
            self.padA = max(0.0, self.padA - dt / 0.8)
            self.shy = max(0.0, self.shy - dt)
            b.seek(self.hx, self.hy, dt, 3.8)
            b.scale += (1.0 - b.scale) * min(1, dt * 3)
            if (b.settled(self.hx, self.hy) and abs(b.scale - 1) < 0.02) or self.phaseT > 4.0:
                self.done = True
        # utok mozgasa (rugo a cel fele)
        for i in range(2):
            target = self.H / 2
            if self.phase == 1:
                coming = (b.vx < 0) if i == 0 else (b.vx > 0)
                if coming:
                    target = b.y
                    if self.loser == i:
                        target = b.y + math.copysign(self.padH * 1.1, self.H / 2 - b.y)
            w = 6.0
            a = w * w * (target - self.padY[i]) - 2 * w * self.padV[i]
            self.padV[i] += a * dt; self.padY[i] += self.padV[i] * dt
            self.padY[i] = clamp(self.padY[i], self.padH / 2, self.H - self.padH / 2)

    def _eyes_pong(self):
        b = self.bodies[0]
        return [e[:5] + (max(e[5], self.shy),) + e[6:] for e in self._bodyEyes(b)]

    def _fx_pong(self, layer):
        if layer == "back" or self.padA <= 0.01: return []
        u = self.u; fx = []
        for i in range(2):
            fx.append(("rrect", self.padX[i] - self.padW / 2, self.padY[i] - self.padH / 2,
                       self.padW, self.padH, self.padW / 2, R.CYAN, self.padA))
        dash = 26 * u; gap = 22 * u; y = gap / 2
        while y < self.H:
            fx.append(("rrect", self.W / 2 - 3 * u, y, 6 * u, dash, 3 * u, R.CYAN, 0.18 * self.padA))
            y += dash + gap
        return fx

    # ================= 8) OLVADAS =================
    def _init_melt(self):
        u = self.u
        self.parts = self._homeParticles(self.hx, self.hy)
        self.ff = 0.0
        if not self.parts: self.done = True; return
        bottom = max(p.y for p in self.parts); top = min(p.y for p in self.parts)
        h = max(1.0, bottom - top)
        for p in self.parts:
            p.delay = 0.25 + (bottom - p.y) / h * 1.6 + random.uniform(0, 0.35)
            p.state = 0
        self.floor = self.H - 8 * u
        self.landed = 0

    def _upd_melt(self, dt):
        u = self.u; g = 1700 * u
        if self.phase == 0:                                  # olvad, lecsorog, tocsaba gyulik
            landed = 0
            fr = math.exp(-3.2 * dt)
            for p in self.parts:
                if p.state == 0:
                    if self.phaseT >= p.delay:
                        p.state = 1; p.vx = random.uniform(-40, 40) * u; p.vy = 0
                        p.x += random.uniform(-1, 1) * u
                    else:
                        # mar "langyos": enyhen remeg, lefele nyulik
                        p.y += math.sin(self.t * 20 + p.ph) * 0.15 * u
                elif p.state == 1:
                    p.vy += g * dt; p.x += p.vx * dt; p.y += p.vy * dt
                    fl = self.floor - random.uniform(0, 6) * u
                    if p.y >= fl:
                        p.y = fl; p.state = 2; p.vy = 0
                        p.vx = random.choice((-1, 1)) * random.uniform(60, 420) * u
                elif p.state == 2:
                    p.vx *= fr; p.x += p.vx * dt
                    p.x = clamp(p.x, 4 * u, self.W - 4 * u)
                    landed += 1
            self.landed = landed
            if landed == len(self.parts) and all(abs(p.vx) < 15 * u for p in self.parts):
                for p in self.parts: p.d = p.y
                self._next()
        elif self.phase == 1:                                # a tocsa hullamzik
            env = math.sin(clamp(self.phaseT / 1.8, 0, 1) * math.pi)
            for p in self.parts:
                p.y = p.d - abs(math.sin(p.x * 0.02 / u + self.t * 7)) * 9 * u * env
            if self.phaseT > 1.8:
                for p in self.parts:
                    p.delay = random.uniform(0, 0.7); p.vy = -random.uniform(300, 700) * u; p.vx = 0
                    p.w = random.uniform(2.8, 3.8)
                self._next()
        else:                                                # visszaszallnak a helyukre
            for p in self.parts:
                if self.phaseT < p.delay: continue
                p.seek(p.hx, p.hy, dt, p.w)
            self._updFinalFade(dt, self.parts)
            if self.phaseT > 6.0: self.done = True

    def _eyes_melt(self):
        return self._finalEyes()

    def _fx_melt(self, layer):
        if layer == "back":
            if self.phase == 2 and self.phaseT > 0.8 or not self.parts: return []
            xs = [p.x for p in self.parts if p.state == 2] if self.phase == 0 else [p.x for p in self.parts]
            if len(xs) < 5: return []
            frac = len(xs) / len(self.parts)
            if self.phase == 2: frac *= 1 - self.phaseT / 0.8
            mx = sum(xs) / len(xs); spread = (max(xs) - min(xs)) / 2 + 30 * self.u
            return [("glow", mx, self.floor, spread * 1.1, 26 * self.u, R.CYAN, 0.55 * frac)]
        return self._pxFx(self.parts)

    # ================= 9) SZIKRA-SZEL =================
    def _init_wind(self):
        u = self.u
        self.parts = self._homeParticles(self.hx, self.hy)
        self.ff = 0.0
        for p in self.parts:
            a = random.uniform(0, 2 * math.pi); sp = random.uniform(200, 650) * u
            p.vx = math.cos(a) * sp; p.vy = math.sin(a) * sp
            p.color = random.choice((R.CYAN, R.CYAN, (210, 255, 255), (255, 255, 255), (120, 200, 255)))
            p.size *= random.uniform(0.6, 1.0)

    def _field(self, x, y, t):
        u = self.u; k = 0.0032 / u
        vx = 300 * u * math.sin(y * k * 1.3 + t * 0.8) + 200 * u * math.cos((x * 0.7 + y) * k * 0.9 - t * 1.1) + 110 * u
        vy = 250 * u * math.cos(x * k * 1.1 - t * 0.9) + 180 * u * math.sin((x - y * 0.6) * k + t * 0.6)
        return vx, vy

    def _upd_wind(self, dt):
        u = self.u; t = self.t
        for p in self.parts:
            p.px, p.py = p.x, p.y
        if self.phase == 0:                                  # robbanas + szel
            blend = min(1.0, dt * (1.2 if self.phaseT < 0.8 else 2.4))
            for p in self.parts:
                fx, fy = self._field(p.x, p.y, t)
                p.vx += (fx - p.vx) * blend; p.vy += (fy - p.vy) * blend
                p.x += p.vx * dt; p.y += p.vy * dt
                if p.x < -10: p.x += self.W + 20; p.px = p.x
                elif p.x > self.W + 10: p.x -= self.W + 20; p.px = p.x
                if p.y < -10: p.y += self.H + 20; p.py = p.y
                elif p.y > self.H + 10: p.y -= self.H + 20; p.py = p.y
            if self.phaseT > 7.0: self._next()
        elif self.phase == 1:                                # tolcser az otthon fele
            k = min(1.0, self.phaseT / 1.2)
            for p in self.parts:
                fx, fy = self._field(p.x, p.y, t)
                dx, dy = self.hx - p.x, self.hy - p.y
                d = math.hypot(dx, dy) or 1.0
                inward = min(1000 * u, d * 1.6)
                tang = 650 * u * min(1.0, d / (220 * u))
                vxT = dx / d * inward - dy / d * tang
                vyT = dy / d * inward + dx / d * tang
                tx = fx * (1 - k) + vxT * k; ty = fy * (1 - k) + vyT * k
                p.vx += (tx - p.vx) * min(1, dt * 3); p.vy += (ty - p.vy) * min(1, dt * 3)
                p.x += p.vx * dt; p.y += p.vy * dt
            if self.phaseT > 2.4:
                self._next()
        else:                                                # pontosan a helyere
            for p in self.parts:
                p.seek(p.hx, p.hy, dt, 6.0)
            self._updFinalFade(dt, self.parts)
            if self.phaseT > 5.0: self.done = True

    def _eyes_wind(self):
        return self._finalEyes()

    def _fx_wind(self, layer):
        if layer == "back": return []
        out = []
        for p in self.parts:
            if p.a <= 0.01: continue
            tw = 0.65 + 0.35 * math.sin(self.t * 11 + p.ph)
            if self.phase == 2:
                out.append(("px", p.x, p.y, p.size, 0.0, p.color, p.a))
            else:
                tx = p.x - p.vx * 0.035; ty = p.y - p.vy * 0.035
                out.append(("line", tx, ty, p.x, p.y, p.size * 0.9, p.color, p.a * tw))
        return out

    # ================= 10) HIPERUGRAS =================
    def _init_hyper(self):
        n = 120 if self.mini else 170
        self.stars = [self._newStar(random.uniform(0.05, 1.0)) for _ in range(n)]
        self.warp = 0.12; self.starA = 0.0
        self.shot = False; self.zoom = 1.0; self.zoomA = 1.0
        self.shake = 0.0; self.flashT = -1.0
        self.arrived = False

    def _newStar(self, z=1.0):
        return [random.uniform(-1, 1), random.uniform(-1, 1), z]

    def _proj(self, s, z):
        f = max(self.W, self.H) * 0.5
        return self.W / 2 + s[0] / z * f, self.H / 2 + s[1] / z * f * 0.75

    def _upd_hyper(self, dt):
        u = self.u; b = self.bodies[0]; t = self.t
        T_SHOT = 4.3
        # csillagsebesseg
        if t < T_SHOT:
            self.warp = 0.12 + 3.6 * R.ease((t - 0.8) / (T_SHOT - 0.8)) ** 2
            self.starA = min(1.0, t / 0.8)
        else:
            self.warp = 0.12 + 3.6 * (1 - R.ease((t - T_SHOT) / 1.8))
            self.starA = 1 - R.ease((t - T_SHOT - 0.8) / 1.4)
        for s in self.stars:
            s[2] -= self.warp * dt * 0.5
            x, y = self._proj(s, max(s[2], 0.01))
            if s[2] <= 0.02 or x < -50 or x > self.W + 50 or y < -50 or y > self.H + 50:
                s[:] = self._newStar(1.0)
        if self.flashT >= 0:
            self.flashT += dt
            if self.flashT > 0.6: self.flashT = -1
        if self.phase == 0:                                  # kozepre, remeg
            b.seek(self.W / 2, self.H / 2, dt, 3.5)
            self.shake = 7 * u * R.ease((t - 1.2) / (T_SHOT - 1.2)) ** 2
            if t >= T_SHOT:
                self.flashT = 0.0; self.flashX, self.flashY = b.x, b.y
                self._next()
        elif self.phase == 1:                                # kilo a nezo fele
            self.shake = 0.0
            k = R.ease(self.phaseT / 0.35)
            self.zoom = 1 + 9 * k ** 2; self.zoomA = 1 - k
            if self.phaseT > 2.2:
                fromLeft = self.hx > self.W / 2
                b.x = -200 * u if fromLeft else self.W + 200 * u
                b.y = self.hy; b.vx = (1 if fromLeft else -1) * 2600 * u; b.vy = 0
                self.zoom = 1.0; self.zoomA = 1.0
                self._next()
        else:                                                # visszaerkezik a tuloldalrol, lefekez
            b.seek(self.hx, self.hy, dt, 4.2)
            if not self.arrived and abs(self.hx - b.x) < 30 * u:
                self.arrived = True; b.kick("x", 9)
            if (b.settled(self.hx, self.hy) and self.phaseT > 1.0) or self.phaseT > 4.0:
                self.done = True

    def _eyes_hyper(self):
        b = self.bodies[0]
        if self.zoomA <= 0.01: return []
        sx_, sy_ = b.sxsy()
        ox = random.uniform(-1, 1) * self.shake; oy = random.uniform(-1, 1) * self.shake
        out = []
        for i, (ex, ey) in enumerate(self._eyeCenters(b.x + ox, b.y + oy, sx_ * self.zoom)):
            out.append((ex, ey, sx_ * self.zoom, sy_ * self.zoom, i == 0, b.closeAmt(), R.CYAN, self.zoomA))
        return out

    def _fx_hyper(self, layer):
        if layer == "back":
            if self.starA <= 0.01: return []
            out = []
            lag = 0.02 + self.warp * 0.035
            for s in self.stars:
                z = max(s[2], 0.02)
                x1, y1 = self._proj(s, z)
                x0, y0 = self._proj(s, z + lag)
                near = clamp(1.2 - z, 0.15, 1.0)
                out.append(("line", x0, y0, x1, y1, (1.0 + 2.2 * near) * self.u, (200, 230, 255), self.starA * near))
            return out
        if self.flashT >= 0:
            u = self.flashT / 0.6
            return [("flash", self.flashX, self.flashY, max(self.W, self.H) * 0.6 * R.ease(u), (1 - u) ** 2)]
        return []


def install(cls):
    """Az uj animaciok hozzaadasa a Rampage osztalyhoz es a KINDS listahoz."""
    for name, val in ExtraAnims.__dict__.items():
        if name.startswith("__"): continue
        if not hasattr(cls, name):
            setattr(cls, name, val)
    for k in EXTRA_KINDS:
        if k not in R.KINDS:
            R.KINDS.append(k)
