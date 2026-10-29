"""DV-IAS points-svc：积分子图（账户/流水/幂等入账/事件消费）。"""
import sys
import threading
import time

sys.path.insert(0, "/srv")

import httpx
from strawberry.fastapi import GraphQLRouter

from szxc_common.web import create_app, gql_context
from szxc_common import db
from app.schema import schema
from app.repo import init_db, ensure_accounts, earn, GOV_URL

app = create_app("points")
app.include_router(GraphQLRouter(schema, context_getter=gql_context), prefix="/graphql")

_cursor = {"last": 0}


def _poll_loop():
    while True:
        try:
            r = httpx.get(f"{GOV_URL}/internal/approved", params={"after": _cursor["last"]},
                          timeout=5)
            for ev in r.json().get("events", []):
                earn(ev["reporter_id"], f"evt-{ev['id']}", ev["type"])
                _cursor["last"] = max(_cursor["last"], ev["id"])
        except Exception:
            pass  # 治理服务暂不可达：下一轮重试（最终一致，P8）
        time.sleep(3)


@app.on_event("startup")
def _init():
    init_db()
    ensure_accounts()
    threading.Thread(target=_poll_loop, daemon=True).start()
