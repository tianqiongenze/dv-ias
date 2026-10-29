"""DV-IAS Web 基建：应用工厂（健康/就绪/指标）、GraphQL 上下文与鉴权。"""
import os
import time

import jwt
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from . import db

REQ_TOTAL = Counter("szxc_http_requests_total", "HTTP请求总数", ["svc", "path", "code"])
REQ_LATENCY = Histogram("szxc_http_request_seconds", "HTTP延迟", ["svc", "path"])

JWT_SECRET = os.environ.get("JWT_SECRET", "SzxcJwt-2026-bN8wQ4vXzA6sD1fG")


def create_app(svc_name: str, startup=None) -> FastAPI:
    app = FastAPI(title=f"DV-IAS {svc_name}", docs_url=None, redoc_url=None)
    state = {"ready": False, "started": time.time()}

    @app.on_event("startup")
    async def _s():
        if startup:
            await startup() if hasattr(startup, "__await__") else startup()
        state["ready"] = True

    @app.get("/healthz")
    def healthz():
        return {"svc": svc_name, "status": "up", "uptime": int(time.time() - state["started"])}

    @app.get("/readyz")
    def readyz():
        if not state["ready"]:
            return PlainTextResponse("not ready", status_code=503)
        try:
            db.query("SELECT 1")
        except Exception as e:
            return PlainTextResponse(f"db: {e}", status_code=503)
        return {"ready": True}

    @app.get("/metrics")
    def metrics():
        return PlainTextResponse(generate_latest().decode(), media_type=CONTENT_TYPE_LATEST)

    @app.middleware("http")
    async def instrument(request: Request, call_next):
        start = time.time()
        resp = await call_next(request)
        path = request.url.path
        REQ_TOTAL.labels(svc_name, path, resp.status_code).inc()
        REQ_LATENCY.labels(svc_name, path).observe(time.time() - start)
        return resp

    return app


def gql_context(request: Request) -> dict:
    """GraphQL 上下文：信任网关注入的身份头（内网，00/06号文档安全模型）。
    x-user-name 由网关 Base64 编码（HTTP 头仅允许 ByteString），此处解码；兼容明文。"""
    import base64 as _b64
    _un = request.headers.get("x-user-name", "")
    try:
        _un = _b64.b64decode(_un, validate=True).decode("utf-8")
    except Exception:
        pass  # 明文直传（直连子图调试场景）
    return {
        "request": request,
        "user_id": int(request.headers.get("x-user-id") or 0),
        "user_name": _un,
        "user_roles": (request.headers.get("x-user-roles") or "").split(","),
    }


def issue_token(sub: int, name: str, roles: list, ttl_seconds: int = 86400 * 15) -> str:
    return jwt.encode({"sub": str(sub), "name": name, "roles": roles,
                       "exp": int(time.time()) + ttl_seconds}, JWT_SECRET, algorithm="HS256")


def require_user(info, roles: list = None):
    """鉴权断言：未登录/无角色 → GraphQL 业务错误（06号文档§3 错误码）。"""
    ctx = info.context
    if not ctx.get("user_id"):
        raise Exception429("UNAUTHENTICATED", "请先登录")
    if roles and not set(roles) & set(ctx.get("user_roles") or []):
        raise Exception429("FORBIDDEN", "无权限执行该操作")
    return ctx


class Exception429(Exception):
    def __init__(self, code: str, msg: str):
        self.code, self.msg = code, msg
        super().__init__(msg)
