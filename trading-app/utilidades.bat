@echo off
color 0D
cls
echo ================================================================================
echo    UTILIDADES - TRADING PLATFORM AI
echo ================================================================================
echo.

:menu
echo Que deseas hacer?
echo.
echo [1]  Ver estado de servicios
echo [2]  Reiniciar un servicio
echo [3]  Reiniciar todos los servicios
echo [4]  Conectar a PostgreSQL (psql)
echo [5]  Conectar a Redis (redis-cli)
echo [6]  Ver uso de recursos (CPU, RAM)
echo [7]  Limpiar volumenes no utilizados
echo [8]  Entrenar modelo RL
echo [9]  Ver IP de los contenedores
echo [10] Exportar base de datos
echo [11] Importar base de datos
echo [0]  Salir
echo.
set /p choice="Selecciona una opcion (0-11): "

if "%choice%"=="0" goto :end
if "%choice%"=="1" goto :status
if "%choice%"=="2" goto :restart_service
if "%choice%"=="3" goto :restart_all
if "%choice%"=="4" goto :connect_postgres
if "%choice%"=="5" goto :connect_redis
if "%choice%"=="6" goto :resource_usage
if "%choice%"=="7" goto :cleanup
if "%choice%"=="8" goto :train_model
if "%choice%"=="9" goto :show_ips
if "%choice%"=="10" goto :export_db
if "%choice%"=="11" goto :import_db
goto :invalid

:status
echo.
echo ================================================================================
echo    ESTADO DE SERVICIOS
echo ================================================================================
echo.
docker-compose ps
echo.
pause
cls
goto :menu

:restart_service
echo.
echo Servicios disponibles:
echo   - backend
echo   - postgres
echo   - redis
echo   - frontend
echo   - grafana
echo   - prometheus
echo.
set /p service="Nombre del servicio a reiniciar: "
echo.
echo Reiniciando %service%...
docker-compose restart %service%
echo.
echo OK - Servicio reiniciado
echo.
pause
cls
goto :menu

:restart_all
echo.
echo Reiniciando todos los servicios...
docker-compose restart
echo.
echo OK - Todos los servicios reiniciados
echo.
pause
cls
goto :menu

:connect_postgres
echo.
echo ================================================================================
echo    CONECTANDO A POSTGRESQL
echo ================================================================================
echo.
echo Conectando como trading_user a la base de datos trading_db...
echo Para salir escribe: \q
echo.
pause
docker exec -it trading_postgres psql -U trading_user -d trading_db
echo.
pause
cls
goto :menu

:connect_redis
echo.
echo ================================================================================
echo    CONECTANDO A REDIS
echo ================================================================================
echo.
echo Para salir escribe: exit
echo.
pause
docker exec -it trading_redis redis-cli
echo.
pause
cls
goto :menu

:resource_usage
echo.
echo ================================================================================
echo    USO DE RECURSOS
echo ================================================================================
echo.
docker stats --no-stream
echo.
pause
cls
goto :menu

:cleanup
echo.
echo ================================================================================
echo    LIMPIEZA DE VOLUMENES NO UTILIZADOS
echo ================================================================================
echo.
echo Esto eliminara volumenes huerfanos (no afecta a servicios activos)
echo.
set /p confirm="Continuar? (S/N): "
if /i not "%confirm%"=="S" (
    cls
    goto :menu
)
docker volume prune -f
echo.
echo OK - Limpieza completada
echo.
pause
cls
goto :menu

:train_model
echo.
echo ================================================================================
echo    ENTRENAR MODELO RL
echo ================================================================================
echo.
echo Ejecutando entrenamiento dentro del contenedor backend...
echo.
docker exec -it trading_backend python ml/train_rl.py
echo.
echo OK - Entrenamiento completado
echo.
pause
cls
goto :menu

:show_ips
echo.
echo ================================================================================
echo    DIRECCIONES IP DE CONTENEDORES
echo ================================================================================
echo.
for /f "tokens=*" %%i in ('docker ps --format "{{.Names}}"') do (
    for /f "tokens=*" %%j in ('docker inspect -f "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}" %%i') do (
        echo %%i: %%j
    )
)
echo.
pause
cls
goto :menu

:export_db
echo.
echo ================================================================================
echo    EXPORTAR BASE DE DATOS
echo ================================================================================
echo.
set /p filename="Nombre del archivo (sin extension): "
echo.
echo Exportando a %filename%.sql...
docker exec trading_postgres pg_dump -U trading_user trading_db > %filename%.sql
echo.
echo OK - Base de datos exportada a %filename%.sql
echo.
pause
cls
goto :menu

:import_db
echo.
echo ================================================================================
echo    IMPORTAR BASE DE DATOS
echo ================================================================================
echo.
set /p filename="Nombre del archivo a importar (con .sql): "
echo.
if not exist "%filename%" (
    echo [ERROR] Archivo no encontrado: %filename%
    pause
    cls
    goto :menu
)
echo.
echo Importando %filename%...
type %filename% | docker exec -i trading_postgres psql -U trading_user -d trading_db
echo.
echo OK - Base de datos importada
echo.
pause
cls
goto :menu

:invalid
echo.
echo [ERROR] Opcion invalida.
timeout /t 2 /nobreak >nul
cls
goto :menu

:end
echo.
echo Saliendo...
exit /b 0
