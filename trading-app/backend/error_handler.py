"""
Sistema de Manejo de Errores y Notificaciones
Middleware para capturar y registrar todos los errores del backend
"""

import logging
import traceback
import sys
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import asyncio

logger = logging.getLogger(__name__)

class ErrorNotificationMiddleware(BaseHTTPMiddleware):
    """
    Middleware para capturar y notificar errores en tiempo real
    """

    def __init__(self, app, ws_manager=None):
        super().__init__(app)
        self.ws_manager = ws_manager
        self.error_count = 0
        self.errors_log = []
        self.max_log_size = 100

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response

        except HTTPException as exc:
            # Errores HTTP controlados
            await self.log_error(
                error_type="HTTPException",
                message=exc.detail,
                status_code=exc.status_code,
                path=request.url.path,
                method=request.method,
                level="warning"
            )
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail, "type": "http_error"}
            )

        except Exception as exc:
            # Errores no controlados
            error_details = self.format_exception(exc)

            await self.log_error(
                error_type=type(exc).__name__,
                message=str(exc),
                details=error_details,
                path=request.url.path,
                method=request.method,
                level="critical"
            )

            # Retornar respuesta de error
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Error interno del servidor",
                    "type": "internal_error",
                    "error": str(exc),
                    "timestamp": datetime.now().isoformat()
                }
            )

    async def log_error(
        self,
        error_type: str,
        message: str,
        status_code: int = 500,
        details: Optional[Dict] = None,
        path: Optional[str] = None,
        method: Optional[str] = None,
        level: str = "error"
    ):
        """Registrar error y notificar por WebSocket"""

        self.error_count += 1

        error_log = {
            "id": self.error_count,
            "timestamp": datetime.now().isoformat(),
            "type": error_type,
            "message": message,
            "status_code": status_code,
            "path": path,
            "method": method,
            "level": level,
            "details": details or {}
        }

        # Agregar al log
        self.errors_log.append(error_log)
        if len(self.errors_log) > self.max_log_size:
            self.errors_log.pop(0)

        # Log a archivo
        log_message = f"[{level.upper()}] {error_type}: {message} | Path: {path}"

        if level == "critical":
            logger.critical(log_message, extra=error_log)
        elif level == "error":
            logger.error(log_message, extra=error_log)
        elif level == "warning":
            logger.warning(log_message, extra=error_log)
        else:
            logger.info(log_message, extra=error_log)

        # Notificar por WebSocket si está disponible
        if self.ws_manager:
            await self.ws_manager.broadcast({
                "type": "error_notification",
                "data": {
                    "title": f"❌ {error_type}",
                    "message": message,
                    "level": level,
                    "timestamp": error_log["timestamp"],
                    "path": path
                }
            })

    def format_exception(self, exc: Exception) -> Dict[str, Any]:
        """Formatear excepción con traceback completo"""
        exc_type, exc_value, exc_traceback = sys.exc_info()

        tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        tb_text = ''.join(tb_lines)

        return {
            "exception_type": exc_type.__name__ if exc_type else "Unknown",
            "exception_value": str(exc_value),
            "traceback": tb_text,
            "traceback_lines": traceback.format_tb(exc_traceback) if exc_traceback else []
        }

    def get_error_stats(self) -> Dict:
        """Obtener estadísticas de errores"""
        if not self.errors_log:
            return {
                "total_errors": 0,
                "by_type": {},
                "by_level": {},
                "recent_errors": []
            }

        by_type = {}
        by_level = {}

        for error in self.errors_log:
            error_type = error["type"]
            level = error["level"]

            by_type[error_type] = by_type.get(error_type, 0) + 1
            by_level[level] = by_level.get(level, 0) + 1

        return {
            "total_errors": self.error_count,
            "by_type": by_type,
            "by_level": by_level,
            "recent_errors": self.errors_log[-10:]  # Últimos 10
        }


class WebSocketManager:
    """Gestor de conexiones WebSocket para notificaciones"""

    def __init__(self):
        self.connections = []

    def add_connection(self, websocket):
        """Agregar nueva conexión"""
        self.connections.append(websocket)
        logger.info(f"Nueva conexión WebSocket. Total: {len(self.connections)}")

    def remove_connection(self, websocket):
        """Remover conexión"""
        if websocket in self.connections:
            self.connections.remove(websocket)
        logger.info(f"Conexión WebSocket removida. Total: {len(self.connections)}")

    async def broadcast(self, message: Dict):
        """Enviar mensaje a todas las conexiones"""
        if not self.connections:
            return

        disconnected = []

        for ws in self.connections:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.error(f"Error enviando mensaje por WebSocket: {e}")
                disconnected.append(ws)

        # Limpiar conexiones muertas
        for ws in disconnected:
            self.remove_connection(ws)


# Decorador para capturar errores en funciones específicas
def handle_errors(error_type="FunctionError"):
    """
    Decorador para capturar errores en funciones específicas

    Uso:
        @handle_errors("CustomError")
        async def my_function():
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as exc:
                logger.error(f"{error_type} en {func.__name__}: {exc}")
                logger.error(traceback.format_exc())
                raise

        return wrapper
    return decorator


# Función helper para validación de datos
def validate_data(data: Dict, required_fields: list, error_prefix="Validación"):
    """
    Valida que todos los campos requeridos estén presentes

    Args:
        data: Diccionario con datos
        required_fields: Lista de campos requeridos
        error_prefix: Prefijo para el mensaje de error

    Raises:
        HTTPException: Si falta algún campo
    """
    missing = [field for field in required_fields if field not in data]

    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"{error_prefix}: Faltan campos requeridos: {', '.join(missing)}"
        )


# Logger personalizado para errores de base de datos
class DatabaseErrorHandler:
    """Manejador específico para errores de base de datos"""

    @staticmethod
    def handle_db_error(operation: str, error: Exception):
        """Manejar error de base de datos"""

        error_msg = str(error)

        # Errores comunes de PostgreSQL
        if "duplicate key" in error_msg.lower():
            raise HTTPException(
                status_code=409,
                detail=f"Conflicto: El registro ya existe ({operation})"
            )

        elif "foreign key" in error_msg.lower():
            raise HTTPException(
                status_code=400,
                detail=f"Error de relación: Referencia inválida ({operation})"
            )

        elif "not-null" in error_msg.lower() or "null value" in error_msg.lower():
            raise HTTPException(
                status_code=400,
                detail=f"Campo requerido faltante ({operation})"
            )

        elif "connection" in error_msg.lower():
            raise HTTPException(
                status_code=503,
                detail="Servicio de base de datos no disponible"
            )

        else:
            # Error genérico
            logger.error(f"Error de base de datos en {operation}: {error}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=f"Error de base de datos: {operation}"
            )


# Logger personalizado para errores de API externa
class ExternalAPIErrorHandler:
    """Manejador específico para errores de APIs externas (TopstepX)"""

    @staticmethod
    def handle_api_error(api_name: str, error: Exception, operation: str = ""):
        """Manejar error de API externa"""

        error_msg = str(error)

        if "401" in error_msg or "unauthorized" in error_msg.lower():
            raise HTTPException(
                status_code=401,
                detail=f"{api_name}: Credenciales inválidas o expiradas"
            )

        elif "403" in error_msg or "forbidden" in error_msg.lower():
            raise HTTPException(
                status_code=403,
                detail=f"{api_name}: Acceso denegado"
            )

        elif "404" in error_msg or "not found" in error_msg.lower():
            raise HTTPException(
                status_code=404,
                detail=f"{api_name}: Recurso no encontrado"
            )

        elif "timeout" in error_msg.lower():
            raise HTTPException(
                status_code=504,
                detail=f"{api_name}: Timeout en la conexión"
            )

        elif "connection" in error_msg.lower():
            raise HTTPException(
                status_code=503,
                detail=f"{api_name}: Servicio no disponible"
            )

        else:
            logger.error(f"Error de {api_name} en {operation}: {error}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=502,
                detail=f"Error en servicio externo: {api_name}"
            )
