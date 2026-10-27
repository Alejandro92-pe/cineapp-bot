BEGIN;
CREATE TABLE IF NOT EXISTS cine_security.catalog_jobs (
    kind varchar(20) NOT NULL, tmdb integer NOT NULL, source text NOT NULL,
    status varchar(16) NOT NULL, attempts integer NOT NULL, ready double precision NOT NULL,
    created_at double precision NOT NULL, note varchar(300), PRIMARY KEY(kind,tmdb)
);
CREATE INDEX IF NOT EXISTS catalog_jobs_pending ON cine_security.catalog_jobs(status,ready,created_at);
CREATE TABLE IF NOT EXISTS cine_security.catalog_settings (key varchar(80) PRIMARY KEY,value double precision NOT NULL);
CREATE TABLE IF NOT EXISTS cine_security.catalog_cache (key varchar(64) PRIMARY KEY,payload text NOT NULL,expires double precision NOT NULL);
CREATE INDEX IF NOT EXISTS catalog_cache_expiry ON cine_security.catalog_cache(expires);
ALTER TABLE cine_security.catalog_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE cine_security.catalog_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE cine_security.catalog_cache ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON cine_security.catalog_jobs,cine_security.catalog_settings,cine_security.catalog_cache FROM PUBLIC,anon,authenticated;

CREATE OR REPLACE FUNCTION public.importar_catalogo_automatico(documento jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE result jsonb; c jsonb := documento->'contenido'; cid integer;
BEGIN
    IF c->>'tipo' IN ('serie','anime') THEN
        result := public.importar_vimeus(documento);
    ELSIF c->>'tipo'='pelicula' AND c->>'tmdb_media'='movie' THEN
        result := public.importar_metadatos(documento);
    ELSE RAISE EXCEPTION 'Unsupported import'; END IF;
    cid := (result->>'contenido_id')::integer;
    UPDATE public.contenido SET
      rating=CASE WHEN jsonb_typeof(c->'rating')='number' AND (c->>'rating')::numeric BETWEEN 0 AND 10 THEN (c->>'rating')::numeric ELSE rating END,
      "año"=CASE WHEN c->>'año' ~ '^[0-9]{4}$' THEN (c->>'año')::integer ELSE "año" END,
      fuente=CASE WHEN fuente='okru' THEN fuente ELSE 'vimeus' END,
      playback_unverified=false
    WHERE id=cid;
    RETURN result;
END $$;
REVOKE ALL ON FUNCTION public.importar_catalogo_automatico(jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.importar_catalogo_automatico(jsonb) TO service_role;
COMMIT;
