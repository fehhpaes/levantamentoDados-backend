FROM node:20-slim

# Install dependencies for canvas or ML if needed (optional but good practice)
RUN apt-get update && apt-get install -y \
    python3 \
    make \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

RUN npm run build

EXPOSE 3001

# Start the worker service
CMD ["node", "dist/server.js"]
