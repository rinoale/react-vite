"""Tests for auto_tag_engine AND/OR logic."""
import pytest
from types import SimpleNamespace

from trade.services.auto_tag_engine import _eval_condition


def _make_payload(*, listing_options=None, **kwargs):
    return SimpleNamespace(listing_options=listing_options or [], **kwargs)


def _opt(option_type, option_name, rolled_value=0):
    return SimpleNamespace(option_type=option_type, option_name=option_name, rolled_value=rolled_value)


class TestPluralAndOr:
    """Test AND/OR logic for plural table (reforge_options) conditions."""

    CONFIG = {
        "conditions": [
            {"table": "reforge_options", "column": "option_name", "op": "==", "value": "최대 공격력", "logic": "AND"},
            {"table": "reforge_options", "column": "option_name", "op": "==", "value": "스매시 대미지", "logic": "OR"},
            {"table": "reforge_options", "column": "rolled_value", "op": ">=", "value": 19, "logic": "AND"},
        ],
        "tag_template": "최공스매",
    }

    def test_max_attack_high_roll(self):
        """최대 공격력 with rolled_value >= 19 → match."""
        payload = _make_payload(listing_options=[
            _opt("reforge_options", "최대 공격력", 20),
        ])
        assert _eval_condition(payload, self.CONFIG, None) == ["최공스매"]

    def test_smash_high_roll(self):
        """스매시 대미지 with rolled_value >= 19 → match."""
        payload = _make_payload(listing_options=[
            _opt("reforge_options", "스매시 대미지", 19),
        ])
        assert _eval_condition(payload, self.CONFIG, None) == ["최공스매"]

    def test_max_attack_low_roll(self):
        """최대 공격력 with rolled_value < 19 → no match."""
        payload = _make_payload(listing_options=[
            _opt("reforge_options", "최대 공격력", 18),
        ])
        assert _eval_condition(payload, self.CONFIG, None) == []

    def test_wrong_option_high_roll(self):
        """Neither 최대 공격력 nor 스매시 대미지 → no match."""
        payload = _make_payload(listing_options=[
            _opt("reforge_options", "밸런스", 20),
        ])
        assert _eval_condition(payload, self.CONFIG, None) == []

    def test_multiple_rows_one_matches(self):
        """Multiple reforge rows, one matches."""
        payload = _make_payload(listing_options=[
            _opt("reforge_options", "밸런스", 20),
            _opt("reforge_options", "스매시 대미지", 19),
        ])
        assert _eval_condition(payload, self.CONFIG, None) == ["최공스매"]

    def test_no_options(self):
        """No reforge options → no match."""
        payload = _make_payload(listing_options=[])
        assert _eval_condition(payload, self.CONFIG, None) == []


class TestPluralAllAnd:
    """Backward compat: all AND conditions still work."""

    CONFIG = {
        "conditions": [
            {"table": "reforge_options", "column": "option_name", "op": "==", "value": "밸런스", "logic": "AND"},
            {"table": "reforge_options", "column": "rolled_value", "op": ">=", "value": 15, "logic": "AND"},
        ],
        "tag_template": "high_balance",
    }

    def test_match(self):
        payload = _make_payload(listing_options=[
            _opt("reforge_options", "밸런스", 18),
        ])
        assert _eval_condition(payload, self.CONFIG, None) == ["high_balance"]

    def test_name_mismatch(self):
        payload = _make_payload(listing_options=[
            _opt("reforge_options", "대미지", 18),
        ])
        assert _eval_condition(payload, self.CONFIG, None) == []

    def test_value_too_low(self):
        payload = _make_payload(listing_options=[
            _opt("reforge_options", "밸런스", 10),
        ])
        assert _eval_condition(payload, self.CONFIG, None) == []


class TestSingularAndOr:
    """Test AND/OR on singular tables."""

    CONFIG = {
        "conditions": [
            {"table": "listing", "column": "item_type", "op": "==", "value": "weapon", "logic": "AND"},
            {"table": "listing", "column": "item_type", "op": "==", "value": "armor", "logic": "OR"},
        ],
        "tag_template": "combat_item",
    }

    def test_weapon(self):
        payload = _make_payload(item_type="weapon")
        assert _eval_condition(payload, self.CONFIG, None) == ["combat_item"]

    def test_armor(self):
        payload = _make_payload(item_type="armor")
        assert _eval_condition(payload, self.CONFIG, None) == ["combat_item"]

    def test_accessory(self):
        payload = _make_payload(item_type="accessory")
        assert _eval_condition(payload, self.CONFIG, None) == []


class TestCrossRowGroups:
    """Test group-based cross-row matching."""

    CONFIG = {
        "conditions": [
            {"group": 1, "table": "reforge_options", "column": "option_name", "op": "==", "value": "최대 공격력", "logic": "AND"},
            {"group": 1, "table": "reforge_options", "column": "rolled_value", "op": ">", "value": 19, "logic": "AND"},
            {"group": 2, "table": "reforge_options", "column": "option_name", "op": "==", "value": "스매시 대미지", "logic": "AND"},
            {"group": 2, "table": "reforge_options", "column": "rolled_value", "op": ">", "value": 19, "logic": "AND"},
        ],
        "tag_template": "최공스매19",
    }

    def test_both_high(self):
        """Both options with rolled > 19 → match."""
        payload = _make_payload(listing_options=[
            _opt("reforge_options", "최대 공격력", 20),
            _opt("reforge_options", "스매시 대미지", 20),
        ])
        assert _eval_condition(payload, self.CONFIG, None) == ["최공스매19"]

    def test_only_one_present(self):
        """Only one option present → no match."""
        payload = _make_payload(listing_options=[
            _opt("reforge_options", "최대 공격력", 20),
        ])
        assert _eval_condition(payload, self.CONFIG, None) == []

    def test_both_present_one_low(self):
        """Both present but 스매시 rolled <= 19 → no match."""
        payload = _make_payload(listing_options=[
            _opt("reforge_options", "최대 공격력", 20),
            _opt("reforge_options", "스매시 대미지", 19),
        ])
        assert _eval_condition(payload, self.CONFIG, None) == []

    def test_both_present_other_low(self):
        """Both present but 최대 공격력 rolled <= 19 → no match."""
        payload = _make_payload(listing_options=[
            _opt("reforge_options", "최대 공격력", 19),
            _opt("reforge_options", "스매시 대미지", 20),
        ])
        assert _eval_condition(payload, self.CONFIG, None) == []

    def test_extra_rows_dont_interfere(self):
        """Extra unrelated rows don't affect matching."""
        payload = _make_payload(listing_options=[
            _opt("reforge_options", "밸런스", 25),
            _opt("reforge_options", "최대 공격력", 20),
            _opt("reforge_options", "크리티컬", 15),
            _opt("reforge_options", "스매시 대미지", 21),
        ])
        assert _eval_condition(payload, self.CONFIG, None) == ["최공스매19"]

    def test_no_options(self):
        """No reforge options → no match."""
        payload = _make_payload(listing_options=[])
        assert _eval_condition(payload, self.CONFIG, None) == []

    def test_wrong_options_high_roll(self):
        """High rolls but wrong option names → no match."""
        payload = _make_payload(listing_options=[
            _opt("reforge_options", "밸런스", 25),
            _opt("reforge_options", "크리티컬", 25),
        ])
        assert _eval_condition(payload, self.CONFIG, None) == []
