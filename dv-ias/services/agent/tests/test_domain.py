"""agent TDD：检索打分与降级策略（不依赖外部模型）。"""
import sys; sys.path.insert(0, "/srv")
from app.main import retrieve, KB

def test_retrieve_hits_relevant():
    hits = retrieve("水稻稻瘟病怎么防治")
    assert hits and hits[0]["id"] == "k3"

def test_retrieve_empty_when_no_match():
    assert retrieve("zzzz 无关词") == []

def test_kb_has_answer_text():
    assert all(len(k["a"]) > 20 for k in KB)
