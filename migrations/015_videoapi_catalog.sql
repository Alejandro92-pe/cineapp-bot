-- Local review: additive VideoAPI publication; never delete or replace downloads.
BEGIN;
CREATE TABLE IF NOT EXISTS cine_security.videoapi_jobs (LIKE cine_security.catalog_jobs INCLUDING ALL);
ALTER TABLE cine_security.videoapi_jobs ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON cine_security.videoapi_jobs FROM PUBLIC,anon,authenticated;
ALTER TABLE public.contenido ADD COLUMN IF NOT EXISTS videoapi_kind text CHECK(videoapi_kind IN ('pelicula','serie','anime'));
ALTER TABLE public.episodios ADD COLUMN IF NOT EXISTS videoapi_available boolean NOT NULL DEFAULT false;
CREATE OR REPLACE FUNCTION public.importar_videoapi(documento jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE c jsonb:=documento->'contenido'; s jsonb; e jsonb; cid integer; sid integer;
  target integer:=(documento->>'content_id')::integer; old public.contenido%ROWTYPE;
  added integer:=0; changed integer:=0; total integer:=0; existed boolean;
BEGIN
  IF c->>'tipo' NOT IN ('pelicula','serie','anime') OR c->>'tmdb_media' NOT IN ('movie','tv')
    OR (c->>'tmdb_id')::bigint<=0 THEN RAISE EXCEPTION 'Invalid metadata'; END IF;
  PERFORM pg_advisory_xact_lock(hashtextextended('catalog:'||(c->>'tmdb_media')||':'||(c->>'tmdb_id'),0));
  IF (c->>'tipo'='pelicula') <> (c->>'tmdb_media'='movie')
    OR c->>'videoapi_kind' IS DISTINCT FROM c->>'tipo' THEN RAISE EXCEPTION 'Invalid provider identity'; END IF;
  IF (SELECT count(*) FROM public.contenido x WHERE x.tmdb_id=(c->>'tmdb_id')::bigint
      AND CASE WHEN c->>'tmdb_media'='movie' THEN x.tipo='pelicula' OR (x.tipo='biblico' AND x.tmdb_media='movie')
               ELSE x.tipo IN ('serie','anime') OR (x.tipo='biblico' AND x.tmdb_media='tv') END
      AND NOT EXISTS(SELECT 1 FROM public.catalog_aliases a WHERE a.original_id=x.id)) > 1
    THEN RAISE EXCEPTION 'Ambiguous TMDB identity; review existing titles'; END IF;
  SELECT * INTO old FROM public.contenido x WHERE x.tmdb_id=(c->>'tmdb_id')::bigint
      AND CASE WHEN c->>'tmdb_media'='movie' THEN x.tipo='pelicula' OR (x.tipo='biblico' AND x.tmdb_media='movie')
               ELSE x.tipo IN ('serie','anime') OR (x.tipo='biblico' AND x.tmdb_media='tv') END
      AND NOT EXISTS(SELECT 1 FROM public.catalog_aliases a WHERE a.original_id=x.id) FOR UPDATE;
  IF FOUND THEN cid:=old.id; END IF;
  IF cid IS NOT NULL THEN
    IF old.tmdb_media IS NOT NULL AND old.tmdb_media<>c->>'tmdb_media' THEN RAISE EXCEPTION 'Media mismatch'; END IF;
    UPDATE public.contenido SET rating=coalesce((c->>'rating')::double precision,rating),tmdb_id=(c->>'tmdb_id')::bigint,tmdb_media=c->>'tmdb_media',
      imagen_url=coalesce(nullif(imagen_url,''),c->>'imagen_url'),
      sinopsis=coalesce(nullif(sinopsis,''),c->>'sinopsis'),
      genero=coalesce(nullif(genero,''),c->>'genero'),
      trailer_url=coalesce(nullif(trailer_url,''),c->>'trailer_url'),
      backdrop_url=coalesce(nullif(backdrop_url,''),c->>'backdrop_url') WHERE id=cid;
  ELSE
    INSERT INTO public.contenido(tipo,tmdb_id,tmdb_media,titulo,sinopsis,imagen_url,genero,fuente,disponible,destacado,trailer_url,backdrop_url,rating)
    VALUES(c->>'tipo',(c->>'tmdb_id')::bigint,c->>'tmdb_media',c->>'titulo',c->>'sinopsis',c->>'imagen_url',c->>'genero',
      'vimeus',true,false,c->>'trailer_url',c->>'backdrop_url',(c->>'rating')::double precision) RETURNING id INTO cid;
  END IF;
  UPDATE public.contenido SET videoapi_kind=c->>'videoapi_kind',
      fuente=CASE WHEN fuente='okru' THEN fuente ELSE 'vimeus' END,
      playback_unverified=CASE WHEN fuente='okru' THEN playback_unverified ELSE false END,
      "año"=coalesce("año",(c->>'año')::integer) WHERE id=cid;
  FOR s IN SELECT value FROM jsonb_array_elements(documento->'temporadas') LOOP
    INSERT INTO public.temporadas(contenido_id,numero,nombre,poster_url,descripcion,episodios)
    VALUES(cid,(s->>'numero')::integer,s->>'nombre',s->>'poster_url',s->>'descripcion',0)
    ON CONFLICT(contenido_id,numero) DO UPDATE SET numero=excluded.numero RETURNING id INTO sid;
    FOR e IN SELECT value FROM jsonb_array_elements(s->'capitulos') LOOP
      SELECT EXISTS(SELECT 1 FROM public.episodios WHERE temporada_id=sid AND numero=(e->>'numero')::integer) INTO existed;
      INSERT INTO public.episodios(temporada_id,numero,titulo,sinopsis,imagen_url,duracion,disponible,videoapi_available)
      VALUES(sid,(e->>'numero')::integer,e->>'titulo',e->>'sinopsis',e->>'imagen_url',(e->>'duracion')::integer,true,true)
      ON CONFLICT(temporada_id,numero) DO UPDATE SET videoapi_available=true,
        titulo=CASE WHEN public.episodios.titulo='Episodio '||excluded.numero THEN excluded.titulo ELSE public.episodios.titulo END,
        sinopsis=coalesce(nullif(public.episodios.sinopsis,''),excluded.sinopsis),
        imagen_url=coalesce(nullif(public.episodios.imagen_url,''),excluded.imagen_url),
        duracion=coalesce(public.episodios.duracion,excluded.duracion);
      IF existed THEN changed:=changed+1; ELSE added:=added+1; END IF; total:=total+1;
    END LOOP;
    UPDATE public.temporadas SET episodios=(SELECT count(*) FROM public.episodios WHERE temporada_id=sid AND disponible) WHERE id=sid;
  END LOOP;
  -- No retirement, playback, visibility or download updates on existing rows.
  RETURN jsonb_build_object('success',true,'contenido_id',cid,'titulo',(SELECT titulo FROM public.contenido WHERE id=cid),
    'temporadas',jsonb_array_length(documento->'temporadas'),'episodios',total,'creados',added,'actualizados',changed,'retirados',0,
    'provider','videoapi');
END $$;
REVOKE ALL ON FUNCTION public.importar_videoapi(jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.importar_videoapi(jsonb) TO service_role;


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
    PERFORM pg_advisory_xact_lock(hashtextextended('catalog:tv:' || (c->>'tmdb_id'), 0));
    SELECT id INTO cid FROM public.contenido x WHERE tmdb_id=(c->>'tmdb_id')::bigint AND tipo IN ('serie','anime') AND NOT EXISTS(SELECT 1 FROM public.catalog_aliases a WHERE a.original_id=x.id) ORDER BY id LIMIT 1;
    IF cid IS NOT NULL THEN c:=jsonb_set(c,'{tipo}',to_jsonb((SELECT tipo FROM public.contenido WHERE id=cid))); END IF;
    INSERT INTO public.contenido (tipo,tmdb_id,titulo,imagen_url,sinopsis,genero,fuente,disponible,destacado,trailer_url,backdrop_url,rating)
    VALUES (c->>'tipo',(c->>'tmdb_id')::bigint,c->>'titulo',c->>'imagen_url',c->>'sinopsis',c->>'genero','vimeus',true,false,c->>'trailer_url',c->>'backdrop_url',(c->>'rating')::double precision)
    ON CONFLICT (tipo,tmdb_id) WHERE tmdb_id IS NOT NULL DO UPDATE SET fuente=CASE WHEN public.contenido.fuente='okru' THEN 'okru' ELSE 'vimeus' END, rating=COALESCE(EXCLUDED.rating,public.contenido.rating), trailer_url=COALESCE(NULLIF(public.contenido.trailer_url,''),EXCLUDED.trailer_url), backdrop_url=COALESCE(NULLIF(public.contenido.backdrop_url,''),EXCLUDED.backdrop_url)
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
            ON CONFLICT (temporada_id,numero) DO UPDATE SET vimeus_id=EXCLUDED.vimeus_id, disponible=true, provider_download_url=coalesce(EXCLUDED.provider_download_url,public.episodios.provider_download_url),
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
    FROM public.temporadas t WHERE ep.temporada_id=t.id AND t.contenido_id=cid AND ep.disponible AND NOT ep.videoapi_available
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
