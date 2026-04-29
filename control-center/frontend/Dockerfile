FROM node:20-alpine AS builder

WORKDIR /app

COPY frontend/package.json .
RUN npm install

COPY frontend/ .

ARG VITE_TILE_SERVER_URL=https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png
ARG VITE_AGGREGATION_WS_URL=
ARG VITE_SIGNALING_URL=

ENV VITE_TILE_SERVER_URL=$VITE_TILE_SERVER_URL
ENV VITE_AGGREGATION_WS_URL=$VITE_AGGREGATION_WS_URL
ENV VITE_SIGNALING_URL=$VITE_SIGNALING_URL

RUN npm run build

# Copy dist to the shared volume on startup (always overwrites)
CMD ["sh", "-c", "rm -rf /vol/* && cp -r /app/dist/. /vol/ && echo 'Frontend dist copied to volume.'"]
