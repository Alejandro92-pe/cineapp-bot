"""Local rehearsal of the unchanged web app + TV sharing the same account store."""
import os
import time
from pathlib import Path


def main():
    root=Path(__file__).resolve().parents[1];out=root/'.local/tv-integration';out.mkdir(parents=True,exist_ok=True)
    os.environ.update(APP_MODE='local',APP_ORIGIN='http://127.0.0.1:5022',APP_ORIGIN_ALIASES='',TELEGRAM_PREVIEW='false',
        SECURITY_DATABASE_URL='sqlite:///'+(out/'accounts.sqlite').as_posix(),TV_ENABLED='true',
        BOT_TOKEN='123456:TV_LOCAL_INTEGRATION_ONLY',SUPABASE_URL='',SUPABASE_KEY='',SUPABASE_SERVICE_KEY='',
        TMDB_API_KEY='',VIMEUS_API_KEY='',VIMEUS_VIEW_KEY='',VIDEOAPI_ENABLED='true',
        ADMIN_PASSWORD_HASH='',ADMIN_PASSWORD='',CRON_SECRET='',BMC_WEBHOOK_SECRET='',BMC_MONTHLY_READY='false')
    from local_support import block_external_network
    block_external_network()
    from tv.server import app
    import main as web
    from tv.preview import load_snapshot
    from security import password_hash
    from billing.schema import access
    from sqlalchemy import select
    snapshot=load_snapshot(Path('C:/Users/richa/Mis Proyectos/cineapp-render/.local'))
    for table in ('contenido','temporadas','episodios'):web.supabase_service.rows[table]=snapshot.rows[table]
    for email,name,telegram,paid in [
        ('propietario.tv@example.test','Propietario · prueba',5824989040,False),
        ('miembro.tv@example.test','Miembro · prueba',None,True),
        ('sinacceso.tv@example.test','Sin acceso · prueba',None,False)]:
        account=web.security_store.account(email=email)
        if not account:account=web.security_store.create_account(name,email,password_hash('Integracion-TV-2026!'),telegram_id=telegram)
        if paid:
            with web.security_store.engine.begin() as c:
                if not c.execute(select(access).where(access.c.account_id==account['id'])).first():c.execute(access.insert().values(account_id=account['id'],expires_at=time.time()+30*86400))
    from werkzeug.serving import run_simple
    print('Integracion aislada web + TV: http://127.0.0.1:5022/tv; solo cuentas sinteticas.',flush=True)
    run_simple('127.0.0.1',5022,app,use_reloader=False,threaded=True)


if __name__=='__main__':main()
