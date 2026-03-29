"""
Page State — snapshot of the current browser state for LLM context.
Combines URL, title, indexed elements, and text content.
"""


class PageState:
    """Immutable snapshot of the current page state."""

    def __init__(
        self,
        url: str,
        title: str,
        elements_text: str,
        page_text: str,
        element_count: int,
        error: str = "",
    ):
        self.url = url
        self.title = title
        self.elements_text = elements_text
        self.page_text = page_text
        self.element_count = element_count
        self.error = error

    def format_for_llm(self) -> str:
        """Build the full state block the LLM sees."""
        parts = [
            f"Current URL: {self.url}",
            f"Page Title: {self.title}",
            f"Interactive Elements ({self.element_count}):",
            self.elements_text,
        ]

        if self.page_text:
            parts.append(f"\nPage Content:\n{self.page_text}")

        if self.error:
            parts.append(f"\n⚠️ Last Error: {self.error}")

        return "\n".join(parts)


async def capture_state(controller, dom_processor, indexer) -> PageState:
    """
    Full perception pipeline:
    1. Get page from controller
    2. Extract DOM via dom_processor
    3. Index elements
    4. Build PageState snapshot
    """
    try:
        page = await controller.get_page()
        url = controller.current_url()
        title = await controller.current_title()

        # Extract all visible elements and text
        extraction = await dom_processor.extract_all(page)

        # Index interactive elements
        indexed = indexer.index(extraction["elements"])
        elements_text = indexer.format_for_llm()

        # Format text content
        page_text = indexer.format_text_for_llm(extraction["texts"])

        return PageState(
            url=url,
            title=title,
            elements_text=elements_text,
            page_text=page_text,
            element_count=indexer.count,
        )

    except Exception as e:
        return PageState(
            url=controller.current_url() if controller else "unknown",
            title="",
            elements_text="(extraction failed)",
            page_text="",
            element_count=0,
            error=str(e),
        )
