"""
demo.py  —  Hybrid Content Decision System | Phase 1 Demo
==================================================================
HOW TO RUN (IMPORTANT)
    python demo.py
    from the PROJECT ROOT directory only.

    WRONG:  python demo\demo.py          (breaks imports)
    WRONG:  python -m demo               (unnecessary here)
    RIGHT:  cd hybrid-content-decision-system && python demo.py

WHAT THIS DEMO PROVES (Phase 1 scope)
    1. AI layer  (mock_analyzer)  analyzes content -> dict.
    2. Mapper    (ai_to_kbs_mapper) converts dicts -> Facts.
    3. Engine    (kbs_engine)      holds Facts in working memory.
    4. Engine runs with ZERO rules -> ZERO decisions fired.
    5. Working memory is fully inspectable Fact by Fact.

WHAT IT DOES NOT DO (Phase 2 — Ibrahim & Najat)
    Produce any verdict (Allowed / Warning / Blocked / Review).
    Phase 2 @Rule methods will be added to KBSEngine and will
    fire during engine.run() to produce Decision + Explanation.
==================================================================
"""

from ai_layer.mock_analyzer import analyze
from ai_layer.ai_to_kbs_mapper import build_facts
from engine.kbs_engine import KBSEngine
from facts.all_facts import (
    UserProfile, ParentSettings, ContentInput, AIAnalysis,
    BannedCategory, BannedKeyword, DetectedCategory, SensitiveKeyword,
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
    _section("STEP 3 — Working Memory (after engine.run())")

    rows = engine.list_facts()          # hides experta's internal InitialFact
    rule_count = len(engine.get_rules())

    print(f"  Rules loaded : {rule_count}  ← must be 0 in Phase 1")
    print(f"  Facts in WM  : {len(rows)}")
    print()
    for idx, fact in rows:
        print(f"    f-{idx:<3}  {type(fact).__name__:<20} {fact.as_dict()}")

    print()
    if rule_count == 0:
        print("  [Phase 1 OK] engine.run() fired 0 rules — no decision made.")
        print("  [Phase 2]    Ibrahim & Najat's @Rules will fire here.")
    else:
        print(f"  [WARNING] {rule_count} rule(s) fired — Phase 1 should have 0.")


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
    engine.run()                # Phase 1: 0 rules -> 0 activations -> 0 decisions
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
]


# ==================================================================
# ENTRY POINT
# ==================================================================

if __name__ == "__main__":
    print("\n" + "=" * 62)
    print("  HYBRID CONTENT DECISION SYSTEM — Phase 1 Demo")
    print("  (AI analysis + fact mapping + empty engine)")
    print("  No decisions are made here — that is Phase 2.")
    print("=" * 62)

    for scenario in SCENARIOS:
        run_scenario(
            title=scenario["title"],
            user_data=scenario["user_data"],
            parent_data=scenario["parent_data"],
            content_data=scenario["content_data"],
        )

    print("\n" + "=" * 62)
    print("  Phase 1 complete. All Facts enter the engine correctly.")
    print("  Next: Ibrahim & Najat add @Rule methods to KBSEngine.")
    print("=" * 62 + "\n")
