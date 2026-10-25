# -*- coding: utf-8 -*-
"""
Rajzolo fuggvenyek - az eredeti Adafruit GFX rajzolas QPainter-re atultetve.
A painter mar a 160x128-as "canvas" egysegekre van skalazva.
A fekete "kivagasok" (BG_BLACK) atlatszoak lesznek: minden szem sajat
kis kepre rajzolodik, es ott Clear modban vagjuk ki a format.
"""
import math
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (QPainter, QColor, QImage, QPen, QFont, QFontMetricsF,
                           QPolygonF, QPainterPath)

import miniface as mf

COLORS = {
    mf.NEON_BLUE: QColor(0, 255, 255),
    mf.LEMON_YELLOW: QColor(255, 255, 123),
    mf.REACT_RED: QColor(255, 40, 40),
    mf.REACT_GREEN: QColor(40, 255, 80),
}


def col(c):
    return COLORS.get(c, c) if not isinstance(c, QColor) else c


class Ctx:
    """Rajzolasi kornyezet: mini mod, latott terulet (viewport), pixel/egyseg arany."""
    def __init__(self, ps=2.0, mini=False, viewport=QRectF(0, 0, 160, 128)):
        self.ps = ps
        self.mini = mini
        self.viewport = viewport


# ================= SZEM =================
def drawEyeShaped(p, ctx, cx, cy, s, closed, isLeftEye, extraScale=1.0, color=mf.NEON_BLUE):
    c = col(color)
    if closed:
        halfW = s.w * extraScale / 2
        pen = QPen(c, 2.0); pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen); p.setBrush(Qt.NoBrush)
        p.drawLine(QPointF(cx - halfW, cy), QPointF(cx + halfW, cy))
        return
    w = s.w * extraScale; h = s.h * extraScale
    if w < 1 or h < 1:
        return
    x = cx - w / 2; y = cy - h / 2
    ps = max(0.5, ctx.ps)
    iw = int(math.ceil((w + 2) * ps)); ih = int(math.ceil((h + 2) * ps))
    if iw < 1 or ih < 1:
        return
    img = QImage(iw, ih, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    q = QPainter(img)
    q.setRenderHint(QPainter.Antialiasing)
    q.scale(ps, ps)
    q.translate(-x + 1, -y + 1)
    q.setPen(Qt.NoPen); q.setBrush(c)
    r = min(s.cornerRadius * extraScale, w / 2, h / 2)
    q.drawRoundedRect(QRectF(x, y, w, h), r, r)

    q.setCompositionMode(QPainter.CompositionMode_Clear)
    q.setBrush(Qt.black)
    outerCut = s.outerTopCut * 14 * extraScale
    innerCut = s.innerTopCut * 14 * extraScale
    if outerCut > 1:
        if isLeftEye: tri(q, x - 1, y - 1, x + outerCut, y - 1, x - 1, y + outerCut)
        else: tri(q, x + w + 1, y - 1, x + w - outerCut, y - 1, x + w + 1, y + outerCut)
    if innerCut > 1:
        if isLeftEye: tri(q, x + w + 1, y - 1, x + w - innerCut, y - 1, x + w + 1, y + innerCut)
        else: tri(q, x - 1, y - 1, x + innerCut, y - 1, x - 1, y + innerCut)
    if s.bottomCurveIn > 0.02:
        maxCarveR = w * 0.95
        carveR = maxCarveR * s.bottomCurveIn
        carveCy = y + h + carveR * 0.35
        q.drawEllipse(QPointF(cx, carveCy), carveR, carveR)
    q.end()
    p.drawImage(QRectF(x - 1, y - 1, w + 2, h + 2), img)


def drawEyeBlink(p, ctx, cx, cy, s, closeAmt, isLeftEye, extraScale=1.0, color=mf.NEON_BLUE):
    """UJ: puha pislogas - closeAmt 0 = nyitott, 1 = csukott (vonal); kozben a szem lapul."""
    if closeAmt >= 0.9:
        drawEyeShaped(p, ctx, cx, cy, s, True, isLeftEye, extraScale, color); return
    if closeAmt <= 0.01:
        drawEyeShaped(p, ctx, cx, cy, s, False, isLeftEye, extraScale, color); return
    c = closeAmt / 0.9
    c = c * c * (3 - 2 * c)
    h = max(2.0, s.h * (1 - c))
    s2 = mf.ShapeParams(s.w * (1 + 0.08 * c), h, min(s.cornerRadius, h / 2),
                        s.outerTopCut * (1 - c), s.innerTopCut * (1 - c), s.bottomCurveIn * (1 - c))
    drawEyeShaped(p, ctx, cx, cy, s2, False, isLeftEye, extraScale, color)


def tri(q, x0, y0, x1, y1, x2, y2):
    q.drawPolygon(QPolygonF([QPointF(x0, y0), QPointF(x1, y1), QPointF(x2, y2)]))


def fillTri(p, c, x0, y0, x1, y1, x2, y2):
    p.setPen(Qt.NoPen); p.setBrush(col(c)); tri(p, x0, y0, x1, y1, x2, y2)


def fillCircle(p, c, x, y, r):
    p.setPen(Qt.NoPen); p.setBrush(col(c)); p.drawEllipse(QPointF(x, y), r + 0.5, r + 0.5)


def drawCircle(p, c, x, y, r):
    p.setPen(QPen(col(c), 1.2)); p.setBrush(Qt.NoBrush); p.drawEllipse(QPointF(x, y), r, r)


def drawLine(p, c, x0, y0, x1, y1):
    pen = QPen(col(c), 1.2); pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen); p.drawLine(QPointF(x0, y0), QPointF(x1, y1))


def drawSyncEye(p, ctx, cx, cy, shape, color):
    if shape == mf.SYNC_CURIOUS: drawEyeShaped(p, ctx, cx, cy, mf.SHAPE_DEFS[mf.SHAPE_CURIOUS], False, True, 1.0, color)
    elif shape == mf.SYNC_FLAT: drawEyeShaped(p, ctx, cx, cy, mf.SHAPE_DEFS[mf.SHAPE_FOCUSED], False, True, 1.0, color)
    elif shape == mf.SYNC_CIRCLE: drawEyeShaped(p, ctx, cx, cy, mf.SHAPE_DEFS[mf.SHAPE_CIRCLE], False, True, 1.0, color)
    elif shape == mf.SYNC_DIAMOND:
        hw, hh = 15, 20
        fillTri(p, color, cx, cy - hh, cx - hw, cy, cx + hw, cy)
        fillTri(p, color, cx, cy + hh, cx - hw, cy, cx + hw, cy)
    elif shape == mf.SYNC_TRIANGLE:
        hw, hh = 15, 20
        fillTri(p, color, cx, cy - hh, cx - hw, cy + hh, cx + hw, cy + hh)


def drawArcPoints(p, cx, cy, r, startDeg, endDeg, c):
    a = startDeg
    while a <= endDeg:
        rad = math.radians(a)
        fillCircle(p, c, cx + math.cos(rad) * r, cy + math.sin(rad) * r, 0.4)
        a += 12


def drawDreamIcon(p, cx, cy, iconType, c):
    if iconType == 0:  # hopehely
        drawLine(p, c, cx - 7, cy, cx + 7, cy); drawLine(p, c, cx, cy - 7, cx, cy + 7)
        drawLine(p, c, cx - 5, cy - 5, cx + 5, cy + 5); drawLine(p, c, cx - 5, cy + 5, cx + 5, cy - 5)
    elif iconType == 1:  # hangjegy
        fillCircle(p, c, cx - 3, cy + 5, 3); drawLine(p, c, cx, cy + 5, cx, cy - 7); drawLine(p, c, cx, cy - 7, cx + 5, cy - 5)
    elif iconType == 2:  # sziv
        fillCircle(p, c, cx - 3, cy - 2, 4); fillCircle(p, c, cx + 3, cy - 2, 4)
        fillTri(p, c, cx - 7, cy, cx + 7, cy, cx, cy + 8)
    elif iconType == 3:  # ora
        drawCircle(p, c, cx, cy, 8); drawLine(p, c, cx, cy, cx, cy - 5); drawLine(p, c, cx, cy, cx + 4, cy)
    elif iconType == 4:  # mosoly
        drawCircle(p, c, cx, cy, 8); fillCircle(p, c, cx - 3, cy - 2, 1); fillCircle(p, c, cx + 3, cy - 2, 1)
        drawArcPoints(p, cx, cy, 4, 20, 160, c)
    elif iconType == 5:  # integetes
        p.setPen(Qt.NoPen); p.setBrush(col(c)); p.drawRoundedRect(QRectF(cx - 3, cy - 2, 6, 8), 2, 2)
        drawLine(p, c, cx - 3, cy - 2, cx - 5, cy - 7); drawLine(p, c, cx, cy - 2, cx, cy - 8)
        drawLine(p, c, cx + 3, cy - 2, cx + 5, cy - 7)
    elif iconType == 6:  # szeles mosoly
        drawCircle(p, c, cx, cy, 8); fillCircle(p, c, cx - 3, cy - 2, 1); fillCircle(p, c, cx + 3, cy - 2, 1)
        drawArcPoints(p, cx, cy - 1, 5, 15, 165, c)


def drawBubbleOutline(p, x, y):
    c = mf.NEON_BLUE
    fillCircle(p, c, x, y, 2); fillCircle(p, c, x + 7, y - 7, 3); fillCircle(p, c, x + 15, y - 15, 4)
    bx, by = x + 16, y - 36
    p.setPen(QPen(col(c), 1.2)); p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(bx, by, 44, 22), 10, 10)
    return bx, by


def drawThoughtBubbleDots(p, x, y, dotsVisible):
    bx, by = drawBubbleOutline(p, x, y)
    for i in range(3):
        if i < dotsVisible: fillCircle(p, mf.NEON_BLUE, bx + 12 + i * 11, by + 11, 3)


def drawThoughtBubbleIcon(p, x, y, iconType):
    bx, by = drawBubbleOutline(p, x, y)
    drawDreamIcon(p, bx + 22, by + 11, iconType, mf.NEON_BLUE)


def drawSleepZZZ(p, ctx, x, y, count):
    if count >= 1: drawText(p, ctx, x, y, 1, "Z", mf.NEON_BLUE, fit=False)
    if count >= 2: drawText(p, ctx, x + 8, y - 12, 2, "Z", mf.NEON_BLUE, fit=False)
    if count >= 3: drawText(p, ctx, x + 18, y - 28, 3, "Z", mf.NEON_BLUE, fit=False)


# ================= SZOVEG =================
_fontCache = {}


def _font(size_px):
    key = round(size_px * 4)
    f = _fontCache.get(key)
    if f is None:
        f = QFont()
        f.setFamilies(["Consolas", "Cascadia Mono", "DejaVu Sans Mono", "Courier New", "monospace"])
        f.setStyleHint(QFont.Monospace)
        f.setPixelSize(max(1, int(round(size_px * 10))))
        f.setBold(True)
        f.setHintingPreference(QFont.PreferNoHinting)
        _fontCache[key] = f
    return f


def _textWidth(size, text):
    return len(text) * 6 * size


def drawText(p, ctx, x, y, size, text, color, fit=True, center=False):
    """Adafruit szoveg: (x,y) a bal felso sarok, egy karakter 6*size x 8*size.
    Mini modban (fit=True) a latott teruletre igazitja es szukseg eseten kicsinyiti."""
    if ctx.mini and fit:
        vp = ctx.viewport
        maxW = vp.width() - 4
        if _textWidth(size, text) > maxW:
            size = max(0.45, maxW / (len(text) * 6.0))
        center = True
    w = _textWidth(size, text)
    if center:
        cxp = ctx.viewport.center().x() if ctx.mini else 80
        x = cxp - w / 2
    # a font 10 egyseg/size magas -> 10px font, kozel 6px/karakter
    p.save()
    p.translate(x, y)
    p.scale(size / 10.0, size / 10.0)
    f = _font(9.6)   # ~96 egyseg magas betu a 80 egyseges cellaban (kb. Adafruit-meret)
    p.setFont(f)
    p.setPen(col(color))
    cx = 0.0
    for ch in text:
        p.drawText(QRectF(cx - 10, -10, 80, 100), Qt.AlignCenter, ch)
        cx += 60
    p.restore()


def drawKindMessage(p, ctx, msg):
    maxChars = 12 if ctx.mini else 25
    maxLines = 4 if ctx.mini else 3
    words = msg.split(" ")
    lines = []; cur = ""
    for word in words:
        test = word if not cur else cur + " " + word
        if len(test) > maxChars and cur:
            lines.append(cur); cur = word
        else:
            cur = test
        if len(lines) >= maxLines: break
    if len(lines) < maxLines and cur: lines.append(cur)
    lh = 12
    if ctx.mini:
        cy = ctx.viewport.center().y()
    else:
        cy = 64
    y = cy - (len(lines) * lh) / 2
    for k, line in enumerate(lines):
        drawText(p, ctx, 0, y + k * lh, 1, line, mf.LEMON_YELLOW, fit=True, center=True)


# ================= TELJES JELENET =================
def renderFrame(p, ctx, f):
    mini = ctx.mini
    e1cx, e1cy, e2cx, e2cy = f.e1cx, f.e1cy, f.e2cx, f.e2cy
    e1x, e1y = f.e1x, f.e1y
    if mini and not f.clipToBox:
        # mini modban kisebb a hely: a mozgas kiterjedeset a felere vesszuk
        k = 0.45
        e1cx = 53 + (e1cx - 53) * k; e1cy = 60 + (e1cy - 60) * k
        e1x = e1cx - mf.EYE_W / 2; e1y = e1cy - mf.EYE_H / 2

    if f.clipToBox:
        p.save()
        p.setClipRect(boxRect(mini))

    if f.feedBall is not None:
        bx, by = f.feedBall
        if mini: bx = e1cx; by = 60 + (by - 60) * 0.45
        fillCircle(p, mf.LEMON_YELLOW, bx, by, 6)

    if f.sync:
        if mini:
            p.save(); p.translate(e1cx, e1cy); p.scale(0.55, 0.55)
            drawSyncEye(p, ctx, -24, 0, f.syncLeft, f.eyeColor)
            drawSyncEye(p, ctx, 24, 0, f.syncRight, f.eyeColor)
            p.restore()
        else:
            drawSyncEye(p, ctx, e1cx, e1cy, f.syncLeft, f.eyeColor)
            drawSyncEye(p, ctx, e2cx, e2cy, f.syncRight, f.eyeColor)
    else:
        if mini:
            shape = f.eye1Shape
            if f.eye2ForceCircle and not f.eye1ForceCircle: shape = f.eye2Shape
            c1 = getattr(f, "eye1CloseAmt", 1.0 if f.eye1Closed else 0.0)
            c2 = getattr(f, "eye2CloseAmt", 1.0 if f.eye2Closed else 0.0)
            drawEyeBlink(p, ctx, e1cx, e1cy, shape, max(c1, c2), True, f.eye1Scale, f.eyeColor)
        else:
            c1 = getattr(f, "eye1CloseAmt", 1.0 if f.eye1Closed else 0.0)
            c2 = getattr(f, "eye2CloseAmt", 1.0 if f.eye2Closed else 0.0)
            drawEyeBlink(p, ctx, e1cx, e1cy, f.eye1Shape, c1, True, f.eye1Scale, f.eyeColor)
            drawEyeBlink(p, ctx, e2cx, e2cy, f.eye2Shape, c2, False, f.eye2Scale, f.eyeColor)

    if f.clipToBox:
        p.restore()

    if f.particles:
        ox = e1cx if mini else (e1cx + e2cx) / 2
        for (px, py) in f.particles:
            fillCircle(p, mf.NEON_BLUE, ox + px, e1cy + py, 2)

    if f.info is not None:
        p.save(); p.setOpacity(getattr(f, "infoAlpha", 1.0))
        kind = f.info[0]
        if kind == "time":
            drawText(p, ctx, 38, 46, 2, f.info[1], mf.NEON_BLUE, center=True)
            drawText(p, ctx, 50, 74, 1, f.info[2], mf.NEON_BLUE, center=True)
        elif kind == "weather":
            drawText(p, ctx, 56, 36, 1, f.info[1], mf.NEON_BLUE, center=True)
            drawText(p, ctx, 38, 52, 2, f.info[2], mf.NEON_BLUE, center=True)
            drawText(p, ctx, 0, 78, 1, f.info[3], mf.NEON_BLUE, center=True)
        elif kind == "kind":
            drawKindMessage(p, ctx, f.info[1])
        p.restore()

    # buborekok / ZZZ: nagy modban a jobb szem mellett, mini modban kicsinyitve az egy szem mellett
    if f.thought is not None or f.dream is not None or f.zzz is not None:
        if mini:
            ax, ay, sc = e1x + mf.EYE_W - 6, e1y + 6, 0.5
        else:
            ax, ay, sc = f.e2x + mf.EYE_W, f.e2y, 1.0
        p.save(); p.translate(ax, ay); p.scale(sc, sc)
        if f.thought is not None: drawThoughtBubbleDots(p, 0, 0, f.thought)
        if f.dream is not None: drawThoughtBubbleIcon(p, 0, 0, f.dream)
        if f.zzz is not None: drawSleepZZZ(p, ctx, -6, -4, f.zzz)
        p.restore()

    if f.bottom:
        p.save(); p.setOpacity(getattr(f, "bottomAlpha", 1.0))
        if mini:
            drawText(p, ctx, 0, ctx.viewport.bottom() - 9, 1, f.bottom, mf.NEON_BLUE)
        else:
            drawText(p, ctx, 4, 116, 1, f.bottom, mf.NEON_BLUE, fit=False)
        p.restore()


# ================= TEGLALAPOK =================
# Nagy mod: a szemeket egybefogo (kattinthato) belso teglalap canvas-egysegben
BOX_BIG = QRectF(31, 31, 94, 58)
# Mini mod: a latott terulet (egy szem kozepre igazitva)
VIEW_MINI = QRectF(53 - 32, 60 - 32, 64, 64)
BOX_MINI = QRectF(53 - 22, 60 - 28, 44, 56)
VIEW_BIG = QRectF(0, 0, 160, 128)


def boxRect(mini):
    return BOX_MINI if mini else BOX_BIG


def viewRect(mini):
    return VIEW_MINI if mini else VIEW_BIG


def drawPausedOverlay(p, ctx):
    """Szunet: csukott szemek + kis || jel."""
    mini = ctx.mini
    s = mf.SHAPE_BASE
    if mini:
        drawEyeShaped(p, ctx, 53, 60, s, True, True)
    else:
        drawEyeShaped(p, ctx, 53, 60, s, True, True)
        drawEyeShaped(p, ctx, 103, 60, s, True, False)
    b = boxRect(mini)
    c = QColor(0, 255, 255, 170)
    p.setPen(Qt.NoPen); p.setBrush(c)
    x = b.right() - 9; y = b.top() + 4
    p.drawRoundedRect(QRectF(x, y, 2.2, 7), 1, 1)
    p.drawRoundedRect(QRectF(x + 4, y, 2.2, 7), 1, 1)
