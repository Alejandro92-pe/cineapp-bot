from conftest import send
from services.hero import HeroRotation, PERIOD, LIMA_OFFSET, choose_ids


def catalogue(system, count=12):
    rows = system.supabase_service.rows['contenido']
    sample = dict(rows[0])
    rows[:] = [{**sample, 'id': i, 'destacado': False} for i in range(1, count+1)]
    return rows


def test_three_days_shared_snapshot_survives_new_imports_and_restart(system):
    rows = catalogue(system)
    first = HeroRotation(system.catalog_job_store, system.supabase_service, lambda: 100*PERIOD+LIMA_OFFSET+10)
    ids = [r['id'] for r in first.titles()]
    assert len(ids) == len(set(ids)) == 3
    rows.extend([{**rows[0], 'id': i} for i in range(20,50)])
    restarted = HeroRotation(system.catalog_job_store, system.supabase_service, lambda: 101*PERIOD+LIMA_OFFSET-1)
    assert [r['id'] for r in restarted.titles()] == ids
    following = HeroRotation(system.catalog_job_store, system.supabase_service, lambda: 101*PERIOD+LIMA_OFFSET)
    assert not set(ids).intersection(r['id'] for r in following.titles())


def test_public_hero_keeps_private_downloads_out_and_excludes_unavailable(client, system):
    rows=catalogue(system)
    rows[0]['disponible']=False
    rows[1]['tipo']='serie'
    rows[2]['imagen_url']=None
    result=send(client,'/api/tendencias',method='GET')
    assert result.status_code == 200 and len(result.json)==3
    assert all(r['id'] not in (1,2,3) and 'descarga' not in r and 'enlace_canal' not in r for r in result.json)
    hidden=result.json[0]['id']
    next(r for r in rows if r['id']==hidden)['disponible']=False
    assert hidden not in [r['id'] for r in send(client,'/api/tendencias',method='GET').json]


def test_empty_or_small_catalogue_and_deterministic_selection(system):
    rows=catalogue(system,2)
    hero=HeroRotation(system.catalog_job_store, system.supabase_service, lambda: 100*PERIOD)
    assert len(hero.titles())==2
    rows.clear()
    assert hero.titles()==[]
    assert choose_ids([5,2,1,2,4],6)==choose_ids([4,2,5,1],6)


def test_only_first_visit_scans_candidates_and_pagination_is_complete(system, monkeypatch):
    rows=catalogue(system,510)
    for row in rows[:500]:row['imagen_url']=None
    hero=HeroRotation(system.catalog_job_store, system.supabase_service)
    assert all(r['id']>500 for r in hero.titles())
    original=hero.movies
    def no_scan(fields):
        assert fields=='*'
        return original(fields)
    monkeypatch.setattr(hero,'movies',no_scan)
    assert len(hero.titles())==3
