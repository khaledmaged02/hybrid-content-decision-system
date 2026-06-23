"""
ai_layer/ai_to_kbs_mapper.py
==================================================================
Phase 1 (Khaled) — the AI-to-KBS MAPPER.

ROLE IN THE PIPELINE
    Content Input
    -> AI Layer (mock_analyzer.py) ........... produces analysis dict
    -> [THIS FILE] AI-to-KBS Mapper .......... converts dicts -> Facts
    -> KBS Engine (kbs_engine.py) ............ holds Facts in memory
    -> KBS Rules (Phase 2) ................... match Facts -> Decision

WHY THIS FILE EXISTS
    The AI layer speaks plain Python dicts.
    experta speaks Facts.
    This file is the translator. Neither layer needs to know the
    other exists — the AI doesn't import experta; the rules don't
    know where the data came from.

WHAT THIS FILE DOES
    1. Builds one entity Fact for each of the 4 contract entities.
    2. Explodes every list field into separate atomic Facts so that
       Phase 2 rules can match individual items WITHOUT any Python loop.
    3. Returns a flat list — callers pass it straight to load_facts().

PURE-experta NOTE
    The `for` loops below are CONVERSION, not decisions. They iterate
    a list to create Facts — exactly what the contract says "plain Python
    IS allowed for". The banned pattern is using a loop to CHOOSE a
    verdict. These loops never read a value and branch on it.
==================================================================
"""

from facts.all_facts import (
    UserProfile, ParentSettings, ContentInput, AIAnalysis,
    BannedCategory, BannedKeyword, DetectedCategory, SensitiveKeyword,
)


def build_facts(user_data, parent_data, content_data, analysis_data):
    """Convert four plain dicts into a flat list of experta Facts.

    Parameters
    ----------
    user_data     : dict   Keys: age(int), age_group(str), language(str)
    parent_data   : dict   Keys: protection_level, banned_categories(list),
                                 banned_keywords(list)
    content_data  : dict   Keys: text, source_type, source_reputation
    analysis_data : dict   Keys: the 10 AIAnalysis contract fields
                                 (as returned by mock_analyzer.analyze())

    Returns
    -------
    list[Fact]    A flat list of all Facts ready for engine.load_facts().
                  Order: entity Facts first, then atomic Facts (lists).
                  The engine doesn't care about order, but it makes the
                  printed working memory easier to read in demo.py.
    """
    facts = []

    # ------------------------------------------------------------------
    # SECTION A — Entity Facts (one per contract entity)
    # ------------------------------------------------------------------

    facts.append(UserProfile(
        age=int(user_data["age"]),          # int guard: never accidentally str
        age_group=user_data["age_group"],
        language=user_data["language"],
    ))

    facts.append(ParentSettings(
        protection_level=parent_data["protection_level"],
        # CONTRACT (facts_schema §2): the banned lists are NOT stored on the
        # Fact. They are exploded into atomic BannedCategory / BannedKeyword
        # Facts in SECTION B below, straight from parent_data.
    ))

    facts.append(ContentInput(
        text=content_data["text"],
        source_type=content_data["source_type"],
        source_reputation=content_data["source_reputation"],
    ))

    facts.append(AIAnalysis(
        category=analysis_data["category"],
        risk_score=int(analysis_data["risk_score"]),     # int guard
        risk_level=analysis_data["risk_level"],
        # CRITICAL: Field(float) rejects a bare int (isinstance(1, float) is
        # False in Python). Always cast to float here so experta's validate()
        # never raises on a value like 1 or 0.
        confidence_score=float(analysis_data["confidence_score"]),
        confidence_level=analysis_data["confidence_level"],
        # CONTRACT (facts_schema §2): detected_categories / sensitive_keywords
        # are NOT stored on the Fact — they are exploded into atomic
        # DetectedCategory / SensitiveKeyword Facts in SECTION B below.
        suggested_min_age=int(analysis_data["suggested_min_age"]),  # int guard
        language=analysis_data["language"],
        analyzer_type=analysis_data["analyzer_type"],
    ))

    # ------------------------------------------------------------------
    # SECTION B — Atomic Facts (one Fact per list element)
    # ------------------------------------------------------------------
    # FIELD NAME CONTRACT: all atomic Facts use `value=` (not `name=`),
    # so Phase 2 rules use MATCH.value consistently across all four types.
    #
    # Example of a Phase 2 rule this enables (NOT written here):
    #   Rule(DetectedCategory(value=MATCH.c), BannedCategory(value=MATCH.c))
    #   => a detected category IS a banned category -> raise a Signal
    # ------------------------------------------------------------------

    # From ParentSettings
    for cat in parent_data["banned_categories"]:
        facts.append(BannedCategory(value=cat))

    for kw in parent_data["banned_keywords"]:
        facts.append(BannedKeyword(value=kw))

    # From AIAnalysis
    for cat in analysis_data["detected_categories"]:
        facts.append(DetectedCategory(value=cat))

    for kw in analysis_data["sensitive_keywords"]:
        facts.append(SensitiveKeyword(value=kw))

    return facts


# ==================================================================
# SMOKE TEST (needs experta + Python 3.9.6 env)
# Runs a full end-to-end conversion and prints every Fact that
# would enter the engine. Makes ZERO decisions.
# ==================================================================
if __name__ == "__main__":
    # -- Sample inputs (mirror the demo scenario) --------------------
    user_data = {
        "age": 10,
        "age_group": "child",
        "language": "ar",
        "protection_level": "high",    # mapper reads this from user_data
    }

    parent_data = {
        "protection_level": "high",
        "banned_categories": ["violence", "gambling"],
        "banned_keywords": ["kill", "bet"],
    }

    content_data = {
        "text": "how to kill someone with a weapon",
        "source_type": "text",
        "source_reputation": "suspicious",
    }

    # Simulate what mock_analyzer.analyze() returns
    analysis_data = {
        "category": "violence",
        "risk_score": 100,
        "risk_level": "critical",
        "confidence_score": 0.8,       # float (also test int->float cast below)
        "confidence_level": "high",
        "detected_categories": ["violence", "weapons"],
        "sensitive_keywords": ["kill", "weapon"],
        "suggested_min_age": 16,
        "language": "ar",
        "analyzer_type": "mock",
    }

    all_facts = build_facts(user_data, parent_data, content_data, analysis_data)

    entity_types = (UserProfile, ParentSettings, ContentInput, AIAnalysis)

    print("=== ENTITY FACTS ===")
    for f in all_facts:
        if isinstance(f, entity_types):
            print(f"  {type(f).__name__}: {f.as_dict()}")

    print("\n=== ATOMIC (LIST-ITEM) FACTS ===")
    for f in all_facts:
        if not isinstance(f, entity_types):
            print(f"  {type(f).__name__}(value={f['value']!r})")

    print(f"\nTotal Facts built: {len(all_facts)}")

    # Verify the float-cast guard works on an int input
    analysis_data_int_confidence = {**analysis_data, "confidence_score": 1}
    all_facts_int = build_facts(user_data, parent_data, content_data,
                                analysis_data_int_confidence)
    ai_fact = next(f for f in all_facts_int if isinstance(f, AIAnalysis))
    assert isinstance(ai_fact["confidence_score"], float), \
        "BUG: confidence_score must be float, not int"
    print("Float-cast guard OK: int confidence_score -> float in AIAnalysis.")

    print("\nOK: mapper produces all Facts with correct types and field names.")
