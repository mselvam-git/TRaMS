FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --prefer-offline
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
# Copy static files not processed by Vite
COPY public/manifest.json /usr/share/nginx/html/manifest.json
COPY public/sw.js         /usr/share/nginx/html/sw.js
COPY nginx.conf           /etc/nginx/conf.d/default.conf

# Replace backend URL placeholder at container start
ARG BACKEND_URL=https://trams-c6ln.onrender.com
RUN sed -i "s|__BACKEND_URL__|${BACKEND_URL}|g" /etc/nginx/conf.d/default.conf && \
    sed -i "s|__BACKEND_URL_SLASH__|${BACKEND_URL}/api/|g" /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
