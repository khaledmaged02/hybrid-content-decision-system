"""
engine/decision_service.py
==================================================================
T2.5 — API-ready decision service.

This file connects the full pipeline:

Input data
→ Mock AI Analyzer
→ AI-to-KBS Mapper
→ KBSEngine
→ Experta Decision  (+ Experta Explanation)
→ API-ready output

Important:
This file does NOT decide Allowed / Warning / Blocked / Review, and it does
NOT compose the explanation text. Both the final Decision(verdict=...) and
the aggregated Explanation(reasons_text=...) must already exist as Experta
facts. Python here only runs the pipeline, validates the output, and formats
the response (e.g. wrapping the Explanation's reasons_text with the AI
confidence for the API payload).
==================================================================
"""

from ai_layer.mock_analyzer import analyze
from ai_layer.ai_to_kbs_mapper import build_facts
from engine.kbs_engine import KBSEngine

from facts.all_facts import Decision, Reason, Signal, Explanation


def _facts_of_type(engine, fact_type):
    """
    Collect facts of a specific type from working memory.

    This is output collection only.
    It does not decide the final verdict.
    """
    return [
        fact
        for _, fact in engine.list_facts()
        if isinstance(fact, fact_type)
    ]


def _fact_to_dict(fact):
    """Convert an Experta Fact into a plain dictionary for output."""
    return dict(fact.as_dict())


def _collect_triggered_rules(signals, reasons):
    """
    Collect triggered rule names from Signal and Reason facts.

    This does not choose a decision.
    It only documents what rules participated.
    """
    triggered_rules = []

    for signal in signals:
        signal_dict = signal.as_dict()
        source_rule = signal_dict.get("source_rule")
        if source_rule and source_rule not in triggered_rules:
            triggered_rules.append(source_rule)

    for reason in reasons:
        reason_dict = reason.as_dict()
        rule_name = reason_dict.get("rule_name")
        if rule_name and rule_name not in triggered_rules:
            triggered_rules.append(rule_name)

    return triggered_rules


def _build_arabic_explanation(verdict, ai_result, reason_text, signals):
    """
    Build the Arabic explanation string.

    This function does NOT choose the verdict.
    It receives the verdict that Experta already produced.
    """

    verdict_ar = {
        "Blocked": "تم حظر المحتوى",
        "Review": "تم تحويل المحتوى للمراجعة",
        "Warning": "تم إصدار تحذير للمحتوى",
        "Allowed": "تم السماح بالمحتوى",
    }.get(verdict, f"القرار النهائي هو {verdict}")

    signal_names = []

    for signal in signals:
        signal_type = signal.as_dict().get("type")
        if signal_type:
            signal_names.append(signal_type)

    if signal_names:
        signals_text = "الإشارات التي أثرت على القرار: " + ", ".join(signal_names) + "."
    else:
        signals_text = "لم تظهر إشارات خطورة مؤثرة."

    ai_text = (
        f"تحليل الـ AI صنّف المحتوى ضمن فئة '{ai_result.get('category')}' "
        f"بدرجة خطورة {ai_result.get('risk_score')} "
        f"ومستوى ثقة {ai_result.get('confidence_level')} "
        f"({ai_result.get('confidence_score')})."
    )

    return f"{verdict_ar}. {ai_text} {signals_text} السبب: {reason_text}"


def run_decision_engine(input_data):
    """
    Run one complete evaluation request.

    P3:
    A fresh KBSEngine instance is created for every request.
    This prevents Working Memory contamination between requests.

    input_data expected shape:
    {
        "text": "...",
        "source_type": "text/video/image",
        "source_reputation": "trusted/unknown/suspicious",
        "age": 10,
        "age_group": "child",
        "language": "ar",
        "protection_level": "high",
        "banned_categories": [...],
        "banned_keywords": [...]
    }
    """

    # --------------------------------------------------------------
    # 1. Split API-style input into the existing project contract
    # --------------------------------------------------------------
    user_data = {
        "age": int(input_data["age"]),
        "age_group": input_data["age_group"],
        "language": input_data["language"],
    }

    parent_data = {
        "protection_level": input_data["protection_level"],
        "banned_categories": list(input_data.get("banned_categories", [])),
        "banned_keywords": list(input_data.get("banned_keywords", [])),
    }

    content_data = {
        "text": input_data["text"],
        "source_type": input_data.get("source_type", "text"),
        "source_reputation": input_data.get("source_reputation", "unknown"),
    }

    # --------------------------------------------------------------
    # 2. AI layer — analysis only, no decision
    # --------------------------------------------------------------
    ai_result = analyze(
        text=content_data["text"],
        source_type=content_data["source_type"],
        source_reputation=content_data["source_reputation"],
        language=user_data["language"],
    )

    # --------------------------------------------------------------
    # 3. Mapper — convert dictionaries into Experta Facts
    # --------------------------------------------------------------
    facts = build_facts(
        user_data=user_data,
        parent_data=parent_data,
        content_data=content_data,
        analysis_data=ai_result,
    )

    # --------------------------------------------------------------
    # 4. Fresh KBS engine per request — P3
    # --------------------------------------------------------------
    engine = KBSEngine()
    engine.reset()
    engine.load_facts(facts)
    engine.run_until_stable()   # decision phase (P1 halt) + explanation phase (P1 halt)

    # --------------------------------------------------------------
    # 5. Collect facts produced by Experta
    # --------------------------------------------------------------
    decisions = _facts_of_type(engine, Decision)
    reasons = _facts_of_type(engine, Reason)
    signals = _facts_of_type(engine, Signal)
    explanations = _facts_of_type(engine, Explanation)

    # Validation only — we do NOT choose a fallback decision/explanation in
    # Python. Both must come from Experta: exactly one of each (P1).
    if len(decisions) != 1:
        raise RuntimeError(
            f"Expected exactly one Decision from Experta, but got {len(decisions)}."
        )
    if len(explanations) != 1:
        raise RuntimeError(
            f"Expected exactly one Explanation from Experta, but got {len(explanations)}."
        )

    verdict = decisions[0]["verdict"]
    # The aggregated reason text is produced by the experta Explanation rule
    # (T2.4), not joined here. Python below only PRESENTS it for the API.
    reason_text = explanations[0]["reasons_text"]
    triggered_rules = _collect_triggered_rules(signals, reasons)
    explanation = _build_arabic_explanation(
        verdict=verdict,
        ai_result=ai_result,
        reason_text=reason_text,
        signals=signals,
    )

    return {
        "ai_result": ai_result,
        "kbs_result": {
            "decision": verdict,
            "reason": reason_text,
            "triggered_rules": triggered_rules,
            "signals": [_fact_to_dict(signal) for signal in signals],
        },
        "explanation": explanation,
    }


# ==================================================================
# SMOKE TEST
# Run:
#   python -m engine.decision_service
# ==================================================================
if __name__ == "__main__":
    sample_input = {
        "text": "how to kill someone with a weapon",
        "source_type": "text",
        "source_reputation": "suspicious",
        "age": 10,
        "age_group": "child",
        "language": "ar",
        "protection_level": "high",
        "banned_categories": ["violence", "weapons"],
        "banned_keywords": ["kill", "weapon"],
    }

    result = run_decision_engine(sample_input)

    print("AI Result:")
    print(result["ai_result"])

    print("\nKBS Result:")
    print(result["kbs_result"])

    print("\nArabic Explanation:")
    print(result["explanation"])