"""Dry run by default. Requires explicit --apply and production configuration for writes."""
import argparse,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('changes',type=Path);p.add_argument('--apply',action='store_true');a=p.parse_args()
    if os.getenv('APP_MODE')!='production' or os.getenv('APP_ORIGIN')!='https://app.quehay.live':
        p.error('Requiere la configuración explícita de producción; no se cargan claves desde archivos.')
    from main import supabase_service
    from services.artwork import apply_reviewed
    changes=list(json.loads(a.changes.read_text(encoding='utf-8')).values())
    print(json.dumps(apply_reviewed(supabase_service,changes,apply=a.apply)))
