"""
rules/signal_rules.py
==================================================================
Phase 2 (Najat) — Signal Rules.

These rules read the raw Facts (AIAnalysis, UserProfile, ContentInput)
and produce Signal + Reason facts ONLY.  No final verdict is made here.

P2 contract: every rule guards with NOT(Signal(type="...")) so the
same signal is never asserted more than once per run.
==================================================================
"""

from experta import KnowledgeEngine, Rule, MATCH, TEST, NOT

from facts.all_facts import (
    AIAnalysis,
    UserProfile,
    ContentInput,
    Signal,
    Reason,
)


class SignalRulesMixin(KnowledgeEngine):

    @Rule(
        AIAnalysis(risk_score=MATCH.score),
        TEST(lambda score: score >= 75),
        NOT(Signal(type="high_risk"))
    )
    def rule_high_risk(self, score):
        self.declare(Signal(
            type="high_risk",
            severity="high",
            source_rule="rule_high_risk",
            value=str(score)
        ))
        self.declare(Reason(
            rule_name="rule_high_risk",
            text=f"درجة الخطورة {score} أكبر أو تساوي 75، لذلك تم تسجيل إشارة خطر عالي."
        ))

    @Rule(
        AIAnalysis(risk_score=MATCH.score),
        TEST(lambda score: 40 <= score < 75),
        NOT(Signal(type="medium_risk"))
    )
    def rule_medium_risk(self, score):
        self.declare(Signal(
            type="medium_risk",
            severity="medium",
            source_rule="rule_medium_risk",
            value=str(score)
        ))
        self.declare(Reason(
            rule_name="rule_medium_risk",
            text=f"درجة الخطورة {score} بين 40 و74، لذلك تم تسجيل إشارة خطر متوسط."
        ))

    @Rule(
        AIAnalysis(confidence_score=MATCH.confidence),
        TEST(lambda confidence: confidence < 0.55),
        NOT(Signal(type="low_confidence"))
    )
    def rule_low_confidence(self, confidence):
        self.declare(Signal(
            type="low_confidence",
            severity="medium",
            source_rule="rule_low_confidence",
            value=str(confidence)
        ))
        self.declare(Reason(
            rule_name="rule_low_confidence",
            text=f"ثقة التحليل {confidence} أقل من 0.55، لذلك يحتاج المحتوى إلى حذر أو مراجعة لاحقاً."
        ))

    @Rule(
        AIAnalysis(suggested_min_age=MATCH.min_age),
        UserProfile(age=MATCH.user_age),
        TEST(lambda min_age, user_age: min_age > user_age),
        NOT(Signal(type="age_violation"))
    )
    def rule_age_violation(self, min_age, user_age):
        self.declare(Signal(
            type="age_violation",
            severity="medium",
            source_rule="rule_age_violation",
            value=f"suggested_min_age={min_age}, user_age={user_age}"
        ))
        self.declare(Reason(
            rule_name="rule_age_violation",
            text=f"العمر المقترح للمحتوى هو {min_age} بينما عمر المستخدم {user_age}، لذلك توجد مخالفة عمرية."
        ))

    @Rule(
        AIAnalysis(language=MATCH.content_language),
        UserProfile(language=MATCH.user_language),
        TEST(lambda content_language, user_language: content_language != user_language),
        NOT(Signal(type="language_mismatch"))
    )
    def rule_language_mismatch(self, content_language, user_language):
        self.declare(Signal(
            type="language_mismatch",
            severity="low",
            source_rule="rule_language_mismatch",
            value=f"content_language={content_language}, user_language={user_language}"
        ))
        self.declare(Reason(
            rule_name="rule_language_mismatch",
            text=f"لغة المحتوى {content_language} مختلفة عن لغة المستخدم {user_language}."
        ))

    @Rule(
        ContentInput(source_reputation="suspicious"),
        NOT(Signal(type="suspicious_source"))
    )
    def rule_suspicious_source(self):
        self.declare(Signal(
            type="suspicious_source",
            severity="medium",
            source_rule="rule_suspicious_source",
            value="suspicious"
        ))
        self.declare(Reason(
            rule_name="rule_suspicious_source",
            text="مصدر المحتوى مصنف كمصدر مشبوه، لذلك تم تسجيل إشارة مصدر غير موثوق."
        ))
