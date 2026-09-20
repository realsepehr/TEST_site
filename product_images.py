import os
import re
import sqlite3
import threading
import uuid
from html import unescape
from urllib.parse import quote_plus, urljoin, urlparse
from urllib.request import Request, urlopen

SOURCE_SEARCH = "https://citysazeh.com/?s={query}&post_type=product"
USER_AGENT = "Mozilla/5.0 (compatible; HafezProductImageResolver/3.0)"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = BASE_DIR
os.makedirs(IMAGE_DIR, exist_ok=True)
_lock = threading.Lock()
_pending = set()
_workers_started = False
_queue = []
_queue_event = threading.Event()


def _get(url, timeout=15):
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.7", "Accept": "text/html,application/xhtml+xml"})
    with urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


def _download_image(url, timeout=20):
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.7", "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"})
    with urlopen(req, timeout=timeout) as r:
        data = r.read(8 * 1024 * 1024 + 1)
        if len(data) > 8 * 1024 * 1024:
            return None
        content_type = (r.headers.get("Content-Type") or "").lower()
    if not data:
        return None
    if "image/jpeg" in content_type or data.startswith(b"\xff\xd8\xff"):
        ext = "jpg"
    elif "image/png" in content_type or data.startswith(b"\x89PNG"):
        ext = "png"
    elif "image/webp" in content_type or (data[:4] == b"RIFF" and data[8:12] == b"WEBP"):
        ext = "webp"
    else:
        return None
    filename = f"upload_remote_{uuid.uuid4().hex}.{ext}"
    with open(os.path.join(IMAGE_DIR, filename), "wb") as f:
        f.write(data)
    return filename


def _product_links(html):
    links = re.findall(r'(?:href|data-href)=["\']([^"\']+)["\']', html, flags=re.I)
    result = []
    seen = set()
    for link in links:
        link = unescape(link).strip()
        if not link:
            continue
        absolute = urljoin("https://citysazeh.com/", link)
        parsed = urlparse(absolute)
        if parsed.netloc.lower().removeprefix("www.") != "citysazeh.com":
            continue
        if "/product/" not in parsed.path.lower():
            continue
        absolute = absolute.split("#", 1)[0]
        if absolute not in seen:
            seen.add(absolute)
            result.append(absolute)
    return result


def _norm(value):
    value = unescape(str(value or "")).lower().replace("ي", "ی").replace("ك", "ک")
    return re.sub(r"[^0-9a-z\u0600-\u06ff]+", "", value)


def _first_product_url(html, model="", name="", color=""):
    links = _product_links(html)
    model_key = _norm(model)
    name_key = _norm(name)
    color_key = _norm(color)
    if model_key:
        exact = [link for link in links if model_key in _norm(urlparse(link).path)]
        if exact:
            return exact[0]
    if name_key:
        scored = []
        for link in links:
            path_key = _norm(urlparse(link).path)
            score = 0
            if name_key and name_key in path_key:
                score += 10
            if color_key and color_key in path_key:
                score += 3
            if score:
                scored.append((score, link))
        if scored:
            return sorted(scored, reverse=True)[0][1]
    return links[0] if links else None


def _meta_content(html, prop):
    patterns = [
        rf'<meta[^>]+property=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']{re.escape(prop)}["\']',
        rf'<meta[^>]+name=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']{re.escape(prop)}["\']',
    ]
    for pattern in patterns:
        m = re.search(pattern, html, flags=re.I)
        if m:
            return unescape(m.group(1)).strip()
    return None


def _image_candidates(html, base_url):
    candidates = []
    for prop in ("og:image", "og:image:secure_url", "twitter:image", "twitter:image:src"):
        value = _meta_content(html, prop)
        if value:
            candidates.append(value)
    for attr in ("data-large_image", "data-src", "data-lazy-src", "data-image", "src"):
        for value in re.findall(rf'{attr}=["\']([^"\']+)["\']', html, flags=re.I):
            value = unescape(value).strip()
            if value and not value.startswith("data:"):
                candidates.append(value)
    for match in re.findall(r'"image"\s*:\s*(\[[^\]]+\]|"[^"]+")', html, flags=re.I | re.S):
        candidates.extend(re.findall(r'https?://[^"\'\s,]+', match))
    result = []
    seen = set()
    for value in candidates:
        absolute = urljoin(base_url, value).split("#", 1)[0]
        parsed = urlparse(absolute)
        if parsed.scheme not in ("http", "https"):
            continue
        lower = absolute.lower()
        if any(x in lower for x in ("logo", "icon", "avatar", "placeholder", "woocommerce-placeholder")):
            continue
        if absolute not in seen:
            seen.add(absolute)
            result.append(absolute)
    return result


def resolve_product_image(product):
    model = (product["model"] or "").strip()
    color = (product["color"] or "").strip()
    name = (product["name"] or "").strip()
    queries = []
    for query in (f"{model} {color}" if model and color else "", model, name):
        if query and query not in queries:
            queries.append(query)
    for query in queries:
        try:
            search_html = _get(SOURCE_SEARCH.format(query=quote_plus(query)))
            product_url = _first_product_url(search_html, model=model, name=name, color=color)
            if not product_url:
                continue
            page_html = _get(product_url)
            images = _image_candidates(page_html, product_url)
            if images:
                return images[0]
        except Exception:
            continue
    return None


def _cache_external_image(db_path, product_id, image_url):
    try:
        filename = _download_image(image_url)
        if not filename:
            return None
        c = sqlite3.connect(db_path)
        c.execute("UPDATE products SET image=? WHERE id=?", (filename, product_id))
        c.commit()
        c.close()
        return filename
    except Exception:
        return None


def _local_image_exists(image):
    if not image or image.startswith("http://") or image.startswith("https://"):
        return False
    return os.path.isfile(os.path.join(IMAGE_DIR, os.path.basename(image)))


def resolve_and_cache(db_path, product_id):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    p = c.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    c.close()
    if not p:
        return None
    current = (p["image"] or "").strip()
    if current.startswith("http://") or current.startswith("https://"):
        return _cache_external_image(db_path, product_id, current) or current
    if current and _local_image_exists(current):
        return current
    image = resolve_product_image(p)
    if image:
        return _cache_external_image(db_path, product_id, image)
    return None


def _worker():
    while True:
        _queue_event.wait()
        while True:
            with _lock:
                if not _queue:
                    _queue_event.clear()
                    break
                db_path, product_id = _queue.pop(0)
            key = (db_path, product_id)
            try:
                resolve_and_cache(db_path, product_id)
            except Exception:
                pass
            finally:
                with _lock:
                    _pending.discard(key)


def _ensure_workers():
    global _workers_started
    with _lock:
        if _workers_started:
            return
        _workers_started = True
        for i in range(3):
            threading.Thread(target=_worker, daemon=True, name=f"product-image-worker-{i}").start()


def request_resolve_async(db_path, product_id):
    _ensure_workers()
    key = (db_path, int(product_id))
    with _lock:
        if key in _pending:
            return
        _pending.add(key)
        _queue.append(key)
        _queue_event.set()


def warm_missing_images(db_path):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    rows = c.execute("SELECT id,image FROM products WHERE active=1").fetchall()
    c.close()
    for row in rows:
        image = (row["image"] or "").strip()
        if not image or image.startswith("http://") or image.startswith("https://") or not _local_image_exists(image):
            request_resolve_async(db_path, row["id"])


def start_warmup(db_path):
    threading.Thread(target=warm_missing_images, args=(db_path,), daemon=True, name="product-image-warmup").start()
