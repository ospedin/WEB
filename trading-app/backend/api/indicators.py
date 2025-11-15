# Indicadores Técnicos: SMI, MACD, BB, Medias Móviles
import numpy as np
from typing import List, Tuple, Dict
from dataclasses import dataclass
from .topstep import HistoricalBar

@dataclass
class SMIResult:
    smi: np.ndarray
    signal: np.ndarray
    confidence: float

@dataclass
class MACDResult:
    macd: np.ndarray
    signal: np.ndarray
    histogram: np.ndarray

@dataclass
class BollingerBandsResult:
    upper: np.ndarray
    middle: np.ndarray
    lower: np.ndarray
    bandwidth: np.ndarray

@dataclass
class MovingAveragesResult:
    sma_fast: np.ndarray
    sma_slow: np.ndarray
    ema_fast: np.ndarray
    ema_slow: np.ndarray

@dataclass
class StochRSIResult:
    stoch_rsi: np.ndarray
    k: np.ndarray
    d: np.ndarray

@dataclass
class VWAPResult:
    vwap: np.ndarray
    upper_band: np.ndarray
    lower_band: np.ndarray

@dataclass
class SuperTrendResult:
    supertrend: np.ndarray
    direction: np.ndarray  # 1 = bullish, -1 = bearish

@dataclass
class KDJResult:
    k: np.ndarray
    d: np.ndarray
    j: np.ndarray

class TechnicalIndicators:
    """Indicadores técnicos para trading"""

    @staticmethod
    def calculate_ema(data: np.ndarray, period: int) -> np.ndarray:
        """Calcula EMA (Exponential Moving Average)"""
        if len(data) < period:
            return data.copy()

        alpha = 2.0 / (period + 1.0)
        ema = np.zeros(len(data))
        ema[0] = data[0]

        for i in range(1, len(data)):
            ema[i] = alpha * data[i] + (1 - alpha) * ema[i-1]

        return ema

    @staticmethod
    def calculate_sma(data: np.ndarray, period: int) -> np.ndarray:
        """Calcula SMA (Simple Moving Average)"""
        if len(data) < period:
            return data.copy()

        sma = np.zeros(len(data))
        for i in range(period - 1, len(data)):
            sma[i] = np.mean(data[i - period + 1:i + 1])

        # Rellenar valores iniciales
        sma[:period - 1] = sma[period - 1]

        return sma

    @staticmethod
    def calculate_smi(bars: List[HistoricalBar],
                     k_length: int = 8,
                     d_smoothing: int = 3,
                     signal_period: int = 3) -> SMIResult:
        """
        Calcula SMI (Stochastic Momentum Index)
        Basado en el código de Nuevo_smi.py
        """
        if len(bars) < k_length + d_smoothing * 2 + signal_period:
            empty = np.zeros(len(bars))
            return SMIResult(smi=empty, signal=empty, confidence=0.0)

        closes = np.array([bar.close for bar in bars])
        highs = np.array([bar.high for bar in bars])
        lows = np.array([bar.low for bar in bars])

        # Calcular highest high y lowest low en período K
        high_k = np.zeros(len(bars))
        low_k = np.zeros(len(bars))

        for i in range(k_length - 1, len(bars)):
            start_idx = i - k_length + 1
            end_idx = i + 1
            high_k[i] = np.max(highs[start_idx:end_idx])
            low_k[i] = np.min(lows[start_idx:end_idx])

        # Calcular midpoint y range
        midpoint = (high_k + low_k) / 2
        rr = closes - midpoint
        hl = high_k - low_k

        # Doble suavizado EMA
        dsRR = TechnicalIndicators.calculate_ema(rr, d_smoothing)
        dsRR = TechnicalIndicators.calculate_ema(dsRR, d_smoothing)

        dsHL = TechnicalIndicators.calculate_ema(hl, d_smoothing)
        dsHL = TechnicalIndicators.calculate_ema(dsHL, d_smoothing)

        # Calcular SMI
        smi = np.zeros(len(closes))
        for i in range(len(closes)):
            if dsHL[i] > 1e-10:
                smi[i] = 200.0 * (dsRR[i] / dsHL[i])

        # Calcular señal
        signal = TechnicalIndicators.calculate_ema(smi, signal_period)

        # Calcular confianza
        current_smi = smi[-1]
        current_signal = signal[-1]
        prev_smi = smi[-2] if len(smi) > 1 else current_smi
        prev_signal = signal[-2] if len(signal) > 1 else current_signal

        confidence = 0.0
        if prev_smi <= prev_signal and current_smi > current_signal:
            # Cruce alcista
            confidence = min(0.95, 0.70 + abs(current_smi + 30) / 60 * 0.25)
        elif prev_smi >= prev_signal and current_smi < current_signal:
            # Cruce bajista
            confidence = min(0.95, 0.70 + abs(current_smi - 30) / 60 * 0.25)

        return SMIResult(smi=smi, signal=signal, confidence=confidence)

    @staticmethod
    def calculate_macd(bars: List[HistoricalBar],
                      fast_period: int = 12,
                      slow_period: int = 26,
                      signal_period: int = 9) -> MACDResult:
        """
        Calcula MACD (Moving Average Convergence Divergence)
        """
        closes = np.array([bar.close for bar in bars])

        # Calcular EMAs
        ema_fast = TechnicalIndicators.calculate_ema(closes, fast_period)
        ema_slow = TechnicalIndicators.calculate_ema(closes, slow_period)

        # MACD Line
        macd = ema_fast - ema_slow

        # Signal Line
        signal = TechnicalIndicators.calculate_ema(macd, signal_period)

        # Histogram
        histogram = macd - signal

        return MACDResult(macd=macd, signal=signal, histogram=histogram)

    @staticmethod
    def calculate_bollinger_bands(bars: List[HistoricalBar],
                                 period: int = 20,
                                 std_dev: float = 2.0) -> BollingerBandsResult:
        """
        Calcula Bandas de Bollinger (Bollinger Bands)
        """
        closes = np.array([bar.close for bar in bars])

        # Media móvil (banda media)
        middle = TechnicalIndicators.calculate_sma(closes, period)

        # Desviación estándar
        std = np.zeros(len(closes))
        for i in range(period - 1, len(closes)):
            std[i] = np.std(closes[i - period + 1:i + 1])

        std[:period - 1] = std[period - 1]

        # Bandas superior e inferior
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)

        # Bandwidth (ancho de banda)
        bandwidth = (upper - lower) / middle

        return BollingerBandsResult(
            upper=upper,
            middle=middle,
            lower=lower,
            bandwidth=bandwidth
        )

    @staticmethod
    def calculate_moving_averages(bars: List[HistoricalBar],
                                 sma_fast: int = 20,
                                 sma_slow: int = 50,
                                 ema_fast: int = 12,
                                 ema_slow: int = 26) -> MovingAveragesResult:
        """
        Calcula Medias Móviles (SMA y EMA)
        """
        closes = np.array([bar.close for bar in bars])

        return MovingAveragesResult(
            sma_fast=TechnicalIndicators.calculate_sma(closes, sma_fast),
            sma_slow=TechnicalIndicators.calculate_sma(closes, sma_slow),
            ema_fast=TechnicalIndicators.calculate_ema(closes, ema_fast),
            ema_slow=TechnicalIndicators.calculate_ema(closes, ema_slow)
        )

    @staticmethod
    def calculate_atr(bars: List[HistoricalBar], period: int = 14) -> np.ndarray:
        """Calcula Average True Range (ATR)"""
        highs = np.array([bar.high for bar in bars])
        lows = np.array([bar.low for bar in bars])
        closes = np.array([bar.close for bar in bars])

        if len(highs) < period + 1:
            return np.zeros(len(highs))

        tr = np.zeros(len(highs))
        tr[0] = highs[0] - lows[0]

        for i in range(1, len(highs)):
            tr1 = highs[i] - lows[i]
            tr2 = abs(highs[i] - closes[i-1])
            tr3 = abs(lows[i] - closes[i-1])
            tr[i] = max(tr1, tr2, tr3)

        atr = TechnicalIndicators.calculate_ema(tr, period)
        return atr

    @staticmethod
    def calculate_rsi(data: np.ndarray, period: int = 14) -> np.ndarray:
        """Calcula RSI (Relative Strength Index)"""
        if len(data) < period + 1:
            return np.full(len(data), 50.0)

        deltas = np.diff(data)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.zeros(len(data))
        avg_loss = np.zeros(len(data))

        # Primera media
        avg_gain[period] = np.mean(gains[:period])
        avg_loss[period] = np.mean(losses[:period])

        # Medias móviles exponenciales
        for i in range(period + 1, len(data)):
            avg_gain[i] = (avg_gain[i-1] * (period - 1) + gains[i-1]) / period
            avg_loss[i] = (avg_loss[i-1] * (period - 1) + losses[i-1]) / period

        rsi = np.zeros(len(data))
        for i in range(period, len(data)):
            if avg_loss[i] == 0:
                rsi[i] = 100
            else:
                rs = avg_gain[i] / avg_loss[i]
                rsi[i] = 100 - (100 / (1 + rs))

        rsi[:period] = 50.0
        return rsi

    @staticmethod
    def calculate_stoch_rsi(bars: List[HistoricalBar],
                           rsi_period: int = 14,
                           stoch_period: int = 14,
                           k_smooth: int = 3,
                           d_smooth: int = 3) -> StochRSIResult:
        """
        Calcula StochRSI (Stochastic RSI)
        Aplica estocástico sobre valores RSI
        """
        closes = np.array([bar.close for bar in bars])

        if len(closes) < rsi_period + stoch_period:
            empty = np.zeros(len(closes))
            return StochRSIResult(stoch_rsi=empty, k=empty, d=empty)

        # Calcular RSI
        rsi = TechnicalIndicators.calculate_rsi(closes, rsi_period)

        # Aplicar estocástico sobre RSI
        stoch_rsi = np.zeros(len(rsi))
        for i in range(stoch_period - 1, len(rsi)):
            rsi_window = rsi[i - stoch_period + 1:i + 1]
            rsi_min = np.min(rsi_window)
            rsi_max = np.max(rsi_window)

            if rsi_max - rsi_min > 1e-10:
                stoch_rsi[i] = (rsi[i] - rsi_min) / (rsi_max - rsi_min)
            else:
                stoch_rsi[i] = 0.5

        # Suavizar K
        k = TechnicalIndicators.calculate_sma(stoch_rsi * 100, k_smooth)

        # Suavizar D
        d = TechnicalIndicators.calculate_sma(k, d_smooth)

        return StochRSIResult(stoch_rsi=stoch_rsi * 100, k=k, d=d)

    @staticmethod
    def calculate_vwap(bars: List[HistoricalBar], std_dev: float = 2.0) -> VWAPResult:
        """
        Calcula VWAP (Volume Weighted Average Price)
        Requiere datos de volumen en HistoricalBar
        """
        if len(bars) < 2:
            empty = np.zeros(len(bars))
            return VWAPResult(vwap=empty, upper_band=empty, lower_band=empty)

        # Calcular precio típico
        typical_prices = np.array([(bar.high + bar.low + bar.close) / 3 for bar in bars])

        # Usar volumen si está disponible, sino usar 1
        volumes = np.array([getattr(bar, 'volume', 1.0) for bar in bars])

        # VWAP acumulado
        cumulative_tp_volume = np.cumsum(typical_prices * volumes)
        cumulative_volume = np.cumsum(volumes)

        vwap = cumulative_tp_volume / cumulative_volume

        # Calcular bandas usando desviación estándar
        squared_diff = np.power(typical_prices - vwap, 2)
        cumulative_squared_diff = np.cumsum(squared_diff * volumes)
        variance = cumulative_squared_diff / cumulative_volume
        std = np.sqrt(variance)

        upper_band = vwap + (std * std_dev)
        lower_band = vwap - (std * std_dev)

        return VWAPResult(vwap=vwap, upper_band=upper_band, lower_band=lower_band)

    @staticmethod
    def calculate_supertrend(bars: List[HistoricalBar],
                            period: int = 10,
                            multiplier: float = 3.0) -> SuperTrendResult:
        """
        Calcula SuperTrend
        Indicador de tendencia basado en ATR
        """
        if len(bars) < period + 1:
            empty = np.zeros(len(bars))
            return SuperTrendResult(supertrend=empty, direction=empty)

        highs = np.array([bar.high for bar in bars])
        lows = np.array([bar.low for bar in bars])
        closes = np.array([bar.close for bar in bars])

        # Calcular ATR
        atr = TechnicalIndicators.calculate_atr(bars, period)

        # Bandas básicas
        hl_avg = (highs + lows) / 2
        basic_upper = hl_avg + (multiplier * atr)
        basic_lower = hl_avg - (multiplier * atr)

        # Calcular SuperTrend
        final_upper = np.zeros(len(bars))
        final_lower = np.zeros(len(bars))
        supertrend = np.zeros(len(bars))
        direction = np.zeros(len(bars))

        final_upper[0] = basic_upper[0]
        final_lower[0] = basic_lower[0]
        supertrend[0] = closes[0]
        direction[0] = 1

        for i in range(1, len(bars)):
            # Final Upper Band
            if basic_upper[i] < final_upper[i-1] or closes[i-1] > final_upper[i-1]:
                final_upper[i] = basic_upper[i]
            else:
                final_upper[i] = final_upper[i-1]

            # Final Lower Band
            if basic_lower[i] > final_lower[i-1] or closes[i-1] < final_lower[i-1]:
                final_lower[i] = basic_lower[i]
            else:
                final_lower[i] = final_lower[i-1]

            # SuperTrend
            if closes[i] <= final_upper[i]:
                supertrend[i] = final_upper[i]
                direction[i] = -1  # Bearish
            else:
                supertrend[i] = final_lower[i]
                direction[i] = 1   # Bullish

        return SuperTrendResult(supertrend=supertrend, direction=direction)

    @staticmethod
    def calculate_kdj(bars: List[HistoricalBar],
                     period: int = 9,
                     k_smooth: int = 3,
                     d_smooth: int = 3) -> KDJResult:
        """
        Calcula KDJ (K-D-J Stochastic Oscillator)
        Similar a Stochastic pero con línea J adicional
        """
        if len(bars) < period:
            empty = np.zeros(len(bars))
            return KDJResult(k=empty, d=empty, j=empty)

        closes = np.array([bar.close for bar in bars])
        highs = np.array([bar.high for bar in bars])
        lows = np.array([bar.low for bar in bars])

        # Calcular %K raw
        k_raw = np.zeros(len(bars))
        for i in range(period - 1, len(bars)):
            highest_high = np.max(highs[i - period + 1:i + 1])
            lowest_low = np.min(lows[i - period + 1:i + 1])

            if highest_high - lowest_low > 1e-10:
                k_raw[i] = 100 * (closes[i] - lowest_low) / (highest_high - lowest_low)
            else:
                k_raw[i] = 50

        # Suavizar K
        k = TechnicalIndicators.calculate_sma(k_raw, k_smooth)

        # Suavizar D
        d = TechnicalIndicators.calculate_sma(k, d_smooth)

        # Calcular J
        j = 3 * k - 2 * d

        return KDJResult(k=k, d=d, j=j)

    @staticmethod
    def generate_signal(bars: List[HistoricalBar],
                       use_smi: bool = True,
                       use_macd: bool = True,
                       use_bb: bool = True,
                       use_ma: bool = True,
                       use_stoch_rsi: bool = False,
                       use_vwap: bool = False,
                       use_supertrend: bool = False,
                       use_kdj: bool = False) -> Dict:
        """
        Genera señal de trading combinando múltiples indicadores
        """
        if len(bars) < 50:
            return {
                'signal': 'NEUTRAL',
                'confidence': 0.0,
                'reason': 'Datos insuficientes',
                'indicators': {}
            }

        signals = []
        confidences = []
        reasons = []
        indicators_data = {}

        # SMI
        if use_smi:
            smi_result = TechnicalIndicators.calculate_smi(bars)
            current_smi = smi_result.smi[-1]
            current_signal = smi_result.signal[-1]
            prev_smi = smi_result.smi[-2]
            prev_signal = smi_result.signal[-2]

            indicators_data['smi'] = {
                'value': float(current_smi),
                'signal': float(current_signal)
            }

            if prev_smi <= prev_signal and current_smi > current_signal and current_smi < -20:
                signals.append('LONG')
                confidences.append(smi_result.confidence)
                reasons.append(f'SMI cruce alcista ({current_smi:.1f})')
            elif prev_smi >= prev_signal and current_smi < current_signal and current_smi > 20:
                signals.append('SHORT')
                confidences.append(smi_result.confidence)
                reasons.append(f'SMI cruce bajista ({current_smi:.1f})')

        # MACD
        if use_macd:
            macd_result = TechnicalIndicators.calculate_macd(bars)
            current_macd = macd_result.macd[-1]
            current_macd_signal = macd_result.signal[-1]
            prev_macd = macd_result.macd[-2]
            prev_macd_signal = macd_result.signal[-2]
            histogram = macd_result.histogram[-1]

            indicators_data['macd'] = {
                'macd': float(current_macd),
                'signal': float(current_macd_signal),
                'histogram': float(histogram)
            }

            if prev_macd <= prev_macd_signal and current_macd > current_macd_signal:
                signals.append('LONG')
                confidences.append(0.75)
                reasons.append('MACD cruce alcista')
            elif prev_macd >= prev_macd_signal and current_macd < current_macd_signal:
                signals.append('SHORT')
                confidences.append(0.75)
                reasons.append('MACD cruce bajista')

        # Bollinger Bands
        if use_bb:
            bb_result = TechnicalIndicators.calculate_bollinger_bands(bars)
            current_price = bars[-1].close
            upper = bb_result.upper[-1]
            lower = bb_result.lower[-1]
            middle = bb_result.middle[-1]

            indicators_data['bollinger'] = {
                'upper': float(upper),
                'middle': float(middle),
                'lower': float(lower),
                'bandwidth': float(bb_result.bandwidth[-1])
            }

            if current_price <= lower:
                signals.append('LONG')
                confidences.append(0.70)
                reasons.append('Precio en banda inferior')
            elif current_price >= upper:
                signals.append('SHORT')
                confidences.append(0.70)
                reasons.append('Precio en banda superior')

        # Moving Averages
        if use_ma:
            ma_result = TechnicalIndicators.calculate_moving_averages(bars)
            sma_fast = ma_result.sma_fast[-1]
            sma_slow = ma_result.sma_slow[-1]
            prev_sma_fast = ma_result.sma_fast[-2]
            prev_sma_slow = ma_result.sma_slow[-2]

            indicators_data['moving_averages'] = {
                'sma_fast': float(sma_fast),
                'sma_slow': float(sma_slow),
                'ema_fast': float(ma_result.ema_fast[-1]),
                'ema_slow': float(ma_result.ema_slow[-1])
            }

            if prev_sma_fast <= prev_sma_slow and sma_fast > sma_slow:
                signals.append('LONG')
                confidences.append(0.80)
                reasons.append('Golden Cross (SMA)')
            elif prev_sma_fast >= prev_sma_slow and sma_fast < sma_slow:
                signals.append('SHORT')
                confidences.append(0.80)
                reasons.append('Death Cross (SMA)')

        # StochRSI
        if use_stoch_rsi:
            stoch_rsi_result = TechnicalIndicators.calculate_stoch_rsi(bars)
            k_value = stoch_rsi_result.k[-1]
            d_value = stoch_rsi_result.d[-1]
            prev_k = stoch_rsi_result.k[-2]
            prev_d = stoch_rsi_result.d[-2]

            indicators_data['stoch_rsi'] = {
                'k': float(k_value),
                'd': float(d_value),
                'stoch_rsi': float(stoch_rsi_result.stoch_rsi[-1])
            }

            # Sobrecompra/Sobreventa
            if k_value < 20 and d_value < 20:
                signals.append('LONG')
                confidences.append(0.75)
                reasons.append(f'StochRSI sobreventa ({k_value:.1f})')
            elif k_value > 80 and d_value > 80:
                signals.append('SHORT')
                confidences.append(0.75)
                reasons.append(f'StochRSI sobrecompra ({k_value:.1f})')
            # Cruces
            elif prev_k <= prev_d and k_value > d_value and k_value < 50:
                signals.append('LONG')
                confidences.append(0.70)
                reasons.append('StochRSI cruce alcista')
            elif prev_k >= prev_d and k_value < d_value and k_value > 50:
                signals.append('SHORT')
                confidences.append(0.70)
                reasons.append('StochRSI cruce bajista')

        # VWAP
        if use_vwap:
            vwap_result = TechnicalIndicators.calculate_vwap(bars)
            current_price = bars[-1].close
            vwap_value = vwap_result.vwap[-1]
            upper_band = vwap_result.upper_band[-1]
            lower_band = vwap_result.lower_band[-1]

            indicators_data['vwap'] = {
                'vwap': float(vwap_value),
                'upper_band': float(upper_band),
                'lower_band': float(lower_band)
            }

            # Precio vs VWAP
            if current_price < lower_band:
                signals.append('LONG')
                confidences.append(0.75)
                reasons.append('Precio bajo banda inferior VWAP')
            elif current_price > upper_band:
                signals.append('SHORT')
                confidences.append(0.75)
                reasons.append('Precio sobre banda superior VWAP')
            elif current_price < vwap_value:
                signals.append('LONG')
                confidences.append(0.60)
                reasons.append('Precio bajo VWAP')
            elif current_price > vwap_value:
                signals.append('SHORT')
                confidences.append(0.60)
                reasons.append('Precio sobre VWAP')

        # SuperTrend
        if use_supertrend:
            supertrend_result = TechnicalIndicators.calculate_supertrend(bars)
            current_direction = supertrend_result.direction[-1]
            prev_direction = supertrend_result.direction[-2]
            supertrend_value = supertrend_result.supertrend[-1]

            indicators_data['supertrend'] = {
                'value': float(supertrend_value),
                'direction': int(current_direction)
            }

            # Cambio de tendencia
            if prev_direction <= 0 and current_direction > 0:
                signals.append('LONG')
                confidences.append(0.85)
                reasons.append('SuperTrend cambio a alcista')
            elif prev_direction >= 0 and current_direction < 0:
                signals.append('SHORT')
                confidences.append(0.85)
                reasons.append('SuperTrend cambio a bajista')
            # Tendencia actual
            elif current_direction > 0:
                signals.append('LONG')
                confidences.append(0.65)
                reasons.append('SuperTrend alcista')
            elif current_direction < 0:
                signals.append('SHORT')
                confidences.append(0.65)
                reasons.append('SuperTrend bajista')

        # KDJ
        if use_kdj:
            kdj_result = TechnicalIndicators.calculate_kdj(bars)
            k_value = kdj_result.k[-1]
            d_value = kdj_result.d[-1]
            j_value = kdj_result.j[-1]
            prev_k = kdj_result.k[-2]
            prev_d = kdj_result.d[-2]

            indicators_data['kdj'] = {
                'k': float(k_value),
                'd': float(d_value),
                'j': float(j_value)
            }

            # J line signals
            if j_value < 0:
                signals.append('LONG')
                confidences.append(0.80)
                reasons.append(f'KDJ sobreventa extrema (J={j_value:.1f})')
            elif j_value > 100:
                signals.append('SHORT')
                confidences.append(0.80)
                reasons.append(f'KDJ sobrecompra extrema (J={j_value:.1f})')
            # K-D crossovers
            elif prev_k <= prev_d and k_value > d_value and k_value < 50:
                signals.append('LONG')
                confidences.append(0.75)
                reasons.append('KDJ cruce alcista')
            elif prev_k >= prev_d and k_value < d_value and k_value > 50:
                signals.append('SHORT')
                confidences.append(0.75)
                reasons.append('KDJ cruce bajista')

        # Determinar señal final
        if not signals:
            return {
                'signal': 'NEUTRAL',
                'confidence': 0.0,
                'reason': 'Sin señales claras',
                'indicators': indicators_data
            }

        # Contar señales
        long_count = signals.count('LONG')
        short_count = signals.count('SHORT')

        final_signal = 'NEUTRAL'
        final_confidence = 0.0
        final_reason = ''

        if long_count > short_count:
            final_signal = 'LONG'
            long_confidences = [c for s, c in zip(signals, confidences) if s == 'LONG']
            final_confidence = np.mean(long_confidences)
            long_reasons = [r for s, r in zip(signals, reasons) if s == 'LONG']
            final_reason = ' + '.join(long_reasons)
        elif short_count > long_count:
            final_signal = 'SHORT'
            short_confidences = [c for s, c in zip(signals, confidences) if s == 'SHORT']
            final_confidence = np.mean(short_confidences)
            short_reasons = [r for s, r in zip(signals, reasons) if s == 'SHORT']
            final_reason = ' + '.join(short_reasons)

        return {
            'signal': final_signal,
            'confidence': float(final_confidence),
            'reason': final_reason,
            'indicators': indicators_data,
            'votes': {
                'long': long_count,
                'short': short_count,
                'neutral': len(signals) - long_count - short_count
            }
        }

    @staticmethod
    def calculate_cci(bars: List[HistoricalBar], period: int = 20) -> np.ndarray:
        """
        Calcula CCI (Commodity Channel Index)
        CCI = (Typical Price - SMA(Typical Price)) / (0.015 * Mean Deviation)
        Valores típicos: +100 sobrecompra, -100 sobreventa
        """
        if len(bars) < period:
            return np.zeros(len(bars))

        # Typical Price = (High + Low + Close) / 3
        typical_prices = np.array([(bar.high + bar.low + bar.close) / 3.0 for bar in bars])

        cci = np.zeros(len(bars))

        for i in range(period - 1, len(bars)):
            window = typical_prices[i - period + 1:i + 1]
            sma = np.mean(window)
            mean_deviation = np.mean(np.abs(window - sma))

            if mean_deviation > 0:
                cci[i] = (typical_prices[i] - sma) / (0.015 * mean_deviation)
            else:
                cci[i] = 0.0

        # Rellenar valores iniciales
        cci[:period - 1] = cci[period - 1]

        return cci

    @staticmethod
    def calculate_roc(bars: List[HistoricalBar], period: int = 12) -> np.ndarray:
        """
        Calcula ROC (Rate of Change)
        ROC = ((Close - Close[n periods ago]) / Close[n periods ago]) * 100
        Mide el porcentaje de cambio en el precio
        """
        if len(bars) < period + 1:
            return np.zeros(len(bars))

        closes = np.array([bar.close for bar in bars])
        roc = np.zeros(len(bars))

        for i in range(period, len(bars)):
            if closes[i - period] != 0:
                roc[i] = ((closes[i] - closes[i - period]) / closes[i - period]) * 100.0
            else:
                roc[i] = 0.0

        # Rellenar valores iniciales
        roc[:period] = roc[period]

        return roc

    @staticmethod
    def calculate_williams_r(bars: List[HistoricalBar], period: int = 14) -> np.ndarray:
        """
        Calcula Williams %R
        %R = (Highest High - Close) / (Highest High - Lowest Low) * -100
        Valores: -20 a 0 = sobrecompra, -100 a -80 = sobreventa
        """
        if len(bars) < period:
            return np.zeros(len(bars))

        highs = np.array([bar.high for bar in bars])
        lows = np.array([bar.low for bar in bars])
        closes = np.array([bar.close for bar in bars])

        williams_r = np.zeros(len(bars))

        for i in range(period - 1, len(bars)):
            highest_high = np.max(highs[i - period + 1:i + 1])
            lowest_low = np.min(lows[i - period + 1:i + 1])

            if highest_high != lowest_low:
                williams_r[i] = ((highest_high - closes[i]) / (highest_high - lowest_low)) * -100.0
            else:
                williams_r[i] = -50.0  # Valor neutral

        # Rellenar valores iniciales
        williams_r[:period - 1] = williams_r[period - 1]

        return williams_r
