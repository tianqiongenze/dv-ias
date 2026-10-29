"""DV-IAS data-svc：数据中台子图（大屏指标聚合，CQRS 读侧）。"""
import sys

sys.path.insert(0, "/srv")

from strawberry.fastapi import GraphQLRouter

from szxc_common.web import create_app, gql_context
from app.schema import schema

app = create_app("data")
app.include_router(GraphQLRouter(schema, context_getter=gql_context), prefix="/graphql")
