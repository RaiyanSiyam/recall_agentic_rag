FROM node:20-alpine AS build

WORKDIR /app

COPY apps/web/package*.json ./
RUN npm install

COPY apps/web ./
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 5173

# Simple nginx configuration
RUN sed -i 's/listen       80;/listen       5173;/' /etc/nginx/conf.d/default.conf

CMD ["nginx", "-g", "daemon off;"]
