@echo off
color 0A
cls
echo ================================================================================
echo    INSTALACION Y CONFIGURACION - TRADING PLATFORM AI
echo    Sistema completo de trading con RL + Indicadores Tecnicos
echo ================================================================================
echo.

:: Verificar privilegios de administrador
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Este script requiere privilegios de administrador.
    echo Por favor, ejecuta como administrador (click derecho - Ejecutar como administrador)
    pause
    exit /b 1
)

echo [PASO 1/8] Verificando requisitos del sistema...
echo.

:: Verificar Docker Desktop
echo Verificando Docker Desktop...
docker --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Docker Desktop no esta instalado.
    echo.
    echo Por favor instala Docker Desktop desde:
    echo https://www.docker.com/products/docker-desktop/
    echo.
    pause
    exit /b 1
)
echo OK - Docker Desktop instalado correctamente
echo.

:: Verificar Docker Compose
echo Verificando Docker Compose...
docker-compose --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Docker Compose no esta disponible.
    echo.
    pause
    exit /b 1
)
echo OK - Docker Compose instalado correctamente
echo.

:: Verificar que Docker está corriendo
echo Verificando que Docker esta corriendo...
docker ps >nul 2>&1
if %errorLevel% neq 0 (
    echo [ADVERTENCIA] Docker Desktop no esta corriendo.
    echo.
    echo Iniciando Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo.
    echo Esperando 30 segundos para que Docker inicie...
    timeout /t 30 /nobreak >nul

    docker ps >nul 2>&1
    if %errorLevel% neq 0 (
        echo [ERROR] Docker no pudo iniciarse.
        echo Por favor inicia Docker Desktop manualmente y vuelve a ejecutar este script.
        pause
        exit /b 1
    )
)
echo OK - Docker esta corriendo correctamente
echo.

echo [PASO 2/8] Creando directorios necesarios...
echo.

if not exist "backend\models" mkdir backend\models
if not exist "backend\logs" mkdir backend\logs
if not exist "frontend" mkdir frontend
if not exist "grafana\dashboards" mkdir grafana\dashboards

echo OK - Directorios creados
echo.

echo [PASO 3/8] Verificando archivos de configuracion...
echo.

if not exist "backend\requirements.txt" (
    echo [ERROR] Falta backend\requirements.txt
    pause
    exit /b 1
)
echo OK - backend\requirements.txt encontrado

if not exist "backend\Dockerfile" (
    echo [ERROR] Falta backend\Dockerfile
    pause
    exit /b 1
)
echo OK - backend\Dockerfile encontrado

if not exist "docker-compose.yml" (
    echo [ERROR] Falta docker-compose.yml
    pause
    exit /b 1
)
echo OK - docker-compose.yml encontrado

if not exist "backend\db\init.sql" (
    echo [ERROR] Falta backend\db\init.sql
    pause
    exit /b 1
)
echo OK - backend\db\init.sql encontrado
echo.

echo [PASO 4/8] Creando archivo de configuracion Nginx...
echo.

if not exist "nginx.conf" (
    echo worker_processes 1; > nginx.conf
    echo. >> nginx.conf
    echo events { >> nginx.conf
    echo     worker_connections 1024; >> nginx.conf
    echo } >> nginx.conf
    echo. >> nginx.conf
    echo http { >> nginx.conf
    echo     include mime.types; >> nginx.conf
    echo     default_type application/octet-stream; >> nginx.conf
    echo. >> nginx.conf
    echo     server { >> nginx.conf
    echo         listen 80; >> nginx.conf
    echo         server_name localhost; >> nginx.conf
    echo. >> nginx.conf
    echo         location / { >> nginx.conf
    echo             root /usr/share/nginx/html; >> nginx.conf
    echo             index index.html; >> nginx.conf
    echo             try_files $uri $uri/ /index.html; >> nginx.conf
    echo         } >> nginx.conf
    echo. >> nginx.conf
    echo         location /api { >> nginx.conf
    echo             proxy_pass http://backend:8000; >> nginx.conf
    echo             proxy_set_header Host $host; >> nginx.conf
    echo             proxy_set_header X-Real-IP $remote_addr; >> nginx.conf
    echo         } >> nginx.conf
    echo. >> nginx.conf
    echo         location /ws { >> nginx.conf
    echo             proxy_pass http://backend:8000; >> nginx.conf
    echo             proxy_http_version 1.1; >> nginx.conf
    echo             proxy_set_header Upgrade $http_upgrade; >> nginx.conf
    echo             proxy_set_header Connection "upgrade"; >> nginx.conf
    echo         } >> nginx.conf
    echo     } >> nginx.conf
    echo } >> nginx.conf
    echo OK - nginx.conf creado
) else (
    echo OK - nginx.conf ya existe
)
echo.

echo [PASO 5/8] Creando archivo de configuracion Prometheus...
echo.

if not exist "prometheus.yml" (
    echo global: > prometheus.yml
    echo   scrape_interval: 15s >> prometheus.yml
    echo. >> prometheus.yml
    echo scrape_configs: >> prometheus.yml
    echo   - job_name: 'trading-backend' >> prometheus.yml
    echo     static_configs: >> prometheus.yml
    echo       - targets: ['backend:8000'] >> prometheus.yml
    echo OK - prometheus.yml creado
) else (
    echo OK - prometheus.yml ya existe
)
echo.

echo [PASO 6/8] Creando archivo .env con credenciales...
echo.

if not exist ".env" (
    echo # Base de datos PostgreSQL > .env
    echo DATABASE_URL=postgresql://trading_user:trading_pass@postgres:5432/trading_db >> .env
    echo. >> .env
    echo # Redis >> .env
    echo REDIS_URL=redis://redis:6379 >> .env
    echo. >> .env
    echo # Modelo de Machine Learning >> .env
    echo ML_MODEL_PATH=/app/models/ppo_trading_model.zip >> .env
    echo. >> .env
    echo # TopstepX API (Configurar con tus credenciales) >> .env
    echo TOPSTEP_API_KEY=tu_api_key_aqui >> .env
    echo TOPSTEP_USERNAME=tu_username_aqui >> .env
    echo. >> .env
    echo # Python >> .env
    echo PYTHONUNBUFFERED=1 >> .env
    echo OK - .env creado
    echo.
    echo [IMPORTANTE] Edita el archivo .env y configura tus credenciales de TopstepX
) else (
    echo OK - .env ya existe
)
echo.

echo [PASO 7/8] Descargando imagenes Docker...
echo.
echo Esto puede tardar varios minutos la primera vez...
echo.

docker-compose pull
if %errorLevel% neq 0 (
    echo [ADVERTENCIA] No se pudieron descargar algunas imagenes.
    echo Se intentara construirlas localmente.
)
echo.

echo [PASO 8/8] Construyendo servicios...
echo.

docker-compose build --no-cache
if %errorLevel% neq 0 (
    echo [ERROR] Error al construir los servicios.
    pause
    exit /b 1
)
echo.

echo ================================================================================
echo    INSTALACION COMPLETADA CON EXITO
echo ================================================================================
echo.
echo PROXIMOS PASOS:
echo.
echo 1. Edita el archivo .env con tus credenciales de TopstepX
echo.
echo 2. Inicia los servicios ejecutando: iniciar.bat
echo.
echo 3. Accede a:
echo    - Frontend:    http://localhost:3000
echo    - Backend API: http://localhost:8000
echo    - Grafana:     http://localhost:3001 (user: admin, pass: admin)
echo    - Prometheus:  http://localhost:9090
echo.
echo 4. Para detener los servicios: detener.bat
echo.
echo ================================================================================
pause
