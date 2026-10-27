"""Synthetic catalogue for visual QA only; called by run_local after isolation."""
from pathlib import Path
from html import escape


def seed_catalog(database):
    art = Path(__file__).resolve().parents[1]/'static/catalog/demo'
    art.mkdir(exist_ok=True)
    palettes = [('Horizonte', '#162b43', '#e2b87a'), ('Órbita', '#171b45', '#aeb7ff'),
                ('Marea', '#143a43', '#7dd6cf'), ('El último viaje', '#432b38', '#e7a5a3'),
                ('Luz del norte', '#20294e', '#a8c8ed'), ('Entre montañas', '#243d33', '#d4d8a4')]
    for index, (title, color, glow) in enumerate(palettes):
        (art/f'{index}.svg').write_text(f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 900">
<defs><linearGradient id="sky" x2=".7" y2="1"><stop stop-color="{color}"/><stop offset="1" stop-color="#080f19"/></linearGradient><radialGradient id="glow"><stop stop-color="{glow}" stop-opacity=".65"/><stop offset="1" stop-color="{glow}" stop-opacity="0"/></radialGradient></defs>
<rect width="600" height="900" fill="url(#sky)"/><circle cx="370" cy="270" r="280" fill="url(#glow)"/><circle cx="370" cy="270" r="95" fill="{glow}" opacity=".8"/>
<path d="M0 610 190 330 330 550 450 420 600 620V900H0Z" fill="{color}"/><path d="M0 760 140 540 300 700 440 570 600 720V900H0Z" fill="#0a1422"/>
<path d="m0 810 260-90 340 90v90H0Z" fill="#07101b"/><path d="m295 900 100-170h10L320 900" fill="{glow}" opacity=".4"/>
<text x="42" y="72" font-family="sans-serif" letter-spacing="7" font-size="14" fill="{glow}">QUEHAY · DEMO</text>
<text x="42" y="805" font-family="sans-serif" font-weight="700" font-size="43" fill="#ecf2fb">{escape(title.upper())}</text><text x="44" y="842" font-family="sans-serif" letter-spacing="5" font-size="11" fill="{glow}">UNA HISTORIA DE PRUEBA</text></svg>''', encoding='utf-8')
    rows=database.rows['contenido']
    for index, row in enumerate(rows):
        row.update(imagen_url=f'/static/catalog/demo/{1 if row["tipo"]=="anime" else 0}.svg',
                   titulo=['Horizonte','Horizonte: la serie','Órbita'][index % 3],
                   genero='Aventura, Drama' if row['tipo']!='anime' else 'Animación, Fantasía',
                   año=2026, sinopsis='Una señal en el horizonte. Un viaje que lo cambia todo. Descubre hasta dónde puede llevarte la curiosidad. Ficha ficticia para la vista local.')
    for index in range(24):
        name, _, _ = palettes[(index+2)%6]
        rows.append(dict(id=100+index,titulo=name+(f' · Relato {index//6+1}' if index>=6 else ''),
            tipo='pelicula',genero=['Drama','Aventura','Ciencia ficción','Familia'][index%4],
            año=2023+index%4,imagen_url=f'/static/catalog/demo/{(index+2)%6}.svg',
            disponible=True,destacado=False,fuente='vimeus',tmdb_id=900300+index,
            sinopsis='Historia ficticia para comprobar búsqueda, filtros y navegación. No reproduce contenido externo.',
            descarga='https://www.mediafire.com/file/local-test/example/file' if index%3==0 else None))
