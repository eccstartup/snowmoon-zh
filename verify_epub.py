#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_epub.py — 对 Snowmoon-雪月-中译本.epub 做结构与一致性校验。

用法：
    python3 verify_epub.py [EPUB 路径]      # 默认校验同目录下的成品

检查项：
  1. zip 结构（mimetype 必须第一个、且不压缩）
  2. 每个 XHTML/OPF/NCX 是否良构 XML
  3. manifest ↔ 实际文件一一对应，且**包内所有相对链接**按各自目录解析得通
  4. 正文残留物（oklch / button / input / script / 事件处理器 / :has）
  5. 结构保真：与原站「去掉导航后的 document-page」逐类比对
  6. 三处有意转换的计数核对（配色 / 按钮 / 滑杆）
  7. 样式表里 hue 类是否齐备
  8. 表格分页规则与配色主题（含深色表头底色回归检查）
  9. 术语表、目录、规模

刻意**不**依赖 EPUB 的位置：第 5、6 节以仓库里的 html/chapter-*.html（原站存档）
为基准比对，所以脚本要在 snowmoon-zh/ 目录结构内运行。
"""

import argparse
import os
import posixpath
import re
import sys
import zipfile

from bs4 import BeautifulSoup
from lxml import etree

ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_EPUB = os.path.join(ROOT, "Snowmoon-雪月-中译本.epub")
# 逐章结构比对的基准：仓库里的原站存档，与 EPUB 放哪儿无关
SRC_HTML = os.path.join(ROOT, "html")

fails = []


def check(label, ok, detail=""):
    print("  %s %s%s" % ("✓" if ok else "✗", label, ("  " + detail) if detail else ""))
    if not ok:
        fails.append(label)


def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        prog="verify_epub.py",
        description="校验 Snowmoon-雪月-中译本.epub：zip 结构、XML 良构、manifest、"
                    "包内链接、正文残留物、与原站逐章结构比对、样式与规模。",
        epilog="需在 snowmoon-zh/ 目录结构内运行（第 5、6 节以 html/ 下的原站存档为基准）。")
    ap.add_argument("epub", nargs="?", default=DEFAULT_EPUB,
                    help="要校验的 EPUB（默认 %(default)s）")
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    epub = args.epub

    if not os.path.exists(epub):
        sys.exit("找不到 %s，请先跑 build_epub.py" % epub)
    fails.clear()
    z = zipfile.ZipFile(epub)
    names = z.namelist()
    xhtml = sorted(n for n in names if n.startswith("OEBPS/text/"))

    print("1. zip 结构")
    infos = z.infolist()
    check("mimetype 是第一个条目且不压缩",
          infos[0].filename == "mimetype" and infos[0].compress_type == zipfile.ZIP_STORED)
    check("mimetype 内容正确", z.read("mimetype").decode() == "application/epub+zip")
    check("容器描述存在", "META-INF/container.xml" in names)

    print("2. XML 良构性")
    bad = []
    for n in names:
        if n.endswith((".xhtml", ".opf", ".ncx", ".xml")):
            try:
                etree.fromstring(z.read(n))
            except Exception as e:
                bad.append((n, str(e)[:80]))
    check("全部 XML 良构（%d 个文件）" % sum(
        1 for n in names if n.endswith((".xhtml", ".opf", ".ncx", ".xml"))), not bad)
    for b in bad:
        print("    ", b)

    print("3. manifest ↔ 文件")
    opf = etree.fromstring(z.read("OEBPS/content.opf"))
    ns = {"o": "http://www.idpf.org/2007/opf"}
    items = opf.findall(".//o:item", ns)
    declared = {"OEBPS/" + i.get("href") for i in items}
    check("manifest 里的 href 都真实存在", not (declared - set(names)))
    check("OEBPS/text/ 下的文件都在 manifest 中声明",
          not [n for n in xhtml if n not in declared])
    check("spine 的 idref 都能解析",
          all(("OEBPS/" + i.get("href")) in set(names)
              for i in items
              for r in opf.findall('.//o:itemref', ns) if r.get("idref") == i.get("id")))

    # 全包链接体检：把每个 xhtml/opf/ncx 里的 href/src 按**它自己所在目录**解析。
    # 这一项是补上的——正因为原先没有，nav.xhtml 里按错目录写的相对路径才一路出了厂
    # （症状：Apple Books 目录点了没反应，而 NCX 正常，所以一直没暴露）。
    broken_links = {}
    for n in sorted(names):
        if not n.endswith((".xhtml", ".opf", ".ncx", ".xml")):
            continue
        for attr in ("href", "src"):
            for m in re.finditer(attr + r'="([^"]+)"', z.read(n).decode()):
                tgt = m.group(1)
                if tgt.startswith(("http://", "https://", "mailto:", "data:", "#")):
                    continue
                tgt = tgt.split("#")[0]
                if not tgt:
                    continue
                r = posixpath.normpath(posixpath.join(posixpath.dirname(n), tgt))
                if r not in names:
                    broken_links.setdefault(n, []).append((attr, m.group(1), r))
    check("全包内部链接都能解析到真实文件", not broken_links,
          "" if not broken_links else "%d 个文件有断链：%s"
          % (len(broken_links), sorted(broken_links)[:3]))

    print("4. 正文残留物")
    # 只扫 32 章正文；前置页/术语表是手写的，其中的 oklch 等字样属于正常叙述
    res = {"oklch": 0, "<button": 0, "<input": 0, "<script": 0, "onclick": 0,
           "onchange": 0, "localStorage": 0, ":has(": 0, "javascript:": 0}
    chaps = [n for n in xhtml if "chapter-" in n]
    for n in chaps:
        t = z.read(n).decode()
        for k in res:
            res[k] += t.count(k)
    check("32 章正文无脚本/旧标签残留", not any(res.values()), str(res))

    # style 属性里不该出现空声明（如 color:），那是剥掉 oklch 时留下的残渣
    empty_decl = []
    for n in chaps:
        for m in re.finditer(r'style="([^"]*)"', z.read(n).decode()):
            for d in m.group(1).split(";"):
                d = d.strip()
                if d and d.endswith(":"):
                    empty_decl.append((n, d))
    check("无空 CSS 声明残留", not empty_decl, str(empty_decl[:3]))

    print("5. 结构保真（对比原站）")
    src_dir = SRC_HTML
    if not os.path.isdir(src_dir):
        print("  （跳过：找不到原站 html/ 目录）")
    else:
        keys = {"p": r"<p[ >]", "hr": r"<hr[ >/]", "table": r"<table",
                "blockquote": r"<blockquote", "svg": r"<svg", "dz": r'class="dz-card',
                "dateline": r'class="dateline', "img": r"<img", "li": r"<li[ >]",
                "ul": r"<ul", "ol": r"<ol[ >]", "div": r"<div[ >]",
                "h1": r"<h1[ >]", "h2": r"<h2[ >]", "h3": r"<h3[ >]"}
        mism = []
        for n in range(1, 33):
            soup = BeautifulSoup(open(os.path.join(src_dir, "chapter-%d.html" % n),
                                      encoding="utf-8").read(), "html5lib")
            dp = soup.find("div", class_="document-page")
            for nav in dp.find_all("nav", class_="chapter-nav"):
                nav.decompose()
            base = dp.decode_contents()
            body = re.search(r'<section class="document-page"[^>]*>(.*?)</section>',
                             z.read("OEBPS/text/chapter-%d.xhtml" % n).decode(),
                             re.S).group(1)
            a = {k: len(re.findall(p, base)) for k, p in keys.items()}
            b = {k: len(re.findall(p, body)) for k, p in keys.items()}
            d = {k: (a[k], b[k]) for k in a if a[k] != b[k]}
            exp_span = sum(len(re.findall(p, base)) for p in ("<span", "<button", "<input"))
            got_span = len(re.findall(r"<span", body))
            if exp_span != got_span:
                d["span"] = (exp_span, got_span)
            if d:
                mism.append((n, d))
        check("32 章结构逐类对齐", not mism, "" if not mism else str(mism[:4]))

    print("6. 有意转换的计数")
    if os.path.isdir(src_dir):
        o = h = bt = bi = cb = cr = 0
        for n in range(1, 33):
            s = open(os.path.join(src_dir, "chapter-%d.html" % n), encoding="utf-8").read()
            x = z.read("OEBPS/text/chapter-%d.xhtml" % n).decode()
            # 原站每章另有 1 个 dark-toggle 按钮在 document-page 之外
            o += len(re.findall(r"oklch\(", s))
            h += len(re.findall(r'class="hue\d+"', x))
            bt += len(re.findall(r"<button", s)) - 1
            bi += len(re.findall(r"<input", s))
            cb += len(re.findall(r"\bdv-btn\b", x))
            cr += len(re.findall(r"\bdv-range\b", x))
        check("对话配色 oklch → hue 类", o == h, "%d → %d" % (o, h))
        check("按钮 <button> → .dv-btn", bt == cb, "%d → %d" % (bt, cb))
        check("滑杆 <input> → .dv-range", bi == cr, "%d → %d" % (bi, cr))

    print("7. 样式表")
    css = z.read("OEBPS/styles/zh.css").decode()
    # 去掉注释再检查，避免注释里提到的 oklch/:has 造成误判
    css_code = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    used = set()
    for n in xhtml:
        used |= set(re.findall(r'class="(hue\d+)"', z.read(n).decode()))
    defined = set(re.findall(r"\.(hue\d+)\s*\{", css_code))
    check("用到的 hue 类都有定义", not (used - defined), "用到 %d 类" % len(used))
    check("样式表实际代码不含 oklch/:has()/变量",
          "oklch" not in css_code and ":has(" not in css_code and "var(--" not in css_code)

    print("8. 表格分页规则")
    check("长表断页后表头会重复", "display: table-header-group" in css_code)
    check("行与单元格不被拦腰截断",
          re.search(r"tr,\s*th,\s*td\s*\{[^}]*break-inside:\s*avoid", css_code) is not None)
    check("keep / dv-keep 都有对应样式",
          ".device-view.dv-keep" in css_code and "table.keep" in css_code)

    # 只有确实矮的块才该被标记 keep：太高的块强行留页会溢出。
    # 必须按块解析，不能用正则开个窗口——窗口会溢出到相邻的块里去。
    bad_keep = []
    for n in [x for x in xhtml if "chapter-" in x]:
        for dv in BeautifulSoup(z.read(n).decode(), "html5lib").find_all(
                "div", class_="device-view"):
            if "dv-keep" not in (dv.get("class") or []):
                continue
            hs = [int(s["height"]) for s in dv.find_all("svg")
                  if str(s.get("height") or "").isdigit()]
            if (hs and max(hs) >= 150) or len(dv.find_all("tr")) > 9:
                bad_keep.append((n, max(hs) if hs else 0, len(dv.find_all("tr"))))
    check("没有把含大幅 SVG 的块错标为整块保留", not bad_keep, str(bad_keep[:3]))

    # 术语表的长表不该被标 keep（标了反而会溢出留白）
    gsoup = BeautifulSoup(z.read("OEBPS/text/glossary.xhtml").decode(), "html5lib")
    over = [(len(t.find_all("tr")), "keep" in (t.get("class") or []))
            for t in gsoup.find_all("table") if len(t.find_all("tr")) >= 20]
    check("长表（≥20 行）未被标为整张保留", not any(k for _, k in over),
          "长表 %d 张" % len(over))

    # 表格块走浅色主题：该标的只有「含表格」的块，图示块一律不标
    mis_light = []
    n_light = n_dark_svg = 0
    for n in [x for x in xhtml if "chapter-" in x]:
        for dv in BeautifulSoup(z.read(n).decode(), "html5lib").find_all(
                "div", class_="device-view"):
            marked = "dv-light" in (dv.get("class") or [])
            has_tab = bool(dv.find("table"))
            has_svg = bool(dv.find("svg"))
            if marked:
                n_light += 1
            if has_svg:
                n_dark_svg += 1
            if marked != has_tab or (marked and has_svg):
                mis_light.append((n, marked, has_tab, has_svg))
    check("含表格的块恰好都标了 dv-light、含 SVG 的块都没标",
          not mis_light, "浅色 %d 块 / 仍为深色 %d 块" % (n_light, n_dark_svg))

    check("浅色表格样式齐备",
          ".device-view.dv-light" in css_code
          and ".device-view.dv-light th" in css_code
          and ".device-view.dv-light tbody tr:nth-child(even)" in css_code)

    # 深色模拟块的 th 必须自带 background-color：通用 `th { background: #eceaf6 }`
    # 会盖到模拟块里，把深色表头变成浅底浅字（#cef on #eceaf6 ≈ 1.1:1）。
    check("深色模拟块的 th 自带底色，不被通用 th 规则盖掉",
          re.search(r"\.device-view th\s*\{[^}]*background-color", css_code) is not None)

    print("9. 术语表 / 目录 / 规模")
    g = z.read("OEBPS/text/glossary.xhtml").decode()
    check("术语表含正文表格", g.count("<table") >= 6, "%d 个表" % g.count("<table"))
    nav = z.read("OEBPS/text/nav.xhtml").decode()
    check("目录覆盖 32 章 + 前置 + 术语表", nav.count("<li>") == 38)
    han = 0
    for n in xhtml:
        if "chapter-" in n:
            body = re.search(r'<section class="document-page"[^>]*>(.*?)</section>',
                             z.read(n).decode(), re.S).group(1)
            han += len(re.findall(r"[一-鿿]", re.sub(r"<[^>]+>", "", body)))
    print("  正文汉字 ~%d 字；EPUB 共 %d 个条目" % (han, len(names)))

    print()
    if fails:
        print("有 %d 项未通过：%s" % (len(fails), fails))
        sys.exit(1)
    print("全部检查通过 ✓")


if __name__ == "__main__":
    sys.exit(main())
