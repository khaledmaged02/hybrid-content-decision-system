# Hybrid Content Decision System
### نظام هجين لاتخاذ قرارات إدارة المحتوى

A knowledge-based backend that decides what to do with a piece of content —
**Allowed / Warning / Blocked / Review** — and explains *why*, in Arabic.

It is **hybrid**: an AI layer *analyzes* the content, and a Pure-`experta`
rule engine *decides*. The AI never picks the verdict; the rules never look
at the raw content. The analyst and the judge are separate on purpose.

```
Content Input
  → AI Layer (mock_analyzer)        analyzes  → analysis dict
  → AI-to-KBS Mapper                converts  → experta Facts
  → KBS Engine (Pure experta)       reasons   → Signals → ONE Decision
  → Explanation rule                aggregates→ ONE Explanation (Arabic)
  → decision_service                formats   → API-ready result
```

---

## Why Pure experta for the decision core?

The verdict logic is written entirely as `@Rule`s — no `if/else` chooses a
verdict, no `for/while` lives inside rule logic. This is slightly slower than
hand-written `if/else`, and that trade is deliberate:

| reason | detail |
|--------|--------|
| **Explainability** | every verdict is tied to a named rule that emits a `Reason` and `triggered_rules`. You cannot get that cleanly from `if/else`. |
| **The AI is the real bottleneck** | a real AI model costs 200–2000 ms; experta costs 3–8 ms. The “cost” of Pure experta vs `if/else` (1–3 ms) is noise next to the model. |
| **Knowledge scales by adding rules** | a new policy = a new rule, not edits to a branching tower. |
| **Zero user-visible difference** | the gap is below any HTTP round-trip. |

A full audit confirming the core is Pure experta lives in
[docs/pure_experta_review.md](docs/pure_experta_review.md).

---

## Architecture

### The Facts (`facts/all_facts.py`)
- **Input/context facts:** `ContentInput`, `UserProfile`, `ParentSettings`, `AIAnalysis`
- **Atomic facts** (one per list item, so rules match without loops):
  `BannedCategory`, `BannedKeyword`, `DetectedCategory`, `SensitiveKeyword`
- **Output facts** (asserted by rules): `Signal`, `Reason`, `Decision`,
  `Explanation`, `FinalDecisionMarker`

### The Rules (`rules/`)
| file | layer | what it produces |
|------|-------|------------------|
| `signal_rules.py` | 6 signal rules | `Signal` + `Reason` (high/medium risk, low confidence, age violation, language mismatch, suspicious source) |
| `matching_rules.py` | 2 matching rules | `Signal` for `banned_category_hit`, `keyword_hit` |
| `decision_rules.py` | 9 decision rules | exactly ONE `Decision(verdict)` |
| `explanation_rules.py` | 1 explanation rule | exactly ONE `Explanation(verdict, reasons_text)` |

### Decision priority
Driven by **salience**, made final by **`self.halt()`**:

```
Blocked  >  Review  >  Warning  >  Allowed
```

When several signals appear at once, the strongest verdict's rule fires
first and halts — e.g. `medium_risk` + a banned `keyword_hit` → **Blocked**.

### The four verdicts
| verdict | when |
|---------|------|
| **Allowed** | low risk, no negative signal |
| **Warning** | medium risk or an age violation, with nothing stronger |
| **Blocked** | banned category, banned keyword, or high/critical risk |
| **Review** | low confidence, unknown category, or the case-9 conflict |

---

## The four mandatory performance improvements

| # | improvement | where |
|---|-------------|-------|
| **P1** | `self.halt()` after every final rule | `decision_rules.py`, `explanation_rules.py` |
| **P2** | `NOT(Signal(type="..."))` guards every signal/matching rule | `signal_rules.py`, `matching_rules.py` |
| **P3** | a fresh `KBSEngine()` instance per request | `decision_service.py:run_decision_engine` |
| **P4** | case 9 (high risk + low confidence) decided by explicit rules | `decision_rules.py:rule_review_case9` |

All four are verified by automated tests — see
[docs/pure_experta_review.md](docs/pure_experta_review.md).

---

## Project structure

```
hybrid-content-decision-system/
├── ai_layer/
│   ├── mock_analyzer.py        # fake AI: content → analysis dict
│   └── ai_to_kbs_mapper.py     # analysis dict → experta Facts
├── facts/
│   └── all_facts.py            # every Fact type (the schema)
├── rules/
│   ├── signal_rules.py         # T1.4
│   ├── matching_rules.py       # T1.5 / T1.6
│   ├── decision_rules.py       # T2.1 / T2.2 / T2.3
│   └── explanation_rules.py    # T2.4
├── engine/
│   ├── kbs_engine.py           # KBSEngine (mixins) + run_until_stable()
│   └── decision_service.py     # run_decision_engine() — API entry (T2.5, P3)
├── tests/
│   └── test_cases.py           # 12 required test cases (T3.1)
├── docs/
│   ├── pure_experta_review.md  # T3.2 audit
│   └── django_integration.md   # T3.4 integration path
├── demo.py                     # end-to-end showcase (5 scenarios)
├── contract.md                 # data / fact / decision contract
└── requirements.txt
```

---

## How to run

This project pins `experta==1.9.4`, which needs `frozendict==1.2` and runs
cleanly on **Python 3.9**. A conda env named `hcds` (Python 3.9) is the
reference environment.

```bash
# one-time setup
conda create -n hcds python=3.9
conda activate hcds
pip install -r requirements.txt

# end-to-end demo (5 scenarios)
python demo.py

# the 12 required test cases
python -m unittest tests.test_cases -v
```

> **Windows + Arabic console:** set `PYTHONIOENCODING=utf-8` before running
> so the Arabic reasons/explanations print correctly
> (PowerShell: `$env:PYTHONIOENCODING="utf-8"`).

### Using the engine from code

```python
from engine.decision_service import run_decision_engine

result = run_decision_engine({
    "text": "how to kill someone with a weapon",
    "source_type": "text",
    "source_reputation": "suspicious",
    "age": 10, "age_group": "child", "language": "ar",
    "protection_level": "high",
    "banned_categories": ["violence", "weapons"],
    "banned_keywords": ["kill", "weapon"],
})

result["kbs_result"]["decision"]    # -> "Blocked"
result["kbs_result"]["reason"]      # -> aggregated Arabic reason text
result["explanation"]               # -> full Arabic explanation
```

**Return shape:**
```python
{
  "ai_result":  { ...the 10 AIAnalysis fields... },
  "kbs_result": {
      "decision":        "Blocked",          # one of the 4 verdicts
      "reason":          "…",                # from the Explanation fact
      "triggered_rules": ["rule_…", …],
      "signals":         [ {type, severity, source_rule, value}, … ],
  },
  "explanation": "…full Arabic explanation…",
}
```

---

## Test cases

`tests/test_cases.py` implements the 12 required cases (10 logical + 2 for
the performance improvements): the four verdicts, the salience tie-breaks,
the exact `risk_score == 75` boundary, the case-9 conflict (Review / Blocked),
P2 (no duplicate signals) and P3 (sequential requests stay isolated).

```bash
python -m unittest tests.test_cases -v    # 13/13 OK (case 9 split 9a/9b)
```

---

## Integration with Main Project (Django)

This module is a self-contained backend unit. A Django app will later expose
it over HTTP **without changing any rule logic** — it only calls
`run_decision_engine()`:

```
POST /api/content/evaluate/
```

The request body maps directly to `run_decision_engine`'s input dict, and the
response is its return dict. **Critical (P3):** every request must build a new
`KBSEngine()` inside `run_decision_engine()` — experta is a *stateful* engine,
so reusing one instance across requests would mix working memories. The
service already does this; the Django view must not cache the engine.

Full details, view sketch and request/response examples:
[docs/django_integration.md](docs/django_integration.md).

---

## Status

| phase | tasks | status |
|-------|-------|--------|
| Day 1 | T1.1–T1.7 (engine, mock AI, mapper, signal/matching rules, demo) | ✅ |
| Day 2 | T2.1–T2.5 (decision rules, salience, marker, explanation, service) | ✅ |
| Day 2 PM | T3.1 tests · T3.2 audit · T3.3 README · T3.4 Django docs | ✅ |

Team: **Khaled**, **Ibrahim**, **Najat**.
