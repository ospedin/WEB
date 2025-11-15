# 🚀 Trading Platform AI - Guía de Instalación Windows

Sistema completo de trading con **Reinforcement Learning** (PPO) e **Indicadores Técnicos** integrados.

---

## 📋 **REQUISITOS PREVIOS**

Antes de empezar, asegúrate de tener instalado:

### ✅ **Docker Desktop para Windows**
- **Descargar:** https://www.docker.com/products/docker-desktop/
- **Versión mínima:** 4.0 o superior
- **RAM recomendada:** 8GB mínimo (16GB recomendado)
- **Espacio en disco:** 20GB libres

### ✅ **Windows 10/11**
- Versión: 64-bit, Pro, Enterprise o Education
- WSL 2 activado (Docker Desktop lo activa automáticamente)

### ✅ **Permisos de Administrador**
- Necesarios para la instalación inicial

---

## 🎯 **INSTALACIÓN RÁPIDA (3 PASOS)**

### **Paso 1: Descargar el proyecto**
```bash
git clone https://github.com/tu-usuario/trading-platform.git
cd trading-platform/trading-app
```

### **Paso 2: Ejecutar instalación**
Haz **doble click** en:
```
📄 instalar.bat
```
**⚠️ IMPORTANTE:** Ejecutar como **Administrador** (click derecho → Ejecutar como administrador)

Este script hará automáticamente:
- ✓ Verificar Docker Desktop
- ✓ Crear directorios necesarios
- ✓ Generar archivos de configuración
- ✓ Descargar imágenes de Docker
- ✓ Construir servicios
- ✓ Preparar base de datos

**Tiempo estimado:** 10-15 minutos (primera vez)

### **Paso 3: Configurar credenciales**
Edita el archivo `.env` y configura tus credenciales de TopstepX:
```env
TOPSTEP_API_KEY=tu_api_key_real_aqui
TOPSTEP_USERNAME=tu_username_real_aqui
```

---

## ▶️ **INICIAR EL SISTEMA**

Haz doble click en:
```
📄 iniciar.bat
```

Esto iniciará automáticamente **6 servicios**:
1. **PostgreSQL + TimescaleDB** (Base de datos de series temporales)
2. **Redis** (Cache en memoria)
3. **Backend FastAPI** (API + RL + Indicadores)
4. **Frontend Nginx** (Interfaz web)
5. **Grafana** (Dashboards y monitoreo)
6. **Prometheus** (Métricas)

### **URLs de acceso:**
| Servicio | URL | Credenciales |
|----------|-----|--------------|
| 🌐 **Frontend** | http://localhost:3000 | - |
| 🔌 **Backend API** | http://localhost:8000 | - |
| 📚 **API Docs** | http://localhost:8000/docs | - |
| 📊 **Grafana** | http://localhost:3001 | admin / admin |
| 📈 **Prometheus** | http://localhost:9090 | - |

---

## ⏹️ **DETENER EL SISTEMA**

Haz doble click en:
```
📄 detener.bat
```

**Opciones disponibles:**
1. **Detener servicios (conservar datos)** ← Recomendado
   - Detiene todos los contenedores
   - **CONSERVA** toda la información (DB, modelos, logs)

2. **Detener y eliminar todo**
   - Elimina contenedores + volúmenes + datos
   - ⚠️ **PRECAUCIÓN:** Perderás toda la información

---

## 📊 **VER LOGS EN TIEMPO REAL**

Haz doble click en:
```
📄 ver_logs.bat
```

**Opciones:**
- Ver logs de **todos** los servicios
- Ver logs del **Backend** (para debugging)
- Ver logs de **PostgreSQL**
- Ver logs de **Redis**
- Ver logs de **Frontend/Grafana/Prometheus**

**Tip:** Presiona `Ctrl+C` para salir de los logs

---

## 🛠️ **UTILIDADES AVANZADAS**

Haz doble click en:
```
📄 utilidades.bat
```

### **Funciones disponibles:**

#### **1. Ver estado de servicios**
Muestra qué servicios están corriendo y su estado

#### **2. Reiniciar un servicio**
Reinicia un servicio específico sin afectar los demás
```
Ejemplo: reiniciar "backend" después de cambios en código
```

#### **3. Conectar a PostgreSQL**
Abre una terminal SQL interactiva
```sql
-- Ejemplos de consultas:
SELECT * FROM contracts;
SELECT * FROM backtest_runs ORDER BY created_at DESC LIMIT 5;
\dt  -- Listar tablas
\q   -- Salir
```

#### **4. Conectar a Redis**
Abre Redis CLI
```bash
# Ejemplos:
KEYS *
GET some_key
exit
```

#### **5. Ver uso de recursos**
Muestra CPU, RAM y uso de red de cada contenedor

#### **6. Ejecutar backtest de ejemplo**
Lanza un backtest vía API REST

#### **7. Entrenar modelo RL**
Ejecuta el script de entrenamiento del modelo PPO

#### **8. Exportar/Importar base de datos**
Para respaldos o migración de datos

---

## 🏗️ **ARQUITECTURA DEL SISTEMA**

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Puerto 3000)                  │
│                    Nginx + React/HTML/JS                        │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                     BACKEND API (Puerto 8000)                   │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ FastAPI REST │  │  RL (PPO)    │  │  Indicadores Técnicos│ │
│  │   Endpoints  │  │   LSTM       │  │  SMI/MACD/BB/VWAP   │ │
│  └──────────────┘  └──────────────┘  │  StochRSI/SuperTrend│ │
│                                       │  KDJ/MA              │ │
│  ┌──────────────┐  ┌──────────────┐  └──────────────────────┘ │
│  │  Backtest    │  │  TopstepX    │                           │
│  │   Engine     │  │  API Client  │                           │
│  └──────────────┘  └──────────────┘                           │
└────────────┬──────────────────┬──────────────────────────────┘
             │                  │
    ┌────────▼────────┐  ┌──────▼───────┐
    │   PostgreSQL    │  │    Redis     │
    │  + TimescaleDB  │  │    Cache     │
    │  (Puerto 5432)  │  │ (Puerto 6379)│
    └─────────────────┘  └──────────────┘

             ┌──────────────────┐
             │     Grafana      │
             │  (Puerto 3001)   │
             │   + Prometheus   │
             │  (Puerto 9090)   │
             └──────────────────┘
```

---

## 📚 **CARACTERÍSTICAS IMPLEMENTADAS**

### **🤖 Reinforcement Learning (RL)**
- ✅ Modelo PPO (Proximal Policy Optimization) con LSTM
- ✅ Espacio de acción híbrido (discreto + continuo)
- ✅ 45 features de observación
- ✅ Entrenamiento personalizado por contrato
- ✅ Selección dinámica de 1-3 indicadores

### **📈 Indicadores Técnicos (8 Total)**
- ✅ **SMI** - Stochastic Momentum Index
- ✅ **StochRSI** - Stochastic RSI
- ✅ **MACD** - Moving Average Convergence Divergence
- ✅ **Bollinger Bands** - Bandas de volatilidad
- ✅ **VWAP** - Volume Weighted Average Price
- ✅ **MA DOBLE** - Moving Averages (SMA/EMA)
- ✅ **SuperTrend** - Indicador de tendencia basado en ATR
- ✅ **KDJ** - K-D-J Stochastic Oscillator

### **🔬 Sistema de Backtest**
- ✅ Multi-timeframe (1m, 5m, 15m, 1h, 4h, 1d)
- ✅ Tres modos de operación:
  - **Bot only:** Solo modelo RL
  - **Bot + Indicators:** Combinación (señales coincidentes)
  - **Indicators only:** Solo análisis técnico
- ✅ Generación paralela de señales (asyncio)
- ✅ Cálculo de P&L en ticks y USD
- ✅ Estadísticas completas (Win Rate, Profit Factor, Drawdown)

### **⚙️ Configuración por Contrato**
- ✅ Configuración específica de bot por contrato (ES, NQ, CL, etc.)
- ✅ Configuración específica de indicadores por contrato
- ✅ Modelos RL entrenados por contrato
- ✅ Parámetros personalizables (SL, TP, timeframes)

### **💾 Base de Datos**
- ✅ PostgreSQL + TimescaleDB (optimizada para series temporales)
- ✅ Hypertables con compresión automática
- ✅ Políticas de retención (90 días)
- ✅ Índices optimizados para consultas rápidas

### **🔌 API REST Completa**
- ✅ Gestión de contratos
- ✅ Gestión de posiciones y trades
- ✅ Configuraciones de bot e indicadores
- ✅ Ejecución de backtests
- ✅ Entrenamiento de modelos RL
- ✅ WebSocket para actualizaciones en tiempo real

---

## 🧪 **EJECUTAR UN BACKTEST**

### **Opción 1: Desde utilidades.bat**
1. Ejecuta `utilidades.bat`
2. Selecciona opción **[8] Ejecutar backtest de ejemplo**
3. Ingresa ID del contrato (ej: `ESH25`)
4. Selecciona modo (ej: `bot_indicators`)

### **Opción 2: Desde API (curl/Postman)**
```bash
curl -X POST "http://localhost:8000/api/backtest/run" \
     -H "Content-Type: application/json" \
     -d '{
       "contract_id": "ESH25",
       "mode": "bot_indicators",
       "timeframes": [5, 15],
       "start_date": "2025-01-01T00:00:00Z",
       "end_date": "2025-01-31T23:59:59Z",
       "bot_config_id": 1,
       "indicator_config_id": 1
     }'
```

### **Opción 3: Desde Frontend**
1. Accede a http://localhost:3000
2. Ve a la sección **Backtest**
3. Configura parámetros
4. Click en **Ejecutar Backtest**

---

## 🎓 **ENTRENAR UN MODELO RL**

### **Opción 1: Desde utilidades.bat**
1. Ejecuta `utilidades.bat`
2. Selecciona opción **[9] Entrenar modelo RL**

### **Opción 2: Manualmente**
```bash
# Conectar al contenedor backend
docker exec -it trading_backend bash

# Ejecutar entrenamiento
python ml/train_rl.py

# O con parámetros personalizados
python ml/train_rl.py --contract ESH25 --episodes 10000 --timesteps 2000000
```

**El modelo se guardará en:** `backend/models/ppo_trading_model.zip`

---

## 🔧 **SOLUCIÓN DE PROBLEMAS**

### **❌ "Docker no está corriendo"**
1. Abre Docker Desktop manualmente
2. Espera a que el icono se ponga verde
3. Ejecuta `iniciar.bat` nuevamente

### **❌ "Error al construir servicios"**
1. Verifica que tienes espacio suficiente en disco (mínimo 10GB)
2. Ejecuta `detener.bat` → Opción 2 (eliminar todo)
3. Ejecuta `instalar.bat` nuevamente

### **❌ "Puerto 3000/8000 ya está en uso"**
1. Cierra cualquier aplicación que use esos puertos
2. O modifica `docker-compose.yml` para usar otros puertos:
```yaml
ports:
  - "3001:80"  # Frontend ahora en 3001
  - "8001:8000"  # Backend ahora en 8001
```

### **❌ "Backend no inicia / Error en logs"**
1. Ejecuta `ver_logs.bat` → Opción 2 (Backend)
2. Verifica que el archivo `.env` tenga las credenciales correctas
3. Verifica que PostgreSQL esté corriendo:
```bash
docker-compose ps
```

### **❌ "No hay datos para backtest"**
1. Primero debes descargar datos históricos desde TopstepX
2. O usa el script de carga de datos de ejemplo:
```bash
docker exec -it trading_backend python scripts/load_sample_data.py
```

---

## 📞 **SOPORTE Y RECURSOS**

### **Logs del Sistema**
```bash
# Ver todos los logs
docker-compose logs

# Ver solo errores
docker-compose logs | findstr ERROR

# Ver logs de un servicio específico
docker-compose logs backend
```

### **Comandos útiles de Docker**
```bash
# Estado de contenedores
docker-compose ps

# Uso de recursos
docker stats

# Reiniciar un servicio
docker-compose restart backend

# Reconstruir un servicio
docker-compose up -d --build backend
```

### **Base de Datos**
```bash
# Conectar a PostgreSQL
docker exec -it trading_postgres psql -U trading_user -d trading_db

# Backup de base de datos
docker exec trading_postgres pg_dump -U trading_user trading_db > backup.sql

# Restaurar backup
cat backup.sql | docker exec -i trading_postgres psql -U trading_user -d trading_db
```

---

## 🚀 **PRÓXIMOS PASOS**

1. ✅ **Configura tus credenciales** en `.env`
2. ✅ **Inicia el sistema** con `iniciar.bat`
3. ✅ **Descarga datos históricos** desde TopstepX
4. ✅ **Crea configuraciones** específicas por contrato
5. ✅ **Entrena modelos RL** para cada contrato
6. ✅ **Ejecuta backtests** con diferentes configuraciones
7. ✅ **Optimiza parámetros** basándote en resultados
8. ✅ **Despliega en producción** cuando estés listo

---

## 📄 **ESTRUCTURA DE ARCHIVOS**

```
trading-app/
│
├── 📄 instalar.bat          ← INSTALACIÓN INICIAL
├── 📄 iniciar.bat           ← INICIAR SERVICIOS
├── 📄 detener.bat           ← DETENER SERVICIOS
├── 📄 ver_logs.bat          ← VER LOGS
├── 📄 utilidades.bat        ← HERRAMIENTAS ADICIONALES
├── 📄 README_WINDOWS.md     ← ESTA GUÍA
│
├── 📄 docker-compose.yml    ← Configuración de servicios
├── 📄 .env                  ← Variables de entorno (EDITAR!)
├── 📄 nginx.conf            ← Configuración Nginx
├── 📄 prometheus.yml        ← Configuración Prometheus
│
├── backend/
│   ├── main.py              ← API principal
│   ├── requirements.txt     ← Dependencias Python
│   ├── Dockerfile           ← Imagen Docker backend
│   │
│   ├── api/
│   │   ├── topstep.py       ← Cliente TopstepX API
│   │   └── indicators.py    ← 8 Indicadores técnicos
│   │
│   ├── ml/
│   │   ├── trading_env.py   ← Environment Gymnasium
│   │   ├── ppo_model.py     ← Modelo PPO
│   │   ├── backtest.py      ← Motor de backtest
│   │   └── train_rl.py      ← Script de entrenamiento
│   │
│   ├── db/
│   │   ├── models.py        ← Modelos SQLAlchemy
│   │   └── init.sql         ← Schema de base de datos
│   │
│   └── models/              ← Modelos entrenados
│
├── frontend/                ← Archivos HTML/CSS/JS
│
└── grafana/
    └── dashboards/          ← Dashboards de Grafana
```

---

## 📊 **ENDPOINTS DE LA API**

### **Contratos**
- `GET /api/contracts` - Listar contratos
- `POST /api/contracts` - Crear contrato
- `GET /api/contracts/{id}` - Detalles de contrato

### **Posiciones y Trades**
- `GET /api/positions` - Posiciones abiertas
- `GET /api/trades` - Historial de trades
- `GET /api/stats/daily` - Estadísticas diarias

### **Backtest**
- `POST /api/backtest/run` - Ejecutar backtest
- `GET /api/backtest/history` - Historial de backtests
- `GET /api/backtest/{id}` - Detalles de backtest

### **Configuraciones**
- `POST /api/contract/bot-config` - Config de bot por contrato
- `GET /api/contract/{id}/bot-configs` - Listar configs de bot
- `POST /api/contract/indicator-config` - Config de indicadores
- `GET /api/contract/{id}/indicator-configs` - Listar configs

### **Bot Control**
- `GET /api/bot/status` - Estado del bot
- `POST /api/bot/control` - Iniciar/Detener bot
- `GET /api/bot/config` - Configuración actual

**Documentación completa:** http://localhost:8000/docs

---

## ⚡ **TIPS Y MEJORES PRÁCTICAS**

### **Rendimiento**
- Asigna al menos **4GB de RAM** a Docker Desktop
- Usa **SSD** para mejores tiempos de I/O
- Limpia imágenes no usadas: `docker system prune -a`

### **Seguridad**
- **NUNCA** commits el archivo `.env` con credenciales reales
- Cambia las contraseñas de Grafana por defecto
- Usa HTTPS en producción

### **Desarrollo**
- El backend se recarga automáticamente al cambiar código
- Los logs son tu mejor amigo: `ver_logs.bat`
- Usa el endpoint `/docs` para probar la API

### **Backtesting**
- Empieza con períodos cortos (1 semana)
- Compara los 3 modos de operación
- Optimiza parámetros iterativamente
- Valida con datos out-of-sample

### **Producción**
- Entrena modelos con datos de al menos 3 meses
- Usa configuraciones específicas por contrato
- Monitorea constantemente con Grafana
- Implementa stop loss global

---

## 📝 **CHANGELOG**

### v2.0 (2025-01-14)
- ✅ Sistema de backtest multi-timeframe
- ✅ 4 nuevos indicadores (StochRSI, VWAP, SuperTrend, KDJ)
- ✅ Configuraciones por contrato
- ✅ Generación paralela de señales
- ✅ Scripts .bat para Windows

### v1.0 (2025-01-10)
- ✅ Versión inicial
- ✅ RL con PPO
- ✅ 4 indicadores básicos (SMI, MACD, BB, MA)
- ✅ Integración TopstepX

---

**¡Listo para comenzar! 🚀**

Ejecuta `instalar.bat` y empieza tu journey en trading algorítmico con IA.
