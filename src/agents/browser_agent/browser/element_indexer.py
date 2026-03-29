"""
Element Indexer — assigns stable integer IDs to extracted DOM elements.
Stores internal selector data (never exposed to LLM).
Formats a human-readable element list for LLM consumption.
"""

from typing import Optional


class IndexedElement:
    """An element with an assigned integer ID for LLM reference."""

    __slots__ = [
        "id", "tag", "type", "role", "text", "label",
        "href", "placeholder", "position", "css_selector", "rect"
    ]

    def __init__(self, id: int, raw: dict):
        self.id = id
        self.tag = raw.get("tag", "")
        self.type = raw.get("type", "")
        self.role = raw.get("role", "")
        self.text = raw.get("text", "")
        self.label = raw.get("label", "")
        self.href = raw.get("href", "")
        self.placeholder = raw.get("placeholder", "")
        self.position = raw.get("position", "")
        self.css_selector = raw.get("cssSelector", "")
        self.rect = raw.get("rect", {})

    @property
    def display_type(self) -> str:
        """Human-readable element type for LLM display."""
        if self.role:
            return self.role
        if self.tag == "a":
            return "link"
        if self.tag == "button":
            return "button"
        if self.tag == "input":
            input_type = self.type or "text"
            return f"input ({input_type})"
        if self.tag == "textarea":
            return "textarea"
        if self.tag == "select":
            return "dropdown"
        return self.tag

    @property
    def display_text(self) -> str:
        """Best available display text."""
        return self.label or self.text or self.placeholder or "(no label)"

    def format_for_llm(self) -> str:
        """Format as a single line for LLM: [id] type: "text" (position)"""
        parts = [f"[{self.id}]", f"{self.display_type}:", f'"{self.display_text}"']

        if self.href and self.tag == "a":
            # Show truncated href for links
            href_display = self.href[:60] + ("..." if len(self.href) > 60 else "")
            parts.append(f"→ {href_display}")

        if self.placeholder and self.tag in ("input", "textarea"):
            parts.append(f'(placeholder: "{self.placeholder}")')

        if self.position:
            parts.append(f"({self.position})")

        return " ".join(parts)


class ElementIndexer:
    """
    Takes raw elements from DOMProcessor and assigns integer IDs.
    Maintains the mapping from ID -> selector (internal only).
    """

    def __init__(self):
        self._indexed: list[IndexedElement] = []
        self._id_map: dict[int, IndexedElement] = {}

    def index(self, raw_elements: list[dict]) -> list[IndexedElement]:
        """
        Assign sequential IDs to elements.
        Call this after every DOM extraction (IDs reset each time).
        """
        self._indexed = []
        self._id_map = {}

        for i, raw in enumerate(raw_elements, start=1):
            elem = IndexedElement(id=i, raw=raw)
            self._indexed.append(elem)
            self._id_map[i] = elem

        return self._indexed

    def get_by_id(self, element_id: int) -> Optional[IndexedElement]:
        """Look up an indexed element by its ID."""
        return self._id_map.get(element_id)

    def get_selector(self, element_id: int) -> Optional[str]:
        """Get the internal CSS selector for an element (never shown to LLM)."""
        elem = self._id_map.get(element_id)
        return elem.css_selector if elem else None

    def format_for_llm(self) -> str:
        """Format all indexed elements as a numbered list for LLM."""
        if not self._indexed:
            return "(no interactive elements found)"

        lines = []
        for elem in self._indexed:
            lines.append(elem.format_for_llm())
        return "\n".join(lines)

    def format_text_for_llm(self, texts: list[dict]) -> str:
        """Format extracted text content for LLM context."""
        if not texts:
            return ""

        lines = []
        for t in texts[:15]:  # cap to avoid token explosion
            tag = t.get("tag", "")
            text = t.get("text", "")
            if tag.startswith("h"):
                lines.append(f"## {text}")
            else:
                lines.append(text)
        return "\n".join(lines)

    @property
    def count(self) -> int:
        """Number of indexed elements."""
        return len(self._indexed)
