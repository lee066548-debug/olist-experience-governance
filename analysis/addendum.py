# -*- coding: utf-8 -*-
import json, re, unicodedata, os
import pandas as pd, numpy as np

import os
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BASE = os.environ.get('OLIST_DATA_DIR', os.path.join(ROOT, 'data'))
OUT  = os.environ.get('OLIST_OUT_DIR', ROOT)
M = json.load(open(os.path.join(OUT,'metrics.json'), encoding='utf-8'))

orders = pd.read_csv(os.path.join(BASE,'olist_orders_dataset.csv'))
rev = pd.read_csv(os.path.join(BASE,'olist_order_reviews_dataset.csv'))
for c in ['order_purchase_timestamp','order_delivered_customer_date','order_estimated_delivery_date']:
    orders[c] = pd.to_datetime(orders[c], errors='coerce')
orders['delay'] = (orders.order_delivered_customer_date - orders.order_estimated_delivery_date).dt.total_seconds()/86400

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

b = rev[(rev.review_score <= 2) & rev.review_comment_message.notna()].copy()
b['topic'] = b.review_comment_message.map(classify)
b = b.merge(orders[['order_id','delay','order_purchase_timestamp','order_estimated_delivery_date']], on='order_id', how='left')
b['late'] = b.delay > 1
b['late3'] = b.delay >= 3

out = {}
tab = b.groupby(['topic','late']).size().unstack(fill_value=0)
tab['n'] = tab.sum(axis=1); tab['late_share'] = tab[True]/tab.n
out['topic_x_late'] = tab.reset_index().round(4).to_dict(orient='records')

nonlate = b[~b.late].topic.value_counts()
tot = nonlate.sum()
out['topic_nonlate'] = [{'topic': k, 'n': int(v), 'share': float(v/tot)} for k, v in nonlate.items()]
out['n_nonlate_bad_text'] = int(tot)

nr = b[b.topic == '未收到/物流异常']
out['not_received'] = {
    'n': int(len(nr)),
    'share_still_in_window': float((nr.delay <= 0).mean()),
    'share_not_more_than_1d': float((nr.delay <= 1).mean()),
    'share_late': float((nr.delay > 1).mean()),
    'median_days_after_purchase': float((nr.order_purchase_timestamp - nr.order_purchase_timestamp).dt.days.median()) if False else None,
    'median_delay': float(nr.delay.median()),
}
# days since purchase at review time would need review date; use delay only

# distribution of delay for bad reviews
out['bad_text_delay'] = {
    'share_still_in_window': float((b.delay <= 0).mean()),
    'share_0_1': float(((b.delay > 0) & (b.delay <= 1)).mean()),
    'share_1_3': float(((b.delay > 1) & (b.delay <= 3)).mean()),
    'share_gt3': float((b.delay > 3).mean()),
    'share_missing': float(b.delay.isna().mean()),
}
# topic share x three groups: late<=0, 0-3, >3
b['grp'] = np.where(b.delay <= 0, '在承诺期内', np.where(b.delay <= 3, '晚1-3天', '晚3天以上'))
ct = pd.crosstab(b.topic, b.grp, normalize='columns')
out['topic_by_timing'] = {c: {i: float(v) for i, v in ct[c].items()} for c in ct.columns}
out['timing_sizes'] = {c: int(v) for c, v in b.grp.value_counts().items()}

# review date vs purchase: how quickly do people complain?
rv = rev.copy()
rv['review_creation_date'] = pd.to_datetime(rv.review_creation_date, errors='coerce')
rv = rv.merge(orders[['order_id','order_purchase_timestamp','order_delivered_customer_date','order_estimated_delivery_date']], on='order_id', how='left')
rv['days_to_review'] = (rv.review_creation_date - rv.order_purchase_timestamp).dt.total_seconds()/86400
out['daily'] = {'median_days_to_review_bad': float(rv[rv.review_score<=2].days_to_review.median()),
                'median_days_to_review_good': float(rv[rv.review_score>=4].days_to_review.median())}

M['addendum'] = out
json.dump(M, open(os.path.join(OUT,'metrics.json'),'w',encoding='utf-8'), ensure_ascii=False, indent=2)
print(json.dumps(out, ensure_ascii=False, indent=2))

