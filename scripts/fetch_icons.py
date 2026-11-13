#!/usr/bin/env python3
"""从各软件官网抓取官方图标，存到 static/icons/<slug>.png|svg 并写回 catalog.json 的 icon 字段。

用法: python3 scripts/fetch_icons.py [--force] [slug ...]
已有 icon 的条目默认跳过。抓不到的保持字母占位。
"""
import io, json, re, sys, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "data" / "catalog.json"
OUT = ROOT / "static" / "icons"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
SIZE = 128
MIN = 32


def get(url, limit=4_000_000):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.geturl(), r.headers.get("Content-Type", ""), r.read(limit)


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.icons, self.manifest = [], None

    def handle_starttag(self, tag, a):
        a = dict(a)
        if tag == "link" and a.get("href"):
            rel = (a.get("rel") or "").lower()
            if "icon" in rel:
                m = re.search(r"(\d+)x\d+", a.get("sizes") or "")
                size = int(m.group(1)) if m else (180 if "apple" in rel else 0)
                if (a.get("sizes") or "").lower() == "any" or a["href"].split("?")[0].endswith(".svg"):
                    size = 1000
                self.icons.append((size, a["href"]))
            elif rel == "manifest":
                self.manifest = a["href"]
        elif tag == "meta" and (a.get("property") or "").lower() == "og:image:icon":
            self.icons.append((0, a.get("content")))


def candidates(home):
    base, _, html = get(home)
    p = Links()
    p.feed(html.decode("utf-8", "ignore"))
    out = [(s, urllib.parse.urljoin(base, h)) for s, h in p.icons]
    if p.manifest:
        try:
            murl = urllib.parse.urljoin(base, p.manifest)
            m = json.loads(get(murl)[2])
            for ic in m.get("icons", []):
                mm = re.search(r"(\d+)x", ic.get("sizes", ""))
                out.append((int(mm.group(1)) if mm else 0, urllib.parse.urljoin(murl, ic["src"])))
        except Exception:
            pass
    root = "{0.scheme}://{0.netloc}".format(urllib.parse.urlparse(base))
    out += [(1, root + "/apple-touch-icon.png"), (0, root + "/favicon.ico")]
    seen, res = set(), []
    for s, u in sorted(out, key=lambda x: -x[0]):
        if u not in seen:
            seen.add(u); res.append(u)
    return res


def to_png(data):
    im = Image.open(io.BytesIO(data))
    if getattr(im, "format", "") == "ICO":
        im.size = max(im.ico.sizes())
        im.load()
    im = im.convert("RGBA")
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    if max(im.size) < MIN:
        return None
    r = SIZE / max(im.size)
    im = im.resize((max(1, round(im.width * r)), max(1, round(im.height * r))), Image.LANCZOS)
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    canvas.paste(im, ((SIZE - im.width) // 2, (SIZE - im.height) // 2), im)
    buf = io.BytesIO()
    canvas.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def fetch(item):
    slug = item["slug"]
    pages = [item.get("homepage")]
    repo = (item.get("source") or {}).get("repo")
    if repo and "github.com" not in (item.get("homepage") or ""):
        pass
    for home in filter(None, pages):
        try:
            urls = candidates(home)
        except Exception:
            urls = []
            root = "{0.scheme}://{0.netloc}".format(urllib.parse.urlparse(home))
            urls = [root + "/apple-touch-icon.png", root + "/favicon.ico"]
        for u in urls:
            try:
                _, ctype, data = get(u)
            except Exception:
                continue
            if b"<svg" in data[:600] or "svg" in ctype:
                if b"<svg" in data[:2000]:
                    (OUT / f"{slug}.svg").write_bytes(data)
                    return slug, f"/static/icons/{slug}.svg", u
                continue
            try:
                png = to_png(data)
            except Exception:
                continue
            if png:
                (OUT / f"{slug}.png").write_bytes(png)
                return slug, f"/static/icons/{slug}.png", u
    return slug, None, None


def main():
    force = "--force" in sys.argv
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    OUT.mkdir(parents=True, exist_ok=True)
    cat = json.loads(CATALOG.read_text("utf-8"))
    todo = [i for i in cat if (not only or i["slug"] in only) and (force or not i.get("icon"))]
    with ThreadPoolExecutor(12) as ex:
        results = list(ex.map(fetch, todo))
    got = {s: p for s, p, _ in results if p}
    for s, p, u in results:
        print(("✔ " if p else "✘ ") + s + (f"  <- {u}" if u else ""))
    for i in cat:
        if i["slug"] in got:
            i["icon"] = got[i["slug"]]
    CATALOG.write_text(json.dumps(cat, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(f"抓到 {len(got)}/{len(todo)}")


if __name__ == "__main__":
    main()
