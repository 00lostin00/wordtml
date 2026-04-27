"""
wordtml 本地服务
用法:python server.py  (默认端口 8080)
      python server.py 9000  (自定义端口)

除了静态文件,还提供少量本地 SQLite API,用于长期保存个人做题记录。
"""
import http.server
import json
import os
import socketserver
import sqlite3
import sys
import urllib.request
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).parent

def _load_env():
    for name in ("deepseek.env", ".env"):
        p = ROOT / name
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    k, v = k.strip(), v.strip()
                    if k and k not in os.environ:
                        os.environ[k] = v

_load_env()

PORT = int(os.environ.get("WORDTML_PORT") or (sys.argv[1] if len(sys.argv) > 1 else 8080))
HOST = os.environ.get("WORDTML_HOST") or (sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1")
DB_PATH = Path(os.environ.get("WORDTML_DB_PATH") or (ROOT / "wordtml.db"))


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    return conn


def init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS exam_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id TEXT NOT NULL,
            exam_type TEXT,
            mode TEXT NOT NULL DEFAULT 'exam',
            practice_unit_id TEXT,
            practice_type TEXT,
            started_at INTEGER,
            ended_at INTEGER,
            total_score INTEGER,
            answer_ready INTEGER NOT NULL DEFAULT 0,
            client_key TEXT,
            payload_json TEXT NOT NULL,
            created_at INTEGER NOT NULL DEFAULT (strftime('%s','now') * 1000)
        )
    """)
    ensure_column(conn, "exam_attempts", "client_key", "TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_exam_attempts_exam_id ON exam_attempts(exam_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_exam_attempts_ended_at ON exam_attempts(ended_at)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_exam_attempts_client_key ON exam_attempts(client_key)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS practice_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_id TEXT NOT NULL,
            exam_id TEXT NOT NULL,
            practice_type TEXT NOT NULL,
            title TEXT,
            source TEXT,
            payload_json TEXT NOT NULL,
            drawn_at INTEGER NOT NULL,
            created_at INTEGER NOT NULL DEFAULT (strftime('%s','now') * 1000)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_practice_history_drawn_at ON practice_history(drawn_at)")
    conn.commit()


def ensure_column(conn, table, column, ddl):
    cols = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def attempt_client_key(payload):
    return payload.get("localDbKey") or ":".join(str(x or "") for x in [
        payload.get("mode") or "exam",
        payload.get("examId"),
        payload.get("practiceUnitId"),
        payload.get("startedAt"),
        payload.get("endedAt"),
    ])


def json_response(handler, data, status=200):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def read_json_body(handler):
    length = int(handler.headers.get("Content-Length") or 0)
    if length <= 0:
        return {}
    raw = handler.rfile.read(length).decode("utf-8")
    return json.loads(raw or "{}")


def attempt_from_row(row):
    payload = json.loads(row["payload_json"])
    payload.setdefault("localDbId", row["id"])
    payload.setdefault("examId", row["exam_id"])
    payload.setdefault("examType", row["exam_type"])
    payload.setdefault("mode", row["mode"])
    return payload


def practice_from_row(row):
    payload = json.loads(row["payload_json"])
    payload.setdefault("localDbId", row["id"])
    payload.setdefault("id", row["unit_id"])
    payload.setdefault("examId", row["exam_id"])
    payload.setdefault("type", row["practice_type"])
    payload.setdefault("title", row["title"])
    payload.setdefault("source", row["source"])
    payload.setdefault("at", row["drawn_at"])
    return payload


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api_get(parsed)
            return
        if Path(parsed.path).name in {"wordtml.db", "wordtml.db-shm", "wordtml.db-wal"}:
            self.send_error(403, "Local database is private")
            return
        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api_post(parsed)
            return
        self.send_error(404, "Not found")

    def handle_api_get(self, parsed):
        try:
            if parsed.path == "/api/local/status":
                with db() as conn:
                    attempts = conn.execute("SELECT COUNT(*) AS n FROM exam_attempts").fetchone()["n"]
                    practices = conn.execute("SELECT COUNT(*) AS n FROM practice_history").fetchone()["n"]
                json_response(self, {
                    "ok": True,
                    "dbPath": str(DB_PATH),
                    "examAttempts": attempts,
                    "practiceHistory": practices,
                })
                return

            if parsed.path == "/api/exam-attempts":
                qs = parse_qs(parsed.query)
                limit = min(int((qs.get("limit") or ["200"])[0]), 1000)
                with db() as conn:
                    rows = conn.execute(
                        "SELECT * FROM exam_attempts ORDER BY ended_at DESC, id DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
                json_response(self, {"ok": True, "items": [attempt_from_row(row) for row in rows]})
                return

            if parsed.path == "/api/practice-history":
                qs = parse_qs(parsed.query)
                limit = min(int((qs.get("limit") or ["50"])[0]), 200)
                with db() as conn:
                    rows = conn.execute(
                        "SELECT * FROM practice_history ORDER BY drawn_at DESC, id DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
                json_response(self, {"ok": True, "items": [practice_from_row(row) for row in rows]})
                return

            if parsed.path == "/api/ai-chat/status":
                json_response(self, {
                    "ok": True,
                    "enabled": bool(os.environ.get("DEEPSEEK_API_KEY", "")),
                })
                return

            json_response(self, {"ok": False, "error": "unknown endpoint"}, 404)
        except Exception as e:
            json_response(self, {"ok": False, "error": str(e)}, 500)

    def handle_api_post(self, parsed):
        try:
            payload = read_json_body(self)
            if parsed.path == "/api/exam-attempts":
                client_key = attempt_client_key(payload)
                with db() as conn:
                    existing = conn.execute(
                        "SELECT * FROM exam_attempts WHERE client_key=?",
                        (client_key,),
                    ).fetchone()
                    if existing:
                        json_response(self, {"ok": True, "item": attempt_from_row(existing)})
                        return
                    cur = conn.execute("""
                        INSERT INTO exam_attempts (
                            exam_id, exam_type, mode, practice_unit_id, practice_type,
                            started_at, ended_at, total_score, answer_ready, client_key, payload_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        payload.get("examId") or "",
                        payload.get("examType"),
                        payload.get("mode") or "exam",
                        payload.get("practiceUnitId"),
                        payload.get("practiceType"),
                        payload.get("startedAt"),
                        payload.get("endedAt"),
                        payload.get("totalScore"),
                        1 if payload.get("answerReady") else 0,
                        client_key,
                        json.dumps(payload, ensure_ascii=False),
                    ))
                    conn.commit()
                    row = conn.execute("SELECT * FROM exam_attempts WHERE id=?", (cur.lastrowid,)).fetchone()
                json_response(self, {"ok": True, "item": attempt_from_row(row)}, 201)
                return

            if parsed.path == "/api/practice-history":
                drawn_at = payload.get("at") or payload.get("drawnAt")
                with db() as conn:
                    cur = conn.execute("""
                        INSERT INTO practice_history (
                            unit_id, exam_id, practice_type, title, source, payload_json, drawn_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        payload.get("id") or payload.get("unitId") or "",
                        payload.get("examId") or "",
                        payload.get("type") or payload.get("practiceType") or "",
                        payload.get("title"),
                        payload.get("source"),
                        json.dumps(payload, ensure_ascii=False),
                        drawn_at,
                    ))
                    conn.commit()
                    row = conn.execute("SELECT * FROM practice_history WHERE id=?", (cur.lastrowid,)).fetchone()
                json_response(self, {"ok": True, "item": practice_from_row(row)}, 201)
                return

            if parsed.path == "/api/ai-chat":
                messages = payload.get("messages", [])
                if not messages:
                    json_response(self, {"ok": False, "error": "no messages"}, 400)
                    return
                api_key = os.environ.get("DEEPSEEK_API_KEY", "")
                if not api_key:
                    json_response(self, {"ok": False, "error": "DEEPSEEK_API_KEY 未配置"}, 503)
                    return
                body = json.dumps({
                    "model": "deepseek-v4-flash",
                    "messages": [
                        {"role": "system", "content":
                         "你是一个英语学习助手，专门帮助用户学习英语词汇、做CET6/考研英语真题。"
                         "回答简洁清晰，中英文混用均可。"}
                    ] + messages,
                    "max_tokens": 1024,
                    "stream": False,
                }, ensure_ascii=False).encode("utf-8")
                req = urllib.request.Request(
                    "https://api.deepseek.com/chat/completions",
                    data=body,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}",
                    },
                )
                with urllib.request.urlopen(req, timeout=60) as r:
                    result = json.loads(r.read().decode("utf-8"))
                reply = result["choices"][0]["message"]["content"]
                json_response(self, {"ok": True, "reply": reply})
                return

            json_response(self, {"ok": False, "error": "unknown endpoint"}, 404)
        except Exception as e:
            json_response(self, {"ok": False, "error": str(e)}, 500)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))


class ThreadingTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True


def main():
    with db():
        pass
    with ThreadingTCPServer((HOST, PORT), Handler) as httpd:
        display_host = "127.0.0.1" if HOST in {"", "0.0.0.0", "::"} else HOST
        url = f"http://{display_host}:{PORT}/"
        print(f"wordtml serving at {url}")
        print(f"bind address: {HOST}:{PORT}")
        print(f"local database: {DB_PATH}")
        print("Ctrl+C to stop.")
        if os.environ.get("WORDTML_OPEN_BROWSER", "1") != "0" and display_host in {"127.0.0.1", "localhost"}:
            try:
                webbrowser.open(url)
            except Exception:
                pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped.")


if __name__ == "__main__":
    main()
