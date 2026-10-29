# DV-IAS 数字乡村综合应用系统（Monorepo）

设计文档：`../docs/`（00-13，TOGAF/DDD/GraphQL联邦/多级缓存/等保三级全套）。

## 结构
```
gw/                  GraphQL 联邦网关（Apollo Gateway，Node）
services/common/     公共库：国密SM3/SM4、双池读写分离、多级缓存、JWT、指标
services/iam/        身份与组织子图(8081)   services/portal/   村务公开子图(8082)
services/governance/ 治理事件子图(8083)    services/points/   积分子图(8084)
services/data/       指标子图(8085)        services/mcp/      MCP工具层(8000)
services/agent/      智能体(30087, RAG+LiteLLM)  services/web/  H5/管理端/大屏(30086)
k8s/                 部署清单（00-base / 10-redis / 20-services / 40-k6 / 60-monitors）
scripts/             build.sh / test.sh / deploy.sh（在175服务器 /opt/dv-ias 执行）
perf/                k6 压测脚本
```

## 快速命令（服务器上）
```bash
cd /opt/dv-ias
bash scripts/build.sh    # 构建并推送全部镜像
bash scripts/test.sh     # 运行TDD单元测试
bash scripts/deploy.sh   # 滚动部署
kubectl create -f k8s/40-k6.yaml   # k6基线压测
```

## 入口
- GraphQL 网关：`http://10.167.2.175:30085`（NodePort 30085）
- 村民H5：`http://10.167.2.175:30086/`
- 管理端：`http://10.167.2.175:30086/admin`
- 指挥大屏：`http://10.167.2.175:30086/screen`
- 智能问答：`http://10.167.2.175:30087/chat`
- MCP：`http://10.167.2.175:30087/mcp`（经网关域外的独立NodePort；集群内为 mcp-svc:8000）

## 演示账号（密码均为 szxc@2026）
- 县管理员：13900000001 ｜ 村管理员/网格员：13900000002-13900000013 ｜ 村民：13800000001-30

## 关键决策
见 `../docs/`；执行偏差记录：`../docs/adr/ADR-007-执行期技术决策.md`
