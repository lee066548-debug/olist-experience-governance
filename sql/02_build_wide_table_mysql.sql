-- ============================================================
-- 02_build_wide_table_mysql.sql（MySQL 5.7 / 8.0 通用）
-- 目的：把 9 张原始表拼成订单级分析宽表 wide_orders
-- 说明：显式定义字段类型 + 索引内联，可重复执行（先 DROP）
-- 前提：已用 01_load_olist_mysql.py 导入数据
-- ============================================================

-- ① 评价去重：同一订单可能有多条评价记录
DROP TABLE IF EXISTS review_dedup;
CREATE TABLE review_dedup (
    order_id         VARCHAR(64) NOT NULL,
    review_score_env INT         NULL,
    review_cnt       INT         NULL,
    review_ts        DATETIME    NULL,
    PRIMARY KEY (order_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_general_ci;

INSERT INTO review_dedup (order_id, review_score_env, review_cnt, review_ts)
SELECT
    order_id,
    MAX(review_score),
    COUNT(*),
    MAX(review_creation_date)
FROM order_reviews
GROUP BY order_id;

-- ② 商品聚合：一个订单可能多件商品，先压成订单级
DROP TABLE IF EXISTS item_agg;
CREATE TABLE item_agg (
    order_id       VARCHAR(64) NOT NULL,
    item_cnt       INT         NULL,
    seller_cnt     INT         NULL,
    product_id     VARCHAR(64) NULL,
    seller_id      VARCHAR(64) NULL,
    item_amount    DECIMAL(12, 2) NULL,
    freight_amount DECIMAL(12, 2) NULL,
    PRIMARY KEY (order_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_general_ci;

INSERT INTO item_agg (order_id, item_cnt, seller_cnt, product_id, seller_id,
                      item_amount, freight_amount)
SELECT
    order_id,
    COUNT(*),
    COUNT(DISTINCT seller_id),
    MIN(product_id),
    MIN(seller_id),
    CAST(SUM(price) AS DECIMAL(12, 2)),
    CAST(SUM(freight_value) AS DECIMAL(12, 2))
FROM order_items
GROUP BY order_id;

-- ③ 订单级宽表（字段类型显式声明，索引内联）
DROP TABLE IF EXISTS wide_orders;
CREATE TABLE wide_orders (
    order_id             VARCHAR(64) NOT NULL,
    customer_id          VARCHAR(64) NULL,
    customer_state       VARCHAR(8)  NULL,
    customer_city        VARCHAR(64) NULL,
    order_status         VARCHAR(32) NULL,

    ts_purchase          DATETIME NULL,
    ts_approved          DATETIME NULL,
    ts_carrier           DATETIME NULL,
    ts_delivered         DATETIME NULL,
    ts_estimated         DATETIME NULL,

    days_fulfill         DECIMAL(8, 2) NULL COMMENT '履约天数=签收-下单',
    days_vs_estimate     DECIMAL(8, 2) NULL COMMENT '延迟天数=签收-承诺',
    is_late              TINYINT       NULL COMMENT '1延迟 0准时 NULL缺时间',
    days_to_carrier      DECIMAL(8, 2) NULL COMMENT '发货时效=交承运商-下单',

    review_score         INT     NULL,
    is_bad_review        TINYINT NULL COMMENT '1差评(<=2星) 0非差评 NULL无评价',
    review_cnt           INT     NULL,

    item_cnt             INT     NULL,
    seller_cnt           INT     NULL,
    item_amount          DECIMAL(12, 2) NULL,
    freight_amount       DECIMAL(12, 2) NULL,
    order_amount         DECIMAL(12, 2) NULL,

    product_id           VARCHAR(64) NULL,
    product_category_name VARCHAR(96) NULL,
    category_en          VARCHAR(96) NULL,

    seller_id            VARCHAR(64) NULL,
    seller_state         VARCHAR(8)  NULL,

    PRIMARY KEY (order_id),
    KEY idx_wide_seller (seller_id),
    KEY idx_wide_cat (category_en),
    KEY idx_wide_state (customer_state),
    KEY idx_wide_status (order_status)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_general_ci;

INSERT INTO wide_orders (
    order_id, customer_id, customer_state, customer_city, order_status,
    ts_purchase, ts_approved, ts_carrier, ts_delivered, ts_estimated,
    days_fulfill, days_vs_estimate, is_late, days_to_carrier,
    review_score, is_bad_review, review_cnt,
    item_cnt, seller_cnt, item_amount, freight_amount, order_amount,
    product_id, product_category_name, category_en,
    seller_id, seller_state
)
SELECT
    o.order_id,
    o.customer_id,
    c.customer_state,
    c.customer_city,
    o.order_status,

    o.order_purchase_timestamp,
    o.order_approved_at,
    o.order_delivered_carrier_date,
    o.order_delivered_customer_date,
    o.order_estimated_delivery_date,

    -- 口径①：履约时长（天）= 签收 − 下单
    ROUND(TIMESTAMPDIFF(HOUR, o.order_purchase_timestamp,
                              o.order_delivered_customer_date) / 24.0, 2),

    -- 口径②：延迟天数 = 签收 − 承诺（>0 即延迟）
    ROUND(TIMESTAMPDIFF(HOUR, o.order_estimated_delivery_date,
                              o.order_delivered_customer_date) / 24.0, 2),

    -- 口径③：是否延迟（缺时间记 NULL，不进延迟率分母）
    CASE
        WHEN o.order_delivered_customer_date IS NULL
          OR o.order_estimated_delivery_date IS NULL THEN NULL
        WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 1
        ELSE 0
    END,

    -- 口径④：发货时效（下单 → 交承运商）
    ROUND(TIMESTAMPDIFF(HOUR, o.order_purchase_timestamp,
                              o.order_delivered_carrier_date) / 24.0, 2),

    -- 评价与差评标记
    r.review_score_env,
    CASE
        WHEN r.review_score_env IS NULL THEN NULL
        WHEN r.review_score_env <= 2    THEN 1
        ELSE 0
    END,
    r.review_cnt,

    -- 金额与商品
    i.item_cnt,
    i.seller_cnt,
    i.item_amount,
    i.freight_amount,
    CAST(COALESCE(i.item_amount, 0) + COALESCE(i.freight_amount, 0) AS DECIMAL(12, 2)),

    i.product_id,
    p.product_category_name,
    COALESCE(t.product_category_name_english, p.product_category_name),

    -- 卖家
    i.seller_id,
    s.seller_state

FROM orders o
LEFT JOIN customers c
       ON o.customer_id = c.customer_id
LEFT JOIN review_dedup r
       ON o.order_id = r.order_id
LEFT JOIN item_agg i
       ON o.order_id = i.order_id
LEFT JOIN products p
       ON i.product_id = p.product_id
LEFT JOIN product_category_name_translation t
       ON p.product_category_name = t.product_category_name
LEFT JOIN sellers s
       ON i.seller_id = s.seller_id;

-- ④ 自检
SELECT
    COUNT(*)                        AS total_orders,
    SUM(order_status = 'delivered') AS delivered,
    SUM(review_score IS NOT NULL)   AS reviewed,
    ROUND(AVG(days_fulfill), 2)     AS avg_days_fulfill,
    ROUND(AVG(days_vs_estimate), 2) AS avg_delay_days,
    ROUND(AVG(is_late), 3)          AS late_rate
FROM wide_orders;
