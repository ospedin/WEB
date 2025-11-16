# 🚀 Instrucciones para Usuario Ospedin

## ✅ Usuario Pre-configurado

Se ha creado automáticamente un usuario con las siguientes credenciales:

```
Username: ospedin
Email:    sguedia660smr@gmail.com
Password: prueba19
```

**El usuario está PRE-VERIFICADO** y listo para usar. No necesitas validar el email para iniciar sesión.

---

## 📧 Configuración de Emails (Opcional)

Si deseas habilitar el envío real de emails de verificación para nuevos usuarios:

### Paso 1: Configurar Gmail

1. Ve a tu cuenta de Gmail: https://myaccount.google.com/security
2. **Activa la verificación en 2 pasos** (si no está activada)
3. Ve a **"Contraseñas de aplicaciones"**
4. Genera una nueva contraseña para **"Correo"** o **"Otra aplicación"**
5. **Copia esa contraseña** (16 caracteres sin espacios)

### Paso 2: Editar archivo .env

Abre el archivo `.env` en la raíz del proyecto y configura:

```env
SMTP_USER=tu_email@gmail.com
SMTP_PASSWORD=tu_contraseña_de_aplicacion_de_16_caracteres
```

### Paso 3: Reiniciar servicios

Ejecuta:
```cmd
detener.bat
iniciar.bat
```

---

## 🎯 Cómo Iniciar Sesión

### Opción 1: Inicio de Sesión Directo

1. Ejecuta `iniciar.bat`
2. Espera a que todos los servicios inicien
3. Se abrirá automáticamente http://localhost:3000
4. Haz clic en la pestaña **"Login"**
5. Ingresa:
   - **Username o Email**: `ospedin` o `sguedia660smr@gmail.com`
   - **Password**: `prueba19`
6. Haz clic en **"Iniciar Sesión"**
7. ✅ ¡Listo! Ya estás dentro de la aplicación

---

## 🔄 Flujo de Validación de Email (Para nuevos usuarios)

Si creas un nuevo usuario a través del formulario de registro, el flujo es:

1. El usuario se registra con username, email y password
2. Se envía un código de verificación de 6 dígitos al email
   - **Si SMTP está configurado**: El código se envía por email
   - **Si SMTP NO está configurado**: El código aparece en los logs del servidor
3. El usuario ingresa el código de verificación
4. Tras validar el código, el usuario puede iniciar sesión normalmente

### Ver códigos en logs (si no tienes SMTP configurado)

Para ver los códigos de verificación en los logs:

```cmd
docker-compose logs -f backend
```

Busca líneas como:
```
[EMAIL] Enviando a: email@ejemplo.com, Asunto: ✅ Código de Verificación - AI Trading App, Código: 123456
```

---

## 🛠️ Comandos Útiles

### Iniciar todos los servicios
```cmd
iniciar.bat
```

### Detener todos los servicios
```cmd
detener.bat
```

### Ver logs en tiempo real
```cmd
docker-compose logs -f
```

### Ver logs solo del backend
```cmd
docker-compose logs -f backend
```

### Crear/Verificar usuario ospedin manualmente
```cmd
crear_usuario.bat
```

---

## 🌐 Servicios Disponibles

Una vez iniciado el sistema, tendrás acceso a:

| Servicio | URL | Descripción |
|----------|-----|-------------|
| **Frontend** | http://localhost:3000 | Interfaz web de trading |
| **Backend API** | http://localhost:8000/docs | Documentación interactiva de la API |
| **Grafana** | http://localhost:3001 | Dashboards de monitoreo (admin/admin) |
| **Prometheus** | http://localhost:9090 | Sistema de métricas |

---

## ❓ Preguntas Frecuentes

### ¿Por qué no recibo emails de verificación?

- **Verifica** que hayas configurado `SMTP_USER` y `SMTP_PASSWORD` en el archivo `.env`
- **Asegúrate** de usar una contraseña de aplicación de Gmail, no tu contraseña normal
- **Revisa** los logs del backend: `docker-compose logs -f backend`
- Si ves mensajes como "Email no enviado. Código: XXXXXX", copia ese código manualmente

### ¿Cómo reseteo el usuario ospedin?

Ejecuta:
```cmd
crear_usuario.bat
```

Este script actualizará o recreará el usuario con las credenciales correctas.

### ¿Puedo cambiar la contraseña del usuario ospedin?

Sí, puedes cambiarla desde el panel de configuración una vez iniciada la sesión, o editando el archivo `backend/create_user.py` y ejecutando `crear_usuario.bat`.

---

## ✅ Checklist de Inicio

- [ ] Ejecutar `iniciar.bat`
- [ ] Esperar a que todos los servicios estén listos (se abrirá el navegador automáticamente)
- [ ] Iniciar sesión con `ospedin` / `prueba19`
- [ ] Explorar la interfaz de trading
- [ ] (Opcional) Configurar SMTP si deseas enviar emails reales

---

## 🎉 ¡Todo Listo!

El sistema está completamente configurado y listo para usar. El usuario **ospedin** está pre-verificado y puede iniciar sesión inmediatamente sin necesidad de validar el email.

**¡Disfruta del trading con IA! 🚀📈**
