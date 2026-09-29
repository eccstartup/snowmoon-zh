# 《Snowmoon（雪月）》中文版

Vitalik Buterin 的科幻小说 **《Snowmoon》**（32 章，约 10 万词）的简体中文全译。
本仓库同时装着两件成品和生成它们的脚本：

| 成品 | 位置 | 说明 |
|---|---|---|
| 浏览器镜像站 | `index.html` + `html/chapter-1..32.html` | 结构、配色、暗色模式与人名对话配色全部沿用原作，逐章一一对应 |
| EPUB 3 电子书 | `Snowmoon-雪月-中译本.epub` | 封面／书名页／译者说明／32 章／术语表／两级目录，可直接导入 Apple Books、Kobo、Calibre |

- **原作**：Vitalik Buterin, *Snowmoon* — <https://vitalik.eth.limo/snowmoon/>
- **原作分章**：`https://vitalik.eth.limo/snowmoon/html/chapter-N.html`
- **授权**：**GPL v3**（原作即以此发布，本译本沿用同一授权）— <https://www.gnu.org/licenses/gpl-3.0.html>
- 正文约 **14.3 万汉字**，与原作逐章对应；术语表 6 节。

---

## 快速开始

```bash
make epub      # 重新生成 EPUB（成品写在仓库根）
make check     # 校验成品（26 项检查）
make site      # 本地预览镜像站 → http://localhost:8000/
make help      # 列出全部目标
```

不想装 `make` 就直接调用脚本，两者等价：

```bash
python3 build_epub.py            # 出包；--help 看全部选项
python3 verify_epub.py           # 校验；也可跟一个 EPUB 路径校验别处的成品
```

**依赖**：Python 3 + `beautifulsoup4`、`html5lib`、`Pillow`、`lxml`；`pandoc` 只在把
`术语表.md` 转成 HTML 时用到（缺了会跳过术语表生成）。

---

## 仓库结构

```
snowmoon-zh/
├── index.html                 中文首页（目录 + 授权/AI/爱 三段声明）
├── html/chapter-1..32.html    32 章中文译文
├── assets/style.css           全书样式（提取自原作，含中文字体与排版微调）
├── assets/app.js              明暗主题切换
├── 术语表.md                  全书统一译名总表（6 节）
│
├── build_epub.py              出 EPUB 3（封面／32 章／术语表／目录，可重跑）
├── verify_epub.py             EPUB 校验（9 节 26 项）
├── Makefile                   常用命令封装
├── Snowmoon-雪月-中译本.epub  成品电子书
├── 表格浅色对比.png           表格配色的改前/改后对照（含 WCAG 对比度实测）
├── LICENSE                    GPL v3 全文
│
├── _spec/SPEC.md              翻译规范：结构还原 + 专名体例
├── _spec/专名统一.md          专名中英对照表与「单字名陷阱」清单
├── _spec/js_norm.py           专名体例校平脚本（一次性，支持 --dry-run 复核）
└── _source_en/                原作英文正文存档（校验基准，非成品）
```

生成脚本的原则是**从源重跑，不依赖上次产物**：`build_epub.py` 每次都从
`html/chapter-*.html` 重新生成整包，中间产物写到系统临时目录（所以成品随时可删可重跑）。

---

## 成品一：浏览器镜像站

直接用浏览器打开 **`index.html`** 即可，首页有 32 章的目录。
每章顶部与底部都有「上一章 / 下一章」箭头，右上角 ☀️ 按钮切换明暗主题。

本地起个静态服务器也可以（推荐，避免个别浏览器的本地文件限制）：

```bash
make site        # 等价于 python3 -m http.server 8000
# 然后访问 http://localhost:8000/
```

---

## 成品二：EPUB 3 电子书

`Snowmoon-雪月-中译本.epub` 含封面、书名页、译者说明、32 章正文、术语表与两级目录
（EPUB 3 的 `nav.xhtml` + EPUB 2 的 `toc.ncx`，兼容新旧阅读器）。

`dc:identifier` 用 `uuid5` 从固定命名空间推导，**每次重建都一样**——阅读器不会把重出的包
当成另一本书。包里共 43 个条目，约 0.46 MB。

打包时对原作做了三处必要的等价转换（`verify_epub.py` 第 6 节会逐项核对数量）：

| 原作写法 | EPUB 写法 | 原因 |
|---|---|---|
| `<span style="color:oklch(0.7 0.15 H)">` | `<span class="hueK">`（hex） | 阅读器普遍不支持 `oklch()`，按 27 等分色轮精确换算成等效 sRGB（全书 2541 处） |
| `<button>`（界面模拟块内） | `<span class="dv-btn">` | 不可交互，避免被当控件（26 处） |
| `<input type="range">` | `<span class="dv-range">` | 同上，渲染成静音条（3 处） |

另外：原站顶/底「上一章／下一章」图标导航改为 EPUB 页脚文字导航；
`h1:has(+ .dateline)` 这类阅读器不支持的 CSS 已改为在生成阶段打标；
`<script>`、内联事件、主题切换按钮不在正文内，天然不进包。

### 目录与跳转

`nav.xhtml` 必须和章节放在**同一目录**（`OEBPS/text/`）。原因：它内部写的是
`chapter-1.xhtml`、`../styles/zh.css` 这类**相对**路径，而各章页脚的
`<a href="nav.xhtml">目录</a>` 也按「同一目录」解析——两边是互相咬合的。

早先 `nav.xhtml` 被放在 `OEBPS/` 根上，这两组链接就同时断了（**共 33 个文件**），
症状是在 Apple Books 里**点目录没反应**。之所以一直没被发现，是因为 `toc.ncx` 用的是
`text/…` 这类正确路径，能盖住一部分阅读器。

`verify_epub.py` 现在有一项「**全包链接体检**」：把包里每个 xhtml / opf / ncx 的
`href` / `src` 按**它自己所在目录**逐个解析，确认目标真实存在。这一项正是此前缺的，
所以这类问题才能一路出厂。

> 可重排 EPUB 没有固定页码，阅读器显示的是「位置／百分比」；目录条目标的是**章节**而非页码。

### 表格分页

可重排 EPUB 没有固定页边界，**比屏幕高的表必然要断开**——这是格式性质，不是排版错误，
任何阅读器都一样。能控制的是「断得体不体面」，包里做了三层处理：

1. `tr / th / td { break-inside: avoid }` —— 单元格和整行绝不拦腰截断；
2. `thead { display: table-header-group }` —— 长表真的断页时，**表头在新页自动重复**，
   读者不会失去列名；
3. 估算渲染行数，**明显放得下的表整张保留**：正文 140 个界面模拟块按体型标记 `dv-keep`
   （**83 个矮块**整块保留；其余 **57 个不标记**，允许自然断开——其中 55 个含 SVG 图示、
   2 个是超高的文本块，强行留页会溢出）；
   术语表 8 张表里 4 张短表（估算 ≤16 行）整张保留，4 张长表走「断页 + 表头重复」。

术语表有一张 **41 行**的三方对照表、一张 22 行、一张 20 行，这类表在任何阅读器上都放不进
一屏。若希望它们也「永不断页」，只能改内容形态（拆成多张小表，或改成分条列表），
需要在 `术语表.md` 层面调整。

### 表格配色（浅色主题）

原作与原站在明、暗两种模式下，界面模拟块（`.device-view`）**都是深色设备屏**（`#0a0e27`），
而正文 69 张表全都长在那里面（术语表另有 8 张手写表格，不在模拟块内）——原站没有「浅色表格」可抄。本译本把**含表格的 65 个块**
改成浅色主题：`.device-view.dv-light`，浅底深字、`#e2ebf8` 表头、`#eef4fc` 斑马纹，
只留等宽字体这一点「设备感」。

顺带修掉一个此前引入的缺陷：通用规则 `th { background: #eceaf6 }` 会盖到模拟块里，
把深色表头变成**浅底浅字**（`#cceeff` 压 `#eceaf6`，对比度 **1.02:1**，肉眼等于看不见）。
现在深色块的 `th` 显式写了自己的底色，浅色块另有规则；`verify_epub.py` 有两项回归检查
盯着这件事。

**含 SVG 图示的 56 个块故意不改**：图里的深色界面是 SVG 自己画死的底色
（第 1 章星空图最外层就是 `<rect width="400" height="214" fill="#348">`），
改面板底色不会让图变亮，只会变成「浅色卡片里嵌一块深色图」。

配色模式可以直接从命令行切换：

```bash
python3 build_epub.py --light-device table   # 默认：只改含表格的块
python3 build_epub.py --light-device all     # 连 SVG 图示块也改浅色
python3 build_epub.py --light-device off     # 完全照原作，全部深色设备屏
```

改前 / 改后的实测对照见 `表格浅色对比.png`（表头 1.02:1 → 11.2:1，表体 14.3:1）。

### 为什么把 EPUB 成品也提交进仓库

`.epub` 是二进制、diffs 不可读，一般来说不该入库。这里仍然提交，是因为：

- 它是**最终交付物**——clone 下来就能直接读，不必先配 Python 环境再出包；
- 只有 0.46 MB，二进制成本可以忽略；
- `verify_epub.py` 第 5、6 节以仓库里的 `html/` 原站存档为基准做逐章比对，
  也就是说**成品与基准都在仓库里**，校验不必依赖外部下载。

`.gitattributes` 已把 `*.epub` 标为 `binary`，不会做行尾转换。改稿时记得
**先跑 `make epub` 再提交**，否则仓库里的成品会落后于正文。

> Apple Books 会缓存旧副本：换新包后需先在书库里删掉旧书，再重新导入，否则看到的还是旧的。

---

## 翻译体例（一句话）

**甲类 · 专名**（人名／地名／国名／政体／民族／语言／机构／品牌／棋戏／单位货币）
→ 正文写**英文原词**，每章首次出现补一次中文括注：`Veridia（维瑞迪亚）`、`Zei（泽伊）`、`tick（滴答）`。

**乙类 · 角色／机制／技术／装置／观念词**
→ 正文写**中文**，首次出现补一次英文括注：`引导会（Order of Steering）`、`匿名长袍（privacy robe）`。

**Dzegoban 造语**逐字保留罗马化原文，绝不改写；释义只放在紧随其后的中文括注里。
**日期**（`3724 Snowmoon 3`）与 **dateline** 逐块原样保留。

完整规则见 `_spec/SPEC.md` §2；全部译名见 `术语表.md`。
`_spec/js_norm.py` 是当初用来把「先译后统一」的专名一次校平的工具，留着便于复核——
它**默认就地改写文件**，用前先 `--dry-run`，并确保有 git 兜底。

---

## 结构与质量校验

`make check` 跑 9 节 26 项检查：zip 结构（`mimetype` 必须是第一个条目且不压缩）、
40 个 XML 文件良构、manifest ↔ 实际文件一一对应、**包内相对链接逐条解析**、
正文残留物（`oklch` / `<button>` / `<input>` / `<script>` / 事件处理器 / `:has`）、
与原站逐章结构比对、三处等价转换的计数、样式表完整性、表格分页与配色主题、
术语表与目录规模。

每章都与原作英文正文做过元素级比对，以下各项**与原文字符级一致**：

`<p>` 段落数 · `<nav class="chapter-nav">` · `<div class="dateline">` ·
`<span style="color:oklch(…)">`（对话配色，style 属性一字未改）· `<svg>` · `<table>` ·
`<div class="dz-card">` · `<blockquote>`

需要临时抽查某一类元素时，这段小脚本比整套校验更快：

```bash
python3 - <<'PY'
import re, os
cnt = lambda t: {k: len(re.findall(p, t)) for k, p in {
  'p': r'<p[ >]', 'nav': r'class="chapter-nav', 'dateline': r'class="dateline',
  'oklch': r'<span style="color:oklch', 'svg': r'<svg', 'table': r'<table',
  'dz': r'class="dz-card', 'bq': r'<blockquote'}.items()}
for n in range(1, 33):
    s = f'_source_en/chapter-{n}.body.html'
    if not os.path.exists(s):
        s = f'_source_en/chapter-{n}.src.html'
    a, b = cnt(open(s, encoding='utf-8').read()), cnt(open(f'html/chapter-{n}.html', encoding='utf-8').read())
    print(n, 'OK' if a == b else {k: (a[k], b[k]) for k in a if a[k] != b[k]})
PY
```

---

## 声明（译自原作首页）

**授权**：原作以 **GPL v3** 发布，不是 CC-BY-SA。你可以自由地把它拍成电影、做成动画或任何形式；
但若这么做，须把制作流程（AI 提示词、脚本、针对具体任务的脚手架等）及其他非通用材料一并开源。
本仓库的构建脚本（`build_epub.py`、`verify_epub.py`、`Makefile`）即按此要求一并开放。

**AI 使用声明**（原作）：所有文字由作者本人直接撰写；拼写、语法与文风检查，Minpentai 与 Dzegoban
规则一致性核验，HTML/CSS 与 SVG，均在 Kimi K3 与 Qwen 3.8 Flash Next 协助下完成。
本中文译本由 Claude 辅助翻译，正文全部译自原作英文原文。

**爱 使用声明**：《Snowmoon》是用爱写成的。

---

## 出处

| 内容 | 链接 |
|---|---|
| 原作首页 | <https://vitalik.eth.limo/snowmoon/> |
| 原作分章 | <https://vitalik.eth.limo/snowmoon/html/chapter-1.html> … `chapter-32.html` |
| GPL v3 全文 | <https://www.gnu.org/licenses/gpl-3.0.html> |
| EPUB 3 规范 | <https://www.w3.org/TR/epub-33/> |
| EPUB `nav` 文档 | <https://www.w3.org/TR/epub-33/#sec-nav> |
