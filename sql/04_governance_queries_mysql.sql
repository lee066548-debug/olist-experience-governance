-- ============================================================
-- 04_governance_queries_mysql.sql（MySQL 5.7 / 8.0）
-- 用途：报告的“治理口径”分析——控制变量、归因、地区拆解、承诺时效、
--       卖家风险规则、评论文本归因。全部只统计【已送达】订单。
-- 前提：02_build_wide_table_mysql.sql + 02b_patch_is_late_1d.sql
-- 约定：is_late_1d = 1 表示晚于承诺 1 天以上（= 报告里的“迟到”）
-- ============================================================


-- ------------------------------------------------------------
-- Q1. 品类差评率（n >= 200，按差评率排序）
-- 用途：商品侧治理名单；看板可加一张横向柱状图
-- ------------------------------------------------------------
SELECT
    category_en,
    COUNT(*)                                                            AS orders,
    SUM(review_score IS NOT NULL)                                       AS reviewed,
    ROUND(SUM(is_bad_review = 1) / SUM(review_score IS NOT NULL), 4)    AS bad_rate,
    ROUND(SUM(is_late_1d = 1) / SUM(is_late_1d IS NOT NULL), 4)         AS late_rate,
    ROUND(AVG(review_score), 2)                                         AS avg_score
FROM wide_orders
WHERE order_status = 'delivered'
GROUP BY category_en
HAVING reviewed >= 200
ORDER BY bad_rate DESC
LIMIT 10;
-- 预期 top3：office_furniture 21.8% / audio 21.4% / home_confort 18.1%


-- ------------------------------------------------------------
-- Q2. 卖家四象限 + Wilson 95% 置信下界
-- 用途：把“高单量 + 高差评”的卖家挑出来，避免 n=30 时把噪声当信号
-- 说明：Wilson 下界比裸差评率稳健；判定优先看 wilson_low，而不是 bad_rate
-- ------------------------------------------------------------
SELECT
    seller_id,
    orders,
    reviewed,
    bad_rate,
    ROUND(
        (bad_rate + 3.8416 / (2 * reviewed)
         - 1.96 * SQRT(bad_rate * (1 - bad_rate) / reviewed
                       + 3.8416 / (4 * reviewed * reviewed)))
        / (1 + 3.8416 / reviewed), 4)                                    AS wilson_low,
    CASE
        WHEN orders >= 200 AND bad_rate >= 0.20 THEN 'A 高单量高差评（优先治理）'
        WHEN orders >= 200                     THEN 'B 高单量低差评（标杆）'
        WHEN bad_rate >= 0.20                  THEN 'C 低单量高差评（观察）'
        ELSE                                        'D 低单量低差评'
    END                                                                 AS quadrant
FROM (
    SELECT
        seller_id,
        COUNT(*)                                                         AS orders,
        SUM(review_score IS NOT NULL)                                    AS reviewed,
        ROUND(SUM(is_bad_review = 1) / SUM(review_score IS NOT NULL), 4) AS bad_rate
    FROM wide_orders
    WHERE order_status = 'delivered'
      AND review_score IS NOT NULL
      AND seller_id IS NOT NULL
    GROUP BY seller_id
    HAVING COUNT(*) >= 100          -- 比原来的 30 单更稳；30 单的 95% 区间约 ±14pp
) t
ORDER BY CASE WHEN orders >= 200 AND bad_rate >= 0.20 THEN 0 ELSE 1 END,
         wilson_low DESC
LIMIT 50;
-- 预期：约 205 个卖家 ≥100 单；A 类 6 家、合计约 2,420 单


-- ------------------------------------------------------------
-- Q3. 控制变量①：同一卖家内，迟到 vs 准时的差评率
-- 用途：证明“延迟→差评”不是卖家结构造成的
-- ------------------------------------------------------------
SELECT
    COUNT(*)                                                            AS sellers,
    ROUND(AVG(bad_late - bad_ontime) * 100, 1)                          AS avg_diff_pp,
    SUM(bad_late > bad_ontime)                                          AS sellers_worse,
    SUM(bad_late = bad_ontime)                                          AS sellers_tie
FROM (
    SELECT
        seller_id,
        SUM(is_late_1d = 1 AND review_score IS NOT NULL)                AS n_late,
        SUM(is_late_1d = 0 AND review_score IS NOT NULL)                AS n_ontime,
        SUM(is_late_1d = 1 AND is_bad_review = 1)
            / NULLIF(SUM(is_late_1d = 1 AND review_score IS NOT NULL), 0)  AS bad_late,
        SUM(is_late_1d = 0 AND is_bad_review = 1)
            / NULLIF(SUM(is_late_1d = 0 AND review_score IS NOT NULL), 0)  AS bad_ontime
    FROM wide_orders
    WHERE order_status = 'delivered'
      AND seller_id IS NOT NULL
    GROUP BY seller_id
    HAVING n_late >= 20 AND n_ontime >= 20
) t;
-- 预期：54 个卖家 / +53.2pp / 54 个更差 / 0 个持平或更好


-- ------------------------------------------------------------
-- Q4. 控制变量②：同一品类内，迟到 vs 准时的差评率
-- ------------------------------------------------------------
SELECT
    COUNT(*)                                                            AS categories,
    ROUND(AVG(bad_late - bad_ontime) * 100, 1)                          AS avg_diff_pp,
    SUM(bad_late > bad_ontime)                                          AS cats_worse
FROM (
    SELECT
        category_en,
        SUM(is_late_1d = 1 AND review_score IS NOT NULL)                AS n_late,
        SUM(is_late_1d = 0 AND review_score IS NOT NULL)                AS n_ontime,
        SUM(is_late_1d = 1 AND is_bad_review = 1)
            / NULLIF(SUM(is_late_1d = 1 AND review_score IS NOT NULL), 0)  AS bad_late,
        SUM(is_late_1d = 0 AND is_bad_review = 1)
            / NULLIF(SUM(is_late_1d = 0 AND review_score IS NOT NULL), 0)  AS bad_ontime
    FROM wide_orders
    WHERE order_status = 'delivered'
      AND category_en IS NOT NULL
    GROUP BY category_en
    HAVING n_late >= 30 AND n_ontime >= 30
) t;
-- 预期：29 个品类 / +51.7pp / 29 个更差


-- ------------------------------------------------------------
-- Q5. 归因强度：延迟人群占比（PAF）与差评贡献率
-- 用途：把“延迟解释大部分差评”修正为可辩护的说法
-- ------------------------------------------------------------
SELECT
    p_late,
    bad_late,
    bad_ontime,
    ROUND(bad_late / bad_ontime, 2)                                      AS risk_ratio,
    ROUND(p_late * (bad_late / bad_ontime - 1)
          / (1 + p_late * (bad_late / bad_ontime - 1)), 4)               AS paf,
    ROUND(bad_from_late / all_bad, 4)                                    AS bad_share_from_late
FROM (
    SELECT
        SUM(is_late_1d = 1) / SUM(is_late_1d IS NOT NULL)                AS p_late,
        SUM(is_late_1d = 1 AND is_bad_review = 1)
            / NULLIF(SUM(is_late_1d = 1 AND review_score IS NOT NULL), 0) AS bad_late,
        SUM(is_late_1d = 0 AND is_bad_review = 1)
            / NULLIF(SUM(is_late_1d = 0 AND review_score IS NOT NULL), 0) AS bad_ontime,
        SUM(is_late_1d = 1 AND is_bad_review = 1)                        AS bad_from_late,
        SUM(is_bad_review = 1)                                           AS all_bad
    FROM wide_orders
    WHERE order_status = 'delivered'
) t;
-- 预期：p_late 0.0678 / bad_late 0.6231 / bad_ontime 0.0922 /
--       risk_ratio 6.76 / PAF 0.2762 / bad_share_from_late 0.3252
-- 解读：延迟人群只占 6.8%，但差评率是准时人群的 6.8 倍；
--       延迟可解释约 27.6% 的差评，贡献 32.5% 的差评——是“最大单一杠杆”，不是“大部分”。


-- ------------------------------------------------------------
-- Q6. 地区拆解：RJ 与 SP 的差评率差距从哪来
-- 用途：把“RJ 送达率低”的错误结论改成“RJ 时效差”
-- ------------------------------------------------------------
SELECT
    sp_late, rj_late, sp_bad, rj_bad,
    ROUND(rj_bad - sp_bad, 4)                                            AS gap,
    ROUND((sp_late * rj_bad_late + (1 - sp_late) * rj_bad_ontime) - rj_bad, 4) AS mix_effect,
    ROUND((sp_late * rj_bad_late + (1 - sp_late) * rj_bad_ontime) - sp_bad, 4) AS within_effect
FROM (
    SELECT
        MAX(CASE WHEN customer_state = 'SP' THEN late_share END)         AS sp_late,
        MAX(CASE WHEN customer_state = 'RJ' THEN late_share END)         AS rj_late,
        MAX(CASE WHEN customer_state = 'SP' THEN bad END)                AS sp_bad,
        MAX(CASE WHEN customer_state = 'RJ' THEN bad END)                AS rj_bad,
        MAX(CASE WHEN customer_state = 'RJ' THEN bad_late END)           AS rj_bad_late,
        MAX(CASE WHEN customer_state = 'RJ' THEN bad_ontime END)         AS rj_bad_ontime
    FROM (
        SELECT
            customer_state,
            SUM(is_late_1d = 1) / SUM(is_late_1d IS NOT NULL)            AS late_share,
            SUM(is_bad_review = 1) / SUM(review_score IS NOT NULL)       AS bad,
            SUM(is_late_1d = 1 AND is_bad_review = 1)
                / NULLIF(SUM(is_late_1d = 1 AND review_score IS NOT NULL), 0) AS bad_late,
            SUM(is_late_1d = 0 AND is_bad_review = 1)
                / NULLIF(SUM(is_late_1d = 0 AND review_score IS NOT NULL), 0) AS bad_ontime
        FROM wide_orders
        WHERE order_status = 'delivered'
          AND customer_state IN ('SP', 'RJ')
        GROUP BY customer_state
    ) s
) t;
-- 预期：sp_late 0.0449 / rj_late 0.1211 / sp_bad 0.1063 / rj_bad 0.1826
--       gap 0.0763 / mix_effect -0.0461（即 60% 来自迟到率差异）/ within_effect 0.0302


-- ------------------------------------------------------------
-- Q7. 承诺时效：窗口长度 × 迟到率
-- 用途：支撑“校准承诺”这个低成本动作
-- ------------------------------------------------------------
SELECT
    CASE
        WHEN promise_window <= 15 THEN 'A ≤15天'
        WHEN promise_window <= 20 THEN 'B 15-20天'
        WHEN promise_window <= 25 THEN 'C 20-25天'
        WHEN promise_window <= 30 THEN 'D 25-30天'
        WHEN promise_window <= 40 THEN 'E 30-40天'
        ELSE                           'F >40天'
    END                                                                 AS window_band,
    COUNT(*)                                                            AS orders,
    ROUND(SUM(is_late_1d = 1) / COUNT(*), 4)                            AS late_rate
FROM (
    SELECT
        DATEDIFF(ts_estimated, ts_purchase)                             AS promise_window,
        is_late_1d
    FROM wide_orders
    WHERE order_status = 'delivered'
) t
GROUP BY window_band
ORDER BY window_band;
-- 预期：5.9% / 7.1% / 8.1% / 7.1% / 5.6% / 2.3%
-- 注意：这是描述性证据（窗口与品类、路线相关），不是因果；要证明收益需要 A/B。


-- ------------------------------------------------------------
-- Q8. 风险规则（示例）：卖家历史迟到率 × 承诺窗口
-- 用途：在没有模型之前，先用一条可解释规则找出“下单时就能识别”的高风险订单
-- 说明：seller 的历史迟到率按“该卖家全部已送达订单”计算（上线时请改为滚动历史窗口，
--       避免把当前订单的真实结果泄漏进特征）
-- ------------------------------------------------------------
SELECT
    CASE
        WHEN sel.late_rate IS NULL      THEN '0 无历史'
        WHEN sel.late_rate <  0.05      THEN '1 <5%'
        WHEN sel.late_rate <  0.15      THEN '2 5-15%'
        ELSE                                 '3 >=15%'
    END                                                                 AS seller_band,
    CASE
        WHEN DATEDIFF(o.ts_estimated, o.ts_purchase) <= 15 THEN 'A ≤15天'
        WHEN DATEDIFF(o.ts_estimated, o.ts_purchase) <= 25 THEN 'B 16-25天'
        ELSE                                                    'C >25天'
    END                                                                 AS window_band,
    COUNT(*)                                                            AS orders,
    ROUND(SUM(o.is_late_1d = 1) / COUNT(*), 4)                          AS late_rate
FROM wide_orders o
LEFT JOIN (
    SELECT seller_id,
           AVG(is_late_1d)                                              AS late_rate,
           COUNT(*)                                                     AS seller_orders
    FROM wide_orders
    WHERE order_status = 'delivered'
      AND is_late_1d IS NOT NULL
    GROUP BY seller_id
    HAVING COUNT(*) >= 30
) sel ON o.seller_id = sel.seller_id
WHERE o.order_status = 'delivered'
  AND o.is_late_1d IS NOT NULL
GROUP BY seller_band, window_band
ORDER BY seller_band, window_band;
-- 解读：右上角（3 >=15% × C >25天）就是优先干预人群；
--       用它算“抓取率/提升度”，再决定干预名单和 A/B 的入组规则。


-- ------------------------------------------------------------
-- Q9. 评论文本归因（SQL 版，可解释）
-- 用途：回答“延迟之外那 70% 的差评是什么”
-- 说明：utf8mb4_general_ci 不区分重音，'atras' 能匹配 'atrás'；
--       与 Python 规则版会有 1–2% 差异，属正常。
-- ------------------------------------------------------------
SELECT
    CASE
        WHEN msg LIKE '%nao recebi%' OR msg LIKE '%nao chegou%'
          OR msg LIKE '%nao foi entregue%' OR msg LIKE '%extravio%'
          OR msg LIKE '%aguardando%' OR msg LIKE '%nao veio%'       THEN '未收到/物流异常'
        WHEN msg LIKE '%atras%' OR msg LIKE '%prazo%' OR msg LIKE '%demor%'
          OR msg LIKE '%correio%' OR msg LIKE '%transportadora%'    THEN '延迟/物流慢'
        WHEN msg LIKE '%errado%' OR msg LIKE '%faltando%' OR msg LIKE '%faltou%'
          OR msg LIKE '%incompleto%'                                THEN '错发/缺件'
        WHEN msg LIKE '%quebrad%' OR msg LIKE '%defeito%' OR msg LIKE '%danificad%'
          OR msg LIKE '%qualidade%' OR msg LIKE '%nao funciona%'    THEN '商品质量/破损'
        WHEN msg LIKE '%diferente%' OR msg LIKE '%anuncio%' OR msg LIKE '%foto%'
          OR msg LIKE '%descricao%' OR msg LIKE '%tamanho%'         THEN '描述不符/期望落差'
        WHEN msg LIKE '%atendimento%' OR msg LIKE '%resposta%'
          OR msg LIKE '%suporte%' OR msg LIKE '%contato%'           THEN '客服/售后'
        WHEN msg LIKE '%reembolso%' OR msg LIKE '%estorno%'
          OR msg LIKE '%devolucao%' OR msg LIKE '%cancel%'          THEN '退款/取消'
        WHEN msg LIKE '%caro%' OR msg LIKE '%frete%' OR msg LIKE '%preco%' THEN '价格/运费'
        ELSE                                                            '无具体原因/泛差评'
    END                                                                 AS topic,
    COUNT(*)                                                            AS reviews,
    ROUND(COUNT(*) / (SELECT COUNT(*) FROM order_reviews
                      WHERE review_score <= 2
                        AND review_comment_message IS NOT NULL), 4)      AS share
FROM (
    SELECT review_score,
           LOWER(review_comment_message)                                AS msg
    FROM order_reviews
    WHERE review_score <= 2
      AND review_comment_message IS NOT NULL
) t
GROUP BY topic
ORDER BY reviews DESC;
-- 预期：未收到 30.4% / 无具体原因 24.5% / 延迟 12.9% / 质量 11.2% /
--       描述不符 7.3% / 错发 5.5% / 客服 4.0% / 退款 3.1% / 价格 1.0%


-- ------------------------------------------------------------
-- Q10. 文本 × 延迟：差评到底有多少是“迟到造成的”
-- ------------------------------------------------------------
SELECT
    CASE
        WHEN o.days_vs_estimate IS NULL THEN '未知'
        WHEN o.days_vs_estimate <= 0    THEN '承诺期内送达'
        WHEN o.days_vs_estimate <= 3    THEN '晚 1-3 天'
        ELSE                                 '晚 3 天以上'
    END                                                                 AS timing,
    COUNT(*)                                                            AS reviews
FROM order_reviews r
JOIN wide_orders o ON r.order_id = o.order_id
WHERE r.review_score <= 2
  AND r.review_comment_message IS NOT NULL
GROUP BY timing
ORDER BY reviews DESC;
-- 预期：承诺期内约 59% / 晚 3 天以上约 23% / 晚 1-3 天约 2% / 未知约 15%
-- 解读：多数差评发生在“还没超期”时，说明承诺窗口过长、
--       顾客在到期前就已经不满——这是承诺校准的直接证据。
