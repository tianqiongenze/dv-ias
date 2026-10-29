"""data GraphQL 子图：指标快照（读池+缓存，口径见 05号文档数据服务）。"""
import strawberry

from szxc_common import db
from szxc_common.cache import cached


def _metrics_raw() -> dict:
    def q(sql):
        try:
            return db.query(sql, one=True)
        except Exception:
            return {}

    ev = q("SELECT COUNT(*) total, SUM(state='approved') done, SUM(state IN ('pending','accepted','dispatched')) open_ "
           "FROM szxc_biz.gov_event") or {}
    pub = q("SELECT COUNT(*) c FROM szxc_biz.publication WHERE status='published'") or {}
    pts = q("SELECT COALESCE(SUM(balance),0) s, COUNT(*) n FROM szxc_biz.points_account") or {}
    ppl = q("SELECT COUNT(*) c FROM szxc_md.party") or {}
    org = q("SELECT COUNT(*) c FROM szxc_md.org WHERE level='VILLAGE'") or {}
    total = ev.get("total") or 0
    done = ev.get("done") or 0
    return {
        "villager_total": ppl.get("c") or 0,
        "village_total": org.get("c") or 0,
        "event_total": total,
        "event_done_rate": round(done * 100.0 / total, 1) if total else 0.0,
        "event_open": ev.get("open_") or 0,
        "publication_total": pub.get("c") or 0,
        "points_total": pts.get("s") or 0,
        "points_account_total": pts.get("n") or 0,
    }


@strawberry.type
class MetricSnapshot:
    name: str
    value: float
    unit: str


@strawberry.type
class Query:
    @strawberry.field
    def metrics(self, names: list[str] | None = None) -> list[MetricSnapshot]:
        all_m = cached("dws:metrics:v1", 60, _metrics_raw, l1_ttl=15)
        out = []
        for k, v in all_m.items():
            if not names or k in names:
                unit = "%" if k.endswith("rate") else ""
                out.append(MetricSnapshot(name=k, value=float(v), unit=unit))
        return out


schema = strawberry.federation.Schema(query=Query, enable_federation_2=True)
