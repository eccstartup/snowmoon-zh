# Snowmoon 中文版 · 翻译规范（所有译者必须遵守）

原站：https://vitalik.eth.limo/snowmoon/ ｜ 授权：GPL v3 ｜ 作者：Vitalik Buterin

## 0. 交付物

把 `https://vitalik.eth.limo/snowmoon/html/chapter-N.html` 的正文译成**简体中文**，
写出到 `/Users/eccstartup/code/claude/snowball/snowmoon-zh/html/chapter-N.html`。

同一目录下已有 `../assets/style.css` 与 `../assets/app.js`，**不要**再内联样式表或脚本。

## 1. 结构与还原（最重要）

原文是**左编辑框 / 右预览**的 docs_app 页面，正文全部在 `<div class="document-page">` 里。
翻译时必须做到**结构一一对应**，不得合并、拆分、增删段落。

**原样搬运、一个字都不要动的块：**

- `<nav class="chapter-nav wc-exclude">…</nav>`（正文最前和最后各一个，含其中的 `<svg>` 与 `href`；
  href 形如 `chapter-2.html`，因为是同目录相对链接，**保持原样**）。
  但 nav 里的**英文界面文案要译成中文**：`title="Next chapter: Chapter 5"` → `title="下一章：第 5 章"`，
  `title="Previous chapter: Chapter 3"` → `title="上一章：第 3 章"`，`aria-label` 同理。其余属性（`href`、`class`、svg 几何）不动。
- `<div class="dateline …"><hr class="rule"><span class="txt"><span class="place">…</span><span class="sep">·</span><span class="date">…</span></span></div>`
  整块**逐字保留**：`.place` 用英文地名（专名保留英文），`.date` 如 `3724 Snowmoon 3` 也保留原样。
- `<img>`、`<hr>`、`<br>`

**保留骨架、只换文字：**

- `<h1>` → `第 N 章`
- `<blockquote>`（广告、公告、来信、诗）→ 译文字，保留 `<p>` 结构
- `<ul>/<ol>/<li>` → 保留嵌套层级
- `<table>`（几乎总在 `device-view` 里）→ 保留 `<thead>/<tbody>/<tr>/<td>/<th>`、所有 `style="…"`、
  `width="…"` 属性与 `&#8594;` 之类实体，只把文字译成中文（表头 `From/Message/Time` → `发件人/消息/时间`，
  `→` 保持箭头）。
- `<div class="device-view …">` / `<div class="narrow-device-view">` / `<div class="wide-device-view">`
  → 整块保留，只译其中的可见文字。
- `<div class="dz-card">` → `.dz-title` 译中文；`.dz-mono` 里的造语（Dzegoban 罗马字）**原样保留**，
  可在其后用括号补一句中文释义。
- 对话 `<span style="color:oklch(…)">…</span>` → **`style` 属性一个字符都不许改**，只替换里面的文字。
  同一人物的颜色必须固定不变。

**SVG 图（重要）：**
`viewBox`、`d`、`x/y/width/height`、`transform` 等几何属性**一律不动**。
只把 `<text>` / `<tspan>` 里的可见文字换成中文；中文若明显比英文长或短，**只允许**微调该 `<text>` 的
`font-size`，不得改坐标。SVG 内的专名（Gladias、Veridia…）保持英文。

## 2. 专名与术语（全书唯一体例，不得自行变通）

分两类。**判断标准：英文名是不是「可直译的普通词组合」。**

### 甲类 · 专名 —— 正文里写**英文原词**，每章首次出现补一次中文括注

人名、地名、国名、政体名、民族名、语言名、机构与组织名、品牌与产品名、棋戏名、单位与货币名。

- 例：`Veridia（维瑞迪亚）`、`Meldan（梅尔丹）`、`Dzego（泽戈）`、`Gladias（格拉迪亚斯）`、
  `Zei（泽伊）`、`Bai（白）`、`Fin（芬）`、`Pafogai Du（帕福盖杜）`、`Arctic Empire（北极帝国）`、
  `Arctics（北极人）`、`Veridian（维瑞迪亚人）`、`United Cities（联合城市）`、`Freetown（自由城）`、
  `Redshire（红郡）`、`Northglade（北谷）`、`Northshore（北岸）`、`Greater Plum Harbor（大梅港）`、
  `Glasscrown（玻璃冠）`、`Silverchat（银聊）`、`Bluewhale（蓝鲸）`、`Hydrafill（海德菲尔）`、
  `Dreadknot（死结）`、`Helisport（直升机球）`、`Minpentai（民本台）`、`Bansunpei（班孙培）`、
  `Kungaupei（昆高培）`、`Dzegojan（泽戈人）`、`tick（滴答）`、`longhour（长时）`、
  `lightfoot（光尺）`、`zipcoins（泽币）`。
- 括注只在本章**第一次**出现时给一次，其后只写英文。
- 只有可直译的组合式政体名（Arctic Empire、United Cities、Freetown、Redshire、Northglade、
  Northshore、Greater Plum Harbor、Glasscrown、Helisport、Silverchat、Bluewhale、Hydrafill、
  Dreadknot）也归甲类——因为它们仍是**专名**，统一起来读者才不会在同一页里看到两套写法。

### 乙类 · 角色／机制／技术／装置／观念词 —— 正文里写**中文**，首次出现补一次英文括注

- 例：`引导会（Order of Steering）`、`守望者（Keeper）`、`哨卫（Sentinel）`、`见习者（Acolyte）`、
  `传令者（Herald）`、`评分表（rubric）`、`密码学抽签`、`二次投票（quadratic voting）`、
  `图谱资助（Graph Funding）`、`二次方资助`、`匿名长袍（privacy robe）`、`防传声箔`、`颈带（neck band）`、
  `手边设备（hand device）`、`算力盒（compute box）`、`共同家庭`、`市民议会`、`最高议会`、
  `零知识证明（zero-knowledge proof）`、`作废子（nullifier）`。
- 这类词是**普通名词**（角色、制度、器物），中文读起来才顺，故中文在前。

### 造语

**Dzegoban 造语、Minpentai 喊话串、暗号：逐字保留罗马化原文，绝不改写、绝不意译成中文。**
`dze kai lin pan`、`Dze go ba fau gie`、`MU GU GEI FA`、`po so dze go ban de sia`、`jie fe hen dzi`。
原文若自带释义，释义照常译成中文（如 `dze kai lin pan`（青菜与米饭））。

### 日期

`3724 Snowmoon 3` 原样保留（含月份名，Snowmoon 既是月份名也是书名）。

**术语细节以同目录 `../术语表.md` 与 `专名统一.md` 为准，冲突时以本节为准。**

## 3. 文体

文学性简体中文，克制、干净、有节奏；不堆感叹号，不用网络语，不加译者注进正文。
对话统一用中文双引号 “ ”（嵌套用 ‘ ’）。
数字、百分数、代号（如 `Badra St #1103`、`Rep score ≥ 200`）保留阿拉伯数字与符号。

## 4. 文件模板

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>第 N 章 — Snowmoon 中文版</title>
    <link rel="stylesheet" href="../assets/style.css">
</head>
<body>
    <button class="dark-toggle" onclick="toggleDarkMode()">☀️</button>
    <div class="document-page">
<!-- 这里照抄原文 document-page 内部的全部结构，文字换成中文 -->
    </div>
    <script src="../assets/app.js"></script>
</body>
</html>
```

## 5. 交稿前自检（务必执行）

用 bash + python 比对**原文**与**你的译文**的元素计数，把结果打印出来：

- `<p>` 数量：必须**相等**（正文段数不允许变化）
- `<nav class="chapter-nav` 数量：应为 2
- `<div class="dateline` 数量：与原文相等
- `<span style="color:oklch` 数量：与原文相等
- `<svg`、`<table`、`<div class="dz-card`、`<blockquote` 数量：分别与原文相等
- `<link rel="stylesheet" href="../assets/style.css">` 存在
- 文件里不含残留的英文正文段落（专名、造语、日期除外）

自检命令示例（原文可现取于远端，或直接对同一页面 HTML 计数）：

```bash
python3 - <<'PY'
import re,urllib.request  # 注：禁止用 bash 抓网页；此处仅对已保存的文本计数
for f,label in [('SRC','原文'),('OUT','译文')]:
    t=open(f,encoding='utf-8').read()
    print(label, {k:len(re.findall(p,t)) for k,p in {
      'p':r'<p[ >]','nav':r'class="chapter-nav','dateline':r'class="dateline',
      'span':r'<span style="color:oklch','svg':r'<svg','table':r'<table',
      'dz':r'class="dz-card','bq':r'<blockquote'}.items()})
PY
```

（把 SRC 换成你把抓到的原文保存下来的路径；抓取请使用 WebFetch / mcp__workspace__web_fetch，
**不要**用 curl / wget。）

## 6. 回报格式

完成后回报一行：
`chapter-N OK | 原文词数 W | 译文汉字数 C | 段落 p1→p2 | svg s1→s2 | table t1→t2 | dz d1→d2`
并列出该章你遇到的、`术语表.md` 里没有的新专名（英文 + 你的中文括注）。
