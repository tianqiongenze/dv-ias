#!/bin/bash
# DV-IAS 镜像构建（在 175 服务器 /opt/dv-ias 下执行，构建上下文=仓库根）
set -e
REG=10.167.2.175:30500
TAG=${TAG:-1.1}
cd "$(dirname "$0")/.."

echo "── 构建基础镜像（公共依赖，仅首次较慢）"
docker build -f Dockerfile.base -t $REG/szxc/base:$TAG .
docker push $REG/szxc/base:$TAG

echo "── 构建网关"
docker build -f gw/Dockerfile -t $REG/szxc/gw:$TAG .
docker push $REG/szxc/gw:$TAG

for s in iam portal governance points data mcp agent web; do
  echo "── 构建 $s"
  docker build -f services/$s/Dockerfile --build-arg BASE=$REG/szxc/base:$TAG -t $REG/szxc/$s:$TAG .
  docker push $REG/szxc/$s:$TAG
done
echo "✅ 全部镜像构建并推送完成 tag=$TAG"
