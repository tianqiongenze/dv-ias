"""governance GraphQL Federation 子图。"""
import strawberry

from szxc_common.web import Exception429, require_user
from . import repo


@strawberry.federation.type(keys=["id"])
class Party:
    """跨子图实体引用（与 iam 同名实体 Party，基础字段由 iam 子图提供）。"""
    id: strawberry.ID

    @classmethod
    def _resolve_reference(cls, id: strawberry.ID):
        return cls(id=id)


@strawberry.federation.type(keys=["id"])
class GovernanceEvent:
    id: strawberry.ID
    sn: str
    village_code: str
    type: str
    source: str
    state: str
    description: str | None
    geo_lat: float | None
    geo_lng: float | None
    created_at: str | None

    @strawberry.field
    def reporter(self) -> Party:
        r = repo.get(int(self.id))
        return Party(id=str(r["reporter_id"]))

    @strawberry.field
    def timeline(self) -> list["Transition"]:
        return [Transition(event_id=str(t["event_id"]), action=t["action"],
                           actor_id=str(t["actor_id"] or 0), note=t["note"] or "",
                           created_at=str(t["created_at"])) for t in repo.timeline(int(self.id))]

    @classmethod
    def _resolve_reference(cls, id: strawberry.ID):
        r = repo.get(int(id))
        return _to_type(r) if r else None


def _to_type(r) -> GovernanceEvent:
    return GovernanceEvent(id=str(r["id"]), sn=r["sn"], village_code=r["village_code"],
                           type=r["type"], source=r["source"], state=r["state"],
                           description=r["description"], geo_lat=r["geo_lat"], geo_lng=r["geo_lng"],
                           created_at=str(r["created_at"]))


@strawberry.type
class Transition:
    event_id: strawberry.ID
    action: str
    actor_id: strawberry.ID
    note: str
    created_at: str | None


@strawberry.type
class EventPage:
    total: int
    items: list[GovernanceEvent]


@strawberry.type
class Query:
    @strawberry.field
    def events(self, village_code: str | None = None, state: str | None = None,
               page: int = 1, size: int = 20) -> EventPage:
        size = min(size, 50)
        rows = repo.list_events(village_code, state, None, page, size)
        return EventPage(total=len(rows) if page == 1 and len(rows) < size else -1,
                         items=[_to_type(r) for r in rows])

    @strawberry.field
    def my_events(self, info, page: int = 1) -> EventPage:
        ctx = require_user(info)
        rows = repo.list_events(reporter_id=ctx["user_id"], page=page)
        return EventPage(total=len(rows), items=[_to_type(r) for r in rows])

    @strawberry.field
    def event(self, id: strawberry.ID) -> GovernanceEvent | None:
        r = repo.get(int(id))
        return _to_type(r) if r else None


@strawberry.type
class Mutation:
    @strawberry.mutation
    def report_event(self, info, type: str, village_code: str,
                     geo_lat: float = 0.0, geo_lng: float = 0.0, desc: str = "") -> GovernanceEvent:
        ctx = require_user(info)
        eid = repo.submit(village_code, type, "citizen", geo_lat, geo_lng, desc, ctx["user_id"])
        return _to_type(repo.get(eid))

    @strawberry.mutation
    def accept_event(self, info, id: strawberry.ID) -> GovernanceEvent:
        ctx = require_user(info, roles=["grid_admin", "village_admin", "county_admin"])
        return _apply(int(id), "accept", ctx)

    @strawberry.mutation
    def dispatch_event(self, info, id: strawberry.ID) -> GovernanceEvent:
        ctx = require_user(info, roles=["grid_admin", "village_admin", "county_admin"])
        return _apply(int(id), "dispatch", ctx)

    @strawberry.mutation
    def resolve_event(self, info, id: strawberry.ID, note: str = "") -> GovernanceEvent:
        ctx = require_user(info, roles=["grid_admin", "village_admin", "county_admin"])
        return _apply(int(id), "resolve", ctx, note)

    @strawberry.mutation
    def approve_event(self, info, id: strawberry.ID) -> GovernanceEvent:
        ctx = require_user(info, roles=["village_admin", "county_admin"])
        return _apply(int(id), "approve", ctx)


def _apply(eid, action, ctx, note="") -> GovernanceEvent:
    try:
        r = repo.transition(eid, action, ctx["user_id"], note)
    except ValueError as e:
        raise Exception429("VALIDATION", str(e))
    return _to_type(r)


schema = strawberry.federation.Schema(query=Query, mutation=Mutation, enable_federation_2=True)
