# -*- coding: utf-8 -*-
"""Recompute every number used in the revised report from the raw CSVs.
Writes metrics.json + topic_summary.csv next to this script.
"""
import json, re, unicodedata, os
import pandas as pd, numpy as np

BASE = r'C:\Users\李\Desktop\李志豪的获奖\个人项目\Olist体验治理分析\github-repo\data'
OUT  = r'C:\Users\李\Documents\deepseek-harness\default-workspace\olist_review'
os.makedirs(OUT, exist_ok=True)

orders = pd.read_csv(os.path.join(BASE, 'olist_orders_dataset.csv'))
cust   = pd.read_csv(os.path.join(BASE, 'olist_customers_dataset.csv'))
items  = pd.read_csv(os.path.join(BASE, 'olist_order_items_dataset.csv'))
rev    = pd.read_csv(os.path.join(BASE, 'olist_order_reviews_dataset.csv'))
prod   = pd.read_csv(os.path.join(BASE, 'olist_products_dataset.csv'))
trans  = pd.read_csv(os.path.join(BASE, 'product_category_name_translation.csv'))
sellers= pd.read_csv(os.path.join(BASE, 'olist_sellers_dataset.csv'))

DATE_COLS = ['order_purchase_timestamp','order_approved_at','order_delivered_carrier_date',
             'order_delivered_customer_date','order_estimated_delivery_date']
for c in DATE_COLS:
    orders[c] = pd.to_datetime(orders[c], errors='coerce')

M = {}
M['total_orders'] = int(len(orders))
M['delivered'] = int((orders.order_status == 'delivered').sum())
M['delivery_rate'] = M['delivered'] / M['total_orders']
M['date_min'] = str(orders.order_purchase_timestamp.min().date())
M['date_max'] = str(orders.order_purchase_timestamp.max().date())
M['approved'] = int(orders.order_approved_at.notna().sum())
M['approved_rate'] = M['approved'] / M['total_orders']
M['carrier'] = int(orders.order_delivered_carrier_date.notna().sum())

# review dedup: keep highest score (as in the pipeline), remember whether any text exists
rev['has_text'] = rev.review_comment_message.notna()
agg = rev.groupby('order_id').agg(sc=('review_score','max'), has_text=('has_text','max'),
                                  n_rev=('review_score','size'))
M['review_rows'] = int(len(rev))
M['reviewed_orders'] = int(len(agg))
M['dup_review_orders'] = int((agg.n_rev > 1).sum())
M['avg_score_all'] = float(rev.review_score.mean())
M['bad_rate_all'] = float((rev.review_score <= 2).mean())
M['score_dist_all'] = {int(k): int(v) for k, v in rev.review_score.value_counts().sort_index().items()}

orders['sc'] = orders.order_id.map(agg.sc)
orders['has_text'] = orders.order_id.map(agg.has_text)
orders['n_rev'] = orders.order_id.map(agg.n_rev)
orders['state'] = orders.merge(cust[['customer_id','customer_state']], on='customer_id', how='left').customer_state.values
orders['is_delivered'] = orders.order_status == 'delivered'
orders['fulfill'] = (orders.order_delivered_customer_date - orders.order_purchase_timestamp).dt.total_seconds()/86400
orders['to_carrier'] = (orders.order_delivered_carrier_date - orders.order_purchase_timestamp).dt.total_seconds()/86400
orders['delay'] = (orders.order_delivered_customer_date - orders.order_estimated_delivery_date).dt.total_seconds()/86400
orders['promise_window'] = (orders.order_estimated_delivery_date - orders.order_purchase_timestamp).dt.total_seconds()/86400

d = orders[orders.is_delivered].copy()
M['delivered_with_ts'] = int(d.delay.notna().sum())
M['avg_fulfill'] = float(d.fulfill.mean())
M['avg_to_carrier'] = float(d.to_carrier.mean())
M['avg_score_delivered'] = float(d.sc.mean())
M['reviewed_delivered'] = int(d.sc.notna().sum())
M['bad_delivered'] = int((d.sc <= 2).sum())
M['bad_rate_delivered'] = M['bad_delivered'] / M['reviewed_delivered']
M['score_dist_delivered_orders'] = {int(k): int(v) for k, v in d.sc.value_counts().sort_index().items()}

# late definitions
late_mask = d.delay > 1
M['late_n'] = int(late_mask.sum())
M['late_rate'] = M['late_n'] / M['delivered_with_ts']
M['late_any_rate'] = float((d.delay > 0).sum() / d.delay.notna().sum())
M['late_any_n'] = int((d.delay > 0).sum())

# 4-bucket ladder (this is the canonical one)
bins = [-1e9, 1, 3, 7, 1e9]
labels = ['准时或提前(<1天)', '延迟1-3天', '延迟3-7天', '延迟7天以上']
dd = d.dropna(subset=['delay']).copy()
dd['bucket'] = pd.cut(dd.delay, bins=bins, labels=labels, right=False)
g = dd.groupby('bucket', observed=True).agg(orders=('order_id','size'), reviewed=('sc','count'),
                                            avg_score=('sc','mean'),
                                            bad=('sc', lambda x:(x<=2).sum()))
g['bad_rate'] = g.bad / g.reviewed
g['share'] = g.orders / g.orders.sum()
M['ladder'] = [{'bucket': str(i), 'orders': int(r.orders), 'share': float(r.share),
                'reviewed': int(r.reviewed), 'avg_score': float(r.avg_score),
                'bad': int(r.bad), 'bad_rate': float(r.bad_rate)} for i, r in g.iterrows()]
M['ladder_checksum_orders'] = int(g.orders.sum())

# attribution
bad = d[d.sc <= 2]
M['bad_with_late_gt1'] = int((bad.delay > 1).sum())
M['bad_with_late_gt1_share'] = float((bad.delay > 1).sum() / len(bad))
late3 = d.delay >= 3
M['late3_n'] = int(late3.sum())
M['late3_share'] = float(late3.mean())
M['late3_bad'] = int(((d.sc <= 2) & late3).sum())
M['late3_bad_share'] = float(((d.sc <= 2) & late3).sum() / M['bad_delivered'])
M['late3_bad_rate'] = float((d[late3].sc <= 2).sum() / d[late3].sc.notna().sum())
M['paf_late'] = float((M['late_rate'] * ((M['late3_bad_rate'] if False else 0)) ))
# PAF with late>1
p = M['late_rate']; rr = (d[late_mask].sc <= 2).mean() / (d[~late_mask & d.delay.notna()].sc <= 2).mean()
M['paf'] = float(p*(rr-1)/(1+p*(rr-1)))
M['bad_rate_late'] = float((d[late_mask].sc <= 2).sum() / d[late_mask].sc.notna().sum())
_on = d[~late_mask & d.delay.notna()]; M['bad_rate_ontime'] = float((_on.sc <= 2).sum() / _on.sc.notna().sum())
M['avg_score_late'] = float(d[late_mask].sc.mean())
M['avg_score_ontime'] = float(d[~late_mask & d.delay.notna()].sc.mean())
# 1-star
M['one_star'] = int((d.sc == 1).sum())
M['one_star_late_share'] = float(((d.sc == 1) & late_mask).sum() / M['one_star'])

# monthly
orders['month'] = orders.order_purchase_timestamp.dt.to_period('M').astype(str)
mon = orders.groupby('month').agg(orders=('order_id','size'), delivered=('is_delivered','sum')).reset_index()
mon = mon[(mon.month >= '2017-01') & (mon.month <= '2018-08')]
mon['delivery_rate'] = mon.delivered / mon.orders
M['monthly'] = mon.round(4).to_dict(orient='records')

# states
st = d.groupby('state').agg(orders=('order_id','size'), reviewed=('sc','count'),
                            bad=('sc', lambda x:(x<=2).sum()),
                            late=('delay', lambda x:(x>1).sum()),
                            with_ts=('delay','count'),
                            avg_score=('sc','mean'), fulfill=('fulfill','mean')).reset_index()
st['bad_rate'] = st.bad/st.reviewed; st['late_rate'] = st.late/st.with_ts
st['delivery_rate'] = st.orders / st.orders  # placeholder
st_all = orders.groupby('state').agg(all_orders=('order_id','size'), delivered=('is_delivered','sum')).reset_index()
st = st.merge(st_all, on='state')
st['delivery_rate'] = st.delivered / st.all_orders
M['states'] = st.sort_values('orders', ascending=False).head(10).round(4).to_dict(orient='records')
M['sp'] = st[st.state=='SP'].round(4).to_dict(orient='records')[0]
M['rj'] = st[st.state=='RJ'].round(4).to_dict(orient='records')[0]
M['sp_rj_share'] = float(orders.state.isin(['SP','RJ']).mean())

# RJ vs SP decomposition
def parts(x):
    z = x[x.sc.notna()]
    w = (x.delay > 1).mean(); bl = (z[z.delay > 1].sc <= 2).mean(); bo = (z[z.delay <= 1].sc <= 2).mean()
    return w, bl, bo
sp = d[d.state=='SP'].dropna(subset=['delay']); rj = d[d.state=='RJ'].dropna(subset=['delay'])
wsp, blsp, bosp = parts(sp); wrj, blrj, borj = parts(rj)
cf = wsp*blrj + (1-wsp)*borj
M['rj_decomp'] = {'sp_late_share': float(wsp), 'sp_bad_late': float(blsp), 'sp_bad_ontime': float(bosp),
                  'sp_bad': float((sp.sc<=2).sum()/sp.sc.notna().sum()),
                  'rj_late_share': float(wrj), 'rj_bad_late': float(blrj), 'rj_bad_ontime': float(borj),
                  'rj_bad': float((rj.sc<=2).sum()/rj.sc.notna().sum()),
                  'counterfactual': float(cf), 'gap': float((rj.sc<=2).sum()/rj.sc.notna().sum()-(sp.sc<=2).sum()/sp.sc.notna().sum()),
                  'mix_effect': float(cf-(rj.sc<=2).sum()/rj.sc.notna().sum()),
                  'within_effect': float(cf-(sp.sc<=2).sum()/sp.sc.notna().sum())}

# within-seller / within-category
it = items.groupby('order_id').agg(sell=('seller_id','min'), prod=('product_id','min')).reset_index()
d2 = d.merge(it, on='order_id', how='left')
d2['late'] = d2.delay > 1
gs = d2.dropna(subset=['sell']).groupby(['sell','late']).agg(n=('order_id','size'), bad=('sc', lambda x:(x<=2).mean())).unstack().dropna()
gs = gs[(gs[('n',True)] >= 20) & (gs[('n',False)] >= 20)]
M['within_seller'] = {'sellers': int(len(gs)), 'mean_diff_pp': float((gs[('bad',True)]-gs[('bad',False)]).mean()*100),
                      'all_worse': bool((gs[('bad',True)] > gs[('bad',False)]).all()),
                      'median_late_bad': float(gs[('bad',True)].median()), 'median_ontime_bad': float(gs[('bad',False)].median())}
d3 = d2.merge(prod[['product_id','product_category_name']], left_on='prod', right_on='product_id', how='left').merge(trans, on='product_category_name', how='left')
d3['cat'] = d3.product_category_name_english.fillna(d3.product_category_name)
gc = d3.dropna(subset=['cat']).groupby(['cat','late']).agg(n=('order_id','size'), bad=('sc', lambda x:(x<=2).mean())).unstack().dropna()
gc = gc[(gc[('n',True)] >= 30) & (gc[('n',False)] >= 30)]
M['within_cat'] = {'cats': int(len(gc)), 'mean_diff_pp': float((gc[('bad',True)]-gc[('bad',False)]).mean()*100),
                   'all_worse': bool((gc[('bad',True)] > gc[('bad',False)]).all())}

# category table
cat = d3.groupby('cat').agg(orders=('order_id','size'), reviewed=('sc','count'),
                            bad=('sc', lambda x:(x<=2).sum()), late=('late','sum'),
                            avg_score=('sc','mean')).reset_index()
cat = cat[cat.reviewed >= 200].copy(); cat['bad_rate'] = cat.bad/cat.reviewed; cat['late_rate'] = cat.late/cat.orders
M['categories_n200'] = int(len(cat))
M['category_top'] = cat.sort_values('bad_rate', ascending=False).head(8).round(4).to_dict(orient='records')
M['category_big'] = cat.sort_values('orders', ascending=False).head(6).round(4).to_dict(orient='records')

# sellers
sl = d2.dropna(subset=['sell']).groupby('sell').agg(orders=('order_id','size'), reviewed=('sc','count'),
                                                    bad=('sc', lambda x:(x<=2).sum()), late=('late','sum'))
sl['bad_rate'] = sl.bad/sl.reviewed; sl['late_rate'] = sl.late/sl.orders
M['sellers_total'] = int(len(sl)); M['sellers_ge30'] = int((sl.orders >= 30).sum())
M['sellers_ge100'] = int((sl.orders >= 100).sum())
q = sl[(sl.orders >= 100)]
M['seller_quadrant'] = {'A":0': 0}
M['seller_A_n'] = int(((q.orders >= 200) & (q.bad_rate >= 0.2)).sum())
M['seller_A_orders'] = int(q[(q.orders >= 200) & (q.bad_rate >= 0.2)].orders.sum())
M['seller_concentration_top10'] = float(sl.orders.nlargest(10).sum()/sl.orders.sum())
M['seller_concentration_top100'] = float(sl.orders.nlargest(100).sum()/sl.orders.sum())

# repeat purchase
u = orders.merge(cust[['customer_id','customer_unique_id']], on='customer_id', how='left')
cnt = u.groupby('customer_unique_id').order_id.nunique()
M['unique_customers'] = int(len(cnt)); M['one_time'] = int((cnt==1).sum()); M['one_time_share'] = float((cnt==1).mean())
M['occasional'] = int(((cnt>=2)&(cnt<=3)).sum()); M['loyal'] = int((cnt>=4).sum())
first = u.sort_values('order_purchase_timestamp').groupby('customer_unique_id').first()
first['repeats'] = cnt
first['late'] = (first.order_delivered_customer_date - first.order_estimated_delivery_date).dt.total_seconds()/86400 > 1
first = first[first.order_delivered_customer_date.notna() & first.order_estimated_delivery_date.notna()]
M['repeat_by_late'] = {'repeat_late': float(first[first.late].repeats.ge(2).mean()),
                       'repeat_ontime': float(first[~first.late].repeats.ge(2).mean()),
                       'n_late': int(first.late.sum()), 'n_ontime': int((~first.late).sum())}

# promise window
d['win_bucket'] = pd.cut(d.promise_window, [0,15,20,25,30,40,1e9],
                         labels=['≤15天','15-20天','20-25天','25-30天','30-40天','>40天'])
w = d.dropna(subset=['delay','win_bucket']).groupby('win_bucket', observed=True).agg(
    orders=('order_id','size'), late=('delay', lambda x:(x>1).mean()))
M['promise_window'] = {'avg_window': float(d.promise_window.mean()), 'avg_fulfill': float(d.fulfill.mean()),
                       'buffer': float((d.promise_window - d.fulfill).mean()),
                       'buckets': [{'bucket': str(i), 'orders': int(r.orders), 'late_rate': float(r.late)} for i, r in w.iterrows()]}

# gmv
M['gmv_product'] = float(items.price.sum()); M['gmv_freight'] = float(items.freight_value.sum())
M['gmv_total'] = float(items.price.sum() + items.freight_value.sum())
M['avg_order_value'] = float(d2.merge(items.groupby('order_id').price.sum().rename('amt'), on='order_id').amt.mean())

# ---------------- text attribution ----------------
def norm(s):
    s = str(s).lower()
    s = unicodedata.normalize('NFKD', s).encode('ascii','ignore').decode()
    s = re.sub(r'[^a-z\s]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()

TOPICS = [
    ('未收到/物流异常', ['nao recebi','nao chegou','nao foi entregue','extravio','extraviado','perdido',
                        'aguardando','nao veio','nunca chegou','nao recebido','entrega nao realizada']),
    ('延迟/物流慢', ['atras','prazo','demor','demora','lento','correio','transportadora','rastre',
                    'logistica','entrega demorou','chegou depois']),
    ('错发/缺件', ['errado','faltando','faltou','incompleto','veio outro','produto diferente','trocado',
                  'veio so','nao veio o','item errado']),
    ('商品质量/破损', ['quebrad','defeito','danificad','ruim','pessim','qualidade','nao funciona',
                      'estragad','rachad','amassad','mau estado','horrivel','lixo','falso','original']),
    ('描述不符/期望落差', ['diferente','nao e o que','anuncio','foto','descricao','tamanho','cor',
                          'esperava','menor','maior','modelo']),
    ('客服/售后', ['atendimento','contato','resposta','suporte','sac','email','telefone','nao responderam',
                  'reclamacao','devolucao']),
    ('退款/取消', ['reembolso','estorno','devolver','devolucao','cancel','dinheiro','pagamento']),
    ('价格/运费', ['caro','frete','preco','valor']),
]
def classify(txt):
    t = norm(txt)
    for name, kws in TOPICS:
        for kw in kws:
            if kw in t:
                return name
    return '无具体原因/泛差评'

badtext = rev[(rev.review_score <= 2) & rev.review_comment_message.notna()].copy()
badtext['topic'] = badtext.review_comment_message.map(classify)
tt = badtext.topic.value_counts()
M['text'] = {'bad_reviews_with_text': int(len(badtext)),
             'bad_review_rows': int((rev.review_score <= 2).sum()),
             'coverage': float(len(badtext)/(rev.review_score <= 2).sum()),
             'topics': [{'topic': k, 'n': int(v), 'share': float(v/len(badtext))} for k, v in tt.items()]}
# topic vs late (only orders, join delay)
bt = badtext.merge(orders[['order_id','delay','state','sc']], on='order_id', how='left')
bt['late'] = bt.delay > 1
tab = bt.groupby(['topic','late']).size().unstack(fill_value=0)
tab['late_share'] = tab[True]/(tab[True]+tab[False])
M['text_by_late'] = [{'topic': i, 'late_share': float(r.late_share), 'n': int(r[True]+r[False])}
                     for i, r in tab.iterrows()]
M['text']['late_share_overall'] = float(bt.late.mean())

# top terms per topic (tf-idf style, just document frequency for transparency)
def top_terms(texts, k=8):
    from collections import Counter
    c = Counter()
    for t in texts:
        c.update(set(norm(t).split()))
    stop = set('de da do que nao e o a um uma para com muito mais foi eh em no na por os as se me meu minha '
               'so bem ja ate porque mas ou quando como tem ter pelo pela dos das nos nas lhe isso isto aqui'.split())
    return [w for w, _ in [(w, n) for w, n in c.most_common(200) if w not in stop and len(w) > 2]][:k]
M['text_top_terms'] = {name: top_terms(badtext[badtext.topic == name].review_comment_message, 8)
                       for name in tt.index}
# sample messages
M['text_samples'] = {name: badtext[badtext.topic == name].review_comment_message.head(2).tolist() for name in tt.index}

with open(os.path.join(OUT, 'metrics.json'), 'w', encoding='utf-8') as f:
    json.dump(M, f, ensure_ascii=False, indent=2)

pd.DataFrame(M['text']['topics']).to_csv(os.path.join(OUT, 'topic_summary.csv'), index=False, encoding='utf-8-sig')
print(json.dumps({k: M[k] for k in ['total_orders','delivered','avg_score_all','avg_score_delivered','late_rate','paf',
                                    'late3_bad_share','within_seller','within_cat','rj_decomp']},
                 ensure_ascii=False, indent=2))
print('TOPICS'); print(pd.DataFrame(M['text']['topics']).to_string())
print('LADDER'); print(pd.DataFrame(M['ladder']).to_string())

