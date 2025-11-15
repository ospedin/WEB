# 🚀 AI Trading Platform - Multi-Indicator Strategy

Plataforma completa de trading con IA que utiliza **TopstepX API** y múltiples indicadores técnicos (SMI, MACD, Bollinger Bands, Medias Móviles) para generar señales de trading automáticas.

## 📋 Características

### ✅ **Indicadores Técnicos Implementados**
- **SMI** (Stochastic Momentum Index) - Basado en Nuevo_smi.py
- **MACD** (Moving Average Convergence Divergence)
- **Bollinger Bands** (BB)
- **Moving Averages** (MA) - SMA y EMA

### 🎯 **Módulos de la Plataforma**

#### 1. **Dashboard Principal**
- Visualización en tiempo real de posiciones activas
- Estadísticas de trading (Balance, P&L, Win Rate)
- Indicadores técnicos en vivo
- Señales de trading combinadas
- Historial de operaciones

#### 2. **Bot IA**
- Trading automático basado en señales múltiples
- Configuración de parámetros de riesgo
- Selección de indicadores activos
- Control de activación/desactivación en tiempo real

#### 3. **Backtest**
- Prueba de estrategias con datos históricos
- Métricas de rendimiento (Win Rate, Profit Factor, Drawdown)
- Curva de capital
- Historial detallado de operaciones

#### 4. **Configuración**
- Gestión de credenciales TopstepX API
- Parámetros de estrategia (SL, TP, Max Positions)
- Notificaciones y alertas
- Tema claro/oscuro

## 🏗️ Arquitectura

```
trading-app/
├── backend/
│   ├── main.py                  # FastAPI server
│   ├── api/
│   │   ├── topstep.py          # Cliente TopstepX API
│   │   └── indicators.py       # Indicadores técnicos
│   └── requirements.txt
├── frontend/
│   ├── index.html              # UI principal
│   └── app.js                  # Lógica JavaScript
└── README.md
```

## 🔧 Instalación

### Requisitos Previos
- Python 3.11+
- Cuenta en TopstepX con API Key

### 1. Clonar el Repositorio
```bash
git clone <tu-repo>
cd trading-app
```

### 2. Instalar Backend
```bash
cd backend
pip install -r requirements.txt
```

### 3. Iniciar Backend
```bash
python main.py
```

El servidor estará disponible en `http://localhost:8000`

### 4. Iniciar Frontend
```bash
cd ../frontend
# Abrir index.html en un navegador
# O usar un servidor local:
python -m http.server 3000
```

Acceder a `http://localhost:3000`

## 🚀 Uso

### 1. **Autenticación**
Al abrir la aplicación, se mostrará el modal de autenticación:
- Ingresar **API Key** de TopstepX
- Ingresar **Username**
- Click en "Conectar"

### 2. **Cargar Contratos**
En el módulo **Bot**:
- Ingresar símbolos separados por coma (ej: `NQ,ES,CL,HG`)
- Click en "Cargar Contratos"
- Seleccionar contrato para operar

### 3. **Ver Indicadores**
El sistema automáticamente:
- Descarga datos históricos
- Calcula SMI, MACD, BB, MA
- Genera señales de trading
- Muestra todo en el Dashboard

### 4. **Trading Automático**
En el módulo **Bot**:
- Configurar parámetros (SL, TP, Timeframe)
- Seleccionar indicadores activos
- Activar el toggle del Bot
- El sistema operará automáticamente

### 5. **Backtest**
En el módulo **Backtest**:
- Seleccionar fechas de inicio y fin
- Configurar capital inicial
- Click en "Ejecutar Backtest"
- Ver resultados y curva de capital

## 📊 Estrategia de Trading

### **Sistema de Señales Combinadas**

La plataforma genera señales basándose en **consenso de múltiples indicadores**:

#### **Señal LONG**
Se genera cuando la mayoría de indicadores coinciden:
- **SMI**: Cruce alcista sobre señal en zona < -20
- **MACD**: Cruce alcista del histograma
- **BB**: Precio cerca de banda inferior
- **MA**: Golden Cross (SMA rápida cruza sobre lenta)

#### **Señal SHORT**
Se genera cuando la mayoría de indicadores coinciden:
- **SMI**: Cruce bajista bajo señal en zona > 20
- **MACD**: Cruce bajista del histograma
- **BB**: Precio cerca de banda superior
- **MA**: Death Cross (SMA rápida cruza bajo lenta)

### **Gestión de Riesgo**
- **Stop Loss**: Fijo de $150 por operación (configurable)
- **Take Profit**: 2.5x el Stop Loss = $375 (configurable)
- **Max Posiciones**: 8 simultáneas (configurable)
- **Cálculo por Ticks**: Usa `tick_size` y `tick_value` de cada contrato

### **Ejemplo de Operación**
```
Contrato: NQ (Nasdaq E-mini)
Tick Size: 0.25
Tick Value: $5.00
Cantidad: 1 contrato

Entrada: 18,300.00 (LONG)
Stop Loss: 30 ticks = $150
Take Profit: 75 ticks = $375

Si sale en TP: +75 ticks × $5 × 1 = +$375 ✅
Si sale en SL: -30 ticks × $5 × 1 = -$150 ❌
```

## 🔌 API Endpoints

### **Autenticación**
```bash
POST /api/auth/login
Body: {"api_key": "...", "username": "..."}
```

### **Contratos**
```bash
POST /api/contracts/search
Body: {"symbols": ["NQ", "ES", "CL"]}
```

### **Datos Históricos**
```bash
POST /api/historical/download
Body: {
  "contract_id": "...",
  "start_date": "2024-01-01T00:00:00Z",
  "end_date": "2024-01-07T00:00:00Z",
  "timeframe": 1
}
```

### **Indicadores**
```bash
POST /api/indicators/calculate
Body: {"contract_id": "..."}

Response: {
  "smi": {"value": -25.5, "signal": -28.3, "confidence": 0.85},
  "macd": {"macd": 0.0045, "signal": 0.0032, "histogram": 0.0013},
  "bollinger_bands": {"upper": 18350, "middle": 18300, "lower": 18250},
  "moving_averages": {"sma_fast": 18310, "sma_slow": 18295},
  "atr": 45.2
}
```

### **Señales**
```bash
POST /api/signals/generate
Body: {"contract_id": "..."}

Response: {
  "signal": "LONG",
  "confidence": 0.85,
  "reason": "SMI cruce alcista + MACD alcista + Precio en banda inferior",
  "votes": {"long": 3, "short": 0, "neutral": 1}
}
```

### **Posiciones**
```bash
GET /api/positions
POST /api/positions/open
DELETE /api/positions/{position_id}
```

### **Estadísticas**
```bash
GET /api/stats

Response: {
  "total_trades": 45,
  "winning_trades": 31,
  "losing_trades": 14,
  "total_pnl": 3250.50,
  "win_rate": 68.9,
  "avg_win": 175.25,
  "avg_loss": 145.80
}
```

### **WebSocket**
```bash
WS ws://localhost:8000/ws

Recibe actualizaciones en tiempo real cada 5 segundos:
{
  "type": "update",
  "timestamp": "2024-01-15T10:30:00Z",
  "positions": [...],
  "stats": {...}
}
```

## 📝 Configuración Avanzada

### **Parámetros del Backend** (`backend/main.py`)
```python
state.config = {
    'stop_loss_usd': 150.0,
    'take_profit_ratio': 2.5,
    'max_positions': 8,
    'use_smi': True,
    'use_macd': True,
    'use_bb': True,
    'use_ma': True
}
```

### **Parámetros de Indicadores** (`backend/api/indicators.py`)
```python
# SMI
k_length = 8
d_smoothing = 3
signal_period = 3
oversold = -30
overbought = 30

# MACD
fast_period = 12
slow_period = 26
signal_period = 9

# Bollinger Bands
period = 20
std_dev = 2.0

# Moving Averages
sma_fast = 20
sma_slow = 50
ema_fast = 12
ema_slow = 26
```

## 🔄 Comparación con Nuevo_smi.py

| Aspecto | Nuevo_smi.py | Trading App |
|---------|--------------|-------------|
| **Uso** | Backtesting | Trading en Vivo |
| **Indicadores** | SMI Quantum Pro | SMI + MACD + BB + MA |
| **Interfaz** | Terminal | Dashboard Web |
| **API** | TopstepX ✅ | TopstepX ✅ |
| **Cálculos** | Por Tick ✅ | Por Tick ✅ |
| **Actualización** | Histórico | Tiempo Real (WebSocket) |
| **Señales** | SMI solo | Consenso múltiple |

## 🐛 Solución de Problemas

### Backend no inicia
```bash
# Verificar que el puerto 8000 esté libre
lsof -i :8000

# O usar otro puerto
uvicorn main:app --port 8001
```

### Error de autenticación
- Verificar API Key y Username de TopstepX
- Verificar que la cuenta esté activa
- Revisar logs en `backend/` (salida de consola)

### WebSocket no conecta
- Verificar que el backend esté corriendo
- Verificar que no haya firewall bloqueando WebSocket
- Abrir consola del navegador (F12) para ver errores

### No muestra indicadores
- Asegurarse de que se hayan cargado contratos
- Verificar que haya datos históricos descargados
- Revisar logs del backend

## 📚 Referencias

- [TopstepX API Documentation](https://api.topstepx.com/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Technical Indicators Theory](https://www.investopedia.com/technical-analysis-4689657)

## 🤝 Contribuir

Para contribuir al proyecto:
1. Fork el repositorio
2. Crear una rama (`git checkout -b feature/nueva-caracteristica`)
3. Commit cambios (`git commit -am 'Agregar nueva característica'`)
4. Push a la rama (`git push origin feature/nueva-caracteristica`)
5. Crear Pull Request

## 📄 Licencia

MIT License - Ver archivo LICENSE para más detalles

## 👨‍💻 Autor

Desarrollado utilizando:
- Backend: Python + FastAPI
- Frontend: JavaScript Vanilla + TailwindCSS
- API: TopstepX
- Indicadores: Basados en Nuevo_smi.py

---

**⚠️ DISCLAIMER**: Esta plataforma es para fines educativos. El trading de futuros conlleva riesgos significativos. Siempre practique con cuentas demo antes de usar capital real.
