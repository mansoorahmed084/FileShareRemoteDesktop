"""Input injection — translate remote mouse/keyboard events into OS-level input.

Windows: uses ctypes + SendInput (fastest, no extra deps).
Fallback: pynput (cross-platform).
"""

import ctypes
import ctypes.wintypes
import sys

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

WHEEL_DELTA = 120


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.wintypes.LONG),
        ("dy", ctypes.wintypes.LONG),
        ("mouseData", ctypes.wintypes.DWORD),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.wintypes.WORD),
        ("wScan", ctypes.wintypes.WORD),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.wintypes.DWORD), ("union", _INPUT_UNION)]


class Win32InputInjector:
    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self._user32 = ctypes.windll.user32

    def handle(self, msg: dict):
        msg_type = msg.get("type", "")
        if msg_type == "mouse_move":
            self._mouse_move(msg["x"], msg["y"])
        elif msg_type == "mouse_down":
            self._mouse_button(msg.get("button", "left"), down=True)
        elif msg_type == "mouse_up":
            self._mouse_button(msg.get("button", "left"), down=False)
        elif msg_type == "mouse_scroll":
            self._mouse_scroll(msg.get("dx", 0), msg.get("dy", 0))
        elif msg_type == "key_down":
            self._key_event(msg, down=True)
        elif msg_type == "key_up":
            self._key_event(msg, down=False)

    def _mouse_move(self, x_norm: float, y_norm: float):
        x = int(x_norm * 65535)
        y = int(y_norm * 65535)
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.union.mi.dx = x
        inp.union.mi.dy = y
        inp.union.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE
        self._send_input(inp)

    def _mouse_button(self, button: str, down: bool):
        flags = {
            "left": MOUSEEVENTF_LEFTDOWN if down else MOUSEEVENTF_LEFTUP,
            "right": MOUSEEVENTF_RIGHTDOWN if down else MOUSEEVENTF_RIGHTUP,
            "middle": MOUSEEVENTF_MIDDLEDOWN if down else MOUSEEVENTF_MIDDLEUP,
        }
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.union.mi.dwFlags = flags.get(button, MOUSEEVENTF_LEFTDOWN if down else MOUSEEVENTF_LEFTUP)
        self._send_input(inp)

    def _mouse_scroll(self, dx: int, dy: int):
        if dy != 0:
            inp = INPUT()
            inp.type = INPUT_MOUSE
            inp.union.mi.dwFlags = MOUSEEVENTF_WHEEL
            inp.union.mi.mouseData = ctypes.wintypes.DWORD(dy * WHEEL_DELTA)
            self._send_input(inp)

    def _key_event(self, msg: dict, down: bool):
        vk = msg.get("vk", 0)
        char = msg.get("char", "")
        flags = 0 if down else KEYEVENTF_KEYUP

        if vk:
            inp = INPUT()
            inp.type = INPUT_KEYBOARD
            inp.union.ki.wVk = vk
            inp.union.ki.dwFlags = flags
            self._send_input(inp)
        elif char and down:
            inp = INPUT()
            inp.type = INPUT_KEYBOARD
            inp.union.ki.wVk = 0
            inp.union.ki.wScan = ord(char)
            inp.union.ki.dwFlags = KEYEVENTF_UNICODE
            self._send_input(inp)

    def _send_input(self, inp: INPUT):
        self._user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


class PynputInputInjector:
    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        from pynput.mouse import Controller as MouseController
        from pynput.keyboard import Controller as KeyController, Key
        self._mouse = MouseController()
        self._keyboard = KeyController()
        self._Key = Key

    def handle(self, msg: dict):
        msg_type = msg.get("type", "")
        if msg_type == "mouse_move":
            x = int(msg["x"] * self.screen_width)
            y = int(msg["y"] * self.screen_height)
            self._mouse.position = (x, y)
        elif msg_type == "mouse_down":
            from pynput.mouse import Button
            btn = getattr(Button, msg.get("button", "left"), Button.left)
            self._mouse.press(btn)
        elif msg_type == "mouse_up":
            from pynput.mouse import Button
            btn = getattr(Button, msg.get("button", "left"), Button.left)
            self._mouse.release(btn)
        elif msg_type == "mouse_scroll":
            self._mouse.scroll(msg.get("dx", 0), msg.get("dy", 0))
        elif msg_type == "key_down":
            self._handle_key(msg, press=True)
        elif msg_type == "key_up":
            self._handle_key(msg, press=False)

    def _handle_key(self, msg: dict, press: bool):
        char = msg.get("char", "")
        vk = msg.get("vk", 0)
        if char and len(char) == 1:
            if press:
                self._keyboard.press(char)
            else:
                self._keyboard.release(char)
        elif vk:
            from pynput.keyboard import KeyCode
            key = KeyCode.from_vk(vk)
            if press:
                self._keyboard.press(key)
            else:
                self._keyboard.release(key)


def create_injector(screen_width: int, screen_height: int):
    if sys.platform == "win32":
        return Win32InputInjector(screen_width, screen_height)
    try:
        return PynputInputInjector(screen_width, screen_height)
    except ImportError:
        print("  Warning: pynput not installed — remote input disabled")
        return _NoOpInjector()


class _NoOpInjector:
    def handle(self, msg: dict):
        pass
