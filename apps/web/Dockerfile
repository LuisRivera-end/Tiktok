FROM node:22.17.1-alpine3.22 AS build
WORKDIR /web
COPY package.json ./
RUN npm install --ignore-scripts && npm rebuild esbuild
COPY . .
RUN npm run build

FROM nginx:1.27.4-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/dist /usr/share/nginx/html
EXPOSE 80
