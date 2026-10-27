-- Prepared for production review; not applied. Requires 002, 004, 005 and 007.
BEGIN;
ALTER TABLE public.contenido ADD COLUMN IF NOT EXISTS tmdb_media text;
CREATE OR REPLACE FUNCTION public.importar_metadatos(documento jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE c jsonb:=documento->'contenido'; s jsonb; e jsonb; cid integer; sid integer;
  target integer:=(documento->>'content_id')::integer; old public.contenido%ROWTYPE;
  added integer:=0; changed integer:=0; total integer:=0; existed boolean;
BEGIN
  IF c->>'tipo' NOT IN ('pelicula','biblico') OR c->>'tmdb_media' NOT IN ('movie','tv')
    OR (c->>'tmdb_id')::bigint<=0 THEN RAISE EXCEPTION 'Invalid metadata'; END IF;
  PERFORM pg_advisory_xact_lock(hashtextextended('metadata:'||(c->>'tipo')||':'||(c->>'tmdb_id'),0));
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
    UPDATE public.contenido SET tmdb_id=(c->>'tmdb_id')::bigint,tmdb_media=c->>'tmdb_media',
      imagen_url=coalesce(nullif(imagen_url,''),c->>'imagen_url'),
      sinopsis=coalesce(nullif(sinopsis,''),c->>'sinopsis'),
      genero=coalesce(nullif(genero,''),c->>'genero'),
      trailer_url=coalesce(nullif(trailer_url,''),c->>'trailer_url'),
      backdrop_url=coalesce(nullif(backdrop_url,''),c->>'backdrop_url') WHERE id=cid;
  ELSE
    INSERT INTO public.contenido(tipo,tmdb_id,tmdb_media,titulo,sinopsis,imagen_url,genero,fuente,disponible,destacado,trailer_url,backdrop_url)
    VALUES(c->>'tipo',(c->>'tmdb_id')::bigint,c->>'tmdb_media',c->>'titulo',c->>'sinopsis',c->>'imagen_url',c->>'genero',
      CASE WHEN c->>'tipo'='pelicula' THEN 'vimeus' ELSE 'okru' END,true,false,c->>'trailer_url',c->>'backdrop_url') RETURNING id INTO cid;
  END IF;
  FOR s IN SELECT value FROM jsonb_array_elements(documento->'temporadas') LOOP
    INSERT INTO public.temporadas(contenido_id,numero,nombre,poster_url,descripcion,episodios)
    VALUES(cid,(s->>'numero')::integer,s->>'nombre',s->>'poster_url',s->>'descripcion',0)
    ON CONFLICT(contenido_id,numero) DO UPDATE SET numero=excluded.numero RETURNING id INTO sid;
    FOR e IN SELECT value FROM jsonb_array_elements(s->'capitulos') LOOP
      SELECT EXISTS(SELECT 1 FROM public.episodios WHERE temporada_id=sid AND numero=(e->>'numero')::integer) INTO existed;
      INSERT INTO public.episodios(temporada_id,numero,titulo,sinopsis,imagen_url,duracion,disponible)
      VALUES(sid,(e->>'numero')::integer,e->>'titulo',e->>'sinopsis',e->>'imagen_url',(e->>'duracion')::integer,true)
      ON CONFLICT(temporada_id,numero) DO UPDATE SET
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
    'metadata_only',c->>'tipo'='biblico');
END $$;
REVOKE ALL ON FUNCTION public.importar_metadatos(jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.importar_metadatos(jsonb) TO service_role;
COMMIT;
