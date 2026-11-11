from app.services.citation import locate_quote, similarity, verify_quote


def test_exact_quote_verified():
    assert verify_quote("投资总额 3,000 万美元", "项目投资总额 3,000 万美元，其中设备 800 万。")


def test_quote_with_whitespace_and_punctuation_verified():
    assert verify_quote(
        "租赁期限 30 年，到期后自动续期 30 年",
        "租赁期限30年; 到期后自动续期30年。",
    )


def test_near_quote_uses_similarity_threshold():
    assert similarity("设备总功率 1250 kW", "设备总功率 1,250 kW") >= 0.85


def test_missing_quote_not_verified():
    assert not verify_quote("注册资本 5 亿泰铢", "注册资本 1 亿泰铢。")


def test_locate_quote_returns_offsets():
    text = "前文。投资总额 3,000 万美元。后文。"
    start, end = locate_quote("投资总额 3,000 万美元", text)
    assert text[start:end] == "投资总额 3,000 万美元"
