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
    Enviar email de verificación usando SMTP de Gmail
    """
    import logging
    import os
    logger = logging.getLogger(__name__)

    # Obtener configuración de email desde variables de entorno
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER)

    if purpose == "verification":
        subject = "✅ Código de Verificación - AI Trading App"
        html_message = f"""
        <html>
            <body style="font-family: Arial, sans-serif; background-color: #0a0f1e; color: #ffffff; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background-color: #121826; border-radius: 10px; padding: 30px;">
                    <h1 style="color: #00d4ff; text-align: center;">AI Trading App</h1>
                    <h2 style="color: #ffffff;">Código de Verificación</h2>
                    <p style="font-size: 16px;">Tu código de verificación es:</p>
                    <div style="background-color: #1e2432; border-radius: 5px; padding: 20px; text-align: center; margin: 20px 0;">
                        <span style="font-size: 32px; font-weight: bold; color: #00d4ff; letter-spacing: 5px;">{code}</span>
                    </div>
                    <p style="color: #9ca3af;">Este código expirará en <strong>15 minutos</strong>.</p>
                    <p style="color: #9ca3af;">Si no solicitaste este código, puedes ignorar este mensaje.</p>
                    <hr style="border: 1px solid #1e2432; margin: 30px 0;">
                    <p style="color: #6b7280; font-size: 12px; text-align: center;">
                        © 2025 AI Trading App - Plataforma de Trading con Inteligencia Artificial
                    </p>
                </div>
            </body>
        </html>
        """
    else:  # recovery
        subject = "🔑 Recuperación de Contraseña - AI Trading App"
        html_message = f"""
        <html>
            <body style="font-family: Arial, sans-serif; background-color: #0a0f1e; color: #ffffff; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background-color: #121826; border-radius: 10px; padding: 30px;">
                    <h1 style="color: #00d4ff; text-align: center;">AI Trading App</h1>
                    <h2 style="color: #ffffff;">Recuperación de Contraseña</h2>
                    <p style="font-size: 16px;">Tu código de recuperación es:</p>
                    <div style="background-color: #1e2432; border-radius: 5px; padding: 20px; text-align: center; margin: 20px 0;">
                        <span style="font-size: 32px; font-weight: bold; color: #00d4ff; letter-spacing: 5px;">{code}</span>
                    </div>
                    <p style="color: #9ca3af;">Este código expirará en <strong>15 minutos</strong>.</p>
                    <p style="color: #9ca3af;">Si no solicitaste este código, puedes ignorar este mensaje.</p>
                    <hr style="border: 1px solid #1e2432; margin: 30px 0;">
                    <p style="color: #6b7280; font-size: 12px; text-align: center;">
                        © 2025 AI Trading App - Plataforma de Trading con Inteligencia Artificial
                    </p>
                </div>
            </body>
        </html>
        """

    # Log del intento de envío
    logger.info(f"[EMAIL] Enviando a: {email}, Asunto: {subject}, Código: {code}")

    # Si no hay configuración SMTP, solo registrar en logs (modo desarrollo)
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.warning(f"[EMAIL] Configuración SMTP no encontrada. Email no enviado. Código: {code}")
        logger.info(f"[EMAIL] Para habilitar emails, configure SMTP_USER y SMTP_PASSWORD en variables de entorno")
        return True  # Retornar True para no bloquear el flujo en desarrollo

    # Intentar enviar el email
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = FROM_EMAIL
        msg['To'] = email
        msg['Subject'] = subject

        # Adjuntar HTML
        msg.attach(MIMEText(html_message, 'html'))

        # Enviar email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)

        logger.info(f"[EMAIL] ✅ Email enviado exitosamente a {email}")
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error(f"[EMAIL] ❌ Error de autenticación SMTP. Verifica SMTP_USER y SMTP_PASSWORD")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"[EMAIL] ❌ Error SMTP: {e}")
        return False
    except Exception as e:
        logger.error(f"[EMAIL] ❌ Error enviando email: {e}")
        return False

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
