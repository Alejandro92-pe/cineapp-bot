-- Prepared for review only, NOT applied to production. Requires 002, 004, 005, 007.
BEGIN;
CREATE OR REPLACE FUNCTION public.guardar_okru(documento jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
DECLARE cid integer := (documento->>'content_id')::integer;
  sid integer; eid bigint; sn integer; en integer; title text; url text := documento->>'url';
BEGIN
  IF url IS NULL OR url !~ '^https://ok\.ru/videoembed/[1-9][0-9]{0,19}\?nochat=1$'
    OR documento->>'scope' NOT IN ('title','episode') OR documento->>'scope' IS NULL THEN
    RAISE EXCEPTION 'Invalid OK.ru document';
  END IF;
  PERFORM 1 FROM public.contenido WHERE id=cid AND tipo='biblico' FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Biblical title not found'; END IF;
  IF documento->>'scope'='title' THEN
    UPDATE public.contenido SET playback_url=url,fuente='okru' WHERE id=cid;
  ELSE
    sn := (documento->>'season')::integer; en := (documento->>'episode')::integer;
    title := btrim(coalesce(documento->>'title',''));
    IF sn IS NULL OR en IS NULL OR sn NOT BETWEEN 0 AND 9999 OR en NOT BETWEEN 1 AND 99999 OR length(title)>300 THEN
      RAISE EXCEPTION 'Invalid episode numbers';
    END IF;
    INSERT INTO public.temporadas(contenido_id,numero,nombre,episodios)
    VALUES(cid,sn,CASE WHEN sn=0 THEN 'Especiales' ELSE 'Temporada '||sn END,0)
    ON CONFLICT(contenido_id,numero) DO UPDATE SET numero=excluded.numero RETURNING id INTO sid;
    INSERT INTO public.episodios(temporada_id,numero,titulo,playback_url,disponible)
    VALUES(sid,en,coalesce(nullif(title,''),'Episodio '||en),url,true)
    ON CONFLICT(temporada_id,numero) DO UPDATE SET playback_url=excluded.playback_url,
      titulo=CASE WHEN title='' THEN public.episodios.titulo ELSE title END,updated_at=now()
    RETURNING id INTO eid;
    UPDATE public.temporadas SET episodios=(SELECT count(*) FROM public.episodios WHERE temporada_id=sid AND disponible) WHERE id=sid;
    UPDATE public.contenido SET fuente='okru' WHERE id=cid;
  END IF;
  RETURN jsonb_build_object('success',true,'content_id',cid,'episode_id',eid,'url',url);
END $$;
REVOKE ALL ON FUNCTION public.guardar_okru(jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.guardar_okru(jsonb) TO service_role;
COMMIT;
