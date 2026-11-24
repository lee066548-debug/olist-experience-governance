# -*- coding: utf-8 -*-
"""差评文本归因（葡萄牙语关键词规则版）。

输入：olist_order_reviews_dataset.csv
输出：topic_summary.csv（主题、条数、占比、其中迟到订单占比）

用法：
    python 05_text_topics.py [reviews.csv] [orders.csv]

说明：
- 规则版可解释、可复现，适合作为第一版；生产环境建议用 TF-IDF + 聚类
  （或 LLM 打标）复核，规则版可作为先验与校验集。
- 关键词均为“去重音 + 小写”后的形式（ex.: atrasado -> atras），
  因此 atrasado / atrasada / atraso 都能匹配。
"""

import os
import re
import sys
import unicodedata

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'olist_data')
REVIEWS = sys.argv[1] if len(sys.argv) > 1 else os.path.join(DATA, 'olist_order_reviews_dataset.csv')
ORDERS = sys.argv[2] if len(sys.argv) > 2 else os.path.join(DATA, 'olist_orders_dataset.csv')

# 顺序即优先级：先命中者为准（一条评论只归一个主因）
TOPICS = [
    ('未收到/物流异常', ['nao recebi', 'nao chegou', 'nao foi entregue', 'extravio',
                        'extraviado', 'perdido', 'aguardando', 'nao veio',
                        'nunca chegou', 'nao recebido', 'entrega nao realizada']),
    ('延迟/物流慢', ['atras', 'prazo', 'demor', 'demora', 'lento', 'correio',
                    'transportadora', 'rastre', 'logistica', 'chegou depois']),
    ('错发/缺件', ['errado', 'faltando', 'faltou', 'incompleto', 'veio outro',
                  'produto diferente', 'trocado', 'veio so', 'item errado']),
    ('商品质量/破损', ['quebrad', 'defeito', 'danificad', 'ruim', 'pessim', 'qualidade',
                      'nao funciona', 'estragad', 'rachad', 'amassad', 'mau estado',
                      'horrivel', 'lixo', 'falso']),
    ('描述不符/期望落差', ['diferente', 'nao e o que', 'anuncio', 'foto', 'descricao',
                          'tamanho', 'cor', 'esperava', 'menor', 'maior', 'modelo']),
    ('客服/售后', ['atendimento', 'contato', 'resposta', 'suporte', 'sac',
                  'email', 'telefone', 'nao responderam', 'reclamacao', 'devolucao']),
    ('退款/取消', ['reembolso', 'estorno', 'devolver', 'devolucao', 'cancel',
                  'dinheiro', 'pagamento']),
    ('价格/运费', ['caro', 'frete', 'preco', 'valor']),
]


def normalize(text: str) -> str:
    """小写 + 去重音 + 只保留字母，便于跨拼写匹配。"""
    text = str(text).lower()
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode()
    text = re.sub(r'[^a-z\s]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def classify(text: str) -> str:
    tokens = normalize(text)
    for name, keywords in TOPICS:
        if any(kw in tokens for kw in keywords):
            return name
    return '无具体原因/泛差评'


def main() -> None:
    reviews = pd.read_csv(REVIEWS)
    bad = reviews[(reviews.review_score <= 2) & reviews.review_comment_message.notna()].copy()
    bad['topic'] = bad.review_comment_message.map(classify)

    summary = (bad.groupby('topic').size().rename('reviews').reset_index()
               .sort_values('reviews', ascending=False))
    summary['share'] = (summary.reviews / len(bad)).round(4)

    # 迟到订单占比：需要订单表的签收/承诺时间
    if os.path.exists(ORDERS):
        orders = pd.read_csv(ORDERS)
        for col in ('order_delivered_customer_date', 'order_estimated_delivery_date'):
            orders[col] = pd.to_datetime(orders[col], errors='coerce')
        orders['is_late_1d'] = (
            (orders.order_delivered_customer_date - orders.order_estimated_delivery_date)
            .dt.total_seconds() / 86400 > 1
        )
        bad = bad.merge(orders[['order_id', 'is_late_1d']], on='order_id', how='left')
        late_share = bad.groupby('topic').is_late_1d.mean().rename('late_share')
        summary = summary.merge(late_share, on='topic', how='left')
        summary['late_share'] = summary.late_share.round(4)

    out = os.path.join(HERE, 'topic_summary.csv')
    summary.to_csv(out, index=False, encoding='utf-8-sig')

    print(f'bad reviews with text: {len(bad):,} / {int((reviews.review_score <= 2).sum()):,}')
    print(summary.to_string(index=False))
    print(f'\nsaved -> {out}')


if __name__ == '__main__':
    main()
