# SmartCam dashboard (Next.js) - runs behind Caddy on the same origin as the API.
#
# Build (from the repo root):   docker build -t smartcam-web ./frontend
# Run:                          docker run -d --name smartcam-web --restart unless-stopped \
#                                 -p 127.0.0.1:3000:3000 smartcam-web
#
# Bound to 127.0.0.1 on purpose: Caddy terminates TLS and proxies to it, so port 3000
# must never be reachable from the internet directly.

FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Left empty on purpose. The dashboard calls the API on its OWN origin through the
# /smartapi prefix that Caddy routes to FastAPI, so no absolute API URL may be baked
# in here. (.env.local is excluded by .dockerignore so a local HTTP value can never leak in.)
ENV NEXT_PUBLIC_API_URL=""
# Stamped into the login page so it is never ambiguous which build is live.
ARG GIT_SHA=dev
ENV NEXT_PUBLIC_BUILD=$GIT_SHA
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/next.config.mjs ./next.config.mjs
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/.next ./.next
COPY --from=build /app/public ./public
EXPOSE 3000
CMD ["npm", "run", "start"]
