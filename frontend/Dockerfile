# The interface as a container: built by Node, served by nginx.
#
# Vite reads VITE_* variables at build time and writes their values into the
# bundle, so the API address is a build argument rather than a runtime
# environment variable. Getting that backwards produces an image that ignores
# its own configuration.

# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------
FROM node:20-alpine AS build

WORKDIR /app

# npm ci rather than npm install: it installs exactly the lock file and fails if
# the two disagree, which is what a reproducible build means.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Where the browser reaches the API, relative to whatever host served the page.
# nginx proxies /api to the API container, so this stays correct on localhost,
# on another machine and behind a tunnel alike.
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

# ---------------------------------------------------------------------------
# serve
# ---------------------------------------------------------------------------
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
