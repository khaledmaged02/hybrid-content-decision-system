"""
facts/all_facts.py
==================================================================
Phase 1 (Khaled) — FOUNDATION: every Fact definition in the
Hybrid Content Decision System.

WHAT A "FACT" IS
----------------
A Fact is one unit of knowledge the experta engine reasons over.
Think of it as a typed record placed into the engine's working memory.
Phase 2 Rules (Ibrahim & Najat) will MATCH against these Facts to produce
a Decision + Explanation.

WHAT THIS FILE IS / IS NOT
--------------------------
IS:     pure data shapes (Fact classes + their fields).
IS NOT: rules, decisions, thresholds, if/else, or loops.
        ==> Zero decision logic here. That is "Pure experta" Phase 2.

CONTRACT LOCK
-------------
Field names below are copied EXACTLY from the agreed data contract.
Do not rename them — Phase 2 rules will rely on `MATCH.<field>`.
==================================================================
"""

from experta import Fact, Field


# ==================================================================
# SECTION 1 — CORE ENTITY FACTS
# One Fact per real-world entity. These carry the full context that
# enters the engine once per evaluation.
# ==================================================================

class UserProfile(Fact):
    """Who we are deciding for (e.g. a child).

    Phase 2 will compare suggested_min_age (from AIAnalysis) against `age`
    to detect an age violation — but that comparison is a RULE, not done here.
    """
    age = Field(int, mandatory=True)            # e.g. 10
    age_group = Field(str, mandatory=True)      # "child" | "teen" | "adult"
    language = Field(str, mandatory=True)       # "ar" | "en" | ...


class ParentSettings(Fact):
    """Parent / guardian configuration.

    CONTRACT (facts_schema §2): this Fact holds ONLY protection_level.
    The banned lists are NOT stored here — the mapper explodes each element
    straight into separate BannedCategory / BannedKeyword Facts (SECTION 2),
    and the rules match THOSE. (Pure experta: no `for x in list` to decide.)
    """
    protection_level = Field(str, mandatory=True)   # "low" | "medium" | "high"


class ContentInput(Fact):
    """The raw content being evaluated + where it came from.

    CONTRACT (facts_schema §2): source_type / source_reputation have defaults,
    so a caller may construct ContentInput(text=...) alone.
    """
    text = Field(str, mandatory=True)
    source_type = Field(str, default="text")             # "text" | "video" | "image"
    source_reputation = Field(str, default="unknown")    # "trusted" | "unknown" | "suspicious"


class AIAnalysis(Fact):
    """The AI layer's analysis. This is ANALYSIS, never a decision.

    CONTRACT (facts_schema §2): the detected_categories / sensitive_keywords
    lists are NOT stored here. The mapper explodes them into DetectedCategory /
    SensitiveKeyword Facts (SECTION 2), which the rules match — never an inline list.
    """
    category = Field(str, mandatory=True)              # single top category
    risk_score = Field(int, mandatory=True)            # 0..100
    risk_level = Field(str, mandatory=True)            # "low"|"medium"|"high"|"critical"
    confidence_score = Field(float, mandatory=True)    # 0.0..1.0  (keep it a float!)
    confidence_level = Field(str, mandatory=True)      # "low"|"medium"|"high"
    suggested_min_age = Field(int, mandatory=True)     # compared to UserProfile.age IN A RULE
    language = Field(str, mandatory=True)              # "ar" | "en" | ...
    analyzer_type = Field(str, default="mock")         # "mock" | "simple" | "full"


# ==================================================================
# SECTION 2 — LIST-ITEM ("ATOMIC") FACTS
# Every element of a contract list becomes ONE of these Facts so that
# Phase 2 rules can match items WITHOUT any Python loop.
#
# CONTRACT LOCK: the field is named `value` on ALL of them, so Ibrahim
# & Najat write `MATCH.value` consistently everywhere.
#
# Example Phase 2 rule (NOT written here, just to show the intent):
#   Rule(DetectedCategory(value=MATCH.c), BannedCategory(value=MATCH.c))
#   -> a detected category that is also banned  =>  Blocked
# ==================================================================

class BannedCategory(Fact):
    """One banned category from ParentSettings.banned_categories."""
    value = Field(str, mandatory=True)


class BannedKeyword(Fact):
    """One banned keyword from ParentSettings.banned_keywords."""
    value = Field(str, mandatory=True)


class DetectedCategory(Fact):
    """One category from AIAnalysis.detected_categories."""
    value = Field(str, mandatory=True)


class SensitiveKeyword(Fact):
    """One keyword from AIAnalysis.sensitive_keywords."""
    value = Field(str, mandatory=True)


# ==================================================================
# SECTION 3 — OUTPUT FACTS (produced BY Phase 2 rules)
# ------------------------------------------------------------------
# These are the Facts that Ibrahim & Najat's RULES will ASSERT while the
# engine reasons. Phase 1 only DEFINES their shape — Phase 1 never asserts
# them from Python logic (that would be deciding outside experta).
# Fields below are locked to the contract; defaults are applied by experta
# when the Fact is declared into the engine.
# ==================================================================

class Signal(Fact):
    """An intermediate finding raised by a rule, so rules can chain:
    one rule raises a Signal, later rules read Signals to reach a verdict.

    `value` here is a generic payload (e.g. the keyword that hit) and is
    UNRELATED to the SECTION 2 atomic-fact `value` field.
    """
    type = Field(str, mandatory=True)        # "high_risk" | "keyword_hit" | ...
    severity = Field(str, default="medium")
    source_rule = Field(str, default="")
    value = Field(str, default="")


class Decision(Fact):
    """The single chosen verdict — one of the 4 contract values."""
    verdict = Field(str, mandatory=True)     # "Allowed"|"Warning"|"Blocked"|"Review"


class Reason(Fact):
    """One human-readable reason contributed by a specific rule.
    Many Reason Facts may exist; an Explanation aggregates their text."""
    rule_name = Field(str, mandatory=True)
    text = Field(str, mandatory=True)


class Explanation(Fact):
    """The final aggregated explanation tied to the chosen verdict."""
    verdict = Field(str, mandatory=True)
    reasons_text = Field(str, mandatory=True)


class FinalDecisionMarker(Fact):
    """Guard Fact: once asserted, the verdict is locked so no later rule
    overrides it (prevents conflicting decisions within one run)."""
    locked = Field(bool, default=True)


# ==================================================================
# SMOKE TEST  (plain-Python plumbing — allowed; NOT system logic)
# Run this file directly to prove every Fact instantiates with the
# exact contract field names. It makes ZERO decisions.
# ==================================================================
if __name__ == "__main__":
    user = UserProfile(age=10, age_group="child", language="ar")
    parents = ParentSettings(
        protection_level="high",
    )
    content = ContentInput(
        text="sample content text",
        source_type="text",
        source_reputation="unknown",
    )
    analysis = AIAnalysis(
        category="violence",
        risk_score=82,
        risk_level="high",
        confidence_score=0.91,
        confidence_level="high",
        suggested_min_age=16,
        language="ar",
        analyzer_type="mock",
    )

    atomic_facts = [
        BannedCategory(value="violence"),
        BannedKeyword(value="kill"),
        DetectedCategory(value="violence"),
        SensitiveKeyword(value="kill"),
    ]

    # Constructing the output Facts here is SHAPE-VERIFICATION ONLY — it
    # proves the classes accept the contract fields. It is NOT a decision;
    # in the real system these are asserted by Phase 2 rules, not Python.
    output_facts = [
        Signal(type="high_risk", severity="high", source_rule="R_high_risk"),
        Signal(type="keyword_hit"),  # severity/source_rule/value -> defaults in-engine
        Decision(verdict="Blocked"),
        Reason(rule_name="R_high_risk", text="risk_score 82 >= 75"),
        Explanation(verdict="Blocked", reasons_text="Blocked due to high risk."),
        FinalDecisionMarker(),       # locked -> default True in-engine
    ]

    print("=== Entity Facts ===")
    for f in (user, parents, content, analysis):
        print(f"  {type(f).__name__}: {f}")

    print("\n=== Atomic (list-item) Facts ===")
    for f in atomic_facts:
        print(f"  {type(f).__name__}: {f}")

    print("\n=== Output Facts (shape only; asserted BY Phase 2 rules) ===")
    for f in output_facts:
        print(f"  {type(f).__name__}: {f}")

    print("\nOK: all Fact classes instantiate with the exact contract fields.")
