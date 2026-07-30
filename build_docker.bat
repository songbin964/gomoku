@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

set IMAGE_NAME=gomoku-server
set IMAGE_TAG=latest
set FULL_IMAGE=%IMAGE_NAME%:%IMAGE_TAG%
set DOCKER_BIN=C:\Users\songb\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe

echo ============================================
echo   Building Gomoku Server Docker Image
echo ============================================
echo.

:: Step 1: Start Docker Desktop if not running
tasklist /FI "IMAGENAME eq Docker Desktop.exe" /FO TABLE /NH 2>nul | findstr /I "Docker Desktop.exe" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Starting Docker Desktop...
    start "" "C:\Users\songb\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe"
    echo [INFO] Waiting for Docker engine to be ready...
    :wait_for_docker
    %DOCKER_BIN% ps >nul 2>&1
    if %errorlevel% neq 0 (
        echo   Still waiting...
        timeout /t 5 /nobreak >nul
        goto wait_for_docker
    )
    echo [INFO] Docker engine ready!
) else (
    echo [INFO] Docker Desktop is running.
)

:: Step 2: Build cross-platform Go binary (optional, but speeds up build)
echo.
echo [STEP 1/3] Pre-building Linux binary (optional optimization)...
where go >nul 2>&1
if %errorlevel% equ 0 (
    set GOOS=linux
    set GOARCH=amd64
    set CGO_ENABLED=0
    cd /d "%~dp0server"
    go build -ldflags="-s -w" -o gomoku-server-linux-amd64 . 2>nul
    if exist gomoku-server-linux-amd64 (
        echo   Pre-built Linux binary ready (6MB).
    )
) else (
    echo   Go not found, will build inside Docker (slower).
)

:: Step 3: Build Docker image
echo.
echo [STEP 2/3] Building Docker image: %FULL_IMAGE%
cd /d "%~dp0server"
%DOCKER_BIN% build -t %FULL_IMAGE% .

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Build failed!
    echo.
    echo Troubleshooting:
    echo   1. Make sure WSL2 is installed: wsl --install
    echo   2. Restart Docker Desktop as Administrator
    echo   3. In Docker Desktop settings, enable "Use the WSL 2 based engine"
    pause
    exit /b 1
)

:: Step 4: Summary
echo.
echo [STEP 3/3] Build complete!
echo.
%DOCKER_BIN% images %FULL_IMAGE%
echo.
echo ============================================
echo   Usage Examples
echo ============================================
echo.
echo   Start server:
echo     docker run -d -p 8080:8080 --name gomoku-server --restart unless-stopped %FULL_IMAGE%
echo.
echo   Or use docker-compose (in project root):
echo     docker-compose up -d
echo.
echo   View logs:
echo     docker logs -f gomoku-server
echo.
echo   Check health:
echo     curl http://localhost:8080/api/rooms
echo.
echo   Stop:
echo     docker stop gomoku-server
echo.
echo   Export image for offline deployment:
echo     docker save -o gomoku-server.tar %FULL_IMAGE%
echo ============================================
pause
endlocal