# Stage 1: Build ứng dụng React với Node.js
FROM node:20-alpine AS build
WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Stage 2: Serve ứng dụng với Nginx
FROM nginx:alpine

# Copy file build React vào thư mục web của Nginx
COPY --from=build /app/dist /usr/share/nginx/html

# Copy file cấu hình Nginx custom
COPY default.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]