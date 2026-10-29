"""data TDD：指标口径（纯函数部分）。"""
def test_done_rate_zero_when_no_events():
    total, done = 0, 0
    rate = round(done * 100.0 / total, 1) if total else 0.0
    assert rate == 0.0

def test_done_rate_rounding():
    assert round(2 * 100.0 / 3, 1) == 66.7
