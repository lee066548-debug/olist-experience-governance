# -*- coding: utf-8 -*-
"""Build images/dashboard.png: a 2x2 preview montage of the four V2 charts."""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = r'C:\Users\李\Documents\deepseek-harness\default-workspace\olist_review'
BOLD = r'C:\Windows\Fonts\msyhbd.ttc'
FONT = r'C:\Windows\Fonts\msyh.ttc'

charts = ['chart_ladder.png', 'chart_topic.png', 'chart_state.png', 'chart_promise.png']
tile_w, tile_h = 790, 442
gap = 18
W = tile_w * 2 + gap * 3
H = 112 + tile_h * 2 + gap * 3

canvas = Image.new('RGB', (W, H), 'white')
d = ImageDraw.Draw(canvas)
d.text((40, 28), 'Olist 体验治理｜差评归因与履约干预（V2）', font=ImageFont.truetype(BOLD, 40), fill=(31, 56, 100))
d.text((40, 80), '延迟阶梯 · 文本归因 · 地区拆解 · 承诺时效　|　99,441 orders, 2016-09 ~ 2018-10',
       font=ImageFont.truetype(FONT, 21), fill=(110, 118, 128))

for i, name in enumerate(charts):
    im = Image.open(os.path.join(OUT, name)).convert('RGB').resize((tile_w, tile_h), Image.LANCZOS)
    x = gap + (i % 2) * (tile_w + gap)
    y = 112 + gap + (i // 2) * (tile_h + gap)
    canvas.paste(im, (x, y))

os.makedirs(os.path.join(OUT, 'images'), exist_ok=True)
canvas.save(os.path.join(OUT, 'images', 'dashboard.png'))
print('saved', canvas.size)
