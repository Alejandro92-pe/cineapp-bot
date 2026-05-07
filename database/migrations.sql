-- ============================================================
-- SCRIPT PARA ACTUALIZAR TABLA "usuarios" EN SUPABASE
-- ============================================================
-- 
-- EJECUTA ESTAS QUERIES en el SQL Editor de Supabase
-- https://app.supabase.com/project/[tu-proyecto]/sql/new
--
-- ============================================================

-- 1. Agregar columnas para flags anti-spam
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS notificacion_3dias_enviada BOOLEAN DEFAULT false;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS notificacion_3horas_enviada BOOLEAN DEFAULT false;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS notificacion_vencida_enviada BOOLEAN DEFAULT false;

-- 2. Agregar columna para rastrear la última renovación
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS fecha_ultima_renovacion TIMESTAMP;

-- ============================================================
-- VERIFICACIÓN (ejecuta esto para confirmar que se agregaron)
-- ============================================================

SELECT 
  column_name, 
  data_type, 
  is_nullable
FROM information_schema.columns
WHERE table_name = 'usuarios' 
AND column_name IN (
  'notificacion_3dias_enviada',
  'notificacion_3horas_enviada', 
  'notificacion_vencida_enviada',
  'fecha_ultima_renovacion'
)
ORDER BY ordinal_position;

-- Debería mostrar 4 columnas nuevas tipo BOOLEAN (false) y TIMESTAMP (null)

-- ============================================================
-- ÍNDICES RECOMENDADOS (para mejor performance del CRON)
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_usuarios_membresia_activa 
  ON usuarios(membresia_activa);

CREATE INDEX IF NOT EXISTS idx_usuarios_fecha_vencimiento 
  ON usuarios(fecha_vencimiento);

CREATE INDEX IF NOT EXISTS idx_usuarios_notificacion_3dias 
  ON usuarios(notificacion_3dias_enviada) 
  WHERE membresia_activa = true;

CREATE INDEX IF NOT EXISTS idx_usuarios_notificacion_3horas 
  ON usuarios(notificacion_3horas_enviada) 
  WHERE membresia_activa = true;

-- ============================================================
-- RESET (si necesitas limpiar flags para testing)
-- ============================================================

-- CUIDADO: Esto reseteará TODOS los flags
-- UPDATE usuarios SET 
--   notificacion_3dias_enviada = false,
--   notificacion_3horas_enviada = false,
--   notificacion_vencida_enviada = false
-- WHERE membresia_activa = true;