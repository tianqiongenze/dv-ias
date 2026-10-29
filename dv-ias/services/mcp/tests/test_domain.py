"""mcp TDD：工具契约（白名单闭合）。"""
import sys; sys.path.insert(0, "/srv")
from app.main import TOOLS, GUIDES

def test_tools_whitelist():
    names = {t["name"] for t in TOOLS}
    assert names == {"query_points", "query_event_progress", "search_service_guide", "query_village_metrics"}

def test_guide_search_by_item():
    hits = [g for g in GUIDES if "户口本" in g["items"]]
    assert len(hits) >= 2
