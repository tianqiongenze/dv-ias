#!/bin/bash
# 部署前冒烟：各服务应用模块可导入、GraphQL联邦schema可构建（不连DB/Redis）
set -e
set -o pipefail
REG=10.167.2.175:30500
TAG=${TAG:-1.2}
cd "$(dirname "$0")/.."
for s in iam portal governance points data mcp agent web; do
  echo "── import-smoke: $s"
  docker run --rm \
    -v "$PWD/services/$s/app":/srv/app \
    -v "$PWD/services/common/szxc_common":/srv/szxc_common \
    -v "$PWD/services/web/static":/srv/static \
    -e PYTHONPATH=/srv -e DB_HOST_WRITE=x:1 -e DB_HOST_READ=x:1 -e DB_USER=x -e DB_PASS=x \
    -e DB_USER_RO=x -e DB_PASS_RO=x -e REDIS_URL=x:1 -e REDIS_PASS=x \
    $REG/szxc/base:$TAG python -c "import sys; sys.path.insert(0,'/srv'); import app.main; print('IMPORT-OK $s')"
done
echo "✅ 全部服务导入冒烟通过"
