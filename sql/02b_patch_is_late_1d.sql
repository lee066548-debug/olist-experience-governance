-- ============================================================
-- 02b_patch_is_late_1d.sql（MySQL 5.7 / 8.0）
-- 目的：给 wide_orders 增加“晚于承诺 1 天以上”的延迟字段，
--       让仓库代码能复现报告里的 6.8%（原 is_late 是“晚于承诺即算”，= 8.1%）
-- 用法：在 02_build_wide_table_mysql.sql 之后执行一次。
--       如果是重建表，建议直接把下面的 CASE 写进 02 的 INSERT，避免再跑 UPDATE。
-- ============================================================

ALTER TABLE wide_orders
    ADD COLUMN is_late_1d TINYINT NULL
    COMMENT '1=晚于承诺1天以上（报告口径） 0=准时/提前 NULL=缺时间'
    AFTER is_late;

UPDATE wide_orders
SET is_late_1d = CASE
    WHEN days_vs_estimate IS NULL THEN NULL
    WHEN days_vs_estimate > 1     THEN 1
    ELSE 0
END;

CREATE INDEX idx_wide_late1d ON wide_orders (is_late_1d);


-- ------------------------------------------------------------
-- 附：重建表时直接写进 02 的写法（把下面这段加到 02 的列定义和 SELECT 里）
-- ------------------------------------------------------------
-- 列定义：
--     is_late      TINYINT NULL COMMENT '1晚于承诺即算 0准时 NULL缺时间',
--     is_late_1d   TINYINT NULL COMMENT '1晚于承诺1天以上 0准时 NULL缺时间',
--
-- SELECT 里：
--     CASE
--         WHEN o.order_delivered_customer_date IS NULL
--           OR o.order_estimated_delivery_date IS NULL THEN NULL
--         WHEN TIMESTAMPDIFF(HOUR, o.order_estimated_delivery_date,
--                                  o.order_delivered_customer_date) > 24 THEN 1
--         ELSE 0
--     END AS is_late_1d,
