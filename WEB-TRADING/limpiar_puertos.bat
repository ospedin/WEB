@echo off
color 0E
cls
echo ================================================================================
echo    LIMPIANDO PUERTOS OCUPADOS - TRADING PLATFORM AI
echo ================================================================================
echo.

echo Verificando y liberando puertos necesarios...
echo.

:: Detener contenedores Docker primero
echo [1/2] Deteniendo contenedores Docker existentes...
docker-compose down 2>nul
docker stop trading_backend trading_frontend trading_postgres trading_redis trading_prometheus trading_grafana 2>nul
docker rm -f trading_backend trading_frontend trading_postgres trading_redis trading_prometheus trading_grafana 2>nul
echo OK - Contenedores Docker limpiados
echo.

:: Liberar cada puerto
echo [2/2] Liberando puertos ocupados...
echo    Liberando puerto 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING 2^>nul') do taskkill /F /PID %%a >nul 2>&1

echo    Liberando puerto 3000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3000 ^| findstr LISTENING 2^>nul') do taskkill /F /PID %%a >nul 2>&1

echo    Liberando puerto 5432...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5432 ^| findstr LISTENING 2^>nul') do taskkill /F /PID %%a >nul 2>&1

echo    Liberando puerto 6379...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :6379 ^| findstr LISTENING 2^>nul') do taskkill /F /PID %%a >nul 2>&1

echo    Liberando puerto 9090...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :9090 ^| findstr LISTENING 2^>nul') do taskkill /F /PID %%a >nul 2>&1

echo    Liberando puerto 3001...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3001 ^| findstr LISTENING 2^>nul') do taskkill /F /PID %%a >nul 2>&1

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
