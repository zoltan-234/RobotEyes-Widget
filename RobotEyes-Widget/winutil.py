# -*- coding: utf-8 -*-
"""
Windows-specifikus segedek (ctypes):
  - idle_seconds():            mennyi ideje nem nyultal egerhez/billentyuzethez
  - set_click_through(hwnd,b): az ablak atengedje-e a kattintast
  - fullscreen_on_my_monitor(hwnd): ugyanazon a monitoron fut-e teljes kepernyos app
Mas rendszeren biztonsagos "semmit nem csinalo" valtozatok futnak.
"""
import sys
import time

IS_WIN = sys.platform.startswith("win")

if IS_WIN:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

    GWL_EXSTYLE = -20
    WS_EX_TRANSPARENT = 0x00000020
    WS_EX_LAYERED = 0x00080000
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_NOACTIVATE = 0x08000000
    MONITOR_DEFAULTTONEAREST = 2

    if ctypes.sizeof(ctypes.c_void_p) == 8:
        _GetWindowLong = user32.GetWindowLongPtrW
        _SetWindowLong = user32.SetWindowLongPtrW
        _GetWindowLong.restype = ctypes.c_longlong
        _GetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int]
        _SetWindowLong.restype = ctypes.c_longlong
        _SetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_longlong]
    else:
        _GetWindowLong = user32.GetWindowLongW
        _SetWindowLong = user32.SetWindowLongW

    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.MonitorFromWindow.restype = wintypes.HMONITOR
    user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetAncestor.restype = wintypes.HWND
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]

    _IGNORED_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
                        "Windows.UI.Core.CoreWindow", "XamlExplorerHostIslandWindow"}

    def idle_seconds():
        lii = LASTINPUTINFO(); lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not user32.GetLastInputInfo(ctypes.byref(lii)):
            return 0.0
        tick = kernel32.GetTickCount() & 0xFFFFFFFF
        return ((tick - lii.dwTime) & 0xFFFFFFFF) / 1000.0

    _ct_state = {}

    def set_click_through(hwnd, enabled):
        hwnd = int(hwnd)
        if _ct_state.get(hwnd) == enabled:
            return
        ex = _GetWindowLong(hwnd, GWL_EXSTYLE)
        if enabled:
            ex |= WS_EX_TRANSPARENT | WS_EX_LAYERED
        else:
            ex &= ~WS_EX_TRANSPARENT
        ex |= WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        _SetWindowLong(hwnd, GWL_EXSTYLE, ex)
        _ct_state[hwnd] = enabled

    def reset_click_through_cache(hwnd):
        _ct_state.pop(int(hwnd), None)

    def _class_name(hwnd):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf, 256)
        return buf.value

    def fullscreen_on_my_monitor(my_hwnd):
        """True, ha az elotérben levo ablak teljes kepernyos, es ugyanazon a monitoron van, mint mi."""
        fg = user32.GetForegroundWindow()
        if not fg:
            return False
        my_hwnd = int(my_hwnd)
        root = user32.GetAncestor(fg, 2)  # GA_ROOT
        if root: fg = root
        if int(fg) == my_hwnd:
            return False
        if _class_name(fg) in _IGNORED_CLASSES:
            return False
        mon_fg = user32.MonitorFromWindow(fg, MONITOR_DEFAULTTONEAREST)
        mon_me = user32.MonitorFromWindow(my_hwnd, MONITOR_DEFAULTTONEAREST)
        if not mon_fg or mon_fg != mon_me:
            return False
        mi = MONITORINFO(); mi.cbSize = ctypes.sizeof(MONITORINFO)
        if not user32.GetMonitorInfoW(mon_fg, ctypes.byref(mi)):
            return False
        r = wintypes.RECT()
        if not user32.GetWindowRect(fg, ctypes.byref(r)):
            return False
        m = mi.rcMonitor
        return r.left <= m.left and r.top <= m.top and r.right >= m.right and r.bottom >= m.bottom

    def mouse_button_down():
        """Le van-e nyomva most barmelyik egergomb (bal / jobb / kozepso)."""
        for vk in (0x01, 0x02, 0x04):
            if user32.GetAsyncKeyState(vk) & 0x8000:
                return True
        return False

    def enable_dpi_awareness():
        # Qt6 alapbol per-monitor DPI aware; ez csak biztonsagi tartalek
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass

else:
    _last_pos = [None, time.monotonic()]

    def idle_seconds(cursor_pos=None):
        if cursor_pos is not None:
            if cursor_pos != _last_pos[0]:
                _last_pos[0] = cursor_pos; _last_pos[1] = time.monotonic()
        return time.monotonic() - _last_pos[1]

    def set_click_through(hwnd, enabled):
        pass

    def reset_click_through_cache(hwnd):
        pass

    def fullscreen_on_my_monitor(my_hwnd):
        return False

    def mouse_button_down():
        from PySide6.QtWidgets import QApplication
        return QApplication.mouseButtons() != 0

    def enable_dpi_awareness():
        pass
