-- Inicialización de base de datos con TimescaleDB
-- Para trading de alta frecuencia

-- Activar TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Tabla de usuarios (credenciales)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);

-- Tabla de credenciales TopstepX
CREATE TABLE IF NOT EXISTS user_credentials (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    api_key TEXT NOT NULL,
    username VARCHAR(100) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, username)
);

CREATE INDEX IF NOT EXISTS idx_user_credentials_user ON user_credentials (user_id);
CREATE INDEX IF NOT EXISTS idx_user_credentials_active ON user_credentials (is_active);

-- Tabla de cuentas TopstepX asociadas a credenciales
CREATE TABLE IF NOT EXISTS topstep_accounts (
    id SERIAL PRIMARY KEY,
    credential_id INTEGER NOT NULL REFERENCES user_credentials(id) ON DELETE CASCADE,
    account_id VARCHAR(50) NOT NULL UNIQUE,
    account_name VARCHAR(200) NOT NULL,
    balance DOUBLE PRECISION DEFAULT 0,
    can_trade BOOLEAN DEFAULT TRUE,
    is_visible BOOLEAN DEFAULT TRUE,
    simulated BOOLEAN DEFAULT FALSE,
    is_selected BOOLEAN DEFAULT FALSE,
    last_sync TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_topstep_accounts_credential ON topstep_accounts (credential_id);
CREATE INDEX IF NOT EXISTS idx_topstep_accounts_account_id ON topstep_accounts (account_id);
CREATE INDEX IF NOT EXISTS idx_topstep_accounts_selected ON topstep_accounts (is_selected);

-- Tabla de barras históricas (OHLCV)
CREATE TABLE IF NOT EXISTS historical_bars (
    time TIMESTAMPTZ NOT NULL,
    contract_id VARCHAR(50) NOT NULL,
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume BIGINT NOT NULL,
    PRIMARY KEY (time, contract_id)
);

-- Convertir a hypertable para series temporales
SELECT create_hypertable('historical_bars', 'time', if_not_exists => TRUE);

-- Índices para consultas rápidas
CREATE INDEX IF NOT EXISTS idx_bars_contract_time ON historical_bars (contract_id, time DESC);

-- Tabla de indicadores calculados
CREATE TABLE IF NOT EXISTS indicators (
    time TIMESTAMPTZ NOT NULL,
    contract_id VARCHAR(50) NOT NULL,
    smi_value DOUBLE PRECISION,
    smi_signal DOUBLE PRECISION,
    macd_value DOUBLE PRECISION,
    macd_signal DOUBLE PRECISION,
    macd_histogram DOUBLE PRECISION,
    bb_upper DOUBLE PRECISION,
    bb_middle DOUBLE PRECISION,
    bb_lower DOUBLE PRECISION,
    sma_fast DOUBLE PRECISION,
    sma_slow DOUBLE PRECISION,
    ema_fast DOUBLE PRECISION,
    ema_slow DOUBLE PRECISION,
    atr DOUBLE PRECISION,
    stoch_rsi_value DOUBLE PRECISION,
    stoch_rsi_k DOUBLE PRECISION,
    stoch_rsi_d DOUBLE PRECISION,
    vwap_value DOUBLE PRECISION,
    vwap_upper DOUBLE PRECISION,
    vwap_lower DOUBLE PRECISION,
    supertrend_value DOUBLE PRECISION,
    supertrend_direction DOUBLE PRECISION,
    kdj_k DOUBLE PRECISION,
    kdj_d DOUBLE PRECISION,
    kdj_j DOUBLE PRECISION,
    rsi DOUBLE PRECISION,
    PRIMARY KEY (time, contract_id)
);

SELECT create_hypertable('indicators', 'time', if_not_exists => TRUE);

-- Tabla de señales de trading
CREATE TABLE IF NOT EXISTS trading_signals (
    id SERIAL,
    time TIMESTAMPTZ NOT NULL,
    contract_id VARCHAR(50) NOT NULL,
    signal VARCHAR(10) NOT NULL, -- LONG, SHORT, FLAT
    confidence DOUBLE PRECISION NOT NULL,
    indicators_used TEXT[], -- Array de indicadores usados
    reason TEXT,
    PRIMARY KEY (time, contract_id, id)
);

SELECT create_hypertable('trading_signals', 'time', if_not_exists => TRUE);

-- Tabla de posiciones
CREATE TABLE IF NOT EXISTS positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id VARCHAR(50) NOT NULL,
    contract_name VARCHAR(100) NOT NULL,
    side VARCHAR(10) NOT NULL,
    quantity INTEGER NOT NULL,
    entry_price DOUBLE PRECISION NOT NULL,
    entry_time TIMESTAMPTZ NOT NULL,
    stop_loss DOUBLE PRECISION NOT NULL,
    take_profit DOUBLE PRECISION NOT NULL,
    exit_price DOUBLE PRECISION,
    exit_time TIMESTAMPTZ,
    exit_reason VARCHAR(50),
    pnl DOUBLE PRECISION,
    ticks DOUBLE PRECISION,
    tick_size DOUBLE PRECISION NOT NULL,
    tick_value DOUBLE PRECISION NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN', -- OPEN, CLOSED
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_positions_status ON positions (status);
CREATE INDEX IF NOT EXISTS idx_positions_contract ON positions (contract_id);
CREATE INDEX IF NOT EXISTS idx_positions_entry_time ON positions (entry_time DESC);

-- Tabla de trades (histórico completo)
CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id UUID REFERENCES positions(id),
    contract_id VARCHAR(50) NOT NULL,
    contract_name VARCHAR(100) NOT NULL,
    side VARCHAR(10) NOT NULL,
    quantity INTEGER NOT NULL,
    entry_price DOUBLE PRECISION NOT NULL,
    exit_price DOUBLE PRECISION NOT NULL,
    entry_time TIMESTAMPTZ NOT NULL,
    exit_time TIMESTAMPTZ NOT NULL,
    pnl DOUBLE PRECISION NOT NULL,
    ticks DOUBLE PRECISION NOT NULL,
    exit_reason VARCHAR(50) NOT NULL,
    duration_minutes DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trades_contract ON trades (contract_id);
CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON trades (entry_time DESC);
CREATE INDEX IF NOT EXISTS idx_trades_pnl ON trades (pnl DESC);

-- Tabla de estadísticas diarias
CREATE TABLE IF NOT EXISTS daily_stats (
    date DATE PRIMARY KEY,
    total_trades INTEGER NOT NULL DEFAULT 0,
    winning_trades INTEGER NOT NULL DEFAULT 0,
    losing_trades INTEGER NOT NULL DEFAULT 0,
    total_pnl DOUBLE PRECISION NOT NULL DEFAULT 0,
    gross_profit DOUBLE PRECISION NOT NULL DEFAULT 0,
    gross_loss DOUBLE PRECISION NOT NULL DEFAULT 0,
    win_rate DOUBLE PRECISION NOT NULL DEFAULT 0,
    profit_factor DOUBLE PRECISION NOT NULL DEFAULT 0,
    max_drawdown DOUBLE PRECISION NOT NULL DEFAULT 0,
    sharpe_ratio DOUBLE PRECISION NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tabla de contratos
CREATE TABLE IF NOT EXISTS contracts (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    symbol_id VARCHAR(50) NOT NULL,
    tick_size DOUBLE PRECISION NOT NULL,
    tick_value DOUBLE PRECISION NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_contracts_active ON contracts (active);
CREATE INDEX IF NOT EXISTS idx_contracts_symbol ON contracts (symbol_id);

-- Tabla de configuración del bot
CREATE TABLE IF NOT EXISTS bot_config (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    stop_loss_usd DOUBLE PRECISION NOT NULL DEFAULT 150,
    take_profit_ratio DOUBLE PRECISION NOT NULL DEFAULT 2.5,
    max_positions INTEGER NOT NULL DEFAULT 8,
    max_daily_loss DOUBLE PRECISION NOT NULL DEFAULT 600,
    max_daily_trades INTEGER NOT NULL DEFAULT 400,
    use_smi BOOLEAN NOT NULL DEFAULT TRUE,
    use_macd BOOLEAN NOT NULL DEFAULT TRUE,
    use_bb BOOLEAN NOT NULL DEFAULT TRUE,
    use_ma BOOLEAN NOT NULL DEFAULT TRUE,
    timeframe_minutes INTEGER NOT NULL DEFAULT 1,
    min_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.60,
    cooldown_seconds INTEGER NOT NULL DEFAULT 45,
    active BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tabla de horarios de trading
CREATE TABLE IF NOT EXISTS trading_schedule (
    id SERIAL PRIMARY KEY,
    day_of_week INTEGER NOT NULL, -- 0=Lunes, 6=Domingo
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_schedule_active ON trading_schedule (active);

-- Insertar configuración por defecto
INSERT INTO bot_config (name) VALUES ('Default Strategy')
ON CONFLICT DO NOTHING;

-- Insertar horarios por defecto (Lunes a Viernes, 9:30 AM - 4:00 PM)
INSERT INTO trading_schedule (day_of_week, start_time, end_time, active) VALUES
(0, '09:30:00', '16:00:00', TRUE), -- Lunes
(1, '09:30:00', '16:00:00', TRUE), -- Martes
(2, '09:30:00', '16:00:00', TRUE), -- Miércoles
(3, '09:30:00', '16:00:00', TRUE), -- Jueves
(4, '09:30:00', '16:00:00', TRUE)  -- Viernes
ON CONFLICT DO NOTHING;

-- Tabla de episodios de entrenamiento RL
CREATE TABLE IF NOT EXISTS rl_training_episodes (
    id SERIAL PRIMARY KEY,
    episode_number INTEGER NOT NULL,
    total_reward DOUBLE PRECISION NOT NULL,
    episode_length INTEGER NOT NULL,
    avg_confidence DOUBLE PRECISION,
    total_trades INTEGER NOT NULL DEFAULT 0,
    winning_trades INTEGER NOT NULL DEFAULT 0,
    pnl DOUBLE PRECISION NOT NULL DEFAULT 0,
    sharpe_ratio DOUBLE PRECISION,
    max_drawdown DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rl_episodes_number ON rl_training_episodes (episode_number DESC);

-- Tabla de acciones del modelo RL
CREATE TABLE IF NOT EXISTS rl_actions (
    id SERIAL,
    time TIMESTAMPTZ NOT NULL,
    contract_id VARCHAR(50) NOT NULL,
    action VARCHAR(10) NOT NULL, -- LONG, SHORT, FLAT
    position_size DOUBLE PRECISION NOT NULL,
    stop_loss DOUBLE PRECISION,
    take_profit DOUBLE PRECISION,
    indicators_selected TEXT[],
    confidence DOUBLE PRECISION,
    reward DOUBLE PRECISION,
    PRIMARY KEY (time, contract_id, id)
);

SELECT create_hypertable('rl_actions', 'time', if_not_exists => TRUE);

-- Vistas materializadas para consultas rápidas

-- Vista de estadísticas en tiempo real
CREATE MATERIALIZED VIEW IF NOT EXISTS stats_realtime AS
SELECT
    COUNT(*) as total_trades,
    COUNT(*) FILTER (WHERE pnl > 0) as winning_trades,
    COUNT(*) FILTER (WHERE pnl < 0) as losing_trades,
    COALESCE(SUM(pnl), 0) as total_pnl,
    COALESCE(SUM(pnl) FILTER (WHERE pnl > 0), 0) as gross_profit,
    COALESCE(SUM(ABS(pnl)) FILTER (WHERE pnl < 0), 0) as gross_loss,
    CASE
        WHEN COUNT(*) > 0 THEN (COUNT(*) FILTER (WHERE pnl > 0)::DOUBLE PRECISION / COUNT(*)) * 100
        ELSE 0
    END as win_rate,
    CASE
        WHEN SUM(ABS(pnl)) FILTER (WHERE pnl < 0) > 0
        THEN SUM(pnl) FILTER (WHERE pnl > 0) / SUM(ABS(pnl)) FILTER (WHERE pnl < 0)
        ELSE 0
    END as profit_factor
FROM trades
WHERE entry_time >= CURRENT_DATE;

CREATE UNIQUE INDEX IF NOT EXISTS stats_realtime_idx ON stats_realtime ((1));

-- Función para refrescar stats
CREATE OR REPLACE FUNCTION refresh_stats() RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY stats_realtime;
END;
$$ LANGUAGE plpgsql;

-- Trigger para actualizar updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_bot_config_updated_at BEFORE UPDATE ON bot_config
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_contracts_updated_at BEFORE UPDATE ON contracts
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_daily_stats_updated_at BEFORE UPDATE ON daily_stats
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_credentials_updated_at BEFORE UPDATE ON user_credentials
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_topstep_accounts_updated_at BEFORE UPDATE ON topstep_accounts
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Políticas de retención (mantener solo 90 días de datos crudos)
SELECT add_retention_policy('historical_bars', INTERVAL '90 days', if_not_exists => TRUE);
SELECT add_retention_policy('indicators', INTERVAL '90 days', if_not_exists => TRUE);
SELECT add_retention_policy('rl_actions', INTERVAL '90 days', if_not_exists => TRUE);

-- Compresión automática después de 7 días
SELECT add_compression_policy('historical_bars', INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_compression_policy('indicators', INTERVAL '7 days', if_not_exists => TRUE);

-- Nuevas tablas para configuraciones por contrato y backtesting

-- Tabla de configuración del bot por contrato
CREATE TABLE IF NOT EXISTS contract_bot_config (
    id SERIAL PRIMARY KEY,
    contract_id VARCHAR(50) NOT NULL REFERENCES contracts(id),
    name VARCHAR(100) NOT NULL,
    stop_loss_usd DOUBLE PRECISION NOT NULL DEFAULT 150,
    take_profit_ratio DOUBLE PRECISION NOT NULL DEFAULT 2.5,
    max_positions INTEGER NOT NULL DEFAULT 3,
    max_daily_loss DOUBLE PRECISION NOT NULL DEFAULT 600,
    max_daily_trades INTEGER NOT NULL DEFAULT 50,
    timeframe_minutes INTEGER NOT NULL DEFAULT 5,
    min_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.70,
    cooldown_seconds INTEGER NOT NULL DEFAULT 45,
    model_path VARCHAR(255),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_contract_bot_config_contract ON contract_bot_config (contract_id);
CREATE INDEX IF NOT EXISTS idx_contract_bot_config_active ON contract_bot_config (active);

CREATE TRIGGER update_contract_bot_config_updated_at BEFORE UPDATE ON contract_bot_config
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Tabla de configuración de indicadores por contrato
CREATE TABLE IF NOT EXISTS contract_indicator_config (
    id SERIAL PRIMARY KEY,
    contract_id VARCHAR(50) NOT NULL REFERENCES contracts(id),
    name VARCHAR(100) NOT NULL,
    use_smi BOOLEAN NOT NULL DEFAULT TRUE,
    use_macd BOOLEAN NOT NULL DEFAULT TRUE,
    use_bb BOOLEAN NOT NULL DEFAULT TRUE,
    use_ma BOOLEAN NOT NULL DEFAULT TRUE,
    use_stoch_rsi BOOLEAN NOT NULL DEFAULT FALSE,
    use_vwap BOOLEAN NOT NULL DEFAULT FALSE,
    use_supertrend BOOLEAN NOT NULL DEFAULT FALSE,
    use_kdj BOOLEAN NOT NULL DEFAULT FALSE,
    smi_k_length INTEGER NOT NULL DEFAULT 8,
    smi_d_smoothing INTEGER NOT NULL DEFAULT 3,
    smi_signal_period INTEGER NOT NULL DEFAULT 3,
    macd_fast_period INTEGER NOT NULL DEFAULT 12,
    macd_slow_period INTEGER NOT NULL DEFAULT 26,
    macd_signal_period INTEGER NOT NULL DEFAULT 9,
    bb_period INTEGER NOT NULL DEFAULT 20,
    bb_std_dev DOUBLE PRECISION NOT NULL DEFAULT 2.0,
    ma_sma_fast INTEGER NOT NULL DEFAULT 20,
    ma_sma_slow INTEGER NOT NULL DEFAULT 50,
    ma_ema_fast INTEGER NOT NULL DEFAULT 12,
    ma_ema_slow INTEGER NOT NULL DEFAULT 26,
    stoch_rsi_period INTEGER NOT NULL DEFAULT 14,
    stoch_rsi_stoch_period INTEGER NOT NULL DEFAULT 14,
    stoch_rsi_k_smooth INTEGER NOT NULL DEFAULT 3,
    stoch_rsi_d_smooth INTEGER NOT NULL DEFAULT 3,
    vwap_std_dev DOUBLE PRECISION NOT NULL DEFAULT 2.0,
    supertrend_period INTEGER NOT NULL DEFAULT 10,
    supertrend_multiplier DOUBLE PRECISION NOT NULL DEFAULT 3.0,
    kdj_period INTEGER NOT NULL DEFAULT 9,
    kdj_k_smooth INTEGER NOT NULL DEFAULT 3,
    kdj_d_smooth INTEGER NOT NULL DEFAULT 3,
    timeframe_minutes INTEGER NOT NULL DEFAULT 5,
    min_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.70,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_contract_indicator_config_contract ON contract_indicator_config (contract_id);
CREATE INDEX IF NOT EXISTS idx_contract_indicator_config_active ON contract_indicator_config (active);

CREATE TRIGGER update_contract_indicator_config_updated_at BEFORE UPDATE ON contract_indicator_config
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Tabla de ejecuciones de backtest
CREATE TABLE IF NOT EXISTS backtest_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    contract_id VARCHAR(50) NOT NULL REFERENCES contracts(id),
    mode VARCHAR(20) NOT NULL, -- bot_only, bot_indicators, indicators_only
    timeframes INTEGER[] NOT NULL, -- [1, 5, 15] minutos
    start_date TIMESTAMPTZ NOT NULL,
    end_date TIMESTAMPTZ NOT NULL,
    total_trades INTEGER NOT NULL DEFAULT 0,
    winning_trades INTEGER NOT NULL DEFAULT 0,
    losing_trades INTEGER NOT NULL DEFAULT 0,
    total_pnl DOUBLE PRECISION NOT NULL DEFAULT 0,
    win_rate DOUBLE PRECISION,
    profit_factor DOUBLE PRECISION,
    max_drawdown DOUBLE PRECISION,
    sharpe_ratio DOUBLE PRECISION,
    bot_config_id INTEGER REFERENCES contract_bot_config(id),
    indicator_config_id INTEGER REFERENCES contract_indicator_config(id),
    completed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_backtest_runs_contract ON backtest_runs (contract_id);
CREATE INDEX IF NOT EXISTS idx_backtest_runs_created ON backtest_runs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_backtest_runs_completed ON backtest_runs (completed);

COMMIT;
