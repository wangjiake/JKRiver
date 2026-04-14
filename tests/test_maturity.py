"""Pure unit tests — no database, no LLM, no network."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.sleep._maturity import _calculate_maturity_decay, _MATURITY_TIERS


class TestMaturityDecay:
    def test_no_upgrade_short_span(self):
        # span=30 days, 1 evidence, current=30 → not enough for any tier
        assert _calculate_maturity_decay(30, 1, 30) == 30

    def test_tier3_upgrade(self):
        # span=90, evidence=3, current=30 → should upgrade to 180
        assert _calculate_maturity_decay(90, 3, 30) == 180

    def test_tier2_upgrade(self):
        # span=365, evidence=6, current=30 → should upgrade to 365
        assert _calculate_maturity_decay(365, 6, 30) == 365

    def test_tier1_upgrade(self):
        # span=730, evidence=10, current=30 → should upgrade to 730
        assert _calculate_maturity_decay(730, 10, 30) == 730

    def test_no_downgrade(self):
        # current_decay=365, even if tier3 matches, won't downgrade
        assert _calculate_maturity_decay(90, 3, 365) == 365

    def test_key_anchor_boost(self):
        # With key anchor boost (0.6x thresholds):
        # tier3: min_span=90*0.6=54, min_ev=max(1,3*0.6)=max(1,1)=1
        # span=60, evidence=2, current=30 → should hit tier3 → 180
        assert _calculate_maturity_decay(60, 2, 30, in_key_anchors=True) == 180

    def test_key_anchor_no_boost_without_flag(self):
        # Same values without boost → no upgrade
        assert _calculate_maturity_decay(60, 2, 30, in_key_anchors=False) == 30

    def test_already_at_max(self):
        # current=730, nothing higher
        assert _calculate_maturity_decay(1000, 20, 730) == 730

    def test_zero_evidence(self):
        # evidence=0, key anchor boost makes min_ev=max(1,0)=1, still need ≥1
        assert _calculate_maturity_decay(100, 0, 30, in_key_anchors=True) == 30

    def test_tiers_are_ordered(self):
        # Verify tiers are checked from highest to lowest
        targets = [t[2] for t in _MATURITY_TIERS]
        assert targets == sorted(targets, reverse=True)


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
