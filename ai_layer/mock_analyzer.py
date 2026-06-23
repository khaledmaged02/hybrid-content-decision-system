"""
ai_layer/mock_analyzer.py
==================================================================
Phase 1 (Khaled) — the FAKE ("mock") AI layer.

ROLE IN THE PIPELINE
    Content Input
      -> [THIS FILE] AI Layer .......... analyzes content -> ANALYSIS
      -> AI-to-KBS Mapper (Task 4) ..... turns analysis into experta Facts
      -> KBS Rules (Phase 2) ........... make the explainable DECISION

WHAT IT RETURNS
    A plain Python dict whose keys are EXACTLY the 10 AIAnalysis contract
    fields. It deliberately does NOT import experta and does NOT build
    Facts — converting analysis into Facts is the Mapper's job (Task 4).
    Keeping the AI layer ignorant of experta is the whole point of the
    "hybrid" design: the analyst and the judge are separate.

PURE-experta NOTE (read this carefully)
    The if/for code below is ANALYSIS — the AI's own reasoning about the
    content — which the project explicitly allows as plain Python. It NEVER
    emits a verdict (Allowed/Warning/Blocked/Review) and never decides what
    happens to the user. The 4 verdicts come ONLY from Phase 2 rules.
    Detecting "this text mentions a casino" is analysis; choosing to BLOCK
    it is a decision. This file does the former, never the latter.
==================================================================
"""

# Hardcoded so the contract field `analyzer_type` is always correct here.
ANALYZER_TYPE = "mock"

# A tiny pretend "model knowledge": keyword -> (category, risk_weight, min_age).
# This stands in for a real ML model. The team can edit this dict to craft
# test cases for Phase 2 rules without touching any logic.
LEXICON = {
    "kill":   ("violence", 45, 16),
    "blood":  ("violence", 25, 13),
    "weapon": ("weapons",  35, 16),
    "bet":    ("gambling", 40, 18),
    "casino": ("gambling", 45, 18),
    "drug":   ("drugs",    50, 18),
    "hate":   ("hate",     40, 16),
}


def _risk_level(score):
    """AI metadata: label the numeric risk. This is the AI describing
    itself, NOT a verdict. (Phase 2's risk *decision* is a separate Rule.)"""
    if score >= 90:
        return "critical"
    if score >= 75:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _confidence_level(score):
    """AI metadata: label its own confidence. NOT a verdict.
    0.55 is intentional — Phase 2 treats confidence_score < 0.55 as low."""
    if score < 0.55:
        return "low"
    if score < 0.80:
        return "medium"
    return "high"


def analyze(text, source_type="text", source_reputation="unknown", language="ar"):
    """Pretend to analyze `text` and return an AIAnalysis-shaped dict.

    Inputs mirror the ContentInput contract (text/source_type/source_reputation).
    Output keys are the EXACT 10 AIAnalysis field names so the Mapper (Task 4)
    can consume the dict directly with zero renaming.
    """
    lowered = (text or "").lower()

    detected_categories = []
    sensitive_keywords = []
    risk_score = 10          # baseline: nothing is ever perfectly "safe"
    suggested_min_age = 0

    # --- AI ANALYSIS (allowed plain Python; NOT a KBS decision) -----------
    # Scanning content for known signals is the AI's job. This loop builds
    # ANALYSIS data; it does not pick a verdict for any user.
    for keyword, (category, weight, min_age) in LEXICON.items():
        if keyword in lowered:
            sensitive_keywords.append(keyword)
            if category not in detected_categories:
                detected_categories.append(category)
            risk_score += weight
            suggested_min_age = max(suggested_min_age, min_age)

    # Source reputation nudges the AI's risk estimate (still analysis).
    if source_reputation == "suspicious":
        risk_score += 15
    elif source_reputation == "trusted":
        risk_score -= 5

    risk_score = max(0, min(100, risk_score))   # clamp to contract range 0..100

    # Confidence: the more distinct categories it recognised, the surer it is.
    if not sensitive_keywords:
        confidence_score = 0.50                 # recognised nothing -> unsure
    else:
        confidence_score = min(0.95, 0.60 + 0.10 * len(set(detected_categories)))
    confidence_score = round(confidence_score, 2)

    # Primary category = first thing detected, else a neutral label.
    category = detected_categories[0] if detected_categories else "general"

    # The dict's keys are the AIAnalysis contract fields — exact spelling.
    return {
        "category": category,
        "risk_score": risk_score,
        "risk_level": _risk_level(risk_score),
        "confidence_score": confidence_score,
        "confidence_level": _confidence_level(confidence_score),
        "detected_categories": detected_categories,
        "sensitive_keywords": sensitive_keywords,
        "suggested_min_age": suggested_min_age,
        "language": language,
        "analyzer_type": ANALYZER_TYPE,
    }


# ==================================================================
# SMOKE TEST (plain-Python plumbing; no experta, no decisions)
# Run directly to see varied, contract-shaped analysis output.
# ==================================================================
if __name__ == "__main__":
    samples = [
        ("Lets go to the casino and bet tonight", "text", "unknown"),
        ("A cute video about puppies", "video", "trusted"),
        ("how to kill someone with a weapon", "text", "suspicious"),
    ]
    for sample_text, s_type, s_rep in samples:
        print(f"\nINPUT: {sample_text!r}  (source_reputation={s_rep})")
        result = analyze(sample_text, source_type=s_type, source_reputation=s_rep)
        for key, val in result.items():
            print(f"   {key:20} = {val}")

    print("\nOK: mock analyzer returns AIAnalysis-shaped dicts (no verdicts).")
