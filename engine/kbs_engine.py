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

from experta import KnowledgeEngine, Rule, MATCH, TEST, NOT
from experta.fact import InitialFact   # experta declares one of these on reset()

from facts.all_facts import (
    AIAnalysis,
    UserProfile,
    ContentInput,
    DetectedCategory,
    SensitiveKeyword,
    BannedCategory,
    BannedKeyword,
    Signal,
    Reason,
)


class KBSEngine(KnowledgeEngine):
    """The Knowledge-Based System engine.

    Phase 1: Khaled created the empty engine shell.
    Phase 2: Najat adds derived Signal rules.
    """

    # ==============================================================
    # Phase 2 - Najat: Derived Signal Rules
    # These rules produce Signal + Reason facts only.
    # They DO NOT produce final decisions.
    # ==============================================================

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
    # ==============================================================
    # Phase 2 - Ibrahim: Matching Rules
    # These rules match AI-detected atomic facts with parent-banned
    # atomic facts. They produce Signals only, not final decisions.
    # ==============================================================

    @Rule(
        DetectedCategory(value=MATCH.category),
        BannedCategory(value=MATCH.category),
        NOT(Signal(type="banned_category_hit"))
    )
    def rule_banned_category_hit(self, category):
        self.declare(Signal(
            type="banned_category_hit",
            severity="high",
            source_rule="rule_banned_category_hit",
            value=category
        ))
        self.declare(Reason(
            rule_name="rule_banned_category_hit",
            text=f"الفئة المكتشفة '{category}' موجودة ضمن الفئات المحظورة من إعدادات الأهل."
        ))

    @Rule(
        SensitiveKeyword(value=MATCH.keyword),
        BannedKeyword(value=MATCH.keyword),
        NOT(Signal(type="keyword_hit"))
    )
    def rule_keyword_hit(self, keyword):
        self.declare(Signal(
            type="keyword_hit",
            severity="high",
            source_rule="rule_keyword_hit",
            value=keyword
        ))
        self.declare(Reason(
            rule_name="rule_keyword_hit",
            text=f"الكلمة الحساسة '{keyword}' موجودة ضمن الكلمات المحظورة من إعدادات الأهل."
        ))
        
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
# SMOKE TEST (Phase 2)
# Proves: engine constructs, has rules, accepts facts, and can run.
# This test still makes NO final decisions.
# ==================================================================
if __name__ == "__main__":
    from facts.all_facts import (
        ContentInput,
        UserProfile,
        ParentSettings,
        AIAnalysis,
        DetectedCategory,
        SensitiveKeyword,
        BannedCategory,
        BannedKeyword,
    )

    engine = KBSEngine()
    engine.reset()

    rule_count = len(engine.get_rules())
    print(f"rules loaded: {rule_count}  (Phase 2: signal + matching rules)")

    engine.load_facts([
        ContentInput(
            text="فيديو يحتوي على تهديد",
            source_type="video",
            source_reputation="suspicious"
        ),
        UserProfile(
            age=10,
            age_group="child",
            language="ar"
        ),
        ParentSettings(
            protection_level="high",
            banned_categories=["violence", "adult", "drugs"],
            banned_keywords=["تهديد", "قتل"]
        ),
        AIAnalysis(
            category="violence",
            risk_score=88,
            risk_level="high",
            confidence_score=0.87,
            confidence_level="high",
            detected_categories=["violence"],
            sensitive_keywords=["تهديد"],
            suggested_min_age=16,
            language="ar",
            analyzer_type="mock"
        ),
        DetectedCategory(value="violence"),
        SensitiveKeyword(value="تهديد"),
        BannedCategory(value="violence"),
        BannedCategory(value="adult"),
        BannedCategory(value="drugs"),
        BannedKeyword(value="تهديد"),
        BannedKeyword(value="قتل"),
    ])

    engine.run()

    print("working memory after rules:")
    engine.print_facts()

    print("\nOK: Phase 2 rules run and produce Signals/Reasons only.")