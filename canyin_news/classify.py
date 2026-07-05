LOW_VALUE = ("招商", "加盟", "报名", "点击领取", "注册资本")
PLATFORMS = (
    "美团",
    "饿了么",
    "淘宝闪购",
    "京东外卖",
    "京东秒送",
    "抖音生活服务",
)
PLATFORM_EVENTS = (
    "上线",
    "合作",
    "补贴",
    "助力金",
    "扶持",
    "商户",
    "参保",
    "增长",
    "发布",
    "调整",
    "内测",
    "佣金",
    "规则",
    "流量",
    "配送",
    "战略",
    "组织调整",
    "新业务",
)
AI_SOURCES = (
    "OpenAI",
    "Anthropic",
    "Google DeepMind",
    "Hugging Face",
    "NVIDIA",
    "Microsoft Research",
)
AI_EVENTS = (
    "AI",
    "模型",
    "大模型",
    "智能体",
    "Agent",
    "人工智能",
    "OpenAI",
    "Anthropic",
    "Claude",
    "GPT",
    "Gemini",
    "LLM",
    "Midjourney",
)
FOOD_SOURCES = (
    "红餐网",
    "餐饮老板内参",
    "餐企老板内参",
    "餐饮O2O",
    "窄门餐眼",
)
FOOD_EVENTS = (
    "新品",
    "菜单",
    "新店",
    "餐饮品牌",
    "门店",
    "连锁",
    "出海",
    "供应链",
    "会员",
)
FOOD_CONTEXT = (
    "餐饮",
    "餐厅",
    "外卖",
    "食品",
    "饮品",
    "咖啡",
    "茶饮",
    "奶茶",
    "火锅",
    "烘焙",
    "快餐",
    "肯德基",
    "麦当劳",
    "瑞幸",
    "库迪",
    "蜜雪冰城",
    "星巴克",
    "喜茶",
    "奈雪",
    "霸王茶姬",
    "海底捞",
)


def classify_article(title: str, summary: str, source: str) -> str | None:
    text = f"{title} {summary}"
    if any(word in text for word in LOW_VALUE):
        return None
    if any(entity in text for entity in PLATFORMS) and any(
        event in text for event in PLATFORM_EVENTS
    ):
        return "平台动态"
    if source in AI_SOURCES or any(word in text for word in AI_EVENTS):
        return "AI行业资讯"
    if source in FOOD_SOURCES or (
        any(word in text for word in FOOD_CONTEXT)
        and any(word in text for word in FOOD_EVENTS)
    ):
        return "餐饮动态"
    return None
