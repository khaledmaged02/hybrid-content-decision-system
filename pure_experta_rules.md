# Pure-experta Rules Contract (T0.4)

The rules every member must follow when writing decision logic. This is the
*spec*; the *confirmation that the code obeys it* is in
[docs/pure_experta_review.md](docs/pure_experta_review.md).

---

## The golden rule

1. **No `if/else` decides a final verdict.** Every `Allowed | Warning |
   Blocked | Review` must be produced by an `@Rule` asserting
   `Decision(verdict=...)`. You may never compute the verdict in Python and
   then declare it.
2. **No `for/while` inside rule logic.** Matching many items is done by
   declaring atomic Facts and matching them (see
   [facts_schema.md](facts_schema.md) Section 2), not by looping.

## Where plain Python IS allowed

Python is fine for everything that is **not** choosing a verdict:

- reading the request and splitting it into the contract dicts;
- the AI layer's own content analysis (`ai_layer/`);
- converting dicts → Facts (`ai_to_kbs_mapper.py`);
- engine plumbing (`load_facts`, `run_until_stable`);
- collecting facts and formatting the API payload / explanation string;
- tests.

Rule of thumb: *detecting* "this text mentions a casino" is analysis;
*choosing to block it* is a decision. Python may do the former, never the
latter.

---

## The four mandatory performance improvements

### P1 — `self.halt()` after every final rule
Every decision rule, and the explanation rule, must call `self.halt()` right
after it asserts its `Decision` / `Explanation`. This stops the engine the
instant the verdict is locked (40–60% faster on Blocked cases).

```python
def rule_blocked_banned_category(self):
    self.declare(Decision(verdict="Blocked"))
    self.declare(FinalDecisionMarker())
    self.declare(Reason(rule_name="rule_blocked_banned_category", text="..."))
    self.halt()                      # P1
```

### P2 — `NOT(Signal(type="..."))` on every signal/matching rule
Each signal-producing rule guards its LHS so the same signal type is asserted
at most once, regardless of how many facts match.

```python
@Rule(DetectedCategory(value=MATCH.c),
      BannedCategory(value=MATCH.c),
      NOT(Signal(type="banned_category_hit")))   # P2
def rule_banned_category_hit(self, c):
    self.declare(Signal(type="banned_category_hit", value=c, ...))
```

### P3 — a fresh engine instance per request
`run_decision_engine()` must build a new `KBSEngine()` + `reset()` on every
call. experta is stateful; reusing one instance would mix requests' working
memories.

```python
def run_decision_engine(input_data):
    engine = KBSEngine()             # P3 — never a singleton/global
    engine.reset()
    ...
```

### P4 — case 9 decided by explicit rules
*high risk + low confidence* is ambiguous and must be handled by explicit
rules, never left to a salience tie:

- no banned category/keyword → **Review** (`rule_review_case9`);
- a banned category/keyword present → **Blocked** (the Blocked tier wins on
  salience).

`rule_blocked_high_risk` therefore carries `NOT(Signal(type="low_confidence"))`
so a high-risk item does not auto-block while confidence is low and no banned
hit exists.

---

## Priority by salience (not by code order)

Decision rules run at **negative** salience so they fire only after all
signals exist (signal rules run at salience `0`). Within the decision layer:

```
Blocked (-10..-12)  >  Review (-20..-22)  >  Warning (-30..-31)  >  Allowed (-40)
```

The explanation rule runs last (`-1000`) and, because the decision rules halt,
fires in a second `run()` pass that `KBSEngine.run_until_stable()` performs.

---

## Author checklist (before opening a PR)

- [ ] no `if/else` picks a verdict; no `for/while` in rule logic
- [ ] **P1** every decision/explanation rule ends in `self.halt()`
- [ ] **P2** every signal/matching rule has `NOT(Signal(type="..."))`
- [ ] **P3** `run_decision_engine()` builds a fresh `KBSEngine()`
- [ ] **P4** case 9 is two explicit rules, not a tie
- [ ] Python only in analysis / mapping / plumbing / formatting / tests
