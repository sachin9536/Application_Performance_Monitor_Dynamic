FROM node:18-slim

WORKDIR /app

COPY services/service_delta_package.json /app/package.json
RUN npm install

COPY services/service_delta.js /app/service_delta.js

EXPOSE 9400

CMD ["node", "service_delta.js"]