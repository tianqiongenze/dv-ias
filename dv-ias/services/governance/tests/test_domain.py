"""governance TDD：事件状态机合法迁移（04号文档不变量）。"""
from app.repo import TRANSITIONS

def test_state_machine_happy_path():
    assert TRANSITIONS["pending"]["accept"] == "accepted"
    assert TRANSITIONS["accepted"]["dispatch"] == "dispatched"
    assert TRANSITIONS["dispatched"]["resolve"] == "resolved"
    assert TRANSITIONS["resolved"]["approve"] == "approved"

def test_state_machine_illegal():
    assert "approve" not in TRANSITIONS["pending"]
    assert "resolve" not in TRANSITIONS["accepted"]
    assert not TRANSITIONS.get("approved")  # 终态无出边
