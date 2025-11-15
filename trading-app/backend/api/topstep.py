# Cliente TopstepX API - Basado en Nuevo_smi.py
import logging
import requests
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ContractInfo:
    id: str
    name: str
    description: str
    tick_size: float
    tick_value: float
    active: bool
    symbol_id: str

@dataclass
class HistoricalBar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int

class TopstepAPIClient:
    """Cliente API de TopstepX - Extraído de Nuevo_smi.py"""
    BASE_URL = "https://api.topstepx.com"

    def __init__(self, api_key: str, username: str):
        self.api_key = api_key
        self.username = username
        self.access_token = None
        self.account_id = None
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

        if not self._authenticate():
            raise ConnectionError("Error de autenticación")

    def _authenticate(self) -> bool:
        """Autenticación con TopstepX API"""
        try:
            response = self.session.post(
                f"{self.BASE_URL}/api/Auth/loginKey",
                json={"userName": self.username, "apiKey": self.api_key},
                timeout=10
            )

            if response.status_code == 200:
                auth_data = response.json()
                self.access_token = (
                    auth_data.get('accessToken') or
                    auth_data.get('token') or
                    auth_data.get('access_token')
                )

                if self.access_token:
                    self.session.headers.update({
                        'Authorization': f'Bearer {self.access_token}'
                    })
                    logger.info("✅ Autenticación exitosa")
                    return True

            logger.error(f"❌ Error de autenticación: {response.status_code}")
            return False

        except Exception as e:
            logger.error(f"❌ Error en autenticación: {e}")
            return False

    def get_accounts(self) -> List[Dict]:
        """Obtener cuentas disponibles"""
        try:
            response = self.session.post(
                f"{self.BASE_URL}/api/Account/search",
                json={},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                accounts = data.get('accounts', [])
                return [acc for acc in accounts if acc.get('canTrade') or acc.get('isVisible')]

            return []
        except Exception as e:
            logger.error(f"Error obteniendo cuentas: {e}")
            return []

    def search_contracts(self, search_text: str) -> List[ContractInfo]:
        """Buscar contratos por símbolo"""
        try:
            response = self.session.post(
                f"{self.BASE_URL}/api/Contract/search",
                json={"searchText": search_text, "live": False},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                contracts_raw = data.get('contracts', [])

                contracts = []
                for c in contracts_raw:
                    try:
                        contracts.append(ContractInfo(
                            id=c['id'],
                            name=c['name'],
                            description=c['description'],
                            tick_size=float(c['tickSize']),
                            tick_value=float(c['tickValue']),
                            active=c.get('activeContract', False),
                            symbol_id=c['symbolId']
                        ))
                    except:
                        continue

                logger.info(f"✅ Encontrados {len(contracts)} contratos para '{search_text}'")
                return contracts

            return []
        except Exception as e:
            logger.error(f"Error buscando contratos: {e}")
            return []

    def get_historical_bars_range(self, contract_id: str, start_time: datetime,
                                  end_time: datetime, unit: int = 2,
                                  unit_number: int = 1) -> List[HistoricalBar]:
        """Descarga datos históricos en un rango de fechas

        unit: 1=Seconds, 2=Minutes, 3=Hours, 4=Days
        unit_number: Número de unidades (ej: 1, 5, 15 para minutos)
        """
        all_bars = []
        current_start = start_time
        max_bars_per_request = 5000

        while current_start < end_time:
            current_end = min(
                current_start + timedelta(hours=max_bars_per_request / 60),
                end_time
            )

            try:
                payload = {
                    "contractId": contract_id,
                    "live": False,
                    "startTime": current_start.isoformat(),
                    "endTime": current_end.isoformat(),
                    "unit": unit,
                    "unitNumber": unit_number,
                    "limit": max_bars_per_request,
                    "includePartialBar": True
                }

                response = self.session.post(
                    f"{self.BASE_URL}/api/History/retrieveBars",
                    json=payload,
                    timeout=30
                )

                if response.status_code == 200:
                    data = response.json()

                    if data.get('success', False) and data.get('bars'):
                        for b in data['bars']:
                            try:
                                bar = HistoricalBar(
                                    timestamp=datetime.fromisoformat(
                                        b['t'].replace('Z', '+00:00')
                                    ),
                                    open=float(b['o']),
                                    high=float(b['h']),
                                    low=float(b['l']),
                                    close=float(b['c']),
                                    volume=int(b['v'])
                                )
                                all_bars.append(bar)
                            except:
                                continue

                current_start = current_end

            except Exception as e:
                logger.error(f"Error descargando barras: {e}")
                break

        all_bars.sort(key=lambda x: x.timestamp)
        logger.info(f"✅ Descargadas {len(all_bars)} barras para {contract_id}")

        return all_bars

    def get_account_balance(self) -> Dict:
        """Obtener balance de cuenta"""
        if not self.account_id:
            accounts = self.get_accounts()
            if accounts:
                self.account_id = str(accounts[0]['id'])

        try:
            response = self.session.get(
                f"{self.BASE_URL}/api/Account/{self.account_id}",
                timeout=10
            )

            if response.status_code == 200:
                return response.json()

            return {}
        except Exception as e:
            logger.error(f"Error obteniendo balance: {e}")
            return {}

    def get_current_price(self, contract_id: str) -> Optional[float]:
        """
        Obtener precio actual de un contrato (última barra disponible)

        Args:
            contract_id: ID del contrato

        Returns:
            Precio actual (close de la última barra) o None si no disponible
        """
        try:
            # Obtener la última barra (1 minuto de datos recientes)
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(minutes=5)  # Últimos 5 minutos

            bars = self.get_historical_bars_range(
                contract_id=contract_id,
                start_time=start_time,
                end_time=end_time,
                unit=2,  # Minutos
                unit_number=1
            )

            if bars:
                # Retornar el precio de cierre de la última barra
                return float(bars[-1].close)

            return None

        except Exception as e:
            logger.error(f"Error obteniendo precio actual para {contract_id}: {e}")
            return None

    def get_positions(self) -> List[Dict]:
        """
        Obtener posiciones abiertas desde TopstepX

        Returns:
            Lista de posiciones activas
        """
        if not self.account_id:
            accounts = self.get_accounts()
            if accounts:
                self.account_id = str(accounts[0]['id'])

        try:
            response = self.session.post(
                f"{self.BASE_URL}/api/Position/search",
                json={"accountId": self.account_id},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                positions = data.get('items', []) if isinstance(data, dict) else data

                logger.info(f"Posiciones obtenidas: {len(positions)}")
                return positions

            logger.warning(f"No se pudieron obtener posiciones: {response.status_code}")
            return []

        except Exception as e:
            logger.error(f"Error obteniendo posiciones: {e}")
            return []

    def get_orders(self) -> List[Dict]:
        """
        Obtener órdenes activas desde TopstepX

        Returns:
            Lista de órdenes
        """
        if not self.account_id:
            accounts = self.get_accounts()
            if accounts:
                self.account_id = str(accounts[0]['id'])

        try:
            response = self.session.post(
                f"{self.BASE_URL}/api/Order/search",
                json={"accountId": self.account_id},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                orders = data.get('items', []) if isinstance(data, dict) else data

                logger.info(f"Órdenes obtenidas: {len(orders)}")
                return orders

            return []

        except Exception as e:
            logger.error(f"Error obteniendo órdenes: {e}")
            return []
