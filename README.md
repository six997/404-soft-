# 404软件库

轻量、可核验的静态软件下载目录：只链接官方发布文件，每个文件附 SHA-256；可选把开源软件镜像到网盘。

## 目录
- `data/catalog.json`   软件条目（手工维护：名称、分类、简介、功能、官方仓库、下载文件匹配规则、手工网盘链接 `manual_mirrors`）
- `data/releases.json`  版本数据（脚本自动生成，勿手改）
- `data/categories.json` 分类名称
- `data/ads.json`       广告位开关（`home-top` `feed` `sidebar` `detail-mid` `detail-bottom` `footer`）
- `scripts/sync.py`     同步官方版本 / 镜像到网盘
- `scripts/build.py`    生成静态站到 `dist/`
- `.github/workflows/deploy.yml` 每 6 小时自动同步并部署到 GitHub Pages

## 本地预览
```bash
python3 scripts/sync.py
python3 scripts/build.py
python3 -m http.server -d dist 8000   # 打开 http://localhost:8000/?ads=debug 查看广告占位
```

## 新增软件
在 `catalog.json` 加一条，`source.assets` 里每条 `match` 是匹配 GitHub Release 文件名的正则。提交后 Actions 自动拉版本并上线。

## 网盘镜像（可选）
1. 自建 OpenList，挂载 123云盘 / 夸克 等。
2. 仓库 Settings → Secrets：`OPENLIST_URL`、`OPENLIST_TOKEN`；Variables：`MIRROR_DRIVES`，例如 `123云盘=/123pan,夸克=/quark`。
3. 只有 `mirror_allowed: true` 的条目会被镜像，文件路径为 `/<挂载点>/soft/<slug>/<版本>/<文件名>`，保留最近 2 个版本。
4. 夸克等分享链接：对 `soft/<slug>` 文件夹分享一次，写进条目的 `manual_mirrors`，按下载项 label 对应：
   ```json
   "manual_mirrors": { "Windows x64 · 安装程序": [{ "name": "夸克", "url": "分享链接", "code": "提取码" }] }
   ```

## 广告
编辑 `data/ads.json`，支持三种：
```json
{ "home-top": { "type": "image", "img": "/assets/ad.webp", "href": "https://..." },
  "sidebar":  { "type": "adsense", "client": "ca-pub-XXXX", "slot": "123" },
  "feed":     { "type": "html", "html": "<a href='...'>文字广告</a>" } }
```

## 部署
- GitHub Pages：Settings → Pages → Source 选 GitHub Actions；Variables 设 `BASE_PATH=/404-soft-`、`SITE_URL=https://six997.github.io/404-soft-`。
- Cloudflare Pages（国内更快）：连接本仓库，构建命令 `python3 scripts/build.py`，输出目录 `dist`，`BASE_PATH` 留空。
