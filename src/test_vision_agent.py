"""
Smoke test for the Vision Agent.
Tests each module independently WITHOUT making LLM API calls.

Run: python3 test_vision_agent.py
"""

import sys
import time

sys.path.insert(0, ".")


def test_screen_capture():
    """Test screen capture, base64 encoding, and resolution scaling."""
    print("\n📋 Test 1: Screen Capture")

    from agents.vision_agent.screen import ScreenCapture

    sc = ScreenCapture(max_width=800, max_height=600, jpeg_quality=50)

    # Check monitors
    monitors = sc.available_monitors
    print(f"   🖥️  Monitors found: {len(monitors)}")
    for m in monitors:
        print(f"      [{m['index']}] {m['width']}x{m['height']} at ({m['left']},{m['top']})")

    # Full screen capture
    img = sc.capture_full()
    w, h = img.size
    print(f"   📐 Captured: {w}x{h}")
    assert w > 0 and h > 0, "Image dimensions must be positive"
    assert w <= 800 and h <= 600, f"Image should be scaled down, got {w}x{h}"

    # Base64 encoding
    b64 = sc.to_base64(img)
    print(f"   📦 Base64 length: {len(b64)} chars")
    assert len(b64) > 100, "Base64 string too short"

    # Convenience method
    b64_2, size = sc.capture_and_encode()
    assert size == (w, h), "Size mismatch"
    print(f"   ✅ Capture + encode: {size[0]}x{size[1]}, {len(b64_2)} chars")

    # Region capture
    region_img = sc.capture_region((0, 0, 200, 200))
    print(f"   📐 Region: {region_img.size}")
    assert region_img.size[0] <= 200 and region_img.size[1] <= 200

    sc.close()
    print("   ✅ Screen capture passed")


def test_parser():
    """Test JSON parsing, bbox validation, and coordinate centering."""
    print("\n📋 Test 2: Response Parser")

    from agents.vision_agent.parser import parse_response

    screen = (1920, 1080)

    # Valid click with bbox
    r = parse_response('{"action":"click","target":"Downloads","bbox":[100,200,160,260],"confidence":0.9}', screen)
    assert r["action"] == "click"
    assert r["click_x"] == 130 and r["click_y"] == 230, f"Center: ({r['click_x']},{r['click_y']})"
    assert r["confidence"] == 0.9
    print(f"   ✅ Click: center=({r['click_x']},{r['click_y']}), conf={r['confidence']}")

    # JSON in code block
    r = parse_response('```json\n{"action":"type","text":"hello","confidence":0.8}\n```', screen)
    assert r["action"] == "type" and r["text"] == "hello"
    print(f"   ✅ Code block: type '{r['text']}'")

    # Hotkey
    r = parse_response('{"action":"hotkey","keys":["ctrl","alt","t"],"confidence":0.95}', screen)
    assert r["action"] == "hotkey" and r["keys"] == ["ctrl", "alt", "t"]
    print(f"   ✅ Hotkey: {'+'.join(r['keys'])}")

    # Done status
    r = parse_response('{"status":"done","confidence":1.0}', screen)
    assert r["status"] == "done"
    print(f"   ✅ Done status")

    # Invalid JSON
    r = parse_response("not json {{{", screen)
    assert r["status"] == "error"
    print(f"   ✅ Invalid JSON handled: {r['reason'][:50]}")

    # Missing bbox
    r = parse_response('{"action":"click","target":"X","confidence":0.5}', screen)
    assert r["status"] == "error"
    print(f"   ✅ Missing bbox caught: {r['reason']}")

    # Out-of-bounds bbox (should clamp)
    r = parse_response('{"action":"click","bbox":[0,0,2000,1200],"confidence":0.5}', screen)
    assert r["bbox"][2] <= 1920 and r["bbox"][3] <= 1080
    print(f"   ✅ Bbox clamped: {r['bbox']}")

    print("   ✅ Parser passed")


def test_guard():
    """Test safety guard: rate limiting, hotkey blacklist, runaway detection."""
    print("\n📋 Test 3: Safety Guard")

    from agents.vision_agent.guard import VisionGuard

    guard = VisionGuard(max_actions_per_second=10.0)

    # Add a danger zone
    guard.add_danger_zone("power_button", 1880, 0, 1920, 40)

    # Normal click — should pass
    r = guard.check_action({"action": "click", "click_x": 500, "click_y": 300})
    assert r["status"] == "allowed"
    print("   ✅ Normal click: allowed")

    # Click in danger zone
    time.sleep(0.11)
    r = guard.check_action({"action": "click", "click_x": 1900, "click_y": 20})
    assert r["status"] == "blocked"
    print(f"   ✅ Danger zone: {r['reason']}")

    # Blacklisted hotkey
    time.sleep(0.11)
    r = guard.check_action({"action": "hotkey", "keys": ["ctrl", "alt", "delete"]})
    assert r["status"] == "blocked"
    print(f"   ✅ Blacklisted hotkey: {r['reason']}")

    # Valid hotkey
    time.sleep(0.11)
    r = guard.check_action({"action": "hotkey", "keys": ["ctrl", "c"]})
    assert r["status"] == "allowed"
    print("   ✅ Valid hotkey: allowed")


    # Runaway detection (same action many times)
    guard.reset()
    for i in range(5):
        time.sleep(0.11)
        guard.check_action({"action": "click", "click_x": 100, "click_y": 100})

    time.sleep(0.11)
    r = guard.check_action({"action": "click", "click_x": 100, "click_y": 100})
    assert r["status"] == "blocked", f"Expected blocked, got {r}"
    print(f"   ✅ Runaway detected: {r['reason']}")

    print("   ✅ Guard passed")


def test_planner():
    """Test confidence gating, stuck detection, retry budgets."""
    print("\n📋 Test 4: Action Planner")

    from agents.vision_agent.planner import ActionPlanner

    planner = ActionPlanner(confidence_threshold=0.5, stuck_threshold=3)

    # High confidence — execute
    r = planner.evaluate({"action": "click", "click_x": 100, "click_y": 200, "confidence": 0.9})
    assert r["decision"] == "execute"
    print("   ✅ High confidence: execute")

    # Low confidence — retry
    r = planner.evaluate({"action": "click", "click_x": 300, "click_y": 400, "confidence": 0.2})
    assert r["decision"] == "retry"
    print(f"   ✅ Low confidence: {r['reason']}")

    # Done status — always execute
    r = planner.evaluate({"status": "done"})
    assert r["decision"] == "execute"
    print("   ✅ Done status: execute")

    # Stuck detection
    planner.reset()
    for _ in range(3):
        planner.evaluate({"action": "click", "click_x": 500, "click_y": 500, "confidence": 0.9})

    r = planner.evaluate({"action": "click", "click_x": 500, "click_y": 500, "confidence": 0.9})
    assert r["decision"] == "reject"
    print(f"   ✅ Stuck detected: {r['reason']}")

    print("   ✅ Planner passed")


def test_memory():
    """Test session memory and spatial memory."""
    print("\n📋 Test 5: Memory Systems")

    from agents.vision_agent.memory.session import SessionMemory
    from agents.vision_agent.memory.spatial import SpatialMemory

    # Session memory
    mem = SessionMemory(max_steps=3)
    mem.add(1, {"action": "click", "click_x": 100, "click_y": 200, "target": "Button", "confidence": 0.9},
            {"status": "success", "message": "Clicked"})
    mem.add(2, {"action": "type", "text": "hello", "confidence": 0.8},
            {"status": "success", "message": "Typed"})

    fmt = mem.format_for_llm()
    assert "Step 1" in fmt and "Step 2" in fmt
    print(f"   📝 Memory:\n{fmt}")

    rate = mem.get_success_rate()
    assert rate == 1.0, f"Expected 100% success rate, got {rate}"
    print(f"   ✅ Success rate: {rate*100:.0f}%")

    # Sliding window
    mem.add(3, {"action": "scroll", "confidence": 0.7}, {"status": "success", "message": "Scrolled"})
    mem.add(4, {"action": "click", "click_x": 50, "click_y": 50, "confidence": 0.6},
            {"status": "error", "message": "Missed"})
    assert len(mem.history) == 3, f"Window should be 3, got {len(mem.history)}"
    print(f"   ✅ Sliding window: {len(mem.history)} entries")

    # Spatial memory
    spatial = SpatialMemory(screen_width=1920, screen_height=1080, stale_threshold=5.0)
    spatial.record("Downloads", (100, 500, 160, 560), confidence=0.9)
    spatial.record("Chrome", (200, 500, 260, 560), confidence=0.85)

    lookup = spatial.lookup("Downloads")
    assert lookup is not None
    assert lookup["center"] == (130, 530)
    print(f"   ✅ Spatial lookup: 'Downloads' at {lookup['center']}")

    # Resolution independence
    spatial.update_resolution(3840, 2160)
    lookup2 = spatial.lookup("Downloads")
    assert lookup2["center"] != lookup["center"]
    print(f"   ✅ Resolution scaled: 'Downloads' at {lookup2['center']} (4K)")

    fresh = spatial.get_all_fresh()
    assert len(fresh) == 2
    print(f"   ✅ Fresh elements: {len(fresh)}")

    print("   ✅ Memory systems passed")


def test_executor_bounds():
    """Test executor bounds validation (no actual mouse movement)."""
    print("\n📋 Test 6: Executor Bounds Check")

    from agents.vision_agent.executor import ScreenExecutor

    executor = ScreenExecutor()
    print(f"   🖥️  Screen: {executor.screen_w}x{executor.screen_h}")

    # In bounds
    assert executor._in_bounds(100, 200) == True
    assert executor._in_bounds(0, 0) == True
    print("   ✅ Valid coords: in bounds")

    # Out of bounds
    assert executor._in_bounds(-1, 0) == False
    assert executor._in_bounds(0, -1) == False
    assert executor._in_bounds(99999, 0) == False
    print("   ✅ Invalid coords: out of bounds")

    # Wait action (safe to execute in test)
    result = executor.execute({"action": "wait", "seconds": 0.5})
    assert result["status"] == "success"
    print(f"   ✅ Wait action: {result['message']}")

    print("   ✅ Executor bounds passed")


def test_feedback():
    """Test pixel-diff based feedback (no VLM calls)."""
    print("\n📋 Test 7: Feedback Loop")

    from PIL import Image
    from agents.vision_agent.feedback import FeedbackLoop

    fb = FeedbackLoop(brain=None, vlm_verify=False)

    # Create test images
    img1 = Image.new("RGB", (100, 100), color="red")
    img2 = Image.new("RGB", (100, 100), color="blue")
    img3 = Image.new("RGB", (100, 100), color="red")  # same as img1

    # Different images — screen changed
    result = fb.verify_action(img1, img2, {"action": "click", "target": "button"})
    assert result.screen_changed == True
    print(f"   ✅ Different images: changed={result.screen_changed}, success={result.success}")

    # Same images — screen unchanged
    result = fb.verify_action(img1, img3, {"action": "click", "target": "button"})
    assert result.screen_changed == False
    assert result.should_retry == True
    print(f"   ✅ Same images: changed={result.screen_changed}, retry={result.should_retry}")

    # Wait action — always success
    result = fb.verify_action(img1, img1, {"action": "wait", "seconds": 2})
    assert result.success == True
    print(f"   ✅ Wait action: success={result.success}")

    print("   ✅ Feedback loop passed")


def main():
    print("=" * 60)
    print("🧪 Vision Agent Smoke Test")
    print("=" * 60)

    tests = [
        ("Screen Capture", test_screen_capture),
        ("Response Parser", test_parser),
        ("Safety Guard", test_guard),
        ("Action Planner", test_planner),
        ("Memory Systems", test_memory),
        ("Executor Bounds", test_executor_bounds),
        ("Feedback Loop", test_feedback),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"\n   ❌ FAILED: {name}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*60}")
    if failed == 0:
        print(f"🎉 ALL {passed} TESTS PASSED")
    else:
        print(f"⚠️  {passed} passed, {failed} failed")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
