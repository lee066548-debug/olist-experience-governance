# -*- coding: utf-8 -*-
import json, os
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.section import WD_SECTION
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

import os
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.environ.get('OLIST_OUT_DIR', ROOT)
M = json.load(open(os.path.join(OUT, 'metrics.json'), encoding='utf-8'))

NAVY = RGBColor(0x1F, 0x38, 0x64)
DARK = RGBColor(0x26, 0x26, 0x26)
GREY = RGBColor(0x7F, 0x7F, 0x7F)
ACCENT = RGBColor(0xC0, 0x39, 0x2B)
CN = '微软雅黑'

def pct(x, d=1): return ('%.' + str(d) + 'f%%') % (x * 100)
def num(x): return '{:,}'.format(int(x))

# ------------------------------------------------------------------ helpers
def set_run(run, size=10.5, bold=False, color=DARK, name=CN, italic=False):
    run.font.name = name
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts'); rPr.append(rFonts)
    rFonts.set(qn('w:eastAsia'), name)
    return run

def shade(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear'); shd.set(qn('w:color'), 'auto'); shd.set(qn('w:fill'), hexcolor)
    tcPr.append(shd)

def table_borders(table, color='D9D9D9', sz=4):
    tbl = table._tbl
    tblPr = tbl.tblPr
    borders = OxmlElement('w:tblBorders')
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        e = OxmlElement('w:' + edge)
        e.set(qn('w:val'), 'single'); e.set(qn('w:sz'), str(sz))
        e.set(qn('w:space'), '0'); e.set(qn('w:color'), color)
        borders.append(e)
    tblPr.append(borders)

def cell_margins(table, top=60, bottom=60, left=100, right=100):
    tblPr = table._tbl.tblPr
    mar = OxmlElement('w:tblCellMar')
    for k, v in (('top', top), ('left', left), ('bottom', bottom), ('right', right)):
        e = OxmlElement('w:' + k); e.set(qn('w:w'), str(v)); e.set(qn('w:type'), 'dxa'); mar.append(e)
    tblPr.append(mar)

def caption(doc, text, space_before=4):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(10)
    set_run(p.add_run(text), 9, False, GREY)

def body(doc, text, first_indent=True, size=10.5, space_after=8):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    pf = p.paragraph_format
    pf.line_spacing = 1.55
    pf.space_after = Pt(space_after)
    if first_indent:
        pf.first_line_indent = Pt(size * 2)
    set_run(p.add_run(text), size, False, DARK)
    return p

def bullet(doc, lead, rest='', size=10.5):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.left_indent = Cm(0.55); pf.first_line_indent = Cm(-0.55)
    pf.line_spacing = 1.5; pf.space_after = Pt(5)
    set_run(p.add_run('•  '), size, True, NAVY)
    if lead:
        set_run(p.add_run(lead), size, True, DARK)
    if rest:
        set_run(p.add_run(rest), size, False, DARK)
    return p

def h1(doc, text):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(18); pf.space_after = Pt(8); pf.keep_with_next = True
    set_run(p.add_run(text), 15, True, NAVY)
    # bottom rule
    pPr = p._p.get_or_add_pPr()
    pbdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single'); bottom.set(qn('w:sz'), '8')
    bottom.set(qn('w:space'), '4'); bottom.set(qn('w:color'), '1F3864')
    pbdr.append(bottom); pPr.append(pbdr)
    return p

def h2(doc, text):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(12); pf.space_after = Pt(5); pf.keep_with_next = True
    set_run(p.add_run(text), 11.5, True, RGBColor(0x2F, 0x54, 0x96))
    return p

def add_table(doc, headers, rows, widths, font_size=9, align=None, header_bg='1F3864'):
    t = doc.add_table(rows=1, cols=len(headers))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    table_borders(t)
    cell_margins(t)
    hdr = t.rows[0]
    for i, htxt in enumerate(headers):
        c = hdr.cells[i]
        c.width = Cm(widths[i])
        shade(c, header_bg)
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(2)
        set_run(p.add_run(htxt), font_size, True, RGBColor(0xFF, 0xFF, 0xFF))
    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        for i, val in enumerate(row):
            c = cells[i]
            c.width = Cm(widths[i])
            if ri % 2 == 1:
                shade(c, 'F4F6FA')
            p = c.paragraphs[0]
            p.paragraph_format.space_after = Pt(2)
            p.alignment = (align[i] if align else (WD_ALIGN_PARAGRAPH.LEFT if i == 0 else WD_ALIGN_PARAGRAPH.CENTER))
            set_run(p.add_run(str(val)), font_size, False, DARK)
    return t

def add_figure(doc, path, width_cm=16.2, cap=''):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(2)
    p.add_run().add_picture(path, width=Cm(width_cm))
    if cap:
        caption(doc, cap, 2)

def code_block(doc, text, size=8.5):
    for line in text.split('\n'):
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.left_indent = Cm(0.6); pf.space_before = Pt(0); pf.space_after = Pt(0)
        pf.line_spacing = 1.0
        set_run(p.add_run(line if line.strip() else ' '), size, False, RGBColor(0x22, 0x22, 0x22), 'Consolas')
    doc.paragraphs[-1].paragraph_format.space_after = Pt(8)

def add_footer(section):
    footer = section.footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_run(p.add_run('第 '), 8.5, False, GREY)
    fld = OxmlElement('w:fldSimple'); fld.set(qn('w:instr'), 'PAGE')
    r = OxmlElement('w:r'); t = OxmlElement('w:t'); t.text = '1'; r.append(t); fld.append(r)
    p._p.append(fld)
    set_run(p.add_run(' 页 / 共 '), 8.5, False, GREY)
    fld2 = OxmlElement('w:fldSimple'); fld2.set(qn('w:instr'), 'NUMPAGES')
    r2 = OxmlElement('w:r'); t2 = OxmlElement('w:t'); t2.text = '1'; r2.append(t2); fld2.append(r2)
    p._p.append(fld2)
    set_run(p.add_run(' 页'), 8.5, False, GREY)

def add_header(section, text):
    p = section.header.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    set_run(p.add_run(text), 8.5, False, GREY)

# ------------------------------------------------------------------ document
doc = Document()
section = doc.sections[0]
section.page_width = Cm(21.0); section.page_height = Cm(29.7)
section.top_margin = Cm(2.0); section.bottom_margin = Cm(1.9)
section.left_margin = Cm(2.1); section.right_margin = Cm(2.1)

st = doc.styles['Normal']
st.font.name = CN; st.font.size = Pt(10.5)
st.element.rPr.rFonts.set(qn('w:eastAsia'), CN)

add_header(section, 'Olist 电商体验治理｜差评归因与履约干预（V2）')
add_footer(section)

# ---- title block
p = doc.add_paragraph(); p.paragraph_format.space_before = Pt(6); p.paragraph_format.space_after = Pt(4)
set_run(p.add_run('Olist 电商体验治理'), 24, True, NAVY)
p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(10)
set_run(p.add_run('差评归因与履约干预'), 15, True, RGBColor(0x2F, 0x54, 0x96))
p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(2)
set_run(p.add_run('巴西电商平台｜2016-09 至 2018-10｜99,441 笔订单｜9 张表 1,550,922 行'), 9.5, False, GREY)
p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(14)
set_run(p.add_run('李志豪｜2026 年 11 月｜在线看板：public.tableau.com/app/profile/43153393'), 9.5, False, GREY)

# ---- V2 note box
t = doc.add_table(rows=1, cols=1); t.autofit = False
table_borders(t, 'D6DCE8', 6); cell_margins(t, 90, 90, 140, 140)
c = t.rows[0].cells[0]; c.width = Cm(16.6); shade(c, 'F2F5FB')
p = c.paragraphs[0]; p.paragraph_format.space_after = Pt(3)
set_run(p.add_run('V2 数据口径修订版'), 9.5, True, NAVY)
p = c.add_paragraph(); p.paragraph_format.space_after = Pt(0); p.paragraph_format.line_spacing = 1.35
set_run(p.add_run('本版所有数字由 compute_all.py 从 9 张原始表重算，报告、SQL、看板使用同一口径。相对 V1 修正：'
                  '① 延迟分档统一为三档（4.29 / 3.29 / 1.86，与看板一致）；② SP、RJ 送达率改为 97.0% / 96.1%；'
                  '③ 新增控制变量、评论文本归因与承诺时效分析。看板与报告口径已对齐，附录 B 为可选增强。'), 8.8, False, DARK)

# ---- 核心结论
h1(doc, '核心结论')
concl = [
    ('5% 的订单贡献 28% 的差评。',
     '延迟 4 天以上的订单占 4.8%，却贡献 27.7% 的差评；延迟超过 1 天的 6.8% 订单贡献 32.5%。'
     + '迟到订单差评率 ' + pct(M['bad_rate_late']) + '，是准时订单（' + pct(M['bad_rate_ontime'])
     + '）的 6.8 倍；差评的可归因比例（PAF）为 27.6%。'),
    ('控制卖家与品类后，结论没有衰减。',
     '同卖家对比（54 个卖家同时有 ≥20 单迟到与 ≥20 单准时）：54/54 迟到单更差，平均高 53.2 个百分点；'
     '同品类对比（29 个品类）：29/29 更差，平均高 51.7 个百分点。单变量差 53.1pp，控制后几乎不变。'),
    ('但延迟只能解释约三成差评。',
     '10,890 条带文本差评中，物流类占 43.3%、商品类占 24.0%、客服/退款占 8.2%，另有 24.5% 没有写具体原因；'
     '59% 的带文本差评来自仍在承诺期内送达的订单。'),
    ('RJ 的问题是“慢”，不是“送不到”。',
     'RJ 送达率 96.1%（SP 97.0%），但迟到率 12.1%（SP 4.5%）、平均履约 15.3 天（SP 8.8 天）；'
     '差评率 18.3% vs 10.6%，其中 4.6pp（60%）可由迟到率差异解释。'),
    ('承诺缓冲 11.2 天，是最便宜的杠杆。',
     '平均承诺 23.7 天、实际履约 12.6 天；20–25 天窗口迟到率最高（8.1%），>40 天仅 2.3%。'
     '治理动作应从“催物流”扩展到“校准承诺”。'),
    ('不要把这件事讲成留存故事。',
     '首单迟到客户复购率 3.45%，准时客户 3.17%（n=6,405 / 86,951），未检测到负向影响；'
     '延迟的代价主要体现在评分与搜索权重，而不是复购。'),
]
for lead, rest in concl:
    bullet(doc, lead, rest)

# ---- 一、数据与口径
h1(doc, '一、数据与口径')
body(doc, '数据源为 Kaggle 公开数据集《Brazilian E-Commerce Public Dataset by Olist》，9 张表共 1,550,922 行，'
          '覆盖 2016-09 至 2018-10 的 99,441 笔订单。分析在订单粒度进行：商品明细与评价先各自聚合为“一单一行”，'
          '再与订单、客户、商品、卖家、品类翻译关联，得到 99,441 行 × 27 列的宽表 wide_orders，'
          '避免一对多 join 造成的行数膨胀。')
body(doc, '口径先于结论。下表是本报告用到的全部定义；三处最容易出错的地方是：分母（差评率只除以有评价订单）、'
          '延迟阈值（>1 天还是 >0 天）、以及“有评价”不是漏斗环节。')
caption(doc, '表 1  指标定义与取值', 8)
add_table(doc, ['指标', '定义', '取值'], [
    ['有效订单', "order_status = 'delivered'", '96,478 单（97.02%）'],
    ['差评 / 差评率', '评分 1–2 星；分母为有评价订单', '12.76%（仅送达）/ 14.69%（全部订单）'],
    ['延迟（>1 天）', '签收晚于承诺送达 1 天以上', '6,534 单（6.77%）'],
    ['延迟（>0 天）', '宽表 is_late 字段口径，晚于承诺即算', '7,826 单（8.11%）'],
    ['履约时长', '签收 − 下单', '12.56 天'],
    ['发货时效', '交承运商 − 下单', '3.23 天'],
    ['承诺窗口 / 缓冲', '承诺送达 − 下单 / 窗口 − 履约', '23.74 天 / 11.18 天'],
    ['GMV', '商品金额（不含运费）', 'R$ 13.59M（含运费 15.84M）'],
    ['平均评分', '全部评价 / 仅送达订单', '4.09 / 4.16'],
], [3.4, 7.6, 5.6], 9)
body(doc, '两个平均评分都“对”，但必须标注总体：4.09 是全部 99,224 条评价，4.16 是仅送达订单。'
          '同样，6.77% 与 8.11% 是同一条延迟的两种阈值，不能混用；V2 全文统一使用“>1 天”并在 SQL 中显式命名为 is_late_1d。', space_after=6)

# ---- 二、履约大盘
h1(doc, '二、履约大盘：97% 送达，断点在时效')
body(doc, '漏斗各环节转化率都在 97% 以上，说明“送不送得到”不是主要矛盾。真正的问题在“送得准不准”。')
caption(doc, '表 2  订单履约漏斗', 8)
add_table(doc, ['阶段', '订单数', '占下单'], [
    ['下单', num(M['total_orders']), '—'],
    ['支付通过', num(M['approved']), pct(M['approved_rate'], 2)],
    ['交承运商', num(M['carrier']), pct(M['carrier'] / M['total_orders'], 2)],
    ['签收', num(M['delivered']), pct(M['delivery_rate'], 2)],
], [6.0, 5.0, 5.0], 9)
body(doc, '注：有评价的订单为 98,673 单（99.23%），但其中包含未送达订单，因此它不是漏斗的下一环节，不应画在签收之后。', space_after=6)
add_figure(doc, os.path.join(OUT, 'chart_monthly.png'), 16.2, '图 1  月度订单量与送达率（2017-01 至 2018-08）')
body(doc, '订单量从 2017-01 的 800 单增长到 2017-11 的 7,544 单（黑五），同期送达率 96.6%，大促没有击穿运力；'
          '最低点是 2017-02 的 92.9%，此后逐月改善，2018 年稳定在 97% 以上。'
          '需要注意的是，V1 报告用“已处理订单”口径把 2017-02 写成 96.4%，与大盘 97.0% 的口径不一致，V2 已统一为“送达 / 全部订单”。')

# ---- 三、延迟阶梯
h1(doc, '三、差评归因（一）：延迟阶梯')
body(doc, '按延迟程度切分，差评率不是线性上升：从准时到延迟 1–4 天，由 9.2% 升到 32.1%（3.5 倍）；'
          '延迟 4 天以上再升到 74.7%（2.3 倍）。因此“容忍阈值”在 1 天：跨过 1 天，差评率直接跳到三倍以上；'
          '到 4 天以上，差评几乎是必然。这一分档与看板一致（<1 天 / 1–4 天 / ≥4 天）。')
add_figure(doc, os.path.join(OUT, 'chart_ladder.png'), 16.2, '图 2  差评率与平均评分随延迟程度的变化')
caption(doc, '表 3  延迟分档与差评率', 8)
rows = [[r['bucket'], num(r['orders']), pct(r['share']), '%.2f' % r['avg_score'], pct(r['bad_rate'])] for r in M['ladder']]
rows.append(['迟到合计（>1 天）', num(M['late_n']), '—', '%.2f' % M['avg_score_late'], pct(M['bad_rate_late'])])
add_table(doc, ['延迟分档', '订单数', '占比', '平均评分', '差评率'], rows, [4.6, 3.0, 2.6, 2.8, 3.0], 9)
body(doc, '三档平均评分为 4.29 / 3.29 / 1.86，严重延迟比准时低 2.43 分'
          '（看板标注 2.42 分，为四舍五入差异）；三档数据可与看板逐项核对，不再混用四档。')
body(doc, '把差评拆开看：全部 12,225 条差评中，3,976 条（32.5%）来自延迟超过 1 天的订单；'
          '延迟 4 天以上的 4.8% 订单贡献了 27.7% 的差评；可归因比例（PAF）为 27.6%。'
          '这足以证明延迟是“最可控的单一杠杆”，但不足以支撑“6.8% 的订单解释了大部分差评”这种说法——'
          '延迟之外还有约 70% 的差评需要别的解释。')

# ---- 四、控制变量
h1(doc, '四、差评归因（二）：控制卖家与品类')
body(doc, '双变量比较会被混杂因素污染：迟到订单可能集中在某些卖家、某些品类或某些州。'
          '为此做两个“同层比较”：在同一卖家内、同一品类内，比较迟到与准时订单的差评率。')
caption(doc, '表 4  控制变量后的延迟效应', 8)
add_table(doc, ['检验', '样本', '差评率差异', '方向一致性'], [
    ['单变量（未控制）', '96,470 单', '+53.1pp', '—'],
    ['同卖家', '54 个卖家（各 ≥20 单迟到 + ≥20 单准时）', '+53.2pp', '54/54 迟到更差'],
    ['同品类', '29 个品类（各 ≥30 单）', '+51.7pp', '29/29 迟到更差'],
], [4.2, 8.2, 3.4, 4.2], 9)
body(doc, '控制后效应几乎不衰减（53.1 → 53.2 / 51.7pp），说明结论不是由卖家结构或品类结构造成的。'
          '这仍然不是随机实验：迟到订单可能在“距离、承运商、下单时段”等未观测维度上不同，'
          '但已经排除了最主要的两个混杂来源，比单纯的双变量图可信得多。')
body(doc, '地区差异也可以用同样方法拆开。SP 与 RJ 的差评率差 7.6pp，把 RJ 的迟到率替换成 SP 的迟到率后，'
          'RJ 差评率会从 18.3% 降到 13.7%：4.6pp（60%）来自迟到率差异，3.0pp 来自“同样迟到/准时下 RJ 仍然更差”。'
          '这意味着 RJ 的治理重点是时效，而不是送达率。')

# ---- 五、文本
h1(doc, '五、差评归因（三）：评论文本')
body(doc, 'V1 把“评价只有星级、没有文本”写进了局限——这是一个事实错误：99,224 条评价里有 40,977 条带正文（41.3%），'
          '其中差评 10,890 条。把葡萄牙语文本做关键词规则打标（去重音、按优先级匹配），可以在半小时内得到一张可解释的归因表，'
          '直接回答“延迟之外那 70% 的差评是什么”。')
add_figure(doc, os.path.join(OUT, 'chart_topic.png'), 16.2, '图 3  差评文本主题分布（n=10,890）')
caption(doc, '表 5  差评主题与延迟的关系', 8)
rows = [[r['topic'], num(r['n']), pct(r['share']), pct(next(x['late_share'] for x in M['text_by_late'] if x['topic'] == r['topic']))] for r in M['text']['topics']]
add_table(doc, ['主题', '条数', '占比', '其中迟到订单占比'], rows, [5.4, 3.2, 3.2, 4.6], 9)
body(doc, '三个可以直接用于业务的读数：第一，物流类合计 43.3%，是最大的一块，但其中“没收到”占 30.4%，'
          '说明问题更多是“未送达/丢件”而不是“慢”；这类差评里 44% 的订单确实晚于承诺，35% 仍在承诺期内——'
          '顾客在承诺到期前就已经开始投诉。第二，商品类合计 24.0%（质量 11.2%、描述不符 7.3%、错发缺件 5.5%），'
          '与物流无关，需要商家侧治理。第三，24.5% 的差评没有任何具体原因，这是文本分析的真实上限，不要过度解读。')
body(doc, '方法说明：规则打标可解释、可复现，适合作为第一版；生产环境应升级为 TF-IDF + 聚类（或 LLM 打标）并人工抽检，'
          '本报告在附录 C 给出了可直接运行的 Python 版本。')

# ---- 六、地区
h1(doc, '六、地区：RJ 是“慢”，不是“送不到”')
add_figure(doc, os.path.join(OUT, 'chart_state.png'), 16.2, '图 4  SP / RJ / MG / RS / PR / SC 的迟到率与差评率')
caption(doc, '表 6  重点州履约与体验', 8)
rows = []
for s in M['states']:
    if s['state'] in ('SP', 'RJ', 'MG', 'RS', 'PR', 'SC', 'BA', 'CE'):
        rows.append([s['state'], num(s['orders']), pct(s['delivery_rate']), pct(s['late_rate']),
                     pct(s['bad_rate']), '%.1f' % s['fulfill']])
add_table(doc, ['州', '订单数', '送达率', '迟到率', '差评率', '履约天数'], rows, [2.2, 3.0, 3.0, 3.0, 3.0, 2.8], 9)
body(doc, 'SP 与 RJ 合计 54.9% 的订单，是量的重心。V1 写“SP 送达率 97.6%、RJ 94.7%”，'
          '两个数都无法从原始数据复现：实际是 SP 97.0%、RJ 96.1%，RJ 的送达率与平台均值（96.5%）基本持平。'
          '真正的差距在时效：RJ 迟到率 12.1%（SP 4.5%）、履约 15.3 天（SP 8.8 天）。把治理目标写成“把 RJ 送达率提到 SP 水平”是在修一个不存在的问题，'
          '正确目标是“把 RJ 迟到率从 12.1% 压到 5% 左右”。')

# ---- 七、承诺
h1(doc, '七、承诺时效：被忽略的杠杆')
add_figure(doc, os.path.join(OUT, 'chart_promise.png'), 16.2, '图 5  承诺窗口与迟到率')
body(doc, '平台平均给出 23.7 天的承诺，实际只用 12.6 天，缓冲 11.2 天。缓冲越大，“准时率”越好看，但它同时意味着：'
          '顾客要等很久才下单、且一旦超过承诺就是严重失望。分档看，20–25 天窗口的迟到率最高（8.1%），>40 天最低（2.3%）——'
          '这不是“越长越好”，而是承诺与实际能力错配的区间最危险。')
body(doc, '这条洞察价值在于：调整承诺（按州、按品类、按卖家历史时效动态给窗口）比压承运商便宜得多，而且可以立刻做。'
          '需要注意，窗口与品类、路线高度相关，这里是描述性证据，不能直接读成因果；要证明收益，需要做承诺窗口的 A/B。')

# ---- 八、卖家与品类
h1(doc, '八、卖家与品类：治理对象可以收敛到很小的名单')
body(doc, '品类与卖家是“可执行”的治理对象。品类差评率最高的是办公家具 21.8%（n=1,248）与音频 21.4%（n=345），'
          '而单量最大的床品家纺差评率 15.6%（n=9,153）——高单量品类每改善 1 个百分点，收益远大于小品类。')
caption(doc, '表 7  品类差评率（n ≥ 200，按订单量排序）', 8)
rows = [[c['cat'], num(c['orders']), pct(c['bad_rate']), pct(c['late_rate']), '%.2f' % c['avg_score']] for c in M['category_big']]
add_table(doc, ['品类', '订单数', '差评率', '迟到率', '平均评分'], rows, [6.2, 3.2, 3.0, 3.0, 2.8], 8.5)
body(doc, '卖家侧：2,958 个卖家中，205 个订单 ≥100；同时满足“≥200 单且差评率 ≥20%”的只有 6 家，合计 2,420 单（2.5%）。'
          '这意味着卖家治理可以收敛到一张很短的名单，而不是“全平台整改”。V1 的 SQL 里已经有这个四象限查询，但报告和看板都没有用上——'
          'V2 把它作为治理清单的一部分（附录 B 给了对应的看板图）。')

# ---- 九、治理与实验
h1(doc, '九、治理动作与实验设计')
bullet(doc, '短期（1 个月）：', 'RJ 时效专项（迟到率 12.1% → 7%）；对 20–25 天窗口的订单重设承诺；6 家 A 类卖家限期整改。')
bullet(doc, '中期（1 个季度）：', '延迟预警 + 主动补偿；商品侧治理（办公家具、音频、床品家纺的描述与包装）；把评论主题纳入周报。')
bullet(doc, '长期（半年）：', '承诺时效的动态定价（按州/品类/卖家给窗口）；把“差评主题”接到商家评分体系。')
body(doc, '实验设计沿用 V1 的分层随机思路，但修正两个问题：一是基线不能用“平台差评率 20%”，'
          '而要用“被预测为高风险人群”的差评率（迟到 ≥4 天人群实际是 74.7%）；二是要算可行性——'
          '若按 4.8% 的命中率，每组 3,800 单需要约 15.8 万订单，按 2018 年月均 6,500 单计算约 24 个月，'
          '超过数据窗口。可行的做法是把干预人群从“已经迟到 4 天”改成“下单时预测迟到概率高”的 10%–15%，'
          '或采用分州灰度 + 双重差分（DID）做准实验。')
caption(doc, '表 8  A/B 设计要点', 8)
add_table(doc, ['要素', '设计'], [
    ['分流', '按州（RJ / 非 RJ）× 品类分层，随机 50/50'],
    ['样本量', '基线差评率 45%（预测高风险人群），MDE 相对 15%，α=0.05、power=0.8，约 3,600 / 组（含 15% 缓冲取 4,200）'],
    ['主指标', '差评率（1–2 星 / 有评价订单）'],
    ['护栏指标', 'GMV、退款率、客服工单量、补偿成本占订单金额比'],
    ['判定', '双周读出；主指标显著改善且护栏指标不劣化才全量'],
], [3.2, 12.8], 9)

# ---- 十、局限
h1(doc, '十、局限')
for txt in [
    '观察性数据：控制卖家与品类后仍非随机，距离、承运商、下单时段等未观测因素可能残余混杂。',
    '评论为葡萄牙语短文本，规则打标存在误判；24.5% 的差评没有具体原因，文本归因只能覆盖约四分之三的差评。',
    '缺少退货、客服工单、曝光/流量数据，无法计算延迟对搜索权重与客户终身价值的影响。',
    '同一订单多条评价时取最高分（涉及 547 单），会轻微低估不满；经检验对差评率影响仅 0.1pp（14.63% vs 14.73%），不是主要误差来源。',
    '单平台、单市场（巴西 2016–2018），结论迁移到其他市场需重新验证。',
]:
    bullet(doc, '', txt)

# ---- 附录 A
doc.add_page_break()
h1(doc, '附录 A  口径与数字对照（V1 → V2）')
body(doc, '下表解释“为什么报告、看板、CSV 会出现不同的数”。V2 的原则是：一个指标只有一个口径，所有交付物从同一份指标表生成。')
caption(doc, '表 A1  主要数字的修订', 8)
add_table(doc, ['指标', 'V1 / 看板', 'V2 重算', '说明'], [
    ['延迟分档评分', '4.29 / 3.29 / 1.86（3 档）', '4.29 / 3.29 / 1.86（3 档）', '与看板一致；不再混用四档'],
    ['SP 送达率', '97.6%', '97.0%', '40,501 / 41,746'],
    ['RJ 送达率', '94.7%', '96.1%', '12,350 / 12,852'],
    ['RJ 差评率', '18.3%', '18.3%', '2,230 / 12,211，一致'],
    ['延迟率', '6.8%', '6.8%（>1 天）/ 8.1%（>0 天）', '仓库 is_late 字段是 >0 天，需改名为 is_late_1d'],
    ['延迟评分差', '2.42（4.29 vs 1.86）', '2.43（4.29 − 1.86）', '看板 2.42 为四舍五入差异'],
    ['GMV', '13.6M / 15.84M', '13.59M（商品）/ 15.84M（含运费）', '两个数都对，必须标注是否含运费'],
    ['有评价订单', '98,673（画在漏斗末尾）', '98,673（不作为漏斗环节）', '含未送达订单，后续环节不能小于前序'],
], [2.8, 4.3, 4.9, 4.4], 8.2)

# ---- 附录 B
h1(doc, '附录 B  看板同步修改清单（Tableau）')
body(doc, '看板与报告的分档已经一致（<1 天 / 1–4 天 / ≥4 天），不需要再改计算字段。以下四项是可选的增强：')
for i, txt in enumerate([
    '新增 3 张图：差评率×延迟（柱状，替代只有平均分的图）、差评文本主题（横向柱）、RJ/SP 对比（迟到率+差评率）。对应 SQL 见 sql/03 与 sql/04。',
    '删除两个没接线的参数（参数 1 = 200、参数 2 = 0.2），它们原本是给卖家四象限准备的；若要保留，就把卖家象限图补上。',
    '修 insight 文案：SP 不是短板（差评率 10.6%，低于均值）；“漏斗斗”是错别字；标题统一为《Olist 电商体验治理｜差评归因与履约干预》。',
    '把“迟到率”统一改为 >1 天口径，并在 KPI 卡片备注“迟到 = 晚于承诺 1 天以上”。',
], 1):
    bullet(doc, '', txt)

# ---- 附录 C
h1(doc, '附录 C  复现与代码')
body(doc, '三个脚本按顺序运行即可复现全部数字与图：compute_all.py（宽表指标）→ addendum.py（文本归因）→ make_charts.py（图）。'
          '文本归因的核心代码如下，可直接改用 TF-IDF + 聚类：')
code_block(doc, r'''def norm(s):
    s = unicodedata.normalize("NFKD", str(s).lower()).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z\s]", " ", s)).strip()

TOPICS = [("未收到", ["nao recebi", "nao chegou", "extravio"]),
          ("延迟",   ["atras", "prazo", "demor", "correio"]),
          ("质量",   ["quebrad", "defeito", "qualidade", "nao funciona"]),
          ("描述不符", ["diferente", "anuncio", "foto", "tamanho"])]   # 其余见脚本

def classify(txt):
    t = norm(txt)
    for name, kws in TOPICS:
        if any(k in t for k in kws):
            return name
    return "无具体原因"''', 8.5)
body(doc, '如需升级：用 sklearn 的 TfidfVectorizer(max_features=3000) + NMF(n_components=8) 做主题，'
          '再用轮廓系数或人工抽检确定主题数；规则版可作为聚类的先验与校验集。', space_after=2)
p = doc.add_paragraph(); p.paragraph_format.space_before = Pt(16)
set_run(p.add_run('数据来源：Kaggle, Brazilian E-Commerce Public Dataset by Olist（CC BY-NC-SA 4.0）。'
                  '本文数字均由原始 9 表重算，指标定义见附录 A。'), 8.5, False, GREY)

out_docx = os.path.join(OUT, 'Olist电商体验治理分析报告_V2.docx')
doc.save(out_docx)
print('saved', out_docx)



