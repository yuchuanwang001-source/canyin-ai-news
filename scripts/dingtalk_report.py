#!/usr/bin/env python3
"""钉钉日报发送脚本 — 在GitHub Actions上运行"""
import json, os, sys
from datetime import datetime, timezone, timedelta
from collections import Counter

try:
    import urllib.request
    HAS_REQUESTS = False
except:
    HAS_REQUESTS = True
    import requests

WEBSITE_URL = 'https://yuchuanwang001-source.github.io/canyin-ai-news/articles.json'
AIHOT_URL = 'https://aihot.virxact.com/api/public/daily'
TZ = timezone(timedelta(hours=8))
NOW = datetime.now(TZ)
SKIP_KW = ['广告', '推广', '招商', '加盟', '诚邀', '报名通道', '点击领取']
PREFIXES = ['[HOT]', '[R]', '[CHAIN]', '[POLICY]', '[DATA]', '[TREND]', '[AI]', '[MONEY]', '[GLOBAL]', '[FD]']
WEEKDAYS = ['星期一','星期二','星期三','星期四','星期五','星期六','星期日']

def fetch(url, headers=None):
    h = headers or {}
    try:
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception as e:
        print(f"Fetch error: {e}", file=sys.stderr)
        return None

def clean(r):
    if not r: return ''
    for p in PREFIXES:
        if r.startswith(p):
            r = r[len(p):].strip()
            break
    return r.lstrip(': ').strip()

def is_low(t):
    return any(k in t for k in SKIP_KW)

def select(articles, cat, n=5, ms=45):
    f = [a for a in articles if a.get('category')==cat and a.get('score',0)>=ms and not is_low(a.get('title',''))]
    seen = set()
    u = []
    for a in f:
        if a['title'] not in seen:
            seen.add(a['title'])
            u.append(a)
    # 按时间排序（最新优先），时间相同的按分数
    u.sort(key=lambda x: (x.get('dateSort', ''), x.get('time', '')), reverse=True)
    return u[:n]

def section(title, articles, fb=''):
    lines = [f'### {title}', '']
    if not articles:
        if fb: lines.append(f'> ⚠️ {fb}')
        lines.append('')
        return '\n'.join(lines)
    for i, a in enumerate(articles, 1):
        t = a.get('title','')
        u = a.get('url','')
        s = a.get('source','')
        r = clean(a.get('reason',''))
        if u: lines.append(f'**{i}️⃣ [{t}]({u})**')
        else: lines.append(f'**{i}️⃣ {t}**')
        c = a.get('summary','') or r
        if len(c) > 150: c = c[:147]+'...'
        if c: lines.append(c)
        if r and len(r)<=50: lines.append(f'> *推荐理由：{r}*')
        lines.append(f'来源：{s}')
        lines.append('')
    return '\n'.join(lines)

def ai_section(aihot, articles):
    lines = ['### 🤖 AI行业', '']
    items = []
    if aihot:
        for sec in aihot.get('sections',[]):
            for item in sec.get('items',[]):
                item['_label'] = sec.get('label','')
                items.append(item)
    if not items:
        ai = select(articles, 'AI动态', 4, 45)
        for a in ai:
            items.append({'title':a['title'],'sourceUrl':a.get('url',''),'sourceName':a.get('source',''),'summary':a.get('summary','') or clean(a.get('reason','')),'_label':'行业动态'})
    if not items:
        lines.append('> ⚠️ 今日AI板块暂无更新')
        lines.append('')
        return '\n'.join(lines)
    for i, item in enumerate(items[:4], 1):
        t,u,s = item.get('title',''), item.get('sourceUrl',''), item.get('sourceName','')
        lines.append(f'**{i}️⃣ [{t}]({u})**' if u else f'**{i}️⃣ {t}**')
        c = (item.get('summary','') or '')[:150]
        lines.append(c)
        lines.append(f'来源：{s}')
        lines.append('')
    return '\n'.join(lines)

def main():
    tokens = []
    t1 = os.environ.get('DINGTALK_TOKEN', '')
    if t1: tokens.append(t1)
    t2 = os.environ.get('DINGTALK_TOKEN2', '')
    if t2: tokens.append(t2)
    if not tokens:
        print('ERROR: no DINGTALK_TOKEN set', file=sys.stderr)
        sys.exit(1)

    website = fetch(WEBSITE_URL)
    aihot = fetch(AIHOT_URL, headers={'User-Agent': 'Mozilla/5.0'})
    if not website:
        print('ERROR: cannot fetch articles.json', file=sys.stderr)
        # 仍然尝试发送告警失败消息
        payload = {'msgtype':'text','text':{'content':'[餐饮AI日报告警] 无法获取网站数据，日报未发送'}}
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(f'https://oapi.dingtalk.com/robot/send?access_token={token}', data=data, headers={'Content-Type':'application/json'}, method='POST')
        try:
            urllib.request.urlopen(req, timeout=10)
        except: pass
        sys.exit(1)

    articles = website.get('articles', [])
    print(f'Articles: {len(articles)}')

    now = NOW
    date_str = now.strftime('%Y.%m.%d')
    weekday = WEEKDAYS[now.weekday()]

    canyin = select(articles, '餐饮动态', 5, 45)
    waimai = select(articles, '平台政策', 4, 45)

    parts = [
        f'## 📡 餐饮AI情报站 · {date_str} {weekday}',
        '每天3分钟，读懂今天的餐饮圈与AI圈', '',
        '---', '',
    ]
    fb = '今日餐饮动态暂无更新' if not canyin else ''
    parts.append(section('🍔 餐饮动态', canyin, fb))
    parts.extend(['', '---', ''])
    fb2 = '今日暂无平台政策/规则变动' if not waimai else ''
    parts.append(section('🛵 外卖/即时零售', waimai, fb2))
    parts.extend(['', '---', ''])
    parts.append(ai_section(aihot, articles))
    parts.extend(['', '---', ''])
    total = len(canyin)+len(waimai)
    parts.append(f'📡 *信息来源：红餐网 / 36氪 / AIHOT | 今日共{total}条*')
    report = '\n'.join(parts)

    if len(report) > 3800:
        site_url = WEBSITE_URL.replace('/articles.json', '')
        report = report[:3700] + f'\n\n...内容过长，请访问 [餐饮AI情报站]({site_url}) 查看完整版'

    success_count = 0
    for i, token in enumerate(tokens):
        payload = {
            'msgtype': 'markdown',
            'markdown': {
                'title': f'餐饮AI情报站 · {date_str}',
                'text': report
            }
        }
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(
            f'https://oapi.dingtalk.com/robot/send?access_token={token}',
            data=data, headers={'Content-Type':'application/json'},
            method='POST'
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                result = json.loads(r.read().decode('utf-8'))
                if result.get('errcode') == 0:
                    print(f'SUCCESS: report sent to group {i+1}')
                    success_count += 1
                else:
                    print(f'Group {i+1} FAILED: {result}', file=sys.stderr)
        except Exception as e:
            print(f'Group {i+1} FAILED: {e}', file=sys.stderr)
    
    if success_count == 0:
        sys.exit(1)

if __name__ == '__main__':
    main()
