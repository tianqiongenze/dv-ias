#!/usr/bin/env bash
# DV-IAS k6 压力测试部署运行（350 VU 峰值爬坡）
set -euo pipefail
NS=szxc-prod
SCRIPT=perf/stress.js
echo "→ 同步 stress.js 至 ConfigMap"
kubectl -n "$NS" delete cm k6-stress 2>/dev/null || true
kubectl -n "$NS" create cm k6-stress --from-file=stress.js="$SCRIPT"
cat <<'YAML' | kubectl -n "$NS" apply -f -
apiVersion: batch/v1
kind: Job
metadata: {name: k6-stress, namespace: szxc-prod}
spec:
  backoffLimit: 0
  template:
    metadata: {labels: {app: k6-stress}}
    spec:
      restartPolicy: Never
      priorityClassName: szxc-normal
      containers:
      - name: k6
        image: 10.167.2.175:30500/perf/k6:0.1.3
        env: [{name: GATEWAY, value: "http://gw-svc.szxc-prod.svc.cluster.local:8080/"}]
        command: ["k6", "run", "/scripts/stress.js"]
        volumeMounts: [{name: scripts, mountPath: /scripts, readOnly: true}]
        resources: {requests: {cpu: 500m, memory: 256Mi}, limits: {cpu: "2", memory: 1Gi}}
      volumes:
      - name: scripts
        configMap: {name: k6-stress}
YAML
kubectl -n "$NS" wait --for=condition=Complete job/k6-stress --timeout=600s || true
kubectl -n "$NS" logs job/k6-stress
