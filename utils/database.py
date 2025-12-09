import json
import tkinter as tk
from datetime import datetime
import sqlite3

from utils.helpers import Utils


class Database:
    @staticmethod
    def get_db(db):
        conn = sqlite3.connect(db, check_same_thread=False)
        return conn, conn.cursor()

    @staticmethod
    def initialize_cache_db(db):
        conn, cursor = Database.get_db(db)
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT, timestamp REAL)"
        )
        conn.commit()

        cursor.execute("PRAGMA user_version")
        version = cursor.fetchone()[0]

        if version < 1:
            cursor.execute("DELETE FROM cache")
            cursor.execute("PRAGMA user_version = 1")
            conn.commit()

        conn.close()

    @staticmethod
    def _expired_ts(ts, ceh):
        return datetime.now().timestamp() - ts > ceh * 3600

    @staticmethod
    def cache_get(db_key, db, ceh):
        conn, cursor = Database.get_db(db)
        cursor.execute("SELECT value, timestamp FROM cache WHERE key=?", (db_key,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        value, ts = row
        if Database._expired_ts(ts, ceh):
            Database.cache_delete(db_key, db)
            return None

        try:
            if isinstance(value, bytes):
                value = value.decode("utf-8")
            return json.loads(value)
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
            Database.cache_delete(db_key, db)
            return None

    @staticmethod
    def cache_set(db_key, value, db):
        conn, cursor = Database.get_db(db)
        safe_value = Database._ensure_json_serializable(value)
        blob = json.dumps(safe_value, ensure_ascii=False)
        ts = datetime.now().timestamp()
        cursor.execute("REPLACE INTO cache (key, value, timestamp) VALUES (?, ?, ?)", (db_key, blob, ts))
        conn.commit()
        conn.close()

    @staticmethod
    def cache_delete(db_key, db):
        conn, cursor = Database.get_db(db)
        cursor.execute("DELETE FROM cache WHERE key=?", (db_key,))
        conn.commit()
        conn.close()

    @staticmethod
    def clear_cache(db, rt, pgr):
        conn, cursor = Database.get_db(db)
        cursor.execute("DELETE FROM cache")
        conn.commit()
        conn.close()
        Utils.status_cb("Cache cleared successfully.", rt, pgr, level="good")

    @staticmethod
    def view_cache_stats(db, root):
        conn, cursor = Database.get_db(db)
        cursor.execute("SELECT COUNT(*), SUM(LENGTH(value)) FROM cache")
        count, size = cursor.fetchone()
        size = size if size else 0
        stats_window = tk.Toplevel(root)
        stats_window.title("Cache Statistics")
        tk.Label(stats_window, text=f"Cached Entries: {count}").pack()
        tk.Label(stats_window, text=f"Database Size: {size / 1024:.2f} KB").pack()

    @staticmethod
    def _ensure_json_serializable(value):
        if isinstance(value, dict):
            return {k: Database._ensure_json_serializable(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [Database._ensure_json_serializable(v) for v in value]
        if hasattr(value, "item"):
            try:
                return value.item()
            except Exception:
                pass
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)