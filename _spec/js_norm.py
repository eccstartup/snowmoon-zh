#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""js_norm.py — 专名体例校平：把正文里写成中文的专名改回英文原词
（每章首次出现保留一次中文括注）。

只改文本节点；`<svg>`、dateline、任何标签一律不动。
机制词 / 装置词 / 单位以外的普通词不动。规则表见下方 BARE / NO_BARE。

用法：
    python3 _spec/js_norm.py --dry-run html/chapter-1.html    # 先看会改什么
    python3 _spec/js_norm.py html/chapter-*.html              # 确认后就地改写

注意：**默认就地改写**文件，且没有撤销。批量跑之前先 `--dry-run`，并确保有 git 兜底。
这是一次性校平工具（体例统一后已用完），保留在仓库里用于复核与将来改稿。
"""
import argparse
import os
import re
import sys

# 中文 -> 英文（长度倒序应用）
BARE = [
    ('自由城经济研究所', 'Freetown Economics Institute'),
    ('维瑞迪亚国立大学', 'Veridia National University'),
    ('埃莱纳森林', 'Elenar Forest'), ('格勒博山脉', 'Gelebor mountains'),
    ('大梅港', 'Greater Plum Harbor'),
    ('北极帝国', 'Arctic Empire'), ('北极皇帝', 'Arctic Emperor'),
    ('北极恐慌', 'Arctic scare'), ('北极人', 'Arctics'),
    ('联合城市', 'United Cities'), ('维瑞迪亚人', 'Veridian'),
    ('直升机球', 'Helisport'),
    ('帕福盖杜', 'Pafogai Du'), ('萨祖杜', 'Sadzu Du'), ('玻璃冠', 'Glasscrown'),
    ('德普勒克西', 'Deplexi'), ('彼得斯维尔', 'Petersvil'), ('德文维尔', 'Devanvil'),
    ('英格尔沃', 'Inglewore'), ('梅萨利亚', 'Messalia'), ('多利纳尔', 'Dolinar'),
    ('特尔罗伊', 'Telroy'), ('特尔滕', 'Telten'), ('特尔波', 'Telpo'),
    ('泽戈人', 'Dzegojan'), ('泽戈语', 'Dzegoban'),
    ('民本台', 'Minpentai'), ('班孙培', 'Bansunpei'), ('昆高培', 'Kungaupei'),
    ('海德菲尔', 'Hydrafill'), ('银聊', 'Silverchat'), ('蓝鲸', 'Bluewhale'),
    ('死结', 'Dreadknot'), ('银滩', 'Silverbeach'),
    ('贝帕基', 'Belpaki'), ('翁达克', 'Ondak'), ('伊普塔克', 'Iptak'), ('曼塔克', 'Mantak'),
    ('哈普顿', 'Hapton'), ('阿图里亚', 'Arturia'), ('马布里', 'Mabuli'),
    ('埃尔迪尔', 'Eldil'), ('撒尔杜', 'Thaldur'),
    ('维瑞迪亚', 'Veridia'), ('梅尔丹', 'Meldan'), ('卡利马尔', 'Kalimar'),
    ('自由城', 'Freetown'), ('红郡', 'Redshire'),
    ('北谷', 'Northglade'), ('北岸', 'Northshore'), ('泽戈', 'Dzego'),
    ('格拉迪亚斯', 'Gladias'), ('埃菲里昂勋爵', 'Lord Ephelion'), ('德尔瓦特', 'Delwart'),
    ('维尔朵', 'Verdow'), ('莱克托比', 'Lectoby'), ('塞维尔特', 'Sewlert'),
    ('阿拉盖尔', 'Alagael'), ('埃维洛尔', 'Evelor'), ('乌塔库', 'Utaku'),
    ('塔芬德尔', 'Tafindel'), ('瓦卡里亚', 'Vakaria'), ('加洛瓦', 'Gallowar'),
    ('莱克托', 'Lektor'), ('费布里克', 'Febric'), ('赫蕾达', 'Hreda'),
    ('塞拉', 'Seila'), ('兹文', 'Zven'), ('莫格纳', 'Mogna'), ('翡翠', 'Emerald'),
    ('德鲁因', 'Deluin'), ('叙尔卡', 'Sylka'), ('安库斯', 'Ancus'), ('帕普利', 'Papli'),
    ('贝尔戈', 'Belgor'), ('凯隆', 'Caeron'), ('泽文', 'Zevin'), ('佩莱', 'Pelae'),
    ('莫夫', 'Mov'), ('莉莉', 'Lily'), ('达娅', 'Daia'),
    ('毫滴答', 'milli-tick'), ('滴答', 'tick'), ('光尺', 'lightfoot'), ('泽币', 'zipcoins'),
    ('长时', 'longhour'), ('北极', 'Arctic'),
]
BARE.sort(key=lambda kv: -len(kv[0]))
NO_BARE = {'长时', '泽伊', '白', '芬', '穆', '苏', '登', '敏', '扬', '维尔',
           '波·祖墨', '贡·才白', '考·赛扎', '潘·蒙宝', '扎·京戈', '监考人金'}

# 只用于“括注该不该翻转”的判定：中文括注 -> 英文专名
GLOSS_NAMES = {
    '泽伊': 'Zei', '白': 'Bai', '芬': 'Fin', '穆': 'Mu', '苏': 'Su', '登': 'Den',
    '敏': 'Min', '扬': 'Jahn', '维尔': 'Vil', '泽戈人': 'Dzegojan',
    '波·祖墨': 'Bo Zume', '贡·才白': 'Gun Caibai', '考·赛扎': 'Kau Seiza',
    '潘·蒙宝': 'Pan Munbau', '扎·京戈': 'Dza Dzingo', '监考人金': 'Taskmaster Jin',
    '北极人': 'Arctics', '维瑞迪亚人': 'Veridian',
    '阿图里亚': 'Arturia', '哈普顿': 'Hapton', '因伯': 'Imber',
}
PROPER_ZH = dict(BARE)
PROPER_ZH.update(GLOSS_NAMES)

G_EN_ZH = re.compile(r'([A-Za-z][A-Za-z0-9 .,\'\-·]{0,60}?)（([^）\n（]{1,48})）')
_ALT = '|'.join(re.escape(k) for k in sorted(PROPER_ZH, key=len, reverse=True))
G_ZH_EN = re.compile(r'(' + _ALT + r')（([A-Za-z][A-Za-z0-9 .,\'\-·]{0,60}?)）')
TOKEN = re.compile(r'(<svg\b.*?</svg>|<div class="dateline\b.*?</div>|<[^>]+>)', re.S)


def convert(txt, stats):
    hold = []

    def stash_en_zh(m):
        a, b = m.group(1).strip(), m.group(2).strip()
        if PROPER_ZH.get(b) == a:            # 已知专名：英文在前，翻转后形式不变
            hold.append('%s（%s）' % (a, b))
        else:                                # 机制词 / 造语释义：原样保留
            hold.append(m.group(0))
        return '\x01%d\x02' % (len(hold) - 1)

    def stash_zh_en(m):
        zh, en = m.group(1), m.group(2).strip()
        hold.append('%s（%s）' % (en, zh))    # 专名：一律英文在前
        return '\x01%d\x02' % (len(hold) - 1)

    txt = G_EN_ZH.sub(stash_en_zh, txt)
    txt = G_ZH_EN.sub(stash_zh_en, txt)

    for zh, en in BARE:
        if zh in NO_BARE or zh not in txt:
            continue
        stats[zh] = stats.get(zh, 0) + txt.count(zh)
        txt = txt.replace(zh, en)
    n = len(re.findall(r'长时(?!间)', txt))
    if n:
        stats['长时'] = stats.get('长时', 0) + n
        txt = re.sub(r'长时(?!间)', 'longhour', txt)

    txt = re.sub('\x01(\\d+)\x02', lambda m: hold[int(m.group(1))], txt)
    txt = re.sub(r'(?<=[A-Za-z0-9%])(?=[一-鿿])', ' ', txt)
    txt = re.sub(r'(?<=[一-鿿])(?=[A-Za-z0-9])', ' ', txt)
    return re.sub(r' {2,}', ' ', txt)


def run(path, dry_run=False):
    """对单个文件跑一遍，返回 {中文专名: 改动次数}。dry_run=True 时只统计不写回。"""
    src = open(path, encoding='utf-8').read()
    stats = {}
    out = ''.join(p if p.startswith('<') else convert(p, stats) for p in TOKEN.split(src))
    if not dry_run:
        open(path, 'w', encoding='utf-8').write(out)
    return stats


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog='js_norm.py',
        description='把正文里写成中文的专名改回英文原词（章内首见保留中文括注）。',
        epilog='默认就地改写文件；批量跑之前先加 --dry-run 看一眼，并确保有 git 兜底。')
    ap.add_argument('paths', nargs='+', help='要处理的 HTML 文件')
    ap.add_argument('-n', '--dry-run', action='store_true', help='只报告，不写回文件')
    ap.add_argument('-q', '--quiet', action='store_true', help='不逐文件打印，只给总数')
    args = ap.parse_args(argv)

    total = 0
    for p in args.paths:
        s = run(p, dry_run=args.dry_run)
        total += sum(s.values())
        if args.quiet:
            continue
        top = sorted(s.items(), key=lambda kv: -kv[1])
        print(os.path.basename(p), '| 改动', sum(s.values()), '|',
              ', '.join('%s×%d' % (k, v) for k, v in top))

    if args.dry_run:
        print('（--dry-run：未写回任何文件）')
    print('共 %d 处改动 / %d 个文件' % (total, len(args.paths)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
