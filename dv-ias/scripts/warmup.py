"""DV-IAS Redis 缓存预热：驱动各服务真实查询回填共享缓存（冷启动≈0）。"""
import sys, time, json
sys.path.insert(0, "/srv")
import urllib.request, urllib.error

GW = "http://gw-svc.szxc-prod.svc.cluster.local:8080/"


def gql(url, query, headers=None):
    req = urllib.request.Request(url, data=json.dumps({"query": query}).encode(),
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        urllib.request.urlopen(req, timeout=20)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    t0 = time.time()
    try:
        login = json.loads(urllib.request.urlopen(urllib.request.Request(GW,
            data=json.dumps({"query": 'mutation { login(phone: "13800000001", password: "szxc@2026") { token name } }'}).encode(),
            headers={"Content-Type": "application/json"}), timeout=20).read())
        tok = (login.get("data") or {}).get("login", {}).get("token", "")
    except Exception:
        tok = ""
    auth = {"Authorization": "Bearer " + tok} if tok else {}
    calls = [
        "{ metrics { name value unit } }",
        "{ orgTree { code name } }",
        "{ party(id: 58) { name pointsAccount { balance } } }",
        "{ publications(villageCode: \"53060010101\") { id title } }",
        "{ events(state: \"pending\") { id sn } }",
        "{ leaderboard { partyId balance } }",
        "{ myPoints { balance } }",
        "{ parties(page: 1, size: 50, orgCode: \"53060010101\") { items { id name } } }",
    ]
    ok = sum(1 for q in calls if gql(GW, q, auth))
    print("WARMUP gw=%d/%d took=%ds" % (ok, len(calls), time.time() - t0), flush=True)