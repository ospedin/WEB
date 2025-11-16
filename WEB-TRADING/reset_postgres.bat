@echo off
color 0C
cls
echo ================================================================================
echo    RESETEAR POSTGRESQL - TRADING PLATFORM AI
echo ================================================================================
echo.
echo ADVERTENCIA: Este script eliminara COMPLETAMENTE el volumen de PostgreSQL.
echo Se perderan todos los datos de la base de datos.
echo.
echo Esto es necesario cuando:
echo   - Cambias las credenciales de PostgreSQL
echo   - PostgreSQL no inicia correctamente
echo   - Hay errores de autenticacion
echo.
echo ================================================================================
echo.

set /p confirm="¿Estas seguro de que deseas continuar? (S/N): "
if /i not "%confirm%"=="S" (
    echo.
    echo Operacion cancelada.
    pause
    exit /b 0
)

echo.
echo ================================================================================
echo    ELIMINANDO CONTENEDORES Y VOLUMENES
echo ================================================================================
echo.

echo [1/4] Deteniendo servicios...
docker-compose down 2>nul
docker stop trading_postgres 2>nul
docker rm -f trading_postgres 2>nul
echo OK - Servicios detenidos
echo.

echo [2/4] Eliminando volumen de PostgreSQL...
docker volume rm trading-app_postgres_data 2>nul
if %errorLevel% equ 0 (
    echo OK - Volumen eliminado
) else (
    echo ADVERTENCIA - No se encontro el volumen o ya estaba eliminado
)
echo.

echo [3/4] Limpiando volumenes huerfanos...
docker volume prune -f >nul 2>&1
echo OK - Volumenes huerfanos eliminados
echo.

echo [4/4] Verificando limpieza...
docker volume ls | findstr postgres >nul 2>&1
if %errorLevel% equ 0 (
    echo ADVERTENCIA - Todavia hay volumenes de PostgreSQL
    echo Puede que necesites eliminarlos manualmente:
    echo    docker volume ls | findstr postgres
    echo    docker volume rm [nombre_del_volumen]
) else (
    echo OK - No se encontraron volumenes de PostgreSQL
)
echo.

echo ================================================================================
echo    LIMPIEZA COMPLETA
echo ================================================================================
echo.
echo PostgreSQL ha sido completamente reseteado.
echo.
echo PROXIMOS PASOS:
echo   1. Ejecuta: iniciar.bat
echo   2. PostgreSQL se creara con las nuevas credenciales:
echo      Usuario: ospedin
echo      Password: scouder
echo.
echo ================================================================================
echo.
pause
