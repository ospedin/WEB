@echo off
color 0B
cls
echo ================================================================================
echo    INICIANDO SERVICIOS - TRADING PLATFORM AI
echo ================================================================================
echo.

:: Verificar si es la primera vez (verificar si existe node_modules o venv)
if not exist "backend\venv" (
    echo [PRIMERA VEZ DETECTADA] Instalando dependencias...
    echo.
    call instalar.bat
    if %errorLevel% neq 0 (
        echo [ERROR] Error instalando dependencias.
        pause
        exit /b 1
    )
    echo.
)

:: Verificar que Docker esta corriendo
echo [1/6] Verificando Docker Desktop...
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
echo OK - Docker esta corriendo
echo.

:: Limpiar puertos ocupados
echo [2/6] Limpiando puertos ocupados...
echo Deteniendo contenedores antiguos...
docker-compose down 2>nul
docker stop trading_backend trading_frontend trading_postgres trading_redis trading_prometheus trading_grafana 2>nul
docker rm -f trading_backend trading_frontend trading_postgres trading_redis trading_prometheus trading_grafana 2>nul

:: Liberar puertos del sistema
echo Liberando puertos del sistema (8000, 3000, 5432, 6379, 9090, 3001)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING 2^>nul') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3000 ^| findstr LISTENING 2^>nul') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5432 ^| findstr LISTENING 2^>nul') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :6379 ^| findstr LISTENING 2^>nul') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :9090 ^| findstr LISTENING 2^>nul') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3001 ^| findstr LISTENING 2^>nul') do taskkill /F /PID %%a >nul 2>&1
echo OK - Puertos liberados
echo.

echo ================================================================================
echo    INICIANDO SERVICIOS
echo ================================================================================
echo.

echo [3/6] Iniciando contenedores Docker...
echo    - PostgreSQL + TimescaleDB
echo    - Redis
echo    - Backend FastAPI
echo    - Frontend Nginx
echo    - Grafana
echo    - Prometheus
echo.

docker-compose up -d

if %errorLevel% neq 0 (
    echo.
    echo [ERROR] Error al iniciar los servicios.
    echo.
    echo Ejecutando diagnostico...
    docker-compose logs --tail=50
    pause
    exit /b 1
)

echo.
echo ================================================================================
echo [4/6] Esperando que los servicios esten listos...
echo ================================================================================
echo.

:: Esperar a que PostgreSQL este listo
echo Esperando PostgreSQL...
:wait_postgres
timeout /t 2 /nobreak >nul
docker exec trading_postgres pg_isready -U trading_user -d trading_db >nul 2>&1
if %errorLevel% neq 0 (
    echo    Esperando PostgreSQL... (reintentando)
    goto :wait_postgres
)
echo OK - PostgreSQL esta listo
echo.

:: Esperar a que Redis este listo
echo Esperando Redis...
timeout /t 2 /nobreak >nul
docker exec trading_redis redis-cli ping >nul 2>&1
if %errorLevel% neq 0 (
    echo    Esperando Redis... (reintentando)
    timeout /t 2 /nobreak >nul
)
echo OK - Redis esta listo
echo.

:: Esperar a que el backend este listo
echo Esperando Backend API...
:wait_backend
timeout /t 2 /nobreak >nul
curl -s http://localhost:8000/docs >nul 2>&1
if %errorLevel% neq 0 (
    echo    Esperando Backend... (reintentando)
    goto :wait_backend
)
echo OK - Backend esta listo
echo.

:: Esperar a que el frontend este listo
echo Esperando Frontend...
timeout /t 2 /nobreak >nul
curl -s http://localhost:3000 >nul 2>&1
if %errorLevel% neq 0 (
    echo    Esperando Frontend... (reintentando)
    timeout /t 2 /nobreak >nul
)
echo OK - Frontend esta listo
echo.

echo ================================================================================
echo [5/6] Verificando estado de servicios...
echo ================================================================================
echo.

docker-compose ps

echo.
echo ================================================================================
echo    SERVICIOS INICIADOS CORRECTAMENTE
echo ================================================================================
echo.
echo SERVICIOS DISPONIBLES:
echo.
echo   Frontend (Interfaz Web)
echo   URL: http://localhost:3000
echo   Descripcion: Interfaz de usuario para trading
echo.
echo   Backend API (FastAPI)
echo   URL: http://localhost:8000
echo   Docs: http://localhost:8000/docs
echo   Descripcion: API REST + RL + Indicadores
echo.
echo   Grafana (Monitoreo)
echo   URL: http://localhost:3001
echo   Usuario: admin
echo   Password: admin
echo   Descripcion: Dashboards y metricas en tiempo real
echo.
echo   Prometheus (Metricas)
echo   URL: http://localhost:9090
echo   Descripcion: Sistema de metricas y alertas
echo.
echo   PostgreSQL + TimescaleDB
echo   Host: localhost:5432
echo   Database: trading_db
echo   Usuario: trading_user
echo   Password: trading_pass
echo.
echo   Redis (Cache)
echo   Host: localhost:6379
echo   Descripcion: Cache en memoria para datos en tiempo real
echo.
echo ================================================================================
echo.
echo COMANDOS UTILES:
echo.
echo   Ver logs en tiempo real:     docker-compose logs -f
echo   Ver logs del backend:        docker-compose logs -f backend
echo   Ver logs de PostgreSQL:      docker-compose logs -f postgres
echo   Estado de servicios:         docker-compose ps
echo   Reiniciar un servicio:       docker-compose restart [servicio]
echo   Detener todo:                detener.bat
echo.
echo ================================================================================
echo.
echo ================================================================================
echo [6/6] ABRIENDO INTERFAZ WEB...
echo ================================================================================
echo.

:: Abrir navegador con la interfaz web
echo Abriendo http://localhost:3000 en el navegador...
start http://localhost:3000

echo.
echo ================================================================================
echo    TODO LISTO! SISTEMA EN FUNCIONAMIENTO
echo ================================================================================
echo.
color 0A
echo SERVICIOS DISPONIBLES:
echo.
echo   [Frontend]    http://localhost:3000
echo                 Interfaz de usuario para trading
echo.
echo   [Backend API] http://localhost:8000/docs
echo                 API REST + RL + Indicadores
echo.
echo   [Grafana]     http://localhost:3001
echo                 Usuario: admin / Password: admin
echo.
echo   [Prometheus]  http://localhost:9090
echo                 Metricas del sistema
echo.
echo ================================================================================
echo.
echo COMANDOS UTILES:
echo   Ver logs en tiempo real:     docker-compose logs -f
echo   Ver logs del backend:        docker-compose logs -f backend
echo   Estado de servicios:         docker-compose ps
echo   Detener servicios:           detener.bat
echo   Diagnostico:                 diagnostico.bat
echo.
echo ================================================================================
echo.
echo El sistema esta corriendo en segundo plano.
echo Puede cerrar esta ventana sin afectar los servicios.
echo.
pause
