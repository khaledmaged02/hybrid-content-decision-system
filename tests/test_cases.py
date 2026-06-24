"""
tests/test_cases.py
==================================================================
T3.1 (Khaled) — the required test suite.

12 cases, mapped ONE-TO-ONE to the "حالات الاختبار المطلوبة" table in
KBS_PROJECT_PLAN_FINAL_PURE_EXPERTA.md (10 logical + 2 for the
performance improvements):

  #   plan description                              expected verdict
  --  -------------------------------------------   ----------------
  1   safe educational content, trusted source      Allowed
  2   medium risk, no banned category               Warning
  3   high-risk content                             Blocked
  4   a banned sensitive keyword is present          Blocked
  5   unclear classification + low confidence        Review
  6   banned category + medium risk                  Blocked
  7   safe content but the source is suspicious      Warning|Review  -> Review
  8   suggested_min_age > user age                   Warning|Blocked -> Warning
  9   low confidence + high risk                     Review (no ban) / Blocked (ban)
  10  risk_score exactly on the threshold            per the locked threshold (75 -> Blocked)
  11  duplicate-Signal stress (P2 check)             every signal type appears once
  12  two different sequential requests (P3 check)   each request is clean, no leak

HOW TO RUN (from the project root, hcds env):
    python -m unittest tests.test_cases -v
    # or:
    python -m tests.test_cases

WHY SOME CASES BUILD FACTS DIRECTLY (case 9)
    The mock analyzer can never emit (high risk + low confidence) at once:
    low confidence (0.50) only happens when it recognises NO keyword, and
    with no keyword the risk stays low. Case 9 is the P4 conflict, so we
    feed crafted AIAnalysis/atomic facts straight into a fresh KBSEngine —
    exactly what rules/decision_rules.py does in its own smoke test. The
    verdict still comes ONLY from experta; the test never decides it.

PURE-experta NOTE
    Tests are plain Python (the plan explicitly allows Python in
    tests/output). Not one verdict is chosen here: every assertion reads a
    Decision/Explanation/Signal fact that the experta rules produced.
==================================================================
"""

import unittest

from engine.decision_service import run_decision_engine
from engine.kbs_engine import KBSEngine
from facts.all_facts import (
    AIAnalysis,
    UserProfile,
    DetectedCategory,
    BannedCategory,
    Decision,
)


# ------------------------------------------------------------------
# Helpers (plumbing only — they run the pipeline, they decide nothing)
# ------------------------------------------------------------------

def _make_input(text, *, age, age_group, language="en",
                source_type="text", source_reputation="unknown",
                protection_level="medium",
                banned_categories=None, banned_keywords=None):
    """Build one API-style input dict for run_decision_engine()."""
    return {
        "text": text,
        "source_type": source_type,
        "source_reputation": source_reputation,
        "age": age,
        "age_group": age_group,
        "language": language,
        "protection_level": protection_level,
        "banned_categories": banned_categories or [],
        "banned_keywords": banned_keywords or [],
    }


def _evaluate(input_data):
    """Run the full AI -> Mapper -> KBS pipeline, return the result dict."""
    return run_decision_engine(input_data)


def _signal_types(result):
    """The list of signal `type` strings the engine raised for a result."""
    return [s["type"] for s in result["kbs_result"]["signals"]]


def _verdict_from_facts(facts):
    """Declare crafted facts into a FRESH engine and return its verdict.

    Used only by case 9 (the conflict the mock analyzer cannot produce).
    The verdict is read from the Decision fact experta asserts — never
    chosen by this function.
    """
    engine = KBSEngine()
    engine.reset()
    engine.load_facts(facts)
    engine.run_until_stable()
    decisions = [f for _, f in engine.list_facts() if isinstance(f, Decision)]
    return decisions


# A neutral AIAnalysis whose own fields raise NO signal on their own, so a
# crafted case can control exactly which signals exist. Risk/confidence are
# overridden per case.
def _ai(**overrides):
    base = dict(
        category="violence", risk_score=80, risk_level="high",
        confidence_score=0.50, confidence_level="low",
        suggested_min_age=16, language="ar", analyzer_type="mock",
    )
    base.update(overrides)
    return AIAnalysis(**base)


class TestDecisionCases(unittest.TestCase):

    # ============================================================== #
    # CASE 1 — safe educational content, high-ish confidence, trusted
    #          source  ->  Allowed
    # NOTE: the mock's confidence for a single safe category is 0.70
    # (medium). That is the realistic ceiling for low-risk content and,
    # crucially, it is NOT low (>= 0.55) so no Review is triggered. The
    # decisive facts for Allowed are: risk < 40, no banned hit, no age
    # violation, confidence not low -> zero negative signals.
    # ============================================================== #
    def test_case_01_allowed_safe_trusted(self):
        result = _evaluate(_make_input(
            "a nature documentary that briefly shows some blood",
            age=16, age_group="teen", language="en",
            source_type="video", source_reputation="trusted",
            banned_categories=["gambling"], banned_keywords=["bet"],
        ))
        self.assertEqual(result["kbs_result"]["decision"], "Allowed")
        self.assertEqual(_signal_types(result), [],
                         "a truly safe item must raise no negative signal")

    # ============================================================== #
    # CASE 2 — medium risk (bet -> 50), category NOT banned  ->  Warning
    # ============================================================== #
    def test_case_02_warning_medium_risk(self):
        result = _evaluate(_make_input(
            "thinking about going to bet on the match",
            age=20, age_group="adult", language="en",
            banned_categories=["drugs"], banned_keywords=["drug"],
        ))
        self.assertEqual(result["kbs_result"]["decision"], "Warning")
        self.assertIn("medium_risk", _signal_types(result))

    # ============================================================== #
    # CASE 3 — high risk (kill+weapon -> 90), nothing banned  ->  Blocked
    # ============================================================== #
    def test_case_03_blocked_high_risk(self):
        result = _evaluate(_make_input(
            "how to kill someone with a weapon",
            age=16, age_group="teen", language="en",
            banned_categories=["gambling"], banned_keywords=["bet"],
        ))
        self.assertEqual(result["kbs_result"]["decision"], "Blocked")
        self.assertIn("high_risk", _signal_types(result))
        self.assertIn("rule_blocked_high_risk", result["kbs_result"]["triggered_rules"])

    # ============================================================== #
    # CASE 4 — a banned sensitive keyword is present  ->  Blocked
    # (gambling NOT banned, but "bet" IS a banned keyword -> keyword_hit)
    # ============================================================== #
    def test_case_04_blocked_banned_keyword(self):
        result = _evaluate(_make_input(
            "thinking about going to bet on the match",
            age=20, age_group="adult", language="en",
            banned_categories=["drugs"], banned_keywords=["bet"],
        ))
        self.assertEqual(result["kbs_result"]["decision"], "Blocked")
        self.assertIn("keyword_hit", _signal_types(result))
        self.assertIn("rule_blocked_keyword", result["kbs_result"]["triggered_rules"])

    # ============================================================== #
    # CASE 5 — unclear classification (general) + low confidence -> Review
    # (no recognised keyword -> confidence 0.50, category "general")
    # ============================================================== #
    def test_case_05_review_low_confidence(self):
        result = _evaluate(_make_input(
            "this is some unclear random text about nothing specific",
            age=30, age_group="adult", language="en",
        ))
        self.assertEqual(result["kbs_result"]["decision"], "Review")
        self.assertIn("low_confidence", _signal_types(result))

    # ============================================================== #
    # CASE 6 — banned category + medium risk  ->  Blocked
    # (gambling IS banned -> banned_category_hit beats medium_risk)
    # ============================================================== #
    def test_case_06_blocked_banned_category(self):
        result = _evaluate(_make_input(
            "thinking about going to bet on the match",
            age=20, age_group="adult", language="en",
            banned_categories=["gambling"], banned_keywords=["drug"],
        ))
        self.assertEqual(result["kbs_result"]["decision"], "Blocked")
        self.assertIn("banned_category_hit", _signal_types(result))
        self.assertIn("rule_blocked_banned_category", result["kbs_result"]["triggered_rules"])

    # ============================================================== #
    # CASE 7 — safe content but suspicious source -> Warning|Review
    # The plan allows either; with this mock, unrecognised text gives
    # confidence 0.50 (low) -> low_confidence -> Review. suspicious_source
    # is raised as an advisory signal but has no decision rule of its own.
    # ============================================================== #
    def test_case_07_suspicious_source(self):
        result = _evaluate(_make_input(
            "this is some unclear random text",
            age=30, age_group="adult", language="en",
            source_reputation="suspicious",
        ))
        self.assertIn(result["kbs_result"]["decision"], ("Warning", "Review"))
        self.assertEqual(result["kbs_result"]["decision"], "Review")
        self.assertIn("suspicious_source", _signal_types(result))

    # ============================================================== #
    # CASE 8 — suggested_min_age (13) > user age (10) -> Warning|Blocked
    # Low-weight keyword (blood -> risk 35, below medium) so the ONLY
    # signal is age_violation -> Warning (risk not high -> not Blocked).
    # ============================================================== #
    def test_case_08_age_violation_warning(self):
        result = _evaluate(_make_input(
            "a nature documentary that briefly shows some blood",
            age=10, age_group="child", language="en",
            banned_categories=["gambling"], banned_keywords=["bet"],
        ))
        self.assertIn(result["kbs_result"]["decision"], ("Warning", "Blocked"))
        self.assertEqual(result["kbs_result"]["decision"], "Warning")
        self.assertIn("age_violation", _signal_types(result))

    # ============================================================== #
    # CASE 9 — low confidence + high risk (the P4 conflict).
    #   * no banned category/keyword -> Review
    #   * a banned category present  -> Blocked
    # Crafted facts: the mock analyzer cannot produce this combination.
    # ============================================================== #
    def test_case_09a_conflict_no_ban_is_review(self):
        decisions = _verdict_from_facts([
            _ai(risk_score=80, confidence_score=0.50, confidence_level="low"),
            UserProfile(age=20, age_group="adult", language="ar"),
        ])
        self.assertEqual(len(decisions), 1, "exactly one Decision (P1)")
        self.assertEqual(decisions[0]["verdict"], "Review")

    def test_case_09b_conflict_with_ban_is_blocked(self):
        decisions = _verdict_from_facts([
            _ai(risk_score=80, confidence_score=0.50, confidence_level="low"),
            UserProfile(age=20, age_group="adult", language="ar"),
            DetectedCategory(value="violence"),
            BannedCategory(value="violence"),
        ])
        self.assertEqual(len(decisions), 1, "exactly one Decision (P1)")
        self.assertEqual(decisions[0]["verdict"], "Blocked")

    # ============================================================== #
    # CASE 10 — risk_score EXACTLY on the high threshold.
    # blood(25) + bet(40) + baseline(10) = 75. The signal rule fires at
    # risk_score >= 75, so exactly 75 is "high" -> Blocked. Asserting the
    # exact 75 proves the boundary is inclusive.
    # ============================================================== #
    def test_case_10_threshold_boundary_75_is_high(self):
        result = _evaluate(_make_input(
            "a documentary about blood and a story about a bet",
            age=20, age_group="adult", language="en",
            banned_categories=["drugs"], banned_keywords=["drug"],
        ))
        self.assertEqual(result["ai_result"]["risk_score"], 75,
                         "this input must sit exactly on the 75 threshold")
        self.assertEqual(result["kbs_result"]["decision"], "Blocked")
        self.assertIn("high_risk", _signal_types(result))

    # ============================================================== #
    # CASE 11 — duplicate-Signal stress test (P2).
    # Three banned categories match and two banned keywords match, yet each
    # signal TYPE must appear EXACTLY once (NOT(Signal(type=...)) guard).
    # ============================================================== #
    def test_case_11_no_duplicate_signals_p2(self):
        result = _evaluate(_make_input(
            "how to kill with a weapon and also bet at the casino",
            age=20, age_group="adult", language="en",
            banned_categories=["violence", "weapons", "gambling"],
            banned_keywords=["kill", "bet"],
        ))
        types = _signal_types(result)
        # multiple categories/keywords matched, but P2 collapses each type:
        self.assertEqual(types.count("banned_category_hit"), 1,
                         "P2: banned_category_hit must appear exactly once")
        self.assertEqual(types.count("keyword_hit"), 1,
                         "P2: keyword_hit must appear exactly once")
        # no signal type at all may be duplicated:
        self.assertEqual(len(types), len(set(types)),
                         "P2: no signal type may be duplicated")

    # ============================================================== #
    # CASE 12 — two different sequential requests stay isolated (P3).
    # A fresh KBSEngine is built per call, so request B must not inherit
    # any fact/signal from request A.
    # ============================================================== #
    def test_case_12_sequential_requests_isolated_p3(self):
        req_a = _make_input(
            "how to kill someone with a weapon",
            age=16, age_group="teen", language="en",
            banned_categories=["gambling"], banned_keywords=["bet"],
        )
        req_b = _make_input(
            "a nature documentary that briefly shows some blood",
            age=16, age_group="teen", language="en",
            source_type="video", source_reputation="trusted",
            banned_categories=["gambling"], banned_keywords=["bet"],
        )

        result_a = _evaluate(req_a)
        result_b = _evaluate(req_b)

        self.assertEqual(result_a["kbs_result"]["decision"], "Blocked")
        self.assertEqual(result_b["kbs_result"]["decision"], "Allowed")
        # P3: B was evaluated on a clean engine — A's high_risk did not leak.
        self.assertNotIn("high_risk", _signal_types(result_b))
        self.assertEqual(_signal_types(result_b), [],
                         "P3: the second request must start from a clean state")


if __name__ == "__main__":
    unittest.main(verbosity=2)
