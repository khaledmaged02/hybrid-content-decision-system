"""
rules/decision_rules.py
==================================================================
Phase 2 (Day-2) — DECISION Rules.

These rules read the Signal facts produced by the signal + matching
rules and assert exactly ONE final Decision(verdict=...) per run,
together with a Reason(rule_name, text) that explains it.

The four contract verdicts:  Blocked | Review | Warning | Allowed.

-------------------------------------------------------------------
PRIORITY (contract.md):   Blocked > Review > Warning > Allowed
-------------------------------------------------------------------
The priority is driven by SALIENCE alone, and P1 `self.halt()` makes
it final:

  * Each tier has a higher salience than the tier below it, so when
    several signals appear at once, the strongest verdict's rule is the
    first activation experta picks.
  * MANDATORY (P1): that rule calls self.halt() right after asserting
    Decision + Reason. halt() stops the run, so every weaker rule that
    was ALSO activated never gets to fire. Exactly one verdict.

  Worked example — content with `medium_risk` AND a banned `keyword_hit`:
    both rule_blocked_keyword (salience -11) and rule_warning_medium_risk
    (salience -30) are activated. experta fires the higher one first:
    rule_blocked_keyword -> Decision("Blocked") -> halt(). The Warning
    rule never fires. Final verdict = Blocked. (The strongest wins.)

WHY THE SALIENCE IS NEGATIVE
    The signal + matching rules run at the default salience 0. Decision
    rules MUST run only AFTER every signal has been asserted, otherwise
    `Allowed` (the lowest tier) could fire before any signal exists.
    A NEGATIVE salience puts every decision rule strictly below the
    signal rules on the agenda. Among the decision rules themselves the
    ORDER is what matters: -10 > -20 > -30 > -40 gives
    Blocked > Review > Warning > Allowed.

THE ONE GUARD THAT IS NOT ABOUT PRIORITY — CASE-9 (P4 / T0.5)
    high_risk AND low_confidence is a conflict:
        * a banned category OR keyword hit present -> Blocked
        * otherwise (no banned hit)                -> Review
    Salience+halt already makes the banned/keyword rules win when a hit
    exists. The ONLY extra condition needed is that a high_risk item must
    NOT auto-block when confidence is low and there is no banned hit — so
    rule_blocked_high_risk carries `NOT(Signal(type="low_confidence"))`,
    handing that case to rule_review_case9. That is the single NOT() guard
    in this file, and it is logic, not precedence.

PURE experta
    No `for` loops and no `if` statements. Priority is salience; the only
    branch is the case-9 NOT() pattern above.
==================================================================
"""

from experta import KnowledgeEngine, Rule, NOT

from facts.all_facts import (
    AIAnalysis,
    Signal,
    Decision,
    Reason,
)

# ------------------------------------------------------------------
# Salience ladder — Blocked > Review > Warning > Allowed.
# All NEGATIVE so decisions fire AFTER the signal rules (salience 0).
# Graded WITHIN a tier so that, when several same-tier rules match, the
# most specific one fires first -> deterministic reason text.
# ------------------------------------------------------------------
SAL_BLOCKED = -10
SAL_REVIEW = -20
SAL_WARNING = -30
SAL_ALLOWED = -40


class DecisionRulesMixin(KnowledgeEngine):

    # ==============================================================
    # TIER 1 — BLOCKED   (banned category | keyword hit | high/critical risk)
    # ==============================================================

    @Rule(
        Signal(type="banned_category_hit"),
        salience=SAL_BLOCKED,
    )
    def rule_blocked_banned_category(self):
        self.declare(Decision(verdict="Blocked"))
        self.declare(Reason(
            rule_name="rule_blocked_banned_category",
            text="تم حظر المحتوى لأنه يحتوي على فئة محظورة من إعدادات الأهل."
        ))
        self.halt()

    @Rule(
        Signal(type="keyword_hit"),
        salience=SAL_BLOCKED - 1,
    )
    def rule_blocked_keyword(self):
        self.declare(Decision(verdict="Blocked"))
        self.declare(Reason(
            rule_name="rule_blocked_keyword",
            text="تم حظر المحتوى لاحتوائه على كلمة محظورة من إعدادات الأهل."
        ))
        self.halt()

    # high_risk covers BOTH "high" (75-89) and "critical" (>=90); the
    # signal rule fires at risk_score >= 75. The NOT(low_confidence) guard
    # is the CASE-9 carve-out: a high-risk item is NOT auto-blocked when
    # confidence is low and no banned/keyword hit exists — that goes to
    # rule_review_case9 instead. With a banned/keyword hit the two rules
    # above already win on salience.
    @Rule(
        Signal(type="high_risk"),
        NOT(Signal(type="low_confidence")),
        salience=SAL_BLOCKED - 2,
    )
    def rule_blocked_high_risk(self):
        self.declare(Decision(verdict="Blocked"))
        self.declare(Reason(
            rule_name="rule_blocked_high_risk",
            text="تم حظر المحتوى لأن درجة الخطورة عالية أو حرجة (75 فأكثر)."
        ))
        self.halt()

    # ==============================================================
    # TIER 2 — REVIEW   (case-9 conflict | low confidence | unknown category)
    # ==============================================================

    # CASE-9 (P4): high risk + low confidence. If a banned/keyword hit is
    # present the Blocked tier wins on salience (Blocked > Review), so no
    # extra guard is needed here — this rule simply produces the Review
    # verdict for the no-banned-hit conflict.
    @Rule(
        Signal(type="high_risk"),
        Signal(type="low_confidence"),
        salience=SAL_REVIEW,
    )
    def rule_review_case9(self):
        self.declare(Decision(verdict="Review"))
        self.declare(Reason(
            rule_name="rule_review_case9",
            text=("خطورة عالية مع ثقة منخفضة (الحالة 9)، وفي حال عدم وجود "
                  "فئة أو كلمة محظورة يُحوّل المحتوى إلى المراجعة البشرية.")
        ))
        self.halt()

    # Plain low confidence. If high risk is also present, rule_review_case9
    # (higher salience) fires first and supplies the case-9 reason; here we
    # only need to match low_confidence.
    @Rule(
        Signal(type="low_confidence"),
        salience=SAL_REVIEW - 1,
    )
    def rule_review_low_confidence(self):
        self.declare(Decision(verdict="Review"))
        self.declare(Reason(
            rule_name="rule_review_low_confidence",
            text="ثقة التحليل منخفضة (أقل من 0.55)، لذلك يُحوّل المحتوى إلى المراجعة."
        ))
        self.halt()

    # Unknown category: the AI could not assign a specific category
    # (category == "general") yet flagged a non-low risk (medium_risk).
    # "Unclassified but risky" -> Review. With the current mock analyzer
    # category=="general" always co-occurs with low confidence, so this
    # fires only with a richer AI; the higher Blocked/Review rules win on
    # salience whenever their signals are also present.
    @Rule(
        AIAnalysis(category="general"),
        Signal(type="medium_risk"),
        salience=SAL_REVIEW - 2,
    )
    def rule_review_unknown_category(self):
        self.declare(Decision(verdict="Review"))
        self.declare(Reason(
            rule_name="rule_review_unknown_category",
            text=("الفئة غير معروفة (general) مع خطورة متوسطة، "
                  "لذلك يُحوّل المحتوى إلى المراجعة.")
        ))
        self.halt()

    # ==============================================================
    # TIER 3 — WARNING   (medium risk | age_violation)
    # ==============================================================
    # No "absent signal" guards: any blocking or review signal wins on
    # salience and halts before these rules can fire.

    @Rule(
        Signal(type="medium_risk"),
        salience=SAL_WARNING,
    )
    def rule_warning_medium_risk(self):
        self.declare(Decision(verdict="Warning"))
        self.declare(Reason(
            rule_name="rule_warning_medium_risk",
            text=("درجة الخطورة متوسطة (بين 40 و74) وبدون إشارة أقوى، "
                  "لذلك يصدر تحذير.")
        ))
        self.halt()

    @Rule(
        Signal(type="age_violation"),
        salience=SAL_WARNING - 1,
    )
    def rule_warning_age_violation(self):
        self.declare(Decision(verdict="Warning"))
        self.declare(Reason(
            rule_name="rule_warning_age_violation",
            text=("يوجد تجاوز عمري (العمر المقترح أكبر من عمر المستخدم) "
                  "وبدون إشارة أقوى، لذلك يصدر تحذير.")
        ))
        self.halt()

    # ==============================================================
    # TIER 4 — ALLOWED   (the default — nothing stronger fired)
    # ==============================================================
    # Matches AIAnalysis() so it is activated exactly once per evaluation.
    # Being the LOWEST salience, it only fires when no Blocked/Review/
    # Warning rule fired and halted first. The advisory signals
    # (suspicious_source, language_mismatch) have no decision rule, so they
    # never block this default.
    @Rule(
        AIAnalysis(),
        salience=SAL_ALLOWED,
    )
    def rule_allowed(self):
        self.declare(Decision(verdict="Allowed"))
        self.declare(Reason(
            rule_name="rule_allowed",
            text="لا توجد إشارات سلبية والخطورة منخفضة، لذلك يُسمح بالمحتوى."
        ))
        self.halt()


# ==================================================================
# SMOKE TEST (needs experta + the Python 3.9.6 env)
# Declares CRAFTED Signal/AIAnalysis facts directly (bypassing the mock
# analyzer) so every verdict — including the case-9 conflict that the
# mock cannot produce, and the "strongest wins" combos — is exercised.
# Run:  python -X utf8 -m rules.decision_rules
# ==================================================================
if __name__ == "__main__":
    from rules.signal_rules import SignalRulesMixin
    from rules.matching_rules import MatchingRulesMixin

    class _Engine(SignalRulesMixin, MatchingRulesMixin, DecisionRulesMixin):
        """Full rule stack, same MRO the real KBSEngine uses."""

    # An AIAnalysis fact is present in every real evaluation; the Allowed
    # default and the unknown-category rule both need one to match.
    BASE_AI = dict(
        category="general", risk_score=10, risk_level="low",
        confidence_score=0.9, confidence_level="high",
        suggested_min_age=0, language="ar", analyzer_type="mock",
    )

    def _verdict(signal_facts, ai_overrides=None):
        """Run the engine over a crafted AIAnalysis + Signal facts."""
        eng = _Engine()
        eng.reset()
        eng.declare(AIAnalysis(**{**BASE_AI, **(ai_overrides or {})}))
        for f in signal_facts:                       # plumbing: declare crafted facts
            eng.declare(f)
        eng.run()
        return [fact["verdict"] for _, fact in eng.facts.items()
                if isinstance(fact, Decision)]

    cases = {
        # name: (signals, ai_overrides, expected_verdict)
        "Blocked (banned category)": ([Signal(type="banned_category_hit")], None, "Blocked"),
        "Blocked (keyword hit)": ([Signal(type="keyword_hit")], None, "Blocked"),
        "Blocked (high risk)": ([Signal(type="high_risk")], None, "Blocked"),
        "Blocked (STRONGEST WINS: medium_risk + keyword_hit)": (
            [Signal(type="medium_risk"), Signal(type="keyword_hit")], None, "Blocked"),
        "Blocked (case-9 WITH banned hit)": (
            [Signal(type="high_risk"), Signal(type="low_confidence"),
             Signal(type="banned_category_hit")], None, "Blocked"),
        "Review (CASE-9: high risk + low conf, no banned)": (
            [Signal(type="high_risk"), Signal(type="low_confidence")], None, "Review"),
        "Review (low confidence)": ([Signal(type="low_confidence")], None, "Review"),
        "Review (unknown category + medium risk)": (
            [Signal(type="medium_risk")], {"category": "general"}, "Review"),
        "Warning (medium risk)": (
            [Signal(type="medium_risk")], {"category": "gambling"}, "Warning"),
        "Warning (age violation)": ([Signal(type="age_violation")], None, "Warning"),
        "Allowed (advisory signal only)": ([Signal(type="language_mismatch")], None, "Allowed"),
        "Allowed (truly clean)": ([], None, "Allowed"),
    }

    print("=== DECISION RULE SMOKE TEST (salience + halt) ===\n")
    all_ok = True
    for name, (signals, ai_over, want) in cases.items():
        verdicts = _verdict(signals, ai_over)
        got = verdicts[0] if len(verdicts) == 1 else f"{verdicts!r} (expected exactly 1)"
        ok = (len(verdicts) == 1) and (verdicts[0] == want)
        all_ok = all_ok and ok
        print(f"  [{'OK  ' if ok else 'FAIL'}] {name:<52} -> {got}")

    print("\nP1 check: each case asserts EXACTLY ONE Decision (halt stops the rest).")
    print("ALL OK" if all_ok else "SOME CASES FAILED")
