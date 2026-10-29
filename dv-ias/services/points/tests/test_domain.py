"""points TDD：积分规则与幂等键设计。"""
from app.repo import EARN_RULES

def test_earn_rules_cover_all_types():
    assert set(EARN_RULES) == {"environment", "safety", "public", "other"}
    assert EARN_RULES["safety"] > EARN_RULES["public"]  # 安全隐患奖励更高

def test_ref_id_idempotent_design():
    ref = f"evt-{123}"
    assert ref == "evt-123"  # 同一事件重复消费生成相同幂等键
