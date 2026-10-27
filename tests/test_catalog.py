import pytest
from conftest import send


def test_combined_catalog_filters_and_private_download_url(client, system):
    rows = system.supabase_service.rows['contenido']
    rows.extend([{**rows[0], 'id':i, 'titulo':f'Historia {i}', 'año':2025 if i==2 else 2026,
                  'tipo':'anime' if i==4 else 'pelicula', 'descarga':None if i==5 else rows[0]['descarga']}
                 for i in range(2,6)])
    result=send(client,'/api/contenido',{'tipo':'pelicula','busqueda':'Historia','genero':'Drama','año':2026,'descarga':True})
    assert result.status_code==200
    assert [r['id'] for r in result.json['data']]==[3]
    assert result.json['data'][0]['has_download'] is True
    assert 'descarga' not in result.json['data'][0]


@pytest.mark.parametrize('year',[True,1800,'invalid',2026.5,9999])
def test_invalid_year_rejected(client,year):
    assert send(client,'/api/contenido',{'año':year}).status_code==400


def test_pagination_counts_all_matches_without_duplicates(client,system):
    rows=system.supabase_service.rows['contenido']
    rows.extend([{**rows[0],'id':i,'titulo':f'Película {i}'} for i in range(2,30)])
    first=send(client,'/api/contenido',{'limit':24,'offset':0}).json
    second=send(client,'/api/contenido',{'limit':24,'offset':24}).json
    assert first['total']==second['total']==29
    assert len(first['data'])==24 and len(second['data'])==5
    assert len({r['id'] for r in first['data']+second['data']})==29


def test_hidden_title_never_becomes_featured(client,system):
    system.supabase_service.rows['contenido'][0]['disponible']=False
    assert send(client,'/api/tendencias',method='GET').json==[]
