# Stage 1: Build React app
FROM node:18-alpine AS build

WORKDIR /app

# Accept backend URL at build time (CRA bakes REACT_APP_* into the JS bundle)
ARG REACT_APP_BACKEND_URL=http://localhost:3016
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL

# Copy package.json and lock file
COPY package*.json ./

# Install dependencies
RUN npm install --legacy-peer-deps

# Copy source files
COPY . .

# Build for production (REACT_APP_BACKEND_URL is embedded here)
RUN npm run build

# Stage 2: Serve with Nginx
FROM nginx:alpine

# Copy build output to Nginx html directory
COPY --from=build /app/build /usr/share/nginx/html

# Replace default Nginx config with custom one
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
