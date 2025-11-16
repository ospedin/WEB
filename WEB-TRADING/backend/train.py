#!/usr/bin/env python3
"""
Script de entrenamiento del modelo PPO para trading

Uso:
    python train.py --symbols NQ,ES --timesteps 10000000 --save-path models/ppo_trading_model
"""

import argparse
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np

# Agregar path del backend
sys.path.insert(0, str(Path(__file__).parent))

from ml.trading_env import TradingEnv
from ml.ppo_model import create_ppo_model, save_model
from api.topstep import TopstepAPIClient
from api.indicators import TechnicalIndicators
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def download_training_data(api_client: TopstepAPIClient,
                           contract_id: str,
                           days_back: int = 365) -> list:
    """
    Descarga datos históricos para entrenamiento

    Args:
        api_client: Cliente de TopstepX
        contract_id: ID del contrato
        days_back: Días hacia atrás para descargar

    Returns:
        Lista de barras con indicadores calculados
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    logger.info(f"📥 Descargando datos desde {start_date.date()} hasta {end_date.date()}")

    # Descargar barras de 1 minuto
    bars = api_client.get_historical_bars_range(
        contract_id=contract_id,
        start_time=start_date,
        end_time=end_date,
        unit=2,  # Minutos
        unit_number=1
    )

    if not bars:
        raise ValueError("No se descargaron datos históricos")

    logger.info(f"✅ Descargadas {len(bars)} barras")

    # Calcular indicadores
    logger.info("📊 Calculando indicadores técnicos...")

    smi_result = TechnicalIndicators.calculate_smi(bars)
    macd_result = TechnicalIndicators.calculate_macd(bars)
    bb_result = TechnicalIndicators.calculate_bollinger_bands(bars)
    ma_result = TechnicalIndicators.calculate_moving_averages(bars)
    atr = TechnicalIndicators.calculate_atr(bars)

    # Construir datos con indicadores
    bars_with_indicators = []

    for i, bar in enumerate(bars):
        bar_dict = {
            'timestamp': bar.timestamp,
            'open': bar.open,
            'high': bar.high,
            'low': bar.low,
            'close': bar.close,
            'volume': bar.volume,
            'smi': float(smi_result.smi[i]) if i < len(smi_result.smi) else 0.0,
            'smi_signal': float(smi_result.signal[i]) if i < len(smi_result.signal) else 0.0,
            'macd': float(macd_result.macd[i]) if i < len(macd_result.macd) else 0.0,
            'macd_signal': float(macd_result.signal[i]) if i < len(macd_result.signal) else 0.0,
            'macd_histogram': float(macd_result.histogram[i]) if i < len(macd_result.histogram) else 0.0,
            'bb_upper': float(bb_result.upper[i]) if i < len(bb_result.upper) else bar.close,
            'bb_middle': float(bb_result.middle[i]) if i < len(bb_result.middle) else bar.close,
            'bb_lower': float(bb_result.lower[i]) if i < len(bb_result.lower) else bar.close,
            'bb_bandwidth': float(bb_result.bandwidth[i]) if i < len(bb_result.bandwidth) else 0.0,
            'sma_fast': float(ma_result.sma_fast[i]) if i < len(ma_result.sma_fast) else bar.close,
            'sma_slow': float(ma_result.sma_slow[i]) if i < len(ma_result.sma_slow) else bar.close,
            'ema_fast': float(ma_result.ema_fast[i]) if i < len(ma_result.ema_fast) else bar.close,
            'ema_slow': float(ma_result.ema_slow[i]) if i < len(ma_result.ema_slow) else bar.close,
            'atr': float(atr[i]) if i < len(atr) else 0.0,
            # Placeholders para order flow
            'delta_volume': 0.0,
            'cvd': 0.0,
            'dom_imbalance': 0.0,
            'rsi': 50.0,
            'adx': 0.0
        }
        bars_with_indicators.append(bar_dict)

    logger.info("✅ Indicadores calculados")

    return bars_with_indicators

def train_model(bars_data: list,
                tick_size: float,
                tick_value: float,
                timesteps: int = 10_000_000,
                save_path: str = "models/ppo_trading_model",
                tensorboard_log: str = "./logs"):
    """
    Entrena el modelo PPO

    Args:
        bars_data: Datos históricos con indicadores
        tick_size: Tamaño del tick
        tick_value: Valor del tick
        timesteps: Número total de timesteps para entrenar
        save_path: Path donde guardar el modelo
        tensorboard_log: Path para logs de TensorBoard
    """
    logger.info("🤖 Creando entorno de trading...")

    # Crear entorno
    env = TradingEnv(
        bars_data=bars_data,
        initial_capital=50000.0,
        max_positions=8,
        stop_loss_usd=150.0,
        take_profit_ratio=2.5,
        tick_size=tick_size,
        tick_value=tick_value,
        commission_per_trade=2.50,
        lookback_window=100
    )

    logger.info("🧠 Creando modelo PPO...")

    # Crear modelo
    model = create_ppo_model(
        env=env,
        learning_rate=3e-4,
        n_steps=2048,
        batch_size=256,
        n_epochs=10,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.01,
        tensorboard_log=tensorboard_log
    )

    logger.info(f"🚀 Iniciando entrenamiento por {timesteps:,} timesteps...")
    logger.info(f"📝 TensorBoard logs: {tensorboard_log}")
    logger.info(f"💾 Modelo se guardará en: {save_path}")

    # Entrenar
    try:
        model.learn(
            total_timesteps=timesteps,
            callback=None,
            log_interval=10,
            tb_log_name="PPO_Trading",
            reset_num_timesteps=True,
            progress_bar=True
        )

        logger.info("✅ Entrenamiento completado")

        # Guardar modelo
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        save_model(model, save_path)

        # Evaluar modelo
        logger.info("📊 Evaluando modelo...")
        evaluate_model(model, env, n_episodes=10)

    except KeyboardInterrupt:
        logger.warning("⚠️ Entrenamiento interrumpido por usuario")
        # Guardar modelo parcial
        partial_path = f"{save_path}_partial"
        save_model(model, partial_path)
        logger.info(f"💾 Modelo parcial guardado en: {partial_path}")

    except Exception as e:
        logger.error(f"❌ Error durante entrenamiento: {e}")
        raise

def evaluate_model(model, env, n_episodes: int = 10):
    """
    Evalúa el modelo entrenado

    Args:
        model: Modelo PPO entrenado
        env: Entorno de trading
        n_episodes: Número de episodios para evaluar
    """
    episode_rewards = []
    episode_lengths = []
    episode_win_rates = []
    episode_pnls = []

    for episode in range(n_episodes):
        obs, info = env.reset()
        episode_reward = 0
        episode_length = 0
        done = False

        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = env.step(action)
            episode_reward += reward
            episode_length += 1
            done = terminated or truncated

        episode_rewards.append(episode_reward)
        episode_lengths.append(episode_length)
        episode_win_rates.append(info['win_rate'])
        episode_pnls.append(info['total_pnl'])

        logger.info(f"Episodio {episode + 1}/{n_episodes}: "
                   f"Reward={episode_reward:.2f}, "
                   f"P&L=${info['total_pnl']:.2f}, "
                   f"Win Rate={info['win_rate']*100:.1f}%, "
                   f"Trades={info['total_trades']}")

    # Estadísticas finales
    logger.info("\n" + "="*60)
    logger.info("📊 RESULTADOS DE EVALUACIÓN")
    logger.info("="*60)
    logger.info(f"Reward promedio: {np.mean(episode_rewards):.2f} ± {np.std(episode_rewards):.2f}")
    logger.info(f"P&L promedio: ${np.mean(episode_pnls):.2f} ± ${np.std(episode_pnls):.2f}")
    logger.info(f"Win Rate promedio: {np.mean(episode_win_rates)*100:.1f}%")
    logger.info(f"Longitud promedio: {np.mean(episode_lengths):.0f} steps")
    logger.info("="*60 + "\n")

def main():
    parser = argparse.ArgumentParser(description='Entrenar modelo PPO para trading')

    parser.add_argument('--api-key', type=str, required=True, help='TopstepX API Key')
    parser.add_argument('--username', type=str, required=True, help='TopstepX Username')
    parser.add_argument('--symbols', type=str, default='NQ', help='Símbolos separados por coma (ej: NQ,ES,CL)')
    parser.add_argument('--timesteps', type=int, default=10_000_000, help='Número de timesteps para entrenar')
    parser.add_argument('--days-back', type=int, default=365, help='Días históricos para descargar')
    parser.add_argument('--save-path', type=str, default='models/ppo_trading_model', help='Path donde guardar modelo')
    parser.add_argument('--tensorboard-log', type=str, default='./logs', help='Path para logs TensorBoard')

    args = parser.parse_args()

    logger.info("="*60)
    logger.info("🤖 ENTRENAMIENTO DE MODELO PPO PARA TRADING")
    logger.info("="*60)
    logger.info(f"Símbolos: {args.symbols}")
    logger.info(f"Timesteps: {args.timesteps:,}")
    logger.info(f"Días históricos: {args.days_back}")
    logger.info("="*60 + "\n")

    try:
        # Conectar a API
        logger.info("🔌 Conectando a TopstepX API...")
        api_client = TopstepAPIClient(args.api_key, args.username)

        # Buscar contratos
        symbols = [s.strip().upper() for s in args.symbols.split(',')]

        for symbol in symbols:
            logger.info(f"\n{'='*60}")
            logger.info(f"📈 ENTRENANDO CON {symbol}")
            logger.info(f"{'='*60}\n")

            # Buscar contrato
            contracts = api_client.search_contracts(symbol)

            if not contracts:
                logger.warning(f"⚠️ No se encontró contrato para {symbol}, saltando...")
                continue

            contract = contracts[0]
            logger.info(f"✅ Contrato encontrado: {contract.name}")
            logger.info(f"   Tick Size: {contract.tick_size}")
            logger.info(f"   Tick Value: ${contract.tick_value}")

            # Descargar datos
            bars_data = download_training_data(
                api_client=api_client,
                contract_id=contract.id,
                days_back=args.days_back
            )

            # Entrenar modelo
            model_path = f"{args.save_path}_{symbol.lower()}"

            train_model(
                bars_data=bars_data,
                tick_size=contract.tick_size,
                tick_value=contract.tick_value,
                timesteps=args.timesteps,
                save_path=model_path,
                tensorboard_log=args.tensorboard_log
            )

        logger.info("\n" + "="*60)
        logger.info("✅ ENTRENAMIENTO COMPLETADO EXITOSAMENTE")
        logger.info("="*60)
        logger.info("Para visualizar métricas de entrenamiento:")
        logger.info(f"  tensorboard --logdir {args.tensorboard_log}")
        logger.info("="*60 + "\n")

    except Exception as e:
        logger.error(f"\n❌ Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
