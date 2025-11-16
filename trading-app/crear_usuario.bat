@echo off
setlocal enabledelayedexpansion
color 0B
cls
echo ================================================================================
echo    CREAR USUARIO INICIAL - TRADING PLATFORM AI
echo ================================================================================
echo.

:: Verificar que PostgreSQL este corriendo
echo [1/2] Verificando que PostgreSQL este corriendo...
docker exec trading_postgres pg_isready -U ospedin -d trading_db >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo [ERROR] PostgreSQL no esta corriendo.
    echo.
    echo Por favor ejecuta primero: iniciar.bat
    echo.
    pause
    exit /b 1
)
echo OK - PostgreSQL esta corriendo
echo.

:: Ejecutar script de creación de usuario dentro del contenedor
echo [2/2] Creando usuario 'ospedin' en la base de datos...
echo.

docker exec -it trading_backend python create_user.py

if %errorLevel% neq 0 (
    echo.
    echo [ERROR] No se pudo crear el usuario.
    echo.
    pause
    exit /b 1
)

echo.
echo ================================================================================
echo    USUARIO CREADO EXITOSAMENTE
echo ================================================================================
echo.
echo Puedes iniciar sesion con:
echo   Username: ospedin
echo   Email: sguedia660smr@gmail.com
echo   Password: prueba19
echo.
echo El usuario esta pre-verificado y listo para usar.
echo.
pause
