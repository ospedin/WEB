@echo off
color 0E
cls
echo ================================================================================
echo    DIAGNOSTICO DE SERVICIOS - TRADING PLATFORM
echo ================================================================================
echo.
echo Este script te ayudara a diagnosticar problemas con los servicios.
echo.

echo ============================================================================
echo 1. VERIFICANDO ESTADO DE DOCKER
echo ============================================================================
echo.

docker --version
if %errorLevel% neq 0 (
    echo [ERROR] Docker no esta instalado
    echo Por favor instala Docker Desktop desde:
    echo https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)

echo.
docker ps >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Docker Desktop no esta corriendo
    echo Por favor inicia Docker Desktop manualmente
    pause
    exit /b 1
)

echo OK - Docker esta corriendo
echo.

echo ============================================================================
echo 2. ESTADO DE CONTENEDORES
echo ============================================================================
echo.

docker-compose ps

echo.
echo ============================================================================
echo 3. VERIFICANDO PUERTOS
echo ============================================================================
echo.

echo Puerto 8000 (Backend):
netstat -an | findstr ":8000" | findstr "LISTENING"
if %errorLevel% equ 0 (
    echo OK - Puerto 8000 esta en uso
) else (
    echo [ADVERTENCIA] Puerto 8000 NO esta en uso
)

echo.
echo Puerto 3000 (Frontend):
netstat -an | findstr ":3000" | findstr "LISTENING"
if %errorLevel% equ 0 (
    echo OK - Puerto 3000 esta en uso
) else (
    echo [ADVERTENCIA] Puerto 3000 NO esta en uso
)

echo.
echo Puerto 5432 (PostgreSQL):
netstat -an | findstr ":5432" | findstr "LISTENING"
if %errorLevel% equ 0 (
    echo OK - Puerto 5432 esta en uso
) else (
    echo [ADVERTENCIA] Puerto 5432 NO esta en uso
)

echo.
echo ============================================================================
echo 4. PROBANDO CONECTIVIDAD
echo ============================================================================
echo.

echo Probando Backend API...
curl -s http://localhost:8000/ >nul 2>&1
if %errorLevel% equ 0 (
    echo OK - Backend responde correctamente
    curl -s http://localhost:8000/
) else (
    echo [ERROR] Backend NO responde
    echo.
    echo Mostrando logs del backend:
    docker-compose logs --tail=100 backend
)

echo.
echo Probando Frontend...
curl -s -I http://localhost:3000/ | findstr "200"
if %errorLevel% equ 0 (
    echo OK - Frontend responde correctamente
) else (
    echo [ERROR] Frontend NO responde
)

echo.
echo ============================================================================
echo 5. LOGS DE SERVICIOS (ultimas 50 lineas)
echo ============================================================================
echo.

echo === BACKEND ===
docker-compose logs --tail=50 backend

echo.
echo === POSTGRES ===
docker-compose logs --tail=20 postgres

echo.
echo === REDIS ===
docker-compose logs --tail=20 redis

echo.
echo === FRONTEND ===
docker-compose logs --tail=20 frontend

echo.
echo ============================================================================
echo 6. USO DE RECURSOS
echo ============================================================================
echo.

docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"

echo.
echo ============================================================================
echo    DIAGNOSTICO COMPLETADO
echo ============================================================================
echo.
echo Si hay errores, revisa los logs arriba.
echo.
echo SOLUCIONES COMUNES:
echo.
echo 1. Si el backend no responde:
echo    - Ejecuta: docker-compose restart backend
echo    - Verifica que requirements.txt tenga todas las dependencias
echo.
echo 2. Si PostgreSQL falla:
echo    - Ejecuta: docker-compose down -v
echo    - Luego ejecuta: iniciar.bat
echo.
echo 3. Si necesitas reconstruir todo:
echo    - Ejecuta: docker-compose down -v
echo    - Ejecuta: docker-compose build --no-cache
echo    - Ejecuta: iniciar.bat
echo.
pause
