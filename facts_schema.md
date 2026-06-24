# Fact Schema (T0.3)

The single source of truth for every `experta` Fact in the system. It is the
shared contract all three members code against, so the pieces fit at merge
time. The authoritative implementation is [facts/all_facts.py](facts/all_facts.py);
this file documents it.

> **List rule (important):** list fields (banned categories/keywords, detected
> categories, sensitive keywords) are **not** stored on a Fact. The mapper
> explodes every element into its own atomic Fact (Section 2) so rules match
> items **without any Python loop**.

---

## Section 1 — Input / context Facts

### `ContentInput` — the content being evaluated
| field | type | required | values |
|-------|------|----------|--------|
| `text` | str | yes | the raw content |
| `source_type` | str | no (default `text`) | `text` \| `video` \| `image` |
| `source_reputation` | str | no (default `unknown`) | `trusted` \| `unknown` \| `suspicious` |

### `UserProfile` — who is consuming the content
| field | type | required | values |
|-------|------|----------|--------|
| `age` | int | yes | e.g. `10` |
| `age_group` | str | yes | `child` \| `teen` \| `adult` |
| `language` | str | yes | `ar` \| `en` \| … |

### `ParentSettings` — guardian / system configuration
| field | type | required | values |
|-------|------|----------|--------|
| `protection_level` | str | yes | `low` \| `medium` \| `high` |

> The banned lists live as atomic `BannedCategory` / `BannedKeyword` Facts,
> not on this Fact.

### `AIAnalysis` — the AI layer's analysis (never a verdict)
| field | type | required | values |
|-------|------|----------|--------|
| `category` | str | yes | top category, e.g. `violence`, or `general` |
| `risk_score` | int | yes | `0..100` |
| `risk_level` | str | yes | `low` \| `medium` \| `high` \| `critical` |
| `confidence_score` | float | yes | `0.0..1.0` (must be a real float) |
| `confidence_level` | str | yes | `low` \| `medium` \| `high` |
| `suggested_min_age` | int | yes | compared to `UserProfile.age` in a rule |
| `language` | str | yes | `ar` \| `en` \| … |
| `analyzer_type` | str | no (default `mock`) | `mock` \| `simple` \| `full` |

> The detected-categories / sensitive-keywords lists live as atomic
> `DetectedCategory` / `SensitiveKeyword` Facts, not on this Fact.

---

## Section 2 — Atomic ("list-item") Facts

One Fact per list element. **All four use the field name `value`**, so rules
write `MATCH.value` consistently.

| Fact | field | source |
|------|-------|--------|
| `BannedCategory` | `value: str` | `ParentSettings.banned_categories[i]` |
| `BannedKeyword` | `value: str` | `ParentSettings.banned_keywords[i]` |
| `DetectedCategory` | `value: str` | `AIAnalysis.detected_categories[i]` |
| `SensitiveKeyword` | `value: str` | `AIAnalysis.sensitive_keywords[i]` |

This is what lets a rule match *"a detected category that is also banned"*
without iterating a list:

```python
Rule(DetectedCategory(value=MATCH.c), BannedCategory(value=MATCH.c)) -> Signal(...)
```

---

## Section 3 — Output Facts (asserted by rules only)

| Fact | fields | asserted by |
|------|--------|-------------|
| `Signal` | `type: str`, `severity: str=medium`, `source_rule: str=""`, `value: str=""` | signal + matching rules |
| `Reason` | `rule_name: str`, `text: str` | any rule that contributes an explanation line |
| `Decision` | `verdict: str` | decision rules (exactly one) |
| `Explanation` | `verdict: str`, `reasons_text: str` | explanation rule (exactly one) |
| `FinalDecisionMarker` | `locked: bool=True` | decision rules — guard against a second verdict |

### Signal `type` values
`high_risk`, `medium_risk`, `low_confidence`, `age_violation`,
`language_mismatch`, `suspicious_source`, `banned_category_hit`, `keyword_hit`.

---

## The four final verdicts

| verdict | meaning | when |
|---------|---------|------|
| `Allowed` | allow the content | low risk, no negative signal |
| `Warning` | show a warning | medium risk or age violation, nothing stronger |
| `Blocked` | block the content | banned category, banned keyword, or high/critical risk |
| `Review` | send to human review | low confidence, unknown category, or the case-9 conflict |

Priority when several apply: **Blocked > Review > Warning > Allowed**
(enforced by salience + `self.halt()` — see
[pure_experta_rules.md](pure_experta_rules.md)).
