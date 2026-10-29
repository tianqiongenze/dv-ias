FROM node:20-alpine
ENV NPM_CONFIG_REGISTRY=https://registry.npmmirror.com
WORKDIR /app
COPY gw/package.json .
RUN npm install --omit=dev
COPY gw/gateway.js .
EXPOSE 8080
CMD ["node", "gateway.js"]
