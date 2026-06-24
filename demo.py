"""
demo.py  —  Hybrid Content Decision System | Phase 1 Demo
==================================================================
HOW TO RUN (IMPORTANT)
    python demo.py
    from the PROJECT ROOT directory only.

    WRONG:  python demo\demo.py          (breaks imports)
    WRONG:  python -m demo               (unnecessary here)
    RIGHT:  cd hybrid-content-decision-system && python demo.py

WHAT THIS DEMO PROVES
    1. AI layer  (mock_analyzer)  analyzes content -> dict.
    2. Mapper    (ai_to_kbs_mapper) converts dicts -> Facts.
    3. Engine    (kbs_engine)      holds Facts in working memory.
    4. Signal + Matching rules fire -> Signal + Reason facts.
    5. Each signal type appears EXACTLY once (P2 verification).
    6. Decision rules read those Signals -> ONE final verdict
       (Blocked / Review / Warning / Allowed) + its Reason.
       Priority Blocked > Review > Warning > Allowed — see contract.md.

STILL TO COME (T2.2+)
    Explanation rules will aggregate the Reason facts into a single
    Explanation tied to the chosen verdict.
==================================================================
"""

from ai_layer.mock_analyzer import analyze
from ai_layer.ai_to_kbs_mapper import build_facts
from engine.kbs_engine import KBSEngine
from facts.all_facts import (
    UserProfile, ParentSettings, ContentInput, AIAnalysis,
    BannedCategory, BannedKeyword, DetectedCategory, SensitiveKeyword,
    Signal, Reason, Decision,
)

# ── Atomic Fact types as a set for isinstance checks in print helpers ──
ATOMIC_TYPES = (BannedCategory, BannedKeyword, DetectedCategory, SensitiveKeyword)
ENTITY_TYPES = (UserProfile, ParentSettings, ContentInput, AIAnalysis)


# ==================================================================
# DISPLAY HELPERS (pure plumbing / printing — no decisions)
# ==================================================================

def _header(title):
    line = "=" * 62
    print(f"\n{line}")
    print(f"  SCENARIO: {title}")
    print(line)


def _section(label):
    print(f"\n  {'─' * 56}")
    print(f"  {label}")
    print(f"  {'─' * 56}")


def _print_analysis(analysis_dict):
    _section("STEP 1 — AI Analysis (mock_analyzer output)")
    skip = {"detected_categories", "sensitive_keywords"}   # printed separately
    for k, v in analysis_dict.items():
        if k not in skip:
            print(f"    {k:<22} = {v}")
    print(f"    {'detected_categories':<22} = {analysis_dict['detected_categories']}")
    print(f"    {'sensitive_keywords':<22} = {analysis_dict['sensitive_keywords']}")


def _print_facts(all_facts):
    _section("STEP 2 — Facts built by Mapper (before engine entry)")

    print("  Entity Facts:")
    for f in all_facts:
        if isinstance(f, ENTITY_TYPES):
            d = f.as_dict()
            print(f"    [{type(f).__name__}]")
            for k, v in d.items():
                print(f"      {k:<22} = {v}")

    print("\n  Atomic (list-item) Facts:")
    for f in all_facts:
        if isinstance(f, ATOMIC_TYPES):
            print(f"    {type(f).__name__:<20} value = {f['value']!r}")

    print(f"\n  Total Facts: {len(all_facts)}")


def _print_engine_state(engine):
    _section("STEP 3 — Engine run: Signals produced")

    rows = engine.list_facts()          # hides experta's internal InitialFact
    rule_count = len(engine.get_rules())

    signals   = [f for _, f in rows if isinstance(f, Signal)]
    reasons   = [f for _, f in rows if isinstance(f, Reason)]
    decisions = [f for _, f in rows if isinstance(f, Decision)]

    print(f"  Rules loaded   : {rule_count}  (signal + matching + decision)")
    print(f"  Facts in WM    : {len(rows)}")
    print(f"  Signals raised : {len(signals)}")

    print("\n  Signals:")
    if not signals:
        print("    (none — this content produced no risk/match signals)")
    for s in signals:
        d = s.as_dict()
        print(f"    • {d['type']:<22} severity={d.get('severity', ''):<7}"
              f" by {d.get('source_rule', '')}")

    print("\n  Reasons (explainability payload, one per fired rule):")
    for r in reasons:
        print(f"    - {r['text']}")

    # P2 verification: each signal type must appear EXACTLY once
    types = [s['type'] for s in signals]
    duplicates = sorted({t for t in types if types.count(t) > 1})

    print()
    if duplicates:
        print(f"  [P2 FAIL] duplicated signal types: {duplicates}")
    else:
        print("  [P2 OK]   every signal type appears exactly once.")

    # ── STEP 4: the final verdict produced by the decision rules ──────
    _section("STEP 4 — Decision: the final verdict")

    decision_reasons = [r for r in reasons
                        if r['rule_name'].startswith(("rule_blocked_",
                                                      "rule_review_",
                                                      "rule_warning_",
                                                      "rule_allowed"))]
    for d in decisions:
        print(f"  VERDICT : {d['verdict']}")
    for r in decision_reasons:
        print(f"  Reason  : {r['text']}")

    # P1 invariant: the decision rules assert EXACTLY ONE Decision (halt).
    if len(decisions) == 1:
        print("\n  [P1 OK]   exactly one Decision asserted (self.halt() honoured).")
    else:
        print(f"\n  [P1 FAIL] expected 1 Decision, got {len(decisions)}.")


# ==================================================================
# CORE: run one full scenario end-to-end
# ==================================================================

def run_scenario(title, user_data, parent_data, content_data):
    """Wire AI -> Mapper -> Engine for one scenario and print every step."""

    _header(title)

    # Print the raw inputs so the reader knows what we're evaluating
    print(f"\n  User  : age={user_data['age']} | "
          f"group={user_data['age_group']} | "
          f"lang={user_data['language']}")
    print(f"  Parent: protection={parent_data['protection_level']} | "
          f"banned_cats={parent_data['banned_categories']}")
    print(f"  Content: \"{content_data['text']}\"")
    print(f"           source_type={content_data['source_type']} | "
          f"reputation={content_data['source_reputation']}")

    # ── STEP 1: AI layer analyzes the content ──────────────────────
    analysis = analyze(
        text=content_data["text"],
        source_type=content_data["source_type"],
        source_reputation=content_data["source_reputation"],
        language=user_data["language"],
    )
    _print_analysis(analysis)

    # ── STEP 2: Mapper converts dicts -> Facts ─────────────────────
    all_facts = build_facts(user_data, parent_data, content_data, analysis)
    _print_facts(all_facts)

    # ── STEP 3: Engine loads Facts and runs ────────────────────────
    engine = KBSEngine()
    engine.reset()              # REQUIRED before declare (initialises RETE)
    engine.load_facts(all_facts)
    engine.run()                # signal + matching rules, then ONE decision rule
    _print_engine_state(engine)


# ==================================================================
# THREE DEMO SCENARIOS
# chosen to cover the main threshold boundaries Phase 2 will decide on:
#   - clearly safe   (low risk, trusted source, no banned hits)
#   - clearly blocked (critical risk, suspicious source, banned category hit)
#   - borderline     (medium risk, unknown source, age gap, low confidence)
# ==================================================================

SCENARIOS = [
    {
        "title": "SAFE — child / puppet video / trusted source",
        "user_data": {
            "age": 8,
            "age_group": "child",
            "language": "ar",
        },
        "parent_data": {
            "protection_level": "high",
            "banned_categories": ["violence", "gambling", "drugs"],
            "banned_keywords": ["kill", "bet", "drug"],
        },
        "content_data": {
            "text": "A cute video about puppies playing in the garden",
            "source_type": "video",
            "source_reputation": "trusted",
        },
    },
    {
        "title": "BLOCK — child / violent text / suspicious source",
        "user_data": {
            "age": 10,
            "age_group": "child",
            "language": "ar",
        },
        "parent_data": {
            "protection_level": "high",
            "banned_categories": ["violence", "weapons"],
            "banned_keywords": ["kill", "weapon"],
        },
        "content_data": {
            "text": "how to kill someone with a weapon",
            "source_type": "text",
            "source_reputation": "suspicious",
        },
    },
    {
        "title": "BORDERLINE — teen / gambling / unknown source",
        "user_data": {
            "age": 15,
            "age_group": "teen",
            "language": "en",
        },
        "parent_data": {
            "protection_level": "medium",
            "banned_categories": ["gambling"],
            "banned_keywords": ["bet"],
        },
        "content_data": {
            "text": "lets go to the casino tonight",
            "source_type": "text",
            "source_reputation": "unknown",
        },
    },
    {
        # medium_risk (bet -> 50) but the category/keyword are NOT banned
        # and the adult user clears suggested_min_age -> WARNING, not Blocked.
        "title": "WARNING — adult / gambling not banned / medium risk",
        "user_data": {
            "age": 20,
            "age_group": "adult",
            "language": "en",
        },
        "parent_data": {
            "protection_level": "medium",
            "banned_categories": ["drugs"],
            "banned_keywords": ["drug"],
        },
        "content_data": {
            "text": "thinking about going to bet on the match",
            "source_type": "text",
            "source_reputation": "unknown",
        },
    },
    {
        # one low-weight keyword (blood -> risk 30, low) recognised so
        # confidence is 0.70 (NOT low), category not banned, user old
        # enough -> ZERO negative signals -> ALLOWED.
        "title": "ALLOWED — teen / recognised but harmless / trusted source",
        "user_data": {
            "age": 16,
            "age_group": "teen",
            "language": "en",
        },
        "parent_data": {
            "protection_level": "medium",
            "banned_categories": ["gambling"],
            "banned_keywords": ["bet"],
        },
        "content_data": {
            "text": "a nature documentary that briefly shows some blood",
            "source_type": "video",
            "source_reputation": "trusted",
        },
    },
]


# ==================================================================
# ENTRY POINT
# ==================================================================

if __name__ == "__main__":
    print("\n" + "=" * 62)
    print("  HYBRID CONTENT DECISION SYSTEM — Demo")
    print("  AI analysis + fact mapping + Signal/Matching + Decision rules")
    print("  Each scenario ends in ONE verdict: Blocked/Review/Warning/Allowed.")
    print("=" * 62)

    for scenario in SCENARIOS:
        run_scenario(
            title=scenario["title"],
            user_data=scenario["user_data"],
            parent_data=scenario["parent_data"],
            content_data=scenario["content_data"],
        )

    print("\n" + "=" * 62)
    print("  Complete: AI -> Facts -> Signals -> ONE Decision per scenario.")
    print("  Next (T2.2+): Explanation rules aggregate Reasons per verdict.")
    print("=" * 62 + "\n")
