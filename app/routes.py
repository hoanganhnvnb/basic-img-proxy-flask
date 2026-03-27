from flask import Blueprint, current_app, jsonify, request, Response

from app.proxy_service import fetch_remote_image

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    return {
        "ok": True,
        "service": "flask-image-proxy",
        "usage": {
            "health": "/health",
            "proxy": "/img?url=https://example.com/image.jpg",
        },
    }


@bp.get("/health")
def health():
    return {"status": "healthy"}


@bp.get("/img")
def proxy_image():
    url = request.args.get("url", "").strip()

    if not url:
        return jsonify({"error": "Missing query param: url"}), 400

    result = fetch_remote_image(
        url=url,
        timeout=current_app.config["PROXY_TIMEOUT"],
        enable_cache=current_app.config["ENABLE_CACHE"],
        cache_dir=current_app.config["CACHE_DIR"],
    )

    if "error" in result:
        return jsonify(result["error"]), result["status_code"]

    return Response(
        result["body"],
        status=result["status_code"],
        headers=result["headers"],
        direct_passthrough=True,
    )