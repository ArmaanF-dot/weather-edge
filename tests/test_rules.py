from rules.registry import kalshi_taker_fee, lst_day_window_utc, c_to_f_whole
def test_fee_rounds_up():
    assert kalshi_taker_fee(1, 0.5) == 0.02      # 0.0175 -> 0.02
    assert kalshi_taker_fee(100, 0.5) == 1.75
def test_lst_ignores_dst():
    s, e = lst_day_window_utc("2026-07-01", -6)   # July, Chicago: still UTC-6 for settlement
    assert s.hour == 6 and (e - s).days == 1
def test_c_to_f():
    assert c_to_f_whole(20.0) == 68
