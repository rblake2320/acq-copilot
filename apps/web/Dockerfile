FROM node:20-alpine AS base
WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm ci

# Copy source
COPY . .

# Development mode
EXPOSE 3000
CMD ["npm", "run", "dev"]
