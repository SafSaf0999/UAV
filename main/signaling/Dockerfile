FROM node:20-alpine

WORKDIR /app

COPY main/signaling/package.json .
RUN npm install --omit=dev

COPY main/signaling/server.js .

ENV SIGNALING_PORT=8765

ENTRYPOINT ["node", "server.js"]
