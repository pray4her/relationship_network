FROM oven/bun:1.3.10-alpine AS dependencies

WORKDIR /app
COPY package.json bun.lock ./
RUN bun ci

FROM dependencies AS build

COPY . .
RUN bun run build

FROM oven/bun:1.3.10-alpine AS runtime

ENV HOSTNAME=0.0.0.0 \
    NODE_ENV=production \
    PORT=3000

WORKDIR /app
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static

EXPOSE 3000

CMD ["bun", "server.js"]
