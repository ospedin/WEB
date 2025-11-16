#!/usr/bin/env python3
"""
Script para inicializar todas las tablas de la base de datos
"""
import os
import sys
from sqlalchemy import create_engine
from db.models import Base

# Configuración de la base de datos
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://ospedin:scouder@localhost:5432/trading_db")

def init_database():
    """Crear todas las tablas en la base de datos"""

    print("=" * 80)
    print("INICIALIZANDO BASE DE DATOS")
    print("=" * 80)
    print()
    print(f"Database URL: {DATABASE_URL}")
    print()

    try:
        # Crear engine
        engine = create_engine(DATABASE_URL)

        print("Creando todas las tablas...")

        # Crear todas las tablas definidas en los modelos
        Base.metadata.create_all(engine)

        print("✅ Tablas creadas exitosamente")
        print()
        print("Tablas creadas:")
        for table in Base.metadata.sorted_tables:
            print(f"  - {table.name}")

        print()
        print("=" * 80)
        print("BASE DE DATOS INICIALIZADA")
        print("=" * 80)
        print()

        return True

    except Exception as e:
        print(f"❌ Error inicializando base de datos: {e}")
        return False

if __name__ == "__main__":
    success = init_database()
    sys.exit(0 if success else 1)
