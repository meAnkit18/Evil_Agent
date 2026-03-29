"""
Spatial Memory — tracks known UI element locations across frames.
Percentage-based coordinate normalization for resolution independence.
"""

import time
from typing import Dict, Optional, Tuple, List


class SpatialMemory:
    """
    Remembers where UI elements were last seen on screen.
    Uses percentage-based normalization to handle resolution changes.
    """

    def __init__(
        self,
        screen_width: int = 1920,
        screen_height: int = 1080,
        stale_threshold: float = 10.0,
    ):
        """
        Args:
            screen_width: Current screen width in pixels
            screen_height: Current screen height in pixels
            stale_threshold: Seconds before an entry is considered stale
        """
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.stale_threshold = stale_threshold

        # element_name -> location data
        self._elements: Dict[str, dict] = {}

    def record(
        self,
        name: str,
        bbox: Tuple[int, int, int, int],
        confidence: float = 1.0,
    ):
        """
        Record or update a UI element's location.

        Args:
            name: Element name/label (e.g., "Downloads folder", "Chrome icon")
            bbox: (x1, y1, x2, y2) in pixel coordinates
            confidence: Detection confidence
        """
        x1, y1, x2, y2 = bbox

        # Normalize to percentages (0.0 - 1.0)
        norm_bbox = (
            x1 / self.screen_width,
            y1 / self.screen_height,
            x2 / self.screen_width,
            y2 / self.screen_height,
        )

        key = name.lower().strip()

        if key in self._elements:
            self._elements[key]["bbox_px"] = bbox
            self._elements[key]["bbox_norm"] = norm_bbox
            self._elements[key]["confidence"] = confidence
            self._elements[key]["last_seen"] = time.time()
            self._elements[key]["seen_count"] += 1
        else:
            self._elements[key] = {
                "name": name,
                "bbox_px": bbox,
                "bbox_norm": norm_bbox,
                "confidence": confidence,
                "last_seen": time.time(),
                "seen_count": 1,
            }

    def lookup(self, name: str) -> Optional[dict]:
        """
        Look up a known element by name.

        Returns:
            Element dict with denormalized pixel coords, or None
        """
        key = name.lower().strip()
        entry = self._elements.get(key)

        if entry is None:
            return None

        # Check staleness
        age = time.time() - entry["last_seen"]
        is_stale = age > self.stale_threshold

        # Denormalize to current screen resolution
        nx1, ny1, nx2, ny2 = entry["bbox_norm"]
        current_bbox = (
            int(nx1 * self.screen_width),
            int(ny1 * self.screen_height),
            int(nx2 * self.screen_width),
            int(ny2 * self.screen_height),
        )

        return {
            "name": entry["name"],
            "bbox": current_bbox,
            "center": (
                (current_bbox[0] + current_bbox[2]) // 2,
                (current_bbox[1] + current_bbox[3]) // 2,
            ),
            "confidence": entry["confidence"],
            "age": age,
            "stale": is_stale,
            "seen_count": entry["seen_count"],
        }

    def update_resolution(self, width: int, height: int):
        """Update screen resolution (coordinates auto-adjust via normalization)."""
        self.screen_width = width
        self.screen_height = height

    def get_all_fresh(self) -> List[dict]:
        """Get all non-stale elements."""
        now = time.time()
        results = []
        for key, entry in self._elements.items():
            if now - entry["last_seen"] <= self.stale_threshold:
                results.append(self.lookup(entry["name"]))
        return results

    def format_for_llm(self) -> str:
        """Format known element locations for LLM context."""
        fresh = self.get_all_fresh()
        if not fresh:
            return ""

        lines = ["Known element locations:"]
        for elem in fresh:
            x, y = elem["center"]
            lines.append(
                f"  - \"{elem['name']}\" at ({x},{y}) "
                f"[seen {elem['seen_count']}x, {elem['age']:.1f}s ago]"
            )
        return "\n".join(lines)

    def clear(self):
        """Clear all spatial memory."""
        self._elements.clear()
