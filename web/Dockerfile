# --- Build stage ---
FROM node:22-slim AS builder

WORKDIR /app

COPY web/package*.json ./
RUN npm ci

COPY web/ .
RUN NEXT_PUBLIC_API_URL=/api npm run build

# --- Runtime stage ---
FROM node:22-slim AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_PUBLIC_API_URL=/api

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000

CMD ["node", "server.js"]
