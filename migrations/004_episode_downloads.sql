-- Local review only. Apply to production only with explicit approval.
BEGIN;
ALTER TABLE public.episodios ADD COLUMN IF NOT EXISTS descarga text;
COMMENT ON COLUMN public.episodios.descarga IS 'Manually maintained episode download URL. Preserved by Vimeus reimports.';
COMMIT;
