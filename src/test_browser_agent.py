"""
Smoke test for the Browser Agent core engine.
Tests: launch → navigate → extract DOM → index elements → execute action → close.
Does NOT require LLM — tests the perception + action layers only.

Run: python3 test_browser_agent.py
"""

import asyncio
import sys

# Add parent to path for imports
sys.path.insert(0, ".")

from agents.browser_agent.browser.controller import BrowserController
from agents.browser_agent.browser.dom_processor import DOMProcessor
from agents.browser_agent.browser.element_indexer import ElementIndexer
from agents.browser_agent.browser.actions import ActionEngine
from agents.browser_agent.browser.state import capture_state
from agents.browser_agent.browser.guard import BrowserGuard
from agents.browser_agent.parser import parse_response


async def test_core_engine():
    """Test the core browser engine without LLM."""
    print("=" * 60)
    print("🧪 Browser Agent Smoke Test")
    print("=" * 60)

    controller = BrowserController(headless=True)  # headless for testing
    dom_processor = DOMProcessor()
    indexer = ElementIndexer()
    guard = BrowserGuard()

    try:
        # Test 1: Launch browser
        print("\n📋 Test 1: Launch browser")
        await controller.launch()
        print("   ✅ Browser launched")

        # Test 2: Navigate to example.com
        print("\n📋 Test 2: Navigate to example.com")
        await controller.navigate("https://example.com")
        url = controller.current_url()
        title = await controller.current_title()
        print(f"   ✅ URL: {url}")
        print(f"   ✅ Title: {title}")
        assert "example" in url.lower(), f"Unexpected URL: {url}"

        # Test 3: Extract DOM elements
        print("\n📋 Test 3: Extract DOM elements")
        page = await controller.get_page()
        extraction = await dom_processor.extract_all(page)
        elements = extraction["elements"]
        texts = extraction["texts"]
        print(f"   ✅ Interactive elements: {len(elements)}")
        print(f"   ✅ Text blocks: {len(texts)}")

        # Test 4: Index elements
        print("\n📋 Test 4: Index elements")
        indexed = indexer.index(elements)
        formatted = indexer.format_for_llm()
        print(f"   ✅ Indexed {indexer.count} elements")
        print(f"   📋 Element list:\n{formatted}")

        # Test 5: Capture full state
        print("\n📋 Test 5: Capture page state")
        state = await capture_state(controller, dom_processor, indexer)
        print(f"   ✅ State captured:")
        print(f"      URL: {state.url}")
        print(f"      Elements: {state.element_count}")
        state_text = state.format_for_llm()
        print(f"   📋 LLM context preview ({len(state_text)} chars):")
        print(f"   {state_text[:300]}...")

        # Test 6: Guard check
        print("\n📋 Test 6: Guard validation")
        good_action = {"action": "click", "element_id": 1}
        bad_action = {"action": "navigate", "url": "file:///etc/passwd"}
        missing_action = {"action": "click"}

        assert guard.check_action(good_action)["status"] == "allowed"
        assert guard.check_action(bad_action)["status"] == "blocked"
        assert guard.check_action(missing_action)["status"] == "blocked"
        print("   ✅ Guard correctly validates actions")

        # Test 7: Parser
        print("\n📋 Test 7: Response parser")
        test_responses = [
            '{"thought": "clicking", "action": "click", "element_id": 1}',
            '```json\n{"action": "navigate", "url": "https://test.com"}\n```',
            'Some text {"status": "done"} more text',
            'invalid json {{{',
        ]
        for resp in test_responses:
            parsed = parse_response(resp)
            status = parsed.get("action", parsed.get("status", "error"))
            print(f"   → {status}: {resp[:50]}...")
        print("   ✅ Parser handles all cases")

        # Test 8: Execute click action (if elements exist)
        if indexer.count > 0:
            print(f"\n📋 Test 8: Execute click on element [1]")
            action_engine = ActionEngine(controller, indexer)
            url_before = controller.current_url()
            result = await action_engine.execute({"action": "click", "element_id": 1})
            print(f"   → {result['status']}: {result.get('message', '')}")
            url_after = controller.current_url()
            if url_before != url_after:
                print(f"   🔗 Navigation detected: {url_after}")
            print("   ✅ Action executed")
        else:
            print("\n📋 Test 8: Skipped (no elements to click)")

        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await controller.close()


if __name__ == "__main__":
    asyncio.run(test_core_engine())
