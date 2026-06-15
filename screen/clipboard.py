"""Clipboard sync — detect changes and exchange clipboard content between machines.

Windows: uses win32clipboard for reading/writing + polling for change detection.
Fallback: pyperclip (cross-platform).
"""

import asyncio
import sys
import time


class ClipboardSync:
    def __init__(self):
        self._last_content: str | None = None
        self._last_check = 0.0
        self._suppressed: str | None = None
        self._impl = _Win32Clipboard() if sys.platform == "win32" else _PyperclipClipboard()

    def poll_change_sync(self) -> str | None:
        now = time.time()
        if now - self._last_check < 0.5:
            return None
        self._last_check = now
        try:
            content = self._impl.read()
        except Exception:
            return None
        if content and content != self._last_content and content != self._suppressed:
            self._last_content = content
            return content
        return None

    async def poll_change(self) -> str | None:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.poll_change_sync)

    def receive(self, content: str):
        if not content:
            return
        self._suppressed = content
        self._last_content = content
        try:
            self._impl.write(content)
        except Exception:
            pass

    def stop(self):
        pass


class _Win32Clipboard:
    def read(self) -> str | None:
        import ctypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        CF_UNICODETEXT = 13

        if not user32.OpenClipboard(0):
            return None
        try:
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return None
            ptr = kernel32.GlobalLock(handle)
            if not ptr:
                return None
            try:
                return ctypes.wstring_at(ptr)
            finally:
                kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()

    def write(self, text: str):
        import ctypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002

        data = text.encode("utf-16-le") + b"\x00\x00"
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not h:
            return
        ptr = kernel32.GlobalLock(h)
        if not ptr:
            kernel32.GlobalFree(h)
            return
        ctypes.memmove(ptr, data, len(data))
        kernel32.GlobalUnlock(h)

        if not user32.OpenClipboard(0):
            kernel32.GlobalFree(h)
            return
        try:
            user32.EmptyClipboard()
            user32.SetClipboardData(CF_UNICODETEXT, h)
        finally:
            user32.CloseClipboard()


class _PyperclipClipboard:
    def __init__(self):
        try:
            import pyperclip
            self._pyperclip = pyperclip
        except ImportError:
            self._pyperclip = None

    def read(self) -> str | None:
        if self._pyperclip:
            try:
                return self._pyperclip.paste()
            except Exception:
                return None
        return None

    def write(self, text: str):
        if self._pyperclip:
            try:
                self._pyperclip.copy(text)
            except Exception:
                pass
