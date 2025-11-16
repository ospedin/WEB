# SOLUCIÓN A ERRORES DE CONEXIÓN "Failed to fetch"

## 🔴 PROBLEMA
Cuando abres la aplicación en el navegador ves errores como:
```
❌ Error de Red
Failed to fetch
http://localhost:8000/api/users/register
```

## ✅ SOLUCIÓN GARANTIZADA (Sigue estos pasos EN ORDEN)

### PASO 1: Detener TODO
```batch
cd trading-app
detener.bat
```

### PASO 2: Limpiar contenedores y volúmenes
```batch
docker-compose down -v
```

### PASO 3: Reconstruir TODO desde cero
```batch
docker-compose build --no-cache
```

### PASO 4: Iniciar servicios
```batch
iniciar.bat
```

El script `iniciar.bat` ahora tiene verificaciones automáticas que:
- ✅ Esperan a que PostgreSQL esté listo
- ✅ Esperan a que Redis esté listo
- ✅ Esperan a que el Backend responda (hasta 90 segundos)
- ✅ Verifican que el Frontend esté accesible

**NO abras el navegador hasta que veas:**
```
================================================================================
   TODOS LOS SERVICIOS ESTAN FUNCIONANDO CORRECTAMENTE
================================================================================
```

### PASO 5: Verificar que funciona
Abre el navegador en: http://localhost:3000

Si aún hay problemas, ejecuta:
```batch
diagnostico.bat
```

## 🔍 DIAGNÓSTICO MANUAL

### Verificar que el Backend está corriendo:
```batch
curl http://localhost:8000/
```

Deberías ver:
```json
{"status":"running","service":"Trading Platform API","version":"1.0.0",...}
```

### Ver logs del backend:
```batch
docker-compose logs backend
```

### Ver estado de todos los contenedores:
```batch
docker-compose ps
```

Todos deben estar "Up" y "healthy"

## ⚠️ PROBLEMAS COMUNES Y SOLUCIONES

### 1. "Backend NO responde" después de 90 segundos
**Causa:** Faltan dependencias en Python o error en el código

**Solución:**
```batch
docker-compose logs backend
```
Busca errores tipo:
- `ModuleNotFoundError`
- `ImportError`
- `SyntaxError`

Si falta un módulo, añádelo a `backend/requirements.txt` y reconstruye:
```batch
docker-compose build backend
```

### 2. "PostgreSQL no inicio correctamente"
**Causa:** El puerto 5432 está ocupado o hay problemas con el volumen

**Solución:**
```batch
docker-compose down -v
docker-compose up -d postgres
docker-compose logs postgres
```

### 3. "Puerto 8000 ya está en uso"
**Causa:** Otro servicio está usando el puerto 8000

**Solución:**
```batch
# Ver qué está usando el puerto
netstat -ano | findstr ":8000"

# Matar el proceso (reemplaza PID con el número que veas)
taskkill /PID <numero> /F

# O cambia el puerto en docker-compose.yml:
# ports:
#   - "8001:8000"  # Usa 8001 en lugar de 8000
```

### 4. El frontend carga pero no conecta al backend
**Causa:** El frontend está buscando el backend en la URL incorrecta

**Solución:**
Verifica en `frontend/app.js` la línea:
```javascript
const API_BASE_URL = 'http://localhost:8000';
```

Debe ser exactamente eso. Si cambiaste el puerto, actualízalo.

## 🚀 REINICIO COMPLETO (Última Opción)

Si NADA funciona, borra TODO y empieza de cero:

```batch
cd trading-app

# Detener y eliminar TODO
docker-compose down -v
docker system prune -a --volumes

# Reconstruir
docker-compose build --no-cache

# Iniciar
iniciar.bat
```

## 📝 NOTAS IMPORTANTES

1. **SIEMPRE** espera a que `iniciar.bat` termine TODAS las verificaciones
2. **NO** abras el navegador manualmente hasta que el script lo haga
3. Si cambias código Python, ejecuta: `docker-compose restart backend`
4. Si cambias HTML/JS, solo refresca el navegador (Ctrl+F5)
5. Si cambias docker-compose.yml, ejecuta: `docker-compose down && docker-compose up -d`

## ✅ VERIFICACIÓN RÁPIDA

Ejecuta estos comandos y TODOS deben funcionar:

```batch
curl http://localhost:8000/
curl http://localhost:3000/
docker-compose ps
```

Si alguno falla, hay un problema que debes resolver ANTES de continuar.
