import hashlib
import mimetypes
from pathlib import Path
from urllib.parse import urlparse

import requests

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}

PASSTHROUGH_RESPONSE_HEADERS = {
    "content-type",
    "content-length",
    "content-disposition",
    "content-encoding",
    "cache-control",
    "etag",
    "last-modified",
    "expires",
    "accept-ranges",
}


def is_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def build_request_headers(img_url: str) -> dict:
    parsed = urlparse(img_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": origin + "/",
        "Origin": origin,
    }


def filter_response_headers(upstream_headers):
    headers = []
    for key, value in upstream_headers.items():
        key_lower = key.lower()

        if key_lower in HOP_BY_HOP_HEADERS:
            continue

        if key_lower in PASSTHROUGH_RESPONSE_HEADERS:
            headers.append((key, value))

    return headers


def build_cache_path(cache_dir: str, img_url: str) -> Path:
    parsed = urlparse(img_url)
    suffix = Path(parsed.path).suffix or ".bin"
    digest = hashlib.sha256(img_url.encode("utf-8")).hexdigest()
    return Path(cache_dir) / f"{digest}{suffix}"


def guess_content_type(file_path: Path) -> str:
    content_type, _ = mimetypes.guess_type(str(file_path))
    return content_type or "application/octet-stream"


def raw_stream(upstream, chunk_size=8192):
    try:
        for chunk in upstream.raw.stream(chunk_size, decode_content=False):
            if chunk:
                yield chunk
    finally:
        upstream.close()


def fetch_remote_image(url: str, timeout: int, enable_cache: bool, cache_dir: str):
    if not is_valid_url(url):
        return {
            "error": {"error": "Invalid url"},
            "status_code": 400,
        }

    try:
        cache_path = None

        if enable_cache:
            Path(cache_dir).mkdir(parents=True, exist_ok=True)
            cache_path = build_cache_path(cache_dir, url)

            if cache_path.exists():
                return {
                    "body": open(cache_path, "rb"),
                    "status_code": 200,
                    "headers": [("Content-Type", guess_content_type(cache_path))],
                }

        headers = build_request_headers(url)

        session = requests.Session()
        upstream = session.get(
            url,
            headers=headers,
            stream=True,
            timeout=timeout,
            allow_redirects=True,
        )

        content_type = upstream.headers.get("Content-Type", "")
        if upstream.status_code == 200 and not content_type.lower().startswith("image/"):
            upstream.close()
            session.close()
            return {
                "error": {
                    "error": "URL did not return an image",
                    "content_type": content_type,
                },
                "status_code": 415,
            }

        response_headers = filter_response_headers(upstream.headers)

        if enable_cache and cache_path and upstream.status_code == 200:
            with open(cache_path, "wb") as f:
                for chunk in upstream.raw.stream(8192, decode_content=False):
                    if chunk:
                        f.write(chunk)

            upstream.close()
            session.close()

            return {
                "body": open(cache_path, "rb"),
                "status_code": 200,
                "headers": [
                    ("Content-Type", upstream.headers.get("Content-Type", guess_content_type(cache_path))),
                ],
            }

        return {
            "body": raw_stream(upstream),
            "status_code": upstream.status_code,
            "headers": response_headers,
        }

    except requests.exceptions.Timeout:
        return {
            "error": {"error": "Upstream timeout"},
            "status_code": 504,
        }
    except requests.exceptions.RequestException as exc:
        return {
            "error": {
                "error": "Upstream request failed",
                "detail": str(exc),
            },
            "status_code": 502,
        }