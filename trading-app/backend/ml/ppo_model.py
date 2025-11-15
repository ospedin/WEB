# Modelo PPO para Trading con Stable-Baselines3
import torch
import torch.nn as nn
from stable_baselines3 import PPO
from stable_baselines3.common.policies import ActorCriticPolicy
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
from typing import Dict
import gymnasium as gym

class TradingFeatureExtractor(BaseFeaturesExtractor):
    """
    Feature Extractor custom con LSTM para capturar patrones temporales

    Arquitectura: Input(45) -> LSTM(256) -> LSTM(512) -> LSTM(256) -> Output(256)
    """

    def __init__(self, observation_space: gym.spaces.Box, features_dim: int = 256):
        super().__init__(observation_space, features_dim)

        n_input_features = observation_space.shape[0]

        # Red LSTM multicapa
        self.lstm1 = nn.LSTM(
            input_size=n_input_features,
            hidden_size=256,
            num_layers=1,
            batch_first=True,
            dropout=0.0
        )

        self.lstm2 = nn.LSTM(
            input_size=256,
            hidden_size=512,
            num_layers=1,
            batch_first=True,
            dropout=0.2
        )

        self.lstm3 = nn.LSTM(
            input_size=512,
            hidden_size=256,
            num_layers=1,
            batch_first=True,
            dropout=0.1
        )

        # Capas fully connected
        self.fc = nn.Sequential(
            nn.Linear(256, features_dim),
            nn.LayerNorm(features_dim),
            nn.ReLU(),
            nn.Dropout(0.1)
        )

    def forward(self, observations: torch.Tensor) -> torch.Tensor:
        # observations shape: (batch_size, n_features)
        # Reshape para LSTM: (batch_size, sequence_length=1, n_features)
        x = observations.unsqueeze(1)

        # Primera capa LSTM
        x, _ = self.lstm1(x)

        # Segunda capa LSTM
        x, _ = self.lstm2(x)

        # Tercera capa LSTM
        x, (h_n, _) = self.lstm3(x)

        # Tomar última salida
        x = h_n[-1]

        # FC layers
        x = self.fc(x)

        return x

class TradingActorCriticPolicy(ActorCriticPolicy):
    """
    Policy custom Actor-Critic para trading
    Usa el TradingFeatureExtractor con LSTM
    """

    def __init__(self, *args, **kwargs):
        # Forzar uso del feature extractor custom
        super().__init__(
            *args,
            **kwargs,
            features_extractor_class=TradingFeatureExtractor,
            features_extractor_kwargs=dict(features_dim=256),
        )

def create_ppo_model(env,
                     learning_rate: float = 3e-4,
                     n_steps: int = 2048,
                     batch_size: int = 256,
                     n_epochs: int = 10,
                     gamma: float = 0.99,
                     gae_lambda: float = 0.95,
                     clip_range: float = 0.2,
                     ent_coef: float = 0.01,
                     vf_coef: float = 0.5,
                     max_grad_norm: float = 0.5,
                     tensorboard_log: str = "./logs",
                     device: str = "auto") -> PPO:
    """
    Crea modelo PPO optimizado para trading

    Args:
        env: Entorno de trading (TradingEnv)
        learning_rate: Learning rate inicial
        n_steps: Número de steps antes de actualizar
        batch_size: Tamaño de batch para entrenamiento
        n_epochs: Número de epochs por actualización
        gamma: Factor de descuento
        gae_lambda: Lambda para GAE
        clip_range: Rango de clipping PPO
        ent_coef: Coeficiente de entropía (exploración)
        vf_coef: Coeficiente de value function
        max_grad_norm: Max norm para gradient clipping
        tensorboard_log: Path para logs de TensorBoard
        device: Device para entrenamiento (cpu/cuda/auto)

    Returns:
        Modelo PPO configurado
    """

    # Configuración de política
    policy_kwargs = dict(
        features_extractor_class=TradingFeatureExtractor,
        features_extractor_kwargs=dict(features_dim=256),
        net_arch=dict(
            pi=[512, 512, 256],  # Actor network
            vf=[512, 512, 256]   # Critic network
        ),
        activation_fn=nn.ReLU,
        normalize_images=False
    )

    model = PPO(
        policy=TradingActorCriticPolicy,
        env=env,
        learning_rate=learning_rate,
        n_steps=n_steps,
        batch_size=batch_size,
        n_epochs=n_epochs,
        gamma=gamma,
        gae_lambda=gae_lambda,
        clip_range=clip_range,
        clip_range_vf=None,
        normalize_advantage=True,
        ent_coef=ent_coef,
        vf_coef=vf_coef,
        max_grad_norm=max_grad_norm,
        use_sde=False,
        sde_sample_freq=-1,
        target_kl=None,
        tensorboard_log=tensorboard_log,
        policy_kwargs=policy_kwargs,
        verbose=1,
        seed=None,
        device=device
    )

    return model

def load_trained_model(model_path: str, env) -> PPO:
    """
    Carga un modelo PPO ya entrenado

    Args:
        model_path: Path al archivo .zip del modelo
        env: Entorno de trading

    Returns:
        Modelo PPO cargado
    """
    model = PPO.load(model_path, env=env)
    return model

def save_model(model: PPO, save_path: str):
    """
    Guarda modelo PPO

    Args:
        model: Modelo a guardar
        save_path: Path donde guardar
    """
    model.save(save_path)
    print(f"✅ Modelo guardado en: {save_path}")

class TradingCallback:
    """
    Callback para tracking durante entrenamiento
    Guarda métricas en base de datos
    """

    def __init__(self, db_session=None):
        self.db_session = db_session
        self.episode_rewards = []
        self.episode_lengths = []

    def on_step(self, locals_dict, globals_dict):
        """Llamado en cada step"""
        # Aquí se puede loggear a DB
        pass

    def on_episode_end(self, episode_num, episode_reward, episode_length, info):
        """Llamado al final de cada episodio"""
        self.episode_rewards.append(episode_reward)
        self.episode_lengths.append(episode_length)

        print(f"Episode {episode_num}: Reward={episode_reward:.2f}, "
              f"Length={episode_length}, Win Rate={info.get('win_rate', 0)*100:.1f}%")

        # Guardar en DB si está disponible
        if self.db_session:
            # Aquí se guardaría en la tabla rl_training_episodes
            pass
