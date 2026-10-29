"""DV-IAS governance-svc：乡村治理子图（事件闭环状态机）。"""
import sys

sys.path.insert(0, "/srv")

from strawberry.fastapi import GraphQLRouter
from fastapi import Request
from fastapi.responses import JSONResponse

from szxc_common.web import create_app, gql_context
from app.schema import schema
from app.repo import init_db, seed_if_empty, approved_after

app = create_app("governance")
app.include_router(GraphQLRouter(schema, context_getter=gql_context), prefix="/graphql")


@app.on_event("startup")
def _init():
    init_db()
    seed_if_empty()


@app.get("/internal/approved")
async def internal_approved(after: int = 0, request: Request = None):
    """供 points-svc 幂等拉取已办结事件（MVP轮询通道；正式通道为 Pulsar szxc/core/topics，见ADR-007）。"""
    rows = approved_after(after)
    return JSONResponse({"events": [
        {"id": r["id"], "reporter_id": r["reporter_id"], "type": r["type"],
         "approved_at": str(r["updated_at"])} for r in rows]})
