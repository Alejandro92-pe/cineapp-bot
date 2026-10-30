-- LOCAL REVIEW ONLY: requires backup and separate approval before production.
-- One atomic publication; incremental row writes, unchanged scheduling/API inputs.
BEGIN;

CREATE OR REPLACE FUNCTION cine_security.merge_catalog_episodes(cid integer, seasons jsonb, mode text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE payload jsonb; total integer; added integer; changed integer; removed integer := 0;
BEGIN
  IF mode IS NULL OR mode NOT IN ('videoapi','vimeus','metadata')
     OR jsonb_typeof(seasons) IS DISTINCT FROM 'array' OR jsonb_array_length(seasons)>100 THEN
    RAISE EXCEPTION 'Invalid episode publication';
  END IF;
  IF jsonb_array_length(seasons)=0 THEN
    RETURN jsonb_build_object('episodios',0,'creados',0,'actualizados',0,'sin_cambios',0,'retirados',0);
  END IF;
  IF EXISTS (SELECT 1 FROM jsonb_to_recordset(seasons) AS s(numero integer,capitulos jsonb)
             WHERE numero IS NULL OR numero<0 OR jsonb_typeof(capitulos) IS DISTINCT FROM 'array')
     OR (SELECT count(*)<>count(DISTINCT numero) FROM jsonb_to_recordset(seasons) AS s(numero integer)) THEN
    RAISE EXCEPTION 'Invalid or duplicate seasons';
  END IF;
  SELECT coalesce(jsonb_agg(e.value || jsonb_build_object('season',s.numero)),'[]'::jsonb)
    INTO payload FROM jsonb_to_recordset(seasons) AS s(numero integer,capitulos jsonb)
    CROSS JOIN LATERAL jsonb_array_elements(s.capitulos) e;
  total := jsonb_array_length(payload);
  IF total>5000 OR (SELECT count(*)<>count(DISTINCT (season,numero)) FROM
        jsonb_to_recordset(payload) AS e(season integer,numero integer))
     OR EXISTS (SELECT 1 FROM jsonb_to_recordset(payload) AS e(numero integer,titulo text,sinopsis text,imagen_url text,duracion integer,vimeus_id bigint)
        WHERE numero IS NULL OR numero<1 OR titulo IS NULL OR sinopsis IS NULL OR imagen_url IS NULL
           OR duracion<=0 OR vimeus_id<=0) THEN
    RAISE EXCEPTION 'Invalid, duplicate or excessive episodes';
  END IF;
  -- Missing seasons only: no dummy UPDATE, no sequence consumption on reimport.
  INSERT INTO public.temporadas(contenido_id,numero,nombre,poster_url,descripcion,episodios)
    SELECT cid,s.numero,s.nombre,s.poster_url,s.descripcion,0
    FROM jsonb_to_recordset(seasons) AS s(numero integer,nombre text,poster_url text,descripcion text)
    WHERE NOT EXISTS(SELECT 1 FROM public.temporadas t WHERE t.contenido_id=cid AND t.numero=s.numero)
    ON CONFLICT(contenido_id,numero) DO NOTHING;

  -- Compute the desired values before filtering; never touch manual URLs.
  WITH incoming AS MATERIALIZED (
    SELECT t.id AS sid,e.* FROM jsonb_to_recordset(payload) AS e(season integer,numero integer,
      titulo text,sinopsis text,imagen_url text,duracion integer,vimeus_id bigint,provider_download_url text)
    JOIN public.temporadas t ON t.contenido_id=cid AND t.numero=e.season
  ), desired AS MATERIALIZED (
    SELECT ep.id,
      CASE WHEN mode='vimeus' THEN CASE WHEN i.titulo='Episodio '||i.numero THEN ep.titulo ELSE i.titulo END
           WHEN ep.titulo='Episodio '||i.numero THEN i.titulo ELSE ep.titulo END AS titulo,
      CASE WHEN mode='vimeus' THEN coalesce(nullif(i.sinopsis,''),ep.sinopsis)
           ELSE coalesce(nullif(ep.sinopsis,''),i.sinopsis) END AS sinopsis,
      CASE WHEN mode='vimeus' THEN coalesce(nullif(i.imagen_url,''),ep.imagen_url)
           ELSE coalesce(nullif(ep.imagen_url,''),i.imagen_url) END AS imagen_url,
      CASE WHEN mode='vimeus' THEN coalesce(i.duracion,ep.duracion) ELSE coalesce(ep.duracion,i.duracion) END AS duracion,
      CASE WHEN mode='vimeus' THEN coalesce(i.vimeus_id,ep.vimeus_id) ELSE ep.vimeus_id END AS vimeus_id,
      CASE WHEN mode='vimeus' THEN coalesce(nullif(i.provider_download_url,''),ep.provider_download_url) ELSE ep.provider_download_url END AS provider_download_url,
      CASE WHEN mode='vimeus' THEN true ELSE ep.disponible END AS disponible,
      ep.videoapi_available OR mode='videoapi' AS videoapi_available
    FROM incoming i JOIN public.episodios ep ON ep.temporada_id=i.sid AND ep.numero=i.numero
  )
  UPDATE public.episodios ep SET titulo=d.titulo,sinopsis=d.sinopsis,imagen_url=d.imagen_url,
    duracion=d.duracion,vimeus_id=d.vimeus_id,provider_download_url=d.provider_download_url,
    disponible=d.disponible,videoapi_available=d.videoapi_available,updated_at=now()
  FROM desired d WHERE ep.id=d.id AND
    ROW(ep.titulo,ep.sinopsis,ep.imagen_url,ep.duracion,ep.vimeus_id,ep.provider_download_url,ep.disponible,ep.videoapi_available)
    IS DISTINCT FROM ROW(d.titulo,d.sinopsis,d.imagen_url,d.duracion,d.vimeus_id,d.provider_download_url,d.disponible,d.videoapi_available);
  GET DIAGNOSTICS changed = ROW_COUNT;

  INSERT INTO public.episodios(temporada_id,numero,titulo,sinopsis,imagen_url,duracion,vimeus_id,provider_download_url,disponible,videoapi_available)
    SELECT t.id,e.numero,e.titulo,e.sinopsis,e.imagen_url,e.duracion,
      CASE WHEN mode='vimeus' THEN e.vimeus_id END,
      CASE WHEN mode='vimeus' THEN e.provider_download_url END,true,mode='videoapi'
    FROM jsonb_to_recordset(payload) AS e(season integer,numero integer,titulo text,sinopsis text,imagen_url text,duracion integer,vimeus_id bigint,provider_download_url text)
    JOIN public.temporadas t ON t.contenido_id=cid AND t.numero=e.season
    WHERE NOT EXISTS(SELECT 1 FROM public.episodios ep WHERE ep.temporada_id=t.id AND ep.numero=e.numero)
    ON CONFLICT(temporada_id,numero) DO NOTHING;
  GET DIAGNOSTICS added = ROW_COUNT;

  IF mode='vimeus' THEN
    -- Preserve manual/other-provider episodes, including links not present in
    -- Vimeus's snapshot. Retire only Vimeus-only playback, never delete rows.
    WITH incoming AS MATERIALIZED (
      SELECT season,numero FROM jsonb_to_recordset(payload) AS e(season integer,numero integer)
    )
    UPDATE public.episodios ep SET disponible=false,updated_at=now()
    FROM public.temporadas t WHERE ep.temporada_id=t.id AND t.contenido_id=cid
      AND ep.disponible AND ep.vimeus_id IS NOT NULL AND NOT ep.videoapi_available
      AND nullif(ep.descarga,'') IS NULL AND nullif(ep.playback_url,'') IS NULL
      AND nullif(ep.provider_download_url,'') IS NULL
      AND NOT EXISTS(SELECT 1 FROM incoming i WHERE i.season=t.numero AND i.numero=ep.numero);
    GET DIAGNOSTICS removed = ROW_COUNT;
  END IF;
  WITH counts AS (
    SELECT t.id,count(ep.id)::integer AS n FROM public.temporadas t
    LEFT JOIN public.episodios ep ON ep.temporada_id=t.id AND ep.disponible
    WHERE t.contenido_id=cid GROUP BY t.id
  )
  UPDATE public.temporadas t SET episodios=c.n FROM counts c
    WHERE t.id=c.id AND t.episodios IS DISTINCT FROM c.n;
  RETURN jsonb_build_object('episodios',total,'creados',added,'actualizados',changed,
                           'sin_cambios',total-added-changed,'retirados',removed);
END $$;
REVOKE ALL ON FUNCTION cine_security.merge_catalog_episodes(integer,jsonb,text) FROM PUBLIC,anon,authenticated,service_role;

-- Public entry points keep their JSON contract; counters reflect actual writes.
CREATE OR REPLACE FUNCTION public.importar_videoapi(documento jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE c jsonb:=documento->'contenido'; s jsonb; e jsonb; cid integer; sid integer;
  target integer:=(documento->>'content_id')::integer; old public.contenido%ROWTYPE;
  added integer:=0; changed integer:=0; total integer:=0; counts jsonb;
BEGIN
  IF c->>'tmdb_media' IS NULL THEN RAISE EXCEPTION 'Missing media type'; END IF;
  IF c->>'tipo' IS NULL OR c->>'tmdb_id' IS NULL THEN RAISE EXCEPTION 'Missing identity'; END IF;
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
      backdrop_url=coalesce(nullif(backdrop_url,''),c->>'backdrop_url') WHERE id=cid
      AND ROW(rating, tmdb_id, tmdb_media, imagen_url, sinopsis, genero, trailer_url, backdrop_url) IS DISTINCT FROM ROW(coalesce((c->>'rating')::double precision,rating), (c->>'tmdb_id')::bigint, c->>'tmdb_media', coalesce(nullif(imagen_url,''),c->>'imagen_url'), coalesce(nullif(sinopsis,''),c->>'sinopsis'), coalesce(nullif(genero,''),c->>'genero'), coalesce(nullif(trailer_url,''),c->>'trailer_url'), coalesce(nullif(backdrop_url,''),c->>'backdrop_url'));
  ELSE
    INSERT INTO public.contenido(tipo,tmdb_id,tmdb_media,titulo,sinopsis,imagen_url,genero,fuente,disponible,destacado,trailer_url,backdrop_url,rating)
    VALUES(c->>'tipo',(c->>'tmdb_id')::bigint,c->>'tmdb_media',c->>'titulo',c->>'sinopsis',c->>'imagen_url',c->>'genero',
      'vimeus',true,false,c->>'trailer_url',c->>'backdrop_url',(c->>'rating')::double precision) RETURNING id INTO cid;
  END IF;
  UPDATE public.contenido SET videoapi_kind=c->>'videoapi_kind',
      fuente=CASE WHEN fuente='okru' THEN fuente ELSE 'vimeus' END,
      playback_unverified=CASE WHEN fuente='okru' THEN playback_unverified ELSE false END,
      "año"=coalesce("año",(c->>'año')::integer) WHERE id=cid
      AND ROW(videoapi_kind, fuente, playback_unverified, "año") IS DISTINCT FROM ROW(c->>'videoapi_kind', CASE WHEN fuente='okru' THEN fuente ELSE 'vimeus' END, CASE WHEN fuente='okru' THEN playback_unverified ELSE false END, coalesce("año",(c->>'año')::integer));
  counts := cine_security.merge_catalog_episodes(cid, documento->'temporadas', 'videoapi');
  added := (counts->>'creados')::integer; changed := (counts->>'actualizados')::integer;
  total := (counts->>'episodios')::integer;
  -- No retirement, playback, visibility or download updates on existing rows.
  RETURN jsonb_build_object('success',true,'contenido_id',cid,'titulo',(SELECT titulo FROM public.contenido WHERE id=cid),
    'temporadas',jsonb_array_length(documento->'temporadas'),'episodios',total,'creados',added,'actualizados',changed,'retirados',0,'sin_cambios',(counts->>'sin_cambios')::integer,
    'provider','videoapi');
END $$;
REVOKE ALL ON FUNCTION public.importar_videoapi(jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.importar_videoapi(jsonb) TO service_role;

CREATE OR REPLACE FUNCTION public.importar_metadatos(documento jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE c jsonb:=documento->'contenido'; s jsonb; e jsonb; cid integer; sid integer;
  target integer:=(documento->>'content_id')::integer; old public.contenido%ROWTYPE;
  added integer:=0; changed integer:=0; total integer:=0; counts jsonb;
BEGIN
  IF c->>'tmdb_media' IS NULL THEN RAISE EXCEPTION 'Missing media type'; END IF;
  IF c->>'tipo' IS NULL OR c->>'tmdb_id' IS NULL THEN RAISE EXCEPTION 'Missing identity'; END IF;
  IF c->>'tipo' NOT IN ('pelicula','biblico') OR c->>'tmdb_media' NOT IN ('movie','tv')
    OR (c->>'tmdb_id')::bigint<=0 THEN RAISE EXCEPTION 'Invalid metadata'; END IF;
  PERFORM pg_advisory_xact_lock(hashtextextended('catalog:'||(c->>'tmdb_media')||':'||(c->>'tmdb_id'),0));
  IF target IS NOT NULL THEN
    SELECT * INTO old FROM public.contenido WHERE id=target AND tipo=c->>'tipo' FOR UPDATE;
    IF NOT FOUND OR (old.tmdb_id IS NOT NULL AND old.tmdb_id<>(c->>'tmdb_id')::bigint) THEN RAISE EXCEPTION 'Target mismatch'; END IF;
    cid:=old.id;
  ELSE
    SELECT * INTO old FROM public.contenido WHERE tipo=c->>'tipo' AND tmdb_id=(c->>'tmdb_id')::bigint FOR UPDATE;
    IF FOUND THEN cid:=old.id; END IF;
  END IF;
  IF cid IS NOT NULL THEN
    IF old.tmdb_media IS NOT NULL AND old.tmdb_media<>c->>'tmdb_media' THEN RAISE EXCEPTION 'Media mismatch'; END IF;
    UPDATE public.contenido SET rating=coalesce((c->>'rating')::double precision,rating),tmdb_id=(c->>'tmdb_id')::bigint,tmdb_media=c->>'tmdb_media',
      imagen_url=coalesce(nullif(imagen_url,''),c->>'imagen_url'),
      sinopsis=coalesce(nullif(sinopsis,''),c->>'sinopsis'),
      genero=coalesce(nullif(genero,''),c->>'genero'),
      trailer_url=coalesce(nullif(trailer_url,''),c->>'trailer_url'),
      backdrop_url=coalesce(nullif(backdrop_url,''),c->>'backdrop_url') WHERE id=cid
      AND ROW(rating, tmdb_id, tmdb_media, imagen_url, sinopsis, genero, trailer_url, backdrop_url) IS DISTINCT FROM ROW(coalesce((c->>'rating')::double precision,rating), (c->>'tmdb_id')::bigint, c->>'tmdb_media', coalesce(nullif(imagen_url,''),c->>'imagen_url'), coalesce(nullif(sinopsis,''),c->>'sinopsis'), coalesce(nullif(genero,''),c->>'genero'), coalesce(nullif(trailer_url,''),c->>'trailer_url'), coalesce(nullif(backdrop_url,''),c->>'backdrop_url'));
  ELSE
    INSERT INTO public.contenido(tipo,tmdb_id,tmdb_media,titulo,sinopsis,imagen_url,genero,fuente,disponible,destacado,trailer_url,backdrop_url,rating)
    VALUES(c->>'tipo',(c->>'tmdb_id')::bigint,c->>'tmdb_media',c->>'titulo',c->>'sinopsis',c->>'imagen_url',c->>'genero',
      CASE WHEN c->>'tipo'='pelicula' THEN 'vimeus' ELSE 'okru' END,true,false,c->>'trailer_url',c->>'backdrop_url',(c->>'rating')::double precision) RETURNING id INTO cid;
  END IF;
  counts := cine_security.merge_catalog_episodes(cid, documento->'temporadas', 'metadata');
  added := (counts->>'creados')::integer; changed := (counts->>'actualizados')::integer;
  total := (counts->>'episodios')::integer;
  -- No retirement, playback, visibility or download updates on existing rows.
  RETURN jsonb_build_object('success',true,'contenido_id',cid,'titulo',(SELECT titulo FROM public.contenido WHERE id=cid),
    'temporadas',jsonb_array_length(documento->'temporadas'),'episodios',total,'creados',added,'actualizados',changed,'retirados',0,'sin_cambios',(counts->>'sin_cambios')::integer,
    'metadata_only',c->>'tipo'='biblico');
END $$;
REVOKE ALL ON FUNCTION public.importar_metadatos(jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.importar_metadatos(jsonb) TO service_role;

CREATE OR REPLACE FUNCTION public.importar_vimeus(documento jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
DECLARE
    c jsonb := documento->'contenido'; s jsonb; e jsonb;
    cid integer; sid integer; added integer := 0; updated integer := 0;
    removed integer := 0; total integer := 0; seasons integer := 0;
    counts jsonb; ids integer[];
BEGIN
  IF c->>'tipo' IS NULL OR c->>'tmdb_id' IS NULL THEN RAISE EXCEPTION 'Missing identity'; END IF;
    IF c->>'tipo' NOT IN ('serie','anime') OR (c->>'tmdb_id')::bigint <= 0
       OR jsonb_array_length(documento->'temporadas') = 0 THEN
        RAISE EXCEPTION 'Invalid import document';
    END IF;
    -- Serializes concurrent reimports across all Render workers.
    PERFORM pg_advisory_xact_lock(hashtextextended('catalog:tv:' || (c->>'tmdb_id'), 0));
    SELECT array_agg(id) INTO ids FROM (
      SELECT x.id FROM public.contenido x WHERE x.tmdb_id=(c->>'tmdb_id')::bigint
        AND (x.tipo IN ('serie','anime') OR (x.tipo='biblico' AND x.tmdb_media='tv'))
        AND NOT EXISTS(SELECT 1 FROM public.catalog_aliases a WHERE a.original_id=x.id)
        ORDER BY x.id LIMIT 2
    ) candidates;
    IF cardinality(ids)>1 THEN RAISE EXCEPTION 'Ambiguous TMDB identity; review existing titles'; END IF;
    cid := ids[1];
    IF cid IS NULL THEN
      INSERT INTO public.contenido (tipo,tmdb_id,titulo,imagen_url,sinopsis,genero,fuente,disponible,destacado,trailer_url,backdrop_url,rating)
      VALUES (c->>'tipo',(c->>'tmdb_id')::bigint,c->>'titulo',c->>'imagen_url',c->>'sinopsis',c->>'genero','vimeus',true,false,c->>'trailer_url',c->>'backdrop_url',(c->>'rating')::double precision)
      RETURNING id INTO cid;
    ELSE
      PERFORM 1 FROM public.contenido WHERE id=cid FOR UPDATE;
      UPDATE public.contenido SET fuente=CASE WHEN fuente='okru' THEN fuente ELSE 'vimeus' END,
        rating=coalesce((c->>'rating')::double precision,rating),
        trailer_url=coalesce(nullif(trailer_url,''),c->>'trailer_url'),
        backdrop_url=coalesce(nullif(backdrop_url,''),c->>'backdrop_url') WHERE id=cid
      AND ROW(fuente, rating, trailer_url, backdrop_url) IS DISTINCT FROM ROW(CASE WHEN fuente='okru' THEN fuente ELSE 'vimeus' END, coalesce((c->>'rating')::double precision,rating), coalesce(nullif(trailer_url,''),c->>'trailer_url'), coalesce(nullif(backdrop_url,''),c->>'backdrop_url'));
    END IF;
    -- Preserve existing editorial metadata, descarga, legacy links and availability.
  counts := cine_security.merge_catalog_episodes(cid, documento->'temporadas', 'vimeus');
  added := (counts->>'creados')::integer; updated := (counts->>'actualizados')::integer;
  total := (counts->>'episodios')::integer;
  seasons := jsonb_array_length(documento->'temporadas'); removed := (counts->>'retirados')::integer;
    RETURN jsonb_build_object('contenido_id',cid,'titulo',(SELECT titulo FROM public.contenido WHERE id=cid),
        'temporadas',seasons,'episodios',total,'creados',added,'actualizados',updated,'retirados',removed,'sin_cambios',(counts->>'sin_cambios')::integer);
END;
$$;
REVOKE ALL ON FUNCTION public.importar_vimeus(jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.importar_vimeus(jsonb) TO service_role;

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
    UPDATE public.contenido SET rating=CASE WHEN jsonb_typeof(c->'rating')='number' AND (c->>'rating')::numeric BETWEEN 0 AND 10 THEN (c->>'rating')::numeric ELSE rating END,
      "año"=CASE WHEN c->>'año' ~ '^[0-9]{4}$' THEN (c->>'año')::integer ELSE "año" END,
      fuente=CASE WHEN fuente='okru' THEN fuente ELSE 'vimeus' END,
      playback_unverified=CASE WHEN fuente='okru' THEN playback_unverified ELSE false END WHERE id=cid
      AND ROW(rating, "año", fuente, playback_unverified) IS DISTINCT FROM ROW(CASE WHEN jsonb_typeof(c->'rating')='number' AND (c->>'rating')::numeric BETWEEN 0 AND 10 THEN (c->>'rating')::numeric ELSE rating END, CASE WHEN c->>'año' ~ '^[0-9]{4}$' THEN (c->>'año')::integer ELSE "año" END, CASE WHEN fuente='okru' THEN fuente ELSE 'vimeus' END, CASE WHEN fuente='okru' THEN playback_unverified ELSE false END);
    RETURN result;
END $$;
REVOKE ALL ON FUNCTION public.importar_catalogo_automatico(jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.importar_catalogo_automatico(jsonb) TO service_role;
COMMIT;
