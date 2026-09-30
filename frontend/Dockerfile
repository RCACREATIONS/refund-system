FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
ENV NODE_ENV=development
RUN npm ci --include=dev
COPY . .
RUN test -x node_modules/.bin/tsc
RUN npm run build

FROM nginx:1.27-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 3000
