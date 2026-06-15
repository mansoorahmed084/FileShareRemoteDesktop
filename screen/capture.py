"""Screen capture backends — dxcam (fast, Windows) with mss fallback."""

import asyncio
import numpy as np

try:
    import dxcam

    _HAS_DXCAM = True
except ImportError:
    _HAS_DXCAM = False

import mss


class MSSCapture:
    def __init__(self, monitor: int = 0):
        self._sct = mss.mss()
        self._mon = self._sct.monitors[monitor + 1]

    @property
    def width(self) -> int:
        return self._mon["width"]

    @property
    def height(self) -> int:
        return self._mon["height"]

    def grab(self) -> np.ndarray:
        img = self._sct.grab(self._mon)
        frame = np.array(img, dtype=np.uint8)[:, :, :3]
        return frame

    def close(self):
        self._sct.close()


class DXCamCapture:
    def __init__(self, monitor: int = 0):
        self._cam = dxcam.create(output_idx=monitor, output_color="BGR")
        self._width = self._cam.width
        self._height = self._cam.height

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    def grab(self) -> np.ndarray:
        frame = self._cam.grab()
        if frame is None:
            frame = self._cam.grab()
        if frame is None:
            return np.zeros((self._height, self._width, 3), dtype=np.uint8)
        return frame

    def close(self):
        try:
            del self._cam
        except Exception:
            pass


def create_capture(monitor: int = 0, prefer_dxcam: bool = True):
    if prefer_dxcam and _HAS_DXCAM:
        try:
            cap = DXCamCapture(monitor)
            print(f"  Using dxcam (DXGI) capture — {cap.width}x{cap.height}")
            return cap
        except Exception as e:
            print(f"  dxcam failed ({e}), falling back to mss")
    cap = MSSCapture(monitor)
    print(f"  Using mss capture — {cap.width}x{cap.height}")
    return cap


def list_monitors() -> list[dict]:
    sct = mss.mss()
    monitors = []
    for i, mon in enumerate(sct.monitors[1:], start=0):
        monitors.append({
            "index": i,
            "width": mon["width"],
            "height": mon["height"],
            "left": mon["left"],
            "top": mon["top"],
            "primary": i == 0,
        })
    sct.close()
    return monitors


async def grab_async(capture) -> np.ndarray:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, capture.grab)
