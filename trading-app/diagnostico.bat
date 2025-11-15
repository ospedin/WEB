@echo off
color 0F
cls
echo ================================================================================
echo    DIAGNOSTICO DEL SISTEMA - TRADING PLATFORM AI
echo ================================================================================
echo.
echo Este script recopilara informacion para ayudar a diagnosticar problemas
echo.
pause

echo.
echo ================================================================================
echo    1. INFORMACION DEL SISTEMA
echo ================================================================================
echo.

echo [Windows Version]
ver
echo.

echo [Docker Version]
docker --version 2>nul
if %errorLevel% neq 0 (
    echo ERROR - Docker no esta instalado o no esta en el PATH
) else (
    echo OK - Docker instalado
)
echo.

echo [Docker Compose Version]
docker-compose --version 2>nul
if %errorLevel% neq 0 (
    echo ERROR - Docker Compose no esta instalado
) else (
    echo OK - Docker Compose instalado
)
echo.

echo [Docker Status]
docker ps >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR - Docker no esta corriendo
    echo Solucion: Inicia Docker Desktop
) else (
    echo OK - Docker esta corriendo
)
echo.

echo.
echo ================================================================================
echo    2. ESTADO DE SERVICIOS
echo ================================================================================
echo.

docker-compose ps 2>nul
if %errorLevel% neq 0 (
    echo ERROR - No se pudo obtener el estado de servicios
    echo Posibles causas:
    echo - No estas en el directorio correcto
    echo - docker-compose.yml no existe
    echo - Docker no esta corriendo
)
echo.

echo.
echo ================================================================================
echo    3. USO DE RECURSOS
echo ================================================================================
echo.

docker stats --no-stream 2>nul
if %errorLevel% neq 0 (
    echo ERROR - No se pudieron obtener estadisticas de recursos
)
echo.

echo.
echo ================================================================================
echo    4. VERIFICACION DE PUERTOS
echo ================================================================================
echo.

echo Verificando puertos en uso:
echo.

netstat -ano | findstr :3000 >nul
if %errorLevel% equ 0 (
    echo OK - Puerto 3000 (Frontend) EN USO
) else (
    echo OK - Puerto 3000 (Frontend) LIBRE
)

netstat -ano | findstr :8000 >nul
if %errorLevel% equ 0 (
    echo OK - Puerto 8000 (Backend) EN USO
) else (
    echo OK - Puerto 8000 (Backend) LIBRE
)

netstat -ano | findstr :5432 >nul
if %errorLevel% equ 0 (
    echo OK - Puerto 5432 (PostgreSQL) EN USO
) else (
    echo OK - Puerto 5432 (PostgreSQL) LIBRE
)

netstat -ano | findstr :6379 >nul
if %errorLevel% equ 0 (
    echo OK - Puerto 6379 (Redis) EN USO
) else (
    echo OK - Puerto 6379 (Redis) LIBRE
)

netstat -ano | findstr :3001 >nul
if %errorLevel% equ 0 (
    echo OK - Puerto 3001 (Grafana) EN USO
) else (
    echo OK - Puerto 3001 (Grafana) LIBRE
)

netstat -ano | findstr :9090 >nul
if %errorLevel% equ 0 (
    echo OK - Puerto 9090 (Prometheus) EN USO
) else (
    echo OK - Puerto 9090 (Prometheus) LIBRE
)
echo.

echo.
echo ================================================================================
echo    5. VERIFICACION DE ARCHIVOS CRITICOS
echo ================================================================================
echo.

if exist "docker-compose.yml" (
    echo OK - docker-compose.yml existe
) else (
    echo ERROR - docker-compose.yml NO ENCONTRADO
)

if exist ".env" (
    echo OK - .env existe
) else (
    echo ADVERTENCIA - .env NO ENCONTRADO
)

if exist "backend\requirements.txt" (
    echo OK - backend\requirements.txt existe
) else (
    echo ERROR - backend\requirements.txt NO ENCONTRADO
)

if exist "backend\Dockerfile" (
    echo OK - backend\Dockerfile existe
) else (
    echo ERROR - backend\Dockerfile NO ENCONTRADO
)

if exist "backend\main.py" (
    echo OK - backend\main.py existe
) else (
    echo ERROR - backend\main.py NO ENCONTRADO
)

if exist "backend\db\init.sql" (
    echo OK - backend\db\init.sql existe
) else (
    echo ERROR - backend\db\init.sql NO ENCONTRADO
)
echo.

echo.
echo ================================================================================
echo    6. LOGS RECIENTES DE ERRORES
echo ================================================================================
echo.

echo [Backend Errors - Ultimas 20 lineas]
docker-compose logs backend --tail=20 2>nul | findstr /i "error ERROR exception Exception"
if %errorLevel% neq 0 (
    echo OK - No se encontraron errores recientes en backend
)
echo.

echo [PostgreSQL Errors - Ultimas 20 lineas]
docker-compose logs postgres --tail=20 2>nul | findstr /i "error ERROR fatal FATAL"
if %errorLevel% neq 0 (
    echo OK - No se encontraron errores recientes en PostgreSQL
)
echo.

echo.
echo ================================================================================
echo    SOLUCIONES COMUNES
echo ================================================================================
echo.
echo 1. Si Docker no esta instalado:
echo    - Descarga e instala Docker Desktop desde docker.com
echo.
echo 2. Si Docker no esta corriendo:
echo    - Abre Docker Desktop manualmente
echo.
echo 3. Si faltan archivos criticos:
echo    - Verifica que estas en el directorio correcto
echo    - Re-clona el repositorio si es necesario
echo.
echo 4. Si hay errores en los logs:
echo    - Ejecuta: ver_logs.bat para mas detalles
echo    - Revisa las credenciales en .env
echo.
echo 5. Si los servicios no inician:
echo    - Ejecuta: detener.bat (opcion 1)
echo    - Luego: iniciar.bat
echo.
echo 6. Si hay conflictos de puertos:
echo    - Cierra aplicaciones que usen puertos 3000, 8000, 5432, 6379
echo    - O modifica docker-compose.yml para usar otros puertos
echo.
echo ================================================================================
echo.
pause
