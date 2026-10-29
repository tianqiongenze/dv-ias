# 09 质量保障体系（DDD×TDD×SDD×BDD + CI/CD）

> 质量模型依据 ISO/IEC 25010；流程融入敏捷迭代（Scrum，2 周迭代）。

---

## 1. 四个 D 的职责分工（一张图）

```
DDD  ──"做什么"──  限界上下文/聚合/事件（04号文档） ── 喂给 ──┐
SDD  ──"契约是什么"── GraphQL SDL / AsyncAPI / JSON Schema / Gherkin（唯一事实源）─┤
TDD  ──"怎么实现"── 红→绿→重构，先写测试后写代码（单元层）     ├─▶ 可发布增量
BDD  ──"验收什么"── Given-When-Then 业务可读场景（验收层）    ─┘
```

## 2. SDD：契约先行流水线

1. **规格即代码**：`schemas/` 目录为唯一事实源——
   - `schemas/graphql/*.graphqls`（联邦子图 SDL）
   - `schemas/asyncapi/asyncapi.yaml`（Pulsar 事件契约：topic/载荷 JSON Schema）
   - `schemas/mcp/tools/*.json`（MCP 工具入出参 JSON Schema）
   - `specs/bdd/*.feature`（Gherkin）
2. **CI 门禁**：
   - `rover supergraph compose` 校验联邦兼容 + **破坏性变更检测**（字段删除/类型变更直接失败）；
   - JSON Schema 对样例载荷 100% 校验；
   - 由规格生成服务端桩（DGS codegen、JSON-Schema→POJO），实现必须落在桩上。
3. **消费者驱动契约（CDC）**：Pact——portal(消费)↔iam(提供) 等关键链路，提供者 CI 拉取消费者契约回放。

## 3. TDD：单元层

- 节奏：先写失败测试（红）→ 最小实现（绿）→ 重构。PR 中测试与实现同交，禁"后补测试"。
- 覆盖率门禁：**domain 层行覆盖 ≥90%、application ≥80%、整体 ≥75%**（JaCoCo + Sonar 质量门）。
- 测试速度：单元测试无 I/O，单服务全套 ≤30s（CI 反馈环）。
- 测试数据库：Testcontainers 起真实 TiDB 兼容（MySQL 模式容器）而非 H2（方言差异零容忍）。
- 领域不变量测试表（节选）：余额不可负、一人一票、SLA 超时必升级、控制指令必双签、敏感字段必加密存储。

## 4. BDD：验收层

- Gherkin 场景在迭代计划会前与产品（业务专家）共同评审——**规格可执行**。
- 技术栈：Cucumber(JVM)/pytest-bdd(Python) + Playwright 驱动 H5。
- 场景库分层：核心旅程（每迭代回归 30 条）+ 全量（版本级 200+ 条）。
- 示例（积分闭环）见 04 号文档 §7。

## 5. 测试金字塔与入口

| 层 | 工具 | 触发 | 时长预算 |
|---|---|---|---|
| L1 单元 | JUnit5 / pytest | 每次 push | 10min |
| L2 集成 | SpringBoot Test + Testcontainers | PR | 15min |
| L3 契约 | Pact + SDL 校验 | PR | 5min |
| L4 E2E(BDD) | Playwright + Cucumber | 每日/发版 | 40min |
| L5 性能 | k6 smoke（核心 6 接口） | 每日夜间 | 20min |
| L6 安全 | 依赖漏洞扫描 + ZAP 基线 | 每周 | 30min |

## 6. CI/CD 流水线（集群内 Registry）

```
push → ①lint+单测 → ②集成+契约 → ③构建镜像(docker build) 
     → ④推 Registry 10.167.2.175:30500/szxc/<svc>:<sha>
     → ⑤kustomize 渲染(overlay: dev/prod) → ⑥部署 szxc-dev 自动 
     → ⑦E2E+k6 smoke → ⑧人工批准 → ⑨prod 滚动(金丝雀 10%→50%→100%)
```

- 版本策略：镜像 tag=git sha；`latest` 禁止上 prod；回滚=切回上一 tag（≤2min）。
- 金丝雀指标：错误率、P95、业务指标（上报成功率）任一劣化 >10% 自动回退。
- GitOps 演进：一期 kustomize+kubectl（从 175 管理机执行），二期可上 ArgoCD（ADR 记录）。

## 7. 缺陷与代码质量治理

- Sonar 质量门：0 新增 Blocker/Critical；重复率 <3%；圈复杂度方法 ≤10。
- 缺陷分级 P0-P3；P0（核心链路不可用/数据错/安全）2h 响应、24h 修复 SLA。
- 每迭代缺陷逃逸率复盘（逃逸=上线后发现），目标 <10%。
- 技术债看板：Sonar 热点 + TODO 扫描入 Backlog，迭代预留 15% 偿还。

## 8. 文档与知识管理

- ADR（docs/adr）记录全部架构决策；
- 每个 svc README（启动/测试/排障三分钟上手）；
- API 变更 changelog 自动生成（SDL diff）；
- 运维手册 + 值班 Runbook（10 号文档），故障复盘模板（无责文化，时间线+根因+行动项）。
