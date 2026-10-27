-- Prepared only. Not applied in production in phase 12.
-- Playback URLs are private: only the entitlement-checked route releases a canonical embed.
ALTER TABLE public.contenido ADD COLUMN IF NOT EXISTS playback_url text;
ALTER TABLE public.episodios ADD COLUMN IF NOT EXISTS playback_url text;
