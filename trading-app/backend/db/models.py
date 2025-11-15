# Modelos SQLAlchemy para base de datos
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Date, Time, ARRAY, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

Base = declarative_base()

class User(Base):
    """Usuario del sistema"""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    credentials = relationship("UserCredential", back_populates="user", cascade="all, delete-orphan")

class UserCredential(Base):
    """Credenciales de TopstepX de un usuario"""
    __tablename__ = 'user_credentials'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    api_key = Column(Text, nullable=False)
    username = Column(String(100), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="credentials")
    accounts = relationship("TopstepAccount", back_populates="credential", cascade="all, delete-orphan")

class TopstepAccount(Base):
    """Cuenta de TopstepX asociada a credenciales"""
    __tablename__ = 'topstep_accounts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    credential_id = Column(Integer, ForeignKey('user_credentials.id', ondelete='CASCADE'), nullable=False, index=True)
    account_id = Column(String(50), nullable=False, unique=True, index=True)
    account_name = Column(String(200), nullable=False)
    balance = Column(Float, default=0)
    can_trade = Column(Boolean, default=True)
    is_visible = Column(Boolean, default=True)
    simulated = Column(Boolean, default=False)
    is_selected = Column(Boolean, default=False, index=True)
    last_sync = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    credential = relationship("UserCredential", back_populates="accounts")

class HistoricalBar(Base):
    __tablename__ = 'historical_bars'

    time = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    contract_id = Column(String(50), primary_key=True, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)

class Indicator(Base):
    __tablename__ = 'indicators'

    time = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    contract_id = Column(String(50), primary_key=True, nullable=False)

    # Indicadores básicos
    smi_value = Column(Float)
    smi_signal = Column(Float)
    macd_value = Column(Float)
    macd_signal = Column(Float)
    macd_histogram = Column(Float)
    bb_upper = Column(Float)
    bb_middle = Column(Float)
    bb_lower = Column(Float)
    sma_fast = Column(Float)
    sma_slow = Column(Float)
    ema_fast = Column(Float)
    ema_slow = Column(Float)
    atr = Column(Float)

    # Nuevos indicadores
    stoch_rsi_value = Column(Float)
    stoch_rsi_k = Column(Float)
    stoch_rsi_d = Column(Float)
    vwap_value = Column(Float)
    vwap_upper = Column(Float)
    vwap_lower = Column(Float)
    supertrend_value = Column(Float)
    supertrend_direction = Column(Float)  # 1 = alcista, -1 = bajista
    kdj_k = Column(Float)
    kdj_d = Column(Float)
    kdj_j = Column(Float)
    rsi = Column(Float)

class TradingSignal(Base):
    __tablename__ = 'trading_signals'

    id = Column(Integer, primary_key=True, autoincrement=True)
    time = Column(DateTime(timezone=True), nullable=False, index=True)
    contract_id = Column(String(50), nullable=False, index=True)
    signal = Column(String(10), nullable=False)  # LONG, SHORT, FLAT
    confidence = Column(Float, nullable=False)
    indicators_used = Column(ARRAY(Text))
    reason = Column(Text)

class Position(Base):
    __tablename__ = 'positions'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contract_id = Column(String(50), nullable=False, index=True)
    contract_name = Column(String(100), nullable=False)
    side = Column(String(10), nullable=False)
    quantity = Column(Integer, nullable=False)
    entry_price = Column(Float, nullable=False)
    entry_time = Column(DateTime(timezone=True), nullable=False, index=True)
    stop_loss = Column(Float, nullable=False)
    take_profit = Column(Float, nullable=False)
    exit_price = Column(Float)
    exit_time = Column(DateTime(timezone=True))
    exit_reason = Column(String(50))
    pnl = Column(Float)
    ticks = Column(Float)
    tick_size = Column(Float, nullable=False)
    tick_value = Column(Float, nullable=False)
    status = Column(String(20), nullable=False, default='OPEN', index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Trade(Base):
    __tablename__ = 'trades'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    position_id = Column(UUID(as_uuid=True), ForeignKey('positions.id'))
    contract_id = Column(String(50), nullable=False, index=True)
    contract_name = Column(String(100), nullable=False)
    side = Column(String(10), nullable=False)
    quantity = Column(Integer, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=False)
    entry_time = Column(DateTime(timezone=True), nullable=False, index=True)
    exit_time = Column(DateTime(timezone=True), nullable=False)
    pnl = Column(Float, nullable=False, index=True)
    ticks = Column(Float, nullable=False)
    exit_reason = Column(String(50), nullable=False)
    duration_minutes = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class DailyStat(Base):
    __tablename__ = 'daily_stats'

    date = Column(Date, primary_key=True)
    total_trades = Column(Integer, nullable=False, default=0)
    winning_trades = Column(Integer, nullable=False, default=0)
    losing_trades = Column(Integer, nullable=False, default=0)
    total_pnl = Column(Float, nullable=False, default=0)
    gross_profit = Column(Float, nullable=False, default=0)
    gross_loss = Column(Float, nullable=False, default=0)
    win_rate = Column(Float, nullable=False, default=0)
    profit_factor = Column(Float, nullable=False, default=0)
    max_drawdown = Column(Float, nullable=False, default=0)
    sharpe_ratio = Column(Float, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Contract(Base):
    __tablename__ = 'contracts'

    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    symbol_id = Column(String(50), nullable=False, index=True)
    tick_size = Column(Float, nullable=False)
    tick_value = Column(Float, nullable=False)
    active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class BotConfig(Base):
    __tablename__ = 'bot_config'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    stop_loss_usd = Column(Float, nullable=False, default=150)
    take_profit_ratio = Column(Float, nullable=False, default=2.5)
    max_positions = Column(Integer, nullable=False, default=8)
    max_daily_loss = Column(Float, nullable=False, default=600)
    max_daily_trades = Column(Integer, nullable=False, default=50)
    use_smi = Column(Boolean, nullable=False, default=True)
    use_macd = Column(Boolean, nullable=False, default=True)
    use_bb = Column(Boolean, nullable=False, default=True)
    use_ma = Column(Boolean, nullable=False, default=True)
    timeframe_minutes = Column(Integer, nullable=False, default=1)
    min_confidence = Column(Float, nullable=False, default=0.70)
    cooldown_seconds = Column(Integer, nullable=False, default=45)
    active = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class TradingSchedule(Base):
    __tablename__ = 'trading_schedule'

    id = Column(Integer, primary_key=True, autoincrement=True)
    day_of_week = Column(Integer, nullable=False)  # 0=Lunes, 6=Domingo
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class RLTrainingEpisode(Base):
    __tablename__ = 'rl_training_episodes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    episode_number = Column(Integer, nullable=False, index=True)
    total_reward = Column(Float, nullable=False)
    episode_length = Column(Integer, nullable=False)
    avg_confidence = Column(Float)
    total_trades = Column(Integer, nullable=False, default=0)
    winning_trades = Column(Integer, nullable=False, default=0)
    pnl = Column(Float, nullable=False, default=0)
    sharpe_ratio = Column(Float)
    max_drawdown = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class RLAction(Base):
    __tablename__ = 'rl_actions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    time = Column(DateTime(timezone=True), nullable=False, index=True)
    contract_id = Column(String(50), nullable=False, index=True)
    action = Column(String(10), nullable=False)  # LONG, SHORT, FLAT
    position_size = Column(Float, nullable=False)
    stop_loss = Column(Float)
    take_profit = Column(Float)
    indicators_selected = Column(ARRAY(Text))
    confidence = Column(Float)
    reward = Column(Float)

class ContractBotConfig(Base):
    """Configuración del bot específica por contrato"""
    __tablename__ = 'contract_bot_config'

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(String(50), ForeignKey('contracts.id'), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    stop_loss_usd = Column(Float, nullable=False, default=150)
    take_profit_ratio = Column(Float, nullable=False, default=2.5)
    max_positions = Column(Integer, nullable=False, default=3)
    max_daily_loss = Column(Float, nullable=False, default=600)
    max_daily_trades = Column(Integer, nullable=False, default=50)
    timeframe_minutes = Column(Integer, nullable=False, default=5)
    min_confidence = Column(Float, nullable=False, default=0.70)
    cooldown_seconds = Column(Integer, nullable=False, default=45)
    model_path = Column(String(255))  # Ruta al modelo RL específico
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class ContractIndicatorConfig(Base):
    """Configuración de indicadores específica por contrato"""
    __tablename__ = 'contract_indicator_config'

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(String(50), ForeignKey('contracts.id'), nullable=False, index=True)
    name = Column(String(100), nullable=False)

    # Indicadores habilitados
    use_smi = Column(Boolean, nullable=False, default=True)
    use_macd = Column(Boolean, nullable=False, default=True)
    use_bb = Column(Boolean, nullable=False, default=True)
    use_ma = Column(Boolean, nullable=False, default=True)
    use_stoch_rsi = Column(Boolean, nullable=False, default=False)
    use_vwap = Column(Boolean, nullable=False, default=False)
    use_supertrend = Column(Boolean, nullable=False, default=False)
    use_kdj = Column(Boolean, nullable=False, default=False)

    # Parámetros SMI
    smi_k_length = Column(Integer, nullable=False, default=8)
    smi_d_smoothing = Column(Integer, nullable=False, default=3)
    smi_signal_period = Column(Integer, nullable=False, default=3)

    # Parámetros MACD
    macd_fast_period = Column(Integer, nullable=False, default=12)
    macd_slow_period = Column(Integer, nullable=False, default=26)
    macd_signal_period = Column(Integer, nullable=False, default=9)

    # Parámetros Bollinger Bands
    bb_period = Column(Integer, nullable=False, default=20)
    bb_std_dev = Column(Float, nullable=False, default=2.0)

    # Parámetros Moving Averages
    ma_sma_fast = Column(Integer, nullable=False, default=20)
    ma_sma_slow = Column(Integer, nullable=False, default=50)
    ma_ema_fast = Column(Integer, nullable=False, default=12)
    ma_ema_slow = Column(Integer, nullable=False, default=26)

    # Parámetros StochRSI
    stoch_rsi_period = Column(Integer, nullable=False, default=14)
    stoch_rsi_stoch_period = Column(Integer, nullable=False, default=14)
    stoch_rsi_k_smooth = Column(Integer, nullable=False, default=3)
    stoch_rsi_d_smooth = Column(Integer, nullable=False, default=3)

    # Parámetros VWAP
    vwap_std_dev = Column(Float, nullable=False, default=2.0)

    # Parámetros SuperTrend
    supertrend_period = Column(Integer, nullable=False, default=10)
    supertrend_multiplier = Column(Float, nullable=False, default=3.0)

    # Parámetros KDJ
    kdj_period = Column(Integer, nullable=False, default=9)
    kdj_k_smooth = Column(Integer, nullable=False, default=3)
    kdj_d_smooth = Column(Integer, nullable=False, default=3)

    # Configuración general
    timeframe_minutes = Column(Integer, nullable=False, default=5)
    min_confidence = Column(Float, nullable=False, default=0.70)

    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class BacktestRun(Base):
    """Registro de ejecuciones de backtest"""
    __tablename__ = 'backtest_runs'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    contract_id = Column(String(50), ForeignKey('contracts.id'), nullable=False)

    # Configuración del backtest
    mode = Column(String(20), nullable=False)  # bot_only, bot_indicators, indicators_only
    timeframes = Column(ARRAY(Integer), nullable=False)  # [1, 5, 15] minutos
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)

    # Resultados
    total_trades = Column(Integer, nullable=False, default=0)
    winning_trades = Column(Integer, nullable=False, default=0)
    losing_trades = Column(Integer, nullable=False, default=0)
    total_pnl = Column(Float, nullable=False, default=0)
    win_rate = Column(Float)
    profit_factor = Column(Float)
    max_drawdown = Column(Float)
    sharpe_ratio = Column(Float)

    # Metadata
    bot_config_id = Column(Integer, ForeignKey('contract_bot_config.id'))
    indicator_config_id = Column(Integer, ForeignKey('contract_indicator_config.id'))

    completed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
