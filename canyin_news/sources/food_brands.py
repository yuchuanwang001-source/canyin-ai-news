KA_BRANDS = (
    "肯德基", "麦当劳", "小谷姐姐", "瑞幸", "库迪", "蜜雪冰城",
    "星巴克", "喜茶", "奈雪", "霸王茶姬", "海底捞", "塔斯汀",
    "华莱士", "茶百道", "古茗", "沪上阿姨", "杨国福", "张亮麻辣烫",
)
BRAND_ACTIONS = (
    "新品", "菜单", "联名", "营销", "会员", "价格", "降价", "涨价",
    "开店", "新店", "店型", "扩张", "关店", "加盟", "出海", "供应链",
    "数字化", "上线", "合作", "战略",
)


def keep_ka_brand_articles(articles):
    selected = []
    for article in articles:
        text = f"{article.title} {article.summary}"
        if any(brand in text for brand in KA_BRANDS) and any(
            action in text for action in BRAND_ACTIONS
        ):
            article.category = "餐饮动态"
            selected.append(article)
    return selected
