# 🍔🤖 餐饮AI情报站

每日自动更新的餐饮行业 + AI行业情报聚合站。

## 本地运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行爬虫抓取数据
python scraper.py

# 3. 启动本地服务器预览
python -m http.server 8080
# 浏览器打开 http://localhost:8080
```

## 部署到 GitHub Pages

1. 在 GitHub 上创建新仓库（公开）
2. 把本项目所有文件推送到仓库
3. 进入仓库 Settings → Pages → Source 选 "GitHub Actions"
4. 以后每天 8:00 自动更新，你也可以在 Actions 页面手动触发

## 数据来源

- 红餐网 (canyin88.com)
- 36氪 AI (36kr.com)
- 亿欧 (iyiou.com)
- RSS 订阅

## 技术栈

- 前端：纯 HTML + CSS + JavaScript（无需框架）
- 后端：Python 爬虫（GitHub Actions 自动运行）
- 部署：GitHub Pages
