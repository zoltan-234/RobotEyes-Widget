# -*- coding: utf-8 -*-
"""
RobotEyes Widget - a MiniFace robotszemek asztali (Windows) valtozata.

Inditas:  pythonw main.py   (vagy a lefordított RobotEyes-Widget.exe)
Kezeles:
  - a szemeket egybefogo (lathatatlan) teglalapra kattintva -> menu
  - a teglalapot megfogva -> athelyezes (barmelyik monitorra)
  - talcaikon: bal katt = elrejt/megjelenit, jobb katt = menu
"""
import os
import sys
import json
import math
import time
import random

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF, QPoint, QLockFile, QDir
from PySide6.QtGui import (QPainter, QColor, QPen, QCursor, QIcon, QPixmap, QAction, QRadialGradient, QPolygonF,
                           QActionGroup, QGuiApplication)
from PySide6.QtWidgets import QApplication, QWidget, QMenu, QSystemTrayIcon

import miniface as mf
import render as rd
import rampage as rp
import winutil
import smooth

APP_NAME = "RobotEyes-Widget"
APP_TITLE = "RobotEyes Widget"
OLD_APP_NAME = "RobotSzem"       # korabbi nev - a regi beallitasok atvetelehez
IDLE_RAMPAGE_SEC = 300          # 5 perc tetlenseg utan randalirozhat
RAMPAGE_REPEAT = 20.0           # utana fix ennyi masodpercenkent ujra (amig nem nyulsz a gephez)
SIZES = {"Pici": 0.85, "Kicsi": 1.3, "Közepes": 1.8, "Nagy": 2.5}
MINI_SCALE = 1.15


# ================= VIRTUALIS ORA (szunetnel megall) =================
class VClock:
    def __init__(self):
        self.start = time.monotonic()
        self.pausedTotal = 0.0
        self.pausedAt = None

    def ms(self):
        now = self.pausedAt if self.pausedAt is not None else time.monotonic()
        return int((now - self.start - self.pausedTotal) * 1000) + 1

    def pause(self):
        if self.pausedAt is None: self.pausedAt = time.monotonic()

    def resume(self):
        if self.pausedAt is not None:
            self.pausedTotal += time.monotonic() - self.pausedAt
            self.pausedAt = None


# ================= BEALLITASOK =================
def pidPath():
    return os.path.join(os.path.dirname(configPath()), "roboteyes.pid")


def writePidFile():
    """UJ: a futo peldany azonositoja - az eltavolito (uninstall.bat) ez alapjan allitja le."""
    try:
        with open(pidPath(), "w") as fh:
            fh.write(str(os.getpid()))
    except Exception:
        pass


def removePidFile():
    try:
        os.remove(pidPath())
    except Exception:
        pass


def configPath():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, APP_NAME)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "config.json")


def migrateOldConfig():
    """UJ: ha a program meg RobotSzem neven futott, a regi beallitasokat (hely, meret, mod) atveszi."""
    try:
        new = configPath()
        if os.path.exists(new):
            return
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        old = os.path.join(base, OLD_APP_NAME, "config.json")
        if os.path.exists(old):
            import shutil
            shutil.copyfile(old, new)
    except Exception:
        pass


def loadConfig():
    migrateOldConfig()
    try:
        with open(configPath(), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def saveConfig(cfg):
    try:
        with open(configPath(), "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2)
    except Exception:
        pass


# ================= IKON =================
def makeIcon():
    pm = QPixmap(64, 64); pm.fill(Qt.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen); p.setBrush(QColor(12, 18, 24)); p.drawRoundedRect(QRectF(2, 2, 60, 60), 14, 14)
    p.setBrush(QColor(0, 255, 255))
    p.drawRoundedRect(QRectF(13, 17, 15, 30), 6, 6)
    p.drawRoundedRect(QRectF(36, 17, 15, 30), 6, 6)
    p.end()
    return QIcon(pm)


# ================= FO ABLAK =================
class EyeWindow(QWidget):
    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool |
                         Qt.WindowDoesNotAcceptFocus | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.setWindowTitle(APP_TITLE)

        self.cfg = loadConfig()
        self.mini = bool(self.cfg.get("mini", False))
        self.sizeName = self.cfg.get("size", "Közepes")
        if self.sizeName not in SIZES: self.sizeName = "Közepes"

        self.clock = VClock()
        self.face = mf.MiniFace(self.clock.ms, cursor_rel=self.cursorRel, peek_dir=self.peekDir)
        self.face.setup()
        self.frame = self.face.loop()
        self.smoother = smooth.Smoother()                 # UJ: 60 fps-es simitas
        self.smoother.push(self.frame, time.monotonic())
        self.hoverA = 0.0

        self.paused = False
        self.userHidden = False
        self.fsHidden = False
        self.hover = False
        self.menuOpen = False
        self.press = None          # (gomb, globalis pont, offset)
        self.dragging = False

        self.rampage = None
        self._forcedRampage = False
        self.normalGeom = None
        self.lastTick = time.monotonic()
        self.nextLogic = 0.0
        self.lastFsCheck = 0.0
        self.nextRampageAt = 0.0

        self.applySize(keepCenter=False)
        self.restorePosition()

        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)

    # ---------------- meretek / koordinatak ----------------
    @property
    def S(self):
        return MINI_SCALE if self.mini else SIZES[self.sizeName]

    def view(self):
        return rd.viewRect(self.mini)

    def canvasToWidget(self, x, y):
        v = self.view()
        return QPointF((x - v.x()) * self.S, (y - v.y()) * self.S)

    def widgetToCanvas(self, pt):
        v = self.view()
        return QPointF(pt.x() / self.S + v.x(), pt.y() / self.S + v.y())

    def boxGlobal(self):
        b = rd.boxRect(self.mini)
        tl = self.canvasToWidget(b.left(), b.top()); br = self.canvasToWidget(b.right(), b.bottom())
        g = self.mapToGlobal(QPoint(0, 0))
        return QRectF(tl.x() + g.x(), tl.y() + g.y(), br.x() - tl.x(), br.y() - tl.y())

    def pairCenterGlobal(self):
        cx = 53 if self.mini else 78
        pt = self.canvasToWidget(cx, 60)
        g = self.mapToGlobal(QPoint(0, 0))
        return QPointF(pt.x() + g.x(), pt.y() + g.y())

    def applySize(self, keepCenter=True):
        oldCenter = self.boxGlobal().center() if keepCenter else None
        v = self.view()
        w = int(round(v.width() * self.S)); h = int(round(v.height() * self.S))
        self.setFixedSize(w, h)
        if oldCenter is not None:
            b = rd.boxRect(self.mini)
            c = self.canvasToWidget(b.center().x(), b.center().y())
            self.move(int(oldCenter.x() - c.x()), int(oldCenter.y() - c.y()))
        self.update()

    def restorePosition(self):
        pos = self.cfg.get("pos")
        if pos and QGuiApplication.screenAt(QPoint(pos[0] + self.width() // 2, pos[1] + self.height() // 2)):
            self.move(pos[0], pos[1])
        else:
            ag = QGuiApplication.primaryScreen().availableGeometry()
            self.move(ag.right() - self.width() - 20, ag.top() + 20)

    def saveState(self):
        if self.rampage is None:
            self.cfg["pos"] = [self.x(), self.y()]
        self.cfg["mini"] = self.mini
        self.cfg["size"] = self.sizeName
        saveConfig(self.cfg)

    # ---------------- callbackek a MiniFace-nek ----------------
    def cursorRel(self):
        c = QCursor.pos(); pc = self.pairCenterGlobal()
        return ((c.x() - pc.x()) / self.S, (c.y() - pc.y()) / self.S)

    def peekDir(self):
        """A teglalaphoz legkozelebbi kepernyoszel iranya (arra bujik el). Ha mind messze van: lefele."""
        scr = self.screen()
        if scr is None: return (0.0, 1.0)
        ag = scr.availableGeometry(); b = self.boxGlobal()
        d = {(-1.0, 0.0): b.left() - ag.left(), (1.0, 0.0): ag.right() - b.right(),
             (0.0, -1.0): b.top() - ag.top(), (0.0, 1.0): ag.bottom() - b.bottom()}
        best = min(d, key=d.get)
        return best if d[best] < 250 else (0.0, 1.0)

    # ---------------- fo ciklus ----------------
    def tick(self):
        now = time.monotonic()
        dt = now - self.lastTick; self.lastTick = now
        hwnd = int(self.winId())

        if now - self.lastFsCheck > 1.0:
            self.lastFsCheck = now
            self.checkFullscreenApp(hwnd)

        if winutil.IS_WIN:
            idle = winutil.idle_seconds()
        else:
            c = QCursor.pos(); idle = winutil.idle_seconds((c.x(), c.y()))

        if self.rampage is not None:
            self.tickRampage(dt, idle)
            return

        if not self.isVisible():
            return

        if not self.paused:
            self.maybeStartRampage(now, idle)
            if self.rampage is not None:
                return
            # UJ: a logika fix utemben lep, a rajzolas minden kepkockaban (simitva)
            if now >= self.nextLogic:
                self.frame = self.face.loop()
                self.smoother.push(self.frame, now)
                self.nextLogic = max(self.nextLogic + smooth.LOGIC_DT, now - smooth.LOGIC_DT)
            self.update()

        self.updateHover(hwnd)
        self.updateHoverFade(dt)

    def updateHover(self, hwnd):
        inside = self.boxGlobal().contains(QPointF(QCursor.pos()))
        active = inside or self.dragging or self.press is not None
        winutil.set_click_through(hwnd, not active)
        if inside != self.hover:
            self.hover = inside
            self.update()

    def updateHoverFade(self, dt):
        """UJ: a keret puhan jelenik meg / tunik el."""
        target = 1.0 if (self.hover or self.dragging) else 0.0
        if self.hoverA != target:
            self.hoverA = smooth._approach(self.hoverA, target, 1 / 0.15, dt)
            self.update()

    # ---------------- teljes kepernyos app -> eltunik ----------------
    def checkFullscreenApp(self, hwnd):
        fs = winutil.fullscreen_on_my_monitor(hwnd)
        if fs and not self.fsHidden:
            self.fsHidden = True
            if self.rampage is not None: self.endRampage()
            self.hide()
        elif not fs and self.fsHidden:
            self.fsHidden = False
            if not self.userHidden:
                self.showNoActivate()

    def showNoActivate(self):
        self.show()
        winutil.reset_click_through_cache(int(self.winId()))

    # ---------------- randalirozas ----------------
    def maybeStartRampage(self, now, idle):
        if idle < IDLE_RAMPAGE_SEC:
            self.nextRampageAt = 0.0
            return
        if now < self.nextRampageAt or not self.face.isIdleForRampage():
            return
        self.startRampage(self.nextRampageKind())

    def nextRampageKind(self):
        """UJ: veletlen sorrend, de ismetles nelkul - amig mind le nem ment, egyik sem jon ujra."""
        bag = getattr(self, "_rampageBag", None)
        if not bag:
            bag = list(rp.KINDS)
            random.shuffle(bag)
            last = getattr(self, "_lastRampage", None)
            if len(bag) > 1 and bag[-1] == last:          # ne legyen ket egyforma egymas utan
                bag[0], bag[-1] = bag[-1], bag[0]
            self._rampageBag = bag
        kind = bag.pop()
        self._lastRampage = kind
        return kind

    def startRampage(self, kind):
        if self.rampage is not None or self.paused or not self.isVisible():
            return
        scr = self.screen() or QGuiApplication.primaryScreen()
        geom = scr.geometry()
        home = self.pairCenterGlobal()
        self.normalGeom = self.geometry()
        self.rampage = rp.Rampage(kind, geom.width(), geom.height(),
                                  (home.x() - geom.x(), home.y() - geom.y()), self.S, self.mini)
        # UJ: a magnes-animacio az egerkurzort koveti (kijelzohoz relativ koordinata)
        self.rampage.cursorFn = lambda g=geom: (QCursor.pos().x() - g.x(), QCursor.pos().y() - g.y())
        self.setMinimumSize(0, 0); self.setMaximumSize(16777215, 16777215)
        self.setGeometry(geom)
        winutil.set_click_through(int(self.winId()), True)
        self.lastTick = time.monotonic()
        self.update()

    def tickRampage(self, dt, idle):
        # termeszetes (5 perc utani) randalirozas: barmilyen eger/billentyu -> azonnal vissza
        # menubol inditott: csak kattintasra all le (hogy nyugodtan nezheted)
        if self._forcedRampage:
            if self.rampage.t > 0.5 and winutil.mouse_button_down():
                self.endRampage(); return
        elif idle < 0.4:
            self.endRampage(); return
        self.rampage.update(dt)
        if self.rampage.done:
            self.endRampage()
            self.nextRampageAt = time.monotonic() + RAMPAGE_REPEAT
        self.update()

    def endRampage(self):
        self.rampage = None
        self._forcedRampage = False
        if self.normalGeom is not None:
            self.setGeometry(self.normalGeom)
        self.applySize(keepCenter=False)
        if self.normalGeom is not None:
            self.move(self.normalGeom.topLeft())
        f = self.face
        f.lastMoveTime = f.millis(); f.isMoving = False
        self.nextLogic = 0.0
        self.smoother.reset()
        self.update()

    # ---------------- rajzolas ----------------
    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        dpr = self.devicePixelRatioF()

        if self.rampage is not None:
            self.paintRampage(p, dpr)
            p.end(); return

        S = self.S
        p.scale(S, S)
        v = self.view()
        p.translate(-v.x(), -v.y())
        ctx = rd.Ctx(ps=S * dpr, mini=self.mini, viewport=v)

        # a kattinthato belso teglalap: szinte lathatatlan kitoltes, hoverre halvany keret
        b = rd.boxRect(self.mini)
        p.setPen(Qt.NoPen); p.setBrush(QColor(0, 0, 0, 3))
        p.drawRoundedRect(b, 8, 8)
        if self.hoverA > 0.01:
            a = self.hoverA
            p.setBrush(QColor(0, 40, 50, int(40 * a)))
            p.setPen(QPen(QColor(0, 255, 255, int(90 * a)), 1.0 / S * 1.5))
            p.drawRoundedRect(b, 8, 8)

        if self.paused:
            rd.drawPausedOverlay(p, ctx)
        else:
            f = self.smoother.get(time.monotonic()) or self.frame
            rd.renderFrame(p, ctx, f)
        p.end()

    def paintRampage(self, p, dpr):
        S = self.S
        self.paintRampageFx(p, "back")
        for it in self.rampage.eyes():
            cx, cy, sx, sy, isLeft, closeAmt, color, alpha = it[:8]
            if alpha <= 0.01 or sx <= 0.005 or sy <= 0.005:
                continue
            shape = it[8] if len(it) > 8 and it[8] is not None else mf.SHAPE_BASE
            rot = it[9] if len(it) > 9 else 0.0
            p.save()
            p.setOpacity(min(1.0, alpha))
            p.translate(cx, cy)
            if rot: p.rotate(rot)
            p.scale(S * sx, S * sy)
            if shape is mf.SHAPE_BASE and closeAmt < 0.01:
                # gyors ut: sima szem = lekerekitett teglalap (sok szemnel is gyors)
                p.setPen(Qt.NoPen); p.setBrush(QColor(*color))
                p.drawRoundedRect(QRectF(-13, -20, 26, 40), 10, 10)
            else:
                ctx = rd.Ctx(ps=S * max(sx, sy) * dpr, mini=False)
                rd.drawEyeBlink(p, ctx, 0, 0, shape, closeAmt, isLeft, 1.0, QColor(*color))
            p.restore()
        self.paintRampageFx(p, "front")

    def paintRampageFx(self, p, layer):
        """UJ: extra rajzelemek (palyak, reszecskek, villanas, fekete lyuk, utok, csillagcsikok)."""
        for item in self.rampage.extras(layer):
            kind = item[0]
            if kind == "px":
                _, x, y, size, rot, color, a = item
                c = QColor(color[0], color[1], color[2], int(255 * max(0.0, min(1.0, a))))
                if abs(rot) < 1e-3:
                    p.fillRect(QRectF(x - size / 2, y - size / 2, size, size), c)
                else:
                    p.save(); p.translate(x, y); p.rotate(math.degrees(rot))
                    p.fillRect(QRectF(-size / 2, -size / 2, size, size), c)
                    p.restore()
            elif kind == "line":
                _, x0, y0, x1, y1, w, color, a = item
                pen = QPen(QColor(color[0], color[1], color[2], int(255 * max(0.0, min(1.0, a)))), w)
                pen.setCapStyle(Qt.RoundCap)
                p.setPen(pen); p.drawLine(QPointF(x0, y0), QPointF(x1, y1))
            elif kind == "rrect":
                _, x, y, w, h, r, color, a = item
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(color[0], color[1], color[2], int(255 * max(0.0, min(1.0, a)))))
                p.drawRoundedRect(QRectF(x, y, w, h), r, r)
            elif kind == "glow":
                _, x, y, rx, ry, color, a = item
                if rx < 1 or ry < 1: continue
                p.save(); p.translate(x, y); p.scale(1.0, ry / rx)
                g = QRadialGradient(QPointF(0, 0), rx)
                g.setColorAt(0.0, QColor(color[0], color[1], color[2], int(200 * a)))
                g.setColorAt(1.0, QColor(color[0], color[1], color[2], 0))
                p.setPen(Qt.NoPen); p.setBrush(g); p.drawEllipse(QPointF(0, 0), rx, rx)
                p.restore()
            elif kind == "poly":
                _, pts, color, a = item
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(color[0], color[1], color[2], int(255 * max(0.0, min(1.0, a)))))
                p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))
            elif kind == "pline":
                _, pts, w, color, a = item
                pen = QPen(QColor(color[0], color[1], color[2], int(255 * max(0.0, min(1.0, a)))), w)
                pen.setCapStyle(Qt.RoundCap); pen.setJoinStyle(Qt.RoundJoin)
                p.setPen(pen); p.setBrush(Qt.NoBrush)
                p.drawPolyline(QPolygonF([QPointF(x, y) for x, y in pts]))
            elif kind == "blackhole":
                _, x, y, r, spin, a = item
                self.paintBlackHole(p, x, y, r, spin, a)
            elif kind == "orbit":
                _, pts, a = item
                pen = QPen(QColor(0, 255, 255, int(255 * a)), 1.6 * self.S / 1.8)
                p.setPen(pen); p.setBrush(Qt.NoBrush)
                p.drawPolyline(QPolygonF([QPointF(x, y) for x, y in pts]))
            elif kind == "flash":
                _, x, y, r, a = item
                if r < 1 or a <= 0.01: continue
                g = QRadialGradient(QPointF(x, y), r)
                g.setColorAt(0.0, QColor(255, 255, 255, int(200 * a)))
                g.setColorAt(0.35, QColor(120, 255, 255, int(110 * a)))
                g.setColorAt(1.0, QColor(0, 255, 255, 0))
                p.setPen(Qt.NoPen); p.setBrush(g)
                p.drawEllipse(QPointF(x, y), r, r)

    def paintBlackHole(self, p, x, y, r, spin, a):
        """UJ: fekete lyuk - izzo, forgo akkrecios gyuru + fekete korong."""
        p.save()
        p.setOpacity(max(0.0, min(1.0, a)))
        g = QRadialGradient(QPointF(x, y), r * 3.4)
        g.setColorAt(0.0, QColor(0, 0, 0, 255))
        g.setColorAt(0.28, QColor(0, 0, 0, 255))
        g.setColorAt(0.33, QColor(150, 255, 255, 230))
        g.setColorAt(0.45, QColor(0, 200, 255, 150))
        g.setColorAt(0.7, QColor(120, 60, 255, 60))
        g.setColorAt(1.0, QColor(60, 0, 120, 0))
        p.setPen(Qt.NoPen); p.setBrush(g)
        p.drawEllipse(QPointF(x, y), r * 3.4, r * 3.4)
        # forgo ivek
        for i in range(6):
            rr = r * (1.25 + 0.28 * (i % 3))
            pen = QPen(QColor(180, 255, 255, 170 - 22 * i), max(1.0, r * 0.07))
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen); p.setBrush(Qt.NoBrush)
            start = int((math.degrees(spin) * (1 + 0.3 * (i % 2)) + i * 60) * 16)
            p.drawArc(QRectF(x - rr, y - rr, 2 * rr, 2 * rr), start, 70 * 16)
        p.setPen(Qt.NoPen); p.setBrush(QColor(0, 0, 0))
        p.drawEllipse(QPointF(x, y), r, r)
        p.restore()

    # ---------------- eger ----------------
    def inBox(self, wpt):
        return rd.boxRect(self.mini).contains(self.widgetToCanvas(wpt))

    def mousePressEvent(self, e):
        if self.rampage is not None:
            self.endRampage(); return
        if not self.inBox(e.position()):
            e.ignore(); return
        gp = e.globalPosition().toPoint()
        self.press = (e.button(), gp, gp - self.pos())
        self.dragging = False

    def mouseMoveEvent(self, e):
        if self.press is None: return
        btn, gp0, off = self.press
        gp = e.globalPosition().toPoint()
        if btn == Qt.LeftButton and (self.dragging or (gp - gp0).manhattanLength() > 5):
            self.dragging = True
            self.move(gp - off)

    def mouseReleaseEvent(self, e):
        if self.press is None: return
        btn = self.press[0]
        wasDrag = self.dragging
        self.press = None; self.dragging = False
        if wasDrag:
            self.saveState(); self.update()
            return
        self.handleClick(btn)

    def handleClick(self, btn):
        f = self.face
        # kattintasra azonnal vissza a sima allapotba
        if not self.paused and f.endExtras():
            self.update(); return
        if not self.paused and btn == Qt.LeftButton and (f.reactionActive or f.syncActive):
            f.onPetShort(); return
        self.showMenu()

    # ---------------- menu ----------------
    def buildMenu(self, forTray=False, m=None):
        f = self.face
        if m is None:
            m = QMenu()
        else:
            m.clear()
        if not forTray:
            if f.gameWaitingChoice and not self.paused:
                m.addAction("Fej", f.onPetShort)
                m.addAction("Írás", f.onGameShort)
                m.addSeparator()

            awake = f.isEffectivelyAwake() and f.miniState != mf.MF_SLEEP
            a = m.addAction("Simogatás", f.onPetShort)
            a.setEnabled(not self.paused and awake and f.hungerState == mf.HUNGER_IDLE and not f.gameActive)
            if f.hungerState == mf.HUNGER_CIRCLE:
                m.addAction("Etetés (éhes!)", f.onPetLong).setEnabled(not self.paused)
            if f.miniState == mf.MF_SLEEP:
                m.addAction("Ébresztés", f.onPetLong).setEnabled(not self.paused)

            g = m.addMenu("Játék")
            for i, name in enumerate(("Fej vagy írás", "Reakcióteszt", "Szem-szinkron")):
                act = g.addAction(name, lambda t=i: self.startGame(t))
                act.setEnabled(not self.paused)
            g.setEnabled(not self.paused and not f.gameActive)

            s = m.addMenu("Mutasd")
            for i, name in enumerate(("Időt", "Kedves szót", "Időjárást")):
                s.addAction(name, lambda k=i: self.showInfo(k))
            s.setEnabled(not self.paused)

            r = m.addMenu("Randalírozz most")
            for k, name in zip(rp.KINDS, ("Pattogás", "Sokszorozódás", "Cikázás", "Gyorsuló zuhanás",
                                            "DVD-logó pattogás", "Atom + robbanás",
                                            "Fekete lyuk", "Kígyó", "Mátrix-eső", "Kaleidoszkóp",
                                            "Pingpong", "Olvadás", "Szikra-szél", "Hiperugrás",
                                            "Homokóra", "Porrá válás", "Üvegtörés", "Gravitáció-fordítás",
                                            "Vízcsepp", "Mágnes (egérkurzor)")):
                r.addAction(name, lambda kk=k: self.forceRampage(kk))
            r.setEnabled(not self.paused)
            m.addSeparator()

        m.addAction("Folytatás" if self.paused else "Szünet", self.togglePause)
        a = m.addAction("Mini mód (egy szem)"); a.setCheckable(True); a.setChecked(self.mini)
        a.toggled.connect(self.setMini)
        sz = m.addMenu("Méret")
        grp = QActionGroup(sz)
        for name in SIZES:
            act = sz.addAction(name); act.setCheckable(True); act.setChecked(name == self.sizeName)
            grp.addAction(act)
            act.triggered.connect(lambda _=False, n=name: self.setSizeName(n))
        sz.setEnabled(not self.mini)
        m.addSeparator()
        if forTray:
            m.addAction("Elrejtés" if self.isVisible() else "Megjelenítés", self.toggleVisible)
        else:
            m.addAction("Elrejtés (tálcára)", self.toggleVisible)
        m.addAction("Kilépés", QApplication.instance().quit)
        return m

    def showMenu(self):
        self.menuOpen = True
        m = self.buildMenu()
        m.exec(QCursor.pos())
        self.menuOpen = False

    def startGame(self, gameType):
        f = self.face
        f.startGameSelect()
        if f.gameSelectMode:
            f.selectedGameType = gameType
            f.confirmGameSelect()

    def showInfo(self, idx):
        f = self.face
        f.menuIndex = (idx - 1) % 3
        f.onGameLong()

    def forceRampage(self, kind):
        self.startRampage(kind)
        self._forcedRampage = self.rampage is not None

    def togglePause(self):
        self.paused = not self.paused
        if self.paused: self.clock.pause()
        else: self.clock.resume()
        self.update()

    def setMini(self, on):
        if self.rampage is not None: self.endRampage()
        self.mini = bool(on)
        self.applySize(keepCenter=True)
        self.saveState()

    def setSizeName(self, name):
        self.sizeName = name
        if not self.mini:
            self.applySize(keepCenter=True)
        self.saveState()

    def toggleVisible(self):
        if self.isVisible():
            if self.rampage is not None: self.endRampage()
            self.userHidden = True
            self.hide()
        else:
            self.userHidden = False
            if not self.fsHidden:
                self.showNoActivate()


def main():
    winutil.enable_dpi_awareness()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName(APP_NAME)

    lock = QLockFile(os.path.join(QDir.tempPath(), APP_NAME + ".lock"))
    if not lock.tryLock(100):
        return 0   # mar fut egy peldany
    writePidFile()

    w = EyeWindow()
    icon = makeIcon()
    app.setWindowIcon(icon)

    tray = QSystemTrayIcon(icon)
    tray.setToolTip(APP_TITLE)

    def onTray(reason):
        if reason == QSystemTrayIcon.Trigger:
            w.toggleVisible()

    tray.activated.connect(onTray)
    trayMenu = QMenu()
    w.buildMenu(forTray=True, m=trayMenu)
    # a menu minden megnyitas elott ujraepul (Szunet/Folytatas, Elrejtes/Megjelenites felirat)
    trayMenu.aboutToShow.connect(lambda: w.buildMenu(forTray=True, m=trayMenu))
    tray.setContextMenu(trayMenu)
    tray.show()

    w.showNoActivate()
    app.aboutToQuit.connect(w.saveState)
    rc = app.exec()
    removePidFile()
    lock.unlock()
    return rc


if __name__ == "__main__":
    sys.exit(main())
