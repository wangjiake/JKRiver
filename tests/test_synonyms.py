"""Pure unit tests — no database, no LLM, no network."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.storage._synonyms import _get_category_synonyms, _get_subject_synonyms, is_significant_category


class TestSynonyms:
    def test_category_known(self):
        syns = _get_category_synonyms("位置")
        assert "居住地" in syns
        assert "居住" in syns
        assert "位置" in syns

    def test_category_unknown_returns_singleton(self):
        syns = _get_category_synonyms("未知分类")
        assert syns == {"未知分类"}

    def test_category_symmetry(self):
        # "位置" and "居住地" should return the same set
        assert _get_category_synonyms("位置") == _get_category_synonyms("居住地")

    def test_subject_known(self):
        syns = _get_subject_synonyms("居住地")
        assert "居住城市" in syns
        assert "当前居住地" in syns

    def test_subject_unknown_returns_singleton(self):
        syns = _get_subject_synonyms("未知主题")
        assert syns == {"未知主题"}

    def test_subject_symmetry(self):
        assert _get_subject_synonyms("女朋友") == _get_subject_synonyms("女友")

    def test_all_category_groups_bidirectional(self):
        from agent.storage._synonyms import _CATEGORY_SYNONYM_GROUPS
        for group in _CATEGORY_SYNONYM_GROUPS:
            for name in group:
                assert _get_category_synonyms(name) == group

    def test_all_subject_groups_bidirectional(self):
        from agent.storage._synonyms import _SUBJECT_SYNONYM_GROUPS
        for group in _SUBJECT_SYNONYM_GROUPS:
            for name in group:
                assert _get_subject_synonyms(name) == group

    def test_english_category_synonym(self):
        assert _get_category_synonyms("career") == _get_category_synonyms("职业")

    def test_english_location_synonym(self):
        assert _get_category_synonyms("location") == _get_category_synonyms("居住")

    def test_japanese_category_synonym(self):
        assert _get_category_synonyms("仕事") == _get_category_synonyms("职业")

    def test_japanese_location_synonym(self):
        assert _get_category_synonyms("場所") == _get_category_synonyms("location")

    def test_english_subject_synonym(self):
        syns = _get_subject_synonyms("current city")
        assert "居住城市" in syns
        assert "居住都市" in syns

    def test_japanese_subject_synonym(self):
        syns = _get_subject_synonyms("卒業校")
        assert "学校" in syns
        assert "university" in syns

    def test_girlfriend_multilingual(self):
        syns = _get_subject_synonyms("girlfriend")
        assert "女朋友" in syns
        assert "彼女" in syns

    def test_boyfriend_multilingual(self):
        syns = _get_subject_synonyms("boyfriend")
        assert "男朋友" in syns
        assert "彼氏" in syns

    def test_sports_multilingual(self):
        syns = _get_subject_synonyms("sports")
        assert "运动" in syns
        assert "スポーツ" in syns

    def test_games_multilingual(self):
        syns = _get_subject_synonyms("games")
        assert "游戏" in syns
        assert "ゲーム" in syns


class TestSignificantCategory:
    def test_chinese_career(self):
        assert is_significant_category("职业") is True

    def test_english_career(self):
        assert is_significant_category("career") is True

    def test_english_location(self):
        assert is_significant_category("location") is True

    def test_chinese_family(self):
        assert is_significant_category("家庭") is True

    def test_english_family(self):
        assert is_significant_category("family") is True

    def test_english_health(self):
        assert is_significant_category("health") is True

    def test_english_education(self):
        assert is_significant_category("education") is True

    def test_synonym_expansion(self):
        # "住址" is a synonym of "居住" which is a significant anchor
        assert is_significant_category("住址") is True

    def test_japanese_significant_career(self):
        assert is_significant_category("仕事") is True

    def test_japanese_significant_family(self):
        assert is_significant_category("家族") is True

    def test_japanese_significant_health(self):
        assert is_significant_category("健康") is True

    def test_non_significant(self):
        assert is_significant_category("兴趣") is False
        assert is_significant_category("hobby") is False

    def test_unknown_category(self):
        assert is_significant_category("随便什么") is False


if __name__ == "__main__":
    passed = failed = 0
    for cls_name, cls in sorted(globals().items()):
        if not isinstance(cls, type) or not cls_name.startswith("Test"):
            continue
        for method_name in sorted(dir(cls)):
            if not method_name.startswith("test_"):
                continue
            name = f"{cls_name}.{method_name}"
            try:
                getattr(cls(), method_name)()
                print(f"  PASS  {name}")
                passed += 1
            except Exception as e:
                print(f"  FAIL  {name}: {e}")
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
