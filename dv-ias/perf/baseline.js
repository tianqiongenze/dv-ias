// DV-IAS k6 基线压测（13号文档 S1/S2 场景的CI级基线）
// 运行：k6 run -e GATEWAY=http://gw-svc.szxc-prod.svc.cluster.local:8080 baseline.js
import http from 'k6/http';
import { check, sleep } from 'k6';

const GATEWAY = __ENV.GATEWAY || 'http://gw-svc.szxc-prod.svc.cluster.local:8080';

export const options = {
  scenarios: {
    browse: {  // S1 公开浏览（读路径，验证多级缓存）
      executor: 'ramping-vus',
      startVUs: 5, stages: [
        { duration: '30s', target: 50 },
        { duration: '1m', target: 50 },
        { duration: '15s', target: 0 },
      ],
      exec: 'browse',
    },
    report: {  // S2 事件上报+登录（写路径）
      executor: 'constant-vus',
      vus: 10, duration: '1m', startTime: '30s', exec: 'report',
    },
  },
  thresholds: {
    'http_req_duration{scenario:browse}': ['p(95)<500'],
    'http_req_duration{scenario:report}': ['p(95)<800'],
    'http_req_failed': ['rate<0.05'],
  },
};

const BROWSE_Q = JSON.stringify({ query: '{publications(size:5){total items{title column}} metrics{name value}}' });

export function browse() {
  const r = http.post(GATEWAY, BROWSE_Q, { headers: { 'Content-Type': 'application/json' } });
  check(r, { 'pubs-200': (res) => res.status === 200 });
  sleep(1 + Math.random() * 3);
}

export function report() {
  // 登录取号（演示村民）
  const login = http.post(GATEWAY, JSON.stringify({
    query: 'mutation($p:String!,$w:String!){login(phone:$p,password:$w){token}}',
    variables: { p: '13800000001', w: 'szxc@2026' },
  }), { headers: { 'Content-Type': 'application/json' } });
  const token = login.json('data.login.token');
  check(login, { 'login-ok': () => !!token });
  if (!token) { sleep(1); return; }
  const r = http.post(GATEWAY, JSON.stringify({
    query: 'mutation($t:String!,$v:String!,$d:String){reportEvent(type:$t,villageCode:$v,desc:$d){id sn state}}',
    variables: { t: 'environment', v: '53060010101', d: 'k6压测上报' },
  }), { headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` } });
  check(r, { 'report-200': (res) => res.status === 200 });
  sleep(2);
}
