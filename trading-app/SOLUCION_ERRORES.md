# Solución de Errores - Trading Platform AI

## Fecha: 2025-11-15

## Problemas Identificados y Solucionados

### 1. ❌ Error: Puerto 8000 ocupado
**Problema:** El puerto 8000 (Backend) estaba siendo utilizado por otro proceso, causando el error:
```
Error response from daemon: ports are not available: exposing port TCP 0.0.0.0:8000
```

**Solución:**
- ✅ Creado script `limpiar_puertos.bat` que libera automáticamente todos los puertos necesarios (8000, 3000, 5432, 6379, 9090, 3001)
- ✅ Modificado `iniciar.bat` para liberar puertos automáticamente antes de iniciar los servicios
- ✅ Agregado limpieza de contenedores Docker antiguos

### 2. ❌ Error: Failed to fetch desde el frontend
**Problema:** El frontend no podía conectarse al backend en `http://localhost:8000`

**Solución:**
- ✅ Mejorado el script `iniciar.bat` con verificación de que todos los servicios estén funcionando antes de abrir el navegador
- ✅ Agregado healthchecks para:
  - PostgreSQL (espera hasta que esté listo para aceptar conexiones)
  - Redis (espera ping exitoso)
  - Backend API (espera respuesta HTTP)
  - Frontend (espera respuesta HTTP)

### 3. ❌ Configuración TopstepX sin botón Conectar/Desconectar
**Problema:** El usuario solicitó un botón dinámico que cambie entre "Conectar" y "Desconectar" según el estado

**Solución:**
- ✅ Implementado botón dinámico en la página de Configuración
- ✅ El botón cambia de:
  - **"Conectar"** (azul) → **"Desconectar"** (rojo) cuando se conecta
  - **"Desconectar"** (rojo) → **"Conectar"** (azul) cuando se desconecta
- ✅ Agregado indicador visual de estado de conexión con:
  - Ícono verde/rojo según estado
  - Texto descriptivo
  - Información de Account ID cuando está conectado
- ✅ Las credenciales se guardan en localStorage para persistencia
- ✅ Al recargar la página, se restaura el estado de conexión automáticamente

## Archivos Modificados

### Nuevos Archivos
1. **`limpiar_puertos.bat`** - Script para limpiar puertos ocupados manualmente

### Archivos Actualizados
1. **`iniciar.bat`** - Mejorado con:
   - Limpieza automática de puertos
   - Verificación de servicios con healthchecks
   - Mejor manejo de errores
   - Mensajes de progreso más claros
   - Espera activa hasta que cada servicio esté listo

2. **`frontend/index.html`** - Actualizado con:
   - Nuevo indicador de estado de conexión TopstepX
   - Botón dinámico Conectar/Desconectar
   - Información de Account ID

3. **`frontend/app.js`** - Mejorado con:
   - Estado de conexión TopstepX en el objeto `state`
   - Función `toggleTopstepConnection()` para conectar/desconectar
   - Función `connectTopstepX()` para establecer conexión
   - Función `disconnectTopstepX()` para cerrar conexión
   - Función `loadSavedTopstepConfig()` para restaurar configuración guardada
   - Función mejorada `testTopstepConnection()` con mejor feedback visual
   - Guardado de credenciales en localStorage

## Funcionalidades Agregadas

### 1. Limpieza Automática de Puertos
El script `iniciar.bat` ahora:
- Detiene contenedores Docker antiguos
- Libera puertos del sistema operativo automáticamente
- Verifica que los puertos estén disponibles antes de iniciar

### 2. Verificación de Servicios
El script ahora espera activamente hasta que cada servicio esté listo:
- **PostgreSQL**: Verifica con `pg_isready`
- **Redis**: Verifica con `redis-cli ping`
- **Backend**: Verifica con petición HTTP a `/docs`
- **Frontend**: Verifica con petición HTTP a `/`

### 3. Sistema de Conexión TopstepX Mejorado
- **Estado Persistente**: Las credenciales se guardan en localStorage
- **Indicador Visual**: Muestra estado actual (conectado/desconectado)
- **Botón Dinámico**: Cambia automáticamente entre Conectar/Desconectar
- **Información en Tiempo Real**: Muestra Account ID cuando está conectado
- **Manejo de Errores**: Mensajes claros cuando falla la conexión

## Instrucciones de Uso

### Iniciar el Sistema
1. Ejecuta `iniciar.bat`
2. El script automáticamente:
   - Limpiará los puertos ocupados
   - Iniciará Docker Desktop si no está corriendo
   - Iniciará todos los servicios
   - Esperará a que todos estén listos
   - Abrirá el navegador automáticamente

### Conectar a TopstepX
1. Abre la aplicación en http://localhost:3000
2. Inicia sesión o regístrate
3. Ve a la pestaña "Configuración"
4. Ingresa tu usuario y API Key de TopstepX
5. Haz clic en "Conectar"
6. El botón cambiará a "Desconectar" y mostrará el Account ID
7. Para desconectar, simplemente haz clic en "Desconectar"

### Limpiar Puertos Manualmente
Si necesitas limpiar los puertos sin iniciar los servicios:
```
limpiar_puertos.bat
```

## Verificaciones Realizadas

### Primera Pasada ✅
- Script de limpieza de puertos creado
- iniciar.bat mejorado con healthchecks
- Botón Conectar/Desconectar implementado

### Segunda Pasada ✅
- Verificado que todos los cambios funcionen correctamente
- Probado el guardado de configuración en localStorage
- Verificado el cambio dinámico del botón

### Tercera Pasada ✅
- Revisado el código para asegurar consistencia
- Verificado que no haya errores de sintaxis
- Confirmado que todos los archivos estén actualizados

## Servicios Disponibles

Una vez iniciado el sistema, tendrás acceso a:

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000/docs
- **Grafana**: http://localhost:3001 (admin/admin)
- **Prometheus**: http://localhost:9090
- **PostgreSQL**: localhost:5432 (usuario: ospedin, contraseña: scouder)
- **Redis**: localhost:6379

## Comandos Útiles

- `iniciar.bat` - Inicia todos los servicios
- `detener.bat` - Detiene los servicios
- `limpiar_puertos.bat` - Limpia puertos ocupados
- `config_db.bat` - Gestión de base de datos PostgreSQL (conectar, backup, restore, etc.)
- `diagnostico.bat` - Muestra diagnóstico del sistema
- `ver_logs.bat` - Muestra logs en tiempo real

## Gestión de Base de Datos

### Nuevo Script: `config_db.bat`

He creado un script completo para gestionar la base de datos PostgreSQL con tus credenciales:

**Credenciales configuradas:**
- Usuario: `ospedin`
- Contraseña: `scouder`
- Base de datos: `trading_db`
- Puerto: `5432`

**Funcionalidades del script:**

1. **Conectar a PostgreSQL (psql)** - Abre una terminal interactiva de PostgreSQL
2. **Ver tablas** - Muestra todas las tablas de la base de datos
3. **Crear backup** - Genera un archivo de backup con fecha y hora
4. **Restaurar backup** - Restaura la base de datos desde un archivo de backup
5. **Reiniciar PostgreSQL** - Reinicia el contenedor de PostgreSQL
6. **Ver logs** - Muestra los logs de PostgreSQL en tiempo real

**Ejemplo de uso:**
```batch
# Ejecutar el script
config_db.bat

# Luego selecciona una opción del menú:
# [1] Para conectarte a la base de datos
# [3] Para crear un backup
# etc.
```

## Notas Importantes

1. **Puertos Ocupados**: Si algún puerto sigue ocupado después de ejecutar `limpiar_puertos.bat`, es posible que necesites ejecutar el script como Administrador.

2. **Docker Desktop**: Asegúrate de que Docker Desktop tenga suficientes recursos asignados (mínimo 4GB RAM recomendado).

3. **Primera Ejecución**: La primera vez puede tardar más porque Docker necesita descargar las imágenes. IMPORTANTE: Como se cambiaron las credenciales de PostgreSQL, es necesario eliminar el volumen anterior y crear uno nuevo.

4. **Credenciales TopstepX**: Las credenciales se guardan localmente en el navegador (localStorage). Si cambias de navegador o limpias los datos, necesitarás reconectar.

5. **Credenciales de Base de Datos**: Todas las credenciales de PostgreSQL han sido actualizadas a `ospedin`/`scouder`. El backend y todos los scripts usan estas credenciales automáticamente.

## Solución a Problemas Comunes

### El puerto 8000 sigue ocupado
```batch
# Ejecuta como Administrador
limpiar_puertos.bat
```

### Los servicios no inician
```batch
# Verifica que Docker Desktop esté corriendo
docker ps

# Si no está corriendo, inícialo manualmente y luego:
iniciar.bat
```

### No puedo conectar a TopstepX
1. Verifica que el backend esté corriendo (http://localhost:8000/docs)
2. Verifica que las credenciales sean correctas
3. Haz clic en "Probar Conexión" primero
4. Si el test funciona, haz clic en "Conectar"

### PostgreSQL no inicia o muestra errores de autenticación
Si cambiaste las credenciales de PostgreSQL, necesitas eliminar el volumen anterior:
```batch
# Opción 1: Usar detener.bat con eliminación completa
detener.bat
# Selecciona opción [2] para eliminar todo incluidos volúmenes

# Opción 2: Comando manual
docker-compose down -v
docker volume rm trading-app_postgres_data

# Luego inicia de nuevo
iniciar.bat
```

### Gestionar la base de datos PostgreSQL
Para cualquier operación administrativa de PostgreSQL:
```batch
config_db.bat
```
Este script te permite:
- Conectarte a la base de datos
- Ver tablas
- Crear/restaurar backups
- Reiniciar PostgreSQL
- Ver logs

---

**Todos los cambios han sido implementados y probados exitosamente!** 🎉
