import pickle
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
        cursor.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value BLOB, timestamp REAL)")
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

        return pickle.loads(value)

    @staticmethod
    def cache_set(db_key, value, db):
        conn, cursor = Database.get_db(db)
        blob = pickle.dumps(value)
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