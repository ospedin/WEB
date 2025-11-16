@echo off
color 0C
cls
echo ================================================================================
echo    DETENIENDO SERVICIOS - TRADING PLATFORM AI
echo ================================================================================
echo.

:: Verificar que Docker esta corriendo
docker ps >nul 2>&1
if %errorLevel% neq 0 (
    echo [ADVERTENCIA] Docker no esta corriendo o no hay contenedores activos.
    echo.
    pause
    exit /b 0
)

echo Que deseas hacer?
echo.
echo [1] Detener servicios (conservar datos)
echo [2] Detener y eliminar todo (incluye volumenes y datos)
echo [3] Cancelar
echo.
set /p choice="Selecciona una opcion (1-3): "

if "%choice%"=="1" goto :stop_services
if "%choice%"=="2" goto :stop_and_remove
if "%choice%"=="3" goto :cancel
goto :invalid_choice

:stop_services
echo.
echo ================================================================================
echo    DETENIENDO SERVICIOS (conservando datos)...
echo ================================================================================
echo.

echo Deteniendo contenedores...
docker-compose stop

if %errorLevel% neq 0 (
    echo.
    echo [ERROR] Error al detener los servicios.
    pause
    exit /b 1
)

echo.
echo OK - Servicios detenidos correctamente
echo.
echo Los datos se han conservado en los volumenes de Docker.
echo Para reiniciar, ejecuta: iniciar.bat
echo.
goto :end

:stop_and_remove
echo.
echo ================================================================================
echo    ADVERTENCIA - ELIMINACION COMPLETA
echo ================================================================================
echo.
echo Esta accion eliminara:
echo   - Todos los contenedores
echo   - Todas las redes
echo   - Todos los volumenes (BASE DE DATOS, modelos, logs)
echo   - Todas las imagenes no utilizadas
echo.
echo NO SE PODRAN RECUPERAR LOS DATOS
echo.
set /p confirm="Estas seguro? Escribe 'SI' para confirmar: "

if /i not "%confirm%"=="SI" (
    echo.
    echo Operacion cancelada.
    goto :end
)

echo.
echo Deteniendo y eliminando servicios...
docker-compose down -v --remove-orphans

if %errorLevel% neq 0 (
    echo.
    echo [ERROR] Error al eliminar los servicios.
    pause
    exit /b 1
)

echo.
echo Eliminando imagenes no utilizadas...
docker image prune -f

echo.
echo OK - Eliminacion completa realizada
echo.
echo Para volver a usar el sistema, ejecuta: instalar.bat
echo.
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
echo ================================================================================
echo.

:: Mostrar estado final
echo Estado actual de contenedores:
echo.
docker-compose ps 2>nul
if %errorLevel% neq 0 (
    echo No hay contenedores corriendo.
)

echo.
echo ================================================================================
pause
