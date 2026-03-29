"""
Vision Agent — pixel-based desktop automation agent.
Perceives the screen via screenshots, reasons via multimodal LLM, acts via mouse/keyboard.
"""

from agents.vision_agent.loop import VisionAgent

__all__ = ["VisionAgent"]
