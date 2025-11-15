"""
Endpoints adicionales para autenticación de usuarios, estrategias y gestión de contratos
Este archivo debe integrarse en main.py
"""
from fastapi import HTTPException
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime, timedelta

# ============================================================================
# MODELOS PYDANTIC
# ============================================================================

class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)

class UserLoginRequest(BaseModel):
    username_or_email: str
    password: str

class VerifyCodeRequest(BaseModel):
    email: EmailStr
    code: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str
    new_password: str = Field(..., min_length=8)

class StrategyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None

    # Modelo RL
    use_model: bool = False
    model_path: Optional[str] = None

    # Indicadores habilitados
    use_smi: bool = False
    use_macd: bool = False
    use_bb: bool = False
    use_ma: bool = False
    use_stoch_rsi: bool = False
    use_vwap: bool = False
    use_supertrend: bool = False
    use_kdj: bool = False
    use_cci: bool = False
    use_roc: bool = False
    use_atr: bool = False
    use_wr: bool = False

    # Parámetros (todos opcionales, usan defaults de la tabla)
    smi_k_length: Optional[int] = None
    smi_d_smoothing: Optional[int] = None
    smi_signal_period: Optional[int] = None

    macd_fast_period: Optional[int] = None
    macd_slow_period: Optional[int] = None
    macd_signal_period: Optional[int] = None

    bb_period: Optional[int] = None
    bb_std_dev: Optional[float] = None

    ma_sma_fast: Optional[int] = None
    ma_sma_slow: Optional[int] = None
    ma_ema_fast: Optional[int] = None
    ma_ema_slow: Optional[int] = None

    stoch_rsi_period: Optional[int] = None
    stoch_rsi_stoch_period: Optional[int] = None
    stoch_rsi_k_smooth: Optional[int] = None
    stoch_rsi_d_smooth: Optional[int] = None

    vwap_std_dev: Optional[float] = None

    supertrend_period: Optional[int] = None
    supertrend_multiplier: Optional[float] = None

    kdj_period: Optional[int] = None
    kdj_k_smooth: Optional[int] = None
    kdj_d_smooth: Optional[int] = None

    cci_period: Optional[int] = None
    roc_period: Optional[int] = None
    atr_period: Optional[int] = None
    wr_period: Optional[int] = None

    # Gestión de riesgo
    stop_loss_usd: Optional[float] = None
    take_profit_ratio: Optional[float] = None
    timeframe_minutes: Optional[int] = None
    min_confidence: Optional[float] = None

class ContractAddRequest(BaseModel):
    contract_id: str
    strategy_id: Optional[int] = None

# ============================================================================
# ENDPOINTS PARA MAIN.PY
# ============================================================================

"""
# ========== AUTENTICACIÓN DE USUARIOS ==========

@app.post("/api/users/register")
async def register_user(request: UserRegisterRequest):
    '''Registrar nuevo usuario'''
    from auth import hash_password, generate_verification_code, send_verification_email
    from db.models import User

    db = get_db()
    try:
        # Verificar si el usuario ya existe
        existing = db.query(User).filter(
            (User.username == request.username) | (User.email == request.email)
        ).first()

        if existing:
            raise HTTPException(status_code=400, detail="Usuario o email ya existe")

        # Crear usuario
        password_hash = hash_password(request.password)
        verification_code = generate_verification_code()
        expiry = datetime.now() + timedelta(minutes=15)

        user = User(
            username=request.username,
            email=request.email,
            password_hash=password_hash,
            verification_code=verification_code,
            verification_code_expiry=expiry,
            is_verified=False
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        # Enviar email de verificación
        send_verification_email(request.email, verification_code, "verification")

        return {
            "success": True,
            "message": "Usuario registrado. Verifica tu email con el código enviado.",
            "user_id": user.id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registrando usuario: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.post("/api/users/verify")
async def verify_user(request: VerifyCodeRequest):
    '''Verificar código de email'''
    from db.models import User

    db = get_db()
    try:
        user = db.query(User).filter(User.email == request.email).first()

        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        if user.is_verified:
            return {"success": True, "message": "Usuario ya verificado"}

        if not user.verification_code or user.verification_code != request.code:
            raise HTTPException(status_code=400, detail="Código inválido")

        if user.verification_code_expiry < datetime.now():
            raise HTTPException(status_code=400, detail="Código expirado")

        # Verificar usuario
        user.is_verified = True
        user.verification_code = None
        user.verification_code_expiry = None
        db.commit()

        return {"success": True, "message": "Usuario verificado exitosamente"}

    finally:
        db.close()

@app.post("/api/users/login")
async def login_user(request: UserLoginRequest):
    '''Login de usuario'''
    from auth import verify_password
    from db.models import User

    db = get_db()
    try:
        # Buscar usuario por username o email
        user = db.query(User).filter(
            (User.username == request.username_or_email) |
            (User.email == request.username_or_email)
        ).first()

        if not user:
            raise HTTPException(status_code=401, detail="Credenciales inválidas")

        if not verify_password(request.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Credenciales inválidas")

        if not user.is_verified:
            raise HTTPException(status_code=403, detail="Email no verificado")

        if not user.is_active:
            raise HTTPException(status_code=403, detail="Usuario desactivado")

        # Actualizar último login
        user.last_login = datetime.now()
        db.commit()

        # En producción usar JWT tokens
        return {
            "success": True,
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "message": "Login exitoso"
        }

    finally:
        db.close()

@app.post("/api/users/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    '''Enviar código de recuperación de contraseña'''
    from auth import generate_verification_code, send_verification_email
    from db.models import User

    db = get_db()
    try:
        user = db.query(User).filter(User.email == request.email).first()

        if not user:
            # Por seguridad, no revelar si el email existe
            return {"success": True, "message": "Si el email existe, se envió un código de recuperación"}

        # Generar código de recuperación
        reset_code = generate_verification_code()
        expiry = datetime.now() + timedelta(minutes=15)

        user.reset_code = reset_code
        user.reset_code_expiry = expiry
        db.commit()

        # Enviar email
        send_verification_email(request.email, reset_code, "recovery")

        return {"success": True, "message": "Código de recuperación enviado"}

    finally:
        db.close()

@app.post("/api/users/reset-password")
async def reset_password(request: ResetPasswordRequest):
    '''Resetear contraseña con código'''
    from auth import hash_password
    from db.models import User

    db = get_db()
    try:
        user = db.query(User).filter(User.email == request.email).first()

        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        if not user.reset_code or user.reset_code != request.code:
            raise HTTPException(status_code=400, detail="Código inválido")

        if user.reset_code_expiry < datetime.now():
            raise HTTPException(status_code=400, detail="Código expirado")

        # Cambiar contraseña
        user.password_hash = hash_password(request.new_password)
        user.reset_code = None
        user.reset_code_expiry = None
        db.commit()

        return {"success": True, "message": "Contraseña actualizada"}

    finally:
        db.close()

@app.get("/api/users/me")
async def get_current_user(user_id: int):
    '''Obtener información del usuario actual'''
    from db.models import User

    db = get_db()
    try:
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_verified": user.is_verified,
            "created_at": user.created_at.isoformat(),
            "last_login": user.last_login.isoformat() if user.last_login else None
        }

    finally:
        db.close()

# ========== ESTRATEGIAS ==========

@app.post("/api/strategies")
async def create_strategy(strategy: StrategyCreateRequest, user_id: int):
    '''Crear nueva estrategia'''
    from db.models import Strategy

    db = get_db()
    try:
        db_strategy = Strategy(
            user_id=user_id,
            name=strategy.name,
            description=strategy.description,
            **strategy.dict(exclude={'name', 'description'})
        )

        db.add(db_strategy)
        db.commit()
        db.refresh(db_strategy)

        return {"success": True, "strategy_id": db_strategy.id, "message": "Estrategia creada"}

    finally:
        db.close()

@app.get("/api/strategies")
async def get_strategies(user_id: int):
    '''Obtener estrategias del usuario'''
    from db.models import Strategy

    db = get_db()
    try:
        strategies = db.query(Strategy).filter(
            Strategy.user_id == user_id,
            Strategy.is_active == True
        ).all()

        return {
            "strategies": [
                {
                    "id": s.id,
                    "name": s.name,
                    "description": s.description,
                    "created_at": s.created_at.isoformat(),
                    "updated_at": s.updated_at.isoformat()
                }
                for s in strategies
            ]
        }

    finally:
        db.close()

@app.get("/api/strategies/{strategy_id}")
async def get_strategy(strategy_id: int, user_id: int):
    '''Obtener detalles de una estrategia'''
    from db.models import Strategy

    db = get_db()
    try:
        strategy = db.query(Strategy).filter(
            Strategy.id == strategy_id,
            Strategy.user_id == user_id
        ).first()

        if not strategy:
            raise HTTPException(status_code=404, detail="Estrategia no encontrada")

        # Retornar todos los campos
        return {
            "id": strategy.id,
            "name": strategy.name,
            "description": strategy.description,
            "use_model": strategy.use_model,
            "model_path": strategy.model_path,
            "indicators": {
                "smi": strategy.use_smi,
                "macd": strategy.use_macd,
                "bb": strategy.use_bb,
                "ma": strategy.use_ma,
                "stoch_rsi": strategy.use_stoch_rsi,
                "vwap": strategy.use_vwap,
                "supertrend": strategy.use_supertrend,
                "kdj": strategy.use_kdj,
                "cci": strategy.use_cci,
                "roc": strategy.use_roc,
                "atr": strategy.use_atr,
                "wr": strategy.use_wr
            },
            "parameters": {
                "smi": {
                    "k_length": strategy.smi_k_length,
                    "d_smoothing": strategy.smi_d_smoothing,
                    "signal_period": strategy.smi_signal_period
                },
                "macd": {
                    "fast_period": strategy.macd_fast_period,
                    "slow_period": strategy.macd_slow_period,
                    "signal_period": strategy.macd_signal_period
                },
                "bb": {
                    "period": strategy.bb_period,
                    "std_dev": strategy.bb_std_dev
                },
                "ma": {
                    "sma_fast": strategy.ma_sma_fast,
                    "sma_slow": strategy.ma_sma_slow,
                    "ema_fast": strategy.ma_ema_fast,
                    "ema_slow": strategy.ma_ema_slow
                },
                "stoch_rsi": {
                    "period": strategy.stoch_rsi_period,
                    "stoch_period": strategy.stoch_rsi_stoch_period,
                    "k_smooth": strategy.stoch_rsi_k_smooth,
                    "d_smooth": strategy.stoch_rsi_d_smooth
                },
                "vwap": {"std_dev": strategy.vwap_std_dev},
                "supertrend": {
                    "period": strategy.supertrend_period,
                    "multiplier": strategy.supertrend_multiplier
                },
                "kdj": {
                    "period": strategy.kdj_period,
                    "k_smooth": strategy.kdj_k_smooth,
                    "d_smooth": strategy.kdj_d_smooth
                },
                "cci": {"period": strategy.cci_period},
                "roc": {"period": strategy.roc_period},
                "atr": {"period": strategy.atr_period},
                "wr": {"period": strategy.wr_period}
            },
            "risk_management": {
                "stop_loss_usd": strategy.stop_loss_usd,
                "take_profit_ratio": strategy.take_profit_ratio,
                "timeframe_minutes": strategy.timeframe_minutes,
                "min_confidence": strategy.min_confidence
            }
        }

    finally:
        db.close()

@app.put("/api/strategies/{strategy_id}")
async def update_strategy(strategy_id: int, strategy: StrategyCreateRequest, user_id: int):
    '''Actualizar estrategia'''
    from db.models import Strategy

    db = get_db()
    try:
        db_strategy = db.query(Strategy).filter(
            Strategy.id == strategy_id,
            Strategy.user_id == user_id
        ).first()

        if not db_strategy:
            raise HTTPException(status_code=404, detail="Estrategia no encontrada")

        # Actualizar campos
        for key, value in strategy.dict().items():
            if value is not None:
                setattr(db_strategy, key, value)

        db.commit()

        return {"success": True, "message": "Estrategia actualizada"}

    finally:
        db.close()

@app.delete("/api/strategies/{strategy_id}")
async def delete_strategy(strategy_id: int, user_id: int):
    '''Eliminar estrategia (soft delete)'''
    from db.models import Strategy

    db = get_db()
    try:
        strategy = db.query(Strategy).filter(
            Strategy.id == strategy_id,
            Strategy.user_id == user_id
        ).first()

        if not strategy:
            raise HTTPException(status_code=404, detail="Estrategia no encontrada")

        strategy.is_active = False
        db.commit()

        return {"success": True, "message": "Estrategia eliminada"}

    finally:
        db.close()

# ========== BALANCE DE CUENTA ==========

@app.get("/api/account/balance")
async def get_account_balance():
    '''Obtener balance de cuenta desde TopstepX'''
    if not topstep_client:
        raise HTTPException(status_code=503, detail="TopstepX API no disponible")

    try:
        balance_data = topstep_client.get_account_balance()

        return {
            "balance": balance_data.get("balance", 0.0),
            "equity": balance_data.get("equity", 0.0),
            "available": balance_data.get("available", 0.0),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error obteniendo balance: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ========== GESTIÓN DE CONTRATOS ==========

@app.delete("/api/contracts/{contract_id}")
async def delete_contract(contract_id: str):
    '''Eliminar contrato (soft delete)'''
    from db.models import Contract as ContractModel

    db = get_db()
    try:
        contract = db.query(ContractModel).filter(ContractModel.id == contract_id).first()

        if not contract:
            raise HTTPException(status_code=404, detail="Contrato no encontrado")

        contract.active = False
        db.commit()

        return {"success": True, "message": "Contrato eliminado"}

    finally:
        db.close()

@app.post("/api/contracts/{contract_id}/add")
async def add_contract_to_bot(contract_id: str, request: ContractAddRequest):
    '''Añadir contrato al bot con estrategia opcional'''
    from db.models import Contract as ContractModel, ContractBotConfig

    db = get_db()
    try:
        # Verificar que el contrato existe
        contract = db.query(ContractModel).filter(ContractModel.id == contract_id).first()

        if not contract:
            raise HTTPException(status_code=404, detail="Contrato no encontrado")

        # Activar contrato si estaba desactivado
        contract.active = True

        # Si se proporciona una estrategia, crear configuración del bot
        if request.strategy_id:
            from db.models import Strategy

            strategy = db.query(Strategy).filter(Strategy.id == request.strategy_id).first()

            if not strategy:
                raise HTTPException(status_code=404, detail="Estrategia no encontrada")

            # Crear o actualizar configuración del bot para este contrato
            bot_config = db.query(ContractBotConfig).filter(
                ContractBotConfig.contract_id == contract_id
            ).first()

            if not bot_config:
                bot_config = ContractBotConfig(
                    contract_id=contract_id,
                    name=f"Config for {contract.name}",
                    stop_loss_usd=strategy.stop_loss_usd,
                    take_profit_ratio=strategy.take_profit_ratio,
                    timeframe_minutes=strategy.timeframe_minutes,
                    min_confidence=strategy.min_confidence
                )
                db.add(bot_config)

        db.commit()

        return {"success": True, "message": "Contrato añadido al bot"}

    finally:
        db.close()
"""
