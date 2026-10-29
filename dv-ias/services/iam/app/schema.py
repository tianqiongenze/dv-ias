"""iam GraphQL Federation 子图 Schema（SDL 契约见 schemas/iam.graphql）。"""
import strawberry

from szxc_common.web import issue_token, Exception429
from szxc_common.crypto import mask_phone
from . import repo


@strawberry.federation.type(keys=["code"])
class Organization:
    code: str
    name: str
    level: str

    @strawberry.field
    def parent(self) -> "Organization | None":
        r = repo.org(self.code)
        if r and r.get("parent_code"):
            p = repo.org(r["parent_code"])
            return Organization(**p) if p else None
        return None

    @strawberry.field
    def children(self) -> list["Organization"]:
        return [Organization(**r) for r in repo.org_children(self.code)]

    @classmethod
    def _resolve_reference(cls, code: str):
        r = repo.org(code)
        return cls(**r) if r else None


@strawberry.federation.type(keys=["id"])
class Party:
    id: strawberry.ID
    name: str
    role: str
    phone_masked: str
    org_code: str

    @strawberry.field
    def org(self) -> Organization | None:
        r = repo.org(self.org_code)
        return Organization(**r) if r else None

    @classmethod
    def _resolve_reference(cls, id: strawberry.ID):
        r = repo.party(int(id))
        if not r:
            return None
        return cls(id=str(r["id"]), name=r["name"], role=r["role"],
                   phone_masked=mask_phone(r["phone"]), org_code=r["org_code"])


@strawberry.type
class AuthToken:
    token: str
    name: str
    roles: list[str]
    party_id: strawberry.ID


@strawberry.type
class PartyPage:
    total: int
    items: list[Party]


def _ctx_party(info) -> Party | None:
    uid = info.context.get("user_id") or 0
    if not uid:
        return None
    r = repo.party(uid)
    if not r:
        return None
    return Party(id=str(r["id"]), name=r["name"], role=r["role"],
                 phone_masked=mask_phone(r["phone"]), org_code=r["org_code"])


@strawberry.type
class Query:
    @strawberry.field
    def org_tree(self) -> list[Organization]:
        def to_org(n: dict) -> Organization:
            o = Organization(code=n["code"], name=n["name"], level=n["level"])
            return o
        return [to_org(n) for n in repo.org_tree_cached()]

    @strawberry.field
    def party(self, id: strawberry.ID) -> Party | None:
        return Party._resolve_reference(id)

    @strawberry.field
    def parties(self, page: int = 1, size: int = 20, org_code: str | None = None) -> PartyPage:
        size = min(size, 100)
        where, args = "", ()
        if org_code:
            where, args = "WHERE org_code LIKE %s", (org_code + "%",)
        total = repo_count(where, args)
        rows = db_q(f"SELECT * FROM szxc_md.party {where} ORDER BY id LIMIT %s OFFSET %s",
                    args + (size, (max(page, 1) - 1) * size))
        items = [Party(id=str(r["id"]), name=r["name"], role=r["role"],
                       phone_masked=mask_phone_from_enc(r["phone_enc"]), org_code=r["org_code"]) for r in rows]
        return PartyPage(total=total, items=items)

    @strawberry.field
    def me(self, info) -> Party | None:
        return _ctx_party(info)


@strawberry.type
class Mutation:
    @strawberry.mutation
    def login(self, phone: str, password: str) -> AuthToken:
        from szxc_common import db as dbm
        from szxc_common.crypto import sm3
        ph = sm3(phone.encode())
        r = dbm.query("SELECT p.id,p.name,p.role,a.password_salt,a.password_hash "
                      "FROM szxc_md.party p JOIN szxc_md.account a ON a.party_id=p.id "
                      "WHERE p.phone_hash=%s AND a.status='active'", (ph,), one=True)
        if not r or repo.hash_password(password, r["password_salt"]) != r["password_hash"]:
            raise Exception429("UNAUTHENTICATED", "手机号或密码错误")
        roles = [r["role"]]
        return AuthToken(token=issue_token(r["id"], r["name"], roles), name=r["name"],
                         roles=roles, party_id=str(r["id"]))


# ── 小工具（避免循环依赖）──
def repo_count(where, args):
    from szxc_common import db as dbm
    r = dbm.query(f"SELECT COUNT(*) c FROM szxc_md.party {where}", args, one=True)
    return r["c"]


def db_q(sql, args):
    from szxc_common import db as dbm
    return dbm.query(sql, args)


def mask_phone_from_enc(enc: str):
    from szxc_common.crypto import sm4_decrypt
    try:
        return mask_phone(sm4_decrypt(enc))
    except Exception:
        return "***"


schema = strawberry.federation.Schema(query=Query, mutation=Mutation, enable_federation_2=True)
