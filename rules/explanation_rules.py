"""
rules/explanation_rules.py
==================================================================
Phase 2 (Day-2) — EXPLANATION Rules (T2.4 + P1).

After the decision rules have asserted exactly ONE Decision(verdict=...),
this layer asserts exactly ONE Explanation(verdict, reasons_text) that
aggregates every Reason fact produced during the run.

The Explanation is a real experta FACT produced by a real experta RULE —
not a value computed in Python by the service. The service only READS it.

-------------------------------------------------------------------
WHY A SEPARATE "PHASE" / SECOND run()
-------------------------------------------------------------------
Each decision rule ends with self.halt() (P1). halt() terminates the
CURRENT run() immediately, so a single run() can never reach this rule —
the agenda is frozen the moment the verdict is chosen.

experta keeps the agenda across runs: calling engine.run() a SECOND time
resumes it. By then the Decision exists and every decision rule is
deactivated by its NOT(FinalDecisionMarker()) guard (T2.3), so the only
activation left is this explanation rule. It fires once, asserts the
Explanation, and halts (P1 again).

KBSEngine.run_until_stable() (plumbing) performs the two phases so callers
never have to remember to run() twice.

PURE experta
    The verdict is NOT decided here — it is read from the Decision fact via
    MATCH.verdict. The only Python is string-joining the already-produced
    Reason texts: output formatting, not decision logic.
==================================================================
"""

from experta import KnowledgeEngine, Rule, MATCH, NOT

from facts.all_facts import (
    Decision,
    Reason,
    Explanation,
)

# Fire strictly AFTER every decision rule. Decision salience ladder runs
# from -10 (Blocked) down to -40 (Allowed); -1000 guarantees this rule is
# last on the agenda no matter how the ladder grows later.
SAL_EXPLANATION = -1000


class ExplanationRulesMixin(KnowledgeEngine):

    @Rule(
        Decision(verdict=MATCH.verdict),
        NOT(Explanation()),
        salience=SAL_EXPLANATION,
    )
    def rule_build_explanation(self, verdict):
        # String formatting only — gather the Reason texts the rules left
        # in working memory. This decides NOTHING; the verdict already came
        # from the Decision fact above.
        reason_texts = [
            fact["text"]
            for _, fact in self.facts.items()
            if isinstance(fact, Reason)
        ]
        reasons_text = " | ".join(reason_texts) if reason_texts \
            else "لم يتم تسجيل سبب تفصيلي للقرار."

        self.declare(Explanation(verdict=verdict, reasons_text=reasons_text))
        self.halt()   # P1: stop once the final explanation is asserted.
