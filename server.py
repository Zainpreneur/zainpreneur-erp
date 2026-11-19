"""
Zainpreneur ERP — Python backend (stdlib only, zero install).

Endpoints:
  GET    /api/leads        -> list leads
  POST   /api/leads        -> create lead  (body: JSON)
  PUT    /api/leads/<id>   -> update lead  (body: JSON)
  DELETE /api/leads/<id>   -> delete lead
  GET    /api/health       -> health + storage mode

Storage (server-side, choose one):
  * Turso (libSQL) — set TURSO_DB_URL and TURSO_AUTH_TOKEN env vars
  * JSON file      — data/leads.json (default fallback, works immediately)

The Turso auth token never reaches the browser.
"""

import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DATA_FILE = os.path.join(DATA_DIR, "leads.json")

TURSO_DB_URL = os.environ.get("TURSO_DB_URL", "").strip()
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
TURSO_ENABLED = bool(TURSO_DB_URL and TURSO_AUTH_TOKEN)

os.makedirs(DATA_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Storage interface
# ---------------------------------------------------------------------------
class Storage:
    def init(self):
        raise NotImplementedError
    def list(self):
        raise NotImplementedError
    def get(self, lead_id):
        raise NotImplementedError
    def create(self, data):
        raise NotImplementedError
    def update(self, lead_id, data):
        raise NotImplementedError
    def delete(self, lead_id):
        raise NotImplementedError


# ---------------------------------------------------------------------------
# File-based storage (works out of the box)
# ---------------------------------------------------------------------------
class FileStorage(Storage):
    def _load(self):
        if not os.path.exists(DATA_FILE):
            return []
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save(self, rows):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2)

    def init(self):
        # Make sure the file exists
        self._save(self._load())
        return True

    def list(self):
        rows = self._load()
        rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return rows

    def get(self, lead_id):
        for r in self._load():
            if str(r.get("id")) == str(lead_id):
                return r
        return None

    def create(self, data):
        rows = self._load()
        new_id = max([int(r.get("id", 0)) for r in rows], default=0) + 1
        now = datetime.now(timezone.utc).isoformat()
        row = {"id": new_id, "created_at": now, "updated_at": now, **data}
        rows.append(row)
        self._save(rows)
        return row

    def update(self, lead_id, data):
        rows = self._load()
        for i, r in enumerate(rows):
            if str(r.get("id")) == str(lead_id):
                now = datetime.now(timezone.utc).isoformat()
                rows[i] = {"id": lead_id, **r, **data, "updated_at": now}
                self._save(rows)
                return rows[i]
        return None

    def delete(self, lead_id):
        rows = self._load()
        new_rows = [r for r in rows if str(r.get("id")) != str(lead_id)]
        if len(new_rows) == len(rows):
            return None
        self._save(new_rows)
        return lead_id


# ---------------------------------------------------------------------------
# Turso (libSQL) storage — token stays on the server
# ---------------------------------------------------------------------------
class TursoStorage(Storage):
    def __init__(self):
        self.url = TURSO_DB_URL.rstrip("/") + "/v1/pipeline"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + TURSO_AUTH_TOKEN,
            "Accept": "application/json",
        }

    def _request(self, stmt, args=None):
        body = json.dumps({"requests": [{"stmt": stmt, "args": args or []}]}).encode("utf-8")
        req = urllib.request.Request(
            self.url, data=body, headers=self.headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:300]
            raise RuntimeError(f"Turso HTTP {e.code}: {detail}")

    @staticmethod
    def _rows(result_set):
        if not result_set or not result_set.get("results"):
            return []
        rs = result_set["results"][0]
        cols = rs.get("columns", [])
        rows = rs.get("rows", [])
        out = []
        for row in rows:
            obj = {}
            for i, c in enumerate(cols):
                obj[c] = row[i] if i < len(row) else None
            out.append(obj)
        return out

    def init(self):
        self._request(
            """CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT, email TEXT, phone TEXT, company TEXT,
                status TEXT, source TEXT, value REAL, assigned_to TEXT,
                notes TEXT, created_at TEXT, updated_at TEXT)""",
            [],
        )
        return True

    def list(self):
        return self._rows(self._request("SELECT * FROM leads ORDER BY created_at DESC", []))

    def get(self, lead_id):
        rows = self._rows(self._request("SELECT * FROM leads WHERE id = ?", [lead_id]))
        return rows[0] if rows else None

    def create(self, data):
        now = datetime.now(timezone.utc).isoformat()
        row = {"created_at": now, "updated_at": now, **data}
        res = self._request(
            """INSERT INTO leads
               (name, email, phone, company, status, source, value, assigned_to, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                row.get("name"), row.get("email"), row.get("phone"), row.get("company"),
                row.get("status"), row.get("source"), row.get("value"), row.get("assigned_to"),
                row.get("notes"), row["created_at"], row["updated_at"],
            ],
        )
        meta = (res.get("results") or [{}])[0].get("meta", {})
        row["id"] = meta.get("last_row_id")
        return row

    def update(self, lead_id, data):
        now = datetime.now(timezone.utc).isoformat()
        self._request(
            """UPDATE leads
               SET name=?, email=?, phone=?, company=?, status=?, source=?,
                   value=?, assigned_to=?, notes=?, updated_at=?
               WHERE id = ?""",
            [
                data.get("name"), data.get("email"), data.get("phone"), data.get("company"),
                data.get("status"), data.get("source"), data.get("value"), data.get("assigned_to"),
                data.get("notes"), now, lead_id,
            ],
        )
        return {"id": lead_id, "updated_at": now, **data}

    def delete(self, lead_id):
        self._request("DELETE FROM leads WHERE id = ?", [lead_id])
        return lead_id


# ---------------------------------------------------------------------------
# Pick storage
# ---------------------------------------------------------------------------
storage = TursoStorage() if TURSO_ENABLED else FileStorage()
storage.init()
STORAGE_MODE = "turso" if TURSO_ENABLED else "file"


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------
def _json_response(handler, code, payload):
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.end_headers()
    handler.wfile.write(body)


def _read_body(handler):
    length = int(handler.headers.get("Content-Length", 0) or 0)
    if length == 0:
        return {}
    raw = handler.rfile.read(length)
    try:
        return json.loads(raw.decode("utf-8")) if raw else {}
    except Exception:
        return {}


class ERPHandler(BaseHTTPRequestHandler):
    server_version = "ZainpreneurERP/1.0"

    def log_message(self, format, *args):  # quiet default logging
        return

    # ----- CORS preflight -----
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/api/health":
            return _json_response(self, 200, {
                "status": "ok",
                "storage": STORAGE_MODE,
                "app": "Zainpreneur ERP",
                "version": "1.0.0",
            })

        if path == "/api/leads":
            try:
                leads = storage.list()
                return _json_response(self, 200, {"leads": leads, "count": len(leads)})
            except Exception as e:
                return _json_response(self, 500, {"error": str(e)})

        if path.startswith("/api/leads/"):
            lead_id = path.split("/")[-1]
            try:
                lead = storage.get(lead_id)
                if lead is None:
                    return _json_response(self, 404, {"error": "lead not found"})
                return _json_response(self, 200, {"lead": lead})
            except Exception as e:
                return _json_response(self, 500, {"error": str(e)})

        # Static files (index.html, css, js)
        rel = path.lstrip("/") or "index.html"
        file_path = os.path.join(BASE_DIR, rel)
        if not os.path.abspath(file_path).startswith(os.path.abspath(BASE_DIR)):
            return _json_response(self, 403, {"error": "forbidden"})
        if os.path.isfile(file_path):
            self.send_response(200)
            ext = os.path.splitext(file_path)[1].lower()
            ctype = {
                ".html": "text/html; charset=utf-8",
                ".css": "text/css; charset=utf-8",
                ".js": "application/javascript; charset=utf-8",
                ".json": "application/json; charset=utf-8",
            }.get(ext, "application/octet-stream")
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            with open(file_path, "rb") as f:
                self.wfile.write(f.read())
            return
        return _json_response(self, 404, {"error": "not found"})

    def _post_put(self, method):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        body = _read_body(self)

        if path == "/api/leads" and method == "POST":
            try:
                lead = storage.create(body)
                return _json_response(self, 201, {"lead": lead})
            except Exception as e:
                return _json_response(self, 500, {"error": str(e)})

        if path.startswith("/api/leads/") and method == "PUT":
            lead_id = path.split("/")[-1]
            try:
                lead = storage.update(lead_id, body)
                if lead is None:
                    return _json_response(self, 404, {"error": "lead not found"})
                return _json_response(self, 200, {"lead": lead})
            except Exception as e:
                return _json_response(self, 500, {"error": str(e)})

        return _json_response(self, 404, {"error": "not found"})

    def do_POST(self):
        self._post_put("POST")

    def do_PUT(self):
        self._post_put("PUT")

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path.startswith("/api/leads/"):
            lead_id = path.split("/")[-1]
            try:
                result = storage.delete(lead_id)
                if result is None:
                    return _json_response(self, 404, {"error": "lead not found"})
                return _json_response(self, 200, {"deleted": result})
            except Exception as e:
                return _json_response(self, 500, {"error": str(e)})
        return _json_response(self, 404, {"error": "not found"})


def main():
    port = int(os.environ.get("PORT", "4000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), ERPHandler)
    print(f"Zainpreneur ERP backend on http://0.0.0.0:{port}")
    print(f"Storage mode: {STORAGE_MODE}")
    if TURSO_ENABLED:
        print("Turso: enabled (token kept server-side)")
    else:
        print("Turso: not configured -> using data/leads.json fallback")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
