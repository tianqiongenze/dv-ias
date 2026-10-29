"""portal GraphQL Federation 子图。"""
import strawberry

from szxc_common.web import Exception429, require_user
from szxc_common.cache import cached
from . import repo


@strawberry.federation.type(keys=["id"])
class Publication:
    id: strawberry.ID
    village_code: str
    column: str
    title: str
    content: str
    published_at: str | None

    @classmethod
    def _resolve_reference(cls, id: strawberry.ID):
        r = repo.get_pub(int(id))
        return cls(id=str(r["id"]), village_code=r["village_code"], column=r["column"],
                   title=r["title"], content=r["content"],
                   published_at=str(r["published_at"]) if r else None) if r else None


@strawberry.type
class PublicationPage:
    total: int
    items: list[Publication]


@strawberry.type
class Query:
    @strawberry.field
    def publications(self, village_code: str | None = None, column: str | None = None,
                     page: int = 1, size: int = 20) -> PublicationPage:
        size = min(size, 50)
        page = max(page, 1)

        def load():
            rows = repo.list_pub(village_code, column, page, size)
            total = repo.count_pub(village_code, column)
            return {"total": total, "items": [
                {"id": str(r["id"]), "village_code": r["village_code"], "column": r["column"],
                 "title": r["title"], "content": r["content"],
                 "published_at": str(r["published_at"])} for r in rows]}

        data = cached(f"pub:list:{village_code or 'all'}:{column or 'all'}:{page}:{size}",
                      120, load, l1_ttl=15)
        return PublicationPage(total=data["total"], items=[Publication(**i) for i in data["items"]])


@strawberry.type
class Mutation:
    @strawberry.mutation
    def publish_publication(self, info, village_code: str, column: str,
                            title: str, content: str) -> Publication:
        require_user(info, roles=["village_admin", "county_admin"])
        try:
            pid = repo.create_pub(village_code, column, title, content,
                                  info.context["user_id"])
        except ValueError as e:
            raise Exception429("VALIDATION", str(e))
        repo.invalidate_list()
        r = repo.get_pub(pid)
        return Publication(id=str(r["id"]), village_code=r["village_code"], column=r["column"],
                           title=r["title"], content=r["content"], published_at=str(r["published_at"]))


schema = strawberry.federation.Schema(query=Query, mutation=Mutation, enable_federation_2=True)
