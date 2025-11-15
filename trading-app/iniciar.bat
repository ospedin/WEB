@echo off
color 0B
cls
echo ================================================================================
echo    INICIANDO SERVICIOS - TRADING PLATFORM AI
echo ================================================================================
echo.

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
echo Esperando que todos los servicios esten listos...
echo ================================================================================
echo.

:: Esperar 10 segundos para que los servicios inicien
timeout /t 10 /nobreak >nul

:: Verificar estado de servicios
echo Verificando servicios...
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
echo Presiona cualquier tecla para cerrar (los servicios seguiran corriendo)...
pause >nul
