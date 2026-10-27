-- LOCAL REVIEW ONLY. Not applied to Supabase.
BEGIN;
ALTER TABLE public.episodios ALTER COLUMN vimeus_id DROP NOT NULL;
ALTER TABLE public.episodios ADD COLUMN IF NOT EXISTS provider_download_url text;
ALTER TABLE public.contenido ADD COLUMN IF NOT EXISTS trailer_url text;
ALTER TABLE public.contenido ADD COLUMN IF NOT EXISTS backdrop_url text;
CREATE OR REPLACE FUNCTION public.importar_vimeus(documento jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
DECLARE
    c jsonb := documento->'contenido'; s jsonb; e jsonb;
    cid integer; sid integer; added integer := 0; updated integer := 0;
    removed integer := 0; total integer := 0; seasons integer := 0;
    existed boolean;
BEGIN
    IF c->>'tipo' NOT IN ('serie','anime') OR (c->>'tmdb_id')::bigint <= 0
       OR jsonb_array_length(documento->'temporadas') = 0 THEN
        RAISE EXCEPTION 'Invalid import document';
    END IF;
    -- Serializes concurrent reimports across all Render workers.
    PERFORM pg_advisory_xact_lock(hashtextextended('vimeus:' || (c->>'tipo') || ':' || (c->>'tmdb_id'), 0));
    INSERT INTO public.contenido (tipo,tmdb_id,titulo,imagen_url,sinopsis,genero,fuente,disponible,destacado,trailer_url,backdrop_url)
    VALUES (c->>'tipo',(c->>'tmdb_id')::bigint,c->>'titulo',c->>'imagen_url',c->>'sinopsis',c->>'genero','vimeus',true,false,c->>'trailer_url',c->>'backdrop_url')
    ON CONFLICT (tipo,tmdb_id) WHERE tmdb_id IS NOT NULL DO UPDATE SET fuente='vimeus', trailer_url=COALESCE(NULLIF(public.contenido.trailer_url,''),EXCLUDED.trailer_url), backdrop_url=COALESCE(NULLIF(public.contenido.backdrop_url,''),EXCLUDED.backdrop_url)
    RETURNING id INTO cid;
    -- Preserve existing editorial metadata, descarga, legacy links and availability.
    FOR s IN SELECT value FROM jsonb_array_elements(documento->'temporadas') LOOP
        INSERT INTO public.temporadas (contenido_id,numero,nombre,poster_url,descripcion,episodios)
        VALUES (cid,(s->>'numero')::integer,s->>'nombre',s->>'poster_url',s->>'descripcion',jsonb_array_length(s->'capitulos'))
        ON CONFLICT (contenido_id,numero) DO UPDATE SET episodios=EXCLUDED.episodios
        RETURNING id INTO sid;
        seasons := seasons + 1;
        FOR e IN SELECT value FROM jsonb_array_elements(s->'capitulos') LOOP
            SELECT EXISTS(SELECT 1 FROM public.episodios WHERE temporada_id=sid AND numero=(e->>'numero')::integer) INTO existed;
            INSERT INTO public.episodios (temporada_id,numero,titulo,sinopsis,imagen_url,duracion,vimeus_id,disponible,provider_download_url)
            VALUES (sid,(e->>'numero')::integer,e->>'titulo',e->>'sinopsis',e->>'imagen_url',(e->>'duracion')::integer,(e->>'vimeus_id')::bigint,true,e->>'provider_download_url')
            ON CONFLICT (temporada_id,numero) DO UPDATE SET vimeus_id=EXCLUDED.vimeus_id, disponible=true, provider_download_url=EXCLUDED.provider_download_url,
                titulo=CASE WHEN EXCLUDED.titulo = 'Episodio ' || EXCLUDED.numero THEN public.episodios.titulo ELSE EXCLUDED.titulo END,
                sinopsis=COALESCE(NULLIF(EXCLUDED.sinopsis,''), public.episodios.sinopsis),
                imagen_url=COALESCE(NULLIF(EXCLUDED.imagen_url,''), public.episodios.imagen_url),
                duracion=COALESCE(EXCLUDED.duracion,public.episodios.duracion), updated_at=now();
            IF existed THEN updated := updated+1; ELSE added := added+1; END IF;
            total := total+1;
        END LOOP;
    END LOOP;
    -- Only a successfully validated full snapshot may retire missing episodes.
    -- Rows remain recoverable and downloads on contenido/temporadas are untouched.
    UPDATE public.episodios ep SET disponible=false, updated_at=now()
    FROM public.temporadas t WHERE ep.temporada_id=t.id AND t.contenido_id=cid AND ep.disponible
    AND NOT EXISTS (
        SELECT 1 FROM jsonb_array_elements(documento->'temporadas') s2,
        LATERAL jsonb_array_elements(s2->'capitulos') e2
        WHERE (s2->>'numero')::integer=t.numero AND (e2->>'numero')::integer=ep.numero
    );
    GET DIAGNOSTICS removed = ROW_COUNT;
    UPDATE public.temporadas t SET episodios=(SELECT count(*) FROM public.episodios ep WHERE ep.temporada_id=t.id AND ep.disponible)
    WHERE t.contenido_id=cid;
    RETURN jsonb_build_object('contenido_id',cid,'titulo',(SELECT titulo FROM public.contenido WHERE id=cid),
        'temporadas',seasons,'episodios',total,'creados',added,'actualizados',updated,'retirados',removed);
END;
$$;
REVOKE ALL ON FUNCTION public.importar_vimeus(jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.importar_vimeus(jsonb) TO service_role;
COMMIT;
