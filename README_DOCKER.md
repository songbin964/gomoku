# Gomoku Server - Docker 部署说明

## 快速开始

### Windows用户（一键构建）

双击 `build_docker.bat`，脚本会自动：
1. 启动 Docker Desktop（如未运行）
2. 预构建 Linux 二进制（加速构建）
3. 构建 Docker 镜像
4. 输出使用说明

---

## 手动构建命令

### 1. 确保 Docker Desktop 运行

```powershell
# 检查Docker状态
docker ps
```

如果提示 "Docker Desktop is unable to start"：
- 打开 Docker Desktop 应用程序（开始菜单搜索 "Docker Desktop"）
- 等待右下角鲸鱼图标变绿（约30秒-2分钟）
- 确保 Settings → General → "Use the WSL 2 based engine" 已勾选

### 2. 构建镜像

```powershell
cd server
docker build -t gomoku-server:latest .
```

快速构建（使用预编译二进制，约30秒）：
```powershell
# 先在本地交叉编译Linux二进制（已生成 gomoku-server-linux-amd64）
# 然后编辑 Dockerfile 注释 Option 1，取消注释 Option 2
docker build -t gomoku-server:latest .
```

### 3. 运行容器

```powershell
# 方式1：直接docker run
docker run -d `
  -p 8080:8080 `
  --name gomoku-server `
  --restart unless-stopped `
  gomoku-server:latest

# 方式2：docker-compose（推荐）
cd ..
docker-compose up -d
```

### 4. 验证

```powershell
# 查看容器状态
docker ps

# 查看健康检查
docker inspect --format='{{.State.Health.Status}}' gomoku-server

# 测试API
Invoke-RestMethod http://localhost:8080/api/rooms
```

---

## 常用管理命令

```powershell
# 查看日志
docker logs -f gomoku-server

# 最近100行
docker logs --tail 100 gomoku-server

# 重启服务
docker restart gomoku-server

# 停止并删除
docker stop gomoku-server
docker rm gomoku-server

# 进入容器内部
docker exec -it gomoku-server /bin/sh

# 导出镜像（用于离线部署）
docker save -o gomoku-server.tar gomoku-server:latest

# 导入镜像
docker load -i gomoku-server.tar
```

---

## 环境变量配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `TZ` | Asia/Shanghai | 时区设置 |

---

## 端口说明

| 端口 | 说明 |
|------|------|
| `8080/tcp` | WebSocket + REST API |
| | `/ws` - WebSocket连接 |
| | `/api/rooms` - 房间列表API |

---

## docker-compose.yml 说明

```yaml
services:
  gomoku-server:
    image: gomoku-server:latest
    ports:
      - "8080:8080"      # 主机端口:容器端口
    restart: unless-stopped  # 开机自动重启
    healthcheck:      # 健康检查
      test: ["CMD", "wget", "http://localhost:8080/api/rooms"]
      interval: 30s
      timeout: 5s
      retries: 3
    logging:          # 日志轮转，防止占满磁盘
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
```

---

## 服务器部署（Linux）

```bash
# 1. 拷贝预编译二进制到服务器
scp gomoku-server-linux-amd64 user@server:/opt/gomoku/
ssh user@server

# 2. 方式A：直接运行（无需Docker）
cd /opt/gomoku
chmod +x gomoku-server-linux-amd64
./gomoku-server-linux-amd64

# 3. 方式B：使用Docker（推荐）
# 上传 Dockerfile 和 docker-compose.yml 后
docker-compose up -d
```

---

## 故障排查

| 问题 | 解决方案 |
|------|----------|
| "Docker Desktop is unable to start" | 打开 Docker Desktop GUI，等待初始化完成 |
| 构建超时 | 配置 Go 代理：`go env -w GOPROXY=https://goproxy.cn,direct` |
| 容器启动后立即退出 | `docker logs gomoku-server` 查看错误日志 |
| 无法连接端口8080 | 检查防火墙是否开放：`netsh advfirewall firewall add rule name="Gomoku" dir=in action=allow protocol=TCP localport=8080` |
| 健康检查失败 | 检查容器内 `wget http://localhost:8080/api/rooms` 是否正常 |