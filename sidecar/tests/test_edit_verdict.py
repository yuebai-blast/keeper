"""层② 修图判定四态枚举与兜底逻辑测试。"""

from keeper_engine.enumeration.edit_verdict import EditVerdict


def test_four_values():
    assert {v.value for v in EditVerdict} == {
        "ready", "worth_editing", "not_worth", "unfixable",
    }


def test_coerce_keeps_legal_value():
    assert EditVerdict.coerce("worth_editing") == "worth_editing"
    assert EditVerdict.coerce(" unfixable ") == "unfixable"  # 去空白后合法


def test_coerce_falls_back_to_ready():
    assert EditVerdict.coerce("") == "ready"
    assert EditVerdict.coerce("乱写的") == "ready"
    assert EditVerdict.coerce(None) == "ready"  # None 也兜底
