#!/usr/bin/env bash
# DV-IAS 扩充村民账号（压测独立账号，避免限流桶共享）
set -euo pipefail
NS=szxc-prod
SCRIPT=scripts/seed_villagers.py
echo "→ 在 iam-svc Pod 内执行种子扩充（13800000001..13800000600）"
IAM=$(kubectl -n "$NS" get pod -l app=iam-svc -o jsonpath='{.items[0].metadata.name}')
kubectl -n "$NS" cp "$SCRIPT" "$NS/$IAM:/tmp/sv.py" -c app
kubectl -n "$NS" exec "$IAM" -c app -- python /tmp/sv.py
