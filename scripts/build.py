#!/usr/bin/env python3
"""把 data/*.json 生成静态站到 dist/。零依赖，只需 Python 3.9+。

环境变量：
  BASE_PATH  站点子路径。GitHub Pages 项目站填 "/404-soft"，自定义域名或 Cloudflare Pages 留空。
  SITE_URL   站点完整地址（用于 sitemap），例：https://six997.github.io/404-soft
"""
import datetime
import html
import json
import os
import re
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
BASE = (os.getenv("BASE_PATH") or "").rstrip("/")
SITE_URL = (os.getenv("SITE_URL") or "").rstrip("/")
SITE = "404绿色软件库"
SLOGAN = "只收录官方下载入口，每个文件都附 SHA-256 校验。"
PLATFORMS = ["Windows", "macOS", "Linux", "Android"]

e = html.escape


def load(name, default=None):
    p = os.path.join(ROOT, "data", name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default


def url(path):
    return f"{BASE}{path}"


def human_size(n):
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def ago(date_str):
    d = (datetime.date.today() - datetime.date.fromisoformat(date_str)).days
    if d <= 0:
        return "今天"
    if d == 1:
        return "昨天"
    if d < 30:
        return f"{d} 天前"
    return date_str


def md(text):
    """极简 Markdown：标题、列表、粗体、行内代码、链接。足够渲染 GitHub 更新日志。"""
    out, in_list = [], False
    for raw in text.replace("\r", "").split("\n"):
        line = e(raw.rstrip())
        line = re.sub(r"`([^`]+)`", r"<code>\1</code>", line)
        line = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", line)
        line = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', line)
        m = re.match(r"^\s*[-*+]\s+(.*)", line)
        if m:
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{m.group(1)}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        h = re.match(r"^(#{1,6})\s+(.*)", line)
        if h:
            out.append(f"<h4>{h.group(2)}</h4>")
        elif line.strip():
            out.append(f"<p>{line}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def ad(slot):
    return f'<div class="ad-slot" data-ad="{slot}"></div>'


def icon(item, size="md"):
    if item.get("icon"):
        return f'<img class="icon {size}" src="{url(item["icon"])}" alt="{e(item["name"])}" loading="lazy">'
    return f'<span class="icon {size} letter" data-hue="{sum(map(ord, item["slug"])) % 360}">{e(item.get("abbr") or item["name"][:2])}</span>'


def layout(title, body, desc=SLOGAN, active=""):
    cats = load("categories.json", {})
    nav = "".join(
        f'<a href="{url("/category/" + k + "/")}" class="{"on" if active == k else ""}">{e(v)}</a>'
        for k, v in cats.items() if k in USED_CATS
    )
    year = datetime.date.today().year
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="icon" href="{url('/static/favicon.svg')}" type="image/svg+xml">
<link rel="stylesheet" href="{url('/static/style.css')}">
<script>document.documentElement.dataset.theme=localStorage.theme||"";window.BASE="{BASE}";</script>
</head>
<body>
<header class="topbar">
  <div class="container bar">
    <a class="logo" href="{url('/')}"><span class="logo-mark">404</span>绿色软件库</a>
    <nav class="nav">{nav}</nav>
    <div class="bar-actions">
      <a class="icon-btn" href="{url('/')}#search" aria-label="搜索">⌕</a>
      <button class="icon-btn" id="theme" aria-label="切换深色">☾</button>
    </div>
  </div>
</header>
<main class="container">
{body}
</main>
<div class="container">{ad("footer")}</div>
<footer class="footer">
  <div class="container">
    <p><strong>{SITE}</strong> · 仅提供官方合法下载入口与开源许可允许的镜像。我们与软件作者及项目方无隶属关系。</p>
    <p><a href="{url('/about/')}">关于与规范</a> · <a href="{url('/sitemap.xml')}">网站地图</a> · © {year}</p>
  </div>
</footer>
<script src="{url('/static/app.js')}" defer></script>
</body>
</html>"""


def card(item, rel):
    plats = "".join(f'<span class="plat">{p}</span>' for p in item["platforms"])
    if item.get("green"):
        plats = '<span class="plat green">绿色版</span>' + plats
    return f"""<a class="soft-card" href="{url('/software/' + item['slug'] + '/')}" data-platforms="{' '.join(item['platforms'])}{' 绿色版' if item.get('green') else ''}" data-name="{e((item['name'] + ' ' + ' '.join(item.get('tags', []))).lower())}">
  {icon(item)}
  <div class="soft-main">
    <h3>{e(item['name'])} <span class="ver">{e(rel.get('version', ''))}</span></h3>
    <p>{e(item['summary'])}</p>
    <div class="plats">{plats}</div>
  </div>
  <time>{ago(rel['released']) if rel.get('released') else ''}</time>
</a>"""


def sidebar(items, releases, cats):
    cat_links = "".join(
        f'<li><a href="{url("/category/" + k + "/")}">{e(v)}<span>{sum(1 for i in items if i["category"] == k)}</span></a></li>'
        for k, v in cats.items() if k in USED_CATS
    )
    recent = sorted(items, key=lambda i: releases.get(i["slug"], {}).get("released", ""), reverse=True)[:8]
    recent_li = "".join(
        f'<li><a href="{url("/software/" + i["slug"] + "/")}">{e(i["name"])} <em>{e(releases.get(i["slug"], {}).get("version", ""))}</em></a></li>'
        for i in recent
    )
    return f"""<aside class="side">
  <section class="panel"><h2>分类</h2><ul class="cat-list">{cat_links}</ul></section>
  {ad("sidebar")}
  <section class="panel"><h2>最近更新</h2><ul class="rank">{recent_li}</ul></section>
</aside>"""


def page_home(items, releases, cats):
    rel = lambda i: releases.get(i["slug"], {}).get("released") or ""
    pinned = [i for i in items if i.get("featured")]
    recent = sorted((i for i in items if i.get("icon") and rel(i) and not i.get("featured")), key=rel, reverse=True)
    slides = (pinned + recent)[:6] or items[:1]
    slide_html = "".join(
        f'''<a class="slide{' on' if n == 0 else ''}" href="{url('/software/' + s['slug'] + '/')}">
    {icon(s, 'lg')}
    <div><span class="badge">{"站长推荐" if s.get("featured") else "最新更新"}</span><h2>{e(s['name'])} {e(releases.get(s['slug'], {}).get('version', ''))}</h2><p>{e(s['summary'])}</p></div>
  </a>''' for n, s in enumerate(slides))
    dots = "".join(f'<button class="dot{" on" if n == 0 else ""}" aria-label="第 {n + 1} 项"></button>' for n in range(len(slides))) if len(slides) > 1 else ""
    today = datetime.date.today().isoformat()
    today_n = sum(1 for i in items if releases.get(i["slug"], {}).get("released") == today)
    chips = '<button class="chip on" data-plat="">全部</button>' + "".join(
        f'<button class="chip" data-plat="{p}">{p}</button>' for p in PLATFORMS if any(p in i["platforms"] for i in items)
    ) + '<button class="chip" data-plat="绿色版">绿色版</button>'
    ordered = sorted(items, key=lambda i: releases.get(i["slug"], {}).get("released", ""), reverse=True)
    cards = []
    for n, i in enumerate(ordered, 1):
        cards.append(card(i, releases.get(i["slug"], {})))
        if n % 6 == 0:
            cards.append(ad("feed"))
    hot = " ".join(f'<button class="hot" data-q="{e(i["name"])}">{e(i["name"])}</button>' for i in [x for x in items if x.get("hot")][:6] or items[:6])
    body = f"""
<section class="hero" id="search">
  <h1>找对软件，从官方入口开始</h1>
  <p>{SLOGAN}</p>
  <div class="search"><input id="q" type="search" placeholder="搜索软件名或用途，如：截图、密码" autocomplete="off"></div>
  <div class="hots">热门：{hot}</div>
</section>
{ad("home-top")}
<div class="featured" id="featured">
  {slide_html}
  <div class="dots">{dots}</div>
</div>
<div class="layout">
  <section>
    <div class="list-head">
      <h2>最新发布 <small>共 {len(items)} 款 · 今日更新 {today_n}</small></h2>
      <div class="chips">{chips}</div>
    </div>
    <div class="soft-list" id="list">{''.join(cards)}</div>
    <p class="empty" id="empty" hidden>没有匹配的软件，换个关键词试试。</p>
    <button class="more" id="more" hidden>加载更多</button>
  </section>
  {sidebar(items, releases, cats)}
</div>"""
    return layout(f"{SITE} · 官方软件下载目录", body)


def page_category(key, name, items, releases, cats):
    sub = [i for i in items if i["category"] == key]
    sub.sort(key=lambda i: releases.get(i["slug"], {}).get("released", ""), reverse=True)
    cards = "".join(card(i, releases.get(i["slug"], {})) for i in sub)
    body = f"""
<nav class="crumb"><a href="{url('/')}">首页</a> › {e(name)}</nav>
<div class="layout">
  <section>
    <div class="list-head"><h2>{e(name)} <small>{len(sub)} 款</small></h2></div>
    <div class="soft-list">{cards}</div>
  </section>
  {sidebar(items, releases, cats)}
</div>"""
    return layout(f"{name} · {SITE}", body, f"{name}类软件官方下载", key)


def page_detail(item, rel, items, releases, cats):
    cat = cats.get(item["category"], item["category"])
    plats = ('<span class="plat green">绿色版</span>' if item.get("green") else "") + "".join(f'<span class="plat">{p}</span>' for p in item["platforms"])
    intro = "".join(f"<p>{e(p)}</p>" for p in item.get("intro", "").split("\n\n") if p.strip())
    feats = "".join(f"<li>{e(f)}</li>" for f in item.get("features", []))
    tips = "".join(f"<li>{e(t)}</li>" for t in item.get("tips", []))
    shots = "".join(f'<img src="{url(s)}" alt="{e(item["name"])} 截图" loading="lazy">' for s in item.get("screenshots", []))
    manual = item.get("manual_mirrors", {})

    rows = []
    for d in rel.get("downloads", []):
        mirrors = list(d.get("mirrors", [])) + manual.get(d["label"], [])
        mbtn = "".join(
            f'<a class="btn ghost{"" if m.get("ok", True) else " bad"}" href="{e(m["url"])}" target="_blank" rel="noopener">{e(m["name"])}{" · 提取码 " + e(m["code"]) if m.get("code") else ""}{"（异常）" if not m.get("ok", True) else ""}</a>'
            for m in mirrors
        )
        sha = d.get("sha256", "")
        shabox = f'<button class="sha" data-sha="{sha}" title="点击复制 SHA-256">SHA-256 <code>{sha[:12]}…{sha[-6:]}</code></button>' if sha else ""
        rows.append(f"""<li class="dl">
  <div class="dl-info"><strong>{e(d['label'])}{' <span class="plat green">绿色免安装</span>' if d.get('portable') else ''}</strong><span>{e(d['file'])}{' · ' + human_size(d['size']) if d.get('size') else ''}</span>{shabox}</div>
  <div class="dl-btns"><a class="btn" href="{e(d['official'])}" target="_blank" rel="noopener">官方下载</a>{mbtn}</div>
</li>""")
    dl_page = e(item.get("download_page") or item.get("homepage", ""))
    downloads = "".join(rows) or f'<li class="dl"><div class="dl-info"><strong>官方下载</strong><span>本站只提供官网入口，请到官方网站下载最新版。</span></div><div class="dl-btns"><a class="btn" href="{dl_page}" target="_blank" rel="noopener">前往官网</a></div></li>'

    links = [("官方网站", item.get("homepage"))]
    if item.get("source", {}).get("type") == "winget":
        links += [("winget 清单", rel.get("release_url"))]
    if item.get("source", {}).get("repo"):
        repo = item["source"]["repo"]
        links += [("发布页", rel.get("release_url")), ("源代码", f"https://github.com/{repo}")]
    link_html = "".join(f'<a href="{e(u)}" target="_blank" rel="noopener">{n} ↗</a>' for n, u in links if u)

    related = [i for i in items if i["slug"] != item["slug"] and (i["category"] == item["category"] or (set(i.get("tags", [])) & set(item.get("tags", [])) - {"绿色版"}))]
    related = related or [i for i in items if i["slug"] != item["slug"]]
    rel_html = "".join(card(i, releases.get(i["slug"], {})) for i in related[:4])

    changelog = f"""<details class="panel changelog"><summary>更新日志 · {e(rel.get('version', ''))}</summary><div class="md">{md(rel['changelog'])}</div></details>""" if rel.get("changelog") else ""

    body = f"""
<nav class="crumb"><a href="{url('/')}">首页</a> › <a href="{url('/category/' + item['category'] + '/')}">{e(cat)}</a> › {e(item['name'])}</nav>
<div class="layout">
  <article>
    <header class="panel detail-head">
      {icon(item, 'lg')}
      <div class="dh-main">
        <h1>{e(item['name'])} <span class="ver">{e(rel.get('version', ''))}</span></h1>
        <p>{e(item['summary'])}</p>
        <div class="plats">{plats}<span class="plat lic">{e(item.get('license', ''))}</span></div>
        <div class="meta">发布 {e(rel.get('released', '-'))} · 核验 {e(rel.get('verified', '-'))}</div>
      </div>
      <a class="btn big" href="#download">立即下载</a>
    </header>
    {f'<div class="shots">{shots}</div>' if shots else ''}
    <section class="panel prose"><h2>软件简介</h2>{intro}<div class="ext-links">{link_html}</div></section>
    {f'<section class="panel prose"><h2>功能特点</h2><ul class="feat">{feats}</ul></section>' if feats else ''}
    {changelog}
    {ad("detail-mid")}
    <section class="panel" id="download">
      <h2>下载地址</h2>
      <p class="note">官方下载直接指向软件作者的发布地址；网盘镜像为同一文件的转存，下载后可用 SHA-256 核对。</p>
      <ul class="dl-list">{downloads}</ul>
    </section>
    {f'<section class="panel prose"><h2>使用提示</h2><ul>{tips}</ul></section>' if tips else ''}
    {ad("detail-bottom")}
    <section><h2 class="sec-title">相关推荐</h2><div class="soft-list">{rel_html}</div></section>
  </article>
  {sidebar(items, releases, cats)}
</div>"""
    return layout(f"{item['name']} {rel.get('version', '')} 官方下载 · {SITE}", body, item["summary"], item["category"])


def page_about(items, releases, cats):
    body = f"""
<nav class="crumb"><a href="{url('/')}">首页</a> › 关于与规范</nav>
<div class="layout">
  <article class="panel prose">
    <h1>关于与规范</h1>
    <p>{SITE} 是一个轻量的软件下载目录，目标是缩短从「找到软件」到「安全装上」的距离。</p>
    <h2>收录规范</h2>
    <ul>
      <li>只收录免费、开源或官方提供免费版本的软件。</li>
      <li>不提供破解、注册机、去授权或任何修改版。</li>
      <li>下载按钮优先指向官方发布地址；网盘镜像只用于许可证允许再分发的软件，且与官方文件哈希一致。</li>
      <li>版本信息由脚本定时从官方发布页同步，页面上的「核验日期」即最近一次同步时间。</li>
    </ul>
    <h2>如何校验文件</h2>
    <p>Windows：<code>certutil -hashfile 文件名 SHA256</code><br>macOS / Linux：<code>shasum -a 256 文件名</code></p>
    <h2>反馈与投诉</h2>
    <p>链接失效、版本过旧或权利人要求下架，请在 GitHub 仓库提交 Issue。</p>
  </article>
  {sidebar(items, releases, cats)}
</div>"""
    return layout(f"关于与规范 · {SITE}", body)


def write(path, content):
    full = os.path.join(DIST, path.lstrip("/"))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


USED_CATS = set()


def main():
    items = load("catalog.json", [])
    releases = load("releases.json", {})
    cats = load("categories.json", {})
    for i in items:
        r = releases.get(i["slug"], {})
        i["platforms"] = [p for p in PLATFORMS if any(d["platform"] == p for d in r.get("downloads", []))] or i.get("platforms", [])
        i["green"] = any(d.get("portable") for d in r.get("downloads", []))
        USED_CATS.add(i["category"])

    shutil.rmtree(DIST, ignore_errors=True)
    shutil.copytree(os.path.join(ROOT, "static"), os.path.join(DIST, "static"))
    if os.path.isdir(os.path.join(ROOT, "assets")):
        shutil.copytree(os.path.join(ROOT, "assets"), os.path.join(DIST, "assets"))
    shutil.copy(os.path.join(ROOT, "data", "ads.json"), os.path.join(DIST, "ads.json"))

    write("/index.html", page_home(items, releases, cats))
    write("/about/index.html", page_about(items, releases, cats))
    for k in USED_CATS:
        write(f"/category/{k}/index.html", page_category(k, cats.get(k, k), items, releases, cats))
    for i in items:
        write(f"/software/{i['slug']}/index.html", page_detail(i, releases.get(i["slug"], {}), items, releases, cats))
    write("/404.html", layout(f"页面不存在 · {SITE}", f'<section class="hero"><h1>404</h1><p>这个页面不存在，但软件库还在。</p><a class="btn" href="{url("/")}">回到首页</a></section>'))

    paths = ["/", "/about/"] + [f"/category/{k}/" for k in USED_CATS] + [f"/software/{i['slug']}/" for i in items]
    write("/sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
          + "".join(f"<url><loc>{SITE_URL}{p}</loc></url>" for p in paths) + "</urlset>")
    write("/robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")
    open(os.path.join(DIST, ".nojekyll"), "w").close()
    print(f"已生成 {len(paths)} 个页面 -> dist/")


if __name__ == "__main__":
    main()
