"""
DOM Processor — extracts visible, interactive elements from the page.
Runs JavaScript in-page to collect buttons, links, inputs, etc.
Returns raw element data for the indexer to process.
"""

# JavaScript to extract interactive elements from the page
EXTRACT_ELEMENTS_JS = """
() => {
    const interactive = [
        'a', 'button', 'input', 'textarea', 'select',
        '[role="button"]', '[role="link"]', '[role="tab"]',
        '[role="menuitem"]', '[role="checkbox"]', '[role="radio"]',
        '[onclick]', '[tabindex]'
    ];

    const selector = interactive.join(', ');
    const elements = document.querySelectorAll(selector);
    const results = [];

    for (const el of elements) {
        // Skip hidden elements
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);

        if (
            rect.width === 0 || rect.height === 0 ||
            style.display === 'none' ||
            style.visibility === 'hidden' ||
            style.opacity === '0' ||
            el.disabled
        ) {
            continue;
        }

        // Check if element is in viewport (roughly)
        const inViewport = (
            rect.top < window.innerHeight + 200 &&
            rect.bottom > -200 &&
            rect.left < window.innerWidth + 200 &&
            rect.right > -200
        );

        if (!inViewport) continue;

        // Get text content
        let text = '';
        if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
            text = el.value || el.placeholder || '';
        } else if (el.tagName === 'SELECT') {
            const selected = el.options[el.selectedIndex];
            text = selected ? selected.text : '';
        } else {
            // Get direct text, not deeply nested
            text = el.innerText || el.textContent || '';
        }
        text = text.trim().substring(0, 100);  // cap length

        // Get aria-label or title
        const ariaLabel = el.getAttribute('aria-label') || '';
        const title = el.getAttribute('title') || '';
        const label = ariaLabel || title;

        // Determine element type info
        const tag = el.tagName.toLowerCase();
        const type = el.getAttribute('type') || '';
        const role = el.getAttribute('role') || '';
        const href = el.getAttribute('href') || '';
        const name = el.getAttribute('name') || '';
        const id = el.getAttribute('id') || '';
        const placeholder = el.getAttribute('placeholder') || '';

        // Build a CSS selector path for internal use
        let cssSelector = tag;
        if (id) {
            cssSelector = `#${CSS.escape(id)}`;
        } else if (name) {
            cssSelector = `${tag}[name="${CSS.escape(name)}"]`;
        }

        // Position hint (approximate)
        let position = '';
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        const viewW = window.innerWidth;
        const viewH = window.innerHeight;

        if (centerY < viewH * 0.2) position += 'top ';
        else if (centerY > viewH * 0.8) position += 'bottom ';
        if (centerX < viewW * 0.3) position += 'left';
        else if (centerX > viewW * 0.7) position += 'right';
        else position += 'center';
        position = position.trim();

        results.push({
            tag: tag,
            type: type,
            role: role,
            text: text,
            label: label,
            href: href,
            name: name,
            elementId: id,
            placeholder: placeholder,
            cssSelector: cssSelector,
            position: position,
            rect: {
                x: Math.round(rect.x),
                y: Math.round(rect.y),
                width: Math.round(rect.width),
                height: Math.round(rect.height)
            }
        });
    }

    return results;
}
"""

# JavaScript to extract text content blocks (non-interactive)
EXTRACT_TEXT_JS = """
() => {
    const textElements = document.querySelectorAll('h1, h2, h3, h4, p, [role="heading"], [role="alert"]');
    const results = [];

    for (const el of textElements) {
        const text = (el.innerText || el.textContent || '').trim();
        if (!text || text.length < 2) continue;

        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);

        if (rect.width === 0 || rect.height === 0 || style.display === 'none') continue;

        results.push({
            tag: el.tagName.toLowerCase(),
            text: text.substring(0, 200),
        });
    }

    return results;
}
"""


class DOMProcessor:
    """Extracts visible interactive elements and text from a Playwright page."""

    async def extract_elements(self, page) -> list[dict]:
        """
        Run JS extraction in-page and return list of raw element dicts.
        Each dict contains: tag, type, role, text, label, href, cssSelector,
        position, rect, etc.
        """
        try:
            elements = await page.evaluate(EXTRACT_ELEMENTS_JS)
            return elements if elements else []
        except Exception as e:
            print(f"⚠️ DOM extraction error: {e}")
            return []

    async def extract_text(self, page) -> list[dict]:
        """Extract visible text blocks (headings, paragraphs, alerts)."""
        try:
            texts = await page.evaluate(EXTRACT_TEXT_JS)
            return texts if texts else []
        except Exception as e:
            print(f"⚠️ Text extraction error: {e}")
            return []

    async def extract_all(self, page) -> dict:
        """Full extraction: interactive elements + text content."""
        elements = await self.extract_elements(page)
        texts = await self.extract_text(page)
        return {
            "elements": elements,
            "texts": texts,
        }
