#!/usr/bin/env python3
"""同步官方版本信息到 data/releases.json，可选把安装包镜像到网盘。

默认模式（无需任何密钥）：
  source.type = github：读取 GitHub Releases；
  source.type = winget：读取微软 winget-pkgs 官方清单（安装包为厂商官方地址，SHA-256 来自清单）；
  source.type = official：只给官网入口，不同步版本。
  写入版本号、发布日期、更新日志、文件大小、SHA-256（上游 digest）。

镜像模式（设置了 OPENLIST_URL + OPENLIST_TOKEN 时自动开启）：
  新版本出现时下载文件 -> 校验 SHA-256 -> 通过 OpenList 上传到 DRIVES 里的每个挂载点
  -> 只保留最近 KEEP 个版本 -> 镜像直链写入 releases.json。

环境变量：
  GITHUB_TOKEN    可选，提高 API 限额（Actions 里自动提供）
  OPENLIST_URL    例：https://pan.example.com
  OPENLIST_TOKEN  OpenList 后台 -> 设置 -> 其他 -> 令牌
  MIRROR_DRIVES   例："123云盘=/123pan,夸克=/quark"
"""
import datetime
import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(ROOT, "data", "catalog.json")
RELEASES = os.path.join(ROOT, "data", "releases.json")
KEEP = 2

OL = (os.getenv("OPENLIST_URL") or "").rstrip("/")
OL_TOKEN = os.getenv("OPENLIST_TOKEN") or ""
DRIVES = dict(p.split("=", 1) for p in (os.getenv("MIRROR_DRIVES") or "").split(",") if "=" in p)
MIRROR = bool(OL and OL_TOKEN and DRIVES)


def http(url, method="GET", data=None, headers=None, timeout=60):
    h = {"User-Agent": "404-soft-sync"}
    if "api.github.com" in url and os.getenv("GITHUB_TOKEN"):
        h["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    return urllib.request.urlopen(req, timeout=timeout)


def gh_json(url):
    with http(url) as r:
        return json.load(r)


def ol_api(path, payload):
    body = json.dumps(payload).encode()
    with http(f"{OL}{path}", "POST", body, {"Authorization": OL_TOKEN, "Content-Type": "application/json"}) as r:
        return json.load(r)


def ol_upload(local, remote):
    with open(local, "rb") as f:
        data = f.read()
    with http(f"{OL}/api/fs/put", "PUT", data, {
        "Authorization": OL_TOKEN,
        "File-Path": urllib.parse.quote(remote),
        "Content-Type": "application/octet-stream",
        "Content-Length": str(len(data)),
    }, timeout=3600) as r:
        res = json.load(r)
    if res.get("code") != 200:
        raise RuntimeError(f"上传失败 {remote}: {res}")


def vkey(v):
    return [int(n) if n.isdigit() else 0 for n in re.split(r"[.\-]", v)]


def ol_prune(folder):
    res = ol_api("/api/fs/list", {"path": folder, "refresh": True})
    dirs = [x["name"] for x in ((res.get("data") or {}).get("content") or []) if x.get("is_dir")]
    old = sorted(dirs, key=vkey)[:-KEEP]
    if old:
        ol_api("/api/fs/remove", {"dir": folder, "names": old})


def download(url, dest):
    h = hashlib.sha256()
    with http(url, timeout=1800) as r, open(dest, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
            h.update(chunk)
    return h.hexdigest()


def mirror_file(item, ver, asset, upstream_sha):
    mirrors = []
    with tempfile.TemporaryDirectory() as tmp:
        local = os.path.join(tmp, asset["name"])
        digest = download(asset["browser_download_url"], local)
        if upstream_sha and digest != upstream_sha:
            raise RuntimeError(f"{asset['name']} 哈希与上游不符，放弃镜像")
        for name, mount in DRIVES.items():
            folder = f"{mount}/soft/{item['slug']}"
            path = f"{folder}/{ver}/{asset['name']}"
            ol_upload(local, path)
            ol_prune(folder)
            mirrors.append({"name": name, "url": f"{OL}/d{urllib.parse.quote(path)}", "ok": True})
    return mirrors


def vparts(v):
    return [int(x) if x.isdigit() else 0 for x in re.split(r"[.\-_]", v)]


def winget_release(pid):
    path = "/".join([pid[0].lower()] + pid.split("."))
    items = gh_json(f"https://api.github.com/repos/microsoft/winget-pkgs/contents/manifests/{path}")
    vers = [i["name"] for i in items if i["type"] == "dir" and re.match(r"^\d", i["name"])]
    ver = max(vers, key=vparts)
    base = f"https://raw.githubusercontent.com/microsoft/winget-pkgs/master/manifests/{path}/{ver}/{pid}"
    with http(f"{base}.installer.yaml") as r:
        y = r.read().decode("utf-8", "replace")
    installers = []
    for blk in re.split(r"\n-\s", y):
        u = re.search(r"InstallerUrl:\s*(\S+)", blk)
        h = re.search(r"InstallerSha256:\s*(\S+)", blk)
        a = re.search(r"Architecture:\s*(\S+)", blk)
        if u and h:
            installers.append({"url": u.group(1), "sha256": h.group(1).lower(), "arch": a.group(1) if a else ""})
    notes, released = "", ""
    try:
        with http(f"{base}.locale.zh-CN.yaml") as r:
            loc = r.read().decode("utf-8", "replace")
    except Exception:
        try:
            with http(f"{base}.locale.en-US.yaml") as r:
                loc = r.read().decode("utf-8", "replace")
        except Exception:
            loc = ""
    m = re.search(r"ReleaseNotes:\s*\|-?\n((?:\s{2,}.*\n?)+)", loc)
    if m:
        notes = "\n".join(l.strip() for l in m.group(1).splitlines())
    m = re.search(r"ReleaseDate:\s*(\S+)", y)
    if m:
        released = m.group(1)
    return ver, installers, notes, released, f"https://github.com/microsoft/winget-pkgs/tree/master/manifests/{path}/{ver}"


def file_name(u):
    p = urllib.parse.urlparse(u).path
    p = re.sub(r"/download$", "", p)
    return urllib.parse.unquote(p.rsplit("/", 1)[-1]) or u


def sync_winget(item, prev, src):
    ver, installers, notes, released, page = winget_release(src["id"])
    same = prev and prev.get("version") == ver
    want_mirror = MIRROR and item.get("mirror_allowed")
    if same and (not want_mirror or prev.get("mirrored")):
        return prev, False
    downloads = []
    for rule in src["assets"]:
        ins = next((i for i in installers
                    if (not rule.get("arch") or i["arch"] == rule["arch"]) and re.search(rule.get("url", "."), i["url"])), None)
        if not ins:
            continue
        name = file_name(ins["url"])
        asset = {"name": name, "browser_download_url": ins["url"]}
        mirrors = mirror_file(item, ver, asset, ins["sha256"]) if want_mirror else []
        downloads.append({
            "label": rule["label"], "platform": rule.get("platform", "Windows"), "portable": bool(rule.get("portable")),
            "file": name, "size": None, "sha256": ins["sha256"], "official": ins["url"], "mirrors": mirrors,
        })
    today = datetime.date.today().isoformat()
    if same and prev.get("released"):
        released = prev["released"]
    return {
        "version": ver, "released": released, "verified": today, "release_url": page,
        "changelog": notes[:6000], "downloads": downloads, "mirrored": bool(want_mirror), "source": "winget",
    }, not same


def sync_item(item, prev):
    src = item.get("source") or {}
    if src.get("type") == "winget":
        return sync_winget(item, prev, src)
    if src.get("type") != "github":
        return prev, False
    rel = gh_json(f"https://api.github.com/repos/{src['repo']}/releases/latest")
    ver = re.sub(r"^[^0-9]*", "", rel["tag_name"])
    same = prev and prev.get("version") == ver
    want_mirror = MIRROR and item.get("mirror_allowed")
    if same and (not want_mirror or prev.get("mirrored")):
        return prev, False

    downloads = []
    for rule in src["assets"]:
        asset = next((a for a in rel["assets"] if re.search(rule["match"], a["name"])), None)
        if not asset:
            continue
        sha = (asset.get("digest") or "").removeprefix("sha256:")
        mirrors = mirror_file(item, ver, asset, sha) if want_mirror else []
        downloads.append({
            "label": rule["label"], "platform": rule["platform"], "portable": bool(rule.get("portable")), "file": asset["name"],
            "size": asset["size"], "sha256": sha, "official": asset["browser_download_url"],
            "mirrors": mirrors,
        })

    today = datetime.date.today().isoformat()
    return {
        "version": ver,
        "released": rel["published_at"][:10],
        "verified": today,
        "release_url": rel["html_url"],
        "changelog": (rel.get("body") or "")[:6000],
        "downloads": downloads,
        "mirrored": bool(want_mirror),
    }, not same


def check_mirrors(releases):
    for r in releases.values():
        for d in r.get("downloads", []):
            for m in d.get("mirrors", []):
                try:
                    with http(m["url"], "HEAD", timeout=20) as resp:
                        m["ok"] = resp.status < 400
                except Exception:
                    m["ok"] = False


def main():
    catalog = json.load(open(CATALOG, encoding="utf-8"))
    releases = json.load(open(RELEASES, encoding="utf-8")) if os.path.exists(RELEASES) else {}
    today = datetime.date.today().isoformat()
    updated = []
    for item in catalog:
        prev = releases.get(item["slug"])
        try:
            new, changed = sync_item(item, prev)
            if new:
                new["verified"] = today
                releases[item["slug"]] = new
            if changed:
                updated.append(f"{item['name']} {new['version']}")
        except Exception as e:  # 单个失败不影响其他条目
            print(f"[跳过] {item['slug']}: {e}", file=sys.stderr)
    if MIRROR:
        check_mirrors(releases)
    with open(RELEASES, "w", encoding="utf-8") as f:
        json.dump(releases, f, ensure_ascii=False, indent=2)
    print("镜像模式:", "开" if MIRROR else "关")
    print("有更新:", ", ".join(updated) if updated else "无")


if __name__ == "__main__":
    main()
