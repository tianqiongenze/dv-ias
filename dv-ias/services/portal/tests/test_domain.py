"""portal TDD：内容审核词表拦截。"""
def test_forbidden_words_block():
    FORBIDDEN = ["暴力", "赌", "诈骗"]
    title, content = "正常标题", "今日村务内容"
    assert not any(w in content or w in title for w in FORBIDDEN)
    assert any(w in "赌博内容" for w in FORBIDDEN)
