-- CUTOVER ONLY: run after the new server API has replaced the old browser client.
-- Keep all rows, policies and authenticated server access. Do not run on the old UI.
BEGIN;
REVOKE ALL ON public.contenido, public.temporadas, public.usuarios,
  public.membresias_activas, public.membresias_planes, public.pagos_manuales,
  public.pedidos, public.publicaciones_canal FROM anon, authenticated, PUBLIC;
GRANT ALL ON public.contenido, public.temporadas, public.usuarios,
  public.membresias_activas, public.membresias_planes, public.pagos_manuales,
  public.pedidos, public.publicaciones_canal TO service_role;
COMMIT;
