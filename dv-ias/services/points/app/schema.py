"""points GraphQL Federation 子图：向 Party 实体贡献 pointsAccount 字段。"""
import strawberry

from szxc_common.web import require_user, Exception429
from szxc_common.cache import cached
from . import repo


@strawberry.federation.type(keys=["partyId"])
class PointsAccount:
    party_id: strawberry.ID
    balance: int

    @strawberry.field
    def ledger(self) -> list["LedgerEntry"]:
        rows = repo.ledger(int(self.party_id))
        return [LedgerEntry(ref_id=r["ref_id"], change=r["change_amount"],
                            balance_after=r["balance_after"], reason=r["reason"],
                            created_at=str(r["created_at"])) for r in rows]

    @classmethod
    def _resolve_reference(cls, party_id: strawberry.ID):
        r = repo.account(int(party_id))
        if not r:
            return None
        return cls(party_id=str(r["party_id"]), balance=r["balance"])


@strawberry.type
class LedgerEntry:
    ref_id: str
    change: int
    balance_after: int
    reason: str | None
    created_at: str | None


@strawberry.federation.type(keys=["id"])
class Party:
    """向 iam 的 Party 实体贡献积分视图（联邦跨域组合）。"""
    id: strawberry.ID

    @strawberry.field
    def points_account(self) -> PointsAccount | None:
        r = repo.account(int(self.id))
        return PointsAccount(party_id=str(r["party_id"]), balance=r["balance"]) if r else None

    @classmethod
    def _resolve_reference(cls, id: strawberry.ID):
        return cls(id=id)


@strawberry.type
class Query:
    @strawberry.field
    def my_points(self, info) -> PointsAccount:
        ctx = require_user(info)
        r = repo.account(ctx["user_id"])
        if not r:
            raise Exception429("NOT_FOUND", "积分账户不存在")
        return PointsAccount(party_id=str(r["party_id"]), balance=r["balance"])

    @strawberry.field
    def leaderboard(self) -> list[PointsAccount]:
        return [PointsAccount(party_id=str(x["party_id"]), balance=x["balance"])
                for x in repo.leaderboard()]


schema = strawberry.federation.Schema(query=Query, enable_federation_2=True)
