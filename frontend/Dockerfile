# ============================================================================
# STAGE 1: Dependencies - Install node_modules
# ============================================================================
FROM node:20-alpine AS dependencies

WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./

# Install dependencies (including devDependencies for build)
RUN npm ci --legacy-peer-deps && \
    npm cache clean --force

# ============================================================================
# STAGE 2: Builder - Build the application
# ============================================================================
FROM node:20-alpine AS builder

WORKDIR /app

# Copy dependencies from previous stage
COPY --from=dependencies /app/node_modules ./node_modules

# Copy source code
COPY . .

# Build the application with optimizations
ENV NODE_ENV=production
RUN npm run build && \
    # Remove source maps in production for smaller bundle
    find dist -name "*.map" -type f -delete

# ============================================================================
# STAGE 3: Production - Serve with nginx
# ============================================================================
FROM nginx:alpine AS production

# Install curl for healthcheck
RUN apk add --no-cache curl

# Copy built files from builder (only the dist folder)
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Add security headers and optimization
RUN echo 'server_tokens off;' > /etc/nginx/conf.d/security.conf

# Create nginx user and set permissions
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chmod -R 755 /usr/share/nginx/html

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost/ || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
