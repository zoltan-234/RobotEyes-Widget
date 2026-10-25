# -*- coding: utf-8 -*-
"""
MiniFace - az ESP32-es MiniFaceApp.h logikajanak Python portja.

A viselkedes (allapotgep, sulyozott esemenyek, ehseg, napi ritmus, jatekok)
1:1-ben az eredeti. Ami valtozott:
  - millis()  -> virtualis ora (szunetnel megall)
  - a gombok helyett menu/kattintas hivja az onPetShort/onPetLong/... fuggvenyeket
  - a loop() nem rajzol, hanem egy Frame-et ad vissza, amit a render.py rajzol ki
  - helyszin: Szeged (LAT/LON/CITY_NAME, atallithato)
UJ (kulon fuggvenyekben, lent az "UJ" szekcioban):
  - MF_FOLLOW: a szemek egy ideig kovetik az egerkurzort
  - MF_PEEK:   a szemek elbujnak a teglalap szelen, majd kikukucskalnak
"""
import math
import random as _random
import datetime
import threading
import json
import urllib.request

# ---------------- SEGED: Arduino random() ----------------
def random(a, b=None):
    if b is None:
        a, b = 0, a
    return _random.randrange(int(a), int(b))

def radians(d):
    return d * math.pi / 180.0

# ---------------- SZINEK ----------------
NEON_BLUE = "blue"
LEMON_YELLOW = "yellow"
REACT_RED = "red"
REACT_GREEN = "green"

# ---------------- NAPI RITMUS ----------------
DAY_SLEEP, DAY_WAKING, DAY_ACTIVE, DAY_WINDDOWN = range(4)

# ---------------- MINIFACE ALLAPOTOK ----------------
(MF_NONE, MF_THINKING, MF_JOY, MF_WINK, MF_DREAM,
 MF_SLEEP, MF_WAKE,
 MF_CHARGE_HAPPY, MF_FEED_HAPPY,
 MF_CIRCLE_SEQ, MF_EXPLODE, MF_DART, MF_SINK_REPEAT,
 MF_GAME_WIN, MF_GAME_LOSE,
 MF_INFO_TIME, MF_INFO_WEATHER,
 MF_INFO_KIND,
 MF_FOLLOW,      # UJ: kurzorkovetes
 MF_PEEK         # UJ: elbujas / kikukucskalas
 ) = range(20)

# ---------------- ESEMENYEK ----------------
(EVT_NONE, EVT_SHAPE_CURIOUS, EVT_SHAPE_CUTE, EVT_WINK, EVT_THINKING, EVT_JOY,
 EVT_DREAM, EVT_CIRCLE_SEQ, EVT_DART, EVT_SINK_REPEAT, EVT_EXPLODE,
 EVT_INFO_TIME, EVT_INFO_WEATHER, EVT_INFO_KIND,
 EVT_FOLLOW,     # UJ
 EVT_PEEK,       # UJ
 EVT_COUNT) = range(17)

HUNGER_IDLE, HUNGER_CIRCLE, HUNGER_SAD = range(3)

(SHAPE_NORMAL, SHAPE_WORRIED, SHAPE_ANGRY, SHAPE_CURIOUS, SHAPE_CUTE,
 SHAPE_FOCUSED, SHAPE_CIRCLE) = range(7)

SYNC_CURIOUS, SYNC_FLAT, SYNC_CIRCLE, SYNC_DIAMOND, SYNC_TRIANGLE, SYNC_SHAPE_COUNT = range(6)

GAME_COINFLIP, GAME_REACTION, GAME_SYNC, GAME_COUNT = range(4)
REACT_WAITING, REACT_ARMED = range(2)


class ShapeParams:
    __slots__ = ("w", "h", "cornerRadius", "outerTopCut", "innerTopCut", "bottomCurveIn")

    def __init__(self, w, h, cornerRadius, outerTopCut, innerTopCut, bottomCurveIn):
        self.w = w; self.h = h; self.cornerRadius = cornerRadius
        self.outerTopCut = outerTopCut; self.innerTopCut = innerTopCut
        self.bottomCurveIn = bottomCurveIn


def lerpShape(a, b, t):
    return ShapeParams(
        a.w + (b.w - a.w) * t,
        a.h + (b.h - a.h) * t,
        a.cornerRadius + (b.cornerRadius - a.cornerRadius) * t,
        a.outerTopCut + (b.outerTopCut - a.outerTopCut) * t,
        a.innerTopCut + (b.innerTopCut - a.innerTopCut) * t,
        a.bottomCurveIn + (b.bottomCurveIn - a.bottomCurveIn) * t,
    )


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "active")

    def __init__(self):
        self.x = self.y = self.vx = self.vy = 0.0
        self.active = False


# ---------------- KONFIG ----------------
# Szeged koordinatak (Open-Meteo-hoz)
LAT = 46.25
LON = 20.15
CITY_NAME = "Szeged"

EYE1_BASE_X, EYE2_BASE_X, EYE_BASE_Y = 40, 90, 40
EYE_W, EYE_H = 26, 40

hungarianMonths = ["Január", "Február", "Március", "Április", "Május", "Június",
                   "Július", "Augusztus", "Szeptember", "Október", "November", "December"]

SHAPE_BASE = ShapeParams(26, 40, 10, 0, 0, 0)
SHAPE_DEFS = [
    ShapeParams(26, 40, 10, 0, 0, 0),   # NORMAL
    ShapeParams(26, 40, 10, 1, 0, 0),   # WORRIED
    ShapeParams(26, 40, 10, 0, 1, 0),   # ANGRY
    ShapeParams(20, 46, 9, 0, 0, 0),    # CURIOUS
    ShapeParams(26, 34, 13, 0, 0, 1),   # CUTE
    ShapeParams(32, 20, 8, 0, 0, 0),    # FOCUSED (lapos)
    ShapeParams(30, 30, 15, 0, 0, 0),   # CIRCLE (ehseg)
]
SHAPE_BLEND_SPEEDS = [0.015, 0.015, 0.015, 0.05, 0.05, 0.015, 0.015]
SHAPE_HOLD_DURATIONS = [3000, 3000, 3000, 300000, 25000, 3000, 3000]

kindWords = [
    "Jó látni téged!",
    "Szép napod legyen!",
    "Örülök, hogy itt vagy!",
    "Te vagy a kedvenc emberem!",
    "Ma is ragyogsz!",
    "Büszke vagyok rád!",
    "Csak semmi stressz, minden rendben lesz!",
    "Egy mosoly mindig segít!",
    "Köszönöm, hogy velem vagy!",
    "Klassz napod legyen!",
    "Te tudod a legjobban csinálni!",
    "Sose add fel!",
    "Ma is jól csinálod!",
    "Egy jó szó sokat számít!",
    "Érted vagyok!",
]
KIND_WORDS_COUNT = len(kindWords)


def weatherCodeToHungarian(code):
    if code < 0: return "még nem tudom"
    if code == 0: return "tiszta ég"
    if code in (1, 2): return "részben napos"
    if code == 3: return "borult"
    if 45 <= code <= 48: return "ködös"
    if 51 <= code <= 67: return "esős"
    if 71 <= code <= 77: return "havas"
    if 80 <= code <= 82: return "záporos"
    if 85 <= code <= 86: return "havazásos"
    if code >= 95: return "viharos"
    return "változékony"


def randomHungerWait():
    opts = [30, 60, 120, 180]  # perc
    return opts[random(0, 4)] * 60000


class Frame:
    """Egy kirajzolando kep leirasa (a canvas-ra rajzolas helyett)."""
    pass


class MiniFace:
    # ---- idozitok / konstansok ----
    CLOCK_CHECK_INTERVAL = 10000
    WEATHER_INTERVAL = 3600000
    EVENT_CHECK_MIN = 15000
    EVENT_CHECK_MAX = 35000
    LOOKAWAY_TARGET_X, LOOKAWAY_TARGET_Y = -22, 18
    THINK_DOT_INTERVAL, THINK_MAX_LOOPS = 350, 3
    JOY_RADIUS, JOY_THETA_STEP, JOY_MAX_DOWN = 14, 18, 26
    WINK_DURATION = 200
    DREAM_DURATION = 1800
    SLEEP_Z_INTERVAL = 500
    WAKE_SHAKE_DURATION, WAKE_AMPLITUDE, WAKE_FREQ = 600, 5, 0.025
    MANUAL_WAKE_DURATION = 300000
    CHARGE_BOUNCE_TARGET = 2
    FEED_BALL_SPEED = 5.0
    FEED_FLASH_INTERVAL = 150
    FEED_FLASH_TOGGLES = 6
    CIRCLE_SEQ_HOLD, CIRCLE_SEQ_SPEED = 700, 0.06
    EXPLODE_MAX_SCALE = 1.9
    DART_DURATION = 5000
    SINK_MAX_CYCLES = 9
    GAME_LOSE_DURATION = 6000
    GAME_WIN_HOLD_DURATION = 6000
    HUNGER_WINDOW = 60000
    HUNGER_SAD_DURATION = 2000
    GAME_CHOICE_TIMEOUT = 15000
    GAME_SELECT_TIMEOUT = 10000
    REACT_ARMED_TIMEOUT = 3000
    SYNC_MIN_INTERVAL, SYNC_MAX_INTERVAL = 600, 1400
    SYNC_GAME_TIMEOUT = 20000
    SYNC_SIMULTANEOUS_WINDOW = 200
    LONG_PRESS_MS = 800
    INFO_HOLD_DURATION = 4000
    INFO_FADE_SPEED = 0.08

    def __init__(self, millis, cursor_rel=None, peek_dir=None):
        self.millis = millis
        # UJ: kulso callbackek (ablak adja) - kurzor helye canvas-egysegben, kukucskalas iranya
        self.cursor_rel = cursor_rel or (lambda: (0.0, 0.0))
        self.peek_dir = peek_dir or (lambda: (0.0, 1.0))

        # sulyok - magasabb szam = gyakoribb esemeny
        self.eventWeights = [
            22,  # EVT_NONE
            10,  # EVT_SHAPE_CURIOUS
            10,  # EVT_SHAPE_CUTE
            30,  # EVT_WINK
            18,  # EVT_THINKING
            15,  # EVT_JOY
            15,  # EVT_DREAM
            15,  # EVT_CIRCLE_SEQ
            15,  # EVT_DART
            15,  # EVT_SINK_REPEAT
            15,  # EVT_EXPLODE
            22,  # EVT_INFO_TIME
            22,  # EVT_INFO_WEATHER
            22,  # EVT_INFO_KIND
            16,  # EVT_FOLLOW   <-- UJ: kurzorkovetes
            12,  # EVT_PEEK     <-- UJ: elbujas / kikukucskalas
        ]

        # idle mozgas
        self.curX = self.curY = self.targetX = self.targetY = 0.0
        self.lastMoveTime = 0; self.waitTime = 0
        self.isMoving = False; self.isBlinking = False
        self.lastBlinkTime = 0
        self.eye1X = self.eye1Y = self.eye2X = self.eye2Y = 0.0
        self.speed1 = self.speed2 = 0.2

        # ido / napi ritmus
        self.dayPhase = DAY_ACTIVE; self.prevDayPhase = DAY_ACTIVE
        self.currentHour = 12; self.currentMinute = 0
        self.currentMonth = 1; self.currentDay = 1
        self.lastClockCheck = -10**9

        # idojaras
        self.lastTemperature = float("nan")
        self.lastWeatherCode = -1
        self.lastWeatherFetch = 0
        self._weatherBusy = False

        self.miniState = MF_NONE
        self.lastEventCheck = 0
        self.nextEventWait = 30000

        # thinking
        self.thinkInPlace = False; self.thinkDotsVisible = 0
        self.thinkPhaseTime = 0; self.thinkLoops = 0
        # joy
        self.joyPhase = -1; self.joyTheta = 0.0
        self.joyDownY = 0.0; self.joySpringPos = 0.0; self.joySpringVel = 0.0
        # wink
        self.winkEyeIndex = 0; self.winkStart = 0
        # dream
        self.dreamInPlace = False; self.dreamPhaseTime = 0; self.dreamIcon = 0
        # sleep / wake
        self.sleepZVisible = 0; self.sleepZTime = 0
        self.wakePhase = 0; self.wakeStartTime = 0
        self.eye1WakeOffX = self.eye1WakeOffY = self.eye2WakeOffX = self.eye2WakeOffY = 0.0
        self.manualWakeActive = False; self.manualWakeUntil = 0
        # charge happy
        self.chargeBouncePhase = 0; self.chargeBounceCount = 0
        self.chargeBounceY = 0.0; self.chargeBounceVel = 0.0
        # feed happy
        self.feedPhase = 0; self.feedBallY = 0.0
        self.feedFlashCount = 0; self.feedFlashTime = 0; self.feedFlashOn = False
        # circle seq
        self.circleSeqStep = 0; self.circleSeqBlend = 0.0; self.circleSeqPhase = 0
        self.circleSeqHoldStart = 0
        # explode
        self.explodePhase = 0; self.explodeScale = 1.0
        self.particles = [Particle() for _ in range(8)]
        self.explodePhaseTime = 0
        # dart
        self.dartStartTime = 0; self.dartNextJump = 0
        self.dartEye1X = self.dartEye1Y = self.dartEye2X = self.dartEye2Y = 0.0
        # sink
        self.sinkCycle = 0; self.sinkPhase = 0; self.sinkY = 0.0
        # game win / lose
        self.gameLoseStart = 0
        self.gameWinHoldStart = 0; self.gameWinHolding = False
        # ehseg
        self.hungerState = HUNGER_IDLE
        self.hungerTimerStart = 0; self.hungerWaitDuration = 0
        self.hungerShapeBlend = 0.0
        self.hungerLastTick = 0; self.hungerElapsedMs = 0
        # jatek: fej vagy iras
        self.gameActive = False; self.gameWaitingChoice = False
        self.gameStartTime = 0
        self.gameMessage = ""; self.gameMessageUntil = 0
        # jatekvalaszto
        self.selectedGameType = GAME_COINFLIP
        self.gameSelectMode = False; self.gameSelectUntil = 0
        # reakcio
        self.reactionActive = False; self.reactionPhase = REACT_WAITING
        self.reactionWaitUntil = 0; self.reactionArmedTime = 0; self.reactionSide = False
        # szinkron
        self.syncActive = False
        self.syncShapeLeft = SYNC_CURIOUS; self.syncShapeRight = SYNC_CIRCLE
        self.syncLeftNextChange = 0; self.syncRightNextChange = 0
        self.syncGameStart = 0
        self.syncLastPetPress = 0; self.syncLastGamePress = 0
        # menu
        self.menuIndex = 0
        self.menuMessage = ""; self.menuMessageUntil = 0
        self.infoKindMessage = ""
        # szem-forma
        self.activeShapeType = SHAPE_NORMAL
        self.shapePhase = -1; self.shapeBlend = 0.0; self.shapeHoldStart = 0
        self.forceFocusedShape = False
        # info-arc
        self.infoPhase = 0; self.infoEyeScale = 1.0; self.infoPhaseTime = 0

        # UJ: kurzorkovetes
        self.followStart = 0; self.followDuration = 0
        # UJ: kukucskalas
        self.peekPhase = 0; self.peekOff = 0.0; self.peekHoldUntil = 0
        self.peekLookStart = 0; self.peekDirX = 0.0; self.peekDirY = 1.0
        self.peekHideAgain = False
        self.peekLookX = 0.0

    # ================= IDO / NAPI RITMUS =================
    def updateClock(self):
        now = self.millis()
        if now - self.lastClockCheck < self.CLOCK_CHECK_INTERVAL:
            return
        self.lastClockCheck = now
        t = datetime.datetime.now()  # a PC ora mar helyi ido (CET/CEST)
        self.currentHour = t.hour; self.currentMinute = t.minute
        self.currentMonth = t.month; self.currentDay = t.day

        self.prevDayPhase = self.dayPhase
        mins = self.currentHour * 60 + self.currentMinute
        if mins >= 23 * 60 or mins < 7 * 60 + 30: self.dayPhase = DAY_SLEEP
        elif mins < 8 * 60: self.dayPhase = DAY_WAKING
        elif mins < 22 * 60 + 30: self.dayPhase = DAY_ACTIVE
        else: self.dayPhase = DAY_WINDDOWN

        if self.dayPhase == DAY_SLEEP and self.prevDayPhase != DAY_SLEEP and self.miniState != MF_SLEEP:
            self._goToSleep(now)
        if self.dayPhase == DAY_WAKING and self.prevDayPhase == DAY_SLEEP:
            self.miniState = MF_WAKE; self.wakePhase = 0; self.wakeStartTime = now
            self.eye1WakeOffX = self.eye1WakeOffY = self.eye2WakeOffX = self.eye2WakeOffY = 0
        self.forceFocusedShape = (self.dayPhase in (DAY_WINDDOWN, DAY_WAKING))

    def _goToSleep(self, now):
        self.miniState = MF_SLEEP
        self.sleepZVisible = 0; self.sleepZTime = now
        self.manualWakeActive = False
        self.eye1X = self.eye1Y = self.eye2X = self.eye2Y = 0
        self.isMoving = False
        if self.hungerState != HUNGER_IDLE:
            self.hungerState = HUNGER_IDLE; self.hungerElapsedMs = 0
            self.hungerWaitDuration = randomHungerWait()

    # ================= WEATHER =================
    def fetchWeatherIfDue(self):
        now = self.millis()
        if self.lastWeatherFetch != 0 and now - self.lastWeatherFetch < self.WEATHER_INTERVAL:
            return
        if self._weatherBusy:
            return
        self.lastWeatherFetch = now if now != 0 else 1
        self._weatherBusy = True
        threading.Thread(target=self._weatherWorker, args=(now,), daemon=True).start()

    def _weatherWorker(self, now):
        success = False
        try:
            url = ("https://api.open-meteo.com/v1/forecast?latitude=%.2f&longitude=%.2f"
                   "&current_weather=true" % (LAT, LON))
            with urllib.request.urlopen(url, timeout=10) as r:
                doc = json.loads(r.read().decode("utf-8"))
            cw = doc.get("current_weather", {})
            self.lastTemperature = float(cw.get("temperature", float("nan")))
            self.lastWeatherCode = int(cw.get("weathercode", -1))
            success = True
        except Exception:
            pass
        if not success:
            # 15 mp mulva ujra
            self.lastWeatherFetch = now - self.WEATHER_INTERVAL + 15000
        self._weatherBusy = False

    def isEffectivelyAwake(self):
        return (self.dayPhase != DAY_SLEEP) or self.manualWakeActive

    def startChargeHappy(self):
        self.miniState = MF_CHARGE_HAPPY
        self.chargeBouncePhase = 0; self.chargeBounceCount = 0
        self.chargeBounceY = 0; self.chargeBounceVel = 0

    def startFeedHappy(self):
        self.miniState = MF_FEED_HAPPY
        self.feedPhase = 0; self.feedBallY = 70
        self.feedFlashCount = 0; self.feedFlashOn = True

    def _resetJoy(self):
        self.joyPhase = -1; self.joyTheta = 0; self.joyDownY = 0
        self.joySpringPos = 0; self.joySpringVel = 0

    def resolveGame(self, playerPickedHeads):
        self.gameWaitingChoice = False
        self.gameActive = False
        self.shapePhase = 2
        actualHeads = random(0, 2) == 0
        playerWins = (playerPickedHeads == actualHeads)
        self.gameMessage = "Fej!" if actualHeads else "Írás!"
        self.gameMessage += " Te nyertél!" if playerWins else " Én nyertem!"
        self.gameMessageUntil = self.millis() + 3000
        if playerWins:
            self.miniState = MF_GAME_LOSE
            self.gameLoseStart = self.millis()
        else:
            self.miniState = MF_GAME_WIN
            self._resetJoy(); self.gameWinHolding = False

    def onPetShort(self):
        if self.gameSelectMode: self.confirmGameSelect(); return
        if self.gameWaitingChoice: self.resolveGame(True); return
        if self.reactionActive: self.handleReactionPress(); return
        if self.syncActive: self.syncLastPetPress = self.millis(); self.handleSyncPress(); return
        blocked = (self.hungerState != HUNGER_IDLE) or (self.miniState == MF_SLEEP) or not self.isEffectivelyAwake()
        if blocked: return
        self.startChargeHappy()

    def onPetLong(self):
        if self.hungerState == HUNGER_CIRCLE:
            self.hungerState = HUNGER_IDLE
            self.hungerTimerStart = self.millis()
            self.hungerElapsedMs = 0
            self.hungerWaitDuration = randomHungerWait()
            self.startFeedHappy()
            return
        if self.dayPhase == DAY_SLEEP and not self.manualWakeActive:
            if self.miniState == MF_SLEEP:
                self.miniState = MF_WAKE; self.wakePhase = 0; self.wakeStartTime = self.millis()
                self.manualWakeActive = True
                self.manualWakeUntil = self.millis() + self.MANUAL_WAKE_DURATION
            return
        if self.manualWakeActive:
            self.manualWakeUntil = self.millis() + self.MANUAL_WAKE_DURATION

    def startCoinflipGame(self):
        self.gameActive = True; self.gameWaitingChoice = True
        self.gameStartTime = self.millis()
        self.gameMessage = "Fej vagy írás?"
        self.gameMessageUntil = self.millis() + self.GAME_CHOICE_TIMEOUT
        self.activeShapeType = SHAPE_CURIOUS
        self.shapePhase = 0; self.shapeBlend = 0

    # ---------------- REAKCIO TESZT ----------------
    def startReactionGame(self):
        self.gameActive = True; self.reactionActive = True
        self.reactionPhase = REACT_WAITING
        self.reactionWaitUntil = self.millis() + random(2000, 6000)
        self.isMoving = False
        self.eye1X = self.eye1Y = self.eye2X = self.eye2Y = 0
        self.activeShapeType = SHAPE_CURIOUS; self.shapePhase = 0; self.shapeBlend = 0
        self.gameMessage = "Figyelj..."
        self.gameMessageUntil = self.millis() + 60000

    def finishReactionGame(self, cheated, reactionMs):
        self.reactionActive = False; self.gameActive = False
        self.shapePhase = 2
        self.eye1X = self.eye1Y = self.eye2X = self.eye2Y = 0
        if cheated:
            self.gameMessage = "Csalás! Korai nyomás."
            self.miniState = MF_GAME_LOSE; self.gameLoseStart = self.millis()
        else:
            self.gameMessage = "%.2f mp!" % (reactionMs / 1000.0)
            self.miniState = MF_GAME_WIN
            self._resetJoy(); self.gameWinHolding = False
        self.gameMessageUntil = self.millis() + 4000

    def updateReactionGame(self, now):
        if not self.reactionActive: return
        if self.reactionPhase == REACT_WAITING:
            if now >= self.reactionWaitUntil:
                self.reactionPhase = REACT_ARMED
                self.reactionArmedTime = now
                self.reactionSide = random(0, 2) == 0
                self.eye1X = self.eye2X = 22 if self.reactionSide else -22
                self.eye1Y = self.eye2Y = 0
                self.gameMessage = "Nyomj most!"
                self.gameMessageUntil = now + self.REACT_ARMED_TIMEOUT
        elif self.reactionPhase == REACT_ARMED:
            if now - self.reactionArmedTime > self.REACT_ARMED_TIMEOUT:
                self.gameMessage = "Túl lassú voltál!"
                self.finishReactionGame(True, 0)

    def handleReactionPress(self):
        now = self.millis()
        if self.reactionPhase == REACT_WAITING:
            self.finishReactionGame(True, 0)
        elif self.reactionPhase == REACT_ARMED:
            self.finishReactionGame(False, now - self.reactionArmedTime)

    # ---------------- SZEM-SZINKRON ----------------
    def startSyncGame(self):
        self.gameActive = True; self.syncActive = True
        self.syncGameStart = self.millis()
        self.isMoving = False
        self.eye1X = self.eye1Y = self.eye2X = self.eye2Y = 0
        self.syncShapeLeft = random(0, SYNC_SHAPE_COUNT)
        self.syncShapeRight = random(0, SYNC_SHAPE_COUNT)
        self.syncLeftNextChange = self.millis() + random(self.SYNC_MIN_INTERVAL, self.SYNC_MAX_INTERVAL)
        self.syncRightNextChange = self.millis() + random(self.SYNC_MIN_INTERVAL, self.SYNC_MAX_INTERVAL)
        self.syncLastPetPress = 0; self.syncLastGamePress = 0
        self.gameMessage = "Kattints, ha egyeznek!"
        self.gameMessageUntil = self.millis() + 60000

    def finishSyncGame(self, matched):
        self.syncActive = False; self.gameActive = False
        if matched:
            self.gameMessage = "Talált! Egyeznek!"
            self.miniState = MF_GAME_WIN
            self._resetJoy(); self.gameWinHolding = False
        else:
            self.gameMessage = "Nem egyeztek!"
            self.miniState = MF_GAME_LOSE; self.gameLoseStart = self.millis()
        self.gameMessageUntil = self.millis() + 4000

    def updateSyncGame(self, now):
        if not self.syncActive: return
        if now >= self.syncLeftNextChange:
            self.syncShapeLeft = random(0, SYNC_SHAPE_COUNT)
            self.syncLeftNextChange = now + random(self.SYNC_MIN_INTERVAL, self.SYNC_MAX_INTERVAL)
        if now >= self.syncRightNextChange:
            self.syncShapeRight = random(0, SYNC_SHAPE_COUNT)
            self.syncRightNextChange = now + random(self.SYNC_MIN_INTERVAL, self.SYNC_MAX_INTERVAL)
        if now - self.syncGameStart > self.SYNC_GAME_TIMEOUT:
            self.gameMessage = "Lejárt az idő!"
            self.finishSyncGame(False)

    def handleSyncPress(self):
        self.finishSyncGame(self.syncShapeLeft == self.syncShapeRight)

    # ---------------- JATEK-VALASZTO ----------------
    def startGameSelect(self):
        blocked = (self.hungerState != HUNGER_IDLE) or not self.isEffectivelyAwake() or self.gameActive or self.miniState != MF_NONE
        if blocked: return
        self.gameActive = True; self.gameSelectMode = True
        self.selectedGameType = GAME_COINFLIP
        self.gameSelectUntil = self.millis() + self.GAME_SELECT_TIMEOUT
        self.gameMessage = "Játék: Fej vagy írás"
        self.gameMessageUntil = self.gameSelectUntil
        self.activeShapeType = SHAPE_CURIOUS; self.shapePhase = 0; self.shapeBlend = 0

    def cycleGameSelect(self):
        self.selectedGameType = (self.selectedGameType + 1) % GAME_COUNT
        self.gameSelectUntil = self.millis() + self.GAME_SELECT_TIMEOUT
        names = ["Fej vagy írás", "Reakcióteszt", "Szem-szinkron"]
        self.gameMessage = "Játék: " + names[self.selectedGameType]
        self.gameMessageUntil = self.gameSelectUntil

    def confirmGameSelect(self):
        self.gameSelectMode = False
        stillOk = (self.hungerState == HUNGER_IDLE) and self.isEffectivelyAwake()
        if not stillOk:
            self.gameActive = False; self.shapePhase = 2; return
        if self.selectedGameType == GAME_COINFLIP: self.startCoinflipGame()
        elif self.selectedGameType == GAME_REACTION: self.startReactionGame()
        else: self.startSyncGame()

    def updateGameSelect(self, now):
        if not self.gameSelectMode: return
        if now > self.gameSelectUntil:
            self.gameSelectMode = False; self.gameActive = False; self.shapePhase = 2

    def onGameShort(self):
        if self.gameSelectMode: self.cycleGameSelect(); return
        if self.gameWaitingChoice: self.resolveGame(False); return
        if self.reactionActive: self.handleReactionPress(); return
        if self.syncActive: self.syncLastGamePress = self.millis(); self.handleSyncPress(); return
        self.startGameSelect()

    def onGameLong(self):
        if self.dayPhase == DAY_SLEEP and not self.manualWakeActive:
            if self.miniState == MF_SLEEP:
                self.miniState = MF_WAKE; self.wakePhase = 0; self.wakeStartTime = self.millis()
                self.manualWakeActive = True
                self.manualWakeUntil = self.millis() + self.MANUAL_WAKE_DURATION
            return
        if self.manualWakeActive:
            self.manualWakeUntil = self.millis() + self.MANUAL_WAKE_DURATION
        self.menuIndex = (self.menuIndex + 1) % 3
        if self.menuIndex == 0:
            self.menuMessage = "Most %02d:%02d van." % (self.currentHour, self.currentMinute)
        elif self.menuIndex == 1:
            self.menuMessage = kindWords[random(0, KIND_WORDS_COUNT)]
        else:
            if math.isnan(self.lastTemperature): self.menuMessage = "Még nem tudom az időjárást."
            else: self.menuMessage = "Kint %.1f fok van." % self.lastTemperature
        self.menuMessageUntil = self.millis() + 4000

    # ================= ESEMENY-UTEMEZO =================
    def triggerRandomEvent(self):
        totalWeight = sum(self.eventWeights)
        r = random(0, totalWeight)
        cum = 0; chosen = EVT_NONE
        for i, w in enumerate(self.eventWeights):
            cum += w
            if r < cum: chosen = i; break

        now = self.millis()
        if chosen == EVT_NONE:
            pass
        elif chosen == EVT_SHAPE_CURIOUS:
            self.activeShapeType = SHAPE_CURIOUS; self.shapePhase = 0; self.shapeBlend = 0
        elif chosen == EVT_SHAPE_CUTE:
            self.activeShapeType = SHAPE_CUTE; self.shapePhase = 0; self.shapeBlend = 0
        elif chosen == EVT_WINK:
            self.miniState = MF_WINK; self.winkEyeIndex = random(0, 2); self.winkStart = now
        elif chosen == EVT_THINKING:
            self.miniState = MF_THINKING
            self.thinkInPlace = False; self.thinkDotsVisible = 0; self.thinkLoops = 0
            self.isMoving = True; self.targetX = self.LOOKAWAY_TARGET_X; self.targetY = self.LOOKAWAY_TARGET_Y
        elif chosen == EVT_JOY:
            self.miniState = MF_JOY; self._resetJoy(); self.isMoving = False
        elif chosen == EVT_DREAM:
            self.miniState = MF_DREAM
            self.dreamInPlace = False; self.isMoving = True
            self.targetX = self.LOOKAWAY_TARGET_X; self.targetY = self.LOOKAWAY_TARGET_Y
        elif chosen == EVT_CIRCLE_SEQ:
            self.miniState = MF_CIRCLE_SEQ
            self.circleSeqStep = 0; self.circleSeqPhase = 0; self.circleSeqBlend = 0
        elif chosen == EVT_DART:
            self.miniState = MF_DART; self.dartStartTime = now; self.dartNextJump = now
        elif chosen == EVT_SINK_REPEAT:
            self.miniState = MF_SINK_REPEAT
            self.sinkCycle = 0; self.sinkPhase = 0; self.sinkY = 0
        elif chosen == EVT_EXPLODE:
            self.miniState = MF_EXPLODE
            self.explodePhase = 0; self.explodeScale = 1.0; self.explodePhaseTime = now
            for p in self.particles: p.active = False
        elif chosen == EVT_INFO_TIME:
            self.miniState = MF_INFO_TIME; self.infoPhase = 0; self.infoEyeScale = 1.0; self.isMoving = False
        elif chosen == EVT_INFO_WEATHER:
            self.miniState = MF_INFO_WEATHER; self.infoPhase = 0; self.infoEyeScale = 1.0; self.isMoving = False
        elif chosen == EVT_INFO_KIND:
            self.infoKindMessage = kindWords[random(0, KIND_WORDS_COUNT)]
            self.miniState = MF_INFO_KIND; self.infoPhase = 0; self.infoEyeScale = 1.0; self.isMoving = False
        elif chosen == EVT_FOLLOW:
            self.startFollow()
        elif chosen == EVT_PEEK:
            self.startPeek()

    def updateInfoFace(self, now):
        if self.infoPhase == 0:
            self.infoEyeScale -= self.INFO_FADE_SPEED
            if self.infoEyeScale <= 0:
                self.infoEyeScale = 0; self.infoPhase = 1; self.infoPhaseTime = now
            return False
        elif self.infoPhase == 1:
            if now - self.infoPhaseTime > self.INFO_HOLD_DURATION: self.infoPhase = 2
            return False
        else:
            self.infoEyeScale += self.INFO_FADE_SPEED
            if self.infoEyeScale >= 1:
                self.infoEyeScale = 1; return True
            return False

    # ================= MINIFACE FRISSITESEK =================
    def _eyesAtTarget(self):
        return (abs(self.targetX - self.eye1X) < 1 and abs(self.targetY - self.eye1Y) < 1 and
                abs(self.targetX - self.eye2X) < 1 and abs(self.targetY - self.eye2Y) < 1)

    def updateThinking(self, now):
        if not self.thinkInPlace:
            if self._eyesAtTarget():
                self.thinkInPlace = True; self.thinkPhaseTime = now; self.thinkDotsVisible = 0
            return False
        if now - self.thinkPhaseTime > self.THINK_DOT_INTERVAL:
            self.thinkPhaseTime = now; self.thinkDotsVisible += 1
            if self.thinkDotsVisible > 3:
                self.thinkDotsVisible = 0; self.thinkLoops += 1
        return self.thinkLoops >= self.THINK_MAX_LOOPS

    def updateDream(self, now):
        if not self.dreamInPlace:
            if self._eyesAtTarget():
                self.dreamInPlace = True; self.dreamPhaseTime = now; self.dreamIcon = random(0, 7)
            return False
        return (now - self.dreamPhaseTime) > self.DREAM_DURATION

    def updateJoy(self):
        if self.joyPhase == -1:
            self.eye1X += (0 - self.eye1X) * 0.25; self.eye1Y += (0 - self.eye1Y) * 0.25
            self.eye2X += (0 - self.eye2X) * 0.25; self.eye2Y += (0 - self.eye2Y) * 0.25
            if abs(self.eye1X) < 0.5 and abs(self.eye1Y) < 0.5 and abs(self.eye2X) < 0.5 and abs(self.eye2Y) < 0.5:
                self.eye1X = self.eye1Y = self.eye2X = self.eye2Y = 0; self.joyPhase = 0
            return False
        elif self.joyPhase == 0:
            self.joyTheta += self.JOY_THETA_STEP
            if self.joyTheta >= 360: self.joyTheta = 0; self.joyPhase = 1
            return False
        elif self.joyPhase == 1:
            self.joyDownY += 4
            if self.joyDownY >= self.JOY_MAX_DOWN:
                self.joyDownY = self.JOY_MAX_DOWN; self.joyPhase = 2
                self.joySpringPos = self.JOY_MAX_DOWN; self.joySpringVel = 0
            return False
        else:
            k, damping = 0.25, 0.72
            accel = (0 - self.joySpringPos) * k
            self.joySpringVel = (self.joySpringVel + accel) * damping
            self.joySpringPos += self.joySpringVel
            if abs(self.joySpringPos) < 0.5 and abs(self.joySpringVel) < 0.3:
                self.joySpringPos = 0; return True
            return False

    def updateWink(self, now):
        return (now - self.winkStart) > self.WINK_DURATION

    def updateSleepZZZ(self, now):
        if now - self.sleepZTime > self.SLEEP_Z_INTERVAL:
            self.sleepZTime = now
            self.sleepZVisible += 1
            if self.sleepZVisible > 4: self.sleepZVisible = 0

    def updateWake(self, now):
        if self.wakePhase == 0:
            elapsed = now - self.wakeStartTime
            if elapsed >= self.WAKE_SHAKE_DURATION:
                self.wakePhase = 1; return False
            decay = 1.0 - elapsed / self.WAKE_SHAKE_DURATION
            osc = math.sin(elapsed * self.WAKE_FREQ) * self.WAKE_AMPLITUDE * decay
            self.eye2WakeOffX = osc; self.eye2WakeOffY = -osc
            self.eye1WakeOffX = -osc; self.eye1WakeOffY = -osc
            return False
        else:
            self.eye1WakeOffX *= 0.7; self.eye1WakeOffY *= 0.7
            self.eye2WakeOffX *= 0.7; self.eye2WakeOffY *= 0.7
            if (abs(self.eye1WakeOffX) < 0.3 and abs(self.eye1WakeOffY) < 0.3 and
                    abs(self.eye2WakeOffX) < 0.3 and abs(self.eye2WakeOffY) < 0.3):
                self.eye1WakeOffX = self.eye1WakeOffY = self.eye2WakeOffX = self.eye2WakeOffY = 0
                return True
            return False

    def updateChargeHappy(self):
        k, damping = 0.35, 0.65
        if self.chargeBouncePhase == 0:
            self.chargeBounceVel = -6; self.chargeBouncePhase = 1
        accel = (0 - self.chargeBounceY) * k
        self.chargeBounceVel = (self.chargeBounceVel + accel) * damping
        self.chargeBounceY += self.chargeBounceVel
        if (self.chargeBouncePhase == 1 and self.chargeBounceY > -0.5 and
                -0.3 < self.chargeBounceVel < 0.3):
            self.chargeBounceCount += 1
            if self.chargeBounceCount >= self.CHARGE_BOUNCE_TARGET: return True
            self.chargeBounceVel = -6
        return False

    def updateFeedHappy(self, now):
        if self.feedPhase == 0:
            self.feedBallY -= self.FEED_BALL_SPEED
            if self.feedBallY <= 0:
                self.feedBallY = 0; self.feedPhase = 1
                self.feedFlashCount = 0; self.feedFlashTime = now; self.feedFlashOn = True
            return False
        else:
            if now - self.feedFlashTime > self.FEED_FLASH_INTERVAL:
                self.feedFlashTime = now
                self.feedFlashOn = not self.feedFlashOn
                self.feedFlashCount += 1
                if self.feedFlashCount >= self.FEED_FLASH_TOGGLES: return True
            return False

    def updateCircleSeq(self, now):
        if self.circleSeqPhase == 0:
            self.circleSeqBlend += self.CIRCLE_SEQ_SPEED
            if self.circleSeqBlend >= 1:
                self.circleSeqBlend = 1; self.circleSeqPhase = 1; self.circleSeqHoldStart = now
        elif self.circleSeqPhase == 1:
            if now - self.circleSeqHoldStart > self.CIRCLE_SEQ_HOLD: self.circleSeqPhase = 2
        else:
            self.circleSeqBlend -= self.CIRCLE_SEQ_SPEED
            if self.circleSeqBlend <= 0:
                self.circleSeqBlend = 0
                self.circleSeqStep += 1
                if self.circleSeqStep > 2: return True
                self.circleSeqPhase = 0
        return False

    def updateExplode(self, now):
        if self.explodePhase == 0:
            self.explodeScale += 0.05
            if self.explodeScale >= self.EXPLODE_MAX_SCALE:
                self.explodePhase = 1; self.explodePhaseTime = now
                for p in self.particles:
                    p.active = True; p.x = 0; p.y = 0
                    ang = random(0, 360) * math.pi / 180.0
                    spd = random(20, 45) / 10.0
                    p.vx = math.cos(ang) * spd
                    p.vy = math.sin(ang) * spd - 1.5
            return False
        elif self.explodePhase == 1:
            self.explodeScale = 0
            for p in self.particles:
                if p.active:
                    p.x += p.vx; p.y += p.vy; p.vy += 0.35
            if now - self.explodePhaseTime > 1400:
                self.explodePhase = 2; self.explodeScale = 0.1
            return False
        else:
            self.explodeScale += 0.015
            if self.explodeScale >= 1.0:
                self.explodeScale = 1.0; return True
            return False

    def updateDart(self, now):
        if now - self.dartStartTime > self.DART_DURATION:
            self.dartEye1X += (0 - self.dartEye1X) * 0.3; self.dartEye1Y += (0 - self.dartEye1Y) * 0.3
            self.dartEye2X += (0 - self.dartEye2X) * 0.3; self.dartEye2Y += (0 - self.dartEye2Y) * 0.3
            return (abs(self.dartEye1X) < 0.5 and abs(self.dartEye1Y) < 0.5 and
                    abs(self.dartEye2X) < 0.5 and abs(self.dartEye2Y) < 0.5)
        if now >= self.dartNextJump:
            self.dartEye1X = random(-14, 15); self.dartEye1Y = random(-10, 11)
            self.dartEye2X = random(-14, 15); self.dartEye2Y = random(-10, 11)
            self.dartNextJump = now + random(80, 180)
        return False

    def updateSinkRepeat(self):
        speedFactor = 1.0 - (self.sinkCycle * 0.35)
        if speedFactor < 0.18: speedFactor = 0.18
        step = 6.0 / speedFactor
        if self.sinkPhase == 0:
            self.sinkY += step
            if self.sinkY >= 90: self.sinkPhase = 1; self.sinkY = -90
        else:
            self.sinkY += step
            if self.sinkY >= 0:
                self.sinkY = 0; self.sinkPhase = 0; self.sinkCycle += 1
                if self.sinkCycle >= self.SINK_MAX_CYCLES: return True
        return False

    # ================= EHSEG =================
    def updateHunger(self, now):
        asleep = (self.dayPhase == DAY_SLEEP and not self.manualWakeActive)
        if self.hungerLastTick == 0: self.hungerLastTick = now
        if self.hungerState == HUNGER_IDLE:
            if not asleep: self.hungerElapsedMs += (now - self.hungerLastTick)
            self.hungerLastTick = now
            if self.hungerElapsedMs >= self.hungerWaitDuration:
                self.hungerState = HUNGER_CIRCLE
                self.hungerTimerStart = now
                self.hungerShapeBlend = 0
        elif self.hungerState == HUNGER_CIRCLE:
            self.hungerLastTick = now
            if not asleep:
                if self.hungerShapeBlend < 1: self.hungerShapeBlend += 0.08
                if now - self.hungerTimerStart > self.HUNGER_WINDOW:
                    self.hungerState = HUNGER_SAD; self.hungerTimerStart = now
            else:
                self.hungerTimerStart = now
        elif self.hungerState == HUNGER_SAD:
            self.hungerLastTick = now
            if not asleep:
                if now - self.hungerTimerStart > self.HUNGER_SAD_DURATION:
                    self.hungerState = HUNGER_IDLE
                    self.hungerTimerStart = now
                    self.hungerElapsedMs = 0
                    self.hungerWaitDuration = randomHungerWait()
                    self.hungerShapeBlend = 0
            else:
                self.hungerTimerStart = now

    # ================= SZEM-FORMA IDLE RENDSZER =================
    def updateShapeState(self, now):
        allowed = (self.hungerState == HUNGER_IDLE) and (self.miniState == MF_NONE) and not self.gameActive and (self.dayPhase == DAY_ACTIVE)
        if not allowed:
            if self.shapePhase != -1 and self.shapePhase != 2: self.shapePhase = 2
        if self.shapePhase == -1: return
        if self.shapePhase == 0:
            self.shapeBlend += SHAPE_BLEND_SPEEDS[self.activeShapeType]
            if self.shapeBlend >= 1:
                self.shapeBlend = 1; self.shapePhase = 1; self.shapeHoldStart = now
        elif self.shapePhase == 1:
            if not allowed or now - self.shapeHoldStart > SHAPE_HOLD_DURATIONS[self.activeShapeType]:
                self.shapePhase = 2
        elif self.shapePhase == 2:
            self.shapeBlend -= SHAPE_BLEND_SPEEDS[self.activeShapeType]
            if self.shapeBlend <= 0:
                self.shapeBlend = 0; self.shapePhase = -1

    def updateGame(self, now):
        if not self.gameActive or not self.gameWaitingChoice: return
        if now - self.gameStartTime > self.GAME_CHOICE_TIMEOUT:
            self.resolveGame(random(0, 2) == 0)

    # ================= UJ: KURZORKOVETES =================
    def startFollow(self):
        self.miniState = MF_FOLLOW
        self.followStart = self.millis()
        self.followDuration = random(4000, 9000)
        self.isMoving = False

    def updateFollow(self, now):
        dx, dy = self.cursor_rel()
        tx = max(-25.0, min(25.0, dx * 0.12))
        ty = max(-20.0, min(20.0, dy * 0.12))
        self.eye1X += (tx - self.eye1X) * 0.25; self.eye1Y += (ty - self.eye1Y) * 0.25
        self.eye2X += (tx - self.eye2X) * 0.22; self.eye2Y += (ty - self.eye2Y) * 0.22
        return now - self.followStart > self.followDuration

    # ================= UJ: ELBUJAS / KIKUKUCSKALAS =================
    PEEK_SPEED = 3.5

    def _peekHiddenDist(self):
        return 118.0 if abs(self.peekDirX) > 0.5 else 62.0

    def _peekPartialDist(self):
        return 72.0 if abs(self.peekDirX) > 0.5 else 26.0

    def startPeek(self):
        self.miniState = MF_PEEK
        self.peekDirX, self.peekDirY = self.peek_dir()
        self.peekPhase = 0; self.peekOff = 0.0
        self.peekHideAgain = random(0, 100) < 35
        self.peekLookX = 0.0
        self.isMoving = False

    def updatePeek(self, now):
        # 0: elbujik a szelen  1: rejtve var  2: felbukkan felig  3: nezelodik  4: visszajon
        if self.peekPhase == 0:
            self.peekOff += self.PEEK_SPEED
            if self.peekOff >= self._peekHiddenDist():
                self.peekOff = self._peekHiddenDist(); self.peekPhase = 1
                self.peekHoldUntil = now + random(2000, 6000)
        elif self.peekPhase == 1:
            if now >= self.peekHoldUntil: self.peekPhase = 2
        elif self.peekPhase == 2:
            target = self._peekPartialDist()
            self.peekOff += (target - self.peekOff) * 0.12
            if abs(target - self.peekOff) < 0.6:
                self.peekPhase = 3; self.peekLookStart = now
        elif self.peekPhase == 3:
            t = now - self.peekLookStart
            self.peekLookX = math.sin(t * 0.006) * 8.0
            if t > 2600:
                self.peekLookX = 0.0
                if self.peekHideAgain:
                    self.peekHideAgain = False; self.peekPhase = 0
                else:
                    self.peekPhase = 4
        else:
            self.peekOff += (0 - self.peekOff) * 0.15
            if abs(self.peekOff) < 0.5:
                self.peekOff = 0.0; return True
        return False

    def peekOffsets(self):
        # oldaliranyu nezelodes a kukucskalas iranyara merolegesen
        lx = -self.peekDirY * self.peekLookX
        ly = self.peekDirX * self.peekLookX
        return self.peekDirX * self.peekOff + lx, self.peekDirY * self.peekOff + ly

    def endExtras(self):
        """UJ: kattintasra azonnal vissza a sima allapotba (kovetes / kukucskalas)."""
        if self.miniState in (MF_FOLLOW, MF_PEEK):
            self.miniState = MF_NONE
            self.peekOff = 0.0; self.peekPhase = 0; self.peekLookX = 0.0
            self.eye1X = self.eye1Y = self.eye2X = self.eye2Y = 0
            self.isMoving = False; self.lastMoveTime = self.millis(); self.waitTime = random(800, 2000)
            return True
        return False

    def isIdleForRampage(self):
        """UJ: csak akkor randalirozhat, ha nyugodt, ebren levo allapotban van."""
        return (self.miniState == MF_NONE and self.hungerState == HUNGER_IDLE and
                not self.gameActive and self.dayPhase == DAY_ACTIVE)

    def _blink(self, now):
        if not self.isBlinking and now - self.lastBlinkTime > random(3000, 7000):
            self.isBlinking = True; self.lastBlinkTime = now
        elif self.isBlinking and now - self.lastBlinkTime > 150:
            self.isBlinking = False
        return self.isBlinking

    def _finishState(self, now):
        self.miniState = MF_NONE; self.lastMoveTime = now; self.waitTime = random(500, 1500)

    # ================= SETUP / LOOP =================
    def setup(self):
        now = self.millis()
        self.hungerTimerStart = now
        self.hungerWaitDuration = randomHungerWait()
        self.hungerElapsedMs = 0
        self.hungerLastTick = now if now != 0 else 1
        self.lastEventCheck = now
        self.nextEventWait = random(self.EVENT_CHECK_MIN, self.EVENT_CHECK_MAX)
        self.updateClock()
        # ha ejjel inditjuk, rogton aludjon
        if self.dayPhase == DAY_SLEEP:
            self._goToSleep(now)

    def loop(self):
        now = self.millis()
        self.updateClock()
        self.fetchWeatherIfDue()

        hungerBlocking = (self.hungerState != HUNGER_IDLE)
        sleeping = (self.miniState == MF_SLEEP)

        self.updateHunger(now)

        if self.manualWakeActive and now > self.manualWakeUntil:
            self.manualWakeActive = False
            if self.dayPhase == DAY_SLEEP:
                self._goToSleep(now)

        self.updateGame(now)
        self.updateGameSelect(now)
        self.updateReactionGame(now)
        self.updateSyncGame(now)

        if (self.miniState == MF_NONE and not hungerBlocking and not sleeping and not self.gameActive and
                self.dayPhase == DAY_ACTIVE and self.shapePhase == -1 and
                now - self.lastEventCheck > self.nextEventWait):
            self.lastEventCheck = now
            self.nextEventWait = random(self.EVENT_CHECK_MIN, self.EVENT_CHECK_MAX)
            self.triggerRandomEvent()

        ms = self.miniState
        posControlled = ms in (MF_JOY, MF_SLEEP, MF_WAKE, MF_CHARGE_HAPPY, MF_FEED_HAPPY, MF_EXPLODE,
                               MF_DART, MF_SINK_REPEAT, MF_CIRCLE_SEQ, MF_GAME_WIN,
                               MF_INFO_TIME, MF_INFO_WEATHER, MF_INFO_KIND,
                               MF_FOLLOW, MF_PEEK)
        if not posControlled and not hungerBlocking and not self.reactionActive and not self.syncActive:
            if not self.isMoving:
                if now - self.lastMoveTime > self.waitTime:
                    self.targetX = random(-25, 26); self.targetY = random(-20, 21)
                    self.isMoving = True
                    self.speed1 = random(15, 26) / 100.0; self.speed2 = random(15, 26) / 100.0
            else:
                self.eye1X += (self.targetX - self.eye1X) * self.speed1
                self.eye1Y += (self.targetY - self.eye1Y) * self.speed1
                self.eye2X += (self.targetX - self.eye2X) * self.speed2
                self.eye2Y += (self.targetY - self.eye2Y) * self.speed2
                self.curX = (self.eye1X + self.eye2X) / 2.0; self.curY = (self.eye1Y + self.eye2Y) / 2.0
                if (self.miniState != MF_THINKING and self.miniState != MF_DREAM and
                        abs(self.targetX - self.curX) < 1 and abs(self.targetY - self.curY) < 1):
                    self.isMoving = False; self.lastMoveTime = now; self.waitTime = random(800, 3000)

        self.updateShapeState(now)

        eye1Closed = eye2Closed = False
        eye1OffX = eye1OffY = eye2OffX = eye2OffY = 0.0
        eye1Scale = eye2Scale = 1.0
        showThoughtBubble = False; thoughtDots = 0
        showDreamBubble = False; dreamIconToShow = 0
        showZZZ = False; zzzCount = 0
        eye1ForceCircle = eye2ForceCircle = False
        circleBlendAmt = 0.0
        clipToBox = False

        if hungerBlocking:
            if self.hungerState == HUNGER_CIRCLE:
                eye1ForceCircle = eye2ForceCircle = True
                circleBlendAmt = self.hungerShapeBlend
        elif self.miniState == MF_THINKING:
            done = self.updateThinking(now)
            showThoughtBubble = self.thinkInPlace; thoughtDots = self.thinkDotsVisible
            if done: self.miniState = MF_NONE; self.isMoving = False; self.lastMoveTime = now; self.waitTime = random(500, 1500)
        elif self.miniState == MF_DREAM:
            done = self.updateDream(now)
            showDreamBubble = self.dreamInPlace; dreamIconToShow = self.dreamIcon
            if done: self.miniState = MF_NONE; self.isMoving = False; self.lastMoveTime = now; self.waitTime = random(500, 1500)
        elif self.miniState == MF_GAME_WIN and self.gameWinHolding:
            if now - self.gameWinHoldStart > self.GAME_WIN_HOLD_DURATION:
                self.gameWinHolding = False
                self._finishState(now)
        elif self.miniState in (MF_JOY, MF_GAME_WIN):
            done = self.updateJoy()
            if self.joyPhase == 0:
                rad = radians(self.joyTheta)
                eye2OffX = self.JOY_RADIUS * (1 - math.cos(rad)); eye2OffY = -self.JOY_RADIUS * math.sin(rad)
                eye1OffX = -self.JOY_RADIUS * (1 - math.cos(rad)); eye1OffY = -self.JOY_RADIUS * math.sin(rad)
            elif self.joyPhase == 1:
                eye1OffY = eye2OffY = self.joyDownY
            elif self.joyPhase == 2:
                eye1OffY = eye2OffY = self.joySpringPos
            if done:
                if self.miniState == MF_GAME_WIN:
                    self.gameWinHolding = True; self.gameWinHoldStart = now
                else:
                    self._finishState(now)
        elif self.miniState == MF_WINK:
            if self.winkEyeIndex == 0: eye1Closed = True
            else: eye2Closed = True
            if self.updateWink(now): self.miniState = MF_NONE
        elif self.miniState == MF_SLEEP:
            self.updateSleepZZZ(now)
            eye1Closed = eye2Closed = True
            showZZZ = True; zzzCount = 0 if self.sleepZVisible > 3 else self.sleepZVisible
        elif self.miniState == MF_WAKE:
            done = self.updateWake(now)
            eye1OffX += self.eye1WakeOffX; eye1OffY += self.eye1WakeOffY
            eye2OffX += self.eye2WakeOffX; eye2OffY += self.eye2WakeOffY
            if done: self._finishState(now)
        elif self.miniState == MF_CHARGE_HAPPY:
            done = self.updateChargeHappy()
            eye1OffY = eye2OffY = self.chargeBounceY
            if done: self._finishState(now)
        elif self.miniState == MF_FEED_HAPPY:
            if self.updateFeedHappy(now): self._finishState(now)
        elif self.miniState == MF_CIRCLE_SEQ:
            done = self.updateCircleSeq(now)
            if self.circleSeqStep == 0: eye1ForceCircle = True
            elif self.circleSeqStep == 1: eye2ForceCircle = True
            else: eye1ForceCircle = eye2ForceCircle = True
            circleBlendAmt = self.circleSeqBlend
            if done: self._finishState(now)
        elif self.miniState == MF_EXPLODE:
            done = self.updateExplode(now)
            eye1Scale = eye2Scale = self.explodeScale
            if done: self._finishState(now)
        elif self.miniState == MF_DART:
            done = self.updateDart(now)
            eye1OffX = self.dartEye1X; eye1OffY = self.dartEye1Y
            eye2OffX = self.dartEye2X; eye2OffY = self.dartEye2Y
            if done: self._finishState(now)
        elif self.miniState == MF_SINK_REPEAT:
            done = self.updateSinkRepeat()
            eye1OffY = eye2OffY = self.sinkY
            if done: self._finishState(now)
        elif self.miniState == MF_GAME_LOSE:
            if now - self.gameLoseStart > self.GAME_LOSE_DURATION: self._finishState(now)
        elif self.miniState in (MF_INFO_TIME, MF_INFO_WEATHER, MF_INFO_KIND):
            done = self.updateInfoFace(now)
            eye1Scale = eye2Scale = self.infoEyeScale
            if done: self._finishState(now)
        elif self.miniState == MF_FOLLOW:          # UJ
            done = self.updateFollow(now)
            eye1Closed = eye2Closed = self._blink(now)
            if done: self._finishState(now)
        elif self.miniState == MF_PEEK:            # UJ
            done = self.updatePeek(now)
            ox, oy = self.peekOffsets()
            eye1OffX += ox; eye1OffY += oy; eye2OffX += ox; eye2OffY += oy
            clipToBox = True
            if done: self._finishState(now)
        else:
            eye1Closed = eye2Closed = self._blink(now)

        # ================= FRAME OSSZEALLITASA (render helyett) =================
        f = Frame()
        f.e1x = EYE1_BASE_X + (self.eye1X + eye1OffX)
        f.e1y = EYE_BASE_Y + (self.eye1Y + eye1OffY)
        f.e2x = EYE2_BASE_X + (self.eye2X + eye2OffX)
        f.e2y = EYE_BASE_Y + (self.eye2Y + eye2OffY)

        shapeToUse = SHAPE_BASE
        wantsFocused = (self.dayPhase != DAY_ACTIVE)
        if wantsFocused: shapeToUse = SHAPE_DEFS[SHAPE_FOCUSED]
        elif self.hungerState == HUNGER_SAD: shapeToUse = SHAPE_DEFS[SHAPE_WORRIED]
        elif self.shapePhase != -1: shapeToUse = lerpShape(SHAPE_BASE, SHAPE_DEFS[self.activeShapeType], self.shapeBlend)
        elif self.miniState == MF_CHARGE_HAPPY: shapeToUse = SHAPE_DEFS[SHAPE_CUTE]
        elif self.miniState == MF_GAME_LOSE: shapeToUse = SHAPE_DEFS[SHAPE_ANGRY]
        elif self.miniState == MF_GAME_WIN and self.gameWinHolding: shapeToUse = SHAPE_DEFS[SHAPE_CUTE]

        f.eye1Shape = lerpShape(shapeToUse, SHAPE_DEFS[SHAPE_CIRCLE], circleBlendAmt) if eye1ForceCircle else shapeToUse
        f.eye2Shape = lerpShape(shapeToUse, SHAPE_DEFS[SHAPE_CIRCLE], circleBlendAmt) if eye2ForceCircle else shapeToUse
        f.eye1Closed, f.eye2Closed = eye1Closed, eye2Closed
        f.eye1Scale, f.eye2Scale = eye1Scale, eye2Scale
        f.eye1ForceCircle, f.eye2ForceCircle = eye1ForceCircle, eye2ForceCircle

        f.e1cx = f.e1x + EYE_W / 2; f.e1cy = f.e1y + EYE_H / 2
        f.e2cx = f.e2x + EYE_W / 2; f.e2cy = f.e2y + EYE_H / 2

        f.feedBall = None
        if self.miniState == MF_FEED_HAPPY and self.feedPhase == 0:
            f.feedBall = ((f.e1cx + f.e2cx) / 2, EYE_BASE_Y + EYE_H / 2 + self.feedBallY)

        eyeColor = NEON_BLUE
        if self.miniState == MF_FEED_HAPPY and self.feedPhase == 1 and self.feedFlashOn: eyeColor = LEMON_YELLOW
        if self.reactionActive: eyeColor = REACT_RED if self.reactionPhase == REACT_WAITING else REACT_GREEN
        f.eyeColor = eyeColor

        f.sync = self.syncActive
        f.syncLeft, f.syncRight = self.syncShapeLeft, self.syncShapeRight

        f.particles = []
        if self.miniState == MF_EXPLODE and self.explodePhase >= 1:
            f.particles = [(p.x, p.y) for p in self.particles if p.active]

        f.info = None
        if self.miniState == MF_INFO_TIME and self.infoPhase == 1:
            f.info = ("time", "%02d:%02d" % (self.currentHour, self.currentMinute),
                      "%s %d." % (hungarianMonths[self.currentMonth - 1], self.currentDay))
        elif self.miniState == MF_INFO_WEATHER and self.infoPhase == 1:
            temp = "--.-C" if math.isnan(self.lastTemperature) else "%.1f°C" % self.lastTemperature
            f.info = ("weather", CITY_NAME, temp, weatherCodeToHungarian(self.lastWeatherCode))
        elif self.miniState == MF_INFO_KIND and self.infoPhase == 1:
            f.info = ("kind", self.infoKindMessage)

        f.thought = (thoughtDots if showThoughtBubble else None)
        f.dream = (dreamIconToShow if showDreamBubble else None)
        f.zzz = (zzzCount if showZZZ else None)

        f.bottom = None
        if now < self.gameMessageUntil and self.gameMessage:
            f.bottom = self.gameMessage
        elif now < self.menuMessageUntil:
            f.bottom = self.menuMessage

        f.clipToBox = clipToBox
        f.paused = False
        return f
