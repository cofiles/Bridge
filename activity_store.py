"""Local, transactional usage records and preferences."""
import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

class ActivityStore:
    def __init__(self, directory):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(directory / "activity.sqlite", check_same_thread=False)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY, started REAL, ended REAL, server TEXT, bytes INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS usage (day TEXT PRIMARY KEY, bytes INTEGER NOT NULL);
        """)

    def get(self, key, default=None):
        with self.lock:
            row = self.db.execute("SELECT value FROM preferences WHERE key=?", (key,)).fetchone()
            return json.loads(row[0]) if row else default

    def put(self, key, value):
        with self.lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO preferences VALUES (?,?)", (key, json.dumps(value)))

    def begin(self, server, now):
        with self.lock, self.db:
            return self.db.execute("INSERT INTO sessions(started,server) VALUES (?,?)", (now, server)).lastrowid

    def sample(self, session, count, now, end=False):
        day = datetime.fromtimestamp(now).strftime("%Y-%m-%d")
        with self.lock, self.db:
            row = self.db.execute("SELECT bytes FROM sessions WHERE id=?", (session,)).fetchone()
            if row is None:
                return
            delta = max(0, count - row[0])
            self.db.execute("UPDATE sessions SET bytes=?, ended=? WHERE id=?", (max(count,row[0]),now if end else None,session))
            self.db.execute("INSERT INTO usage VALUES (?,?) ON CONFLICT(day) DO UPDATE SET bytes=bytes+excluded.bytes", (day,delta))

    def report(self):
        day = datetime.now().strftime("%Y-%m-%d")
        with self.lock:
            today = self.db.execute("SELECT COALESCE(SUM(bytes),0) FROM usage WHERE day=?", (day,)).fetchone()[0]
            month = self.db.execute("SELECT COALESCE(SUM(bytes),0) FROM usage WHERE day LIKE ?", (day[:7]+"%",)).fetchone()[0]
            rows = self.db.execute("SELECT started,ended,server,bytes FROM sessions ORDER BY id DESC LIMIT 100").fetchall()
        return {"today":today,"month":month,"history":[dict(zip(("started","ended","server","bytes"),row)) for row in rows]}

    def reset(self):
        with self.lock, self.db:
            self.db.execute("PRAGMA secure_delete=ON")
            for table in ("preferences","sessions","usage"):
                self.db.execute("DELETE FROM "+table)
