-- Migración: Agregar columna timeframe_minutes a historical_bars
-- Fecha: 2025-11-16

-- Agregar la columna timeframe_minutes con valor por defecto
ALTER TABLE historical_bars
ADD COLUMN IF NOT EXISTS timeframe_minutes INTEGER NOT NULL DEFAULT 1;

-- Actualizar la clave primaria para incluir timeframe_minutes
-- Primero, eliminar la restricción de clave primaria existente
ALTER TABLE historical_bars DROP CONSTRAINT IF EXISTS historical_bars_pkey;

-- Crear nueva clave primaria que incluya timeframe_minutes
ALTER TABLE historical_bars
ADD CONSTRAINT historical_bars_pkey PRIMARY KEY (time, contract_id, timeframe_minutes);

-- Crear índice para búsquedas por timeframe
CREATE INDEX IF NOT EXISTS idx_historical_bars_timeframe
ON historical_bars (contract_id, timeframe_minutes, time);

-- Verificar los cambios
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'historical_bars'
ORDER BY ordinal_position;
