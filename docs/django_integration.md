# Integration with the Main Project (Django) — T3.4

This decision core is framework-agnostic. The future Django service exposes
it over HTTP **without re-implementing any rule**: the view simply calls
`engine.decision_service.run_decision_engine(input_data)` and returns its
result.

---

## Endpoint

```
POST /api/content/evaluate/
Content-Type: application/json
```

### Request

The body maps 1:1 to `run_decision_engine`'s input dict:

```json
{
  "text": "نص المحتوى هنا",
  "source_type": "text",
  "source_reputation": "unknown",
  "age": 10,
  "age_group": "child",
  "language": "ar",
  "protection_level": "high",
  "banned_categories": ["violence", "weapons"],
  "banned_keywords": ["kill", "weapon"]
}
```

| field | required | notes |
|-------|----------|-------|
| `text` | yes | the content to evaluate |
| `source_type` | no | `text` \| `video` \| `image` (default `text`) |
| `source_reputation` | no | `trusted` \| `unknown` \| `suspicious` (default `unknown`) |
| `age`, `age_group`, `language` | yes | the user profile |
| `protection_level` | yes | parent/system setting |
| `banned_categories`, `banned_keywords` | no | default `[]` |

### Response

The body is exactly `run_decision_engine`'s return dict:

```json
{
  "ai_result": {
    "category": "violence",
    "risk_score": 100,
    "risk_level": "critical",
    "confidence_score": 0.8,
    "confidence_level": "high",
    "detected_categories": ["violence", "weapons"],
    "sensitive_keywords": ["kill", "weapon"],
    "suggested_min_age": 16,
    "language": "ar",
    "analyzer_type": "mock"
  },
  "kbs_result": {
    "decision": "Blocked",
    "reason": "الكلمة الحساسة 'weapon' موجودة ضمن الكلمات المحظورة ... | تم حظر المحتوى لأنه يحتوي على فئة محظورة من إعدادات الأهل.",
    "triggered_rules": [
      "rule_keyword_hit", "rule_banned_category_hit",
      "rule_age_violation", "rule_high_risk",
      "rule_suspicious_source", "rule_blocked_banned_category"
    ],
    "signals": [
      {"type": "keyword_hit", "severity": "high", "source_rule": "rule_keyword_hit", "value": "weapon"}
    ]
  },
  "explanation": "تم حظر المحتوى. تحليل الـ AI صنّف المحتوى ضمن فئة 'violence' ... السبب: ..."
}
```

---

## View sketch (Django REST Framework)

```python
# api/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from engine.decision_service import run_decision_engine


class EvaluateContentView(APIView):
    """POST /api/content/evaluate/ — evaluate one piece of content."""

    def post(self, request):
        try:
            # run_decision_engine builds a FRESH KBSEngine() internally (P3),
            # so this view stays stateless — do NOT cache the engine here.
            result = run_decision_engine(request.data)
        except KeyError as exc:
            return Response(
                {"error": f"missing required field: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except RuntimeError as exc:
            # raised if experta did not produce exactly one Decision/Explanation
            return Response(
                {"error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(result, status=status.HTTP_200_OK)
```

```python
# api/urls.py
from django.urls import path
from .views import EvaluateContentView

urlpatterns = [
    path("api/content/evaluate/", EvaluateContentView.as_view()),
]
```

A plain function-based view works the same way — the only rule is: **call
`run_decision_engine(payload)` and return its result.**

---

## Critical: a fresh engine per request (P3)

experta's `KnowledgeEngine` is **stateful** — its working memory holds the
facts of whatever it last processed. If a Django app created one engine at
startup and reused it across requests, request *B* would see request *A*'s
facts and produce a corrupted verdict.

`run_decision_engine()` already prevents this by constructing
`KBSEngine()` + `reset()` **inside** the function, once per call:

```python
def run_decision_engine(input_data):
    ...
    engine = KBSEngine()     # fresh instance — P3
    engine.reset()
    engine.load_facts(facts)
    engine.run_until_stable()
    ...
```

So the integration rule for Django is simply: **never cache the engine; call
`run_decision_engine()` per request.** Test case 12
(`tests/test_cases.py:test_case_12_sequential_requests_isolated_p3`) proves
two sequential requests stay isolated.

---

## Notes

- **No database required** for the decision itself — it is a pure function of
  its input. Persisting requests/verdicts is a separate concern for the
  Django app.
- **Stateless & thread-safe by construction:** because each call owns its
  engine, concurrent requests do not share working memory.
- **Swapping the real AI in later** changes only `ai_layer/` — the rules,
  the service signature, and this endpoint stay identical.
