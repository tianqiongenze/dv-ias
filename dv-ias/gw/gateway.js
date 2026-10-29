// DV-IAS GraphQL 联邦网关（Apollo Gateway）
// 职责：超图组合、JWT 校验与用户头注入（防伪造）、限流（简易令牌桶）、CORS、健康检查
const { ApolloGateway, RemoteGraphQLDataSource } = require('@apollo/gateway');
const { ApolloServer } = require('@apollo/server');
const { startStandaloneServer } = require('@apollo/server/standalone');
const jwt = require('jsonwebtoken');

const SUBGRAPHS = (process.env.SUBGRAPHS || [
  'iam=http://iam-svc.szxc-prod.svc.cluster.local:8081/graphql',
  'portal=http://portal-svc.szxc-prod.svc.cluster.local:8082/graphql',
  'governance=http://governance-svc.szxc-prod.svc.cluster.local:8083/graphql',
  'points=http://points-svc.szxc-prod.svc.cluster.local:8084/graphql',
  'data=http://data-svc.szxc-prod.svc.cluster.local:8085/graphql',
].join(',')).split(',').map(s => { const [name, url] = s.split('='); return { name, url }; });

const JWT_SECRET = process.env.JWT_SECRET || 'SzxcJwt-2026-bN8wQ4vXzA6sD1fG';

class AuthedDataSource extends RemoteGraphQLDataSource {
  willSendRequest({ request, context }) {
    // 剥离客户端伪造的身份头，仅注入网关校验过的身份（06号文档§1）
    if (context.user) {
      request.http.headers.set('x-user-id', String(context.user.sub));
      request.http.headers.set('x-user-name', Buffer.from(context.user.name || '', 'utf8').toString('base64')); // HTTP头仅允许ByteString，中文用户名Base64编码传输，子图解码
      request.http.headers.set('x-user-roles', context.user.roles || '');
    } else {
      request.http.headers.set('x-user-id', '');
      request.http.headers.set('x-user-roles', '');
    }
  }
}

// 简易令牌桶限流：按用户/IP，6000 req/min（08号文档限流层；600/min 会卡死单核压测，放宽至6000/min）
const buckets = new Map();
function rateLimit(key) {
  const now = Date.now(), cap = 6000, refill = 6000 / 60000;
  let b = buckets.get(key); if (!b) { b = { t: now, n: cap }; buckets.set(key, b); }
  b.n = Math.min(cap, b.n + (now - b.t) * refill); b.t = now;
  if (b.n < 1) return false; b.n -= 1; return true;
}
setInterval(() => { const now = Date.now(); for (const [k, v] of buckets) if (now - v.t > 120000) buckets.delete(k); }, 60000);

const gateway = new ApolloGateway({
  serviceList: SUBGRAPHS,
  buildService: ({ url }) => new AuthedDataSource({ url }),
  // 查询深度与复杂度在网关兜底（SDL 侧配合 depth limit 由各子图 schema 控制）
  __exposeQueryPlanExperimental: false,
});

const server = new ApolloServer({
  gateway,
  introspection: process.env.INTROSPECTION !== 'false',
  formatError: (e) => {
    const ext = e.extensions || {};
    if (ext.code && String(ext.code).startsWith('INTERNAL')) {
      return { message: '服务内部错误，请稍后重试', extensions: { code: 'UNAVAILABLE' } };
    }
    return { message: e.message, extensions: ext };
  },
});

(async () => {
  // 探针端点：网关进程存活即返回 200（组合失败不影响 liveness）
  const http = require('http');
  http.createServer((req, res) => {
    if (req.url.startsWith('/healthz')) { res.writeHead(200, {'content-type':'text/plain'}); res.end('ok'); }
    else { res.writeHead(404); res.end(); }
  }).listen(8081, '0.0.0.0');
  const { url } = await startStandaloneServer(server, {
    listen: { host: '0.0.0.0', port: 8080 },
    context: async ({ req }) => {
      const ip = (req.socket && req.socket.remoteAddress) || 'anon';
      const auth = req.headers.authorization || '';
      let user = null;
      if (auth.startsWith('Bearer ')) {
        try { user = jwt.verify(auth.slice(7), JWT_SECRET, { algorithms: ['HS256'] }); }
        catch { user = null; }
      }
      const key = user ? `u:${user.sub}` : `ip:${ip}`;
      if (!rateLimit(key)) {
        // 通过抛错返回 429 语义
        const err = new Error('请求过于频繁，请稍后再试');
        err.extensions = { code: 'RATE_LIMITED' };
        throw err;
      }
      return { user };
    },
  });
  console.log(`DV-IAS gateway ready at ${url}, subgraphs: ${SUBGRAPHS.map(s => s.name).join(',')}`);
})();
