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
from pydantic import BaseModel, Field
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
    BacktestRun, User, UserCredential, TopstepAccount
)

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
    contract_id: str
    mode: str = Field(..., pattern="^(bot_only|bot_indicators|indicators_only)$")
    timeframes: List[int] = Field(..., min_items=1)  # [1, 5, 15] minutos
    start_date: str  # ISO format
    end_date: str  # ISO format
    bot_config_id: Optional[int] = None
    indicator_config_id: Optional[int] = None
    model_path: Optional[str] = None

class ContractBotConfigRequest(BaseModel):
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
    system_username: Optional[str] = "default_user"  # Usuario del sistema (opcional)

class AccountSelectionRequest(BaseModel):
    account_id: str

class SaveCredentialsRequest(BaseModel):
    api_key: str
    username: str
    system_username: Optional[str] = "default_user"

# ============================================================================
# STARTUP Y SHUTDOWN
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events"""
    global redis_client, topstep_client, rl_model, rl_env

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

    logger.info("✅ Aplicación iniciada correctamente")

    yield

    # Cleanup
    logger.info("🛑 Cerrando aplicación...")

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
    """Autenticación con TopstepX API y guardado de credenciales"""
    global topstep_client

    db = get_db()
    try:
        logger.info(f"Intentando autenticación para usuario: {auth.username}")

        # Intentar autenticación
        topstep_client = TopstepAPIClient(auth.api_key, auth.username)

        # Obtener cuentas
        accounts = topstep_client.get_accounts()

        if not accounts:
            return {"success": False, "message": "No hay cuentas disponibles"}

        # Guardar/actualizar usuario del sistema
        system_user = db.query(User).filter(User.username == auth.system_username).first()
        if not system_user:
            system_user = User(username=auth.system_username)
            db.add(system_user)
            db.flush()

        # Guardar/actualizar credenciales
        credential = db.query(UserCredential).filter(
            UserCredential.user_id == system_user.id,
            UserCredential.username == auth.username
        ).first()

        if not credential:
            credential = UserCredential(
                user_id=system_user.id,
                api_key=auth.api_key,
                username=auth.username,
                is_active=True
            )
            db.add(credential)
        else:
            credential.api_key = auth.api_key
            credential.is_active = True

        db.flush()

        # Guardar/actualizar cuentas
        saved_accounts = []
        for idx, acc in enumerate(accounts):
            account_id = str(acc['id'])
            account_name = acc.get('name', f"Cuenta {account_id}")

            existing_account = db.query(TopstepAccount).filter(
                TopstepAccount.account_id == account_id
            ).first()

            if not existing_account:
                new_account = TopstepAccount(
                    credential_id=credential.id,
                    account_id=account_id,
                    account_name=account_name,
                    balance=acc.get('balance', 0),
                    can_trade=acc.get('canTrade', True),
                    is_visible=acc.get('isVisible', True),
                    simulated=acc.get('simulated', False),
                    is_selected=(idx == 0),  # Primera cuenta seleccionada por defecto
                    last_sync=datetime.now()
                )
                db.add(new_account)
                saved_accounts.append({
                    "id": account_id,
                    "name": account_name,
                    "balance": acc.get('balance', 0),
                    "can_trade": acc.get('canTrade', True),
                    "is_selected": (idx == 0)
                })
            else:
                existing_account.balance = acc.get('balance', existing_account.balance)
                existing_account.can_trade = acc.get('canTrade', existing_account.can_trade)
                existing_account.last_sync = datetime.now()
                saved_accounts.append({
                    "id": account_id,
                    "name": existing_account.account_name,
                    "balance": existing_account.balance,
                    "can_trade": existing_account.can_trade,
                    "is_selected": existing_account.is_selected
                })

        db.commit()

        # Establecer la primera cuenta como activa
        topstep_client.account_id = str(accounts[0]['id'])

        return {
            "success": True,
            "message": "Autenticación exitosa y credenciales guardadas",
            "credential_id": credential.id,
            "accounts": saved_accounts
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error en autenticación: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    finally:
        db.close()

@app.get("/api/auth/status")
async def auth_status():
    """Verificar estado de autenticación"""
    return {
        "authenticated": topstep_client is not None,
        "account_id": topstep_client.account_id if topstep_client else None
    }

@app.get("/api/auth/credentials")
async def get_saved_credentials(system_username: str = "default_user"):
    """Obtener credenciales guardadas del usuario"""
    db = get_db()
    try:
        system_user = db.query(User).filter(User.username == system_username).first()
        if not system_user:
            return {"success": True, "has_credentials": False, "accounts": []}

        credentials = db.query(UserCredential).filter(
            UserCredential.user_id == system_user.id,
            UserCredential.is_active == True
        ).all()

        if not credentials:
            return {"success": True, "has_credentials": False, "accounts": []}

        all_accounts = []
        for cred in credentials:
            accounts = db.query(TopstepAccount).filter(
                TopstepAccount.credential_id == cred.id
            ).all()

            for acc in accounts:
                all_accounts.append({
                    "id": acc.account_id,
                    "name": acc.account_name,
                    "balance": acc.balance,
                    "can_trade": acc.can_trade,
                    "is_selected": acc.is_selected,
                    "simulated": acc.simulated
                })

        return {
            "success": True,
            "has_credentials": True,
            "accounts": all_accounts
        }

    except Exception as e:
        logger.error(f"Error obteniendo credenciales: {e}")
        return {"success": False, "error": str(e)}
    finally:
        db.close()

@app.post("/api/auth/select-account")
async def select_account(request: AccountSelectionRequest):
    """Seleccionar cuenta activa"""
    global topstep_client

    db = get_db()
    try:
        # Desmarcar todas las cuentas como seleccionadas
        db.query(TopstepAccount).update({"is_selected": False})

        # Marcar la cuenta seleccionada
        selected_account = db.query(TopstepAccount).filter(
            TopstepAccount.account_id == request.account_id
        ).first()

        if not selected_account:
            raise HTTPException(status_code=404, detail="Cuenta no encontrada")

        selected_account.is_selected = True
        db.commit()

        # Actualizar cliente TopstepX
        if topstep_client:
            topstep_client.account_id = request.account_id

        return {
            "success": True,
            "message": "Cuenta seleccionada correctamente",
            "account_id": request.account_id,
            "account_name": selected_account.account_name
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error seleccionando cuenta: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

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

        # Guardar en DB
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
                        active=True
                    )
                    db.add(db_contract)
            db.commit()
        finally:
            db.close()

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
async def download_bars(contract_id: str, days_back: int = 30):
    """Descargar barras históricas desde TopstepX"""
    if not topstep_client:
        raise HTTPException(status_code=503, detail="TopstepX API no disponible")

    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        # Descargar
        bars = topstep_client.get_historical_bars_range(
            contract_id=contract_id,
            start_time=start_date,
            end_time=end_date,
            unit=2,  # Minutos
            unit_number=1
        )

        if not bars:
            raise HTTPException(status_code=404, detail="No se encontraron barras")

        # Calcular indicadores
        smi_result = TechnicalIndicators.calculate_smi(bars)
        macd_result = TechnicalIndicators.calculate_macd(bars)
        bb_result = TechnicalIndicators.calculate_bollinger_bands(bars)
        ma_result = TechnicalIndicators.calculate_moving_averages(bars)
        atr = TechnicalIndicators.calculate_atr(bars)

        # Guardar en DB
        db = get_db()
        try:
            for i, bar in enumerate(bars):
                # Guardar barra
                db_bar = HistoricalBar(
                    time=bar.timestamp,
                    contract_id=contract_id,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=bar.volume
                )
                db.merge(db_bar)

                # Guardar indicadores
                db_indicator = Indicator(
                    time=bar.timestamp,
                    contract_id=contract_id,
                    smi_value=float(smi_result.smi[i]) if i < len(smi_result.smi) else 0.0,
                    smi_signal=float(smi_result.signal[i]) if i < len(smi_result.signal) else 0.0,
                    macd_value=float(macd_result.macd[i]) if i < len(macd_result.macd) else 0.0,
                    macd_signal=float(macd_result.signal[i]) if i < len(macd_result.signal) else 0.0,
                    macd_histogram=float(macd_result.histogram[i]) if i < len(macd_result.histogram) else 0.0,
                    bb_upper=float(bb_result.upper[i]) if i < len(bb_result.upper) else bar.close,
                    bb_middle=float(bb_result.middle[i]) if i < len(bb_result.middle) else bar.close,
                    bb_lower=float(bb_result.lower[i]) if i < len(bb_result.lower) else bar.close,
                    sma_fast=float(ma_result.sma_fast[i]) if i < len(ma_result.sma_fast) else bar.close,
                    sma_slow=float(ma_result.sma_slow[i]) if i < len(ma_result.sma_slow) else bar.close,
                    ema_fast=float(ma_result.ema_fast[i]) if i < len(ma_result.ema_fast) else bar.close,
                    ema_slow=float(ma_result.ema_slow[i]) if i < len(ma_result.ema_slow) else bar.close,
                    atr=float(atr[i]) if i < len(atr) else 0.0
                )
                db.merge(db_indicator)

            db.commit()
        finally:
            db.close()

        return {"success": True, "bars_downloaded": len(bars)}

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
    """Obtener posiciones reales desde TopstepX"""
    if not topstep_client:
        raise HTTPException(status_code=503, detail="TopstepX API no disponible")

    try:
        positions = topstep_client.get_positions()
        return {"positions": positions, "count": len(positions)}

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

        # Crear motor de backtest
        backtest_engine = BacktestEngine(
            db_session=db,
            contract_id=request.contract_id,
            mode=request.mode,
            timeframes=request.timeframes,
            start_date=start_date,
            end_date=end_date,
            bot_config_id=request.bot_config_id,
            indicator_config_id=request.indicator_config_id,
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
                "final_balance": results['final_balance']
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

# ---------- WEBSOCKET ----------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket para actualizaciones en tiempo real"""
    await websocket.accept()
    ws_connections.append(websocket)
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
        logger.info(f"WebSocket desconectado. Total: {len(ws_connections)}")

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
