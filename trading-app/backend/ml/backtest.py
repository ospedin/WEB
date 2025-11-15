# Sistema de Backtest Multi-Timeframe con RL y Trading Técnico
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
import numpy as np
from sqlalchemy.orm import Session
import logging

from db.models import (
    HistoricalBar, BacktestRun, ContractBotConfig,
    ContractIndicatorConfig, Contract, Position, Trade
)
from api.indicators import TechnicalIndicators
from api.topstep import HistoricalBar as TopstepBar
from ml.trading_env import TradingEnv
from stable_baselines3 import PPO

logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    Motor de backtest que soporta:
    - Multi-timeframe (1m, 5m, 15m, 1h, etc.)
    - Tres modos: bot_only, bot_indicators, indicators_only
    - Configuración per-contract
    - Generación paralela de señales
    """

    def __init__(
        self,
        db_session: Session,
        contract_id: str,
        mode: str,  # bot_only, bot_indicators, indicators_only
        timeframes: List[int],  # [1, 5, 15] minutos
        start_date: datetime,
        end_date: datetime,
        bot_config_id: Optional[int] = None,
        indicator_config_id: Optional[int] = None,
        model_path: Optional[str] = None
    ):
        self.db = db_session
        self.contract_id = contract_id
        self.mode = mode
        self.timeframes = sorted(timeframes)
        self.start_date = start_date
        self.end_date = end_date
        self.bot_config_id = bot_config_id
        self.indicator_config_id = indicator_config_id
        self.model_path = model_path

        # Cargar configuraciones
        self.contract = self._load_contract()
        self.bot_config = self._load_bot_config() if bot_config_id else None
        self.indicator_config = self._load_indicator_config() if indicator_config_id else None

        # Cargar modelo RL si es necesario
        self.model = None
        if self.mode in ['bot_only', 'bot_indicators'] and model_path:
            try:
                self.model = PPO.load(model_path)
                logger.info(f"Modelo RL cargado desde {model_path}")
            except Exception as e:
                logger.error(f"Error cargando modelo RL: {e}")

        # Estado del backtest
        self.positions: List[Dict] = []
        self.trades: List[Dict] = []
        self.balance = 100000.0  # Balance inicial
        self.peak_balance = self.balance
        self.max_drawdown = 0.0

    def _load_contract(self) -> Contract:
        """Cargar información del contrato"""
        contract = self.db.query(Contract).filter(Contract.id == self.contract_id).first()
        if not contract:
            raise ValueError(f"Contrato {self.contract_id} no encontrado")
        return contract

    def _load_bot_config(self) -> Optional[ContractBotConfig]:
        """Cargar configuración del bot para este contrato"""
        if not self.bot_config_id:
            return None
        config = self.db.query(ContractBotConfig).filter(
            ContractBotConfig.id == self.bot_config_id
        ).first()
        return config

    def _load_indicator_config(self) -> Optional[ContractIndicatorConfig]:
        """Cargar configuración de indicadores para este contrato"""
        if not self.indicator_config_id:
            return None
        config = self.db.query(ContractIndicatorConfig).filter(
            ContractIndicatorConfig.id == self.indicator_config_id
        ).first()
        return config

    def _load_bars_for_timeframe(self, timeframe_minutes: int) -> List[TopstepBar]:
        """Cargar barras históricas para un timeframe específico"""
        bars_query = self.db.query(HistoricalBar).filter(
            HistoricalBar.contract_id == self.contract_id,
            HistoricalBar.time >= self.start_date,
            HistoricalBar.time <= self.end_date
        ).order_by(HistoricalBar.time)

        bars_db = bars_query.all()

        if not bars_db:
            logger.warning(f"No hay datos para {self.contract_id} en el período especificado")
            return []

        # Si es timeframe mayor a 1m, agregar barras
        if timeframe_minutes > 1:
            return self._aggregate_bars(bars_db, timeframe_minutes)
        else:
            # Convertir a TopstepBar
            return [
                TopstepBar(
                    open=float(bar.open),
                    high=float(bar.high),
                    low=float(bar.low),
                    close=float(bar.close),
                    volume=int(bar.volume),
                    time=bar.time.isoformat()
                )
                for bar in bars_db
            ]

    def _aggregate_bars(self, bars_1m: List[HistoricalBar], timeframe_minutes: int) -> List[TopstepBar]:
        """Agregar barras de 1m a timeframe mayor"""
        aggregated = []
        current_bars = []
        current_start = None

        for bar in bars_1m:
            bar_time = bar.time.replace(second=0, microsecond=0)

            # Calcular inicio del período
            minutes_since_midnight = bar_time.hour * 60 + bar_time.minute
            period_start_minutes = (minutes_since_midnight // timeframe_minutes) * timeframe_minutes
            period_start = bar_time.replace(
                hour=period_start_minutes // 60,
                minute=period_start_minutes % 60
            )

            if current_start is None:
                current_start = period_start

            if period_start != current_start:
                # Crear barra agregada
                if current_bars:
                    aggregated.append(self._create_aggregated_bar(current_bars, current_start))
                current_bars = [bar]
                current_start = period_start
            else:
                current_bars.append(bar)

        # Última barra
        if current_bars:
            aggregated.append(self._create_aggregated_bar(current_bars, current_start))

        return aggregated

    def _create_aggregated_bar(self, bars: List[HistoricalBar], time: datetime) -> TopstepBar:
        """Crear barra agregada desde múltiples barras de 1m"""
        return TopstepBar(
            open=float(bars[0].open),
            high=float(max(bar.high for bar in bars)),
            low=float(min(bar.low for bar in bars)),
            close=float(bars[-1].close),
            volume=int(sum(bar.volume for bar in bars)),
            time=time.isoformat()
        )

    async def _generate_bot_signal(self, bars: List[TopstepBar]) -> Optional[Dict]:
        """Generar señal usando el modelo RL"""
        if not self.model:
            return None

        try:
            # Crear environment temporal
            temp_env = TradingEnv(
                bars_data=[],
                contract_symbol=self.contract_id,
                initial_balance=self.balance
            )

            # Preparar observación
            obs_data = temp_env._calculate_technical_features(bars)
            observation = temp_env._build_observation(obs_data, bars[-1])

            # Predecir acción
            action, _ = self.model.predict(observation, deterministic=True)
            decoded_action = temp_env.decode_action(action)

            action_type = decoded_action['action_type']
            if action_type == 0:
                signal = 'LONG'
            elif action_type == 1:
                signal = 'SHORT'
            else:
                signal = 'NEUTRAL'

            return {
                'signal': signal,
                'confidence': 0.75,  # Placeholder
                'source': 'RL_MODEL',
                'position_size': float(decoded_action['position_size'][0]),
                'sl_multiplier': float(decoded_action['sl_multiplier'][0]),
                'tp_multiplier': float(decoded_action['tp_multiplier'][0])
            }

        except Exception as e:
            logger.error(f"Error generando señal RL: {e}")
            return None

    async def _generate_indicator_signal(self, bars: List[TopstepBar]) -> Optional[Dict]:
        """Generar señal usando indicadores técnicos"""
        if not self.indicator_config:
            return None

        try:
            signal_result = TechnicalIndicators.generate_signal(
                bars=bars,
                use_smi=self.indicator_config.use_smi,
                use_macd=self.indicator_config.use_macd,
                use_bb=self.indicator_config.use_bb,
                use_ma=self.indicator_config.use_ma,
                use_stoch_rsi=self.indicator_config.use_stoch_rsi,
                use_vwap=self.indicator_config.use_vwap,
                use_supertrend=self.indicator_config.use_supertrend,
                use_kdj=self.indicator_config.use_kdj
            )

            return {
                'signal': signal_result['signal'],
                'confidence': signal_result['confidence'],
                'source': 'INDICATORS',
                'reason': signal_result['reason'],
                'indicators': signal_result['indicators']
            }

        except Exception as e:
            logger.error(f"Error generando señal de indicadores: {e}")
            return None

    async def _generate_signals_parallel(self, bars: List[TopstepBar]) -> Dict:
        """Generar señales en paralelo (bot e indicadores)"""
        tasks = []

        if self.mode in ['bot_only', 'bot_indicators']:
            tasks.append(self._generate_bot_signal(bars))

        if self.mode in ['indicators_only', 'bot_indicators']:
            tasks.append(self._generate_indicator_signal(bars))

        results = await asyncio.gather(*tasks)

        # Combinar señales según el modo
        if self.mode == 'bot_only':
            return results[0] if results[0] else {'signal': 'NEUTRAL', 'confidence': 0.0}

        elif self.mode == 'indicators_only':
            return results[0] if results[0] else {'signal': 'NEUTRAL', 'confidence': 0.0}

        elif self.mode == 'bot_indicators':
            bot_signal = results[0] if len(results) > 0 else None
            ind_signal = results[1] if len(results) > 1 else None

            # Combinar señales: ambos deben estar de acuerdo
            if bot_signal and ind_signal:
                if bot_signal['signal'] == ind_signal['signal'] and bot_signal['signal'] != 'NEUTRAL':
                    avg_confidence = (bot_signal['confidence'] + ind_signal['confidence']) / 2
                    return {
                        'signal': bot_signal['signal'],
                        'confidence': avg_confidence,
                        'source': 'BOT_AND_INDICATORS',
                        'bot_signal': bot_signal,
                        'indicator_signal': ind_signal
                    }

            return {'signal': 'NEUTRAL', 'confidence': 0.0}

        return {'signal': 'NEUTRAL', 'confidence': 0.0}

    def _open_position(self, signal: Dict, current_bar: TopstepBar):
        """Abrir una nueva posición"""
        if signal['signal'] not in ['LONG', 'SHORT']:
            return

        # Verificar límites de posiciones
        open_positions = len([p for p in self.positions if p['status'] == 'OPEN'])
        max_positions = self.bot_config.max_positions if self.bot_config else 3

        if open_positions >= max_positions:
            return

        # Calcular stop loss y take profit
        sl_multiplier = signal.get('sl_multiplier', 1.0)
        tp_multiplier = signal.get('tp_multiplier', 2.5)

        stop_loss_usd = (self.bot_config.stop_loss_usd if self.bot_config else 150) * sl_multiplier
        ticks_sl = stop_loss_usd / self.contract.tick_value
        distance_sl = ticks_sl * self.contract.tick_size

        if signal['signal'] == 'LONG':
            stop_loss = current_bar.close - distance_sl
            take_profit = current_bar.close + (distance_sl * tp_multiplier)
        else:
            stop_loss = current_bar.close + distance_sl
            take_profit = current_bar.close - (distance_sl * tp_multiplier)

        position = {
            'contract_id': self.contract_id,
            'side': signal['signal'],
            'quantity': 1,
            'entry_price': current_bar.close,
            'entry_time': current_bar.time,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'status': 'OPEN',
            'signal_source': signal.get('source', 'UNKNOWN')
        }

        self.positions.append(position)
        logger.info(f"Posición abierta: {signal['signal']} @ {current_bar.close}")

    def _check_position_exits(self, current_bar: TopstepBar):
        """Verificar si alguna posición debe cerrarse"""
        for position in self.positions:
            if position['status'] != 'OPEN':
                continue

            exit_reason = None
            exit_price = None

            # Verificar stop loss y take profit
            if position['side'] == 'LONG':
                if current_bar.low <= position['stop_loss']:
                    exit_reason = 'STOP_LOSS'
                    exit_price = position['stop_loss']
                elif current_bar.high >= position['take_profit']:
                    exit_reason = 'TAKE_PROFIT'
                    exit_price = position['take_profit']
            else:  # SHORT
                if current_bar.high >= position['stop_loss']:
                    exit_reason = 'STOP_LOSS'
                    exit_price = position['stop_loss']
                elif current_bar.low <= position['take_profit']:
                    exit_reason = 'TAKE_PROFIT'
                    exit_price = position['take_profit']

            if exit_reason:
                self._close_position(position, exit_price, current_bar.time, exit_reason)

    def _close_position(self, position: Dict, exit_price: float, exit_time: str, reason: str):
        """Cerrar una posición y registrar el trade"""
        position['status'] = 'CLOSED'
        position['exit_price'] = exit_price
        position['exit_time'] = exit_time
        position['exit_reason'] = reason

        # Calcular P&L en ticks
        if position['side'] == 'LONG':
            ticks = (exit_price - position['entry_price']) / self.contract.tick_size
        else:
            ticks = (position['entry_price'] - exit_price) / self.contract.tick_size

        pnl = ticks * self.contract.tick_value * position['quantity']

        trade = {
            'contract_id': self.contract_id,
            'side': position['side'],
            'entry_price': position['entry_price'],
            'exit_price': exit_price,
            'entry_time': position['entry_time'],
            'exit_time': exit_time,
            'pnl': pnl,
            'ticks': ticks,
            'exit_reason': reason,
            'signal_source': position['signal_source']
        }

        self.trades.append(trade)
        self.balance += pnl

        # Actualizar drawdown
        if self.balance > self.peak_balance:
            self.peak_balance = self.balance
        else:
            drawdown = self.peak_balance - self.balance
            if drawdown > self.max_drawdown:
                self.max_drawdown = drawdown

        logger.info(f"Posición cerrada: {reason} @ {exit_price}, P&L: ${pnl:.2f}")

    async def run(self) -> Dict:
        """Ejecutar el backtest"""
        logger.info(f"Iniciando backtest para {self.contract_id}")
        logger.info(f"Modo: {self.mode}, Timeframes: {self.timeframes}")
        logger.info(f"Período: {self.start_date} - {self.end_date}")

        # Cargar datos para el timeframe principal (el más pequeño)
        main_timeframe = min(self.timeframes)
        bars = self._load_bars_for_timeframe(main_timeframe)

        if not bars:
            raise ValueError("No hay datos disponibles para el backtest")

        logger.info(f"Cargadas {len(bars)} barras de {main_timeframe}m")

        # Ventana para análisis (necesitamos suficientes barras para indicadores)
        window_size = 100

        for i in range(window_size, len(bars)):
            current_bar = bars[i]
            window_bars = bars[i - window_size:i + 1]

            # Generar señales en paralelo
            signal = await self._generate_signals_parallel(window_bars)

            # Verificar salidas de posiciones existentes
            self._check_position_exits(current_bar)

            # Abrir nueva posición si hay señal
            min_confidence = self.indicator_config.min_confidence if self.indicator_config else 0.70
            if signal['confidence'] >= min_confidence:
                self._open_position(signal, current_bar)

        # Cerrar posiciones abiertas al final
        for position in self.positions:
            if position['status'] == 'OPEN':
                self._close_position(
                    position,
                    bars[-1].close,
                    bars[-1].time,
                    'END_OF_BACKTEST'
                )

        # Calcular estadísticas
        results = self._calculate_results()

        logger.info(f"Backtest completado: {results['total_trades']} trades, P&L: ${results['total_pnl']:.2f}")

        return results

    def _calculate_results(self) -> Dict:
        """Calcular estadísticas del backtest"""
        if not self.trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'total_pnl': 0.0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'max_drawdown': 0.0,
                'final_balance': self.balance
            }

        winning_trades = [t for t in self.trades if t['pnl'] > 0]
        losing_trades = [t for t in self.trades if t['pnl'] < 0]

        gross_profit = sum(t['pnl'] for t in winning_trades)
        gross_loss = abs(sum(t['pnl'] for t in losing_trades))

        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        win_rate = len(winning_trades) / len(self.trades) if self.trades else 0.0

        return {
            'total_trades': len(self.trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'total_pnl': sum(t['pnl'] for t in self.trades),
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'max_drawdown': self.max_drawdown,
            'final_balance': self.balance,
            'trades': self.trades
        }

    def save_to_database(self, results: Dict) -> str:
        """Guardar resultados del backtest en la base de datos"""
        backtest_run = BacktestRun(
            name=f"{self.contract_id}_{self.mode}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            contract_id=self.contract_id,
            mode=self.mode,
            timeframes=self.timeframes,
            start_date=self.start_date,
            end_date=self.end_date,
            total_trades=results['total_trades'],
            winning_trades=results['winning_trades'],
            losing_trades=results['losing_trades'],
            total_pnl=results['total_pnl'],
            win_rate=results['win_rate'],
            profit_factor=results['profit_factor'],
            max_drawdown=results['max_drawdown'],
            bot_config_id=self.bot_config_id,
            indicator_config_id=self.indicator_config_id,
            completed=True,
            completed_at=datetime.now(timezone.utc)
        )

        self.db.add(backtest_run)
        self.db.commit()

        logger.info(f"Backtest guardado con ID: {backtest_run.id}")

        return str(backtest_run.id)
