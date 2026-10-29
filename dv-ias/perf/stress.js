// DV-IAS k6 负载/压力测试脚本（对 GraphQL 联邦网关 30085）
// 场景：browse-读高频、report-写、chat-agent、stress-爬坡压力
// 运行: k6 run -e GATEWAY=http://10.167.2.175:30085/ stress.js
import http from 'k6/http';
import { check, sleep } from 'k6';

const GW = __ENV.GATEWAY || 'http://gw-svc.szxc-prod.svc.cluster.local:8080/';
const VILLAGES = ['53060010101', '53060010102', '53060010103', '53060010201', '53060010202', '53060010203'];
const CATS = ['environment', 'safety', 'public', 'other'];

// 每 VU 懒加载自己的令牌（登录放函数内，__VU 仅在请求上下文可用；module 级 let 按 VU 隔离）
let _tok = '';
function tokenOf() {
  if (_tok) return _tok;
  const phone = '138' + String((__VU - 1) % 600 + 1).padStart(8, '0');
  const r = http.post(GW, JSON.stringify({ query: `mutation { login(phone: "${phone}", password: "szxc@2026") { token } }` }),
    { headers: { 'Content-Type': 'application/json' } });
  try { _tok = r.json().data.login.token; } catch (e) {}
  return _tok;
}
function hdr() {
  const t = tokenOf();
  return { 'Content-Type': 'application/json', ...(t ? { Authorization: 'Bearer ' + t } : {}) };
}

const BROWSE_Q = (v) => JSON.stringify({
  query: `{ metrics { name value unit } publications(villageCode: "${v}") { items { id title } } leaderboard { partyId balance } }`
});
const REPORT_Q = (v, n) => JSON.stringify({
  query: `mutation { reportEvent(type: "${CATS[n % 4]}", villageCode: "${v}", desc: "k6-stress-${n}") { id sn state } }`
});
const AGENT = __ENV.AGENT || 'http://agent-svc.szxc-prod.svc.cluster.local:8000/';
const CHAT_Q = JSON.stringify({ query: '办理低保需要什么材料？' });

export const options = {
  scenarios: {
    browse: {
      executor: 'ramping-vus', startVUs: 10,
      stages: [
        { duration: '1m', target: 200 },
        { duration: '2m', target: 200 },
        { duration: '1m', target: 300 },
        { duration: '2m', target: 300 },
        { duration: '30s', target: 0 },
      ],
      exec: 'browse',
    },
    report: {
      executor: 'constant-vus', vus: 30, duration: '4m', startTime: '1m', exec: 'report',
    },
    chat: {
      executor: 'constant-vus', vus: 20, duration: '4m', startTime: '1m', exec: 'chat',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    // 读场景 p95 目标 < 800ms；写与问答宽松
    'http_req_duration{scenario:browse}': ['p(95)<800'],
  },
};

export function browse() {
  const n = __ITER % 6;
  const r = http.post(GW, BROWSE_Q(VILLAGES[n]), { headers: hdr('villager') });
  check(r, { '200': (r) => r.status === 200 && !r.body.includes('errors') });
  sleep(0.3);
}

export function report() {
  const v = VILLAGES[__ITER % 6];
  const r = http.post(GW, REPORT_Q(v, __ITER), { headers: hdr('villager') });
  check(r, { 'reported': (r) => r.status === 200 && !r.body.includes('errors') });
  sleep(1);
}

export function chat() {
  const r = http.post(AGENT + 'chat', CHAT_Q, { headers: { 'Content-Type': 'application/json' } });
  check(r, { 'chat': (r) => r.status === 200 });
  sleep(1.5);
}