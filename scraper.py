#!/usr/bin/env python3
"""餐饮AI情报站 — 数据爬虫 v2
每天早上8:00自动运行，抓取当天最新内容。
- 只保留当天+昨天文章
- URL提取日期（红餐网从URL取，100%准确）
- 热度评分（信源权重+时效性）
- 尝试抓取配图
"""

import json, re, hashlib, time as t, os
from datetime import datetime, timezone, timedelta
from collections import Counter
import requests
from bs4 import BeautifulSoup

TZ = timezone(timedelta(hours=8))
NOW = datetime.now(TZ)
TODAY = NOW.strftime("%Y-%m-%d")
YESTERDAY = (NOW - timedelta(days=1)).strftime("%Y-%m-%d")

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept-Language": "zh-CN,zh;q=0.9"}
TIMEOUT = 15
session = requests.Session()
session.headers.update(HEADERS)

# ===== HELPERS =====
def mid(url, title):
    return hashlib.md5(f"{url}|{title}".encode()).hexdigest()[:12]

def parse_time(s):
    if not s or not s.strip(): return None
    s = s.strip().replace('  ', ' ').replace(' +', '+')
    # 尝试各种格式和切片长度
    formats = ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
               "%Y-%m-%d %H:%M", "%Y-%m-%d"]
    for fmt in formats:
        for slen in [26, 25, 24, 23, 22, 21, 20, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10]:
            try:
                dt = datetime.strptime(s[:slen], fmt)
                return dt.replace(tzinfo=TZ).isoformat()
            except: pass
    # 尝试 RFC 2822
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(s).astimezone(TZ).isoformat()
    except: pass
    return None

def now_iso():
    return NOW.isoformat()

def txt(el, d=""):
    return el.get_text(strip=True) if el else d

def safe_get(url, **kw):
    for _ in range(2):
        try:
            r = session.get(url, timeout=TIMEOUT, **kw)
            r.raise_for_status()
            return r
        except Exception as e:
            if _: print(f"  [WARN] {url[:50]} — {e}")
            t.sleep(1)
    return None

# ===== 热度评分 =====
SOURCE_WEIGHT = {"红餐网": 10, "36氪AI": 8, "36氪": 7, "36氪快讯": 6,
    "餐企老板内参": 7, "餐饮老板内参": 7, "勇哥餐饮": 5, "餐饮O2O": 6,
    "窄门餐眼": 6, "餐饮报告": 6, "AI餐饮": 5, "外卖平台": 6}

def calc_score(title, summary, source, time_iso):
    score = SOURCE_WEIGHT.get(source, 5) * 5  # 信源基础分 25-50
    # 时效加成：越新越高
    if time_iso:
        try:
            dt = datetime.fromisoformat(time_iso)
            hours_ago = (NOW - dt).total_seconds() / 3600
            if hours_ago < 2: score += 30
            elif hours_ago < 6: score += 20
            elif hours_ago < 12: score += 10
            elif hours_ago < 24: score += 5
        except: pass
    # 关键词加分（重要话题）
    hot_kw = ["融资", "上市", "IPO", "收购", "破产", "出海", "政策", "AI", "人工智能",
              "大模型", "报告", "数据", "连锁", "趋势", "增长", "AI+餐饮"]
    t = (title + " " + (summary or "")).lower()
    for kw in hot_kw:
        if kw.lower() in t:
            score += 5
    return min(score, 100)

def classify(title, summary, src):
    """返回 (category, should_keep) — should_keep=False表示丢弃"""
    t = (title + " " + (summary or "")).lower()

    # ===== 信源固定分类 =====
    # 平台类公众号 → 直接归入平台政策
    platform_sources = ["淘宝闪购本地生活","美团餐饮观察","淘宝闪购商家课堂"]
    if src in platform_sources:
        return ("平台政策", True)

    # AI公司 → 直接归入AI动态
    ai_company_sources = ["OpenAI","DeepSeek","Kimi AI","Google Gemini",
                          "Anthropic Claude","豆包","智谱AI",
                          "阿里AI","腾讯AI","字节AI","百度AI"]
    if src in ai_company_sources:
        return ("AI动态", True)

    # ===== 关键词精准匹配（优先于信源固定分类） =====
    # 平台政策关键词（所有来源都检查，包括红餐网）
    platform_phrases = ["规则调整","规则变更","新规出台","政策变化","政策更新",
                        "商家规则","费率调整","抽成变化","算法规则","合规要求",
                        "平台新规","准入规则","平台补贴","商家政策",
                        "外卖平台","补贴行为","平台规则","补贴规范",
                        "外卖新规","市场监管","平台经济"]
    if any(p in t for p in platform_phrases):
        return ("平台政策", True)

    # 餐饮媒体 → 归入餐饮动态
    food_sources = ["红餐网","餐企老板内参","餐饮老板内参","勇哥餐饮","餐饮O2O","窄门餐眼"]
    if src in food_sources:
        return ("餐饮动态", True)

    # 数据报告关键词
    report_phrases = ["报告显示","报告指出","发布报告","数据显示","白皮书",
                      "问卷调查","调研发现","研究报告","数据分析","数据报告"]
    if any(p in t for p in report_phrases):
        return ("数据报告", True)

    ai_phrases = ["AI模型","AI技术","AI应用","AI+","大模型发布","模型更新",
                  "GPT-4","GPT-5","Claude 4","人工智能","智能体","Agent",
                  "机器学习","深度学习","AI Agent"]
    if any(p in t for p in ai_phrases):
        return ("AI动态", True)

    food_phrases = ["新店开业","门店扩张","关店","餐饮品牌","连锁化",
                    "外卖","团购","到店","新菜单","菜品","餐饮行业",
                    "翻台率","客单价","会员运营","门店数量"]
    if any(p in t for p in food_phrases):
        return ("餐饮动态", True)

    # ===== 兜底规则 =====
    # 36氪等综合科技媒体的文章：不命中任何关键词 → 丢掉
    if src in ["36氪AI","36氪","36氪快讯"]:
        return (None, False)

    # 其他来源（按来源名含有关键词兜底）
    if "AI" in src or "智能" in src:
        return ("AI动态", True)
    if "餐饮" in src or "美食" in src or "外卖" in src:
        return ("餐饮动态", True)

    return (None, False)

def tags(title, summary):
    tags = []
    t = (title + " " + (summary or "")).lower()
    km = {"餐饮趋势":["趋势","赛道","增长","发展","未来","风口"],
          "品牌动态":["品牌","门店","开店","关店","融资","上市","收购","破产"],
          "外卖/平台":["外卖","美团","饿了么","闪购","配送","团购"],
          "AI/数字化":["ai","智能","数字化","机器人","自动化","数据"],
          "餐饮创新":["新品","创新","产品","新式","场景","体验"],
          "供应链":["供应链","食材","物流","采购","源头"],
          "营销/运营":["营销","运营","会员","私域","推广"],
          "出海":["出海","海外","国际化","全球"],
          "资本/投融资":["融资","投资","上市","ipo","资本"],
          "报告/数据":["报告","数据","白皮书","调研"]}
    for tag,kws in km.items():
        if any(k in t for k in kws): tags.append(tag)
    return tags[:3]

SOURCE_REASONS = {
    "红餐网": "餐饮产业头部媒体，深耕行业20年",
    "36氪AI": "36氪AI频道精选，科技前沿资讯",
    "36氪": "36氪每日精选商业科技动态",
    "36氪快讯": "36氪快讯，实时商业科技资讯",
    "餐企老板内参": "餐饮老板内参，深度产业分析",
    "餐饮老板内参": "餐饮老板内参，深度行业观察",
    "勇哥餐饮": "勇哥餐饮，一线餐饮实战分享",
    "餐饮O2O": "餐饮O2O，餐饮互联网前沿",
    "窄门餐眼": "窄门餐眼，餐饮数据洞察",
}

def gen_reason(title, summary, source, score, tags):
    """生成更人性化的推荐理由"""
    t = (title + " " + (summary or "")).lower()
    # 提取关键实体用于推荐语
    entities = []
    key_orgs = ["OpenAI","Anthropic","Google","微软","苹果","阿里","腾讯","字节","美团","饿了么","抖音","小红书","京东"]
    for org in key_orgs:
        if org.lower() in t:
            entities.append(org)
    entity = entities[0] if entities else ""
    
    # 高热度（85+）
    if score >= 85:
        if entity:
            return f"[HOT] {entity}最新动态，行业关注度极高，值得第一时间了解"
        return "[HOT] 今日重磅消息，行业关注度最高，建议优先阅读"

    # 按主题生成带上下文的推荐语
    # 资本市场
    if any(k in t for k in ["融资","上市","IPO","收购","破产"]):
        verb = "融资" if "融资" in t else ("上市" if "上市" in t or "ipo" in t else "资本运作")
        brand = entity or "这家公司"
        return f"[MONEY] {brand}的{verb}动态，如果你是餐饮从业者或者关注行业资本流向，这信息值得留意"

    # AI相关
    if any(k in t for k in ["AI","人工智能","大模型","智能体","Agent","GPT","Claude"]):
        if entity:
            return f"[AI] {entity}在AI领域又有新动作，如果你关注AI怎么落地餐饮场景，这篇能给你一些启发"
        if "Agent" in t or "智能体" in t:
            return f"[AI] AI Agent正在改变各行业，餐饮也不例外，提前了解趋势总没错"
        if "大模型" in t or "GPT" in t or "Claude" in t:
            return f"[AI] 大模型又迭代了，虽然看起来是技术新闻，但AI对餐饮运营的影响比你想象的要快"
        return f"[AI] AI行业新动向，对于正在用AI做餐饮运营的你，保持信息同步很重要"

    # 报告/数据
    if any(k in t for k in ["报告","数据","白皮书","调研","趋势"]):
        if "餐饮" in t:
            return f"[DATA] 餐饮行业最新数据报告，如果你在做会员运营或者品牌策略，数据比感觉靠谱"
        return f"[DATA] 行业报告出炉，做运营离不开数据支撑，这篇值得存下来慢慢看"

    # 平台政策
    if any(k in t for k in ["外卖","美团","饿了么","闪购","平台","规则","政策"]):
        return f"[POLICY] 平台规则有变化，直接影响到你帮品牌做运营的实际操作，建议仔细看看"

    # 餐饮品牌/门店
    if any(k in t for k in ["门店","品牌","开店","关店","连锁"]):
        brand = entity or "这个品牌"
        return f"[FD] {brand}的最新动态，关注竞品在做什么，比闭门造车强得多"

    # 出海
    if any(k in t for k in ["出海","海外","国际化"]):
        return f"[GLOBAL] 餐饮出海是今年的热门方向，如果你服务的品牌有出海计划，这篇可以作为参考"

    # 供应链
    if any(k in t for k in ["供应链","食材","物流"]):
        return f"[CHAIN] 供应链动态，成本控制是餐饮运营的核心命题，这条信息值得关注"

    # 营销/运营
    if any(k in t for k in ["营销","运营","会员","私域","增长"]):
        return f"[TREND] 运营干货，会员运营和私域是你日常工作的一部分，看看别人怎么做的"

    # 默认：根据信源生成
    source_map = {
        "红餐网": f"[R] 红餐网报道，作为餐饮行业头部媒体，他们的内容对了解行业风向很有帮助",
        "36氪AI": f"[R] 36氪AI频道推荐，科技和餐饮的交叉点越来越多，保持关注",
        "36氪": f"[R] 36氪精选，这条虽然不是直接讲餐饮，但宏观趋势会影响每个行业",
        "餐企老板内参": f"[R] 餐饮老板内参出品，深度分析餐饮产业，做这行不看这个会错过很多",
        "餐饮老板内参": f"[R] 餐饮老板内参的一线观察，接地气、有案例，适合实操参考",
        "勇哥餐饮": f"[R] 勇哥餐饮分享，实战派经验，不是纸上谈兵那种",
        "餐饮O2O": f"[R] 餐饮O2O聚焦餐饮互联网，跟你的工作方向很匹配",
        "窄门餐眼": f"[R] 窄门餐眼数据洞察，用数据说话的硬内容",
        "淘宝闪购本地生活": f"[R] 淘宝闪购官方动态，跟你的日常运营工作直接相关",
        "美团餐饮观察": f"[R] 美团官方餐饮观察，平台风向早知道",
        "淘宝闪购商家课堂": f"[R] 淘宝闪购商家课堂，运营实操干货",
        "OpenAI": f"[R] OpenAI最新动态，AI技术迭代影响每一个行业",
        "Anthropic Claude": f"[R] Anthropic Claude动态，AI前沿技术跟踪",
        "Google Gemini": f"[R] Google Gemini动态，全球AI竞赛最新进展",
        "豆包": f"[R] 豆包AI动态，国产AI大模型进展值得关注",
        "DeepSeek": f"[R] DeepSeek动态，国产AI新锐力量",
        "Kimi AI": f"[R] Kimi AI动态，AI应用场景持续扩展",
        "智谱AI": f"[R] 智谱AI动态，国产大模型重要参与者",
        "阿里AI": f"[R] 阿里巴巴AI动态，大厂布局影响行业走向",
        "腾讯AI": f"[R] 腾讯AI动态，大厂AI布局值得关注",
        "字节AI": f"[R] 字节跳动AI动态，技术驱动型大厂动向",
        "百度AI": f"[R] 百度AI动态，AI技术先行者",
        "AI餐饮行业": f"[R] AI+餐饮交叉领域，跟你日常工作直接相关",
        "人工智能餐饮": f"[R] AI+餐饮交叉领域，关注技术如何落地餐饮场景",
    }
    if source in source_map:
        return source_map[source]
    
    return f"[R] 来自{source}的内容，值得花时间看看"

def extract_image(soup, url):
    """尝试从文章页提取配图"""
    for meta in [soup.find('meta', property='og:image'),
                 soup.find('meta', attrs={'name': 'og:image'}),
                 soup.find('meta', attrs={'itemprop': 'image'})]:
        if meta and meta.get('content'):
            return meta['content']
    for img in soup.find_all('img'):
        src = img.get('src') or img.get('data-src') or ''
        if src and not src.endswith('.svg') and 'logo' not in src.lower():
            if src.startswith('http'):
                return src
            if src.startswith('//'):
                return 'https:' + src
            if src.startswith('/'):
                from urllib.parse import urlparse
                return f"{urlparse(url).scheme}://{urlparse(url).netloc}{src}"
    return ""

def is_today_or_yesterday(time_iso):
    if not time_iso:
        return False
    try:
        dt = datetime.fromisoformat(time_iso)
        # 如果带时区，转成北京时间
        if dt.tzinfo:
            dt = dt.astimezone(TZ)
        else:
            dt = dt.replace(tzinfo=TZ)
        date_str = dt.strftime("%Y-%m-%d")
        return date_str == TODAY or date_str == YESTERDAY
    except:
        return False


# ===== 1. 红餐网 =====
def scrape_hongcan():
    print("\n[R] 红餐网 (canyin88.com)")
    articles = []
    for lp in ["https://www.canyin88.com/zixun/", "https://www.canyin88.com/kuaixun/"]:
        r = safe_get(lp)
        if not r: continue
        soup = BeautifulSoup(r.content, 'html.parser')
        for a in soup.find_all('a', href=True):
            h = a['href']
            # zixun: /zixun/2026/06/23/112322.html  (YYYY/MM/DD)
            # kuaixun: /kuaixun/2026/0623/112329.html  (YYYYMMDD)
            m = re.search(r'/(zixun|kuaixun)/\d{4}/(\d{2}/\d{2}|\d{4})/\d+\.html', h)
            if not m: continue
            url = h if h.startswith('http') else 'https://www.canyin88.com' + h
            title = txt(a)
            if not title or len(title) < 8: continue
            # 从URL提取日期（兼容两种格式）
            raw_part = m.group(2)
            if '/' in raw_part:
                date_from_url = raw_part.replace('/', '-')
            else:
                date_from_url = f'{raw_part[:2]}-{raw_part[2:]}'
            year = NOW.year
            time_str = f"{year}-{date_from_url}T12:00:00+08:00"
            summary, img_url = "", ""
            try:
                ar = session.get(url, timeout=TIMEOUT, headers={**HEADERS, "Referer": "https://www.canyin88.com/"})
                ar_soup = BeautifulSoup(ar.content, 'html.parser')
                for p in ar_soup.find_all('p')[:8]:
                    t2 = txt(p)
                    if len(t2) > 30: summary = t2[:200]; break
                img_url = extract_image(ar_soup, url)
            except: pass
            articles.append({"id":mid(url,title),"title":title,"url":url,"source":"红餐网",
                "time":time_str,"summary":summary,"image":img_url,
                "category":"餐饮动态","tags":tags(title,summary)})
    print(f"  ✅ {len(articles)} 篇")
    return articles


# ===== 2. 36氪 =====
def scrape_36kr():
    print("\n[AI] 36氪 (36kr.com)")
    articles = []
    for url in ["https://www.36kr.com/newsflashes", "https://www.36kr.com/information/AI/"]:
        r = safe_get(url)
        if not r: continue
        soup = BeautifulSoup(r.content, 'html.parser')
        for a in soup.find_all('a', href=True):
            m = re.search(r'/p/(\d+)', a['href'])
            if not m: continue
            fu = a['href'] if a['href'].startswith('http') else 'https://www.36kr.com' + a['href']
            title = txt(a)
            if not title or len(title) < 6: continue
            summary, ts, img_url = "", "", ""
            try:
                ar = session.get(fu, timeout=TIMEOUT)
                s2 = BeautifulSoup(ar.content, 'html.parser')
                h1 = s2.find('h1')
                if h1 and len(txt(h1)) > len(title): title = txt(h1)
                md = s2.find('meta', attrs={'name':'description'})
                if md and md.get('content'): summary = md['content'][:200]
                mt = s2.find('meta', attrs={'property':'article:published_time'})
                if mt and mt.get('content'): ts = mt['content']
                img_url = extract_image(s2, fu)
            except: pass
            time_iso = parse_time(ts)
            if not time_iso:
                continue
            articles.append({"id":mid(fu,title),"title":title,"url":fu,"source":"36氪AI",
                "time":time_iso,"summary":summary,"image":img_url,
                "category":classify(title,summary,"36氪"),"tags":tags(title,summary)})
    print(f"  ✅ {len(articles)} 篇")
    return articles


# ===== 3. RSS =====
def scrape_rss():
    print("\n[RSS] RSS")
    import feedparser
    articles = []
    for url, src in [("https://www.36kr.com/feed", "36氪"), ("https://www.36kr.com/feed/newsflash", "36氪快讯")]:
        try:
            fp = feedparser.parse(url)
            for e in fp.entries[:15]:
                title = e.get("title","")
                if not title: continue
                link = e.get("link","")
                raw = (e.get("summary","") or "")
                summary = BeautifulSoup(raw,'html.parser').get_text(strip=True)[:200] if raw else ""
                pub = e.get("published","") or e.get("updated","")
                time_iso = parse_time(pub)
                if not time_iso:
                    time_iso = now_iso()
                articles.append({"id":mid(link,title),"title":title,"url":link,"source":src,
                    "time":time_iso,"summary":summary,"image":"",
                    "category":classify(title,summary,src),"tags":tags(title,summary)})
        except Exception as e:
            print(f"  [SKIP] {url} — {e}")
    print(f"  ✅ {len(articles)} 篇")
    return articles


# ===== 4. 微信公众号 (Exa HTTP API) =====
EXA_API_URL = "https://api.exa.ai"

def exa_search(query, num_results=5):
    """直接HTTP调用Exa搜索API，返回文章列表"""
    api_key = os.environ.get("EXA_API_KEY", "")
    if not api_key:
        print("  [SKIP] EXA_API_KEY 未设置")
        return []
    
    url = f"{EXA_API_URL}/search"
    headers = {"accept": "application/json", "content-type": "application/json", "x-api-key": api_key}
    payload = {"query": query, "numResults": num_results, "useAutoprompt": False}
    
    for _ in range(2):
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=15)
            if r.status_code == 429:
                print("  [LIMIT] Exa 免费额度用尽")
                return []
            r.raise_for_status()
            data = r.json()
            return data.get("results", [])
        except Exception as e:
            if _: print(f"  [WARN] Exa search error: {e}")
            t.sleep(1)
    return []


def exa_fetch(url):
    """直接HTTP调用Exa获取文章内容"""
    api_key = os.environ.get("EXA_API_KEY", "")
    if not api_key:
        return "", ""
    
    api_url = f"{EXA_API_URL}/contents"
    headers = {"accept": "application/json", "content-type": "application/json", "x-api-key": api_key}
    payload = {"urls": [url], "text": {"maxCharacters": 1500}}
    
    try:
        r = requests.post(api_url, json=payload, headers=headers, timeout=20)
        r.raise_for_status()
        data = r.json()
        results = data.get("results", [])
        if results:
            result = results[0]
            text = result.get("text", "")
            pub_date = result.get("publishedDate", "")
            return text, pub_date
    except Exception as e:
        print(f"  [WARN] Exa fetch error {url[:40]}: {e}")
    return "", ""


def scrape_wechat():
    """公众号搜索（Exa HTTP API，兼容本地和GitHub Actions）"""
    print("\n[WX] 公众号 (Exa HTTP API)")
    articles = []
    import time as time_module
    wx_start = time_module.time()
    WX_TIMEOUT = 25  # 整个公众号搜索最多25秒

    # 检测Exa key是否存在，不存在则跳过
    api_key = os.environ.get("EXA_API_KEY", "")
    if not api_key:
        print("  [SKIP] EXA_API_KEY 未设置，跳过公众号搜索")
        return articles

    queries = [
        # 餐饮公众号
        ("餐企老板内参","餐企老板内参"),("餐饮老板内参","餐饮老板内参"),
        ("勇哥餐饮","勇哥餐饮"),("餐饮O2O","餐饮O2O"),("窄门餐眼","窄门餐眼"),
        # 平台类公众号
        ("淘宝闪购本地生活","淘宝闪购本地生活"),
        ("美团餐饮观察","美团餐饮观察"),
        ("淘宝闪购商家课堂","淘宝闪购商家课堂"),
        # 国内互联网大厂AI
        ("阿里AI","阿里 AI"),("腾讯AI","腾讯 AI"),("字节AI","字节 AI"),
        ("百度AI","百度 AI"),
        # 国内AI公司
        ("豆包","豆包"),("DeepSeek","DeepSeek"),("Kimi AI","Kimi"),
        ("智谱AI","智谱AI"),
        # 国际AI公司
        ("OpenAI","OpenAI"),("Anthropic Claude","Anthropic"),
        ("Google Gemini","Google Gemini"),
        # AI+餐饮交叉
        ("AI餐饮行业","AI 餐饮"),("人工智能餐饮","人工智能 餐饮"),
    ]
    seen = set()
    for sname, sterm in queries:
        if time_module.time() - wx_start > WX_TIMEOUT:
            print(f"  [TIMEOUT] 公众号搜索超时，跳过剩余")
            break
        sq = f'site:mp.weixin.qq.com {sterm}'
        results = exa_search(sq, num_results=5)
        if results is None:
            # 额度用尽，提前退出
            break
        for item in results:
            url = item.get("url", "")
            if url in seen: continue
            seen.add(url)
            title = item.get("title", "")
            if not title or len(title) < 8: continue
            summary = item.get("text", "")[:200] if item.get("text") else ""
            published = item.get("publishedDate", "")
            time_iso = parse_time(published)
            if not time_iso:
                time_iso = now_iso()
            articles.append({"id":mid(url,title),"title":title,"url":url,"source":sname,
                "time":time_iso,"summary":summary,"image":"",
                "category":classify(title,summary,sname),"tags":tags(title,summary)})
    print(f"  ✅ {len(articles)} 篇")
    return articles


# ===== MAIN =====
MAX_HISTORY = 10000

def main():
    print("="*50)
    print(f"  餐饮AI情报站 — 数据采集 v3 (历史累积)")
    print(f"  运行时间: {NOW.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50)

    # 收集新文章（不限日期）
    all_new = []
    all_new.extend(scrape_hongcan())
    all_new.extend(scrape_36kr())
    all_new.extend(scrape_rss())
    all_new.extend(scrape_wechat())

    # 新文章去重
    seen = set()
    new_unique = []
    for a in all_new:
        if a["url"] not in seen:
            seen.add(a["url"])
            new_unique.append(a)

    # 读取已有历史数据
    old_articles = []
    if os.path.exists("articles.json"):
        try:
            with open("articles.json", "r", encoding="utf-8") as f:
                old_data = json.load(f)
                old_articles = old_data.get("articles", [])
            print(f"  [HIST] 已有历史: {len(old_articles)} 篇")
        except:
            pass

    # 合并：旧文章优先保留，新文章去重加入
    old_urls = {a["url"] for a in old_articles}
    merged = list(old_articles)
    for a in new_unique:
        if a["url"] not in old_urls:
            merged.append(a)

    # 重新分类、计算评分和推荐理由（覆盖旧文章的错误分类），并过滤无关文章
    merged_filtered = []
    for a in merged:
        cat_result = classify(a["title"], a["summary"], a["source"])
        if isinstance(cat_result, tuple):
            cat, keep = cat_result
        else:
            cat, keep = cat_result, True
        if not keep:
            continue
        a["category"] = cat
        a["score"] = calc_score(a["title"], a["summary"], a["source"], a["time"])
        a["reason"] = gen_reason(a["title"], a["summary"], a["source"], a["score"], a.get("tags", []))
        merged_filtered.append(a)
    merged = merged_filtered

    # 按时间排序（最新的在前）
    merged.sort(key=lambda x: x.get("time", ""), reverse=True)

    # 限制历史总量
    if len(merged) > MAX_HISTORY:
        merged = merged[:MAX_HISTORY]

    # 生成显示字段
    for a in merged:
        try:
            dt = datetime.fromisoformat(a["time"])
            a["date"] = f"{dt.month}月{dt.day}日"
            a["dateSort"] = a["time"][:10]  # "2026-06-10"
            a["timeDisplay"] = f"{dt.hour:02d}:{dt.minute:02d}"
        except:
            a["date"] = "最新"
            a["timeDisplay"] = ""

    out = {"updated": now_iso(), "articleCount": len(merged), "articles": merged}
    with open("articles.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # 统计
    from collections import Counter
    cats = Counter(a['category'] for a in merged)
    srcs = Counter(a['source'] for a in merged)
    dates = Counter(a.get('date','未知') for a in merged)

    print(f"\n{'='*50}")
    print(f"  ✅ 完成！共计 {len(merged)} 篇")
    print(f"  [DATA] 分类: {dict(cats)}")
    print(f"  [R] 信源: {dict(srcs)}")
    print(f"  [CAL] 天数: {len(dates)} 天 ({min(dates.keys())} ~ {max(dates.keys())})")
    print(f"  [FILE] 输出: articles.json")
    print(f"  🕐 更新: {NOW.strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
