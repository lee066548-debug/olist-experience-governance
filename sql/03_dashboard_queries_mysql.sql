-- ============================================================
-- 03_dashboard_queries_mysql.sql（MySQL 5.7 / 8.0）
-- 用途：逐条对应 Tableau 看板的 5 个 KPI 卡片 + 6 张图
-- 前提：已执行
--       01_load_olist_mysql.py
--       02_build_wide_table_mysql.sql
--       02b_patch_is_late_1d.sql
-- 口径：本文件是“看板口径”——除特别注明外均按【全部订单】统计；
--       04_governance_queries_mysql.sql 是“治理口径”（仅已送达），两者不要混用。
-- 用法：每条查询都能直接在 Tableau 里作为一张 sheet 的数据源。
-- ============================================================


-- ------------------------------------------------------------
-- KPI 卡片（对应看板顶部 5 张 KPI：99,441 / 97.0% / 4.09 / 6.8% / R$13.6M）
-- 注意：avg_review_score 的分母是“有评价订单”，late_rate 的分母是“有承诺时间戳的已送达订单”
-- ------------------------------------------------------------
SELECT
    COUNT(*)                                                        AS total_orders,
    ROUND(SUM(order_status = 'delivered') / COUNT(*), 4)            AS delivery_rate,
    ROUND(AVG(review_score), 2)                                     AS avg_review_score,
    ROUND(SUM(is_late_1d = 1) / SUM(is_late_1d IS NOT NULL), 4)     AS late_rate_1d,
    ROUND(SUM(item_amount), 2)                                      AS gmv_product
FROM wide_orders;
-- 预期：99441 / 0.9702 / 4.09 / 0.0678 / 13591643.70


-- ------------------------------------------------------------
-- 图 1「Monthly Orders & Delivery Rate」
-- 横轴 month，左轴 orders（柱），右轴 delivery_rate（线）
-- ------------------------------------------------------------
SELECT
    DATE_FORMAT(ts_purchase, '%Y-%m')                               AS month,
    COUNT(*)                                                        AS orders,
    SUM(order_status = 'delivered')                                 AS delivered_orders,
    ROUND(SUM(order_status = 'delivered') / COUNT(*), 4)            AS delivery_rate
FROM wide_orders
WHERE ts_purchase >= '2017-01-01'
  AND ts_purchase <  '2018-09-01'      -- 2016 年与 2018-09 之后样本不完整，看板不展示
GROUP BY month
ORDER BY month;
-- 预期：2017-01 = 800 单 / 0.9375；2018-08 = 6,512 单 / 0.9753


-- ------------------------------------------------------------
-- 图 2「Delivery Delay Breakdown」（环形图）
-- 看板环形图用四档；图 3 的评分图和报告用三档，两者对应不同图表，不要混用
-- ------------------------------------------------------------
SELECT
    CASE
        WHEN days_vs_estimate IS NULL THEN '5 未签收'
        WHEN days_vs_estimate <  1    THEN '1 准时或提前'
        WHEN days_vs_estimate <  3    THEN '2 延迟1-3天'
        WHEN days_vs_estimate <  7    THEN '3 延迟3-7天'
        ELSE                               '4 延迟7天以上'
    END                                                             AS delay_bucket,
    COUNT(*)                                                        AS orders,
    ROUND(COUNT(*) / (SELECT COUNT(*) FROM wide_orders
                      WHERE order_status = 'delivered'), 4)          AS share
FROM wide_orders
WHERE order_status = 'delivered'
GROUP BY delay_bucket
ORDER BY delay_bucket;
-- 预期：89,936 / 1,370 / 1,819 / 3,345 / 未签收 8


-- ------------------------------------------------------------
-- 图 3「Review Score Delivery Timing」
-- 口径与看板和报告一致：三档（<1 天 / 1–4 天 / ≥4 天）
-- ------------------------------------------------------------
SELECT
    CASE
        WHEN days_vs_estimate IS NULL THEN '4 未签收'
        WHEN days_vs_estimate <  1    THEN '1 准时或提前'
        WHEN days_vs_estimate <  4    THEN '2 延迟1-4天'
        ELSE                               '3 延迟4天以上'
    END                                                             AS delay_bucket,
    COUNT(*)                                                        AS orders,
    ROUND(AVG(review_score), 2)                                     AS avg_score,
    ROUND(SUM(is_bad_review = 1) / SUM(review_score IS NOT NULL), 4) AS bad_rate
FROM wide_orders
WHERE order_status = 'delivered'
GROUP BY delay_bucket
ORDER BY delay_bucket;
-- 预期：4.29/9.2% → 3.29/32.1% → 1.86/74.7%


-- ------------------------------------------------------------
-- 图 4「Top 10 States by Orders Volume」
-- 注意：这里统计的是【全部订单】，所以 SP = 41,746（不是已送达的 40,501）
-- ------------------------------------------------------------
SELECT
    customer_state,
    COUNT(*)                                                        AS orders
FROM wide_orders
GROUP BY customer_state
ORDER BY orders DESC
LIMIT 10;
-- 预期：SP 41,746 / RJ 12,852 / MG 11,635 / RS 5,466 / PR 5,045 ...


-- ------------------------------------------------------------
-- 图 5「Review Score Distribution」
-- 1–5 星各多少单；只统计有评价的订单（去重后 98,673）
-- ------------------------------------------------------------
SELECT
    review_score,
    COUNT(*)                                                        AS orders,
    ROUND(COUNT(*) / (SELECT COUNT(*) FROM wide_orders
                      WHERE review_score IS NOT NULL), 4)           AS share
FROM wide_orders
WHERE review_score IS NOT NULL
GROUP BY review_score
ORDER BY review_score;
-- 预期：1 星 11,316 / 2 星 3,121 / 3 星 8,116 / 4 星 19,044 / 5 星 57,076


-- ------------------------------------------------------------
-- 图 6「Customer Order Frequency」
-- 看板用的是 customer_frequency.csv；这里给出等价 SQL（按 customer_unique_id 去重客户）
-- 说明：wide_orders 只有 customer_id，没有 customer_unique_id，所以要回到原始表 join
-- ------------------------------------------------------------
SELECT
    CASE
        WHEN t.order_cnt = 1            THEN 'One-time'
        WHEN t.order_cnt BETWEEN 2 AND 3 THEN 'Occasional (2-3)'
        ELSE                                 'Loyal (4+)'
    END                                                             AS segment,
    COUNT(*)                                                        AS customers,
    ROUND(COUNT(*) / SUM(COUNT(*)) OVER (), 4)                      AS share
FROM (
    SELECT c.customer_unique_id,
           COUNT(DISTINCT o.order_id) AS order_cnt
    FROM orders o
    JOIN customers c ON o.customer_id = c.customer_id
    GROUP BY c.customer_unique_id
) t
GROUP BY segment
ORDER BY customers DESC;
-- 预期：One-time 93,099（96.9%）/ Occasional 2,948 / Loyal 49
-- 若数据库是 MySQL 5.7（不支持窗口函数），把 share 列删掉，在 Tableau 里算占比即可。


-- ------------------------------------------------------------
-- 自检：把所有 KPI 与看板对一遍
-- 任何一项对不上，先查口径，不要先改数
-- ------------------------------------------------------------
SELECT
    COUNT(*)                                                          AS total_orders,
    SUM(order_status = 'delivered')                                   AS delivered,
    SUM(review_score IS NOT NULL)                                     AS reviewed,
    SUM(is_late_1d = 1)                                               AS late_1d,
    SUM(is_late_1d IS NOT NULL)                                       AS late_denominator,
    ROUND(AVG(days_fulfill), 2)                                       AS avg_fulfill,
    ROUND(AVG(days_to_carrier), 2)                                    AS avg_to_carrier,
    ROUND(AVG(days_vs_estimate), 2)                                   AS avg_delay
FROM wide_orders;
