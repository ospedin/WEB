# Entorno Gymnasium Custom para Trading con RL
import gymnasium as gym
from gymnasium import spaces
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class TradingEnv(gym.Env):
    """
    Entorno de trading personalizado para Reinforcement Learning

    El agente puede:
    - Decidir acción: LONG (0), SHORT (1), FLAT (2)
    - Decidir tamaño de posición: 0.1 a 1.0
    - Decidir qué indicadores usar: SMI, MACD, BB, MA
    - Decidir SL y TP dinámicamente
    """

    metadata = {'render_modes': ['human']}

    def __init__(self,
                 bars_data: List[Dict],
                 initial_capital: float = 50000.0,
                 max_positions: int = 8,
                 stop_loss_usd: float = 150.0,
                 take_profit_ratio: float = 2.5,
                 tick_size: float = 0.25,
                 tick_value: float = 5.0,
                 commission_per_trade: float = 2.50,
                 lookback_window: int = 100):
        """
        Args:
            bars_data: Lista de diccionarios con OHLCV e indicadores
            initial_capital: Capital inicial
            max_positions: Máximo de posiciones simultáneas
            stop_loss_usd: Stop loss fijo en USD
            take_profit_ratio: Ratio TP/SL
            tick_size: Tamaño del tick del contrato
            tick_value: Valor del tick en USD
            commission_per_trade: Comisión por operación
            lookback_window: Ventana de observación
        """
        super().__init__()

        self.bars_data = bars_data
        self.initial_capital = initial_capital
        self.max_positions = max_positions
        self.stop_loss_usd = stop_loss_usd
        self.take_profit_ratio = take_profit_ratio
        self.tick_size = tick_size
        self.tick_value = tick_value
        self.commission = commission_per_trade
        self.lookback_window = lookback_window

        # Estado del entorno
        self.current_step = 0
        self.balance = initial_capital
        self.equity = initial_capital
        self.positions = []  # Lista de posiciones abiertas
        self.trades_history = []
        self.max_drawdown = 0.0
        self.peak_equity = initial_capital

        # Métricas
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0

        # Espacio de observación (45 features normalizadas)
        # OHLCV ratios (5) + Indicadores (16) + Estado (24)
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(45,),
            dtype=np.float32
        )

        # Espacio de acción (híbrido: discreto + continuo)
        # [action_type, position_size, indicator_smi, indicator_macd, indicator_bb, indicator_ma, sl_multiplier, tp_multiplier]
        self.action_space = spaces.Dict({
            'action_type': spaces.Discrete(3),  # 0=LONG, 1=SHORT, 2=FLAT
            'position_size': spaces.Box(low=0.1, high=1.0, shape=(1,), dtype=np.float32),
            'use_smi': spaces.Discrete(2),  # 0=No, 1=Sí
            'use_macd': spaces.Discrete(2),
            'use_bb': spaces.Discrete(2),
            'use_ma': spaces.Discrete(2),
            'sl_multiplier': spaces.Box(low=0.5, high=2.0, shape=(1,), dtype=np.float32),
            'tp_multiplier': spaces.Box(low=1.5, high=4.0, shape=(1,), dtype=np.float32)
        })

    def reset(self, seed=None, options=None):
        """Reset del entorno"""
        super().reset(seed=seed)

        self.current_step = self.lookback_window
        self.balance = self.initial_capital
        self.equity = self.initial_capital
        self.positions = []
        self.trades_history = []
        self.max_drawdown = 0.0
        self.peak_equity = self.initial_capital
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0

        observation = self._get_observation()
        info = self._get_info()

        return observation, info

    def step(self, action: Dict) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """
        Ejecuta un paso en el entorno

        Args:
            action: Diccionario con la acción del agente

        Returns:
            observation, reward, terminated, truncated, info
        """
        # Extraer componentes de la acción
        action_type = action['action_type']  # 0=LONG, 1=SHORT, 2=FLAT
        position_size = float(action['position_size'][0])
        use_indicators = {
            'smi': bool(action['use_smi']),
            'macd': bool(action['use_macd']),
            'bb': bool(action['use_bb']),
            'ma': bool(action['use_ma'])
        }
        sl_mult = float(action['sl_multiplier'][0])
        tp_mult = float(action['tp_multiplier'][0])

        # Obtener datos actuales
        current_bar = self.bars_data[self.current_step]
        current_price = current_bar['close']

        # Actualizar posiciones existentes (verificar SL/TP)
        self._update_positions(current_bar)

        # Ejecutar nueva acción si no es FLAT y hay espacio
        if action_type in [0, 1] and len(self.positions) < self.max_positions:
            self._open_position(
                action_type=action_type,
                position_size=position_size,
                entry_price=current_price,
                sl_multiplier=sl_mult,
                tp_multiplier=tp_mult,
                indicators_used=use_indicators
            )

        # Calcular reward
        reward = self._calculate_reward()

        # Actualizar equity
        self._update_equity(current_price)

        # Avanzar step
        self.current_step += 1

        # Verificar si termina el episodio
        terminated = (self.current_step >= len(self.bars_data) - 1)
        truncated = (self.balance <= self.initial_capital * 0.5)  # Stop si pierde 50%

        # Información adicional
        info = self._get_info()

        # Obtener nueva observación
        observation = self._get_observation()

        return observation, reward, terminated, truncated, info

    def _get_observation(self) -> np.ndarray:
        """
        Construye el vector de observación (45 features)

        Features:
        - OHLCV ratios vs VWAP (5)
        - Indicadores técnicos (16): SMI, MACD, BB, MA, ATR
        - Order flow (3): Delta volume, CVD, DOM imbalance
        - Temporal (3): minuto del día, día de la semana, días hasta vencimiento
        - Estado de la cuenta (10): PnL, drawdown, posiciones, streak
        - Market regime (8): Volatilidad, tendencia, correlaciones
        """
        if self.current_step < self.lookback_window:
            return np.zeros(45, dtype=np.float32)

        current_bar = self.bars_data[self.current_step]
        window_bars = self.bars_data[self.current_step - self.lookback_window:self.current_step]

        obs = []

        # 1. OHLCV ratios (5)
        vwap = np.average([b['close'] for b in window_bars], weights=[b['volume'] for b in window_bars])
        obs.extend([
            current_bar['open'] / vwap - 1.0,
            current_bar['high'] / vwap - 1.0,
            current_bar['low'] / vwap - 1.0,
            current_bar['close'] / vwap - 1.0,
            current_bar['volume'] / np.mean([b['volume'] for b in window_bars]) - 1.0
        ])

        # 2. Indicadores técnicos (16)
        obs.extend([
            current_bar.get('smi', 0.0) / 100.0,  # Normalizar SMI
            current_bar.get('smi_signal', 0.0) / 100.0,
            current_bar.get('macd', 0.0) / current_bar['close'],
            current_bar.get('macd_signal', 0.0) / current_bar['close'],
            current_bar.get('macd_histogram', 0.0) / current_bar['close'],
            current_bar.get('bb_upper', current_bar['close']) / current_bar['close'] - 1.0,
            current_bar.get('bb_middle', current_bar['close']) / current_bar['close'] - 1.0,
            current_bar.get('bb_lower', current_bar['close']) / current_bar['close'] - 1.0,
            current_bar.get('bb_bandwidth', 0.0),
            current_bar.get('sma_fast', current_bar['close']) / current_bar['close'] - 1.0,
            current_bar.get('sma_slow', current_bar['close']) / current_bar['close'] - 1.0,
            current_bar.get('ema_fast', current_bar['close']) / current_bar['close'] - 1.0,
            current_bar.get('ema_slow', current_bar['close']) / current_bar['close'] - 1.0,
            current_bar.get('atr', 0.0) / current_bar['close'],
            current_bar.get('rsi', 50.0) / 100.0,
            current_bar.get('adx', 0.0) / 100.0
        ])

        # 3. Order flow (3) - Simulado
        obs.extend([
            current_bar.get('delta_volume', 0.0) / current_bar['volume'] if current_bar['volume'] > 0 else 0.0,
            current_bar.get('cvd', 0.0) / current_bar['close'],
            current_bar.get('dom_imbalance', 0.0)
        ])

        # 4. Temporal (3)
        timestamp = current_bar.get('timestamp', datetime.now())
        obs.extend([
            timestamp.hour / 24.0,
            timestamp.weekday() / 7.0,
            0.5  # Días hasta vencimiento (placeholder)
        ])

        # 5. Estado de la cuenta (10)
        unrealized_pnl = sum([pos['unrealized_pnl'] for pos in self.positions])
        obs.extend([
            unrealized_pnl / self.initial_capital,
            self.max_drawdown / self.initial_capital,
            len(self.positions) / self.max_positions,
            self._get_win_streak() / 10.0,
            self.equity / self.initial_capital - 1.0,
            (self.equity - self.peak_equity) / self.initial_capital,
            self.total_trades / 100.0,
            self.winning_trades / max(self.total_trades, 1),
            self.balance / self.initial_capital - 1.0,
            1.0 if len(self.positions) > 0 else 0.0
        ])

        # 6. Market regime (8) - Características de volatilidad y tendencia
        closes = np.array([b['close'] for b in window_bars])
        returns = np.diff(closes) / closes[:-1]
        obs.extend([
            np.std(returns) if len(returns) > 0 else 0.0,  # Volatilidad
            np.mean(returns) if len(returns) > 0 else 0.0,  # Tendencia
            np.max(closes) / current_bar['close'] - 1.0,  # Distancia al máximo
            np.min(closes) / current_bar['close'] - 1.0,  # Distancia al mínimo
            (closes[-1] - closes[0]) / closes[0] if len(closes) > 0 else 0.0,  # Cambio total
            np.percentile(closes, 75) / current_bar['close'] - 1.0,  # Percentil 75
            np.percentile(closes, 25) / current_bar['close'] - 1.0,  # Percentil 25
            np.mean([b['volume'] for b in window_bars]) / current_bar['volume'] - 1.0 if current_bar['volume'] > 0 else 0.0
        ])

        return np.array(obs, dtype=np.float32)

    def _open_position(self, action_type: int, position_size: float, entry_price: float,
                      sl_multiplier: float, tp_multiplier: float, indicators_used: Dict):
        """Abre una nueva posición"""
        side = 'LONG' if action_type == 0 else 'SHORT'
        quantity = max(1, int(position_size * 3))  # Hasta 3 contratos

        # Calcular SL y TP por ticks
        total_sl = self.stop_loss_usd * sl_multiplier
        sl_per_contract = total_sl / quantity
        sl_ticks = int(sl_per_contract / self.tick_value)

        total_tp = total_sl * self.take_profit_ratio * tp_multiplier
        tp_per_contract = total_tp / quantity
        tp_ticks = int(tp_per_contract / self.tick_value)

        if side == 'LONG':
            sl_price = entry_price - (sl_ticks * self.tick_size)
            tp_price = entry_price + (tp_ticks * self.tick_size)
        else:
            sl_price = entry_price + (sl_ticks * self.tick_size)
            tp_price = entry_price - (tp_ticks * self.tick_size)

        position = {
            'id': len(self.positions),
            'side': side,
            'quantity': quantity,
            'entry_price': entry_price,
            'entry_step': self.current_step,
            'stop_loss': sl_price,
            'take_profit': tp_price,
            'unrealized_pnl': 0.0,
            'indicators_used': indicators_used
        }

        self.positions.append(position)
        self.balance -= self.commission  # Descontar comisión

    def _update_positions(self, current_bar: Dict):
        """Actualiza posiciones existentes y cierra si alcanzan SL/TP"""
        current_price = current_bar['close']
        positions_to_close = []

        for i, pos in enumerate(self.positions):
            # Calcular P&L no realizado
            price_diff = current_price - pos['entry_price']
            ticks = price_diff / self.tick_size

            if pos['side'] == 'SHORT':
                ticks = -ticks

            pnl = ticks * self.tick_value * pos['quantity']
            pos['unrealized_pnl'] = pnl

            # Verificar SL/TP
            hit_sl = False
            hit_tp = False

            if pos['side'] == 'LONG':
                hit_sl = current_price <= pos['stop_loss']
                hit_tp = current_price >= pos['take_profit']
            else:
                hit_sl = current_price >= pos['stop_loss']
                hit_tp = current_price <= pos['take_profit']

            if hit_sl or hit_tp:
                exit_price = pos['stop_loss'] if hit_sl else pos['take_profit']
                exit_reason = 'Stop Loss' if hit_sl else 'Take Profit'
                self._close_position(pos, exit_price, exit_reason)
                positions_to_close.append(i)

        # Eliminar posiciones cerradas
        for i in sorted(positions_to_close, reverse=True):
            del self.positions[i]

    def _close_position(self, position: Dict, exit_price: float, exit_reason: str):
        """Cierra una posición"""
        price_diff = exit_price - position['entry_price']
        ticks = price_diff / self.tick_size

        if position['side'] == 'SHORT':
            ticks = -ticks

        pnl = ticks * self.tick_value * position['quantity'] - self.commission

        trade = {
            'side': position['side'],
            'quantity': position['quantity'],
            'entry_price': position['entry_price'],
            'exit_price': exit_price,
            'pnl': pnl,
            'ticks': ticks,
            'exit_reason': exit_reason,
            'duration': self.current_step - position['entry_step']
        }

        self.trades_history.append(trade)
        self.balance += pnl
        self.total_trades += 1

        if pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1

    def _update_equity(self, current_price: float):
        """Actualiza equity y drawdown"""
        unrealized_pnl = sum([pos['unrealized_pnl'] for pos in self.positions])
        self.equity = self.balance + unrealized_pnl

        if self.equity > self.peak_equity:
            self.peak_equity = self.equity

        drawdown = (self.peak_equity - self.equity) / self.peak_equity
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown

    def _calculate_reward(self) -> float:
        """
        Calcula el reward basado en múltiples factores

        Reward = (profit * 0.6) - (drawdown * 0.4) + (sharpe_delta * 0.3) - penalties
        """
        if len(self.trades_history) == 0:
            return 0.0

        last_trade = self.trades_history[-1]
        profit_normalized = last_trade['pnl'] / self.initial_capital

        # Reward base por P&L
        reward = profit_normalized * 0.6

        # Penalización por drawdown
        reward -= self.max_drawdown * 0.4

        # Bonus por Sharpe ratio (si mejora)
        if len(self.trades_history) > 5:
            recent_pnls = [t['pnl'] for t in self.trades_history[-5:]]
            sharpe = np.mean(recent_pnls) / (np.std(recent_pnls) + 1e-6)
            reward += np.clip(sharpe / 100, -0.1, 0.3)

        # Penalización por trades muy cortos (< 5 minutos)
        if last_trade['duration'] < 5:
            reward -= 0.1

        # Penalización si el modelo sobreestima
        # (no aplicable en este contexto, pero se podría agregar)

        # Bonus por consistencia
        if self.total_trades >= 10:
            win_rate = self.winning_trades / self.total_trades
            if win_rate > 0.65:
                reward += 0.2

        return float(reward)

    def _get_win_streak(self) -> int:
        """Calcula el streak actual de trades ganadores"""
        if not self.trades_history:
            return 0

        streak = 0
        for trade in reversed(self.trades_history):
            if trade['pnl'] > 0:
                streak += 1
            else:
                break

        return streak

    def _get_info(self) -> Dict:
        """Información adicional del entorno"""
        return {
            'step': self.current_step,
            'balance': self.balance,
            'equity': self.equity,
            'positions': len(self.positions),
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.winning_trades / max(self.total_trades, 1),
            'max_drawdown': self.max_drawdown,
            'total_pnl': self.balance - self.initial_capital
        }

    def decode_action(self, action) -> Dict:
        """
        Decodifica una acción desde diferentes formatos al formato Dict esperado

        Args:
            action: Puede ser Dict (desde SB3), OrderedDict, o array

        Returns:
            Dict con los componentes de la acción
        """
        # Si ya es un Dict (OrderedDict de SB3), devolverlo directamente
        if isinstance(action, dict):
            return {
                'action_type': int(action.get('action_type', 2)),
                'position_size': np.array([float(action.get('position_size', [0.5])[0])], dtype=np.float32),
                'use_smi': int(action.get('use_smi', 1)),
                'use_macd': int(action.get('use_macd', 1)),
                'use_bb': int(action.get('use_bb', 1)),
                'use_ma': int(action.get('use_ma', 1)),
                'sl_multiplier': np.array([float(action.get('sl_multiplier', [1.0])[0])], dtype=np.float32),
                'tp_multiplier': np.array([float(action.get('tp_multiplier', [2.5])[0])], dtype=np.float32)
            }

        # Si es un array/tensor, parsearlo según el orden esperado
        # [action_type, position_size, use_smi, use_macd, use_bb, use_ma, sl_mult, tp_mult]
        if isinstance(action, (list, tuple, np.ndarray)):
            action = np.array(action)
            return {
                'action_type': int(action[0]),
                'position_size': np.array([float(action[1])], dtype=np.float32),
                'use_smi': int(action[2]),
                'use_macd': int(action[3]),
                'use_bb': int(action[4]),
                'use_ma': int(action[5]),
                'sl_multiplier': np.array([float(action[6])], dtype=np.float32),
                'tp_multiplier': np.array([float(action[7])], dtype=np.float32)
            }

        # Fallback: devolver acción segura (FLAT)
        logger.warning(f"Tipo de acción desconocido: {type(action)}, usando FLAT")
        return {
            'action_type': 2,  # FLAT
            'position_size': np.array([0.5], dtype=np.float32),
            'use_smi': 1,
            'use_macd': 1,
            'use_bb': 1,
            'use_ma': 1,
            'sl_multiplier': np.array([1.0], dtype=np.float32),
            'tp_multiplier': np.array([2.5], dtype=np.float32)
        }

    def render(self):
        """Renderiza el estado actual (opcional)"""
        if self.render_mode == 'human':
            print(f"Step: {self.current_step} | Balance: ${self.balance:.2f} | "
                  f"Equity: ${self.equity:.2f} | Positions: {len(self.positions)} | "
                  f"Trades: {self.total_trades} | Win Rate: {self.winning_trades/max(self.total_trades,1)*100:.1f}%")

    def close(self):
        """Cierra el entorno"""
        pass
