#!/bin/bash
# DV-IAS 单元测试（TDD 层）：在基础镜像容器内运行，无需本地Python环境
set -e
set -o pipefail
REG=10.167.2.175:30500
cd "$(dirname "$0")/.."
FAIL=0
for s in iam portal governance points data mcp agent web; do
  echo "── pytest: $s"
  if docker run --rm \
      -v "$PWD/services/$s/app":/srv/app \
      -v "$PWD/services/$s/tests":/srv/tests \
      -v "$PWD/services/common/szxc_common":/srv/szxc_common \
      -v "$PWD/services/web/static":/srv/static \
      -e PYTHONPATH=/srv $REG/szxc/base:1.0 \
      pytest /srv/tests -q --no-header 2>&1 | tail -3; then :; else FAIL=1; fi
done
[ $FAIL -eq 0 ] && echo "✅ 全部单测通过" || { echo "❌ 存在失败"; exit 1; }
