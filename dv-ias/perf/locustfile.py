# -*- coding: utf-8 -*-
"""DV-IAS Locust 性能测试（对 GraphQL 联邦网关 30085 与聚合读接口/SQL 服务）。
场景：浏览(读高频)、上报(写)、问答(agent)、登录。多用户并发，Web UI 实时聚合。
运行：locust -f locustfile.py --host=http://gw-svc.szxc-prod.svc.cluster.local:8080
"""
import random
import json
import time
from locust import HttpUser, task, between

VILLAGES = ["5306001010%d" % i for i in (1, 2, 3)] + ["5306001020%d" % i for i in (1, 2, 3)]
CATS = ["environment", "safety", "public", "other"]
TITLES = ["垃圾堆积", "道路破损", "路灯故障", "水管爆裂", "杂草丛生", "井盖缺失"]


def _post(client, query, name, token=None, variables=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    body = {"query": query}
    if variables:
        body["variables"] = variables
    return client.post("/", json=body, name=name, headers=headers)


class Villager(HttpUser):
    """村民端混合浏览：指标、村务公开、随手拍上报、积分查询、AI问答。"""
    wait_time = between(0.5, 2.0)
    token = ""

    def on_start(self):
        r = _post(self.client,
                  'mutation { login(phone: "13800000001", password: "szxc@2026") { token } }',
                  "login-villager")
        try:
            self.token = r.json()["data"]["login"]["token"]
        except Exception:
            self.token = ""

    @task(6)
    def metrics(self):
        _post(self.client, "{ metrics { name value unit } }", "metrics", self.token)

    @task(4)
    def publications(self):
        v = random.choice(VILLAGES)
        _post(self.client,
              '{ publications(villageCode: "%s") { items { id title } } }' % v, "publications", self.token)

    @task(3)
    def my_points(self):
        _post(self.client, "{ myPoints { balance } }", "myPoints", self.token)

    @task(3)
    def leaderboard(self):
        _post(self.client, "{ leaderboard { partyId balance } }", "leaderboard", self.token)

    @task(2)
    def report_event(self):
        _post(self.client,
              'mutation { reportEvent(type: "%s", villageCode: "%s", desc: "locust-%d") { id } }'
              % (random.choice(CATS), random.choice(VILLAGES), random.randint(1, 99999)),
              "reportEvent", self.token)

    @task(1)
    def chat_agent(self):
        import json as _json
        # 问答为 agent 独立 REST 服务（非网关 GraphQL），直连
        r = self.client.post("http://agent-svc.szxc-prod.svc.cluster.local:8000/chat",
                             json={"query": "办理低保需要什么材料？"}, name="chat-agent",
                             headers={"Content-Type": "application/json"})
        return r


class Admin(HttpUser):
    """管理端高频：事件处置状态查询与流转。"""
    wait_time = between(1, 3)
    token = ""

    def on_start(self):
        r = _post(self.client,
                  'mutation { login(phone: "13900000001", password: "szxc@2026") { token } }',
                  "login-admin")
        try:
            self.token = r.json()["data"]["login"]["token"]
        except Exception:
            self.token = ""

    @task(5)
    def events(self):
        _post(self.client, '{ events(state: "pending") { items { id sn } } }', "events-list", self.token)

    @task(3)
    def events_all(self):
        _post(self.client, "{ events { items { id state } } }", "events-all", self.token)

    @task(2)
    def publish(self):
        v = random.choice(VILLAGES)
        _post(self.client,
              'mutation { publishPublication(villageCode: "%s", column: "notice", title: "公告%d", content: "测试内容") { id } }'
              % (v, random.randint(1, 99999)),
              "publish", self.token)