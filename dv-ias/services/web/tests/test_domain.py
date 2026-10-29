"""web TDD：静态资源就位检查。"""
from pathlib import Path

def test_pages_exist():
    base = Path("/srv/static")
    for p in ["h5/index.html", "admin/index.html", "screen/index.html"]:
        assert (base / p).exists(), p
