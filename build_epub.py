#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_epub.py — 把 snowmoon-zh/ 中文镜像站打包成 EPUB 3。

用法：
    python3 build_epub.py [选项]              # 完整选项见 --help

    -o, --out PATH      输出 EPUB（默认 Snowmoon-雪月-中译本.epub）
    --build-dir PATH    中间产物目录（默认系统临时目录）
    --keep-build        保留中间产物，便于查看生成的 XHTML / CSS
    --light-device M    界面模拟块配色：table（默认）/ all / off
    -q, --quiet         不打印进度

输出：
    Snowmoon-雪月-中译本.epub

依赖：beautifulsoup4 / html5lib / Pillow；pandoc（仅用于把「术语表.md」转 HTML）。

输入只有 html/chapter-*.html、术语表.md 与 assets/；每次都整包重建、不依赖上次产物，
所以成品随时可删可重跑。
"""

import argparse
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
import zipfile

from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ---------------------------------------------------------------- 路径与常量

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_HTML = os.path.join(ROOT, "html")
# 中间产物放系统临时目录，不污染仓库
BUILD = os.path.join(tempfile.gettempdir(), "snowmoon_epub_build")
OUTPUT = os.path.join(ROOT, "Snowmoon-雪月-中译本.epub")
GLOSSARY_MD = os.path.join(ROOT, "术语表.md")

BOOK_TITLE = "Snowmoon（雪月）"
BOOK_AUTHOR = "Vitalik Buterin"
BOOK_TRANSLATOR = "Claude 辅助翻译"
BOOK_LANG = "zh-CN"
BOOK_RIGHTS = "GPL v3"
BOOK_DATE = "2026-09-29"
SOURCE_URL = "https://vitalik.eth.limo/snowmoon/"
LICENSE_URL = "https://www.gnu.org/licenses/gpl-3.0.html"
BOOK_ID = "urn:uuid:" + str(
    uuid.uuid5(uuid.NAMESPACE_URL, "https://vitalik.eth.limo/snowmoon/zh-epub")
)

CHAPTER_COUNT = 32
TEXT_DIR = "text"
HUE_SLOTS = 27  # 原作对话配色 = oklch(0.7 0.15 360k/27) 的 27 等分色轮

# 界面模拟块（device-view）的配色主题。
#   "table" = 只把「含表格」的模拟块改成浅色（用户 2026-09-29 指定：表格用浅色，不要深色）
#   "all"   = 含 SVG 图示的模拟块也一起改浅色
#             （注意：图示里的深色界面是 SVG 自己画死的 fill，改面板底色不会让图变亮）
#   "off"   = 与原作／原站一致，全部深色设备屏
LIGHT_DEVICE = "table"

NS = 'xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"'


# ---------------------------------------------------------------- 颜色：oklch → hex

def oklch_to_hex(L, C, H):
    """把 oklch(L C H) 转成 sRGB hex。EPUB 阅读器对 oklch 支持不一，故预转 hex。"""
    h = math.radians(H)
    a, b = C * math.cos(h), C * math.sin(h)
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    r = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    bl = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s

    def enc(c):
        c = min(1.0, max(0.0, c))
        return c * 12.92 if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055

    return "#%02x%02x%02x" % (round(enc(r) * 255), round(enc(g) * 255), round(enc(bl) * 255))


HUE_HEX = [oklch_to_hex(0.7, 0.15, 360 * k / HUE_SLOTS) for k in range(HUE_SLOTS)]
OKLCH_RE = re.compile(r"oklch\(\s*([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s*\)")


# ---------------------------------------------------------------- 单章清洗

def clean_chapter(n):
    """读 html/chapter-n.html，返回 (body_inner_xhtml, subtitle)。"""
    path = os.path.join(SRC_HTML, "chapter-%d.html" % n)
    soup = BeautifulSoup(open(path, encoding="utf-8").read(), "html5lib")
    dp = soup.find("div", class_="document-page")
    if dp is None:
        raise SystemExit("找不到 chapter-%d 的 document-page" % n)

    # 1) 去掉顶部/底部原有导航（改为 EPUB 自己的页脚导航）
    for nav in dp.find_all("nav", class_="chapter-nav"):
        nav.decompose()

    # 2) 抓副标题：取首条 chapter-open 的「地点 · 日期」
    subtitle = ""
    dl = dp.find("div", class_="chapter-open")
    if dl is not None:
        place = dl.find("span", class_="place")
        date = dl.find("span", class_="date")
        bits = [x.get_text(strip=True) for x in (place, date) if x]
        subtitle = " · ".join(bits)

    # 3) h1 加标记类，替掉阅读器普遍不支持的 CSS :has()
    h1 = dp.find("h1")
    if h1 is not None:
        h1["class"] = (h1.get("class") or []) + ["chapter-title"]

    # 4) 对话配色：<span style="color:oklch(...)"> → <span class="hueK">
    for sp in dp.find_all("span", style=True):
        style = sp["style"]
        m = OKLCH_RE.search(style)
        if not m:
            continue
        k = round(float(m.group(3)) * HUE_SLOTS / 360) % HUE_SLOTS
        # 逐条解析声明，丢掉含 oklch 的那条；只写 color:oklch(…) 时不留 style="color:"
        rest = [
            d.strip() for d in style.split(";")
            if d.strip() and "oklch" not in d
        ]
        if rest:
            sp["style"] = "; ".join(rest)
        else:
            del sp["style"]
        sp["class"] = (sp.get("class") or []) + ["hue%d" % k]

    # 5) 模拟界面里的 <button> / <input>：非交互，转成语义中性的 span
    for b in dp.find_all("button"):
        b.name = "span"
        b["class"] = (b.get("class") or []) + ["dv-btn"]
    for i in dp.find_all("input"):
        i.name = "span"
        i["class"] = (i.get("class") or []) + ["dv-range"]
        for a in ("type", "style", "value"):
            if a in i.attrs:
                del i[a]

    # 5b) 体型小的界面模拟块打上 dv-keep，让其整块留在同一页（深色面板被劈开最难看）。
    #     含大幅 SVG 地图的块刻意不加：那种块本来就比一屏高，强行留页只会溢出。
    for dv in dp.find_all("div", class_="device-view"):
        heights = [int(s["height"]) for s in dv.find_all("svg")
                   if str(s.get("height") or "").isdigit()]
        tallest = max(heights) if heights else 0
        if (tallest < 150
                and len(dv.find_all("tr")) <= 9
                and len(dv.get_text(strip=True)) <= 900):
            dv["class"] = (dv.get("class") or []) + ["dv-keep"]

    # 5c) 含表格的模拟块改走浅色主题（规则见 CSS 里的 .device-view.dv-light）。
    #     只挑「有 table」的块：含 SVG 的块不能改——图里的深色界面是 SVG 自己画死的
    #     fill（如 <rect width=400 height=214 fill="#348">），改面板底色不会让图变亮，
    #     只会变成浅色卡片里嵌一块深色图。
    if LIGHT_DEVICE != "off":
        for dv in dp.find_all("div", class_="device-view"):
            if LIGHT_DEVICE == "all" or dv.find("table"):
                dv["class"] = (dv.get("class") or []) + ["dv-light"]

    # 6) 清掉所有内联事件处理器（EPUB 不执行脚本，留着只是噪声）
    for el in dp.find_all(True):
        for a in list(el.attrs):
            if a.lower().startswith("on"):
                del el[a]

    return dp.decode_contents().strip(), subtitle


def chapter_page(n, body, subtitle):
    prev_link = (
        '<a class="prev" rel="prev" href="chapter-%d.xhtml">← 第 %d 章</a>' % (n - 1, n - 1)
        if n > 1
        else '<span class="prev"></span>'
    )
    next_link = (
        '<a class="next" rel="next" href="chapter-%d.xhtml">第 %d 章 →</a>' % (n + 1, n + 1)
        if n < CHAPTER_COUNT
        else '<span class="next"></span>'
    )
    title = "第 %d 章" % n
    if subtitle:
        title += " · " + subtitle
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<!DOCTYPE html>\n"
        '<html %s lang="%s" xml:lang="%s">\n'
        "<head>\n"
        '  <meta charset="utf-8"/>\n'
        "  <title>%s</title>\n"
        '  <link rel="stylesheet" type="text/css" href="../styles/zh.css"/>\n'
        "</head>\n"
        '<body class="chapter">\n'
        '<section class="document-page" epub:type="chapter">\n'
        "%s\n"
        "</section>\n"
        '<nav class="chapnav">\n'
        "  %s%s%s\n"
        "</nav>\n"
        "</body>\n"
        "</html>\n"
    ) % (
        NS, BOOK_LANG, BOOK_LANG, esc(title), body, prev_link,
        '<a class="toc" href="nav.xhtml">目录</a>', next_link,
    )


def esc(t):
    return (
        t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ---------------------------------------------------------------- 样式表

CSS = """
/* 《Snowmoon（雪月）》中文版 EPUB 样式
   只用 hex 颜色、不用 :has()/CSS 变量/flex 关键布局，尽量兼容各家阅读器。 */

@charset "utf-8";

body {
  font-family: "Noto Serif CJK SC", "Source Han Serif SC", "Songti SC",
               "SimSun", Georgia, serif;
  line-height: 1.8;
  margin: 0 5%;
  padding: 0;
  color: #222;
  background: #ffffff;
  font-size: 1em;
  word-break: normal;
  overflow-wrap: break-word;
}

/* ---- 章节标题与 dateline ---- */

h1.chapter-title {
  font-size: 1.6em;
  font-weight: 600;
  color: #333;
  letter-spacing: 0.08em;
  margin: 0.6em 0 0.2em;
  padding: 0;
  border: 0;
}

p { margin: 0 0 0.75em; text-indent: 0; }
li, blockquote { line-height: 1.75; }

/* 用 border-top 而非 background 画线：个别阅读器不给 hr 上背景色 */
hr { border: 0; border-top: 1px solid #d8d4e8; height: 0; margin: 1.6em 0; }

/* dateline：开场/场景切换的小字行 */
.dateline { margin: 1.5em 0; }
.dateline .rule { margin: 0 0 0.6em; }
.dateline.chapter-open { margin: 0.1em 0 1.8em; }
.dateline.chapter-open .txt {
  font-size: 0.82em; letter-spacing: 0.04em; color: #5a5480;
  text-transform: none;
}
.dateline.chapter-open .date {
  letter-spacing: 0.14em; text-transform: uppercase;
  font-size: 0.9em; color: #8a83a8;
}
.dateline.scene-break { margin: 1.8em 0; text-align: center; }
.dateline.scene-break .rule {
  border-top-color: #c3bed6; width: 34%; margin: 0 auto 0.5em;
}
.dateline.scene-break .txt {
  font-size: 0.72em; letter-spacing: 0.16em; text-transform: uppercase;
  color: #a49dc4;
}
.dateline .place { font-weight: 600; }
.dateline .sep { margin: 0 0.5em; color: #c3bed6; }

/* ---- 对话配色（原作 27 等分色轮，已转 hex） ---- */
/*__HUE_BLOCK__*/

/* ---- 设备界面模拟块 ---- */
.device-view {
  background-color: #0a0e27;
  color: #7fbcff;
  font-family: "Courier New", Menlo, Consolas, monospace;
  padding: 1em 1.1em;
  margin: 1.4em 0;
  border-radius: 10px;
  font-size: 0.8em;
  line-height: 1.5;
  overflow-wrap: anywhere;
}
.device-view.device-view-left { text-align: left; }
.device-view h3 {
  color: #7fbcff; border-bottom: 1px solid #3d70c3;
  padding-bottom: 0.4em; margin: 0.2em 0 1em; font-size: 1em;
}
.device-view table {
  width: 100%; border-collapse: collapse; margin: 0 0 1em;
  font-size: 1em;
  /* 正文里的界面模拟表都很小，整张留在同一页 */
  break-inside: avoid; page-break-inside: avoid;
}
/* 体型不大的模拟块也整块保留：深色圆角面板被劈成两半最难看。
   判定在生成阶段做（见 build_epub.py 的 dv-keep），只有确实矮的块才加这个类；
   含大幅 SVG 地图的块不加，免得强行留页反而溢出。 */
.device-view.dv-keep { break-inside: avoid; page-break-inside: avoid; }
.device-view th, .device-view td {
  border: 1px solid #2a4a7a; padding: 0.4em 0.5em;
  color: #b8d8ff; text-align: left; overflow-wrap: anywhere;
}
.device-view thead tr { background-color: #1a2a4a; }
/* 这里必须显式再写一次 background：下面通用的 `th { background: #eceaf6 }` 会盖到
   模拟块里来，把表头变成浅底浅字（#cef 压 #eceaf6，对比度只有 1.1:1，几乎看不见）。 */
.device-view th { color: #cef; background-color: #1a2a4a; font-weight: bold; }
.device-view p, .device-view li, .device-view ul, .device-view ol {
  color: #9cc2ff; font-size: 1em; line-height: inherit;
  font-family: inherit; margin-bottom: 0.4em;
}
.device-view svg, .device-view img {
  display: block; margin: 0.6em auto; max-width: 100%; height: auto;
}
.device-view.device-view-left svg, .device-view.device-view-left img {
  margin-left: 0; margin-right: auto;
}
.dv-btn {
  display: inline-block;
  background-color: #1a3a6a; border: 1px solid #3d70c3;
  padding: 0.4em 1.2em; border-radius: 3px; color: #cef;
  font-family: inherit; font-size: 1em;
}
.dv-range {
  display: block; height: 5px; margin: 0.7em 0;
  background: #3d70c3; border-radius: 3px;
}

/* ---- 表格面板的浅色主题 ----
   原作与原站在明、暗两种模式下，模拟块都是深蓝设备屏（.device-view #0a0e27）。本译本
   把**含表格**的块改走浅色：正文里读表不再是一整片深蓝，其余留给 SVG 图示块保持深色。
   只保留等宽字体这一点「设备感」，配色换成浅底深字。
   选择器一律比上面的深色规则多一个 .dv-light，特异性更高，因此不需要 !important。 */
.device-view.dv-light {
  background-color: #f5f8fc;
  color: #1f2b3d;
  border: 1px solid #cbd8ea;
}
.device-view.dv-light h3 { color: #2e5f9e; border-bottom-color: #cbd8ea; }
.device-view.dv-light p, .device-view.dv-light li,
.device-view.dv-light ul, .device-view.dv-light ol { color: #1f2b3d; }
.device-view.dv-light th, .device-view.dv-light td {
  border: 1px solid #c8d6e8; color: #1f2b3d;
}
.device-view.dv-light thead tr { background-color: #e2ebf8; }
.device-view.dv-light th { color: #14304d; background-color: #e2ebf8; font-weight: bold; }
.device-view.dv-light tbody tr:nth-child(odd) { background-color: #ffffff; }
.device-view.dv-light tbody tr:nth-child(even) { background-color: #eef4fc; }
.device-view.dv-light .dv-btn {
  background-color: #e2ebf8; border-color: #9fbcdd; color: #14304d;
}
.device-view.dv-light .dv-range { background: #9fbcdd; }

/* ---- Dzegoban 卡片 ---- */
.dz-card {
  background: #1b2b36; color: #e6f4ff;
  border-radius: 8px; padding: 1em 1.2em; margin: 1em 0;
}
.dz-card .dz-title { font-weight: bold; margin-bottom: 0.6em; }
.dz-card.dz-mono { font-family: "Courier New", Menlo, monospace; }

/* ---- 通用元素 ---- */
blockquote {
  border-left: 3px solid #b7b0d4; padding: 0.1em 0 0.1em 1em;
  margin: 1.1em 0; color: #444; font-style: normal;
}
code {
  font-family: "Courier New", Menlo, Consolas, monospace;
  background: #f2f1f7; padding: 0.05em 0.3em; border-radius: 3px;
  font-size: 0.9em; color: #7a3d8f;
}
pre {
  background: #282c34; color: #abb2bf; padding: 1em;
  border-radius: 6px; overflow-wrap: anywhere; white-space: pre-wrap;
  font-size: 0.8em; line-height: 1.45;
}
pre code { background: none; color: inherit; padding: 0; }
table { width: 100%; border-collapse: collapse; margin: 1.2em 0; font-size: 0.86em; }
th, td { border: 1px solid #ddd; padding: 0.45em 0.6em; text-align: left; vertical-align: top; }
th { background: #eceaf6; color: #333; }

/* ---- 表格分页 ----
   可重排 EPUB 里，比屏幕高的表必然要断开，这是格式本身的性质，不是排版错误。
   能控制的是「断得是否体面」：
     1. 单元格与整行绝不拦腰截断（避免半行悬在下页顶部）；
     2. 长表真的断页时，表头在新页自动重复，读者不会失去列名；
     3. 明显放得下的表，整张保留在同一页。
   page-break-* 是给老引擎的，break-* 是新标准，两个都写。 */
thead { display: table-header-group; }
tfoot { display: table-footer-group; }
tr, th, td { break-inside: avoid; page-break-inside: avoid; }
table.keep { break-inside: avoid; page-break-inside: avoid; }
a { color: #4a5fd0; text-decoration: none; }
img { max-width: 100%; height: auto; }
svg { max-width: 100%; height: auto; }

/* ---- 章末导航 ---- */
.chapnav {
  margin: 3em 0 1em; padding-top: 1em;
  border-top: 1px solid #e3def0;
  font-size: 0.78em; letter-spacing: 0.1em;
}
.chapnav a { color: #6b64a0; }
/* 三段等分宽度之和须 <100%，否则会折行 */
.chapnav .prev { display: inline-block; width: 30%; text-align: left; }
.chapnav .toc { display: inline-block; width: 30%; text-align: center; }
.chapnav .next { display: inline-block; width: 30%; text-align: right; }

/* ---- 封面 / 书名页 / 术语表 ---- */
body.cover { margin: 0; padding: 0; text-align: center; }
body.cover img { max-width: 100%; max-height: 100%; }
body.titlepage { margin: 8% 8%; text-align: center; }
body.titlepage h1 {
  font-size: 2.2em; letter-spacing: 0.1em; margin: 1.6em 0 0.3em;
  color: #2a2450; border: 0;
}
body.titlepage .latin {
  font-size: 1em; letter-spacing: 0.4em; color: #6b64a0;
  text-transform: uppercase; margin-bottom: 2.4em;
}
body.titlepage .rule {
  border: 0; border-top: 1px solid #cfc9e6; height: 0;
  width: 40%; margin: 2em auto;
}
body.titlepage .byline { font-size: 1.05em; color: #333; margin: 0.4em 0; }
body.titlepage .meta { font-size: 0.82em; color: #6a6580; margin-top: 3em; line-height: 1.9; }
body.titlepage .meta a { color: #4a5fd0; word-break: break-all; }

body.frontmatter { margin: 6% 7%; }
body.frontmatter h1 { font-size: 1.5em; color: #2a2450; margin-bottom: 1.2em; }
body.frontmatter h2 { font-size: 1.15em; color: #3a3460; margin: 1.6em 0 0.6em; }
body.frontmatter p, body.frontmatter li { font-size: 0.95em; }
body.frontmatter a { word-break: break-all; }

body.glossary h1 { font-size: 1.5em; color: #2a2450; }
body.glossary h2 { font-size: 1.15em; color: #3a3460; margin-top: 1.8em; }
body.glossary h3 { font-size: 1em; color: #4a4470; margin-top: 1.4em; }
body.glossary table { font-size: 0.78em; }
body.glossary blockquote { font-size: 0.9em; }
""".replace(
    "/*__HUE_BLOCK__*/",
    "\n".join(".hue%d { color: %s; }" % (k, v) for k, v in enumerate(HUE_HEX)),
)


# ---------------------------------------------------------------- 封面

SERIF_BOLD = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"
SERIF_REG = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"
SANS_REG = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"


def load_font(candidates, size):
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    raise SystemExit("没有可用的中文字体，无法生成封面")


def tracked(draw, xy, text, font, fill, tracking=0.0, anchor="mm"):
    """按字距逐字绘制（PIL 无 letter-spacing）。"""
    widths = [draw.textlength(ch, font=font) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x, y = xy
    if anchor[0] == "m":
        x -= total / 2
    for ch, w in zip(text, widths):
        draw.text((x, y), ch, font=font, fill=fill, anchor="l" + anchor[1])
        x += w + tracking


def build_cover(path):
    W, H = 1600, 2400
    img = Image.new("RGB", (W, H), (15, 12, 41))

    # 竖向渐变：呼应镜像站的暗色主题 #0f0c29 → #302b63 → #24243e
    stops = [(0.0, (15, 12, 41)), (0.5, (48, 43, 99)), (1.0, (36, 36, 62))]
    px = img.load()
    for y in range(H):
        t = y / (H - 1)
        for i in range(len(stops) - 1):
            (t0, c0), (t1, c1) = stops[i], stops[i + 1]
            if t0 <= t <= t1:
                f = (t - t0) / (t1 - t0)
                col = tuple(round(c0[j] + (c1[j] - c0[j]) * f) for j in range(3))
                break
        for x in range(W):
            px[x, y] = col

    # 月晕 + 月亮
    cx, cy, r = int(W * 0.72), int(H * 0.215), 165
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for rad in range(r + 430, r, -3):
        a = int(46 * (1 - (rad - r) / 430.0) ** 1.9) + 1
        gd.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=(232, 226, 255, a))
    glow = glow.filter(ImageFilter.GaussianBlur(26))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")

    moon = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(moon).ellipse(
        [cx - r, cy - r, cx + r, cy + r], fill=(238, 233, 214, 255)
    )
    moon = moon.filter(ImageFilter.GaussianBlur(1.6))
    img = Image.alpha_composite(img.convert("RGBA"), moon).convert("RGB")

    # 雪点
    snow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(snow)
    rnd = random.Random(7)
    for _ in range(520):
        x = rnd.randint(0, W)
        y = rnd.randint(0, H)
        rad = rnd.choice([1, 1, 1, 2, 2, 3, 4])
        a = rnd.randint(28, 165)
        sd.ellipse([x - rad, y - rad, x + rad, y + rad], fill=(255, 255, 255, a))
    snow = snow.filter(ImageFilter.GaussianBlur(0.7))
    img = Image.alpha_composite(img.convert("RGBA"), snow).convert("RGB")

    d = ImageDraw.Draw(img)
    INK = (244, 241, 255)
    DIM = (186, 180, 220)
    RULE = (108, 100, 160)

    # 书名「雪月」
    f_title = load_font([SERIF_BOLD, SERIF_REG, SANS_REG], 300)
    tracked(d, (W / 2, H * 0.545), "雪月", f_title, INK, tracking=46)

    # 分隔线
    d.line([W * 0.5 - 150, H * 0.635, W * 0.5 + 150, H * 0.635], fill=RULE, width=3)

    # 拉丁书名
    f_latin = load_font([SERIF_REG, SANS_REG], 62)
    tracked(d, (W / 2, H * 0.682), "SNOWMOON", f_latin, DIM, tracking=24)

    # 作者与译者
    f_author = load_font([SERIF_REG, SANS_REG], 60)
    d.text((W / 2, H * 0.795), BOOK_AUTHOR, font=f_author, fill=INK, anchor="mm")
    f_sub = load_font([SANS_REG, SERIF_REG], 44)
    d.text((W / 2, H * 0.848), "简体中文全译", font=f_sub, fill=DIM, anchor="mm")

    d.line([W * 0.5 - 90, H * 0.895, W * 0.5 + 90, H * 0.895], fill=RULE, width=2)
    f_small = load_font([SANS_REG, SERIF_REG], 30)
    d.text(
        (W / 2, H * 0.932), "vitalik.eth.limo/snowmoon", font=f_small,
        fill=(150, 144, 190), anchor="mm",
    )

    img.save(path, "JPEG", quality=92, optimize=True)


# ---------------------------------------------------------------- 前置页

def cover_page():
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
        '<html %s lang="%s" xml:lang="%s">\n<head>\n  <meta charset="utf-8"/>\n'
        "  <title>封面</title>\n"
        '  <link rel="stylesheet" type="text/css" href="../styles/zh.css"/>\n'
        '</head>\n<body class="cover" epub:type="cover">\n'
        '  <img src="../images/cover.jpg" alt="《Snowmoon（雪月）》封面"/>\n'
        "</body>\n</html>\n" % (NS, BOOK_LANG, BOOK_LANG)
    )


def title_page():
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
        '<html %s lang="%s" xml:lang="%s">\n<head>\n  <meta charset="utf-8"/>\n'
        "  <title>书名页</title>\n"
        '  <link rel="stylesheet" type="text/css" href="../styles/zh.css"/>\n'
        '</head>\n<body class="titlepage" epub:type="titlepage">\n'
        "  <h1>雪月</h1>\n"
        '  <p class="latin">Snowmoon</p>\n'
        '  <hr class="rule"/>\n'
        '  <p class="byline">%s 著</p>\n'
        '  <p class="byline">%s</p>\n'
        '  <hr class="rule"/>\n'
        '  <p class="meta">\n'
        "    原著：Vitalik Buterin, <i>Snowmoon</i>（32 章）<br/>\n"
        '    原文：<a href="%s">%s</a><br/>\n'
        '    授权：%s — <a href="%s">GNU GPL v3</a><br/>\n'
        "    本译本沿用原作授权，可自由复制、改编与再发布。<br/>\n"
        "    正文全部译自原作英文原文，译文体例见「译者说明」。\n"
        "  </p>\n"
        "</body>\n</html>\n"
        % (NS, BOOK_LANG, BOOK_LANG, esc(BOOK_AUTHOR), esc(BOOK_TRANSLATOR),
           SOURCE_URL, SOURCE_URL, BOOK_RIGHTS, LICENSE_URL)
    )


def translator_note():
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
        '<html %s lang="%s" xml:lang="%s">\n<head>\n  <meta charset="utf-8"/>\n'
        "  <title>译者说明</title>\n"
        '  <link rel="stylesheet" type="text/css" href="../styles/zh.css"/>\n'
        "</head>\n"
        '<body class="frontmatter" epub:type="preface">\n'
        "  <h1>译者说明</h1>\n"
        "  <p>这是 Vitalik Buterin 的科幻小说《Snowmoon》（中文可作「雪月」，"
        "全书 32 章）的简体中文全译。翻译遵循一套统一体例，读懂下面几条即可顺畅阅读。</p>\n"
        "  <h2>一、专名一律随原文走</h2>\n"
        "  <p><strong>甲类 · 专名</strong>（人名、地名、国名、政体、民族、语言、机构、"
        "品牌、棋戏、单位货币）在正文里<strong>保留英文原词</strong>，每章首次出现时补一次中文括注，"
        "例如 <code>Veridia（维瑞迪亚）</code>、<code>Zei（泽伊）</code>、"
        "<code>tick（滴答）</code>。这样做的代价是行文里会夹带英文，好处是全书专名不会因"
        "多人分段翻译而走样。</p>\n"
        "  <p><strong>乙类 · 角色／机制／技术／装置／观念词</strong>则反过来：正文写"
        "<strong>中文</strong>，首次出现时补一次英文括注，例如 "
        "<code>引导会（Order of Steering）</code>、<code>匿名长袍（privacy robe）</code>。</p>\n"
        "  <h2>二、Dzegoban 造语逐字保留</h2>\n"
        "  <p>书中 Dzegoban 语（泽戈语）的词句一律照抄罗马化原文，绝不改写或意译；"
        "含义只放在紧随其后的中文括注里。所以正文中出现 <code>Dze go ba fau gie</code> "
        "这样的串并非排版错误，而是刻意保留。</p>\n"
        "  <h2>三、日期与 dateline 原样保留</h2>\n"
        "  <p>每章开头与场景切换处的「地点 · 日期」行（如 <code>3725 Snowmoon 29</code>）"
        "逐字保留。月份名 Snowmoon、Rainmoon、Firemoon 等也保留英文，"
        "对应的中文义项见书末「术语表」。</p>\n"
        "  <h2>四、对话颜色</h2>\n"
        "  <p>原作以颜色区分说话人，每个角色有固定的一个色相。本译本完整保留了这套配色，"
        "颜色值由原作 <code>oklch()</code> 换算为等效的十六进制色，肉眼所见与原站一致。</p>\n"
        "  <h2>五、关于版本</h2>\n"
        "  <p>本译本与原作分章一一对应，结构与元素层级做过逐章比对。原文出处："
        '<a href="%s">%s</a>。</p>\n'
        "</body>\n</html>\n" % (NS, BOOK_LANG, BOOK_LANG, SOURCE_URL, SOURCE_URL)
    )


# ---------------------------------------------------------------- 术语表

def glossary_page():
    try:
        html = subprocess.run(
            ["pandoc", GLOSSARY_MD, "-f", "gfm", "-t", "html", "--no-highlight"],
            check=True, capture_output=True, text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as e:
        raise SystemExit("pandoc 转换术语表失败：%s" % e)

    # pandoc 产物过一遍 bs4，保证是良构 XHTML 片段
    soup = BeautifulSoup(html, "html5lib")

    # 估一下渲染行数：每行按最长的单元格折行（中文按 28 字一折，偏保守）。
    # 估算够短的整张保留；长表（如 41 行的三方表）放弃留页，交给表头重复。
    for t in soup.find_all("table"):
        est = 0
        for r in t.find_all("tr"):
            longest = max(
                (len(c.get_text(strip=True)) for c in r.find_all(["td", "th"])),
                default=0,
            )
            est += max(1, -(-longest // 28))
        if est <= 16:
            t["class"] = (t.get("class") or []) + ["keep"]

    body = soup.body.decode_contents().strip() if soup.body else html

    # 术语表原稿会指向仓库里的 _spec/SPEC.md §2；书内没有该文件，
    # 连同章节号一起换成指向「译者说明」的链接
    body = re.sub(
        r"<code>_spec/SPEC\.md</code>\s*§\s*\d+",
        '<a href="translator-note.xhtml">译者说明</a>',
        body,
    )

    return (
        '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
        '<html %s lang="%s" xml:lang="%s">\n<head>\n  <meta charset="utf-8"/>\n'
        "  <title>术语表</title>\n"
        '  <link rel="stylesheet" type="text/css" href="../styles/zh.css"/>\n'
        "</head>\n"
        '<body class="glossary" epub:type="backmatter">\n'
        '%s\n'
        "</body>\n</html>\n" % (NS, BOOK_LANG, BOOK_LANG, body)
    )


# ---------------------------------------------------------------- 导航

def nav_xhtml(chapters):
    items = "\n".join(
        '      <li><a href="chapter-%d.xhtml">第 %d 章%s</a></li>'
        % (n, n, ("　·　" + sub) if sub else "")
        for n, sub in chapters
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
        '<html %s lang="%s" xml:lang="%s">\n<head>\n  <meta charset="utf-8"/>\n'
        "  <title>目录</title>\n"
        '  <link rel="stylesheet" type="text/css" href="../styles/zh.css"/>\n'
        "</head>\n"
        '<body class="frontmatter" epub:type="frontmatter">\n'
        '  <nav epub:type="toc" id="toc">\n'
        "    <h1>目录</h1>\n"
        "    <ol>\n"
        '      <li><a href="titlepage.xhtml">书名页</a></li>\n'
        '      <li><a href="translator-note.xhtml">译者说明</a></li>\n'
        "%s\n"
        '      <li><a href="glossary.xhtml">术语表（译名总表）</a></li>\n'
        "    </ol>\n"
        "  </nav>\n"
        '  <nav epub:type="landmarks" hidden="hidden">\n'
        "    <ol>\n"
        '      <li><a epub:type="cover" href="cover.xhtml">封面</a></li>\n'
        '      <li><a epub:type="toc" href="nav.xhtml">目录</a></li>\n'
        '      <li><a epub:type="bodymatter" href="chapter-1.xhtml">正文</a></li>\n'
        "    </ol>\n"
        "  </nav>\n"
        "</body>\n</html>\n"
    ) % (NS, BOOK_LANG, BOOK_LANG, items)


def toc_ncx(chapters):
    points = []
    order = 1

    def point(pid, label, src, play=None):
        nonlocal order
        points.append(
            '    <navPoint id="%s" playOrder="%d">\n'
            "      <navLabel><text>%s</text></navLabel>\n"
            '      <content src="%s"/>\n'
            "    </navPoint>" % (pid, order, esc(label), src)
        )
        order += 1

    point("titlepage", "书名页", "text/titlepage.xhtml")
    point("note", "译者说明", "text/translator-note.xhtml")
    for n, sub in chapters:
        point("ch%d" % n, "第 %d 章" % n, "text/chapter-%d.xhtml" % n)
    point("glossary", "术语表", "text/glossary.xhtml")

    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1" '
        'xml:lang="%s">\n'
        "  <head>\n"
        '    <meta name="dtb:uid" content="%s"/>\n'
        '    <meta name="dtb:depth" content="1"/>\n'
        '    <meta name="dtb:totalPageCount" content="0"/>\n'
        '    <meta name="dtb:maxPageNumber" content="0"/>\n'
        "  </head>\n"
        "  <docTitle><text>%s</text></docTitle>\n"
        "  <docAuthor><text>%s</text></docAuthor>\n"
        "  <navMap>\n%s\n  </navMap>\n"
        "</ncx>\n"
        % (BOOK_LANG, BOOK_ID, esc(BOOK_TITLE), esc(BOOK_AUTHOR), "\n".join(points))
    )


# ---------------------------------------------------------------- OPF

def content_opf(chapters):
    man = [
        ('nav', 'text/nav.xhtml', 'application/xhtml+xml', 'properties="nav"'),
        ('ncx', 'toc.ncx', 'application/x-dtbncx+xml', None),
        ('css', 'styles/zh.css', 'text/css', None),
        ('cover-image', 'images/cover.jpg', 'image/jpeg', 'properties="cover-image"'),
        ('cover', 'text/cover.xhtml', 'application/xhtml+xml', None),
        ('titlepage', 'text/titlepage.xhtml', 'application/xhtml+xml', None),
        ('note', 'text/translator-note.xhtml', 'application/xhtml+xml', None),
        ('glossary', 'text/glossary.xhtml', 'application/xhtml+xml', None),
    ]
    for n in range(1, CHAPTER_COUNT + 1):
        man.append(('ch%d' % n, 'text/chapter-%d.xhtml' % n,
                    'application/xhtml+xml', None))

    manifest = "\n".join(
        '    <item id="%s" href="%s" media-type="%s"%s/>'
        % (i, h, m, (" " + p) if p else "")
        for i, h, m, p in man
    )

    spine = "\n".join(
        ['    <itemref idref="%s"/>' % i for i in
         ['cover', 'titlepage', 'note', 'nav']]
        + ['    <itemref idref="ch%d"/>' % n for n in range(1, CHAPTER_COUNT + 1)]
        + ['    <itemref idref="glossary"/>']
    )

    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
        'unique-identifier="bookid" xml:lang="%s">\n'
        '  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:opf="http://www.idpf.org/2007/opf">\n'
        '    <dc:identifier id="bookid">%s</dc:identifier>\n'
        '    <dc:title id="title">《%s》中文版</dc:title>\n'
        '    <meta refines="#title" property="file-as">Snowmoon</meta>\n'
        '    <dc:creator id="creator">%s</dc:creator>\n'
        '    <meta refines="#creator" property="role" scheme="marc:relators">aut</meta>\n'
        '    <dc:contributor id="tr">%s</dc:contributor>\n'
        '    <meta refines="#tr" property="role" scheme="marc:relators">trl</meta>\n'
        '    <dc:language>%s</dc:language>\n'
        '    <dc:date>%s</dc:date>\n'
        '    <dc:rights>%s</dc:rights>\n'
        '    <dc:source>%s</dc:source>\n'
        '    <dc:description>Vitalik Buterin 科幻小说《Snowmoon》'
        '（32 章）的简体中文全译，专名与 Dzegoban 造语按统一体例处理。</dc:description>\n'
        '    <meta name="cover" content="cover-image"/>\n'
        '    <meta property="dcterms:modified">%sT00:00:00Z</meta>\n'
        "  </metadata>\n"
        "  <manifest>\n%s\n  </manifest>\n"
        '  <spine toc="ncx">\n%s\n  </spine>\n'
        "</package>\n"
        % (BOOK_LANG, BOOK_ID, BOOK_TITLE, esc(BOOK_AUTHOR), esc(BOOK_TRANSLATOR),
           BOOK_LANG, BOOK_DATE, BOOK_RIGHTS, SOURCE_URL, BOOK_DATE,
           manifest, spine)
    )


CONTAINER = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<container version="1.0" '
    'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
    "  <rootfiles>\n"
    '    <rootfile full-path="OEBPS/content.opf" '
    'media-type="application/oebps-package+xml"/>\n'
    "  </rootfiles>\n"
    "</container>\n"
)


# ---------------------------------------------------------------- 主流程

def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        prog="build_epub.py",
        description="把 snowmoon-zh/ 的中文译文打包成 EPUB 3。"
                    "输入只有 html/chapter-*.html、术语表.md 与 assets/，"
                    "每次都整包重建，可重复运行。",
        epilog="依赖：beautifulsoup4 / html5lib / Pillow；pandoc（仅术语表需要）。")
    ap.add_argument("-o", "--out", default=OUTPUT,
                    help="输出 EPUB 路径（默认 %(default)s）")
    ap.add_argument("--build-dir", default=BUILD,
                    help="中间产物目录（默认系统临时目录）")
    ap.add_argument("--keep-build", action="store_true",
                    help="保留中间产物目录，便于查看生成的 XHTML / CSS")
    ap.add_argument("--light-device", choices=("table", "all", "off"),
                    default=LIGHT_DEVICE,
                    help="界面模拟块配色：table=只把含表格的块改浅色（默认）；"
                         "all=连 SVG 图示块也改；off=全部深色，照原作")
    ap.add_argument("-q", "--quiet", action="store_true", help="不打印进度")
    return ap.parse_args(argv)


def main(argv=None):
    """命令行入口；参数见 python3 build_epub.py --help。"""
    global BUILD, LIGHT_DEVICE
    args = parse_args(argv)
    BUILD = args.build_dir
    LIGHT_DEVICE = args.light_device
    out = args.out

    if os.path.isdir(BUILD):
        shutil.rmtree(BUILD, ignore_errors=True)
    for sub in ("META-INF", "OEBPS/styles", "OEBPS/images", "OEBPS/text"):
        os.makedirs(os.path.join(BUILD, *sub.split("/")))

    # 1) 正文
    chapters = []
    for n in range(1, CHAPTER_COUNT + 1):
        body, subtitle = clean_chapter(n)
        chapters.append((n, subtitle))
        write(os.path.join(BUILD, "OEBPS/text/chapter-%d.xhtml" % n),
              chapter_page(n, body, subtitle))
    if not args.quiet:
        print("正文 %d 章已 XHTML 化" % CHAPTER_COUNT)

    # 2) 前置页 / 术语表 / 导航
    write(os.path.join(BUILD, "OEBPS/text/cover.xhtml"), cover_page())
    write(os.path.join(BUILD, "OEBPS/text/titlepage.xhtml"), title_page())
    write(os.path.join(BUILD, "OEBPS/text/translator-note.xhtml"), translator_note())
    write(os.path.join(BUILD, "OEBPS/text/glossary.xhtml"), glossary_page())
    # nav.xhtml 必须和章节放在同一目录。它内部写的是 chapter-N.xhtml、
    # ../styles/zh.css 这类**相对**路径，而各章页脚的 <a href="nav.xhtml"> 也是按
    # 「同一个目录」解析的。一旦把 nav.xhtml 放到 OEBPS/ 根上，这两组链接会同时断掉，
    # 症状就是 Apple Books 里点目录没反应（NCX 却是好的，所以不容易发现）。
    write(os.path.join(BUILD, "OEBPS", TEXT_DIR, "nav.xhtml"), nav_xhtml(chapters))
    write(os.path.join(BUILD, "OEBPS/toc.ncx"), toc_ncx(chapters))
    write(os.path.join(BUILD, "OEBPS/styles/zh.css"), CSS)
    write(os.path.join(BUILD, "OEBPS/content.opf"), content_opf(chapters))
    write(os.path.join(BUILD, "META-INF/container.xml"), CONTAINER)

    # 3) 封面
    build_cover(os.path.join(BUILD, "OEBPS/images/cover.jpg"))

    # 4) 打包（mimetype 必须第一个且不压缩）
    #    以 "w" 打开会直接截断旧文件，不要先 os.remove（某些沙箱禁止 unlink）
    with zipfile.ZipFile(out, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, "application/epub+zip")
        for root, _, files in os.walk(BUILD):
            for f in sorted(files):
                full = os.path.join(root, f)
                arc = os.path.relpath(full, BUILD)
                z.write(full, arc, compress_type=zipfile.ZIP_DEFLATED)

    if not args.keep_build:
        shutil.rmtree(BUILD, ignore_errors=True)

    size = os.path.getsize(out) / 1024 / 1024
    if not args.quiet:
        print("已生成：%s（%.2f MB）" % (os.path.basename(out), size))
    return 0


def write(path, text):
    """写文本文件，统一 UTF-8。"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


if __name__ == "__main__":
    sys.exit(main())
