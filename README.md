# 餐饮AI情报站

每日自动采集餐饮行业 + AI 领域最新资讯，聚合展示在同一个页面。爬虫通过 GitHub Actions 每天自动运行。

🔗 **在线站点：** https://canyin-ai-news.vercel.app/

## 数据来源

- 红餐网（canyin88.com）
- 36氪（36kr.com）
- 微信公众号搜索

## 功能特点

- 自动分类：餐饮动态 / AI动态 / 平台政策 / 数据报告
- 热度评分系统：综合信源权重 + 时效性 + 关键词
- 个性化推荐语：每条新闻带场景化解读
- 前端：深色/浅色主题切换，分类筛选，全文搜索

## 自动化

每天 UTC 00:00（北京时间 08:00）通过 GitHub Actions 自动运行爬虫，更新数据。

## 项目结构

```
├── scraper.py           # 核心爬虫
├── index.html           # 前端展示页面
├── articles.json        # 采集的数据（自动更新）
├── requirements.txt     # Python依赖
├── vercel.json          # Vercel部署配置
└── .github/
    └── workflows/
        └── daily-update.yml  # 定时任务配置
```

## 本地运行

```bash
pip install -r requirements.txt
python scraper.py
# 然后打开 index.html
```

## 技术栈

Python（爬虫）+ GitHub Actions（定时任务）+ HTML/CSS/JS（前端）+ Vercel（部署）
