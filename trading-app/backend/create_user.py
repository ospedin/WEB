#!/usr/bin/env python3
"""
Script para crear el usuario inicial 'ospedin' con email verificado
"""
import os
import sys
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.models import Base, User
from auth import hash_password

# Configuración de la base de datos
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://ospedin:scouder@localhost:5432/trading_db")

def create_initial_user():
    """Crear usuario ospedin con contraseña prueba19 y email verificado"""

    print("=" * 80)
    print("CREANDO USUARIO INICIAL")
    print("=" * 80)
    print()

    # Crear engine y session
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        # Datos del usuario
        username = "ospedin"
        email = "sguedia660smr@gmail.com"
        password = "prueba19"

        print(f"👤 Usuario: {username}")
        print(f"📧 Email: {email}")
        print(f"🔑 Contraseña: {password}")
        print()

        # Verificar si el usuario ya existe
        existing_user = db.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()

        if existing_user:
            print("⚠️  El usuario ya existe. Actualizando...")

            # Actualizar usuario existente
            existing_user.password_hash = hash_password(password)
            existing_user.email = email
            existing_user.is_verified = True  # Usuario pre-verificado
            existing_user.verification_code = None
            existing_user.verification_code_expiry = None
            existing_user.is_active = True
            existing_user.updated_at = datetime.now()

            db.commit()
            print("✅ Usuario actualizado exitosamente")

        else:
            print("📝 Creando nuevo usuario...")

            # Crear hash de contraseña
            password_hash = hash_password(password)

            # Crear usuario
            user = User(
                username=username,
                email=email,
                password_hash=password_hash,
                is_verified=True,  # Usuario pre-verificado
                verification_code=None,
                verification_code_expiry=None,
                is_active=True
            )

            db.add(user)
            db.commit()
            db.refresh(user)

            print(f"✅ Usuario creado exitosamente con ID: {user.id}")

        print()
        print("=" * 80)
        print("USUARIO LISTO PARA USAR")
        print("=" * 80)
        print()
        print("Puedes iniciar sesión con:")
        print(f"  Username/Email: {username} o {email}")
        print(f"  Contraseña: {password}")
        print()
        print("El usuario está pre-verificado y listo para usar.")
        print()

        return True

    except Exception as e:
        print(f"❌ Error creando usuario: {e}")
        db.rollback()
        return False

    finally:
        db.close()

if __name__ == "__main__":
    success = create_initial_user()
    sys.exit(0 if success else 1)
