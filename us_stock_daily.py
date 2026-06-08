#!/usr/bin/env python3
"""
美股每日推送 Agent — GitHub Actions 版
零成本、无第三方依赖

模式：
1. morning（8:00北京）  — 盘前简报 + 注册今日事件监控
2. event（每30分钟）    — 检查已注册事件是否已结束，结束即推送总结
3. close（22:00北京）  — 收盘总结
"""

import os
import re
import json
import urllib.request
import urllib.parse
import ssl
from datetime import datetime, timedelta

# ================================================================
# 配置
# ================================================================

SCT_KEY = os.environ.get("SCT_KEY", "")

WATCHLIST = [
    "GOOG", "MSFT", "AAPL", "NVDA", "AMD", "KLIC", "TSM", "FORM",
    "SOXL", "PLTR", "CRWV", "VST", "XE", "RKLB", "IONQ", "SHOP",
    "DELL", "NKE", "ABT", "MU", "QCOM", "INTC", "SNDK", "META",
    "AMZN", "GOOS", "F", "VOO", "VGT", "BRK.B", "ENB"
]
HOLDINGS = ["GOOG", "MSFT", "VST", "XE", "NKE", "VOO", "ENB", "ABT", "KLIC", "SHOP"]

# 事件存储（GitHub Actions 用文件模拟持久化）
EVENTS_FILE = "/tmp/watched_events.json"

# 已知事件映射表（手动维护重大事件日）
# 格式：{日期: [{事件名, 关键词, 结束时间(UTC), 关注股票}]}
KNOWN_EVENTS = {
    # 示例格式，实际由 morning 模式动态注册
}


# ================================================================
# 工具函数
# ================================================================

def utc_now():
    return datetime.utcnow()

def beijing_now():
    return utc_now() + timedelta(hours=8)

def fetch_url(url: str, timeout: int = 15) -> str:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"ERROR: {e}"


def push(title: str, content: str):
    url = f"https://sctapi.ftqq.com/{SCT_KEY}.send"
    data = f"title={urllib.parse.quote(title)}&desp={urllib.parse.quote(content)}"
    req = urllib.request.Request(
        url, data=data.encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            result = json.loads(resp.read().decode())
            print(f"Push OK: {title}" if result.get("code") == 0 else f"Push failed: {result}")
    except Exception as e:
        print(f"Push error: {e}")


# ================================================================
# 事件注册与检测
# ================================================================

def load_events():
    """加载已注册的事件列表"""
    if os.path.exists(EVENTS_FILE):
        with open(EVENTS_FILE) as f:
            return json.load(f)
    return []


def save_events(events):
    with open(EVENTS_FILE, "w") as f:
        json.dump(events, f)


def register_today_events():
    """
    晨间简报时，识别并注册今日重大事件。
    通过搜索已知事件日历和新闻来判断。
    """
    events = []
    today = beijing_now().strftime("%Y-%m-%d")

    # 搜索经济日历
    calendar_events = search_todays_events()
    for evt in calendar_events:
        evt["date"] = today
        evt["pushed"] = False
        events.append(evt)

    save_events(events)
    return events


def search_todays_events() -> list:
    """搜索今日重大事件"""
    events = []
    today = beijing_now().strftime("%B %d, %Y")

    # 1. 搜索已知经济数据发布日程
    # MarketWatch / CNBC 经济日历
    url = "https://feeds.content.dowjones.io/public/rss/mw_topstories"
    data = fetch_url(url)
    if not data.startswith("ERROR"):
        headlines = re.findall(r"<title>(.+?)</title>", data)[1:]
        for h in headlines[:20]:
            upper = h.upper()
            for keyword, category in [
                ("CPI", "CPI通胀数据"), ("PPI", "PPI数据"),
                ("NFP", "非农就业"), ("NONFARM", "非农就业"),
                ("JOBS REPORT", "就业报告"), ("FED", "美联储"),
                ("FOMC", "FOMC决议"), ("RATE", "利率决定"),
                ("INFLATION", "通胀数据"), ("GDP", "GDP数据"),
                ("RETAIL SALES", "零售数据"), ("CONSUMER CONFIDENCE", "消费者信心"),
                ("ISM", "ISM制造业"), ("PMI", "PMI数据"),
                ("WWDC", "Apple WWDC"), ("COMPUTEX", "Computex"),
                ("EARNINGS", "财报"),
            ]:
                if keyword in upper:
                    # 提取相关股票
                    related = [s for s in WATCHLIST if s in upper]
                    events.append({
                        "name": h,
                        "category": category,
                        "keywords": keyword,
                        "related": related if related else WATCHLIST[:5],
                        "check_type": "data_release",
                    })
                    break

    # 2. 检查 CNBC 头条是否有重大事件
    cnbc = fetch_url("https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114")
    if not cnbc.startswith("ERROR"):
        titles = re.findall(r"<title><!\[CDATA\[(.+?)\]\]></title>", cnbc)
        for t in titles[:15]:
            upper = t.upper()
            for keyword, category in [
                ("CPI", "CPI"), ("PPI", "PPI"), ("NFP", "非农"),
                ("FED", "美联储"), ("FOMC", "FOMC"), ("POWELL", "鲍威尔讲话"),
                ("WWDC", "WWDC"), ("APPLE", "Apple事件"),
                ("COMPUTEX", "Computex"), ("SPACE", "太空/SpaceX"),
                ("EARNINGS", "财报季"), ("IPO", "重大IPO"),
                ("MICRON", "MU财报"), ("NVIDIA", "NVDA相关"),
            ]:
                if keyword in upper:
                    related = [s for s in WATCHLIST if s in upper]
                    events.append({
                        "name": t,
                        "category": category,
                        "keywords": keyword,
                        "related": related if related else ["VOO", "SPY"],
                        "check_type": "news_event",
                    })
                    break

    # 去重（按关键词+日期）
    seen = set()
    unique = []
    for e in events:
        key = f"{e['keywords']}_{e['category']}"
        if key not in seen:
            seen.add(key)
            unique.append(e)

    return unique


def check_event_completed(event: dict) -> tuple:
    """
    检查一个事件是否已经完成/结果已发布。
    返回 (是否完成, 结果摘要)
    """
    keyword = event.get("keywords", "")
    name = event.get("name", "")
    check_type = event.get("check_type", "news_event")

    if not keyword:
        return False, ""

    # 搜索新闻，看是否已有结果
    search_terms = f"{keyword} results announced today 2026"
    url = f"https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114&term={urllib.parse.quote(keyword)}"
    data = fetch_url(url)

    if data.startswith("ERROR"):
        return False, ""

    titles = re.findall(r"<title><!\[CDATA\[(.+?)\]\]></title>", data)
    if not titles:
        # 尝试 Reuters
        reuters_url = f"https://www.reuters.com/search/news?query={urllib.parse.quote(keyword)}&dateRange=pastWeek"
        reuters_data = fetch_url(reuters_url)

    # 检查标题中是否有"结果"、"发布"、"actual"、"beats"、"misses"等关键词
    result_keywords = ["beats", "misses", "rises", "falls", "surges", "drops",
                       "actual", "released", "announced", "data shows",
                       "高于预期", "低于预期", "符合预期", "发布", "公布",
                       "超预期", "不及预期"]

    for t in titles[:10]:
        lower = t.lower()
        if any(kw in lower for kw in result_keywords):
            return True, t

    # 如果没找到结果标题，但找到了相关更新新闻
    if titles and len(titles) > 0:
        # 检查时间戳（如果有的话）
        return len(titles) > 2, titles[0]  # 有多条新闻说明事件在进行中

    return False, ""


def build_event_summary(event: dict) -> tuple:
    """为已完成的事件构建推送内容"""
    name = event.get("name", event.get("keywords", ""))
    category = event.get("category", "未知")
    related = event.get("related", [])

    # 获取相关股票行情
    prices = fetch_yahoo_quotes()

    sections = []
    sections.append(f"📊 {category}：{name}")
    sections.append("")

    # 对相关股票的影响
    if prices and related:
        sections.append("【相关标的反应】")
        for sym in related[:8]:
            if sym in prices:
                p = prices[sym]
                change = p["change_pct"]
                sign = "+" if change >= 0 else ""
                emoji = "🟢" if change >= 0 else "🔴"
                sections.append(f"  {emoji} {sym}  ${p['price']}  {sign}{change}%")
        sections.append("")

    sections.append("【建议】")
    sections.append("  关注后续走势，如有异常波动建议调整仓位")

    content = "\n".join(sections)
    title = f"📊 {category} 结果"
    return title, content


# ================================================================
# 行情数据
# ================================================================

def fetch_yahoo_quotes() -> dict:
    results = {}
    symbols = ",".join(ticker.replace(".", "%2E") for ticker in WATCHLIST)
    url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbols}&fields=regularMarketPrice,regularMarketChangePercent,regularMarketChange"
    data = fetch_url(url)
    if data.startswith("ERROR"):
        return {}
    try:
        j = json.loads(data)
        for q in j.get("quoteResponse", {}).get("result", []):
            sym = q.get("symbol", "")
            price = q.get("regularMarketPrice", 0)
            change_pct = q.get("regularMarketChangePercent", 0)
            change = q.get("regularMarketChange", 0)
            results[sym] = {
                "price": round(price, 2),
                "change_pct": round(change_pct, 2),
                "change": round(change, 2),
            }
    except Exception:
        pass
    return results


# ================================================================
# 新闻获取
# ================================================================

def fetch_latest_news() -> list:
    """获取最新财经新闻"""
    news = []

    # CNBC
    cnbc = fetch_url("https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114")
    if not cnbc.startswith("ERROR"):
        titles = re.findall(r"<title><!\[CDATA\[(.+?)\]\]></title>", cnbc)
        for t in titles[:8]:
            news.append({"source": "CNBC", "title": t})

    # MarketWatch
    mw = fetch_url("https://feeds.content.dowjones.io/public/rss/mw_topstories")
    if not mw.startswith("ERROR"):
        titles = re.findall(r"<title>(.+?)</title>", mw)
        for t in titles[1:6]:
            news.append({"source": "MarketWatch", "title": t})

    return news


# ================================================================
# 推送内容构建
# ================================================================

def build_morning_brief():
    """每日盘前简报"""
    today = beijing_now().strftime("%Y-%m-%d")
    sections = []
    sections.append(f"📅 今日美股大事记  {today}（北京时间）")
    sections.append("")

    # 持仓行情
    prices = fetch_yahoo_quotes()
    if prices:
        sections.append("【持仓行情】")
        for sym in HOLDINGS:
            if sym in prices:
                p = prices[sym]
                sign = "+" if p["change_pct"] >= 0 else ""
                emoji = "🟢" if p["change_pct"] >= 0 else "🔴"
                sections.append(f"  {emoji} {sym}  ${p['price']}  {sign}{p['change_pct']}%")
        sections.append("")

        # Watchlist 异动
        movers = sorted(
            [(s, p) for s, p in prices.items() if p["change_pct"] != 0],
            key=lambda x: abs(x[1]["change_pct"]), reverse=True
        )
        if movers:
            sections.append("【Watchlist 异动】")
            for sym, p in movers[:5]:
                sign = "+" if p["change_pct"] >= 0 else ""
                emoji = "🟢" if p["change_pct"] >= 0 else "🔴"
                sections.append(f"  {emoji} {sym}  ${p['price']}  {sign}{p['change_pct']}%")
            sections.append("")

    # 宏观事件
    macro = fetch_economic_calendar()
    if macro:
        sections.append("【宏观经济事件】")
        for e in macro:
            sections.append(f"  • [{e['category']}] {e['title']}")
        sections.append("")

    # 今日新闻
    news = fetch_latest_news()
    if news:
        sections.append("【今日新闻】")
        for n in news[:6]:
            sections.append(f"  • {n['title']}")
        sections.append("")

    content = "\n".join(sections)
    return f"📅 今日美股大事记 {today}", content


def fetch_economic_calendar() -> list:
    """获取宏观经济事件"""
    events = []
    urls = [
        ("https://feeds.content.dowjones.io/public/rss/mw_topstories", "宏观"),
        ("https://feeds.content.dowjones.io/public/rss/mw_marketpulse", "市场"),
    ]
    keywords = ["CPI", "PPI", "NFP", "JOBS", "FED", "RATE", "INFLATION", "GDP", "TREASURY", "FOMC"]

    for url, cat in urls:
        data = fetch_url(url)
        if not data.startswith("ERROR"):
            titles = re.findall(r"<title>(.+?)</title>", data)
            for t in titles[1:6]:
                if any(k in t.upper() for k in keywords):
                    events.append({"title": t, "category": cat})
    return events


def build_close_summary():
    """收盘总结"""
    today = beijing_now().strftime("%Y-%m-%d")
    prices = fetch_yahoo_quotes()
    sections = []
    sections.append(f"📊 美股收盘  {today}")
    sections.append("")

    if prices:
        sections.append("【持仓表现】")
        for sym in HOLDINGS:
            if sym in prices:
                p = prices[sym]
                sign = "+" if p["change_pct"] >= 0 else ""
                emoji = "🟢" if p["change_pct"] >= 0 else "🔴"
                sections.append(f"  {emoji} {sym}  ${p['price']}  {sign}{p['change_pct']}%")
        sections.append("")

        sections.append("【异动 >5%】")
        moved = False
        for sym, p in prices.items():
            if abs(p["change_pct"]) >= 5:
                sign = "+" if p["change_pct"] >= 0 else ""
                emoji = "🟢" if p["change_pct"] >= 0 else "🔴"
                sections.append(f"  {emoji} {sym}  ${p['price']}  {sign}{p['change_pct']}%")
                moved = True
        if not moved:
            sections.append("  无大幅异动")

    content = "\n".join(sections)
    return f"📊 美股收盘 {today}", content


# ================================================================
# 主入口
# ================================================================

def main():
    if not SCT_KEY:
        print("ERROR: SCT_KEY 环境变量未设置")
        return

    bjh = beijing_now().hour
    utc_h = utc_now().hour

    # 自动判断模式
    if bjh >= 6 and bjh < 12:
        mode = "morning"
    elif bjh >= 12 and bjh < 15:
        mode = "event"
    elif bjh >= 15 and bjh < 23:
        mode = "event"
    else:
        mode = "close"

    print(f"Mode: {mode} (Beijing hour: {bjh}, UTC hour: {utc_h})")

    if mode == "morning":
        # 晨间简报 + 注册今日事件
        title, content = build_morning_brief()
        push(title, content)

        # 注册今日监控事件
        events = register_today_events()
        print(f"Registered {len(events)} events for monitoring today")

    elif mode == "event":
        # 检查已注册事件是否已出结果
        events = load_events()
        for evt in events:
            if evt.get("pushed"):
                continue
            done, headline = check_event_completed(evt)
            if done:
                evt["pushed"] = True
                evt["result"] = headline
                save_events(events)

                title, content = build_event_summary(evt)
                push(title, content)
                print(f"Event completed: {evt['name']}")

    elif mode == "close":
        title, content = build_close_summary()
        push(title, content)
    else:
        print(f"Unknown mode: {mode}")


if __name__ == "__main__":
    main()
