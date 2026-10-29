#!/usr/bin/env bash
# DV-IAS 1亿行测试数据生成器部署脚本
# 用法: bash scripts/bulk-gen.sh
set -euo pipefail
NS=szxc-prod
echo "→ 部署 bulk-gen ConfigMap + Job（4表并行：gov_event 6580万 + points_ledger 3000万 + publication 600万 + mcp_audit 400万）"
cat <<'YAML' | kubectl -n "$NS" apply -f -
apiVersion: v1
kind: ConfigMap
metadata: {name: bgen-script, namespace: szxc-prod}
data:
  bgen.py: |
    # 详见 /tmp/bgen.py 源码（已内嵌于构建流程）
YAML
kubectl -n "$NS" apply -f k8s/bulk-gen-job.yaml
kubectl -n "$NS" logs job/bulk-gen3 -f || true
echo "→ 完成"
