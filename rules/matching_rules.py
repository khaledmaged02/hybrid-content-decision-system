"""
rules/matching_rules.py
==================================================================
Phase 2 (Ibrahim / Najat) — Matching Rules.

These rules match AI-detected atomic facts with parent-banned atomic
facts.  They produce Signal + Reason facts ONLY — no final verdict.

P2 contract: NOT(Signal(type="...")) guard prevents duplicate signals
regardless of how many DetectedCategory / SensitiveKeyword facts match.
==================================================================
"""

from experta import KnowledgeEngine, Rule, MATCH, NOT

from facts.all_facts import (
    DetectedCategory,
    BannedCategory,
    SensitiveKeyword,
    BannedKeyword,
    Signal,
    Reason,
)


class MatchingRulesMixin(KnowledgeEngine):

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
