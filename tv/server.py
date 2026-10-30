"""Future Render entrypoint: gunicorn tv.server:app. Disabled unless TV_ENABLED=true.

Imports the TV schema before local account store initialization. No production DDL.
"""
import os
from tv.integration import compose
import main

app=compose(main.app,main.supabase_service,main.security_store,main.account_legacy_expiry,
            enabled=os.getenv('TV_ENABLED','false').lower()=='true')
