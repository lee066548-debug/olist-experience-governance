# -*- coding: utf-8 -*-
"""Draw the report charts with Pillow (no matplotlib available)."""
import json, os
from PIL import Image, ImageDraw, ImageFont

import os
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.environ.get('OLIST_OUT_DIR', ROOT)
M = json.load(open(os.path.join(OUT, 'metrics.json'), encoding='utf-8'))

FONT = r'C:\Windows\Fonts\msyh.ttc'
BOLD = r'C:\Windows\Fonts\msyhbd.ttc'
def F(sz, b=False): return ImageFont.truetype(BOLD if b else FONT, sz)

W, H = 1680, 940
NAVY = (31, 56, 100)
GREY = (110, 118, 128)
LGREY = (225, 228, 232)
BLUE = (47, 111, 179)
ORANGE = (230, 126, 34)
RED = (192, 57, 43)
GREEN = (39, 174, 96)
DARKRED = (142, 32, 32)

def canvas(title, subtitle=None):
    img = Image.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(img)
    d.text((70, 46), title, font=F(34, True), fill=NAVY)
    if subtitle:
        d.text((70, 96), subtitle, font=F(21), fill=GREY)
    return img, d

def source(d, text):
    d.text((70, H - 46), text, font=F(17), fill=GREY)

def yaxis(d, x0, y0, x1, y1, vmax, ticks=5, fmt='{:.0f}%'):
    for i in range(ticks + 1):
        v = vmax * i / ticks
        y = y1 - (y1 - y0) * i / ticks
        d.line([(x0, y), (x1, y)], fill=LGREY, width=1)
        d.text((x0 - 14, y), fmt.format(v), font=F(17), fill=GREY, anchor='rm')
    d.line([(x0, y0), (x0, y1)], fill=(150, 155, 162), width=2)
    d.line([(x0, y1), (x1, y1)], fill=(150, 155, 162), width=2)

def legend(d, items, x, y, gap=190):
    for i, (label, color) in enumerate(items):
        d.rectangle([x + i * gap, y + 6, x + i * gap + 20, y + 26], fill=color)
        d.text((x + i * gap + 30, y + 16), label, font=F(18), fill=(60, 60, 60), anchor='lm')

# ---------------------------------------------------------------- 1. ladder
def chart_ladder():
    img, d = canvas('差评率随延迟上升：准时 9.2%，延迟 4 天以上 74.7%',
                    '纵轴：差评率（1–2 星 / 有评价订单）；柱内小字：该档平均评分')
    x0, y0, x1, y1 = 150, 190, W - 90, H - 170
    yaxis(d, x0, y0, x1, y1, 100, 5)
    rows = M['ladder']
    colors = [GREEN, ORANGE, RED, DARKRED]
    n = len(rows); slot = (x1 - x0) / n; bw = slot * 0.52
    for i, r in enumerate(rows):
        cx = x0 + slot * (i + 0.5)
        h = (y1 - y0) * r['bad_rate'] / 1.0
        d.rectangle([cx - bw/2, y1 - h, cx + bw/2, y1], fill=colors[i])
        d.text((cx, y1 - h - 34), '%.1f%%' % (r['bad_rate']*100), font=F(26, True), fill=colors[i], anchor='mm')
        d.text((cx, y1 - h + 26), '均分 %.2f' % r['avg_score'], font=F(19), fill='white', anchor='mm')
        d.text((cx, y1 + 34), r['bucket'], font=F(20, True), fill=(50, 50, 50), anchor='ma')
        d.text((cx, y1 + 64), '{:,} 单 · {:.1f}%'.format(r['orders'], r['share']*100),
               font=F(18), fill=GREY, anchor='ma')
    source(d, '数据：Olist 9 表重算，n=96,470 已送达且有承诺时间戳的订单')
    img.save(os.path.join(OUT, 'chart_ladder.png'))

# ---------------------------------------------------------------- 2. state
def chart_state():
    img, d = canvas('RJ 的差评来自“慢”，不是“送不到”',
                    'SP / RJ / MG / RS / PR / SC 六州；送达率均约 96%–98%，差距主要在迟到率与差评率')
    x0, y0, x1, y1 = 150, 200, W - 90, H - 170
    yaxis(d, x0, y0, x1, y1, 20, 4)
    rows = [s for s in M['states'] if s['state'] in ('SP','RJ','MG','RS','PR','SC')]
    rows = sorted(rows, key=lambda s: s['orders'], reverse=True)
    n = len(rows); slot = (x1 - x0) / n; bw = slot * 0.28
    for i, s in enumerate(rows):
        cx = x0 + slot * (i + 0.5)
        for j, (key, color) in enumerate([('late_rate', BLUE), ('bad_rate', ORANGE)]):
            h = (y1 - y0) * s[key] / 0.20
            xx = cx + (j - 0.5) * bw * 1.15
            d.rectangle([xx - bw/2, y1 - h, xx + bw/2, y1], fill=color)
            d.text((xx, y1 - h - 18), '%.1f' % (s[key]*100), font=F(17, True), fill=color, anchor='mm')
        d.text((cx, y1 + 32), s['state'], font=F(21, True), fill=(50, 50, 50), anchor='ma')
        d.text((cx, y1 + 62), '送达 %.1f%%' % (s['delivery_rate']*100), font=F(16), fill=GREY, anchor='ma')
    legend(d, [('迟到率（>1 天）', BLUE), ('差评率', ORANGE)], x0 + 10, 150)
    source(d, '数据：Olist 已送达订单；迟到率分母为有承诺时间戳订单，差评率分母为有评价订单')
    img.save(os.path.join(OUT, 'chart_state.png'))

# ---------------------------------------------------------------- 3. topics
def chart_topic():
    img, d = canvas('差评文本归因：物流 43%，商品 24%，四分之一没写原因',
                    '横轴：占 %s 条带文本差评的比例；浅色条为“该主题中迟到订单占比”' % '{:,}'.format(M['text']['bad_reviews_with_text']))
    rows = sorted(M['text']['topics'], key=lambda r: r['n'], reverse=True)
    late = {r['topic']: r['late_share'] for r in M['text_by_late']}
    x0, y0, x1, y1 = 330, 190, W - 120, H - 150
    n = len(rows); slot = (y1 - y0) / n; bh = slot * 0.30
    for i in range(6):
        v = 0.50 * i / 5
        x = x0 + (x1 - x0) * i / 5
        d.line([(x, y0), (x, y1)], fill=LGREY, width=1)
        d.text((x, y1 + 22), '%.0f%%' % (v*100), font=F(17), fill=GREY, anchor='ma')
    for i, r in enumerate(rows):
        cy = y0 + slot * (i + 0.5)
        d.text((x0 - 18, cy - 12), r['topic'], font=F(19, True), fill=(45, 45, 45), anchor='rm')
        w1 = (x1 - x0) * r['share'] / 0.50
        d.rectangle([x0, cy - bh - 3, x0 + w1, cy - 3], fill=BLUE)
        d.text((x0 + w1 + 12, cy - bh/2 - 3), '%.1f%%' % (r['share']*100), font=F(17, True), fill=BLUE, anchor='lm')
        lv = late.get(r['topic'], 0)
        w2 = (x1 - x0) * lv / 0.50
        d.rectangle([x0, cy + 3, x0 + w2, cy + 3 + bh], fill=(178, 200, 226))
        d.text((x0 + w2 + 12, cy + 3 + bh/2), '迟到占 %.0f%%' % (lv*100), font=F(15), fill=GREY, anchor='lm')
    source(d, '方法：葡萄牙语关键词规则打标（去重音、优先级匹配），可解释、可复现；生产环境建议 TF-IDF + 聚类 / LLM 复核')
    img.save(os.path.join(OUT, 'chart_topic.png'))

# ---------------------------------------------------------------- 4. promise
def chart_promise():
    img, d = canvas('承诺时效是可控杠杆：20–25 天窗口的迟到率最高（8.1%）',
                    '平均承诺 23.7 天 vs 实际履约 12.6 天，缓冲 11.2 天；窗口 >40 天时迟到率仅 2.3%')
    x0, y0, x1, y1 = 150, 200, W - 90, H - 170
    yaxis(d, x0, y0, x1, y1, 10, 5)
    rows = M['promise_window']['buckets']
    n = len(rows); slot = (x1 - x0) / n
    pts = []
    for i, r in enumerate(rows):
        cx = x0 + slot * (i + 0.5)
        h = (y1 - y0) * r['late_rate'] / 0.10
        d.rectangle([cx - slot*0.22, y1 - h, cx + slot*0.22, y1], fill=(205, 219, 235))
        d.text((cx, y1 + 32), r['bucket'], font=F(20, True), fill=(50, 50, 50), anchor='ma')
        d.text((cx, y1 + 62), '{:,} 单'.format(r['orders']), font=F(17), fill=GREY, anchor='ma')
        pts.append((cx, y1 - h))
    for i in range(len(pts) - 1):
        d.line([pts[i], pts[i+1]], fill=BLUE, width=4)
    for i, (x, y) in enumerate(pts):
        d.ellipse([x-9, y-9, x+9, y+9], fill=BLUE)
        d.text((x, y - 30), '%.1f%%' % (rows[i]['late_rate']*100), font=F(19, True), fill=BLUE, anchor='mm')
    source(d, '数据：Olist 已送达订单；承诺窗口 = 承诺送达日 − 下单日')
    img.save(os.path.join(OUT, 'chart_promise.png'))

# ---------------------------------------------------------------- 5. monthly
def chart_monthly():
    img, d = canvas('订单量持续增长，送达率同步改善（2017-01 至 2018-08）',
                    '柱：月订单量（左轴）；线：送达率（右轴），2018 年稳定在 97% 以上')
    x0, y0, x1, y1 = 150, 200, W - 130, H - 180
    rows = M['monthly']
    vmax = 8000
    for i in range(5):
        v = vmax * i / 4
        y = y1 - (y1 - y0) * i / 4
        d.line([(x0, y), (x1, y)], fill=LGREY, width=1)
        d.text((x0 - 14, y), '{:.0f}K'.format(v/1000), font=F(17), fill=GREY, anchor='rm')
    # right axis 92-100
    for i in range(5):
        v = 92 + 2 * i
        y = y1 - (y1 - y0) * (v - 92) / 8
        d.line([(x1, y), (x1 + 10, y)], fill=LGREY, width=1)
        d.text((x1 + 16, y), '%d%%' % v, font=F(16), fill=GREY, anchor='lm')
    n = len(rows); slot = (x1 - x0) / n
    for i, r in enumerate(rows):
        cx = x0 + slot * (i + 0.5)
        h = (y1 - y0) * r['orders'] / vmax
        d.rectangle([cx - slot*0.32, y1 - h, cx + slot*0.32, y1], fill=(205, 219, 235))
        if i % 3 == 0:
            d.text((cx, y1 + 30), r['month'], font=F(15), fill=GREY, anchor='ma')
    pts = []
    for i, r in enumerate(rows):
        cx = x0 + slot * (i + 0.5)
        y = y1 - (y1 - y0) * (r['delivery_rate'] - 0.92) / 0.08
        pts.append((cx, y))
    for i in range(len(pts) - 1):
        d.line([pts[i], pts[i+1]], fill=BLUE, width=4)
    for i, (x, y) in enumerate(pts):
        d.ellipse([x-6, y-6, x+6, y+6], fill=BLUE)
    source(d, '数据：Olist orders；2016 年与 2018-09 之后样本不完整，已剔除')
    img.save(os.path.join(OUT, 'chart_monthly.png'))

for fn in (chart_ladder, chart_state, chart_topic, chart_promise, chart_monthly):
    fn()
print('charts done')

