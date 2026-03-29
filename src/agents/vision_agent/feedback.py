"""
Feedback Loop — post-action verification via screenshot comparison and VLM confirmation.
The most critical differentiator for reliable vision agents.
"""

import json
import time
from typing import Optional
from PIL import Image, ImageChops, ImageStat


class VerificationResult:
    """Result of a post-action verification."""

    def __init__(
        self,
        success: bool,
        confidence: float,
        evidence: str,
        screen_changed: bool,
        should_retry: bool = False,
    ):
        self.success = success
        self.confidence = confidence
        self.evidence = evidence
        self.screen_changed = screen_changed
        self.should_retry = should_retry

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "screen_changed": self.screen_changed,
            "should_retry": self.should_retry,
        }


class FeedbackLoop:
    """
    Verifies whether an action succeeded by comparing before/after screenshots
    and optionally asking the VLM to confirm.
    """

    def __init__(
        self,
        brain=None,
        pixel_change_threshold: float = 0.5,
        vlm_verify: bool = True,
    ):
        """
        Args:
            brain: VisionBrain instance for VLM-based verification
            pixel_change_threshold: Minimum % pixel difference to count as "changed"
            vlm_verify: Whether to use VLM for verification (costs API calls)
        """
        self.brain = brain
        self.pixel_change_threshold = pixel_change_threshold
        self.vlm_verify = vlm_verify and brain is not None

    def verify_action(
        self,
        before_img: Image.Image,
        after_img: Image.Image,
        action: dict,
        before_b64: Optional[str] = None,
        after_b64: Optional[str] = None,
    ) -> VerificationResult:
        """
        Verify whether an action succeeded.

        Args:
            before_img: Screenshot before action (PIL Image)
            after_img: Screenshot after action (PIL Image)
            action: The action that was executed
            before_b64: Pre-computed base64 of before screenshot
            after_b64: Pre-computed base64 of after screenshot

        Returns:
            VerificationResult
        """
        action_type = action.get("action", "")

        # --- Pixel-level change detection ---
        change_pct = self._compute_pixel_diff(before_img, after_img)
        screen_changed = change_pct > self.pixel_change_threshold

        # For wait actions, success is always true
        if action_type == "wait":
            return VerificationResult(
                success=True,
                confidence=1.0,
                evidence=f"Waited {action.get('seconds', 2)}s",
                screen_changed=screen_changed,
            )

        # For type/hotkey, screen change is expected
        if action_type in ("type", "hotkey"):
            success = screen_changed
            return VerificationResult(
                success=success,
                confidence=0.7 if success else 0.4,
                evidence=f"Screen {'changed' if success else 'unchanged'} after {action_type} ({change_pct:.1f}% diff)",
                screen_changed=screen_changed,
                should_retry=not success,
            )

        # For click/double_click, expect screen change
        if action_type in ("click", "double_click", "right_click"):
            if not screen_changed:
                return VerificationResult(
                    success=False,
                    confidence=0.6,
                    evidence=f"Screen unchanged after {action_type} ({change_pct:.1f}% diff) — click may have missed",
                    screen_changed=False,
                    should_retry=True,
                )

        # --- VLM Verification (if enabled and we have screenshots) ---
        if self.vlm_verify and before_b64 and after_b64:
            try:
                vlm_result = self._vlm_verify(
                    before_b64, after_b64, action
                )
                return vlm_result
            except Exception as e:
                # Fallback to pixel-based if VLM fails
                pass

        # --- Fallback: pixel-based heuristic ---
        if screen_changed:
            return VerificationResult(
                success=True,
                confidence=0.6,
                evidence=f"Screen changed ({change_pct:.1f}% diff) — action likely succeeded",
                screen_changed=True,
            )
        else:
            return VerificationResult(
                success=False,
                confidence=0.5,
                evidence=f"No visible change ({change_pct:.1f}% diff)",
                screen_changed=False,
                should_retry=True,
            )

    def _compute_pixel_diff(self, img1: Image.Image, img2: Image.Image) -> float:
        """
        Compute the percentage of pixels that changed between two images.

        Returns:
            Percentage (0-100) of changed pixels
        """
        try:
            # Ensure same size
            if img1.size != img2.size:
                img2 = img2.resize(img1.size, Image.LANCZOS)

            # Convert to same mode
            img1 = img1.convert("RGB")
            img2 = img2.convert("RGB")

            # Compute difference
            diff = ImageChops.difference(img1, img2)
            stat = ImageStat.Stat(diff)

            # Average difference across RGB channels (0-255)
            avg_diff = sum(stat.mean) / 3.0

            # Convert to percentage (anything > 5 in avg is significant)
            return (avg_diff / 255.0) * 100.0

        except Exception:
            return 0.0

    def _vlm_verify(
        self, before_b64: str, after_b64: str, action: dict
    ) -> VerificationResult:
        """Verify action via VLM before/after comparison."""
        action_type = action.get("action", "unknown")
        target = action.get("target", "element")
        desc = f"{action_type} on '{target}'"

        response = self.brain.verify(
            before_b64=before_b64,
            after_b64=after_b64,
            action_description=desc,
        )

        # Parse VLM verification response
        try:
            # Try to extract JSON
            start = response.find("{")
            end = response.rfind("}") + 1
            if start != -1 and end > 0:
                data = json.loads(response[start:end])
                return VerificationResult(
                    success=data.get("success", False),
                    confidence=float(data.get("confidence", 0.5)),
                    evidence=data.get("evidence", "VLM verification"),
                    screen_changed=data.get("screen_changed", False),
                    should_retry=not data.get("success", False),
                )
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

        # Fallback if VLM response is unparseable
        return VerificationResult(
            success=True,
            confidence=0.4,
            evidence="VLM verification response unparseable — assuming success",
            screen_changed=True,
        )
