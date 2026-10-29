#!/usr/bin/env bash
# DV-IAS 无头浏览器 E2E 部署运行
set -euo pipefail
NS=szxc-prod
SCRIPT=test/e2e_browser.py
echo "→ 同步 E2E 脚本至 ConfigMap"
kubectl -n "$NS" delete cm e2e-scr 2>/dev/null || true
kubectl -n "$NS" create cm e2e-scr --from-file=e2e_browser.py="$SCRIPT"
echo "→ 运行 E2E Pod"
kubectl -n "$NS" delete pod e2e-run 2>/dev/null || true
kubectl -n "$NS" apply -f k8s/50-e2e.yaml
kubectl -n "$NS" wait --for=condition=Completed pod/e2e-run --timeout=300s || true
kubectl -n "$NS" logs e2e-run
