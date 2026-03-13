#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import argparse
import pickle
import tempfile
from pathlib import Path

import h5py
import pymysql


LOAD_COLUMNS = """
symbol,
exchange,
datetime,
`interval`,
volume,
turnover,
open_interest,
open_price,
high_price,
low_price,
close_price
"""


def load_instrument_exchange_map(pk_path: str) -> dict[str, str]:
    with open(pk_path, "rb") as f:
        obj = pickle.load(f)

    mapping: dict[str, str] = {}

    if isinstance(obj, list):
        for item in obj:
            if not isinstance(item, dict):
                continue
            order_book_id = item.get("order_book_id")
            exchange = item.get("exchange")
            if order_book_id:
                mapping[str(order_book_id).strip()] = str(exchange or "").strip().upper()
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, dict):
                exchange = v.get("exchange", "")
                mapping[str(k).strip()] = str(exchange or "").strip().upper()
    else:
        raise TypeError(f"Unsupported instruments.pk type: {type(obj)}")

    return mapping


def normalize_dt(raw_dt) -> str:
    s = str(raw_dt).strip()
    s = s[:8]
    if len(s) != 8 or not s.isdigit():
        raise ValueError(f"invalid datetime: {raw_dt}")
    return f"{s[:4]}-{s[4:6]}-{s[6:8]} 00:00:00"


def export_h5_to_csv(h5_path: str, csv_path: str, exchange_map: dict[str, str]) -> tuple[int, int, int]:
    rows = 0
    datasets = 0
    missing_exchange = 0

    with h5py.File(h5_path, "r") as f, open(csv_path, "w", encoding="utf-8", newline="") as out:
        for symbol in f.keys():
            ds = f[symbol]
            if not isinstance(ds, h5py.Dataset):
                continue

            datasets += 1
            exchange = exchange_map.get(symbol, "")
            if not exchange:
                missing_exchange += 1

            data = ds[:]
            cols = data.dtype.names
            if not cols:
                continue

            has_dt = "datetime" in cols
            has_open = "open" in cols
            has_high = "high" in cols
            has_low = "low" in cols
            has_close = "close" in cols
            has_volume = "volume" in cols
            has_turnover = "total_turnover" in cols or "turnover" in cols
            has_oi = "open_interest" in cols

            if not (has_dt and has_open and has_high and has_low and has_close):
                continue

            for r in data:
                try:
                    dt = normalize_dt(r["datetime"])
                    volume = r["volume"] if has_volume else 0
                    turnover = r["total_turnover"] if "total_turnover" in cols else (r["turnover"] if "turnover" in cols else 0)
                    open_interest = r["open_interest"] if has_oi else 0

                    line = (
                        f"{symbol},{exchange},{dt},d,"
                        f"{volume},{turnover},{open_interest},"
                        f"{r['open']},{r['high']},{r['low']},{r['close']}\n"
                    )
                    out.write(line)
                    rows += 1
                except Exception:
                    continue

    return rows, datasets, missing_exchange


def get_conn():
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = int(os.getenv("DB_PORT", "3306"))
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    database = os.getenv("DB_NAME")

    if not user:
        raise ValueError("DB_USER is not set")
    if password is None:
        raise ValueError("DB_PASSWORD is not set")
    if not database:
        raise ValueError("DB_NAME is not set")

    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        charset="utf8mb4",
        autocommit=False,
        local_infile=True,
    )


def truncate_table(conn, table: str) -> None:
    with conn.cursor() as cur:
        cur.execute(f"TRUNCATE TABLE `{table}`")


def load_csv(conn, csv_path: str, table: str) -> int:
    sql = f"""
    LOAD DATA LOCAL INFILE %s
    INTO TABLE `{table}`
    CHARACTER SET utf8mb4
    FIELDS TERMINATED BY ','
    LINES TERMINATED BY '\\n'
    ({LOAD_COLUMNS})
    """
    with conn.cursor() as cur:
        cur.execute(sql, (csv_path,))
        return cur.rowcount or 0


def main():
    parser = argparse.ArgumentParser(description="Import rqalpha futures.h5 into MariaDB dbbardata")
    parser.add_argument("--h5", required=True, help="Path to futures.h5")
    parser.add_argument("--pk", required=True, help="Path to instruments.pk")
    parser.add_argument("--table", default=os.getenv("DB_TABLE", "dbbardata"))
    args = parser.parse_args()

    h5_path = Path(args.h5)
    pk_path = Path(args.pk)

    if not h5_path.exists():
        raise FileNotFoundError(h5_path)
    if not pk_path.exists():
        raise FileNotFoundError(pk_path)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    csv_path = tmp.name
    tmp.close()

    conn = None
    try:
        print("Loading instruments.pk ...")
        exchange_map = load_instrument_exchange_map(str(pk_path))
        print(f"Loaded exchange map: {len(exchange_map)}")

        print("Reading futures.h5 ...")
        rows, datasets, missing_exchange = export_h5_to_csv(str(h5_path), csv_path, exchange_map)
        print(f"Parsed rows={rows}, datasets={datasets}, missing_exchange_datasets={missing_exchange}")

        if rows == 0:
            raise RuntimeError("No rows parsed from futures.h5")

        conn = get_conn()

        print(f"Truncating table `{args.table}` ...")
        truncate_table(conn, args.table)

        print("Loading data into MariaDB ...")
        affected = load_csv(conn, csv_path, args.table)

        conn.commit()
        print(f"Import finished. affected_rows={affected}")

    except Exception:
        if conn is not None:
            conn.rollback()
        raise
    finally:
        if conn is not None:
            conn.close()
        Path(csv_path).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
