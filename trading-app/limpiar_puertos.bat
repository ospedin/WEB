@echo off
color 0E
cls
echo ================================================================================
echo    LIMPIANDO PUERTOS OCUPADOS - TRADING PLATFORM AI
echo ================================================================================
echo.

echo Verificando y liberando puertos necesarios...
echo.

:: Lista de puertos a verificar y liberar
set PORTS=8000 3000 5432 6379 9090 3001

:: Detener contenedores Docker primero
echo [1/2] Deteniendo contenedores Docker existentes...
docker-compose down 2>nul
docker stop trading_backend trading_frontend trading_postgres trading_redis trading_prometheus trading_grafana 2>nul
docker rm -f trading_backend trading_frontend trading_postgres trading_redis trading_prometheus trading_grafana 2>nul
echo OK - Contenedores Docker limpiados
echo.

:: Liberar cada puerto
echo [2/2] Liberando puertos ocupados...
for %%P in (%PORTS%) do (
    echo    Verificando puerto %%P...
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr :%%P ^| findstr LISTENING') do (
        set PID=%%a
        if not "!PID!"=="" (
            echo       [OCUPADO] Liberando puerto %%P (PID: !PID!)
            taskkill /F /PID !PID! >nul 2>&1
            if !errorLevel! equ 0 (
                echo       [OK] Puerto %%P liberado
            ) else (
                echo       [ADVERTENCIA] No se pudo liberar puerto %%P (puede requerir permisos de administrador)
            )
        )
    )
)

echo.
echo ================================================================================
echo    PUERTOS LIMPIADOS
echo ================================================================================
echo.
echo Los siguientes puertos han sido verificados y liberados:
echo    - 8000 (Backend API)
echo    - 3000 (Frontend)
echo    - 5432 (PostgreSQL)
echo    - 6379 (Redis)
echo    - 9090 (Prometheus)
echo    - 3001 (Grafana)
echo.
echo Ya puedes iniciar los servicios con: iniciar.bat
echo.
