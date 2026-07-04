from dataclasses import dataclass
from datetime import datetime


ALLOWED_CATEGORIES = {"餐饮动态", "平台动态", "AI行业资讯"}
PROMOTIONAL_WORDS = ("招商", "加盟", "报名", "点击领取", "限时抢购")
OFFICIAL_SOURCES = {
    "OpenAI",
    "Anthropic",
    "Google DeepMind",
    "Hugging Face",
    "NVIDIA",
    "Microsoft Research",
}
PROFESSIONAL_SOURCES = {
    "红餐网",
    "餐饮老板内参",
    "餐企老板内参",
    "餐饮O2O",
    "窄门餐眼",
    "36氪",
    "36氪AI",
    "机器之心",
    "量子位",
}
CATEGORY_TERMS = {
    "餐饮动态": ("餐饮", "品牌", "新品", "菜单", "门店", "连锁", "供应链"),
    "平台动态": ("美团", "饿了么", "淘宝闪购", "京东", "抖音生活服务", "商家"),
    "AI行业资讯": ("AI", "模型", "智能体", "人工智能", "Agent"),
}
HIGH_IMPACT_TERMS = (
    "全国",
    "发布",
    "上线",
    "新业务",
    "监管",
    "融资",
    "收购",
    "关店",
    "出海",
    "战略",
    "模型",
)
MEDIUM_IMPACT_TERMS = ("合作", "增长", "升级", "扩张", "调整", "趋势")
ACTIONABLE_TERMS = (
    "商家",
    "成本",
    "佣金",
    "补贴",
    "流量",
    "菜单",
    "门店",
    "会员",
    "供应链",
    "应用",
    "经营",
)


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    relevance: int
    impact: int
    authority: int
    freshness: int
    novelty: int
    actionability: int
    penalty: int
    total: int


def passes_quality_gate(article: dict) -> bool:
    title = article.get("title", "").strip()
    text = f'{title} {article.get("summary", "")}'
    return bool(
        len(title) >= 6
        and article.get("category") in ALLOWED_CATEGORIES
        and str(article.get("url", "")).startswith(("http://", "https://"))
        and article.get("published_at") is not None
        and not any(word in text for word in PROMOTIONAL_WORDS)
    )


def score_article(article: dict, now: datetime) -> ScoreBreakdown:
    text = f'{article.get("title", "")} {article.get("summary", "")}'
    category = article.get("category", "")

    relevance = 25 if any(
        term in text for term in CATEGORY_TERMS.get(category, ())
    ) else 18
    if any(term in text for term in HIGH_IMPACT_TERMS):
        impact = 25
    elif any(term in text for term in MEDIUM_IMPACT_TERMS):
        impact = 15
    else:
        impact = 8

    source = article.get("source", "")
    if "官方" in source or source in OFFICIAL_SOURCES:
        authority = 15
    elif source in PROFESSIONAL_SOURCES:
        authority = 12
    else:
        authority = 5

    published_at = article.get("published_at")
    if published_at is None:
        freshness = 0
    else:
        hours = max(0, (now - published_at).total_seconds() / 3600)
        freshness = 15 if hours <= 24 else 10 if hours <= 48 else 6 if hours <= 72 else 0

    novelty = 0 if article.get("duplicate_event") else 10
    actionability = 10 if any(term in text for term in ACTIONABLE_TERMS) else 5
    penalty = 30 if any(term in text for term in PROMOTIONAL_WORDS) else 0
    total = min(
        100,
        relevance
        + impact
        + authority
        + freshness
        + novelty
        + actionability
        - penalty,
    )
    return ScoreBreakdown(
        relevance=relevance,
        impact=impact,
        authority=authority,
        freshness=freshness,
        novelty=novelty,
        actionability=actionability,
        penalty=penalty,
        total=max(0, total),
    )
