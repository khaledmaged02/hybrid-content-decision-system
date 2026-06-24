# Decision Contract — Hybrid Content Decision System

Scope: the **decision layer** ([rules/decision_rules.py](rules/decision_rules.py)).
It reads the `Signal` facts produced by the signal rules
([rules/signal_rules.py](rules/signal_rules.py)) and matching rules
([rules/matching_rules.py](rules/matching_rules.py)) and asserts **exactly one**
`Decision(verdict=...)` plus a `Reason(rule_name, text)` per evaluation.

Verdicts: `Blocked` · `Review` · `Warning` · `Allowed`.

---

## 1. Priority

```
Blocked  >  Review  >  Warning  >  Allowed
```

If several signals appear at once, the **strongest verdict wins**, driven by
salience and made final by `halt()`:

1. **`salience`** *(the priority driver)* — each tier outranks the one below it
   (Blocked > Review > Warning > Allowed). When several rules are activated,
   experta picks the highest-salience one first.
2. **`self.halt()`** *(Mandatory P1)* — that rule halts the run immediately after
   asserting its `Decision` + `Reason`. Every weaker rule that was *also*
   activated never fires. Exactly one verdict per run.

> **Example.** Content with `medium_risk` **and** a banned `keyword_hit`:
> `rule_blocked_keyword` (salience −11) and `rule_warning_medium_risk` (−30) are
> both activated; experta fires the Blocked rule first → `Decision("Blocked")` →
> `halt()`. The Warning rule never fires. **Final verdict = Blocked.**

There is **one** `NOT(...)` guard in the whole layer, and it is *logic, not
precedence*: the **case-9 carve-out** on `rule_blocked_high_risk` (see §4). Every
other rule simply matches its trigger signal and relies on salience + halt.

### Why salience is negative
The signal + matching rules run at the default `salience = 0`. Decision rules
must run **after** every signal exists; otherwise `Allowed` (the lowest tier,
the default verdict) would fire before any signal is raised. Every decision rule
therefore uses a **negative** salience, placing it strictly below the signal
rules on the agenda. Among the decision rules the *order* is what matters:
`-10 > -20 > -30 > -40` gives Blocked > Review > Warning > Allowed.

### Pure experta
No `for` loops and no `if` statements in the decision layer. Priority is
salience; the only branch is the case-9 `NOT()` pattern (§4).

---

## 2. Signal thresholds (exact numbers)

Produced upstream; the decision rules only match on `Signal(type=...)`.

| Signal `type`         | Fires when                                              | Severity |
|-----------------------|--------------------------------------------------------|----------|
| `high_risk`           | `risk_score >= 75` (covers **high 75–89** & **critical ≥ 90**) | high |
| `medium_risk`         | `40 <= risk_score < 75`                                 | medium   |
| `low_confidence`      | `confidence_score < 0.55`                               | medium   |
| `age_violation`       | `suggested_min_age > user_age`                          | medium   |
| `language_mismatch`   | `content_language != user_language`                    | low      |
| `suspicious_source`   | `source_reputation == "suspicious"`                    | medium   |
| `banned_category_hit` | a `DetectedCategory.value` equals a `BannedCategory.value` | high  |
| `keyword_hit`         | a `SensitiveKeyword.value` equals a `BannedKeyword.value`  | high  |

There is **no separate `critical` signal** — `high_risk` at `>= 75` already
covers high and critical risk.

---

## 3. Decision rules (tiers, triggers, guards, salience)

Each rule matches only its trigger and relies on salience + halt for precedence;
the single `NOT()` guard is the case-9 carve-out.

| Tier | Rule | Verdict | Trigger (LHS) | salience |
|------|------|---------|---------------|----------|
| 1 | `rule_blocked_banned_category` | **Blocked** | `banned_category_hit` | −10 |
| 1 | `rule_blocked_keyword` | **Blocked** | `keyword_hit` | −11 |
| 1 | `rule_blocked_high_risk` | **Blocked** | `high_risk` **and** `NOT(low_confidence)` ← case-9 carve-out | −12 |
| 2 | `rule_review_case9` | **Review** | `high_risk` + `low_confidence` | −20 |
| 2 | `rule_review_low_confidence` | **Review** | `low_confidence` | −21 |
| 2 | `rule_review_unknown_category` | **Review** | `AIAnalysis(category="general")` + `medium_risk` | −22 |
| 3 | `rule_warning_medium_risk` | **Warning** | `medium_risk` | −30 |
| 3 | `rule_warning_age_violation` | **Warning** | `age_violation` | −31 |
| 4 | `rule_allowed` | **Allowed** | `AIAnalysis()` (the default — fires only if nothing stronger did) | −40 |

Plain-English summary:

- **Blocked** — a banned category, a banned keyword, or high/critical risk.
- **Review** — the case-9 conflict (§4), low confidence, or an unknown category
  with risk.
- **Warning** — medium risk or an age violation. (No "absent" guards needed: any
  stronger signal wins on salience and halts first.)
- **Allowed** — the default; fires only when no stronger rule fired.

Graded salience **within** a tier (e.g. −10, −11, −12) means that when several
same-tier rules match, the most specific one fires first — so the reported
reason is deterministic even though the verdict is identical. For example, with
both `high_risk` and `low_confidence`, `rule_review_case9` (−20) outranks
`rule_review_low_confidence` (−21) and supplies the case-9 reason.

---

## 4. Case-9 (Mandatory P4 / T0.5) — `high_risk` **and** `low_confidence`

A strong risk signal the AI is **not confident** about is a conflict. Resolved
rule:

| Has a banned category **or** keyword hit? | Verdict |
|-------------------------------------------|---------|
| **Yes** | **Blocked** — handled by `rule_blocked_banned_category` / `rule_blocked_keyword`, which fire regardless of confidence. |
| **No**  | **Review** — handled by `rule_review_case9`; the conflict goes to a human. |

The Blocked side is why `rule_blocked_high_risk` carries `NOT(low_confidence)`:
without a banned/keyword hit, a low-confidence high-risk item must **not** be
auto-blocked — it must be reviewed.

---

## 5. Edge cases & invariants

1. **Exactly one verdict (P1).** The salience values are all distinct, so exactly
   one decision rule is the top activation; it calls `self.halt()`, ending the
   run before any weaker rule fires. The smoke test asserts exactly one
   `Decision` in every case, including when several signals are present at once
   (e.g. `medium_risk` + `keyword_hit` → one `Blocked`).

2. **Exhaustive.** Every possible signal combination maps to exactly one tier;
   `rule_allowed` (matching `AIAnalysis()`, lowest salience) is the catch-all that
   fires only when no stronger rule fired.

3. **`suspicious_source` and `language_mismatch` are advisory.** They have **no**
   decision rule of their own, so on their own they never change the verdict —
   `rule_allowed` still fires alongside them. They contribute to the `Reason`
   trail only. *(In [demo.py](demo.py) the analyzer is always called with
   `content_language = user_language`, so `language_mismatch` never fires there.)*

4. **Case-9 is currently unreachable through the mock analyzer.** In
   [ai_layer/mock_analyzer.py](ai_layer/mock_analyzer.py), `high_risk` (`>= 75`)
   requires detected keywords, and any detected keyword pushes
   `confidence_score >= 0.60` — never `< 0.55`. So `high_risk` and
   `low_confidence` cannot co-occur via the mock. The rule exists for a **real**
   AI that can report high risk with low confidence, and is exercised by the
   crafted smoke test in [rules/decision_rules.py](rules/decision_rules.py).

5. **`Allowed` is hard to reach through the mock.** Unrecognised content scores
   `confidence_score = 0.50` (`< 0.55`) → `low_confidence` → **Review**. `Allowed`
   needs a *recognised but not-banned* keyword (so `confidence ≈ 0.70`) whose
   risk stays low and whose `suggested_min_age` does not exceed the user's age —
   e.g. the demo's ALLOWED scenario ("blood", risk 30, teen age 16).

6. **`rule_review_unknown_category` does not fire through the mock** either,
   because `category == "general"` always co-occurs with `low_confidence` there.
   It is documented and reserved for a richer analyzer that can be confident
   about a risk it cannot categorise.

---

## 6. Verified behaviour (demo scenarios)

`python -X utf8 demo.py` (UTF-8 mode required on Windows — see §7):

| Scenario | Key signals | Verdict |
|----------|-------------|---------|
| SAFE — puppies / trusted | `low_confidence` | **Review** |
| BLOCK — kill+weapon / suspicious | banned + keyword + high_risk + … | **Blocked** |
| BORDERLINE — casino / gambling banned | `banned_category_hit` + … | **Blocked** |
| WARNING — bet / gambling not banned / adult | `medium_risk` | **Warning** |
| ALLOWED — blood / not banned / teen | *(none)* | **Allowed** |

The `rules/decision_rules.py` smoke test additionally proves both case-9
branches and the multi-blocking-signal case.

---

## 7. Running note (Windows)

Reason texts are in Arabic and the demo uses Unicode box-drawing characters. The
Windows console defaults to cp1252 and will raise `UnicodeEncodeError`. Run in
UTF-8 mode:

```powershell
$env:PYTHONUTF8 = 1
python -X utf8 demo.py
```
