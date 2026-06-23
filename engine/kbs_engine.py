"""
engine/kbs_engine.py
==================================================================
Phase 1 (Khaled) — the ENGINE SHELL.

WHAT THIS IS
    A subclass of experta's KnowledgeEngine that can:
      * reset()        -> prepare working memory (inherited)
      * load_facts()   -> declare prepared Facts into working memory
      * run()          -> fire the agenda (inherited)
      * print_facts()  -> show what's in working memory

WHAT THIS IS NOT (Phase 1 invariant)
    It contains ZERO @Rule methods and ZERO @DefFacts.
    Zero rules == zero decisions. With no rules, run() fires nothing and
    the Facts simply sit in working memory. That is EXACTLY the Phase 1
    contract: "an empty engine that runs."

PHASE 2 (Ibrahim & Najat)
    They add @Rule methods to THIS class (or a subclass of it). Nothing
    in this file needs to change for that — the shell is the seam between
    Phase 1 plumbing and Phase 2 decision logic.

PURE-experta NOTE
    The only loop here (load_facts) is PLUMBING: it moves already-built
    Facts into memory. It matches nothing and decides nothing. The banned
    pattern is using Python to MAKE a verdict — not this.
==================================================================
"""

from experta import KnowledgeEngine
from experta.fact import InitialFact   # experta declares one of these on reset()


class KBSEngine(KnowledgeEngine):
    """The Knowledge-Based System engine shell (no rules in Phase 1)."""

    # --- intentionally no @Rule / @DefFacts here (see module docstring) ---

    def load_facts(self, facts):
        """Declare an iterable of already-built Fact objects into memory.

        PLUMBING, not logic: this `for` loop just inserts prepared Facts;
        it never inspects them to choose a verdict.

        IMPORTANT: experta requires reset() to be called BEFORE declaring
        (it even logs a warning otherwise), so callers must reset() first.
        On each declare(), experta runs fact.validate() — that's where a
        wrong type or a missing mandatory field is caught early.
        """
        for fact in facts:
            self.declare(fact)

    def list_facts(self, include_initial=False):
        """Return [(idx, fact), ...] currently in working memory.

        experta keeps an internal InitialFact (usually idx 0) after reset();
        we hide it by default so callers see only the project's Facts.
        """
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
            # as_dict() returns only the explicitly-set fields (defaults are
            # lazy and won't appear here), unfrozen for readable printing.
            print(f"  f-{idx}: {type(fact).__name__} -> {fact.as_dict()}")


# ==================================================================
# SMOKE TEST (self-contained; needs experta + Python 3.9.6 env)
# Proves: engine constructs, has ZERO rules, accepts facts, run() fires
# nothing, and working memory is inspectable. Makes NO decisions.
# ==================================================================
if __name__ == "__main__":
    from experta import Fact, Field

    class _Ping(Fact):              # throwaway local fact, just for this test
        value = Field(str)

    engine = KBSEngine()
    engine.reset()                 # REQUIRED before declaring

    # The core Phase-1 invariant, checked programmatically:
    rule_count = len(engine.get_rules())
    print(f"rules loaded: {rule_count}  (Phase 1 MUST be 0)")
    assert rule_count == 0, "Phase 1 violation: engine already has rules!"

    engine.load_facts([_Ping(value="hello"), _Ping(value="world")])
    engine.run()                   # zero rules -> nothing fires, no decisions

    print("working memory (project facts only):")
    engine.print_facts()

    print("\nOK: empty engine runs, holds facts, and decides nothing.")
