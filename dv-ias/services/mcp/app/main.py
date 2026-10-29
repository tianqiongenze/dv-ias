"""DV-IAS mcp-dv-tools：MCP 工具层（JSON-RPC 2.0 / Streamable-HTTP 子集，06号文档§4）。

工具=白名单SQL/服务调用，全部审计（Pulsar szxc/core/audit.mcp 主题已建，MVP先落库审计表）。
"""
import sys
import time

sys.path.insert(0, "/srv")

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from szxc_common import db
from szxc_common.crypto import mask_phone

app = FastAPI(title="mcp-dv-tools")

TOOLS = [
    {"name": "query_points", "description": "查询村民积分余额与最近流水（需手机号）",
     "inputSchema": {"type": "object", "properties": {"phone": {"type": "string"}}, "required": ["phone"]}},
    {"name": "query_event_progress", "description": "按事件号查询处置进度",
     "inputSchema": {"type": "object", "properties": {"sn": {"type": "string"}}, "required": ["sn"]}},
    {"name": "search_service_guide", "description": "办事指南关键词检索",
     "inputSchema": {"type": "object", "properties": {"keyword": {"type": "string"}}, "required": ["keyword"]}},
    {"name": "query_village_metrics", "description": "查询村域治理指标快照",
     "inputSchema": {"type": "object", "properties": {"village_code": {"type": "string"}}}},
]

GUIDES = [
    {"title": "最低生活保障申请", "items": ["身份证", "户口本", "收入证明"], "dept": "乡镇民政办", "days": 20},
    {"title": "宅基地审批", "items": ["申请书", "户口本", "一户一宅声明"], "dept": "乡镇自然资源所", "days": 30},
    {"title": "亲属关系证明", "items": ["身份证", "户口本"], "dept": "村委会", "days": 1},
    {"title": "耕地地力保护补贴申领", "items": ["确权耕地信息", "一卡通账号"], "dept": "县农业农村局", "days": 15},
]


def _audit(tool: str, args: dict, ok: bool):
    try:
        db.execute("CREATE TABLE IF NOT EXISTS szxc_biz.mcp_audit("
                   "id BIGINT PRIMARY KEY AUTO_INCREMENT, tool VARCHAR(64), args_json TEXT,"
                   "ok TINYINT, created_at DATETIME)")
        db.execute("INSERT INTO szxc_biz.mcp_audit(tool,args_json,ok,created_at) VALUES(%s,%s,%s,NOW())",
                   (tool, str(args)[:500], 1 if ok else 0))
    except Exception:
        pass


def call_tool(name: str, args: dict):
    if name == "query_points":
        from szxc_common.crypto import sm3
        r = db.query("SELECT p.id,p.name,a.balance FROM szxc_md.party p "
                     "JOIN szxc_biz.points_account a ON a.party_id=p.id "
                     "WHERE p.phone_hash=%s", (sm3(args["phone"].encode()),), one=True)
        return {"found": bool(r), "party": mask_phone(args["phone"]), "balance": r["balance"] if r else None}
    if name == "query_event_progress":
        r = db.query("SELECT sn,state,created_at,updated_at FROM szxc_biz.gov_event WHERE sn=%s",
                     (args["sn"],), one=True)
        return {"found": bool(r), **(r or {})}
    if name == "search_service_guide":
        kw = args["keyword"]
        hits = [g for g in GUIDES if kw in g["title"] or any(kw in i for i in g["items"])]
        return {"count": len(hits), "guides": hits}
    if name == "query_village_metrics":
        code = args.get("village_code", "53060010101")
        r = db.query("SELECT COUNT(*) total, SUM(state='approved') done FROM szxc_biz.gov_event "
                     "WHERE village_code LIKE %s", (code + "%",), one=True)
        return {"village": code, "event_total": r["total"] or 0, "event_done": r["done"] or 0}
    raise ValueError(f"unknown tool: {name}")


@app.post("/mcp")
async def mcp(req: Request):
    body = await req.json()
    method, mid = body.get("method"), body.get("id")

    def result(r):
        return JSONResponse({"jsonrpc": "2.0", "id": mid, "result": r})

    if method == "initialize":
        return result({"protocolVersion": "2025-06-18", "serverInfo": {"name": "mcp-dv-tools", "version": "1.0.0"},
                       "capabilities": {"tools": {}}})
    if method == "tools/list":
        return result({"tools": TOOLS})
    if method == "tools/call":
        p = body.get("params", {})
        name, args = p.get("name"), p.get("arguments", {})
        try:
            out = call_tool(name, args)
            _audit(name, args, True)
            return result({"content": [{"type": "text", "text": str(out)}], "isError": False})
        except Exception as e:
            _audit(name, args, False)
            return result({"content": [{"type": "text", "text": f"工具调用失败: {e}"}], "isError": True})
    if method == "ping":
        return result({})
    return JSONResponse({"jsonrpc": "2.0", "id": mid,
                         "error": {"code": -32601, "message": f"method not found: {method}"}}, status_code=400)


@app.get("/healthz")
async def healthz():
    return {"status": "up"}


@app.get("/metrics")
async def metrics():
    return JSONResponse(generate_latest().decode(), media_type=CONTENT_TYPE_LATEST)
