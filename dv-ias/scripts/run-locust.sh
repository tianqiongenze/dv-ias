#!/usr/bin/env bash
# DV-IAS Locust 性能测试部署运行
set -euo pipefail
NS=szxc-prod
SCRIPT=perf/locustfile.py
echo "→ 同步 locustfile 至 ConfigMap"
kubectl -n "$NS" delete cm locustf 2>/dev/null || true
kubectl -n "$NS" create cm locustf --from-file=locustfile.py="$SCRIPT"
echo "→ 运行 Locust Pod（150 用户，20/s 爬坡，3min）"
kubectl -n "$NS" delete pod locust-run 2>/dev/null || true
kubectl -n "$NS" apply -f k8s/45-locust.yaml
kubectl -n "$NS" wait --for=condition=Completed pod/locust-run --timeout=300s || true
kubectl -n "$NS" logs locust-run
