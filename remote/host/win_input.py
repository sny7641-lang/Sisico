"""Windows 마우스·키보드 입력 주입 (SendInput) 과 클립보드.

윈도우가 아닌 곳에서는 아무것도 하지 않는 대체 구현을 씁니다 (테스트용).
"""
import sys

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
    MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP = 0x0008, 0x0010
    MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP = 0x0020, 0x0040
    MOUSEEVENTF_WHEEL, MOUSEEVENTF_HWHEEL = 0x0800, 0x1000
    MOUSEEVENTF_VIRTUALDESK, MOUSEEVENTF_ABSOLUTE = 0x4000, 0x8000
    KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP, KEYEVENTF_UNICODE = 0x0001, 0x0002, 0x0004
    SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN, SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 76, 77, 78, 79

    ULONG_PTR = ctypes.c_size_t

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]

    class _INPUTUNION(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _anonymous_ = ("u",)
        _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]

    user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
    user32.GetCursorPos.argtypes = (ctypes.POINTER(wintypes.POINT),)
    user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
    user32.MapVirtualKeyW.restype = wintypes.UINT

    # 확장 키 플래그가 필요한 가상 키 (방향키, Home/End, Ins/Del, PgUp/PgDn, 오른쪽 Ctrl/Alt, Win, 앱 키 등)
    EXTENDED_VKS = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E,
                    0x5B, 0x5C, 0x5D, 0xA3, 0xA5, 0x6F, 0x90, 0x2C}

    def _send(*inputs):
        arr = (INPUT * len(inputs))(*inputs)
        user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))

    def _mouse(flags, dx=0, dy=0, data=0):
        i = INPUT(type=INPUT_MOUSE)
        i.mi = MOUSEINPUT(dx, dy, data & 0xFFFFFFFF, flags, 0, 0)
        return i

    def _key(vk=0, scan=0, flags=0):
        i = INPUT(type=INPUT_KEYBOARD)
        i.ki = KEYBDINPUT(vk, scan, flags, 0, 0)
        return i

    def set_dpi_aware():
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                user32.SetProcessDPIAware()
            except Exception:
                pass

    def keep_awake(on: bool):
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED, ES_DISPLAY_REQUIRED = 0x80000000, 0x1, 0x2
        flags = ES_CONTINUOUS | (ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED if on else 0)
        kernel32.SetThreadExecutionState(flags)

    def virtual_screen():
        g = user32.GetSystemMetrics
        return (g(SM_XVIRTUALSCREEN), g(SM_YVIRTUALSCREEN),
                g(SM_CXVIRTUALSCREEN), g(SM_CYVIRTUALSCREEN))

    def cursor_pos():
        p = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(p))
        return p.x, p.y

    def move_abs(x, y):
        """가상 데스크톱 좌표(픽셀)로 커서 이동."""
        vx, vy, vw, vh = virtual_screen()
        x = min(max(x, vx), vx + vw - 1)
        y = min(max(y, vy), vy + vh - 1)
        nx = int(round((x - vx) * 65535 / max(vw - 1, 1)))
        ny = int(round((y - vy) * 65535 / max(vh - 1, 1)))
        _send(_mouse(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK, nx, ny))

    def move_rel(dx, dy):
        x, y = cursor_pos()
        move_abs(x + dx, y + dy)

    _BTN = {"left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
            "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
            "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP)}

    def button(name, down):
        d, u = _BTN.get(name, _BTN["left"])
        _send(_mouse(d if down else u))

    def wheel(dy=0, dx=0):
        if dy:
            _send(_mouse(MOUSEEVENTF_WHEEL, data=int(dy)))
        if dx:
            _send(_mouse(MOUSEEVENTF_HWHEEL, data=int(dx)))

    def key(vk, down):
        vk = int(vk) & 0xFF
        flags = 0 if down else KEYEVENTF_KEYUP
        if vk in EXTENDED_VKS:
            flags |= KEYEVENTF_EXTENDEDKEY
        _send(_key(vk, user32.MapVirtualKeyW(vk, 0), flags))

    def text(s):
        ins = []
        for ch in s:
            if ch == "\n":
                ins += [_key(0x0D, 0, 0), _key(0x0D, 0, KEYEVENTF_KEYUP)]
                continue
            data = ch.encode("utf-16-le")
            for k in range(0, len(data), 2):
                cu = int.from_bytes(data[k:k + 2], "little")
                ins += [_key(0, cu, KEYEVENTF_UNICODE), _key(0, cu, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)]
        if ins:
            _send(*ins)

    # ---- 클립보드 (유니코드 텍스트) ----
    CF_UNICODETEXT, GMEM_MOVEABLE = 13, 0x0002
    kernel32.GlobalAlloc.argtypes = (wintypes.UINT, ctypes.c_size_t)
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = (wintypes.HGLOBAL,)
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalUnlock.argtypes = (wintypes.HGLOBAL,)
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.SetClipboardData.argtypes = (wintypes.UINT, wintypes.HANDLE)
    user32.SetClipboardData.restype = wintypes.HANDLE

    def clipboard_get():
        if not user32.OpenClipboard(None):
            return ""
        try:
            h = user32.GetClipboardData(CF_UNICODETEXT)
            if not h:
                return ""
            p = kernel32.GlobalLock(h)
            try:
                return ctypes.wstring_at(p)
            finally:
                kernel32.GlobalUnlock(h)
        finally:
            user32.CloseClipboard()

    def clipboard_set(s):
        data = s.encode("utf-16-le") + b"\x00\x00"
        if not user32.OpenClipboard(None):
            return False
        try:
            user32.EmptyClipboard()
            h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
            p = kernel32.GlobalLock(h)
            ctypes.memmove(p, data, len(data))
            kernel32.GlobalUnlock(h)
            user32.SetClipboardData(CF_UNICODETEXT, h)
            return True
        finally:
            user32.CloseClipboard()

else:  # 윈도우가 아닌 환경: 테스트용 대체 구현
    _pos = [0, 0]
    _clip = [""]
    log = []

    def set_dpi_aware(): pass
    def keep_awake(on): pass
    def virtual_screen(): return (0, 0, 1920, 1080)
    def cursor_pos(): return tuple(_pos)

    def move_abs(x, y):
        _pos[:] = [int(x), int(y)]; log.append(("move", int(x), int(y)))

    def move_rel(dx, dy): move_abs(_pos[0] + dx, _pos[1] + dy)
    def button(name, down): log.append(("button", name, down))
    def wheel(dy=0, dx=0): log.append(("wheel", dy, dx))
    def key(vk, down): log.append(("key", vk, down))
    def text(s): log.append(("text", s))
    def clipboard_get(): return _clip[0]

    def clipboard_set(s):
        _clip[0] = s
        return True
