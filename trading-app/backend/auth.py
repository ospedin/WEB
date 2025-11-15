"""
Sistema de autenticación de usuarios
"""
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def hash_password(password: str) -> str:
    """Hash de contraseña usando SHA-256 con salt"""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}${pwd_hash}"

def verify_password(password: str, password_hash: str) -> bool:
    """Verificar contraseña"""
    try:
        salt, pwd_hash = password_hash.split('$')
        test_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return test_hash == pwd_hash
    except:
        return False

def generate_verification_code() -> str:
    """Generar código de verificación de 6 dígitos"""
    return str(secrets.randbelow(1000000)).zfill(6)

def send_verification_email(email: str, code: str, purpose: str = "verification") -> bool:
    """
    Enviar email de verificación
    NOTA: Necesitas configurar un servidor SMTP real.
    Por ahora solo registra en logs.
    """
    import logging
    logger = logging.getLogger(__name__)

    if purpose == "verification":
        subject = "Código de Verificación - AI Trading App"
        message = f"""
        Tu código de verificación es: {code}

        Este código expirará en 15 minutos.

        Si no solicitaste este código, ignora este mensaje.
        """
    else:  # recovery
        subject = "Recuperación de Contraseña - AI Trading App"
        message = f"""
        Tu código de recuperación es: {code}

        Este código expirará en 15 minutos.

        Si no solicitaste este código, ignora este mensaje.
        """

    logger.info(f"[EMAIL] To: {email}, Subject: {subject}, Code: {code}")

    # TODO: Implementar envío real de email con SMTP
    # Ejemplo:
    # msg = MIMEMultipart()
    # msg['From'] = "noreply@tradingapp.com"
    # msg['To'] = email
    # msg['Subject'] = subject
    # msg.attach(MIMEText(message, 'plain'))
    #
    # with smtplib.SMTP('smtp.gmail.com', 587) as server:
    #     server.starttls()
    #     server.login("your_email@gmail.com", "your_password")
    #     server.send_message(msg)

    return True

def encrypt_api_key(api_key: str) -> str:
    """
    Encriptar API key (implementación simple)
    Para producción usar cryptography.fernet
    """
    # Por ahora solo encoding base64 reverso (NO ES SEGURO, solo placeholder)
    import base64
    return base64.b64encode(api_key.encode()).decode()

def decrypt_api_key(encrypted_key: str) -> str:
    """Desencriptar API key"""
    import base64
    try:
        return base64.b64decode(encrypted_key.encode()).decode()
    except:
        return ""
