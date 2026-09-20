"""Cloudflare-native D1/R2 adapters with a SQLite fallback for local development."""
from __future__ import annotations

import io
import json
import mimetypes
import os
import uuid
from pathlib import Path
from flask import request

try:
    from pyodide.ffi import run_sync
except Exception:  # local development
    run_sync = None


def worker_env():
    try:
        return request.environ.get("workers.env")
    except RuntimeError:
        return None


def is_cloudflare():
    # The Wrangler var is present during Worker execution and also lets module
    # import-time code avoid starting local SQLite/background threads.
    return os.getenv("CLOUDFLARE_WORKERS", "0").lower() in {"1", "true", "yes"}


class D1Row(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


class D1Result:
    def __init__(self, rows=None, meta=None):
        self._rows = [D1Row(r) for r in (rows or [])]
        self.meta = meta or {}

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class D1Cursor:
    def __init__(self, database):
        self.database = database

    def execute(self, sql, params=()):
        stmt = self.database.prepare(sql)
        params = tuple(params or ())
        if params:
            stmt = stmt.bind(*params)
        upper = sql.lstrip().upper()
        if upper.startswith(("SELECT", "PRAGMA", "WITH", "EXPLAIN")):
            raw = run_sync(stmt.all())
            results = raw.results.to_py() if hasattr(raw.results, "to_py") else raw.results
            meta = raw.meta.to_py() if hasattr(raw.meta, "to_py") else getattr(raw, "meta", {})
            return D1Result(results, meta)
        raw = run_sync(stmt.run())
        meta = raw.meta.to_py() if hasattr(raw.meta, "to_py") else getattr(raw, "meta", {})
        return D1Result([], meta)

    def executescript(self, script):
        # D1 supports multi-statement migrations through Wrangler; this method is
        # intentionally kept only for compatibility with the old app bootstrap.
        for statement in [x.strip() for x in script.split(";") if x.strip()]:
            self.execute(statement)
        return D1Result()

    def commit(self):
        return None

    def close(self):
        return None


def get_db():
    if is_cloudflare():
        env = worker_env()
        if not hasattr(env, "DB"):
            raise RuntimeError("D1 binding DB is missing. Create/bind a D1 database first.")
        return D1Cursor(env.DB)
    import sqlite3
    base = Path(__file__).resolve().parent
    db_path = base / "instance" / "store.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    return c


def _mime(key, default="application/octet-stream"):
    return mimetypes.guess_type(key)[0] or default


def put_media(file_storage, prefix="products"):
    env = worker_env()
    if not is_cloudflare() or not hasattr(env, "MEDIA"):
        raise RuntimeError("R2 binding MEDIA is not configured.")
    filename = os.path.basename(file_storage.filename or "image")
    stem, ext = os.path.splitext(filename)
    ext = ext.lower() or ".bin"
    key = f"{prefix}/{uuid.uuid4().hex}{ext}"
    data = file_storage.stream.read()
    file_storage.stream.seek(0)
    options = {"httpMetadata": {"contentType": file_storage.mimetype or _mime(key)}}
    run_sync(env.MEDIA.put(key, data, options))
    return key


def get_media(key):
    env = worker_env()
    if not is_cloudflare() or not hasattr(env, "MEDIA"):
        return None
    obj = run_sync(env.MEDIA.get(key))
    if obj is None:
        return None
    body = run_sync(obj.body.arrayBuffer())
    data = body.to_py() if hasattr(body, "to_py") else body
    return bytes(data), _mime(key)


def delete_media(key):
    env = worker_env()
    if is_cloudflare() and hasattr(env, "MEDIA"):
        run_sync(env.MEDIA.delete(key))
        return True
    return False


def list_media(prefix=""):
    env = worker_env()
    if not is_cloudflare() or not hasattr(env, "MEDIA"):
        return []
    out = []
    cursor = None
    while True:
        opts = {"prefix": prefix, "limit": 1000}
        if cursor:
            opts["cursor"] = cursor
        result = run_sync(env.MEDIA.list(opts))
        objs = result.objects.to_py() if hasattr(result.objects, "to_py") else result.objects
        for obj in objs:
            row = obj if isinstance(obj, dict) else obj.to_py()
            out.append({
                "name": row.get("key", ""),
                "size": row.get("size", 0),
                "mtime": row.get("uploaded", ""),
            })
        truncated = result.truncated
        if hasattr(truncated, "to_py"):
            truncated = truncated.to_py()
        if not truncated:
            break
        cursor = result.cursor
        if hasattr(cursor, "to_py"):
            cursor = cursor.to_py()
    return out


def media_url(key):
    return "/media/" + str(key).lstrip("/") if key else ""
