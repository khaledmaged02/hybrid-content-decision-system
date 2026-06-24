"""
engine/kbs_engine.py
==================================================================
Phase 1 (Khaled) — ENGINE SHELL.
Phase 2 (Najat / Ibrahim) — rules live in /rules/, imported via mixins.

KBSEngine inherits from:
  SignalRulesMixin   -> rules/signal_rules.py   (Najat, T1.4)
  MatchingRulesMixin -> rules/matching_rules.py (Ibrahim / Najat, T1.5-T1.6)
  DecisionRulesMixin -> rules/decision_rules.py (Day-2, T2.1) — the final
                        Blocked/Review/Warning/Allowed verdict.

This file contains ONLY plumbing: load_facts, list_facts, print_facts.
Explanation rules (T2.2+) will be added as additional mixins next.

PURE-experta NOTE
    The only loop here (load_facts) is PLUMBING: it moves already-built
    Facts into memory. It matches nothing and decides nothing.
==================================================================
"""

from experta.fact import InitialFact

from rules.signal_rules import SignalRulesMixin
from rules.matching_rules import MatchingRulesMixin
from rules.decision_rules import DecisionRulesMixin
from rules.explanation_rules import ExplanationRulesMixin


class KBSEngine(
    SignalRulesMixin,
    MatchingRulesMixin,
    DecisionRulesMixin,
    ExplanationRulesMixin,
):
    """The Knowledge-Based System engine.

    Inherits all @Rule methods from the mixin chain:
      SignalRulesMixin / MatchingRulesMixin -> Signal + Reason facts
      DecisionRulesMixin                    -> ONE Decision (+ halt, P1)
      ExplanationRulesMixin                 -> ONE Explanation (+ halt, P1)

    Add future rule mixins to the base list here — nothing else changes.
    """

    def load_facts(self, facts):
        """Declare an iterable of already-built Fact objects into memory.

        PLUMBING, not logic: this `for` loop just inserts prepared Facts;
        it never inspects them to choose a verdict.

        IMPORTANT: experta requires reset() to be called BEFORE declaring
        (it even logs a warning otherwise), so callers must reset() first.
        """
        for fact in facts:
            self.declare(fact)

    def run_until_stable(self, max_phases=8):
        """Run every rule PHASE, not just the first.

        PLUMBING, not logic. Each final rule calls self.halt() (P1), which
        ends the current run() the instant a verdict — and later the
        explanation — is asserted. The decision phase and the explanation
        phase are therefore two separate run() passes. This helper simply
        keeps calling run() until working memory stops growing, so callers
        never have to know how many halt-terminated phases there are.

        It chooses NO verdict; it only resumes the agenda experta froze.
        """
        previous = -1
        for _ in range(max_phases):
            self.run()
            current = len(self.facts)
            if current == previous:
                break
            previous = current

    def list_facts(self, include_initial=False):
        """Return [(idx, fact), ...] currently in working memory."""
        return [
            (idx, fact)
            for idx, fact in self.facts.items()
            if include_initial or not isinstance(fact, InitialFact)
        ]

    def print_facts(self, include_initial=False):
        """Pretty-print working memory. Demo helper; pure plumbing."""
        rows = self.list_facts(include_initial=include_initial)
        if not rows:
            print("  (no project facts in working memory)")
            return
        for idx, fact in rows:
            print(f"  f-{idx}: {type(fact).__name__} -> {fact.as_dict()}")


# ==================================================================
# SMOKE TEST (Phase 2)
# ==================================================================
if __name__ == "__main__":
    from facts.all_facts import (
        ContentInput,
        UserProfile,
        ParentSettings,
        AIAnalysis,
        DetectedCategory,
        SensitiveKeyword,
        BannedCategory,
        BannedKeyword,
    )

    engine = KBSEngine()
    engine.reset()

    print(f"rules loaded: {len(engine.get_rules())}  (signal + matching + decision + explanation)")

    engine.load_facts([
        ContentInput(
            text="فيديو يحتوي على تهديد",
            source_type="video",
            source_reputation="suspicious"
        ),
        UserProfile(age=10, age_group="child", language="ar"),
        ParentSettings(
            protection_level="high",
            banned_categories=["violence", "adult", "drugs"],
            banned_keywords=["تهديد", "قتل"]
        ),
        AIAnalysis(
            category="violence",
            risk_score=88,
            risk_level="high",
            confidence_score=0.87,
            confidence_level="high",
            detected_categories=["violence"],
            sensitive_keywords=["تهديد"],
            suggested_min_age=16,
            language="ar",
            analyzer_type="mock"
        ),
        DetectedCategory(value="violence"),
        SensitiveKeyword(value="تهديد"),
        BannedCategory(value="violence"),
        BannedCategory(value="adult"),
        BannedCategory(value="drugs"),
        BannedKeyword(value="تهديد"),
        BannedKeyword(value="قتل"),
    ])

    engine.run_until_stable()   # decision phase + explanation phase

    print("\nworking memory after rules:")
    engine.print_facts()
    print("\nOK: rules run -> Signals/Reasons, then ONE Decision, then ONE Explanation.")
