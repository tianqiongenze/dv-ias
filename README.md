# DV-IAS 数字乡村综合服务平台

> "1+1+N" 架构：1 个数字底座 + 1 个指挥中枢 + N 个场景应用
> 技术栈：Kubernetes + GraphQL Federation(Apollo Gateway) + TiDB(HTAP) + Redis Cluster + Strawberry Python 子图 + Node.js 网关
> 教学配套课程：https://github.com/tianqiongenze/dv-ias-course

## 在线状态（验收实测）

| 指标 | 结果 |
|---|---|
| 工作负载 | 18 个（双副本）Running |
| 数据规模 | 1.058 亿行测试数据（4 表） |
| k6 压测 | 350 VU，20.6 万请求 **0 失败**，p95=355ms |
| Locust | 150 用户，3894 请求 **0 失败** |
| Playwright E2E | **12/12 PASS**（三端渲染+业务闭环+联邦跨域） |
| Prometheus | 7/7 服务 target UP |

## 目录

```
docs/       设计文档 00~16（TOGAF/DDD/容量/安全等保/验收）+ ADR + 测试报告
dv-ias/     Monorepo：gw(网关) + services/{iam,portal,governance,points,data,agent,mcp,web,common}
            k8s/ 清单、perf/ 压测脚本、test/ E2E、scripts/ 运维脚本
```

## 快速开始

```bash
# 1. 构建镜像（集群内 Registry）
bash dv-ias/scripts/build.sh

# 2. 部署（namespace szxc-prod）
bash dv-ias/scripts/deploy.sh

# 3. 冒烟 + 全链路验证
bash dv-ias/scripts/smoke-import.sh
python3 dv-ias/test/e2e_browser.py   # 需集群内 Playwright 环境

# 4. 压测
bash dv-ias/scripts/run-stress.sh    # k6 350VU
bash dv-ias/scripts/run-locust.sh    # Locust 150 用户
```

## 安全说明

⚠️ 仓库内 `k8s/00-base.yaml` 的 Secret 为**教学/演示环境凭据**（本地 K8s 集群用），
生产部署必须：改为外部密钥管理（Vault/SealedSecrets）、轮换全部密码与 JWT 密钥、
启用 TiDB TLS 与网关 HTTPS。详见 `docs/11-安全合规与等保三级设计.md`。

## 文档导航

- 方案总览：`docs/00-方案总览与确认清单.md`
- 架构：`docs/03-总体架构设计说明书-TOGAF.md`
- 接口：`docs/06-GraphQL接口与集成设计.md`
- 部署运维：`docs/10-部署与运维方案-K8s.md`
- 测试：`docs/15-融合测试报告.md`、`docs/16-局域网人工测试操作指南.md`

## 姊妹项目

- HSF 高标准农田信息平台（独立立项，复用本工程体系与验收标准）：https://github.com/tianqiongenze/hsf-ias
