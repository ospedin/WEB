@echo off
color 0E
cls
echo ================================================================================
echo    VER LOGS EN TIEMPO REAL - TRADING PLATFORM AI
echo ================================================================================
echo.

:: Verificar que Docker esta corriendo
docker ps >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Docker no esta corriendo o no hay contenedores activos.
    echo.
    echo Por favor inicia los servicios primero con: iniciar.bat
    pause
    exit /b 1
)

echo De que servicio deseas ver los logs?
echo.
echo [1] Todos los servicios
echo [2] Backend (FastAPI + RL)
echo [3] PostgreSQL (Base de datos)
echo [4] Redis
echo [5] Frontend (Nginx)
echo [6] Grafana
echo [7] Prometheus
echo [0] Cancelar
echo.
set /p choice="Selecciona una opcion (0-7): "

if "%choice%"=="0" goto :cancel
if "%choice%"=="1" goto :all_logs
if "%choice%"=="2" goto :backend_logs
if "%choice%"=="3" goto :postgres_logs
if "%choice%"=="4" goto :redis_logs
if "%choice%"=="5" goto :frontend_logs
if "%choice%"=="6" goto :grafana_logs
if "%choice%"=="7" goto :prometheus_logs
goto :invalid_choice

:all_logs
echo.
echo ================================================================================
echo    LOGS DE TODOS LOS SERVICIOS (Ctrl+C para salir)
echo ================================================================================
echo.
docker-compose logs -f
goto :end

:backend_logs
echo.
echo ================================================================================
echo    LOGS DEL BACKEND (Ctrl+C para salir)
echo ================================================================================
echo.
echo Mostrando ultimas 50 lineas y siguiendo en tiempo real...
echo.
docker-compose logs -f --tail=50 backend
goto :end

:postgres_logs
echo.
echo ================================================================================
echo    LOGS DE POSTGRESQL (Ctrl+C para salir)
echo ================================================================================
echo.
echo Mostrando ultimas 50 lineas y siguiendo en tiempo real...
echo.
docker-compose logs -f --tail=50 postgres
goto :end

:redis_logs
echo.
echo ================================================================================
echo    LOGS DE REDIS (Ctrl+C para salir)
echo ================================================================================
echo.
echo Mostrando ultimas 50 lineas y siguiendo en tiempo real...
echo.
docker-compose logs -f --tail=50 redis
goto :end

:frontend_logs
echo.
echo ================================================================================
echo    LOGS DEL FRONTEND (Ctrl+C para salir)
echo ================================================================================
echo.
echo Mostrando ultimas 50 lineas y siguiendo en tiempo real...
echo.
docker-compose logs -f --tail=50 frontend
goto :end

:grafana_logs
echo.
echo ================================================================================
echo    LOGS DE GRAFANA (Ctrl+C para salir)
echo ================================================================================
echo.
echo Mostrando ultimas 50 lineas y siguiendo en tiempo real...
echo.
docker-compose logs -f --tail=50 grafana
goto :end

:prometheus_logs
echo.
echo ================================================================================
echo    LOGS DE PROMETHEUS (Ctrl+C para salir)
echo ================================================================================
echo.
echo Mostrando ultimas 50 lineas y siguiendo en tiempo real...
echo.
docker-compose logs -f --tail=50 prometheus
goto :end

:invalid_choice
echo.
echo [ERROR] Opcion invalida.
goto :end

:cancel
echo.
echo Operacion cancelada.
goto :end

:end
echo.
echo ================================================================================
pause
