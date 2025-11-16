#!/usr/bin/env python3
"""
Backend principal con FastAPI + RL + PostgreSQL + Redis
"""
import os
import asyncio
from datetime import datetime, timedelta, time as dt_time
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, EmailStr, ConfigDict
import redis.asyncio as redis
from sqlalchemy import create_engine, select, update, delete, and_, desc
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool
import numpy as np

from api.topstep import TopstepAPIClient, ContractInfo
from api.indicators import TechnicalIndicators
from ml.trading_env import TradingEnv
from ml.ppo_model import load_trained_model
from db.models import (
    Base, HistoricalBar, Indicator, TradingSignal, Position, Trade,
    DailyStat, Contract as ContractModel, BotConfig, TradingSchedule,
    RLTrainingEpisode, RLAction, ContractBotConfig, ContractIndicatorConfig,
    BacktestRun, User, Strategy, Account
)
from error_handler import ErrorNotificationMiddleware, WebSocketManager

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://trading_user:trading_pass@localhost:5432/trading_db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
ML_MODEL_PATH = os.getenv("ML_MODEL_PATH", "models/ppo_trading_model.zip")
TOPSTEP_API_KEY = os.getenv("TOPSTEP_API_KEY", "")
TOPSTEP_USERNAME = os.getenv("TOPSTEP_USERNAME", "")

# Motor de base de datos
engine = create_engine(DATABASE_URL, poolclass=NullPool)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Cliente Redis
redis_client: Optional[redis.Redis] = None

# Cliente TopstepX
topstep_client: Optional[TopstepAPIClient] = None

# Modelo RL
rl_model = None
rl_env = None

# Estado del bot
bot_state = {
    "running": False,
    "current_positions": [],
    "last_update": None,
    "daily_pnl": 0.0,
    "daily_trades": 0
}

# WebSocket connections
ws_connections: List[WebSocket] = []

# WebSocket Manager para notificaciones
ws_manager = WebSocketManager()

# Middleware de errores
error_middleware = None

# Tarea de actualización de cuentas
accounts_update_task = None

# ============================================================================
# ACTUALIZACIÓN PERIÓDICA DE CUENTAS
# ============================================================================

async def update_accounts_periodically():
    """Actualizar cuentas activas cada minuto"""
    while True:
        try:
            await asyncio.sleep(60)  # Esperar 1 minuto

            if topstep_client:
                logger.info("🔄 Actualizando cuentas activas...")

                accounts = topstep_client.get_active_accounts()

                # Guardar/actualizar en DB
                db = SessionLocal()
                try:
                    for acc in accounts:
                        existing = db.query(Account).filter(Account.id == str(acc['id'])).first()
                        if existing:
                            existing.name = acc['name']
                            existing.balance = acc['balance']
                            existing.can_trade = acc['canTrade']
                            existing.simulated = acc['simulated']
                            existing.is_active = True
                        else:
                            new_account = Account(
                                id=str(acc['id']),
                                name=acc['name'],
                                balance=acc['balance'],
                                can_trade=acc['canTrade'],
                                simulated=acc['simulated'],
                                is_active=True
                            )
                            db.add(new_account)
                    db.commit()
                    logger.info(f"✅ {len(accounts)} cuentas actualizadas")
                except Exception as e:
                    logger.error(f"Error guardando cuentas: {e}")
                    db.rollback()
                finally:
                    db.close()

        except asyncio.CancelledError:
            logger.info("⚠️ Tarea de actualización de cuentas cancelada")
            break
        except Exception as e:
            logger.error(f"Error en actualización periódica: {e}")

# ============================================================================
# MODELOS PYDANTIC
# ============================================================================

class BotConfigRequest(BaseModel):
    name: str = "Default Config"
    stop_loss_usd: float = 150.0
    take_profit_ratio: float = 2.5
    max_positions: int = 8
    max_daily_loss: float = 600.0
    max_daily_trades: int = 50
    use_smi: bool = True
    use_macd: bool = True
    use_bb: bool = True
    use_ma: bool = True
    timeframe_minutes: int = 1
    min_confidence: float = 0.70
    cooldown_seconds: int = 45

class BotControlRequest(BaseModel):
    action: str = Field(..., pattern="^(start|stop)$")

class TradingScheduleRequest(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6)
    start_time: str = Field(..., pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$")
    end_time: str = Field(..., pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$")

class BacktestRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    contract_id: str
    mode: str = Field(..., pattern="^(bot_only|bot_indicators|indicators_only)$")
    timeframes: List[int] = Field(..., min_items=1)  # [1, 5, 15] minutos
    start_date: str  # ISO format
    end_date: str  # ISO format
    bot_config_id: Optional[int] = None
    indicator_config_id: Optional[int] = None
    model_path: Optional[str] = None
    # Parámetros de riesgo del usuario
    stop_loss_usd: Optional[float] = 150.0
    take_profit_ratio: Optional[float] = 2.0
    # Indicadores seleccionados por el usuario
    use_smi: Optional[bool] = False
    use_macd: Optional[bool] = False
    use_bb: Optional[bool] = False
    use_ma: Optional[bool] = False
    use_stoch_rsi: Optional[bool] = False
    use_vwap: Optional[bool] = False
    use_supertrend: Optional[bool] = False
    use_kdj: Optional[bool] = False
    # Parámetros SMI
    smi_k_length: Optional[int] = 8
    smi_d_smoothing: Optional[int] = 3
    smi_signal_period: Optional[int] = 3
    smi_oversold: Optional[float] = -40.0
    smi_overbought: Optional[float] = 40.0
    # Parámetros MACD
    macd_fast_period: Optional[int] = 12
    macd_slow_period: Optional[int] = 26
    macd_signal_period: Optional[int] = 9
    # Parámetros Bollinger Bands
    bb_period: Optional[int] = 20
    bb_std_dev: Optional[float] = 2.0
    # Parámetros Moving Averages
    ma_sma_fast: Optional[int] = 20
    ma_sma_slow: Optional[int] = 50
    ma_ema_fast: Optional[int] = 12
    ma_ema_slow: Optional[int] = 26
    # Parámetros StochRSI
    stoch_rsi_period: Optional[int] = 14
    stoch_rsi_stoch_period: Optional[int] = 14
    stoch_rsi_k_smooth: Optional[int] = 3
    stoch_rsi_d_smooth: Optional[int] = 3
    stoch_rsi_oversold: Optional[float] = 20.0
    stoch_rsi_overbought: Optional[float] = 80.0
    # Parámetros VWAP
    vwap_std_dev: Optional[float] = 2.0
    # Parámetros SuperTrend
    supertrend_period: Optional[int] = 10
    supertrend_multiplier: Optional[float] = 3.0
    # Parámetros KDJ
    kdj_period: Optional[int] = 9
    kdj_k_smooth: Optional[int] = 3
    kdj_d_smooth: Optional[int] = 3
    # Confianza mínima
    min_confidence: Optional[float] = 0.70

class ContractBotConfigRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    contract_id: str
    name: str = "Default Contract Config"
    stop_loss_usd: float = 150.0
    take_profit_ratio: float = 2.5
    max_positions: int = 3
    max_daily_loss: float = 600.0
    max_daily_trades: int = 50
    timeframe_minutes: int = 5
    min_confidence: float = 0.70
    cooldown_seconds: int = 45
    model_path: Optional[str] = None

class ContractIndicatorConfigRequest(BaseModel):
    contract_id: str
    name: str = "Default Indicator Config"
    use_smi: bool = True
    use_macd: bool = True
    use_bb: bool = True
    use_ma: bool = True
    use_stoch_rsi: bool = False
    use_vwap: bool = False
    use_supertrend: bool = False
    use_kdj: bool = False
    timeframe_minutes: int = 5
    min_confidence: float = 0.70

class PositionResponse(BaseModel):
    id: str
    contract_name: str
    side: str
    quantity: int
    entry_price: float
    stop_loss: float
    take_profit: float
    pnl: Optional[float]
    ticks: Optional[float]
    status: str

class TradeResponse(BaseModel):
    id: str
    contract_name: str
    side: str
    quantity: int
    entry_price: float
    exit_price: float
    pnl: float
    ticks: float
    exit_reason: str
    duration_minutes: Optional[float]
    entry_time: str
    exit_time: str

class SignalResponse(BaseModel):
    time: str
    contract_id: str
    signal: str
    confidence: float
    indicators_used: List[str]
    reason: str

class StatsResponse(BaseModel):
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    gross_profit: float
    gross_loss: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float

class AuthRequest(BaseModel):
    api_key: str
    username: str

class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)

class UserLoginRequest(BaseModel):
    username_or_email: str
    password: str

class VerifyCodeRequest(BaseModel):
    email: EmailStr
    code: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str
    new_password: str = Field(..., min_length=8)

class StrategyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    use_model: bool = False
    model_path: Optional[str] = None
    use_smi: bool = False
    use_macd: bool = False
    use_bb: bool = False
    use_ma: bool = False
    use_stoch_rsi: bool = False
    use_vwap: bool = False
    use_supertrend: bool = False
    use_kdj: bool = False
    use_cci: bool = False
    use_roc: bool = False
    use_atr: bool = False
    use_wr: bool = False
    smi_k_length: Optional[int] = None
    smi_d_smoothing: Optional[int] = None
    smi_signal_period: Optional[int] = None
    macd_fast_period: Optional[int] = None
    macd_slow_period: Optional[int] = None
    macd_signal_period: Optional[int] = None
    bb_period: Optional[int] = None
    bb_std_dev: Optional[float] = None
    ma_sma_fast: Optional[int] = None
    ma_sma_slow: Optional[int] = None
    ma_ema_fast: Optional[int] = None
    ma_ema_slow: Optional[int] = None
    stoch_rsi_period: Optional[int] = None
    stoch_rsi_stoch_period: Optional[int] = None
    stoch_rsi_k_smooth: Optional[int] = None
    stoch_rsi_d_smooth: Optional[int] = None
    vwap_std_dev: Optional[float] = None
    supertrend_period: Optional[int] = None
    supertrend_multiplier: Optional[float] = None
    kdj_period: Optional[int] = None
    kdj_k_smooth: Optional[int] = None
    kdj_d_smooth: Optional[int] = None
    cci_period: Optional[int] = None
    roc_period: Optional[int] = None
    atr_period: Optional[int] = None
    wr_period: Optional[int] = None
    stop_loss_usd: Optional[float] = None
    take_profit_ratio: Optional[float] = None
    timeframe_minutes: Optional[int] = None
    min_confidence: Optional[float] = None

class ContractAddRequest(BaseModel):
    contract_id: str
    strategy_id: Optional[int] = None

# ============================================================================
# STARTUP Y SHUTDOWN
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events"""
    global redis_client, topstep_client, rl_model, rl_env, accounts_update_task

    logger.info("🚀 Iniciando aplicación...")

    # Conectar Redis
    try:
        redis_client = await redis.from_url(REDIS_URL, decode_responses=True)
        await redis_client.ping()
        logger.info("✅ Redis conectado")
    except Exception as e:
        logger.error(f"❌ Error conectando Redis: {e}")

    # Conectar TopstepX API
    if TOPSTEP_API_KEY and TOPSTEP_USERNAME:
        try:
            topstep_client = TopstepAPIClient(TOPSTEP_API_KEY, TOPSTEP_USERNAME)
            logger.info("✅ TopstepX API conectada")
        except Exception as e:
            logger.error(f"❌ Error conectando TopstepX API: {e}")

    # Cargar modelo RL (si existe)
    if os.path.exists(ML_MODEL_PATH):
        try:
            # Crear env dummy para cargar el modelo
            dummy_data = [{'timestamp': datetime.now(), 'open': 100, 'high': 101,
                          'low': 99, 'close': 100, 'volume': 1000, 'smi': 0, 'smi_signal': 0,
                          'macd': 0, 'macd_signal': 0, 'macd_histogram': 0, 'bb_upper': 101,
                          'bb_middle': 100, 'bb_lower': 99, 'bb_bandwidth': 2, 'sma_fast': 100,
                          'sma_slow': 100, 'ema_fast': 100, 'ema_slow': 100, 'atr': 1,
                          'delta_volume': 0, 'cvd': 0, 'dom_imbalance': 0, 'rsi': 50, 'adx': 0}]

            rl_env = TradingEnv(bars_data=dummy_data, tick_size=0.25, tick_value=5.0)
            rl_model = load_trained_model(ML_MODEL_PATH, rl_env)
            logger.info(f"✅ Modelo RL cargado desde {ML_MODEL_PATH}")
        except Exception as e:
            logger.error(f"❌ Error cargando modelo RL: {e}")
    else:
        logger.warning(f"⚠️ No se encontró modelo RL en {ML_MODEL_PATH}")

    # Iniciar actualización periódica de cuentas
    if topstep_client:
        accounts_update_task = asyncio.create_task(update_accounts_periodically())
        logger.info("✅ Tarea de actualización de cuentas iniciada")

    logger.info("✅ Aplicación iniciada correctamente")

    yield

    # Cleanup
    logger.info("🛑 Cerrando aplicación...")

    # Cancelar tarea de actualización de cuentas
    if accounts_update_task:
        accounts_update_task.cancel()
        try:
            await accounts_update_task
        except asyncio.CancelledError:
            pass
        logger.info("✅ Tarea de actualización de cuentas detenida")

    if redis_client:
        await redis_client.close()
        logger.info("✅ Redis cerrado")

    logger.info("✅ Aplicación cerrada")

# ============================================================================
# APLICACIÓN FASTAPI
# ============================================================================

app = FastAPI(
    title="Trading Platform API",
    description="API completa para plataforma de trading con RL",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Error Notification Middleware
error_middleware = ErrorNotificationMiddleware(app, ws_manager=ws_manager)
app.add_middleware(ErrorNotificationMiddleware, ws_manager=ws_manager)

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def get_db() -> Session:
    """Obtener sesión de base de datos (debe cerrarse manualmente en cada función)"""
    return SessionLocal()

async def broadcast_ws(message: Dict[str, Any]):
    """Enviar mensaje a todos los WebSockets conectados"""
    if not ws_connections:
        return

    disconnected = []
    for ws in ws_connections:
        try:
            await ws.send_json(message)
        except:
            disconnected.append(ws)

    # Remover conexiones cerradas
    for ws in disconnected:
        ws_connections.remove(ws)

async def get_latest_bars(contract_id: str, limit: int = 100) -> List[Dict]:
    """Obtener últimas barras con indicadores"""
    db = get_db()

    try:
        # Obtener barras
        bars_query = (
            select(HistoricalBar)
            .where(HistoricalBar.contract_id == contract_id)
            .order_by(desc(HistoricalBar.time))
            .limit(limit)
        )
        bars = db.execute(bars_query).scalars().all()

        if not bars:
            return []

        bars = list(reversed(bars))

        # Obtener indicadores
        indicators_query = (
            select(Indicator)
            .where(Indicator.contract_id == contract_id)
            .order_by(desc(Indicator.time))
            .limit(limit)
        )
        indicators = db.execute(indicators_query).scalars().all()
        indicators_dict = {ind.time: ind for ind in indicators}

        # Combinar
        result = []
        for bar in bars:
            ind = indicators_dict.get(bar.time)
            bar_dict = {
                'timestamp': bar.time,
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume,
                'smi': ind.smi_value if ind else 0.0,
                'smi_signal': ind.smi_signal if ind else 0.0,
                'macd': ind.macd_value if ind else 0.0,
                'macd_signal': ind.macd_signal if ind else 0.0,
                'macd_histogram': ind.macd_histogram if ind else 0.0,
                'bb_upper': ind.bb_upper if ind else bar.close,
                'bb_middle': ind.bb_middle if ind else bar.close,
                'bb_lower': ind.bb_lower if ind else bar.close,
                'bb_bandwidth': ind.bb_upper - ind.bb_lower if ind else 0.0,
                'sma_fast': ind.sma_fast if ind else bar.close,
                'sma_slow': ind.sma_slow if ind else bar.close,
                'ema_fast': ind.ema_fast if ind else bar.close,
                'ema_slow': ind.ema_slow if ind else bar.close,
                'atr': ind.atr if ind else 0.0,
                'delta_volume': 0.0,
                'cvd': 0.0,
                'dom_imbalance': 0.0,
                'rsi': 50.0,
                'adx': 0.0
            }
            result.append(bar_dict)

        return result

    finally:
        db.close()

async def model_predict_action(bars_data: List[Dict], contract: ContractInfo) -> Dict[str, Any]:
    """Usar modelo RL para predecir acción"""
    if not rl_model or not bars_data:
        return None

    try:
        # Crear env temporal con los datos
        temp_env = TradingEnv(
            bars_data=bars_data,
            tick_size=contract.tick_size,
            tick_value=contract.tick_value,
            lookback_window=min(100, len(bars_data))
        )

        # Obtener observación
        obs, _ = temp_env.reset()

        # Predecir
        action, _ = rl_model.predict(obs, deterministic=True)

        # Decodificar acción
        action_dict = temp_env.decode_action(action)

        # Determinar señal
        signal = "FLAT"
        if action_dict['action_type'] == 0:
            signal = "LONG"
        elif action_dict['action_type'] == 1:
            signal = "SHORT"

        # Indicadores usados
        indicators_used = []
        if action_dict.get('use_smi', 0) > 0.5:
            indicators_used.append("SMI")
        if action_dict.get('use_macd', 0) > 0.5:
            indicators_used.append("MACD")
        if action_dict.get('use_bb', 0) > 0.5:
            indicators_used.append("BB")
        if action_dict.get('use_ma', 0) > 0.5:
            indicators_used.append("MA")

        return {
            'signal': signal,
            'position_size': float(action_dict.get('position_size', 1.0)),
            'stop_loss_multiplier': float(action_dict.get('sl_multiplier', 1.0)),
            'take_profit_multiplier': float(action_dict.get('tp_multiplier', 2.5)),
            'indicators_used': indicators_used,
            'confidence': 0.75  # Placeholder
        }

    except Exception as e:
        logger.error(f"Error en predicción del modelo: {e}")
        return None

# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Health check"""
    return {
        "status": "running",
        "service": "Trading Platform API",
        "version": "1.0.0",
        "bot_running": bot_state["running"],
        "model_loaded": rl_model is not None
    }

# ---------- AUTENTICACIÓN ----------

@app.post("/api/auth/login")
async def login(auth: AuthRequest):
    """Autenticación con TopstepX API"""
    global topstep_client

    try:
        logger.info(f"Intentando autenticación para usuario: {auth.username}")

        topstep_client = TopstepAPIClient(auth.api_key, auth.username)

        # Obtener cuentas
        accounts = topstep_client.get_accounts()

        if accounts:
            topstep_client.account_id = str(accounts[0]['id'])

            return {
                "success": True,
                "message": "Autenticación exitosa",
                "account_id": topstep_client.account_id,
                "accounts": accounts
            }

        return {"success": False, "message": "No hay cuentas disponibles"}

    except Exception as e:
        logger.error(f"Error en autenticación: {e}")
        raise HTTPException(status_code=401, detail=str(e))

@app.get("/api/auth/status")
async def auth_status():
    """Verificar estado de autenticación"""
    return {
        "authenticated": topstep_client is not None,
        "account_id": topstep_client.account_id if topstep_client else None
    }

# ---------- CONTRATOS ----------

@app.get("/api/contracts", response_model=List[Dict])
async def get_contracts():
    """Obtener contratos disponibles"""
    db = get_db()
    try:
        contracts = db.query(ContractModel).filter(ContractModel.active == True).all()
        return [
            {
                "id": c.id,
                "name": c.name,
                "symbol_id": c.symbol_id,
                "tick_size": c.tick_size,
                "tick_value": c.tick_value
            }
            for c in contracts
        ]
    finally:
        db.close()

@app.get("/api/contracts/search/{symbol}")
async def search_contracts(symbol: str):
    """Buscar contratos por símbolo en TopstepX"""
    if not topstep_client:
        raise HTTPException(status_code=503, detail="TopstepX API no disponible")

    try:
        contracts = topstep_client.search_contracts(symbol)

        # Guardar en DB (pero NO activar automáticamente)
        db = get_db()
        try:
            for contract in contracts:
                existing = db.query(ContractModel).filter(ContractModel.id == contract.id).first()
                if not existing:
                    db_contract = ContractModel(
                        id=contract.id,
                        name=contract.name,
                        description=f"{contract.description}",
                        symbol_id=contract.symbol_id,
                        tick_size=contract.tick_size,
                        tick_value=contract.tick_value,
                        active=False  # NO activar automáticamente al buscar
                    )
                    db.add(db_contract)
            db.commit()
        finally:
            db.close()

        return [
            {
                "id": c.id,
                "name": c.name,
                "description": c.description,
                "symbol_id": c.symbol_id,
                "tick_size": c.tick_size,
                "tick_value": c.tick_value
            }
            for c in contracts
        ]

    except Exception as e:
        logger.error(f"Error buscando contratos: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ---------- DATOS HISTÓRICOS ----------

@app.get("/api/bars/{contract_id}")
async def get_bars(contract_id: str, limit: int = 100):
    """Obtener barras históricas"""
    bars = await get_latest_bars(contract_id, limit)
    return {"bars": bars, "count": len(bars)}

@app.post("/api/bars/download/{contract_id}")
async def download_bars(contract_id: str, days_back: int = 30, timeframe: int = 1):
    """Descargar barras históricas desde TopstepX"""
    if not topstep_client:
        raise HTTPException(status_code=503, detail="TopstepX API no disponible")

    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        # Determinar unit según el timeframe
        if timeframe >= 1440:  # 1 día o más
            unit = 4  # Días
            unit_number = timeframe // 1440
        elif timeframe >= 60:  # 1 hora o más
            unit = 3  # Horas
            unit_number = timeframe // 60
        else:  # Minutos
            unit = 2  # Minutos
            unit_number = timeframe

        logger.info(f"📥 Descargando barras: {contract_id}, {days_back} días, timeframe={timeframe}min (unit={unit}, unit_number={unit_number})")

        # Descargar
        bars = topstep_client.get_historical_bars_range(
            contract_id=contract_id,
            start_time=start_date,
            end_time=end_date,
            unit=unit,
            unit_number=unit_number
        )

        if not bars or len(bars) == 0:
            # Intentar con más días si no hay datos
            if days_back < 90:
                logger.warning(f"No se encontraron barras con {days_back} días, intentando con 90 días")
                start_date = end_date - timedelta(days=90)
                bars = topstep_client.get_historical_bars_range(
                    contract_id=contract_id,
                    start_time=start_date,
                    end_time=end_date,
                    unit=unit,
                    unit_number=unit_number
                )

            if not bars or len(bars) == 0:
                error_msg = f"No se encontraron datos históricos para {contract_id} en el timeframe de {timeframe} minutos. El contrato podría estar expirado o sin datos disponibles."
                logger.error(error_msg)
                raise HTTPException(status_code=404, detail=error_msg)

        # Calcular indicadores
        smi_result = TechnicalIndicators.calculate_smi(bars)
        macd_result = TechnicalIndicators.calculate_macd(bars)
        bb_result = TechnicalIndicators.calculate_bollinger_bands(bars)
        ma_result = TechnicalIndicators.calculate_moving_averages(bars)
        atr = TechnicalIndicators.calculate_atr(bars)

        # Guardar en DB usando UPSERT (INSERT ... ON CONFLICT DO UPDATE)
        db = get_db()
        try:
            from sqlalchemy.dialects.postgresql import insert

            # Deduplicar barras primero (usar dict para mantener solo el último de cada timestamp)
            bars_dict = {}
            for bar in bars:
                bars_dict[bar.timestamp] = bar

            # Convertir de vuelta a lista ordenada
            unique_bars = [bars_dict[ts] for ts in sorted(bars_dict.keys())]

            if len(unique_bars) < len(bars):
                logger.warning(f"⚠️ Se encontraron {len(bars) - len(unique_bars)} barras duplicadas - deduplicadas")

            # Recalcular indicadores con barras únicas
            smi_result = TechnicalIndicators.calculate_smi(unique_bars)
            macd_result = TechnicalIndicators.calculate_macd(unique_bars)
            bb_result = TechnicalIndicators.calculate_bollinger_bands(unique_bars)
            ma_result = TechnicalIndicators.calculate_moving_averages(unique_bars)
            atr = TechnicalIndicators.calculate_atr(unique_bars)

            # Preparar datos para bulk upsert
            bars_data = []
            indicators_data = []

            for i, bar in enumerate(unique_bars):
                # Datos de barra
                bars_data.append({
                    'time': bar.timestamp,
                    'contract_id': contract_id,
                    'timeframe_minutes': timeframe,
                    'open': float(bar.open),
                    'high': float(bar.high),
                    'low': float(bar.low),
                    'close': float(bar.close),
                    'volume': int(bar.volume)
                })

                # Datos de indicadores
                indicators_data.append({
                    'time': bar.timestamp,
                    'contract_id': contract_id,
                    'timeframe_minutes': timeframe,
                    'smi_value': float(smi_result.smi[i]) if i < len(smi_result.smi) else 0.0,
                    'smi_signal': float(smi_result.signal[i]) if i < len(smi_result.signal) else 0.0,
                    'macd_value': float(macd_result.macd[i]) if i < len(macd_result.macd) else 0.0,
                    'macd_signal': float(macd_result.signal[i]) if i < len(macd_result.signal) else 0.0,
                    'macd_histogram': float(macd_result.histogram[i]) if i < len(macd_result.histogram) else 0.0,
                    'bb_upper': float(bb_result.upper[i]) if i < len(bb_result.upper) else bar.close,
                    'bb_middle': float(bb_result.middle[i]) if i < len(bb_result.middle) else bar.close,
                    'bb_lower': float(bb_result.lower[i]) if i < len(bb_result.lower) else bar.close,
                    'sma_fast': float(ma_result.sma_fast[i]) if i < len(ma_result.sma_fast) else bar.close,
                    'sma_slow': float(ma_result.sma_slow[i]) if i < len(ma_result.sma_slow) else bar.close,
                    'ema_fast': float(ma_result.ema_fast[i]) if i < len(ma_result.ema_fast) else bar.close,
                    'ema_slow': float(ma_result.ema_slow[i]) if i < len(ma_result.ema_slow) else bar.close,
                    'atr': float(atr[i]) if i < len(atr) else 0.0
                })

            # Insertar barras con UPSERT (actualizar si existe)
            if bars_data:
                stmt = insert(HistoricalBar.__table__).values(bars_data)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['time', 'contract_id', 'timeframe_minutes'],
                    set_={
                        'open': stmt.excluded.open,
                        'high': stmt.excluded.high,
                        'low': stmt.excluded.low,
                        'close': stmt.excluded.close,
                        'volume': stmt.excluded.volume
                    }
                )
                db.execute(stmt)

            # Insertar indicadores con UPSERT
            if indicators_data:
                stmt = insert(Indicator.__table__).values(indicators_data)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['time', 'contract_id', 'timeframe_minutes'],
                    set_={
                        'smi_value': stmt.excluded.smi_value,
                        'smi_signal': stmt.excluded.smi_signal,
                        'macd_value': stmt.excluded.macd_value,
                        'macd_signal': stmt.excluded.macd_signal,
                        'macd_histogram': stmt.excluded.macd_histogram,
                        'bb_upper': stmt.excluded.bb_upper,
                        'bb_middle': stmt.excluded.bb_middle,
                        'bb_lower': stmt.excluded.bb_lower,
                        'sma_fast': stmt.excluded.sma_fast,
                        'sma_slow': stmt.excluded.sma_slow,
                        'ema_fast': stmt.excluded.ema_fast,
                        'ema_slow': stmt.excluded.ema_slow,
                        'atr': stmt.excluded.atr
                    }
                )
                db.execute(stmt)

            db.commit()
            logger.info(f"✅ {len(unique_bars)} barras únicas y sus indicadores guardados/actualizados correctamente")
        finally:
            db.close()

        return {"success": True, "bars_downloaded": len(unique_bars)}

    except Exception as e:
        logger.error(f"Error descargando barras: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/contracts/{contract_id}/price")
async def get_current_price(contract_id: str):
    """Obtener precio actual de un contrato desde TopstepX"""
    if not topstep_client:
        raise HTTPException(status_code=503, detail="TopstepX API no disponible")

    try:
        current_price = topstep_client.get_current_price(contract_id)

        if current_price is None:
            raise HTTPException(status_code=404, detail="No se pudo obtener el precio")

        return {
            "contract_id": contract_id,
            "price": current_price,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error obteniendo precio: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/positions/topstepx")
async def get_topstepx_positions():
    """Obtener posiciones reales desde TopstepX con P&L calculado"""
    if not topstep_client:
        # Devolver lista vacía en lugar de error cuando no hay cliente TopstepX
        return {"positions": [], "count": 0}

    try:
        positions_raw = topstep_client.get_positions()

        # Procesar cada posición para calcular P&L
        positions_processed = []
        db = get_db()

        try:
            for pos in positions_raw:
                contract_id = pos.get('contractId') or pos.get('contract_id')
                if not contract_id:
                    continue

                # Obtener información del contrato desde BD
                contract = db.query(ContractModel).filter(ContractModel.id == contract_id).first()
                if not contract:
                    # Si no está en BD, intentar buscarlo
                    continue

                # Obtener precio actual
                current_price = topstep_client.get_current_price(contract_id)
                if not current_price:
                    current_price = pos.get('currentPrice', pos.get('last_price', 0))

                # Extraer datos de la posición
                entry_price = float(pos.get('averagePrice', pos.get('avg_price', pos.get('entry_price', 0))))
                quantity = int(pos.get('quantity', pos.get('size', 1)))
                side = pos.get('side', 'LONG').upper()  # LONG o SHORT

                # Calcular P&L basado en tick_size y tick_value
                if current_price and entry_price:
                    # Calcular diferencia en ticks
                    if side == 'LONG':
                        price_diff = current_price - entry_price
                    else:  # SHORT
                        price_diff = entry_price - current_price

                    # Convertir diferencia de precio a ticks
                    ticks = price_diff / contract.tick_size

                    # Calcular P&L en dólares
                    pnl = ticks * contract.tick_value * quantity
                else:
                    ticks = 0
                    pnl = 0

                positions_processed.append({
                    'id': pos.get('id', pos.get('positionId', '')),
                    'contract_id': contract_id,
                    'contract_name': contract.name,
                    'symbol': pos.get('symbol', contract.symbol_id),
                    'side': side,
                    'quantity': quantity,
                    'entry_price': entry_price,
                    'current_price': current_price,
                    'tick_size': contract.tick_size,
                    'tick_value': contract.tick_value,
                    'ticks': round(ticks, 2),
                    'pnl': round(pnl, 2),
                    'status': 'OPEN'
                })
        finally:
            db.close()

        return {"positions": positions_processed, "count": len(positions_processed)}

    except Exception as e:
        logger.error(f"Error obteniendo posiciones: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ---------- SEÑALES ----------

@app.get("/api/signals", response_model=List[SignalResponse])
async def get_signals(limit: int = 50):
    """Obtener señales recientes"""
    db = get_db()
    try:
        signals = db.query(TradingSignal).order_by(desc(TradingSignal.time)).limit(limit).all()
        return [
            SignalResponse(
                time=s.time.isoformat(),
                contract_id=s.contract_id,
                signal=s.signal,
                confidence=s.confidence,
                indicators_used=s.indicators_used or [],
                reason=s.reason or ""
            )
            for s in signals
        ]
    finally:
        db.close()

@app.post("/api/signals/generate/{contract_id}")
async def generate_signal(contract_id: str):
    """Generar señal usando modelo RL"""
    if not rl_model:
        raise HTTPException(status_code=503, detail="Modelo RL no disponible")

    # Obtener contrato
    db = get_db()
    try:
        db_contract = db.query(ContractModel).filter(ContractModel.id == contract_id).first()
        if not db_contract:
            raise HTTPException(status_code=404, detail="Contrato no encontrado")

        contract = ContractInfo(
            id=db_contract.id,
            name=db_contract.name,
            description=db_contract.description or "",
            symbol_id=db_contract.symbol_id,
            tick_size=db_contract.tick_size,
            tick_value=db_contract.tick_value,
            active=db_contract.active
        )
    finally:
        db.close()

    # Obtener datos
    bars_data = await get_latest_bars(contract_id, limit=100)
    if not bars_data:
        raise HTTPException(status_code=404, detail="No hay datos históricos")

    # Predecir
    prediction = await model_predict_action(bars_data, contract)
    if not prediction:
        raise HTTPException(status_code=500, detail="Error en predicción")

    # Guardar señal
    db = get_db()
    try:
        signal = TradingSignal(
            time=datetime.now(),
            contract_id=contract_id,
            signal=prediction['signal'],
            confidence=prediction['confidence'],
            indicators_used=prediction['indicators_used'],
            reason=f"RL Model prediction using {len(prediction['indicators_used'])} indicators"
        )
        db.add(signal)
        db.commit()
        db.refresh(signal)

        # Broadcast
        await broadcast_ws({
            "type": "signal",
            "data": {
                "contract_id": contract_id,
                "signal": prediction['signal'],
                "confidence": prediction['confidence'],
                "indicators": prediction['indicators_used']
            }
        })

        return SignalResponse(
            time=signal.time.isoformat(),
            contract_id=signal.contract_id,
            signal=signal.signal,
            confidence=signal.confidence,
            indicators_used=signal.indicators_used,
            reason=signal.reason
        )

    finally:
        db.close()

# ---------- POSICIONES ----------

@app.get("/api/positions", response_model=List[PositionResponse])
async def get_positions(status: Optional[str] = None):
    """Obtener posiciones"""
    db = get_db()
    try:
        query = db.query(Position)
        if status:
            query = query.filter(Position.status == status)
        positions = query.order_by(desc(Position.entry_time)).all()

        return [
            PositionResponse(
                id=str(p.id),
                contract_name=p.contract_name,
                side=p.side,
                quantity=p.quantity,
                entry_price=p.entry_price,
                stop_loss=p.stop_loss,
                take_profit=p.take_profit,
                pnl=p.pnl,
                ticks=p.ticks,
                status=p.status
            )
            for p in positions
        ]
    finally:
        db.close()

# ---------- TRADES ----------

@app.get("/api/trades", response_model=List[TradeResponse])
async def get_trades(limit: int = 50):
    """Obtener historial de trades"""
    db = get_db()
    try:
        trades = db.query(Trade).order_by(desc(Trade.exit_time)).limit(limit).all()
        return [
            TradeResponse(
                id=str(t.id),
                contract_name=t.contract_name,
                side=t.side,
                quantity=t.quantity,
                entry_price=t.entry_price,
                exit_price=t.exit_price,
                pnl=t.pnl,
                ticks=t.ticks,
                exit_reason=t.exit_reason,
                duration_minutes=t.duration_minutes,
                entry_time=t.entry_time.isoformat(),
                exit_time=t.exit_time.isoformat()
            )
            for t in trades
        ]
    finally:
        db.close()

# ---------- ESTADÍSTICAS ----------

@app.get("/api/stats/daily", response_model=StatsResponse)
async def get_daily_stats():
    """Obtener estadísticas del día"""
    db = get_db()
    try:
        today = datetime.now().date()
        stats = db.query(DailyStat).filter(DailyStat.date == today).first()

        if not stats:
            return StatsResponse(
                total_trades=0, winning_trades=0, losing_trades=0,
                win_rate=0.0, total_pnl=0.0, gross_profit=0.0,
                gross_loss=0.0, profit_factor=0.0, max_drawdown=0.0,
                sharpe_ratio=0.0
            )

        return StatsResponse(
            total_trades=stats.total_trades,
            winning_trades=stats.winning_trades,
            losing_trades=stats.losing_trades,
            win_rate=stats.win_rate,
            total_pnl=stats.total_pnl,
            gross_profit=stats.gross_profit,
            gross_loss=stats.gross_loss,
            profit_factor=stats.profit_factor,
            max_drawdown=stats.max_drawdown,
            sharpe_ratio=stats.sharpe_ratio
        )
    finally:
        db.close()

# ---------- CONFIGURACIÓN DEL BOT ----------

@app.get("/api/bot/config")
async def get_bot_config():
    """Obtener configuración del bot"""
    db = get_db()
    try:
        config = db.query(BotConfig).order_by(desc(BotConfig.id)).first()
        if not config:
            # Crear config por defecto
            config = BotConfig(name="Default")
            db.add(config)
            db.commit()
            db.refresh(config)

        return {
            "id": config.id,
            "name": config.name,
            "stop_loss_usd": config.stop_loss_usd,
            "take_profit_ratio": config.take_profit_ratio,
            "max_positions": config.max_positions,
            "max_daily_loss": config.max_daily_loss,
            "max_daily_trades": config.max_daily_trades,
            "use_smi": config.use_smi,
            "use_macd": config.use_macd,
            "use_bb": config.use_bb,
            "use_ma": config.use_ma,
            "timeframe_minutes": config.timeframe_minutes,
            "min_confidence": config.min_confidence,
            "cooldown_seconds": config.cooldown_seconds,
            "active": config.active
        }
    finally:
        db.close()

@app.post("/api/bot/config")
async def update_bot_config(config: BotConfigRequest):
    """Actualizar configuración del bot"""
    db = get_db()
    try:
        db_config = db.query(BotConfig).order_by(desc(BotConfig.id)).first()

        if db_config:
            # Actualizar
            db_config.name = config.name
            db_config.stop_loss_usd = config.stop_loss_usd
            db_config.take_profit_ratio = config.take_profit_ratio
            db_config.max_positions = config.max_positions
            db_config.max_daily_loss = config.max_daily_loss
            db_config.max_daily_trades = config.max_daily_trades
            db_config.use_smi = config.use_smi
            db_config.use_macd = config.use_macd
            db_config.use_bb = config.use_bb
            db_config.use_ma = config.use_ma
            db_config.timeframe_minutes = config.timeframe_minutes
            db_config.min_confidence = config.min_confidence
            db_config.cooldown_seconds = config.cooldown_seconds
        else:
            # Crear nuevo
            db_config = BotConfig(**config.dict())
            db.add(db_config)

        db.commit()
        return {"success": True, "message": "Configuración actualizada"}
    finally:
        db.close()

@app.post("/api/bot/control")
async def control_bot(request: BotControlRequest):
    """Iniciar o detener el bot"""
    if request.action == "start":
        if not rl_model:
            raise HTTPException(status_code=503, detail="Modelo RL no disponible")

        bot_state["running"] = True
        bot_state["last_update"] = datetime.now().isoformat()

        # Actualizar config en DB
        db = get_db()
        try:
            config = db.query(BotConfig).order_by(desc(BotConfig.id)).first()
            if config:
                config.active = True
                db.commit()
        finally:
            db.close()

        await broadcast_ws({"type": "bot_status", "data": {"running": True}})
        return {"success": True, "message": "Bot iniciado", "running": True}

    elif request.action == "stop":
        bot_state["running"] = False

        # Actualizar config en DB
        db = get_db()
        try:
            config = db.query(BotConfig).order_by(desc(BotConfig.id)).first()
            if config:
                config.active = False
                db.commit()
        finally:
            db.close()

        await broadcast_ws({"type": "bot_status", "data": {"running": False}})
        return {"success": True, "message": "Bot detenido", "running": False}

@app.get("/api/bot/status")
async def get_bot_status():
    """Obtener estado del bot"""
    return {
        "running": bot_state["running"],
        "last_update": bot_state["last_update"],
        "daily_pnl": bot_state["daily_pnl"],
        "daily_trades": bot_state["daily_trades"],
        "current_positions": len(bot_state["current_positions"]),
        "model_loaded": rl_model is not None
    }

# ---------- HORARIOS ----------

@app.get("/api/schedule")
async def get_trading_schedule():
    """Obtener horarios de trading"""
    db = get_db()
    try:
        schedules = db.query(TradingSchedule).filter(TradingSchedule.active == True).all()
        return [
            {
                "id": s.id,
                "day_of_week": s.day_of_week,
                "start_time": s.start_time.isoformat(),
                "end_time": s.end_time.isoformat()
            }
            for s in schedules
        ]
    finally:
        db.close()

@app.post("/api/schedule")
async def add_trading_schedule(schedule: TradingScheduleRequest):
    """Agregar horario de trading"""
    db = get_db()
    try:
        start_parts = schedule.start_time.split(":")
        end_parts = schedule.end_time.split(":")

        db_schedule = TradingSchedule(
            day_of_week=schedule.day_of_week,
            start_time=dt_time(int(start_parts[0]), int(start_parts[1])),
            end_time=dt_time(int(end_parts[0]), int(end_parts[1])),
            active=True
        )
        db.add(db_schedule)
        db.commit()
        db.refresh(db_schedule)

        return {"success": True, "id": db_schedule.id}
    finally:
        db.close()

@app.delete("/api/schedule/{schedule_id}")
async def delete_trading_schedule(schedule_id: int):
    """Eliminar horario de trading"""
    db = get_db()
    try:
        schedule = db.query(TradingSchedule).filter(TradingSchedule.id == schedule_id).first()
        if not schedule:
            raise HTTPException(status_code=404, detail="Horario no encontrado")

        db.delete(schedule)
        db.commit()
        return {"success": True}
    finally:
        db.close()

# ---------- BACKTEST ----------

@app.post("/api/backtest/run")
async def run_backtest(request: BacktestRequest, background_tasks: BackgroundTasks):
    """Ejecutar backtest con configuración específica"""
    from ml.backtest import BacktestEngine
    from datetime import timezone

    db = get_db()
    try:
        # Validar fechas
        start_date = datetime.fromisoformat(request.start_date.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(request.end_date.replace('Z', '+00:00'))

        # Si no hay indicator_config_id y el modo usa indicadores, crear configuración predeterminada
        indicator_config_id = request.indicator_config_id
        if not indicator_config_id and request.mode in ['indicators_only', 'bot_indicators']:
            # Buscar una configuración existente para este contrato
            existing_config = db.query(ContractIndicatorConfig).filter(
                ContractIndicatorConfig.contract_id == request.contract_id
            ).first()

            if existing_config:
                # Actualizar con los valores e indicadores seleccionados por el usuario
                existing_config.use_smi = request.use_smi
                existing_config.use_macd = request.use_macd
                existing_config.use_bb = request.use_bb
                existing_config.use_ma = request.use_ma
                existing_config.use_stoch_rsi = request.use_stoch_rsi
                existing_config.use_vwap = request.use_vwap
                existing_config.use_supertrend = request.use_supertrend
                existing_config.use_kdj = request.use_kdj
                # Parámetros SMI
                existing_config.smi_k_length = request.smi_k_length
                existing_config.smi_d_smoothing = request.smi_d_smoothing
                existing_config.smi_signal_period = request.smi_signal_period
                existing_config.smi_oversold = request.smi_oversold
                existing_config.smi_overbought = request.smi_overbought
                # Parámetros MACD
                existing_config.macd_fast_period = request.macd_fast_period
                existing_config.macd_slow_period = request.macd_slow_period
                existing_config.macd_signal_period = request.macd_signal_period
                # Parámetros Bollinger Bands
                existing_config.bb_period = request.bb_period
                existing_config.bb_std_dev = request.bb_std_dev
                # Parámetros Moving Averages
                existing_config.ma_sma_fast = request.ma_sma_fast
                existing_config.ma_sma_slow = request.ma_sma_slow
                existing_config.ma_ema_fast = request.ma_ema_fast
                existing_config.ma_ema_slow = request.ma_ema_slow
                # Parámetros StochRSI
                existing_config.stoch_rsi_period = request.stoch_rsi_period
                existing_config.stoch_rsi_stoch_period = request.stoch_rsi_stoch_period
                existing_config.stoch_rsi_k_smooth = request.stoch_rsi_k_smooth
                existing_config.stoch_rsi_d_smooth = request.stoch_rsi_d_smooth
                existing_config.stoch_rsi_oversold = request.stoch_rsi_oversold
                existing_config.stoch_rsi_overbought = request.stoch_rsi_overbought
                # Parámetros VWAP
                existing_config.vwap_std_dev = request.vwap_std_dev
                # Parámetros SuperTrend
                existing_config.supertrend_period = request.supertrend_period
                existing_config.supertrend_multiplier = request.supertrend_multiplier
                # Parámetros KDJ
                existing_config.kdj_period = request.kdj_period
                existing_config.kdj_k_smooth = request.kdj_k_smooth
                existing_config.kdj_d_smooth = request.kdj_d_smooth
                # Configuración general
                existing_config.min_confidence = request.min_confidence
                existing_config.timeframe_minutes = request.timeframes[0]
                db.commit()
                indicator_config_id = existing_config.id
                # Contar indicadores activos
                active_indicators = [
                    name for name, enabled in [
                        ('SMI', request.use_smi), ('MACD', request.use_macd), ('BB', request.use_bb),
                        ('MA', request.use_ma), ('StochRSI', request.use_stoch_rsi), ('VWAP', request.use_vwap),
                        ('SuperTrend', request.use_supertrend), ('KDJ', request.use_kdj)
                    ] if enabled
                ]
                logger.info(f"✅ Config actualizado con indicadores: {', '.join(active_indicators) if active_indicators else 'NINGUNO'}")
            else:
                # Crear configuración con indicadores seleccionados por el usuario
                default_config = ContractIndicatorConfig(
                    contract_id=request.contract_id,
                    name=f"Backtest_{request.contract_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    # Usar indicadores seleccionados por el usuario
                    use_smi=request.use_smi,
                    use_macd=request.use_macd,
                    use_bb=request.use_bb,
                    use_ma=request.use_ma,
                    use_stoch_rsi=request.use_stoch_rsi,
                    use_vwap=request.use_vwap,
                    use_supertrend=request.use_supertrend,
                    use_kdj=request.use_kdj,
                    # Parámetros SMI
                    smi_k_length=request.smi_k_length,
                    smi_d_smoothing=request.smi_d_smoothing,
                    smi_signal_period=request.smi_signal_period,
                    smi_oversold=request.smi_oversold,
                    smi_overbought=request.smi_overbought,
                    # Parámetros MACD
                    macd_fast_period=request.macd_fast_period,
                    macd_slow_period=request.macd_slow_period,
                    macd_signal_period=request.macd_signal_period,
                    # Parámetros Bollinger Bands
                    bb_period=request.bb_period,
                    bb_std_dev=request.bb_std_dev,
                    # Parámetros Moving Averages
                    ma_sma_fast=request.ma_sma_fast,
                    ma_sma_slow=request.ma_sma_slow,
                    ma_ema_fast=request.ma_ema_fast,
                    ma_ema_slow=request.ma_ema_slow,
                    # Parámetros StochRSI
                    stoch_rsi_period=request.stoch_rsi_period,
                    stoch_rsi_stoch_period=request.stoch_rsi_stoch_period,
                    stoch_rsi_k_smooth=request.stoch_rsi_k_smooth,
                    stoch_rsi_d_smooth=request.stoch_rsi_d_smooth,
                    stoch_rsi_oversold=request.stoch_rsi_oversold,
                    stoch_rsi_overbought=request.stoch_rsi_overbought,
                    # Parámetros VWAP
                    vwap_std_dev=request.vwap_std_dev,
                    # Parámetros SuperTrend
                    supertrend_period=request.supertrend_period,
                    supertrend_multiplier=request.supertrend_multiplier,
                    # Parámetros KDJ
                    kdj_period=request.kdj_period,
                    kdj_k_smooth=request.kdj_k_smooth,
                    kdj_d_smooth=request.kdj_d_smooth,
                    # Configuración general
                    timeframe_minutes=request.timeframes[0],
                    min_confidence=request.min_confidence
                )
                db.add(default_config)
                db.commit()
                indicator_config_id = default_config.id
                # Contar indicadores activos
                active_indicators = [
                    name for name, enabled in [
                        ('SMI', request.use_smi), ('MACD', request.use_macd), ('BB', request.use_bb),
                        ('MA', request.use_ma), ('StochRSI', request.use_stoch_rsi), ('VWAP', request.use_vwap),
                        ('SuperTrend', request.use_supertrend), ('KDJ', request.use_kdj)
                    ] if enabled
                ]
                logger.info(f"✅ Configuración creada con indicadores: {', '.join(active_indicators) if active_indicators else 'NINGUNO'}")

        # Crear o actualizar bot_config con parámetros de riesgo del usuario
        bot_config_id = request.bot_config_id
        if not bot_config_id:
            # Buscar configuración existente
            existing_bot_config = db.query(ContractBotConfig).filter(
                ContractBotConfig.contract_id == request.contract_id
            ).first()

            if existing_bot_config:
                # Actualizar con valores del usuario
                existing_bot_config.stop_loss_usd = request.stop_loss_usd
                existing_bot_config.take_profit_ratio = request.take_profit_ratio
                db.commit()
                bot_config_id = existing_bot_config.id
                logger.info(f"✅ Bot config actualizado con SL=${request.stop_loss_usd}, TP ratio={request.take_profit_ratio}")
            else:
                # Crear configuración temporal de bot
                temp_bot_config = ContractBotConfig(
                    contract_id=request.contract_id,
                    name=f"Backtest_{request.contract_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    stop_loss_usd=request.stop_loss_usd,
                    take_profit_ratio=request.take_profit_ratio,
                    max_positions=3,
                    max_daily_loss=600.0,
                    max_daily_trades=50,
                    timeframe_minutes=request.timeframes[0],
                    min_confidence=0.70
                )
                db.add(temp_bot_config)
                db.commit()
                bot_config_id = temp_bot_config.id
                logger.info(f"✅ Bot config temporal creado con SL=${request.stop_loss_usd}, TP ratio={request.take_profit_ratio}")

        # Crear motor de backtest
        backtest_engine = BacktestEngine(
            db_session=db,
            contract_id=request.contract_id,
            mode=request.mode,
            timeframes=request.timeframes,
            start_date=start_date,
            end_date=end_date,
            bot_config_id=bot_config_id,
            indicator_config_id=indicator_config_id,
            model_path=request.model_path or ML_MODEL_PATH
        )

        # Ejecutar backtest
        results = await backtest_engine.run()

        # Guardar en base de datos
        backtest_id = backtest_engine.save_to_database(results)

        return {
            "success": True,
            "backtest_id": backtest_id,
            "results": {
                "total_trades": results['total_trades'],
                "winning_trades": results['winning_trades'],
                "losing_trades": results['losing_trades'],
                "total_pnl": results['total_pnl'],
                "win_rate": results['win_rate'],
                "profit_factor": results['profit_factor'],
                "max_drawdown": results['max_drawdown'],
                "initial_balance": results.get('initial_balance', 100000.0),
                "final_balance": results['final_balance'],
                "trades": results.get('trades', []),
                "equity_curve": results.get('equity_curve', []),
                "chart_data": results.get('chart_data', {'candlesticks': [], 'indicators': {}}),
                "contract_info": results.get('contract_info', {})
            }
        }

    except Exception as e:
        logger.error(f"Error ejecutando backtest: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/api/backtest/history")
async def get_backtest_history(contract_id: Optional[str] = None, limit: int = 20):
    """Obtener historial de backtests"""
    db = get_db()
    try:
        query = db.query(BacktestRun).filter(BacktestRun.completed == True)

        if contract_id:
            query = query.filter(BacktestRun.contract_id == contract_id)

        backtests = query.order_by(desc(BacktestRun.created_at)).limit(limit).all()

        return {
            "backtests": [
                {
                    "id": str(bt.id),
                    "name": bt.name,
                    "contract_id": bt.contract_id,
                    "mode": bt.mode,
                    "timeframes": bt.timeframes,
                    "start_date": bt.start_date.isoformat(),
                    "end_date": bt.end_date.isoformat(),
                    "total_trades": bt.total_trades,
                    "win_rate": bt.win_rate,
                    "total_pnl": bt.total_pnl,
                    "profit_factor": bt.profit_factor,
                    "max_drawdown": bt.max_drawdown,
                    "created_at": bt.created_at.isoformat()
                }
                for bt in backtests
            ]
        }
    finally:
        db.close()

@app.get("/api/backtest/{backtest_id}")
async def get_backtest_details(backtest_id: str):
    """Obtener detalles de un backtest específico"""
    db = get_db()
    try:
        from uuid import UUID
        backtest = db.query(BacktestRun).filter(BacktestRun.id == UUID(backtest_id)).first()

        if not backtest:
            raise HTTPException(status_code=404, detail="Backtest no encontrado")

        return {
            "id": str(backtest.id),
            "name": backtest.name,
            "contract_id": backtest.contract_id,
            "mode": backtest.mode,
            "timeframes": backtest.timeframes,
            "start_date": backtest.start_date.isoformat(),
            "end_date": backtest.end_date.isoformat(),
            "total_trades": backtest.total_trades,
            "winning_trades": backtest.winning_trades,
            "losing_trades": backtest.losing_trades,
            "total_pnl": backtest.total_pnl,
            "win_rate": backtest.win_rate,
            "profit_factor": backtest.profit_factor,
            "max_drawdown": backtest.max_drawdown,
            "bot_config_id": backtest.bot_config_id,
            "indicator_config_id": backtest.indicator_config_id,
            "created_at": backtest.created_at.isoformat(),
            "completed_at": backtest.completed_at.isoformat() if backtest.completed_at else None
        }
    finally:
        db.close()

# ---------- CONTRACT CONFIGURATIONS ----------

@app.post("/api/contract/bot-config")
async def create_contract_bot_config(config: ContractBotConfigRequest):
    """Crear configuración de bot específica por contrato"""
    db = get_db()
    try:
        db_config = ContractBotConfig(
            contract_id=config.contract_id,
            name=config.name,
            stop_loss_usd=config.stop_loss_usd,
            take_profit_ratio=config.take_profit_ratio,
            max_positions=config.max_positions,
            max_daily_loss=config.max_daily_loss,
            max_daily_trades=config.max_daily_trades,
            timeframe_minutes=config.timeframe_minutes,
            min_confidence=config.min_confidence,
            cooldown_seconds=config.cooldown_seconds,
            model_path=config.model_path
        )

        db.add(db_config)
        db.commit()
        db.refresh(db_config)

        return {"success": True, "id": db_config.id}
    finally:
        db.close()

@app.get("/api/contract/{contract_id}/bot-configs")
async def get_contract_bot_configs(contract_id: str):
    """Obtener configuraciones de bot para un contrato"""
    db = get_db()
    try:
        configs = db.query(ContractBotConfig).filter(
            ContractBotConfig.contract_id == contract_id,
            ContractBotConfig.active == True
        ).all()

        return {
            "configs": [
                {
                    "id": c.id,
                    "name": c.name,
                    "stop_loss_usd": c.stop_loss_usd,
                    "take_profit_ratio": c.take_profit_ratio,
                    "max_positions": c.max_positions,
                    "timeframe_minutes": c.timeframe_minutes,
                    "min_confidence": c.min_confidence,
                    "model_path": c.model_path
                }
                for c in configs
            ]
        }
    finally:
        db.close()

@app.post("/api/contract/indicator-config")
async def create_contract_indicator_config(config: ContractIndicatorConfigRequest):
    """Crear configuración de indicadores específica por contrato"""
    db = get_db()
    try:
        db_config = ContractIndicatorConfig(
            contract_id=config.contract_id,
            name=config.name,
            use_smi=config.use_smi,
            use_macd=config.use_macd,
            use_bb=config.use_bb,
            use_ma=config.use_ma,
            use_stoch_rsi=config.use_stoch_rsi,
            use_vwap=config.use_vwap,
            use_supertrend=config.use_supertrend,
            use_kdj=config.use_kdj,
            timeframe_minutes=config.timeframe_minutes,
            min_confidence=config.min_confidence
        )

        db.add(db_config)
        db.commit()
        db.refresh(db_config)

        return {"success": True, "id": db_config.id}
    finally:
        db.close()

@app.get("/api/contract/{contract_id}/indicator-configs")
async def get_contract_indicator_configs(contract_id: str):
    """Obtener configuraciones de indicadores para un contrato"""
    db = get_db()
    try:
        configs = db.query(ContractIndicatorConfig).filter(
            ContractIndicatorConfig.contract_id == contract_id,
            ContractIndicatorConfig.active == True
        ).all()

        return {
            "configs": [
                {
                    "id": c.id,
                    "name": c.name,
                    "use_smi": c.use_smi,
                    "use_macd": c.use_macd,
                    "use_bb": c.use_bb,
                    "use_ma": c.use_ma,
                    "use_stoch_rsi": c.use_stoch_rsi,
                    "use_vwap": c.use_vwap,
                    "use_supertrend": c.use_supertrend,
                    "use_kdj": c.use_kdj,
                    "timeframe_minutes": c.timeframe_minutes,
                    "min_confidence": c.min_confidence
                }
                for c in configs
            ]
        }
    finally:
        db.close()

# ---------- AUTENTICACIÓN DE USUARIOS ----------

@app.post("/api/users/register")
async def register_user(request: UserRegisterRequest):
    """Registrar nuevo usuario"""
    from auth import hash_password, generate_verification_code, send_verification_email

    db = get_db()
    try:
        # Verificar si el usuario ya existe
        existing = db.query(User).filter(
            (User.username == request.username) | (User.email == request.email)
        ).first()

        if existing:
            raise HTTPException(status_code=400, detail="Usuario o email ya existe")

        # Crear usuario
        password_hash = hash_password(request.password)
        verification_code = generate_verification_code()
        expiry = datetime.now() + timedelta(minutes=15)

        user = User(
            username=request.username,
            email=request.email,
            password_hash=password_hash,
            verification_code=verification_code,
            verification_code_expiry=expiry,
            is_verified=False
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        # Enviar email de verificación
        send_verification_email(request.email, verification_code, "verification")

        return {
            "success": True,
            "message": "Usuario registrado. Verifica tu email con el código enviado.",
            "user_id": user.id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registrando usuario: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.post("/api/users/verify")
async def verify_user(request: VerifyCodeRequest):
    """Verificar código de email"""
    db = get_db()
    try:
        user = db.query(User).filter(User.email == request.email).first()

        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        if user.is_verified:
            return {"success": True, "message": "Usuario ya verificado"}

        if not user.verification_code or user.verification_code != request.code:
            raise HTTPException(status_code=400, detail="Código inválido")

        if user.verification_code_expiry < datetime.now():
            raise HTTPException(status_code=400, detail="Código expirado")

        # Verificar usuario
        user.is_verified = True
        user.verification_code = None
        user.verification_code_expiry = None
        db.commit()

        return {"success": True, "message": "Usuario verificado exitosamente"}

    finally:
        db.close()

@app.post("/api/users/login")
async def login_user(request: UserLoginRequest):
    """Login de usuario"""
    from auth import verify_password

    db = get_db()
    try:
        # Buscar usuario por username o email
        user = db.query(User).filter(
            (User.username == request.username_or_email) |
            (User.email == request.username_or_email)
        ).first()

        if not user:
            raise HTTPException(status_code=401, detail="Credenciales inválidas")

        if not verify_password(request.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Credenciales inválidas")

        if not user.is_verified:
            raise HTTPException(status_code=403, detail="Email no verificado")

        if not user.is_active:
            raise HTTPException(status_code=403, detail="Usuario desactivado")

        # Actualizar último login
        user.last_login = datetime.now()
        db.commit()

        # En producción usar JWT tokens
        return {
            "success": True,
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "message": "Login exitoso"
        }

    finally:
        db.close()

@app.post("/api/users/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    """Enviar código de recuperación de contraseña"""
    from auth import generate_verification_code, send_verification_email

    db = get_db()
    try:
        user = db.query(User).filter(User.email == request.email).first()

        if not user:
            # Por seguridad, no revelar si el email existe
            return {"success": True, "message": "Si el email existe, se envió un código de recuperación"}

        # Generar código de recuperación
        reset_code = generate_verification_code()
        expiry = datetime.now() + timedelta(minutes=15)

        user.reset_code = reset_code
        user.reset_code_expiry = expiry
        db.commit()

        # Enviar email
        send_verification_email(request.email, reset_code, "recovery")

        return {"success": True, "message": "Código de recuperación enviado"}

    finally:
        db.close()

@app.post("/api/users/reset-password")
async def reset_password(request: ResetPasswordRequest):
    """Resetear contraseña con código"""
    from auth import hash_password

    db = get_db()
    try:
        user = db.query(User).filter(User.email == request.email).first()

        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        if not user.reset_code or user.reset_code != request.code:
            raise HTTPException(status_code=400, detail="Código inválido")

        if user.reset_code_expiry < datetime.now():
            raise HTTPException(status_code=400, detail="Código expirado")

        # Cambiar contraseña
        user.password_hash = hash_password(request.new_password)
        user.reset_code = None
        user.reset_code_expiry = None
        db.commit()

        return {"success": True, "message": "Contraseña actualizada"}

    finally:
        db.close()

@app.get("/api/users/me")
async def get_current_user(user_id: int):
    """Obtener información del usuario actual"""
    db = get_db()
    try:
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_verified": user.is_verified,
            "created_at": user.created_at.isoformat(),
            "last_login": user.last_login.isoformat() if user.last_login else None
        }

    finally:
        db.close()

# ---------- ESTRATEGIAS ----------

@app.post("/api/strategies")
async def create_strategy(strategy: StrategyCreateRequest, user_id: int):
    """Crear nueva estrategia"""
    db = get_db()
    try:
        db_strategy = Strategy(
            user_id=user_id,
            name=strategy.name,
            description=strategy.description,
            **strategy.dict(exclude={'name', 'description'})
        )

        db.add(db_strategy)
        db.commit()
        db.refresh(db_strategy)

        return {"success": True, "strategy_id": db_strategy.id, "message": "Estrategia creada"}

    finally:
        db.close()

@app.get("/api/strategies")
async def get_strategies(user_id: int):
    """Obtener estrategias del usuario"""
    db = get_db()
    try:
        strategies = db.query(Strategy).filter(
            Strategy.user_id == user_id,
            Strategy.is_active == True
        ).all()

        return {
            "strategies": [
                {
                    "id": s.id,
                    "name": s.name,
                    "description": s.description,
                    "created_at": s.created_at.isoformat(),
                    "updated_at": s.updated_at.isoformat()
                }
                for s in strategies
            ]
        }

    finally:
        db.close()

@app.get("/api/strategies/{strategy_id}")
async def get_strategy(strategy_id: int, user_id: int):
    """Obtener detalles de una estrategia"""
    db = get_db()
    try:
        strategy = db.query(Strategy).filter(
            Strategy.id == strategy_id,
            Strategy.user_id == user_id
        ).first()

        if not strategy:
            raise HTTPException(status_code=404, detail="Estrategia no encontrada")

        # Retornar todos los campos
        return {
            "id": strategy.id,
            "name": strategy.name,
            "description": strategy.description,
            "use_model": strategy.use_model,
            "model_path": strategy.model_path,
            "indicators": {
                "smi": strategy.use_smi,
                "macd": strategy.use_macd,
                "bb": strategy.use_bb,
                "ma": strategy.use_ma,
                "stoch_rsi": strategy.use_stoch_rsi,
                "vwap": strategy.use_vwap,
                "supertrend": strategy.use_supertrend,
                "kdj": strategy.use_kdj,
                "cci": strategy.use_cci,
                "roc": strategy.use_roc,
                "atr": strategy.use_atr,
                "wr": strategy.use_wr
            },
            "parameters": {
                "smi": {
                    "k_length": strategy.smi_k_length,
                    "d_smoothing": strategy.smi_d_smoothing,
                    "signal_period": strategy.smi_signal_period
                },
                "macd": {
                    "fast_period": strategy.macd_fast_period,
                    "slow_period": strategy.macd_slow_period,
                    "signal_period": strategy.macd_signal_period
                },
                "bb": {
                    "period": strategy.bb_period,
                    "std_dev": strategy.bb_std_dev
                },
                "ma": {
                    "sma_fast": strategy.ma_sma_fast,
                    "sma_slow": strategy.ma_sma_slow,
                    "ema_fast": strategy.ma_ema_fast,
                    "ema_slow": strategy.ma_ema_slow
                },
                "stoch_rsi": {
                    "period": strategy.stoch_rsi_period,
                    "stoch_period": strategy.stoch_rsi_stoch_period,
                    "k_smooth": strategy.stoch_rsi_k_smooth,
                    "d_smooth": strategy.stoch_rsi_d_smooth
                },
                "vwap": {"std_dev": strategy.vwap_std_dev},
                "supertrend": {
                    "period": strategy.supertrend_period,
                    "multiplier": strategy.supertrend_multiplier
                },
                "kdj": {
                    "period": strategy.kdj_period,
                    "k_smooth": strategy.kdj_k_smooth,
                    "d_smooth": strategy.kdj_d_smooth
                },
                "cci": {"period": strategy.cci_period},
                "roc": {"period": strategy.roc_period},
                "atr": {"period": strategy.atr_period},
                "wr": {"period": strategy.wr_period}
            },
            "risk_management": {
                "stop_loss_usd": strategy.stop_loss_usd,
                "take_profit_ratio": strategy.take_profit_ratio,
                "timeframe_minutes": strategy.timeframe_minutes,
                "min_confidence": strategy.min_confidence
            }
        }

    finally:
        db.close()

@app.put("/api/strategies/{strategy_id}")
async def update_strategy(strategy_id: int, strategy: StrategyCreateRequest, user_id: int):
    """Actualizar estrategia"""
    db = get_db()
    try:
        db_strategy = db.query(Strategy).filter(
            Strategy.id == strategy_id,
            Strategy.user_id == user_id
        ).first()

        if not db_strategy:
            raise HTTPException(status_code=404, detail="Estrategia no encontrada")

        # Actualizar campos
        for key, value in strategy.dict().items():
            if value is not None:
                setattr(db_strategy, key, value)

        db.commit()

        return {"success": True, "message": "Estrategia actualizada"}

    finally:
        db.close()

@app.delete("/api/strategies/{strategy_id}")
async def delete_strategy(strategy_id: int, user_id: int):
    """Eliminar estrategia (soft delete)"""
    db = get_db()
    try:
        strategy = db.query(Strategy).filter(
            Strategy.id == strategy_id,
            Strategy.user_id == user_id
        ).first()

        if not strategy:
            raise HTTPException(status_code=404, detail="Estrategia no encontrada")

        strategy.is_active = False
        db.commit()

        return {"success": True, "message": "Estrategia eliminada"}

    finally:
        db.close()

# ---------- BALANCE DE CUENTA ----------

@app.get("/api/account/balance")
async def get_account_balance():
    """Obtener balance de cuenta desde TopstepX"""
    if not topstep_client:
        # Devolver balance por defecto cuando no hay cliente TopstepX
        return {
            "balance": 0.0,
            "equity": 0.0,
            "available": 0.0,
            "timestamp": datetime.now().isoformat(),
            "connected": False
        }

    try:
        balance_data = topstep_client.get_account_balance()

        return {
            "balance": balance_data.get("balance", 0.0),
            "equity": balance_data.get("equity", 0.0),
            "available": balance_data.get("available", 0.0),
            "timestamp": datetime.now().isoformat(),
            "connected": True
        }

    except Exception as e:
        logger.error(f"Error obteniendo balance: {e}")
        # Devolver balance por defecto en caso de error
        return {
            "balance": 0.0,
            "equity": 0.0,
            "available": 0.0,
            "timestamp": datetime.now().isoformat(),
            "connected": False,
            "error": str(e)
        }

# ---------- GESTIÓN DE CUENTAS ACTIVAS ----------

@app.get("/api/accounts/active")
async def get_active_accounts():
    """Obtener todas las cuentas ACTIVAS de TopstepX"""
    if not topstep_client:
        return {"accounts": [], "connected": False}

    try:
        accounts = topstep_client.get_active_accounts()

        # Guardar/actualizar cuentas en la base de datos
        db = get_db()
        try:
            for acc in accounts:
                existing = db.query(Account).filter(Account.id == str(acc['id'])).first()
                if existing:
                    existing.name = acc['name']
                    existing.balance = acc['balance']
                    existing.can_trade = acc['canTrade']
                    existing.simulated = acc['simulated']
                    existing.is_active = True
                else:
                    new_account = Account(
                        id=str(acc['id']),
                        name=acc['name'],
                        balance=acc['balance'],
                        can_trade=acc['canTrade'],
                        simulated=acc['simulated'],
                        is_active=True
                    )
                    db.add(new_account)
            db.commit()
        except Exception as db_error:
            logger.error(f"Error guardando cuentas en DB: {db_error}")
            db.rollback()
        finally:
            db.close()

        return {
            "accounts": accounts,
            "connected": True,
            "count": len(accounts)
        }

    except Exception as e:
        logger.error(f"Error obteniendo cuentas activas: {e}")
        return {"accounts": [], "connected": False, "error": str(e)}

@app.post("/api/accounts/switch/{account_id}")
async def switch_account(account_id: str):
    """Cambiar a una cuenta activa diferente"""
    if not topstep_client:
        raise HTTPException(status_code=503, detail="TopstepX no conectado")

    try:
        # Cambiar el account_id en el cliente
        topstep_client.account_id = account_id

        # Obtener balance de la nueva cuenta
        balance_data = topstep_client.get_account_balance()

        logger.info(f"✅ Cambiado a cuenta: {account_id}")

        return {
            "success": True,
            "account_id": account_id,
            "balance": balance_data
        }

    except Exception as e:
        logger.error(f"Error cambiando de cuenta: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ---------- GESTIÓN DE CONTRATOS ----------

@app.delete("/api/contracts/{contract_id}")
async def delete_contract(contract_id: str):
    """Eliminar contrato (soft delete)"""
    db = get_db()
    try:
        contract = db.query(ContractModel).filter(ContractModel.id == contract_id).first()

        if not contract:
            raise HTTPException(status_code=404, detail="Contrato no encontrado")

        contract.active = False
        db.commit()

        return {"success": True, "message": "Contrato eliminado"}

    finally:
        db.close()

@app.post("/api/contracts/{contract_id}/add")
async def add_contract_to_bot(contract_id: str, request: ContractAddRequest):
    """Añadir contrato al bot con estrategia opcional"""
    db = get_db()
    try:
        # Verificar que el contrato existe
        contract = db.query(ContractModel).filter(ContractModel.id == contract_id).first()

        if not contract:
            raise HTTPException(status_code=404, detail="Contrato no encontrado")

        # Activar contrato si estaba desactivado
        contract.active = True

        # Si se proporciona una estrategia, crear configuración del bot
        if request.strategy_id:
            strategy = db.query(Strategy).filter(Strategy.id == request.strategy_id).first()

            if not strategy:
                raise HTTPException(status_code=404, detail="Estrategia no encontrada")

            # Crear o actualizar configuración del bot para este contrato
            bot_config = db.query(ContractBotConfig).filter(
                ContractBotConfig.contract_id == contract_id
            ).first()

            if not bot_config:
                bot_config = ContractBotConfig(
                    contract_id=contract_id,
                    name=f"Config for {contract.name}",
                    stop_loss_usd=strategy.stop_loss_usd,
                    take_profit_ratio=strategy.take_profit_ratio,
                    timeframe_minutes=strategy.timeframe_minutes,
                    min_confidence=strategy.min_confidence
                )
                db.add(bot_config)

        db.commit()

        return {"success": True, "message": "Contrato añadido al bot"}

    finally:
        db.close()

# ---------- WEBSOCKET ----------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket para actualizaciones en tiempo real"""
    await websocket.accept()
    ws_connections.append(websocket)
    ws_manager.add_connection(websocket)
    logger.info(f"WebSocket conectado. Total: {len(ws_connections)}")

    try:
        # Enviar estado inicial
        await websocket.send_json({
            "type": "connection",
            "data": {
                "status": "connected",
                "bot_running": bot_state["running"]
            }
        })

        # Mantener conexión
        while True:
            try:
                data = await websocket.receive_text()
                # Procesar mensajes del cliente si es necesario
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error en WebSocket: {e}")
                break

    finally:
        if websocket in ws_connections:
            ws_connections.remove(websocket)
        ws_manager.remove_connection(websocket)
        logger.info(f"WebSocket desconectado. Total: {len(ws_connections)}")

# ---------- LOGS Y ERRORES ----------

@app.post("/api/logs/error")
async def log_frontend_error(request: dict):
    """Recibir logs de errores desde el frontend"""
    try:
        logger.error(f"[Frontend Error] {request.get('title', 'Unknown')}: {request.get('message', '')}")
        logger.error(f"Details: {request.get('details', {})}")
        return {"success": True}
    except Exception as e:
        logger.error(f"Error procesando log de frontend: {e}")
        return {"success": False}

@app.get("/api/errors/stats")
async def get_error_stats():
    """Obtener estadísticas de errores del servidor"""
    global error_middleware

    if error_middleware and hasattr(error_middleware, 'get_error_stats'):
        stats = error_middleware.get_error_stats()
        return stats

    return {
        "total_errors": 0,
        "by_type": {},
        "by_level": {},
        "recent_errors": []
    }

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
