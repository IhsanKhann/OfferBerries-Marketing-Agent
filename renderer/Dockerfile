FROM node:20-slim

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package.json .
RUN npm install
RUN npx playwright install chromium --with-deps

COPY . .

RUN mkdir -p /app/output

EXPOSE 3001
CMD ["node", "server.js"]
