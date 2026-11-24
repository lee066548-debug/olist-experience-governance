# -*- coding: utf-8 -*-
"""Load the Olist CSVs into MySQL.

Credentials are read from environment variables — never hard-code a password
in a file that will be committed.

    export MYSQL_HOST=127.0.0.1
    export MYSQL_PORT=3306
    export MYSQL_USER=root
    export MYSQL_PASSWORD=your_password
    export MYSQL_DB=olist

Usage:
    1) drop the 9 Kaggle CSVs into ./olist_data/
    2) python 01_load_olist_mysql.py

Dependencies: pandas, sqlalchemy, pymysql, cryptography
"""

import os
import sys
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine, text

DB = {
    "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DB", "olist"),
}

DATA_DIR_NAME = "olist_data"

FILES = {
    "olist_customers_dataset.csv": "customers",
    "olist_geolocation_dataset.csv": "geolocation",
    "olist_order_items_dataset.csv": "order_items",
    "olist_order_payments_dataset.csv": "order_payments",
    "olist_order_reviews_dataset.csv": "order_reviews",
    "olist_orders_dataset.csv": "orders",
    "olist_products_dataset.csv": "products",
    "olist_sellers_dataset.csv": "sellers",
    "product_category_name_translation.csv": "product_category_name_translation",
}

DATE_COLS = {
    "orders": [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ],
    "order_reviews": ["review_creation_date", "review_answer_timestamp"],
    "order_items": ["shipping_limit_date"],
}


def find_data_dir() -> str:
    """Locate ./olist_data next to the script, in the cwd, or one level up."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, DATA_DIR_NAME),
        os.path.join(os.getcwd(), DATA_DIR_NAME),
        os.path.join(here, os.pardir, DATA_DIR_NAME),
        os.path.join(os.getcwd(), os.pardir, DATA_DIR_NAME),
    ]
    for c in candidates:
        c = os.path.abspath(c)
        if os.path.isdir(c) and any(f.lower().endswith(".csv") for f in os.listdir(c)):
            return c
    raise SystemExit(
        "Cannot find an 'olist_data' folder containing CSVs. Looked in:\n  "
        + "\n  ".join(os.path.abspath(c) for c in candidates)
    )


def main() -> None:
    if not DB["password"]:
        sys.exit(
            "MYSQL_PASSWORD is not set.\n"
            "  PowerShell: $env:MYSQL_PASSWORD='your_password'\n"
            "  bash:       export MYSQL_PASSWORD=your_password"
        )

    data_dir = find_data_dir()
    print(f"[info] data directory: {data_dir}")

    pwd = quote_plus(DB["password"])
    server_url = (
        f"mysql+pymysql://{DB['user']}:{pwd}@{DB['host']}:{DB['port']}/?charset=utf8mb4"
    )

    server = create_engine(server_url, pool_pre_ping=True)
    with server.begin() as conn:
        conn.execute(
            text(
                f"CREATE DATABASE IF NOT EXISTS `{DB['database']}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci"
            )
        )
    server.dispose()
    print(f"[ok] database `{DB['database']}` ready")

    url = (
        f"mysql+pymysql://{DB['user']}:{pwd}@{DB['host']}:{DB['port']}/"
        f"{DB['database']}?charset=utf8mb4"
    )
    engine = create_engine(url, pool_pre_ping=True)

    total = 0
    for fname, table_name in FILES.items():
        path = os.path.join(data_dir, fname)
        if not os.path.exists(path):
            print(f"[skip] {fname} not found")
            continue
        df = pd.read_csv(path)
        for col in DATE_COLS.get(table_name, []):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        df.to_sql(table_name, engine, if_exists="replace", index=False, chunksize=5000)
        total += len(df)
        print(f"[ok] {table_name:<34} {len(df):>9,d} rows")

    engine.dispose()
    print(f"\nDone: {DB['database']} — {total:,} rows loaded")


if __name__ == "__main__":
    main()
