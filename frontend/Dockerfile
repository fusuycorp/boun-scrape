# Stage 1: Build static assets
FROM node:20-alpine AS build

WORKDIR /app

# Copy package manifests
COPY package.json ./

# Install dependencies using build cache
RUN --mount=type=cache,target=/root/.npm \
    npm install --no-audit --no-fund

# Copy source code and compile static bundle
COPY . .
RUN npm run build

# Stage 2: Serve static files with Nginx Alpine Slim
FROM nginx:alpine-slim

# Copy compiled static assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
