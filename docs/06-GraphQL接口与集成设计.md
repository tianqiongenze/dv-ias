# 06 GraphQL 接口与集成设计（Federation 2 / MCP / 外部系统）

---

## 1. 联邦架构

```
小程序/H5/管理端/大屏
   │ HTTPS (NodePort 30085 → apollo-router ×2)
   ▼
apollo-router（超图路由: APQ、响应缓存、限流、深度限制、禁内省(生产)）
   ├── iam 子图 (DGS :8081)
   ├── portal 子图 (:8082)   ├── governance 子图 (:8083)
   ├── points 子图 (:8084)   ├── agri 子图 (:8085)
   ├── iot 子图 (:8086)      ├── service 子图 (:8087)
   ├── tourism 子图 (:8088)  ├── elder 子图 (:8089)
   ├── trace 子图 (:8090)    └── data 子图 (:8091)
```

- 路由配置要点：query depth limit ≤8、complexity 限流（令牌桶/用户/分钟）、mutation 全局禁缓存、persisted queries 白名单（生产只允许 APQ 命中）、错误屏蔽（内部异常不透出）。
- 安全：网关校验 JWT（RS256 公钥本地验证）→ 向子图注入 `X-User-Id/X-Tenant-Id/X-Scopes`（内网信任，子图不再二次鉴权但做数据范围过滤）。

## 2. 超图 Schema（节选）

```graphql
# ─── iam 子图 ───
type Party @key(fields: "id") { id: ID! name: String! phone: String! household: Household
  org: Organization! pointsAccount: PointsAccount @external }
type Organization { code: String! name: String! level: OrgLevel! children: [Organization] }
enum OrgLevel { COUNTY TOWNSHIP VILLAGE GROUP }

# ─── governance 子图 ───
type GovernanceEvent @key(fields: "id") {
  id: ID! sn: String! type: EventType! state: EventState!
  location: GeoPoint! photos: [Media!]! createdAt: DateTime!
  reporter: Party! assignee: Party timeline: [EventTransition!]! }
input ReportEventInput { type: EventType! geo: GeoPointInput! desc: String photos: [Upload!]! }
type Mutation { reportEvent(input: ReportEventInput!): GovernanceEvent!  # 需登录
  acceptEvent(id: ID!): GovernanceEvent! @auth(role: GRID_WORKER) }

# ─── points 子图（Party 的 federated 扩展）───
type PointsAccount @key(fields: "partyId") { partyId: ID! balance: Int!
  ledger(page: Page): [PointsLedger!]! }
extend type Party @key(fields: "id") { id: ID! @external
  pointsAccount: PointsAccount }

# ─── data 子图（大屏）───
type MetricSnapshot { metric: String! value: Float! window: TimeWindow! at: DateTime! }
type Query { metrics(names: [String!]!, scope: ScopeInput): [MetricSnapshot!]! }
```

完整 SDL 以代码仓 `schemas/*.graphqls` 为唯一事实源（SDD），由 CI 做 `rover supergraph compose` 生成超图并校验破坏性变更（no-breaking-change 门禁）。

## 3. 错误与兼容规范

- 业务错误：`extensions.code` 枚举（UNAUTHENTICATED/FORBIDDEN/VALIDATION/NOT_FOUND/CONFLICT/RATE_LIMITED/UNAVAILABLE），message 面向用户中文文案。
- 分页统一 `Connection`（first/after）；时间 ISO8601+08:00；ID 全局不重复（服务前缀 base64 不强制，直接用TiDB AUTO_RANDOM Bigint + 类型前缀）。
- 破坏性变更禁止：字段只加不删；弃用 `@deprecated` 保持 2 个版本周期。

## 4. MCP 工具层（mcp-dv-tools）

以 MCP Server（Streamable HTTP :8000）暴露受控工具，供 agent-runtime 与未来县级政务智能体调用：

| 工具名 | 入参 | 出参 | 鉴权 |
|---|---|---|---|
| query_points | partyPhone | balance, recent | 用户授权码 |
| query_event_progress | eventSn | state, timeline | 本人/网格员 |
| search_service_guide | keyword, region | top5 指南 | 公开 |
| query_agri_advice | plotId | 农事建议(规则+RAG) | 本人 |
| create_cert_request | itemCode, payload | 申请号 | 用户 token |
| query_iot_realtime | deviceId | latest metrics | 授权设备 |

实现约束：每个工具=白名单 SQL/服务调用，超时 3s，审计入 Pulsar `szxc.audit.mcp`；工具描述即契约（SDD 的一部分，单测校验 schema）。

## 5. A2A 预留

- agent-runtime 发布 Agent Card（`/.well-known/agent.json`）：能力声明（农技问答/办事引导/治理辅助）、认证方式、输入输出 schema。
- 任务委托接口按 A2A 语义实现 `tasks/send`（异步，Pulsar 回执）最小子集；不强依赖对端。

## 6. 外部系统集成（防腐层 ACL）

| 外部系统 | 方式 | 降级策略 |
|---|---|---|
| 微信小程序登录/支付 | 官方 SDK + 服务端回调验签 | 支付不可用→线下核销模式 |
| 政务共享接口 | 网关代理 + 字段映射 ACL + 响应缓存 30min | 不可用→申报制+公示 |
| 短信 | HTTP 网关（可配置 mock） | 站内信兜底 |
| 气象 | 定时拉取入 `agri.weather` | 最近一次缓存 |
| 卫生院视频会诊 | 仅生成会议室链接跳转 | — |
| 手环厂商 API | ACL 适配器（多厂商 SPI） | 厂商间可切换 |

## 7. 实时通道（realtime-gateway）

- WebSocket/SSE：告警、事件流转、消息；订阅鉴权（JWT+topic 归属校验）；心跳 30s；单 Pod 目标 2 万连接，水平扩展按连接数 HPA（自定义指标）。
- 推送链路：Pulsar → realtime-gateway（共享订阅广播到全 Pod，按连接路由表分发）。

## 8. UI 设计规范摘要（资深美工视角）

- Design Tokens：主色 `#2E7D32`（松绿）、辅 `#F9A825`（谷黄）、警示 `#C62828`、底 `#FAFDF7`；圆角 8px；阴影 1-2 级；字体 PingFang/HarmonyOS Sans。
- 村民端：大字号模式（≥16px，可切 20px）、大按钮（≥48px 高）、任务流式首页、方言语音入口预留。
- 管理端：左导航+顶栏工作台；表格密度三档；键盘可达。
- 大屏：1920×1080 与 3840×2160 自适应；暗色科技风但数据色不超过 8 色；5s 轮询 + WS 推送结合。
- 无障碍：对比度 ≥4.5:1（WCAG AA）、图片 alt、村民端核心流程支持读屏。
