@echo off
color 0D
cls
echo ================================================================================
echo    CONFIGURACION DE BASE DE DATOS - TRADING PLATFORM AI
echo ================================================================================
echo.
echo Este script configura las credenciales de administrador de PostgreSQL
echo.

:: Configuracion de credenciales
set DB_USER=ospedin
set DB_PASSWORD=scouder
set DB_NAME=trading_db
set DB_HOST=localhost
set DB_PORT=5432

echo ================================================================================
echo    CREDENCIALES DE BASE DE DATOS
echo ================================================================================
echo.
echo   Usuario:     %DB_USER%
echo   Contraseña:  %DB_PASSWORD%
echo   Base de datos: %DB_NAME%
echo   Host:        %DB_HOST%
echo   Puerto:      %DB_PORT%
echo.
echo ================================================================================
echo.

echo Verificando si Docker esta corriendo...
docker ps >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Docker no esta corriendo.
    echo Por favor inicia Docker Desktop primero.
    pause
    exit /b 1
)
echo OK - Docker esta corriendo
echo.

echo Verificando si PostgreSQL esta corriendo...
docker ps | findstr trading_postgres >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] El contenedor de PostgreSQL no esta corriendo.
    echo Por favor ejecuta: iniciar.bat
    pause
    exit /b 1
)
echo OK - PostgreSQL esta corriendo
echo.

echo ================================================================================
echo    OPCIONES DE GESTION
echo ================================================================================
echo.
echo [1] Conectar a PostgreSQL (psql)
echo [2] Ver tablas de la base de datos
echo [3] Crear backup de la base de datos
echo [4] Restaurar backup de la base de datos
echo [5] Reiniciar PostgreSQL
echo [6] Ver logs de PostgreSQL
echo [7] Salir
echo.
set /p option="Selecciona una opcion (1-7): "

if "%option%"=="1" goto :connect_psql
if "%option%"=="2" goto :show_tables
if "%option%"=="3" goto :backup_db
if "%option%"=="4" goto :restore_db
if "%option%"=="5" goto :restart_postgres
if "%option%"=="6" goto :show_logs
if "%option%"=="7" goto :exit_script
goto :invalid_option

:connect_psql
echo.
echo ================================================================================
echo    CONECTANDO A POSTGRESQL
echo ================================================================================
echo.
echo Conectando como usuario: %DB_USER%
echo Para salir de psql, escribe: \q
echo.
timeout /t 2 /nobreak >nul
docker exec -it trading_postgres psql -U %DB_USER% -d %DB_NAME%
goto :menu

:show_tables
echo.
echo ================================================================================
echo    TABLAS DE LA BASE DE DATOS
echo ================================================================================
echo.
docker exec -it trading_postgres psql -U %DB_USER% -d %DB_NAME% -c "\dt"
echo.
pause
goto :menu

:backup_db
echo.
echo ================================================================================
echo    CREAR BACKUP DE LA BASE DE DATOS
echo ================================================================================
echo.
set BACKUP_FILE=backup_%DB_NAME%_%date:~-4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%%time:~6,2%.sql
set BACKUP_FILE=%BACKUP_FILE: =0%
echo Creando backup: %BACKUP_FILE%
echo.
docker exec trading_postgres pg_dump -U %DB_USER% %DB_NAME% > "%BACKUP_FILE%"
if %errorLevel% equ 0 (
    echo OK - Backup creado exitosamente: %BACKUP_FILE%
) else (
    echo ERROR - No se pudo crear el backup
)
echo.
pause
goto :menu

:restore_db
echo.
echo ================================================================================
echo    RESTAURAR BACKUP DE LA BASE DE DATOS
echo ================================================================================
echo.
echo ADVERTENCIA: Esto sobreescribira la base de datos actual
echo.
set /p backup_file="Ingresa el nombre del archivo de backup: "
if not exist "%backup_file%" (
    echo ERROR - El archivo no existe: %backup_file%
    pause
    goto :menu
)
echo.
echo Restaurando backup: %backup_file%
type "%backup_file%" | docker exec -i trading_postgres psql -U %DB_USER% %DB_NAME%
if %errorLevel% equ 0 (
    echo OK - Backup restaurado exitosamente
) else (
    echo ERROR - No se pudo restaurar el backup
)
echo.
pause
goto :menu

:restart_postgres
echo.
echo ================================================================================
echo    REINICIANDO POSTGRESQL
echo ================================================================================
echo.
echo Reiniciando contenedor de PostgreSQL...
docker restart trading_postgres
if %errorLevel% equ 0 (
    echo OK - PostgreSQL reiniciado
    echo Esperando que PostgreSQL este listo...
    timeout /t 5 /nobreak >nul
) else (
    echo ERROR - No se pudo reiniciar PostgreSQL
)
echo.
pause
goto :menu

:show_logs
echo.
echo ================================================================================
echo    LOGS DE POSTGRESQL
echo ================================================================================
echo.
echo Mostrando ultimos 50 logs (Ctrl+C para salir)...
echo.
timeout /t 2 /nobreak >nul
docker logs --tail=50 -f trading_postgres
goto :menu

:invalid_option
echo.
echo [ERROR] Opcion invalida
timeout /t 2 /nobreak >nul
goto :menu

:menu
echo.
echo ================================================================================
echo    OPCIONES DE GESTION
echo ================================================================================
echo.
echo [1] Conectar a PostgreSQL (psql)
echo [2] Ver tablas de la base de datos
echo [3] Crear backup de la base de datos
echo [4] Restaurar backup de la base de datos
echo [5] Reiniciar PostgreSQL
echo [6] Ver logs de PostgreSQL
echo [7] Salir
echo.
set /p option="Selecciona una opcion (1-7): "

if "%option%"=="1" goto :connect_psql
if "%option%"=="2" goto :show_tables
if "%option%"=="3" goto :backup_db
if "%option%"=="4" goto :restore_db
if "%option%"=="5" goto :restart_postgres
if "%option%"=="6" goto :show_logs
if "%option%"=="7" goto :exit_script
goto :invalid_option

:exit_script
echo.
echo ================================================================================
echo    SALIENDO...
echo ================================================================================
echo.
timeout /t 1 /nobreak >nul
exit /b 0
