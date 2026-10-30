"""Dispatch only /tv to an isolated Flask app, sharing existing account services."""
from tv.app import create_app


class TVRouter:
    def __init__(self, web, tv):
        self.web,self.tv=web,tv

    def __call__(self,environ,start_response):
        path=environ.get('PATH_INFO','')
        target=self.tv if path=='/tv' or path.startswith('/tv/') else self.web
        return target(environ,start_response)


def compose(web_app,database,security,legacy_expiry,*,enabled=False):
    if not enabled:return web_app
    origin=web_app.config['APP_ORIGIN']
    television=create_app(database,security,origin,integrated=True,legacy_expiry=legacy_expiry)
    return TVRouter(web_app,television)
