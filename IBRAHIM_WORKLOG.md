# Ibrahim — Work Log (Day-2, Phase 2)

**Tasks completed:** T2.1 (four decision rules + P1 + P4) and T2.2 (priority arbitration via salience).
**Date:** 2026-06-24 · **Branch:** `ibrahim-branch`

This file is a handoff note for my colleagues. If you continue with Claude/ChatGPT,
paste this file plus [contract.md](contract.md) so the AI knows the current state and
the design rules before it writes anything.

---

## 1. TL;DR — what I built

The **decision layer**: the rules that read the `Signal` facts (made on Day-1) and
produce the **one final verdict** — `Blocked` / `Review` / `Warning` / `Allowed` — with a
`Reason`. Before my work the engine stopped at Signals and produced no verdict.

- ✅ T2.1 — four decision verdicts as Pure-experta rules, `self.halt()` in every rule (P1),
  case-9 resolved as an explicit rule (P4).
- ✅ T2.2 — priority **Blocked > Review > Warning > Allowed** via `salience`; the strongest
  decision wins when several signals appear.

All verified (see §5). No `if`/`else` and no `for`/`while` in the rule logic.

---

## 2. Files I ADDED

| File | What it is |
|---|---|
| [rules/decision_rules.py](rules/decision_rules.py) | **The decision layer.** `DecisionRulesMixin` with 9 `@Rule`s across the 4 verdict tiers. Has a `__main__` smoke test (run it — see §5). |
| [contract.md](contract.md) | Documents the decision contract: priority, exact thresholds, the case-9 resolution (T0.5/P4), and edge cases. This is the spec for the decision layer. |
| [IBRAHIM_WORKLOG.md](IBRAHIM_WORKLOG.md) | This handoff note. |

## 3. Files I MODIFIED

| File | Change |
|---|---|
| [engine/kbs_engine.py](engine/kbs_engine.py) | Added `DecisionRulesMixin` to the `KBSEngine` mixin chain (import + class bases) so the decision rules actually run. Updated the header comment. Fixed two stale strings in its `__main__` smoke test that said "Signals/Reasons only". |
| [demo.py](demo.py) | Added **STEP 4 — Decision** display (prints the verdict + reason). Replaced the old "Day-1 = 0 decisions" check with a "P1: exactly one Decision" check. Added two scenarios (**WARNING** and **ALLOWED**) so the demo exercises all four reachable verdicts. Updated the header/footer text. |

> Environment note: I also created a **Python 3.9.6 virtualenv** at `.venv/` (the project
> pins `experta==1.9.4` / `frozendict==1.2`, which need 3.9.x). `.venv/` is gitignored.

---

## 4. How the decision layer works (read before editing)

**Flow:** `Signals` (Day-1) → decision rules → **one** `Decision(verdict=...)` + `Reason(rule_name, text)`.

**Priority is driven by `salience`, made final by `self.halt()` (P1):**

```
Blocked (-10..-12)  >  Review (-20..-22)  >  Warning (-30..-31)  >  Allowed (-40)
```

- When several signals appear, every matching rule is *activated*, but experta fires the
  **highest-salience** one first; it `halt()`s, so the weaker rules **never fire**.
  Example (verified): `medium_risk` + banned `keyword_hit` → **Blocked**.
- **Salience is NEGATIVE on purpose.** The signal rules run at the default `salience = 0`.
  Decision rules must run *after* all signals exist, so they sit below 0. Among themselves
  the order `-10 > -20 > -30 > -40` gives the Blocked>Review>Warning>Allowed priority.
  ⚠️ **Do not make these positive** — a positive `Allowed` rule would fire before any
  signal exists and always return Allowed.

**Case-9 (P4 / T0.5) — `high_risk` AND `low_confidence`:**
- banned category/keyword present → **Blocked** (the Blocked-tier rules win on salience)
- otherwise → **Review** (`rule_review_case9`)
- This is the ONLY `NOT()` guard in the file: `rule_blocked_high_risk` carries
  `NOT(Signal(type="low_confidence"))` so a low-confidence high-risk item is not
  auto-blocked. That guard is *logic*, not precedence — leave it.

**Rules (all assert `Decision` + `Reason`, then `halt()`):**

| Verdict | Rule(s) | Fires on |
|---|---|---|
| Blocked | `rule_blocked_banned_category`, `rule_blocked_keyword`, `rule_blocked_high_risk` | banned category, keyword hit, or high/critical risk |
| Review | `rule_review_case9`, `rule_review_low_confidence`, `rule_review_unknown_category` | case-9 conflict, low confidence, or unknown category + risk |
| Warning | `rule_warning_medium_risk`, `rule_warning_age_violation` | medium risk or age violation |
| Allowed | `rule_allowed` (matches `AIAnalysis()`, lowest salience) | the default — nothing stronger fired |

Reason texts are in **Arabic** (matches the Day-1 signal rules and T2.4's Arabic explanation goal).

---

## 5. How to run & verify

The repo uses a Python **3.9.6** venv. On Windows the console is cp1252 and will crash on
the Arabic/box characters, so run in **UTF-8 mode**:

```powershell
$env:PYTHONUTF8 = 1
# full pipeline demo (5 scenarios, each ends in one verdict):
.\.venv\Scripts\python.exe -X utf8 demo.py
# decision-layer smoke test (12 crafted cases, incl. case-9 both ways):
.\.venv\Scripts\python.exe -X utf8 -m rules.decision_rules
```

**Verified results (last run):**
- Smoke test: **12/12 OK**, each case asserts exactly one `Decision` (P1 honoured),
  including `medium_risk + keyword_hit → Blocked` and both case-9 branches.
- Demo: SAFE→Review, BLOCK→Blocked, BORDERLINE→Blocked, WARNING→Warning, ALLOWED→Allowed.

**Two known quirks (documented in [contract.md](contract.md) §5):** with the current *mock*
analyzer, (a) case-9 can't occur (high risk always raises confidence ≥0.60), and (b) clean
unrecognised content scores confidence 0.50 → Review, so `Allowed` is hard to reach. The
rules are correct for a real AI; both are covered by the crafted smoke test.

---

## 6. What is NOT done yet (for whoever continues)

Day-2 tasks still open (not mine):
- **T2.3** (Najat) — `FinalDecisionMarker` double-judgment guard (extra safety on top of halt+salience).
- **T2.4** (Najat) — Arabic Explanation rules (`explanation_rules.py`), `self.halt()` after the explanation (P1).
- **T2.5** (Khaled) — `run_decision_engine(input_data)` returning `{ai_result, kbs_result, explanation}`; fresh `KnowledgeEngine()` per call (P3).
- **T3.1** (Khaled) — 12 test cases in `tests/`.
- **T3.2** (Ibrahim) — Pure-experta audit report (verify P1/P2/P3/P4).

Day-1 documentation gaps still missing (the *code* is all done): `README.md`,
`facts_schema.md`, `pure_experta_rules.md`, and the `tests/` + `docs/` folders. `contract.md`
currently covers the decision contract (T0.5) but not the full T0.2 field-by-field data contract.

**Optional follow-up on my own work:** P4's detail text suggests case-9 as *two* explicit
rules. I wrote the Review branch explicitly and let the Blocked branch fall through to the
banned/keyword rules via salience (behaviour is correct and tested). If you want literal
symmetry, add a dedicated `rule_blocked_case9`.

---

## 7. Design rules to respect if you edit the decision layer

1. **No `if/else` and no `for/while` to decide** a verdict — it must come out of a `@Rule`.
2. Every final-decision rule ends with **`self.halt()`** (P1).
3. Keep decision-rule **salience negative** and in the order Blocked>Review>Warning>Allowed.
4. Don't add cross-tier `NOT(signal)` guards back — salience+halt handles precedence. The
   only logic guard is the case-9 `NOT(low_confidence)` on `rule_blocked_high_risk`.
5. Plain Python is fine for mapping/printing/tests — just not for choosing the verdict.
