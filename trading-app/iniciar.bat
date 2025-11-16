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
echo Verificando Docker Desktop...
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

echo Deteniendo contenedores antiguos si existen...
docker-compose down 2>nul
echo.

echo ================================================================================
echo    INICIANDO SERVICIOS
echo ================================================================================
echo.

echo [1/6] PostgreSQL + TimescaleDB...
echo [2/6] Redis...
echo [3/6] Backend FastAPI...
echo [4/6] Frontend Nginx...
echo [5/6] Grafana...
echo [6/6] Prometheus...
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
echo    VERIFICANDO QUE TODOS LOS SERVICIOS ESTEN FUNCIONANDO...
echo ================================================================================
echo.

:: Verificar PostgreSQL (esperar hasta 60 segundos)
echo [1/6] Verificando PostgreSQL...
set /a count=0
:check_postgres
docker exec trading_postgres pg_isready -U trading_user -d trading_db >nul 2>&1
if %errorLevel% equ 0 (
    echo OK - PostgreSQL esta listo
    goto :check_redis
)
set /a count+=1
if %count% geq 60 (
    echo [ERROR] PostgreSQL no inicio correctamente
    echo Mostrando logs de PostgreSQL:
    docker-compose logs postgres
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto :check_postgres

:check_redis
echo [2/6] Verificando Redis...
set /a count=0
:check_redis_loop
docker exec trading_redis redis-cli ping >nul 2>&1
if %errorLevel% equ 0 (
    echo OK - Redis esta listo
    goto :check_backend
)
set /a count+=1
if %count% geq 30 (
    echo [ERROR] Redis no inicio correctamente
    echo Mostrando logs de Redis:
    docker-compose logs redis
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto :check_redis_loop

:check_backend
echo [3/6] Verificando Backend (puede tardar 30-60 segundos)...
set /a count=0
:check_backend_loop
curl -s http://localhost:8000/ >nul 2>&1
if %errorLevel% equ 0 (
    echo OK - Backend esta listo y respondiendo
    goto :check_frontend
)
set /a count+=1
if %count% geq 90 (
    echo [ERROR] Backend no inicio correctamente
    echo.
    echo Mostrando logs del backend:
    docker-compose logs backend
    echo.
    echo Verifica que todas las dependencias estan instaladas en requirements.txt
    pause
    exit /b 1
)
if %count% equ 30 (
    echo Aun esperando al backend... ^(30s^)
)
if %count% equ 60 (
    echo Aun esperando al backend... ^(60s^)
)
timeout /t 1 /nobreak >nul
goto :check_backend_loop

:check_frontend
echo [4/6] Verificando Frontend...
set /a count=0
:check_frontend_loop
curl -s http://localhost:3000/ >nul 2>&1
if %errorLevel% equ 0 (
    echo OK - Frontend esta listo
    goto :check_grafana
)
set /a count+=1
if %count% geq 30 (
    echo [ERROR] Frontend no inicio correctamente
    echo Mostrando logs de Frontend:
    docker-compose logs frontend
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto :check_frontend_loop

:check_grafana
echo [5/6] Verificando Grafana...
set /a count=0
:check_grafana_loop
curl -s http://localhost:3001/ >nul 2>&1
if %errorLevel% equ 0 (
    echo OK - Grafana esta listo
    goto :check_prometheus
)
set /a count+=1
if %count% geq 30 (
    echo [ADVERTENCIA] Grafana no responde, pero no es critico
    goto :check_prometheus
)
timeout /t 1 /nobreak >nul
goto :check_grafana_loop

:check_prometheus
echo [6/6] Verificando Prometheus...
set /a count=0
:check_prometheus_loop
curl -s http://localhost:9090/ >nul 2>&1
if %errorLevel% equ 0 (
    echo OK - Prometheus esta listo
    goto :all_ready
)
set /a count+=1
if %count% geq 30 (
    echo [ADVERTENCIA] Prometheus no responde, pero no es critico
    goto :all_ready
)
timeout /t 1 /nobreak >nul
goto :check_prometheus_loop

:all_ready
echo.
echo ================================================================================
echo    TODOS LOS SERVICIOS ESTAN FUNCIONANDO CORRECTAMENTE
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
echo    ABRIENDO INTERFAZ WEB...
echo ================================================================================
echo.

:: Esperar 3 segundos adicionales para que el frontend este listo
timeout /t 3 /nobreak >nul

:: Abrir navegador con la interfaz web
echo Abriendo http://localhost:3000 en el navegador...
start http://localhost:3000

echo.
echo ================================================================================
echo    TODO LISTO! SISTEMA EN FUNCIONAMIENTO
echo ================================================================================
echo.
echo El sistema esta corriendo en segundo plano.
echo Puede cerrar esta ventana sin afectar los servicios.
echo.
echo Para detener los servicios ejecute: detener.bat
echo.
pause
