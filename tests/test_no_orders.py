"""Paper-only guard: fail the build if order-placement code or trading credentials appear."""
import pathlib, re
BAD = re.compile(r"(portfolio/orders|/orders\b|create_order|place_order|PRIVATE_KEY|KALSHI_API_KEY|submit_order)", re.I)
def test_no_order_code():
    for p in pathlib.Path(".").rglob("*.py"):
        if "tests" in p.parts or ".git" in p.parts: continue
        assert not BAD.search(p.read_text()), f"order-like code in {p}"
