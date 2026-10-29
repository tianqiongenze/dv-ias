# -*- coding: utf-8 -*-
"""DV-IAS 无头浏览器全端全链路功能测试（Playwright，补充用例）。
覆盖三端页面渲染 + 完整业务闭环（登录→上报→流转→积分→可视）。
以 JSON 行输出每步结论，结尾 FAIL 计数。
"""
import json, sys, traceback, base64, os
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "/ms-playwright"
from playwright.sync_api import sync_playwright

GW = "http://gw-svc.szxc-prod.svc.cluster.local:8080/"
WEB = "http://web-svc.szxc-prod.svc.cluster.local:80/"
RESULTS = []
FAIL = [0]


def rec(name, ok, extra=""):
    tag = "PASS" if ok else "FAIL"
    if not ok:
        FAIL[0] += 1
    RESULTS.append("%s | %s | %s" % (tag, name, extra))
    print(RESULTS[-1], flush=True)


def gql(page, query, token=None, timeout=20000):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    resp = page.request.post(GW, data=json.dumps({"query": query}), headers=headers,
                             timeout=timeout)
    return json.loads(resp.text())


def gql_rest(page, url, body, token=None, timeout=20000):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    resp = page.request.post(url, data=json.dumps(body), headers=headers, timeout=timeout)
    try:
        return json.loads(resp.text())
    except Exception:
        return {"raw": resp.text()}


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page()

        # ── 1. H5 村民端渲染 ──
        try:
            page.goto(WEB, timeout=25000)
            page.wait_for_load_state("networkidle", timeout=20000)
            title = page.title()
            rec("H5首页加载", "数字乡村" in title and page.locator("body").inner_text().strip() != "", title[:40])
        except Exception as e:
            rec("H5首页加载", False, str(e)[:80])

        # ── 2. 管理端渲染 ──
        try:
            page.goto(WEB + "admin", timeout=25000)
            page.wait_for_load_state("domcontentloaded", timeout=20000)
            rec("管理端加载", page.locator("body").inner_text().strip() != "", page.title()[:40])
        except Exception as e:
            rec("管理端加载", False, str(e)[:80])

        # ── 3. 指挥大屏渲染 ──
        try:
            page.goto(WEB + "screen", timeout=25000)
            page.wait_for_load_state("domcontentloaded", timeout=20000)
            rec("大屏加载", page.locator("body").inner_text().strip() != "", page.title()[:40])
        except Exception as e:
            rec("大屏加载", False, str(e)[:80])

        # ── 4. 全链路业务闭环（通过浏览器发起 GraphQL）──
        # 4.1 登录
        login = gql(page, 'mutation { login(phone: "13800000001", password: "szxc@2026") { token name } }')
        tok = ((login.get("data") or {}).get("login") or {}).get("token", "")
        rec("村民登录", bool(tok), login.get("data", {}).get("login", {}).get("name", ""))
        if not tok:
            browser.close()
            return
        # 4.2 上报
        ev = gql(page, 'mutation { reportEvent(type: "environment", villageCode: "53060010101", desc: "e2e-browser") { id sn state } }', tok)
        eid = (ev.get("data") or {}).get("reportEvent", {}).get("id")
        rec("随手拍上报", bool(eid), "id=%s" % eid)
        # 4.3 管理登录+流转
        alogin = gql(page, 'mutation { login(phone: "13900000001", password: "szxc@2026") { token } }')
        atok = ((alogin.get("data") or {}).get("login") or {}).get("token", "")
        states = []
        for act, f in [("受理", "acceptEvent"), ("派单", "dispatchEvent"), ("办结", "resolveEvent"), ("审核", "approveEvent")]:
            q = 'mutation { %s(id: %s) { id state } }' % (f, eid)
            r = gql(page, q, atok)
            st = (r.get("data") or {}).get(f, {}).get("state")
            states.append("%s:%s" % (act, st))
        rec("事件四步流转", len(states) == 4 and all(":" in s and s.split(":")[1] for s in states), "; ".join(states))
        # 4.4 积分（轮询等待入账）
        import time
        balance = None
        for _ in range(12):
            mp = gql(page, "{ myPoints { balance } }", tok)
            balance = (mp.get("data") or {}).get("myPoints", {}).get("balance")
            if balance:
                break
            time.sleep(2)
        rec("积分入账", balance is not None and balance >= 20, "balance=%s" % balance)
        # 4.5 联邦跨域
        fp = gql(page, '{ party(id: 58) { name pointsAccount { balance } } }', tok)
        fed = (fp.get("data") or {}).get("party", {})
        rec("联邦跨域查询", "pointsAccount" in fed and fed.get("name"), json.dumps(fed, ensure_ascii=False)[:80])
        # 4.6 指标
        met = gql(page, "{ metrics { name value unit } }", atok)
        ms = (met.get("data") or {}).get("metrics", [])
        rec("指标快照", len(ms) >= 5, "metrics=%d" % len(ms))
        # 4.7 AI问答（agent REST /chat，降级链）
        chat = gql_rest(page, "http://agent-svc.szxc-prod.svc.cluster.local:8000/chat",
                        {"query": "办理低保需要什么材料？"}, tok, timeout=30000)
        ans = chat.get("answer", "") if isinstance(chat, dict) else ""
        rec("AI问答", bool(ans), str(ans)[:60])
        # 4.8 村务公开
        pub = gql(page, '{ publications(villageCode: "53060010101") { id title } }', tok)
        pubs = (pub.get("data") or {}).get("publications", [])
        rec("村务公开列表", isinstance(pubs, list), "count=%d" % len(pubs))
        # 4.9 登录错误鉴权
        bad = gql(page, 'mutation { login(phone: "13800000001", password: "wrong") { token } }')
        rec("错误口令拒绝", bool(bad.get("errors")), str((bad.get("errors") or [{}])[0].get("message", ""))[:40])
        browser.close()

    print("SUMMARY fail=%d total=%d" % (FAIL[0], len(RESULTS)), flush=True)
    sys.exit(1 if FAIL[0] else 0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("FATAL", traceback.format_exc()[-800:], flush=True)
        sys.exit(1)