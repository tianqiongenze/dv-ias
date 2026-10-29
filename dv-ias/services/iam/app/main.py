"""DV-IAS iam-svc：身份与组织子图（GraphQL Federation）。"""
import sys

sys.path.insert(0, "/srv")

from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

from szxc_common.web import create_app, gql_context
from app.schema import schema
from app.repo import init_db, seed_if_empty

app = create_app("iam")
app.include_router(GraphQLRouter(schema, context_getter=gql_context), prefix="/graphql")


@app.on_event("startup")
def _init():
    init_db()
    seed_if_empty()
