-- Preserve links to consolidated titles without deleting their original rows.
BEGIN;
ALTER TABLE public.contenido ADD COLUMN IF NOT EXISTS playback_unverified boolean NOT NULL DEFAULT false;
CREATE TABLE IF NOT EXISTS public.catalog_aliases (
    original_id integer PRIMARY KEY REFERENCES public.contenido(id),
    content_id integer NOT NULL REFERENCES public.contenido(id),
    start_season integer NOT NULL CHECK (start_season >= 0),
    CHECK (original_id <> content_id)
);
ALTER TABLE public.catalog_aliases ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.catalog_aliases FROM PUBLIC, anon, authenticated;
GRANT ALL ON public.catalog_aliases TO service_role;
COMMIT;
