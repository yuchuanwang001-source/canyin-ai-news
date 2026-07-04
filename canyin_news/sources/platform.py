from canyin_news.classify import classify_article


def keep_platform_articles(articles):
    selected = []
    for article in articles:
        category = classify_article(
            article.title,
            article.summary,
            article.source,
        )
        if category == "平台动态":
            article.category = category
            selected.append(article)
    return selected
