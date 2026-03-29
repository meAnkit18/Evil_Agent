"""
Screen Capture — high-performance screenshot capture using mss.
Supports full screen, region capture, multi-monitor, and base64 encoding for VLM APIs.
"""

import base64
import io
import time
from typing import Optional, Tuple, List

import mss
import mss.tools
from PIL import Image


class ScreenCapture:
    """
    High-performance screen capture engine.
    Uses mss for 10x faster captures than pyautogui.screenshot().
    """

    def __init__(
        self,
        monitor: int = 0,
        max_width: int = 1920,
        max_height: int = 1080,
        jpeg_quality: int = 75,
        min_interval: float = 0.2,
    ):
        """
        Args:
            monitor: Monitor index (0 = all monitors combined, 1 = primary, 2+ = others)
            max_width: Max resolution width (downscale if larger, saves API costs)
            max_height: Max resolution height
            jpeg_quality: JPEG compression quality (1-100, lower = smaller payload)
            min_interval: Minimum seconds between captures (FPS limiter)
        """
        self.monitor = monitor
        self.max_width = max_width
        self.max_height = max_height
        self.jpeg_quality = jpeg_quality
        self.min_interval = min_interval
        self._last_capture_time = 0.0
        self._sct = None

    def _get_sct(self) -> mss.mss:
        """Lazy-initialize mss instance."""
        if self._sct is None:
            self._sct = mss.mss()
        return self._sct

    @property
    def screen_size(self) -> Tuple[int, int]:
        """Get the dimensions of the target monitor."""
        sct = self._get_sct()
        mon = sct.monitors[self.monitor]
        return mon["width"], mon["height"]

    @property
    def available_monitors(self) -> List[dict]:
        """List all available monitors with their geometry."""
        sct = self._get_sct()
        return [
            {
                "index": i,
                "left": m["left"],
                "top": m["top"],
                "width": m["width"],
                "height": m["height"],
            }
            for i, m in enumerate(sct.monitors)
        ]

    def capture_full(self) -> Image.Image:
        """
        Capture the full screen (or selected monitor).
        Respects FPS limiter and downscales if needed.
        """
        self._throttle()

        sct = self._get_sct()
        mon = sct.monitors[self.monitor]
        raw = sct.grab(mon)

        # Convert to PIL Image (mss returns BGRA, PIL expects RGB)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

        # Downscale if too large
        img = self._fit_resolution(img)

        self._last_capture_time = time.time()
        return img

    def capture_region(self, bbox: Tuple[int, int, int, int]) -> Image.Image:
        """
        Capture a specific screen region.

        Args:
            bbox: (x1, y1, x2, y2) in absolute screen coordinates
        """
        self._throttle()

        x1, y1, x2, y2 = bbox
        region = {
            "left": x1,
            "top": y1,
            "width": x2 - x1,
            "height": y2 - y1,
        }

        sct = self._get_sct()
        raw = sct.grab(region)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

        self._last_capture_time = time.time()
        return img

    def to_base64(self, image: Image.Image, quality: Optional[int] = None) -> str:
        """
        Convert PIL Image to JPEG base64 string for VLM API.

        Args:
            image: PIL Image
            quality: Override JPEG quality (1-100)

        Returns:
            Base64-encoded JPEG string
        """
        q = quality or self.jpeg_quality
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=q)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def capture_and_encode(self) -> Tuple[str, Tuple[int, int]]:
        """
        Convenience: capture full screen and return (base64_str, (width, height)).
        """
        img = self.capture_full()
        b64 = self.to_base64(img)
        return b64, img.size

    def _fit_resolution(self, img: Image.Image) -> Image.Image:
        """Downscale image to fit within max_width x max_height while preserving aspect ratio."""
        w, h = img.size
        if w <= self.max_width and h <= self.max_height:
            return img

        scale = min(self.max_width / w, self.max_height / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        return img.resize((new_w, new_h), Image.LANCZOS)

    def _throttle(self):
        """Enforce minimum interval between captures."""
        elapsed = time.time() - self._last_capture_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)

    def close(self):
        """Release mss resources."""
        if self._sct:
            self._sct.close()
            self._sct = None
