"""DV-IAS portal-svc：村务公开子图。"""
import sys

sys.path.insert(0, "/srv")

from strawberry.fastapi import GraphQLRouter

from szxc_common.web import create_app, gql_context
from app.schema import schema
from app.repo import init_db, seed_if_empty

app = create_app("portal")
app.include_router(GraphQLRouter(schema, context_getter=gql_context), prefix="/graphql")


@app.on_event("startup")
def _init():
    init_db()
    seed_if_empty()
