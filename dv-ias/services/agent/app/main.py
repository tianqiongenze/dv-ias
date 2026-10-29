"""DV-IAS agent-runtime：数字乡村大脑（RAG问答 + LiteLLM路由 + 降级链 + MCP调用 + AgentCard）。

降级链（07号文档）：Milvus向量检索 → 本地关键词FAQ → 模板兜底；LLM：LiteLLM(qwen2.5:14b本地) → 模板。
"""
import os
import sys
import json
import time

sys.path.insert(0, "/srv")

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

REQ = Counter("szxc_agent_requests_total", "agent请求", ["kind", "status"])
LAT = Histogram("szxc_agent_chat_seconds", "问答耗时")

LITELLM = os.environ.get("LITELLM_URL", "http://litellm.ai-platform.svc.cluster.local:4000")
MODEL = os.environ.get("LLM_MODEL", "qwen2.5:14b")
MCP_URL = os.environ.get("MCP_URL", "http://mcp-svc.szxc-prod.svc.cluster.local:8000")

# ── 知识库（MVP：内置语料；生产走 Milvus 摄取管道，见07号文档§3）──
KB = [
    {"id": "k1", "q": "低保申请", "a": "申请低保请到村委会领取或在小程序填报《最低生活保障申请表》，需提供：身份证、户口本、收入证明。村初审后报乡镇民政办，20个工作日内反馈。"},
    {"id": "k2", "q": "耕地地力保护补贴", "a": "耕地地力保护补贴每年5-6月发放，按确权耕地面积核算，标准以当年县农业农村局公告为准。可在「公共服务-补贴查询」查看个人发放记录。"},
    {"id": "k3", "q": "水稻病虫害 稻瘟病", "a": "稻瘟病防治：发病初期选用75%三环唑可湿性粉剂每亩20-30克兑水喷雾，间隔7天连防2次；避免偏施氮肥，浅水勤灌。安全间隔期不少于21天。"},
    {"id": "k4", "q": "证明开具 无犯罪 亲属关系", "a": "亲属关系证明、居住证明等可在「公共服务-证明开具」在线申请，村干部审核后生成带电子签章的PDF证明，可扫码核验，一般1个工作日办结。"},
    {"id": "k5", "q": "积分 兑换", "a": "参与随手拍上报、环境整治等治理活动可获得积分（环境类20分/件、安全类30分/件），积分可在积分商城兑换生活用品，在「我的-积分明细」查询流水。"},
    {"id": "k6", "q": "垃圾堆放 举报", "a": "发现垃圾堆放、道路积水等问题，请在首页点「随手拍」拍照上报，系统自动派单至网格员，办结后您将获得积分奖励并可在「我的上报」查看进度。"},
    {"id": "k7", "q": "宅基地 申请", "a": "宅基地申请需为本集体经济组织成员、符合「一户一宅」，向村委会提出书面申请，经村民代表会议讨论通过后报乡镇审批，全程可在小程序跟踪。"},
    {"id": "k8", "q": "远程医疗 视频会诊", "a": "小程序「远程医疗」可预约乡镇卫生院与县医院医生的视频会诊，预约成功后会收到会议链接短信，按时间进入即可，无需到院排队。"},
]


def retrieve(question: str, top_k: int = 3) -> list:
    """混合检索MVP：BM25近似（词频重合）打分；生产为 Milvus HNSW + BM25 RRF 融合。"""
    def tok(s):
        return [s[i:i + 2] for i in range(len(s) - 1)]  # 中文二元组
    qt = tok(question)
    scored = []
    for item in KB:
        doc = tok(item["q"] + item["a"])
        overlap = sum(1 for t in set(qt) if t in doc)
        scored.append((overlap, item))
    scored.sort(key=lambda x: -x[0])
    return [x[1] for x in scored[:top_k] if x[0] >= 2]  # 重合度阈值：过滤偶然单字命中


def call_llm(question: str, context: str) -> tuple[str, bool]:
    prompt = (f"你是数字乡村智能助手「村村通」。仅依据以下资料回答，资料不足以回答时明确说明并建议联系村委会。"
              f"回答控制在150字内。\n【资料】{context}\n【村民提问】{question}")
    try:
        r = httpx.post(f"{LITELLM}/v1/chat/completions",
                       json={"model": MODEL, "messages": [{"role": "user", "content": prompt}],
                             "max_tokens": 300, "temperature": 0.3}, timeout=25)
        ans = r.json()["choices"][0]["message"]["content"]
        if ans and len(ans) > 5:
            return ans, True
    except Exception:
        pass
    return "", False


app = FastAPI(title="dv-agent-runtime")


@app.post("/chat")
async def chat(req: Request):
    body = await req.json()
    q = (body.get("question") or "").strip()[:500]
    if not q:
        return JSONResponse({"answer": "请描述您的问题", "refs": [], "engine": "none"}, status_code=200)
    t0 = time.time()
    refs = retrieve(q)
    context = "\n".join(f"[{r['id']}] {r['a']}" for r in refs) or "（无相关资料）"
    ans, llm_ok = call_llm(q, context)
    engine = "llm+rag" if llm_ok and refs else ("llm" if llm_ok else "faq")
    if not llm_ok:
        ans = refs[0]["a"] if refs else "这个问题我还需要学习，请联系村委会或拨打服务热线 0871-6800000。"
    LAT.observe(time.time() - t0)
    REQ.labels(engine, "ok").inc()
    return {"answer": ans, "refs": [{"id": r["id"], "q": r["q"]} for r in refs], "engine": engine}


@app.get("/.well-known/agent.json")
async def agent_card():
    """A2A Agent Card（06号文档§5 预留）。"""
    return {
        "name": "dv-cunzuntong-agent", "description": "数字乡村智能助手（农技/政策/办事/治理）",
        "url": f"http://agent-svc.szxc-prod.svc.cluster.local:8000", "version": "1.0.0",
        "capabilities": {"chat": True, "streaming": False},
        "skills": [{"id": "agri", "name": "农技问答"}, {"id": "gov", "name": "办事引导"},
                   {"id": "report", "name": "治理上报引导"}],
        "mcp_server": MCP_URL,
    }


@app.get("/healthz")
async def healthz():
    return {"status": "up"}


@app.get("/metrics")
async def metrics():
    return JSONResponse(generate_latest().decode(), media_type=CONTENT_TYPE_LATEST)
