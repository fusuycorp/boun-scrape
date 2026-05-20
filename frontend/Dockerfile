# Build stage
FROM node:20-slim AS build

WORKDIR /app

# Copy package files
COPY package.json ./
# If bun.lock exists, we can still use npm to install from package.json
# or we could use bun. For compatibility, we'll use npm.
RUN npm install

# Copy source and build
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built files from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
