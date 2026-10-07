"""
backend/database.py
Quản lý cơ sở dữ liệu SQLite / TiDB Cloud (MySQL).
"""

import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

logger = logging.getLogger("database")

DATABASE_URL = os.getenv("DATABASE_URL")
SQLITE_PATH = os.getenv("SQLITE_PATH", "gold_tracker.db")
VN_TZ = timezone(timedelta(hours=7))
TABLE = "gold_history"

def get_connection() -> Tuple[Any, str]:
    if DATABASE_URL:
        import pymysql
        # Kết nối tới TiDB Cloud / MySQL
        conn = pymysql.connect(
            read_default_file=None,
            cursorclass=pymysql.cursors.DictCursor,
            **pymysql.converters.urlparse(DATABASE_URL) if hasattr(pymysql.converters, "urlparse") else _parse_db_url(DATABASE_URL)
        )
        return conn, "mysql"
    
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn, "sqlite"

def _parse_db_url(url: str) -> dict:
    import urllib.parse as up
    result = up.urlparse(url)
    return {
        'host': result.hostname,
        'user': result.username,
        'password': result.password,
        'database': result.path[1:],
        'port': result.port or 4000,
        # Luôn bật cấu hình SSL an toàn để kết nối mượt mà với TiDB Cloud
        'ssl': {'ssl_ca': '/etc/ssl/certs/ca-certificates.crt'}
    }

def _ph(db_type: str) -> str:
    return "%s" if db_type == "mysql" else "?"

def init_db() -> bool:
    conn = None
    try:
        conn, db_type = get_connection()
        cursor = conn.cursor()
        
        if db_type == "mysql":
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {TABLE} (
                    date VARCHAR(10) PRIMARY KEY,
                    sjc_buy DOUBLE PRECISION,
                    sjc_sell DOUBLE PRECISION,
                    world_price DOUBLE PRECISION,
                    sjc_predict_sell DOUBLE PRECISION,
                    world_predict DOUBLE PRECISION
                )
                """
            )
        else:
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {TABLE} (
                    date VARCHAR(10) PRIMARY KEY,
                    sjc_buy REAL,
                    sjc_sell REAL,
                    world_price REAL,
                    sjc_predict_sell REAL,
                    world_predict REAL
                )
                """
            )
        conn.commit()
        
        _auto_fill_past_real_data()
        return True
    except Exception as exc:
        logger.error("Lỗi init_db: %s", exc)
        if conn: conn.rollback()
        return False
    finally:
        if conn: conn.close()

def _auto_fill_past_real_data():
    """Tự cào lịch sử thật XAU/USD đến trước hoặc bằng ngày hôm nay."""
    try:
        import yfinance as yf
        now = datetime.now(VN_TZ).date()
        start = now - timedelta(days=35)
        
        df = yf.Ticker("GC=F").history(start=start.strftime("%Y-%m-%d"), end=(now + timedelta(days=1)).strftime("%Y-%m-%d"))
        if df.empty: return

        conn, db_type = get_connection()
        cursor = conn.cursor()
        ph = _ph(db_type)

        for date_idx, row in df.iterrows():
            d_str = date_idx.strftime("%Y-%m-%d")
            if d_str > now.strftime("%Y-%m-%d"):
                continue

            close_usd = round(float(row['Close']), 2)
            sjc_est_sell = round((close_usd * 25400 * 1.20565) / 1e6 + 2.5, 2)
            sjc_est_buy = round(sjc_est_sell - 2.0, 2)

            if db_type == "mysql":
                sql = (
                    f"INSERT INTO {TABLE} (date, sjc_buy, sjc_sell, world_price) "
                    f"VALUES ({ph}, {ph}, {ph}, {ph}) "
                    f"ON DUPLICATE KEY UPDATE "
                    f"sjc_buy = COALESCE({TABLE}.sjc_buy, VALUES(sjc_buy)), "
                    f"sjc_sell = COALESCE({TABLE}.sjc_sell, VALUES(sjc_sell)), "
                    f"world_price = COALESCE({TABLE}.world_price, VALUES(world_price))"
                )
            else:
                sql = (
                    f"INSERT INTO {TABLE} (date, sjc_buy, sjc_sell, world_price) "
                    f"VALUES ({ph}, {ph}, {ph}, {ph}) "
                    f"ON CONFLICT (date) DO UPDATE SET "
                    f"sjc_buy = COALESCE({TABLE}.sjc_buy, excluded.sjc_buy), "
                    f"sjc_sell = COALESCE({TABLE}.sjc_sell, excluded.sjc_sell), "
                    f"world_price = COALESCE({TABLE}.world_price, excluded.world_price)"
                )
            cursor.execute(sql, (d_str, sjc_est_buy, sjc_est_sell, close_usd))

        conn.commit()
        conn.close()
    except Exception as exc:
        logger.error("Không thể cào dữ liệu quá khứ: %s", exc)

def save_real_prices(
    date_str: str,
    sjc_buy: float = None,
    sjc_sell: float = None,
    world_price: float = None,
) -> bool:
    values = {"sjc_buy": sjc_buy, "sjc_sell": sjc_sell, "world_price": world_price}
    fields = {k: v for k, v in values.items() if v is not None}
    if not fields:
        return False
    
    conn = None
    try:
        conn, db_type = get_connection()
        cursor = conn.cursor()
        ph = _ph(db_type)
        cols = ["date"] + list(fields)
        
        if db_type == "mysql":
            sql = (
                f"INSERT INTO {TABLE} ({', '.join(cols)}) VALUES ({', '.join([ph] * len(cols))}) "
                f"ON DUPLICATE KEY UPDATE "
                + ", ".join(f"{c} = VALUES({c})" for c in fields)
            )
        else:
            sql = (
                f"INSERT INTO {TABLE} ({', '.join(cols)}) VALUES ({', '.join([ph] * len(cols))}) "
                f"ON CONFLICT (date) DO UPDATE SET "
                + ", ".join(f"{c} = excluded.{c}" for c in fields)
            )
        cursor.execute(sql, (date_str, *fields.values()))

        cutoff_date = (datetime.now(VN_TZ).date() - timedelta(days=35)).strftime("%Y-%m-%d")
        cursor.execute(f"DELETE FROM {TABLE} WHERE date < {ph}", (cutoff_date,))

        conn.commit()
        return True
    except Exception as exc:
        logger.error("Lỗi ghi dữ liệu ngày %s: %s", date_str, exc)
        if conn: conn.rollback()
        return False
    finally:
        if conn: conn.close()

def save_predicted_prices(forecast_sjc: List[Dict], forecast_world: List[Dict]) -> bool:
    conn = None
    try:
        conn, db_type = get_connection()
        cursor = conn.cursor()
        ph = _ph(db_type)
        
        preds = {}
        for item in forecast_sjc:
            preds.setdefault(item["date"], {})["sjc_predict_sell"] = item.get("sell")
        for item in forecast_world:
            preds.setdefault(item["date"], {})["world_predict"] = item.get("sell")

        for d_str, val in preds.items():
            s_pred = val.get("sjc_predict_sell")
            w_pred = val.get("world_predict")
            
            if db_type == "mysql":
                sql = (
                    f"INSERT INTO {TABLE} (date, sjc_predict_sell, world_predict) "
                    f"VALUES ({ph}, {ph}, {ph}) "
                    f"ON DUPLICATE KEY UPDATE "
                    f"sjc_predict_sell = COALESCE(VALUES(sjc_predict_sell), {TABLE}.sjc_predict_sell), "
                    f"world_predict = COALESCE(VALUES(world_predict), {TABLE}.world_predict)"
                )
            else:
                sql = (
                    f"INSERT INTO {TABLE} (date, sjc_predict_sell, world_predict) "
                    f"VALUES ({ph}, {ph}, {ph}) "
                    f"ON CONFLICT (date) DO UPDATE SET "
                    f"sjc_predict_sell = COALESCE(excluded.sjc_predict_sell, {TABLE}.sjc_predict_sell), "
                    f"world_predict = COALESCE(excluded.world_predict, {TABLE}.world_predict)"
                )
            cursor.execute(sql, (d_str, s_pred, w_pred))

        conn.commit()
        return True
    except Exception as exc:
        logger.error("Lỗi lưu giá dự đoán: %s", exc)
        if conn: conn.rollback()
        return False
    finally:
        if conn: conn.close()

def get_history_by_week(week: int = 1) -> List[Dict[str, Any]]:
    conn = None
    try:
        conn, db_type = get_connection()
        cursor = conn.cursor()
        ph = _ph(db_type)

        now = datetime.now(VN_TZ).date()
        this_monday = now - timedelta(days=now.weekday())

        start_date = this_monday - timedelta(weeks=week - 1)
        end_date = start_date + timedelta(days=6)

        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        sql = f"SELECT * FROM {TABLE} WHERE date >= {ph} AND date <= {ph} ORDER BY date ASC"
        cursor.execute(sql, (start_str, end_str))
        rows = [dict(r) for r in cursor.fetchall()]

        date_map = {r["date"]: r for r in rows}
        
        last_sjc_buy = None
        last_sjc_sell = None
        last_world_price = None

        full_week = []
        for i in range(7):
            d = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
            
            if d in date_map:
                row = date_map[d]
                if row.get("sjc_buy") is not None: last_sjc_buy = row.get("sjc_buy")
                if row.get("sjc_sell") is not None: last_sjc_sell = row.get("sjc_sell")
                if row.get("world_price") is not None: last_world_price = row.get("world_price")
                
                full_week.append(row)
            else:
                full_week.append({
                    "date": d,
                    "sjc_buy": last_sjc_buy,
                    "sjc_sell": last_sjc_sell,
                    "world_price": last_world_price,
                    "sjc_predict_sell": None,
                    "world_predict": None
                })
        return full_week
    except Exception as exc:
        logger.error("Lỗi đọc lịch sử tuần %s: %s", week, exc)
        return []
    finally:
        if conn: conn.close()

def get_yesterday_price() -> Dict[str, Any]:
    yesterday_str = (datetime.now(VN_TZ) - timedelta(days=1)).strftime("%Y-%m-%d")
    conn = None
    try:
        conn, db_type = get_connection()
        cursor = conn.cursor()
        ph = _ph(db_type)
        cursor.execute(f"SELECT * FROM {TABLE} WHERE date = {ph}", (yesterday_str,))
        row = cursor.fetchone()
        if row:
            return dict(row)
    except Exception as exc:
        logger.error("Lỗi đọc giá hôm qua: %s", exc)
    finally:
        if conn: conn.close()
    return {}