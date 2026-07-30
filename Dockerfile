# ==============================================
# Gomoku Server - Docker Build (Fast Mode)
# Uses pre-built Linux binary for faster deployment
# ==============================================

# ---- Stage 1: Pre-built binary (fastest, ~10 sec) ----
FROM scratch AS builder
COPY gomoku-server-linux-amd64 /gomoku-server

# ---- Stage 2: Production image ----
FROM alpine:latest

LABEL maintainer="Gomoku Online"
LABEL description="Gomoku (Five in a Row) Online Server"

# Install dependencies: ca-certificates, tzdata (timezone), wget (healthcheck)
RUN apk --no-cache add ca-certificates tzdata wget

WORKDIR /app

# Copy pre-built binary
COPY --from=builder /gomoku-server /gomoku-server

# Make executable
RUN chmod +x /gomoku-server

# Expose WebSocket + REST API port
EXPOSE 8080

# Health check: verify API is responding
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:8080/api/rooms >/dev/null 2>&1 || exit 1

# Default timezone
ENV TZ=Asia/Shanghai

# Run server
CMD ["/gomoku-server"]