#!/bin/bash
# DV-IAS 部署（滚动更新）
set -e
cd "$(dirname "$0")/.."
kubectl apply -f k8s/00-base.yaml
kubectl apply -f k8s/10-redis.yaml
kubectl apply -f k8s/20-services.yaml
if [ -f k8s/60-monitors.yaml ]; then kubectl apply -f k8s/60-monitors.yaml; fi
for d in gw iam-svc portal-svc governance-svc points-svc data-svc mcp-svc agent-svc web; do
  kubectl -n szxc-prod rollout status deploy/$d --timeout=180s
done
echo "✅ 全部部署完成"
