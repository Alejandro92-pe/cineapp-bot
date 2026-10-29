"""Read a local WordPress SQL export and propose exact TMDB matches.

Never connects to MySQL, changes WordPress, or activates redirects.
Private exports and result files belong outside version control.
"""
import argparse
import csv
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote

import requests


def rows(sql, table):
    pattern = re.compile(r"INSERT INTO `" + re.escape(table) + r"` \((.*?)\) VALUES\s*\n(.*?);\s*\n", re.S)
    for match in pattern.finditer(sql):
        columns = re.findall(r"`([^`]+)`", match[1])
        data = match[2]
        i = 0
        while i < len(data):
            if data[i] != '(':
                i += 1
                continue
            i += 1
            values = []
            while True:
                while data[i].isspace():
                    i += 1
                if data[i] == "'":
                    i += 1
                    value = []
                    while i < len(data):
                        ch = data[i]
                        i += 1
                        if ch == '\\':
                            escaped = data[i]
                            i += 1
                            value.append({'n': '\n', 'r': '\r', 't': '\t', '0': '\0', 'Z': '\x1a'}.get(escaped, escaped))
                        elif ch == "'":
                            if i < len(data) and data[i] == "'":
                                value.append("'")
                                i += 1
                            else:
                                break
                        else:
                            value.append(ch)
                    value = ''.join(value)
                else:
                    start = i
                    while data[i] not in ',)':
                        i += 1
                    value = data[start:i].strip()
                    if value == 'NULL':
                        value = None
                values.append(value)
                while data[i].isspace():
                    i += 1
                delimiter = data[i]
                i += 1
                if delimiter == ')':
                    break
                if delimiter != ',':
                    raise ValueError('Unexpected SQL export delimiter')
            if len(columns) != len(values):
                raise ValueError('Unexpected SQL export column count')
            yield dict(zip(columns, values))


def prepare(source, out):
    out.mkdir(parents=True, exist_ok=True)
    sql = source.read_text(encoding='utf-8-sig')
    posts = {r['ID']: r for r in rows(sql, 'wpwz_posts') if r['post_status'] == 'publish' and r['post_type'] in {'amy_movie', 'amy_tvshow'}}
    ids = defaultdict(set)
    for row in rows(sql, 'wpwz_postmeta'):
        if row['post_id'] in posts and row['meta_key'] == '_tmdb_id' and (row['meta_value'] or '').isdigit():
            ids[row['post_id']].add(int(row['meta_value']))
    session = requests.Session()
    origin = 'https://cineapp-bot.onrender.com'
    catalog = []
    for offset in range(0, 20000, 100):
        response = session.post(origin + '/api/contenido', json={'limit':100, 'offset':offset}, headers={'Origin':origin}, timeout=35)
        response.raise_for_status()
        payload = response.json()
        catalog.extend(payload['data'])
        if offset + len(payload['data']) >= payload['total']:
            break
        time.sleep(.3)
    else:
        raise RuntimeError('Catalogue pagination exceeded limit')
    index = defaultdict(list)
    for row in catalog:
        typ = 'movie' if row.get('tipo') == 'pelicula' else 'tv'
        if row.get('tmdb_id'):
            index[(typ, int(row['tmdb_id']))].append(row)
    result = []
    for pid, post in posts.items():
        typ = 'movie' if post['post_type'] == 'amy_movie' else 'tv'
        tmdb = next(iter(ids[pid])) if len(ids[pid]) == 1 else None
        candidates = index.get((typ, tmdb), [])
        unique = candidates[0] if len(candidates) == 1 else None
        result.append({'origen':'https://quehay.live/' + post['post_type'] + '/' + quote(post['post_name'], safe='%') + '/',
                       'titulo':post['post_title'], 'tipo':typ, 'tmdb_id':tmdb or '',
                       'app_id':unique['id'] if unique else '',
                       'destino_candidato':'https://app.quehay.live/?contenido=' + str(unique['id']) if unique else '',
                       'estado':'TMDB y tipo coinciden; falta validar destino SEO' if unique else 'Revisión manual: falta ID, hay duplicados o no está en catálogo',
                       'publicado':'NO'})
    with (out/'equivalencias-tmdb.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer = csv.DictWriter(f,fieldnames=list(result[0])); writer.writeheader(); writer.writerows(result)
    summary = {'wordpress_published_titles':len(posts), 'catalog_titles':len(catalog),
               'exact_tmdb_type_matches':sum(bool(r['app_id']) for r in result),
               'manual_review':sum(not r['app_id'] for r in result), 'activated_redirects':0}
    (out/'seo-summary.json').write_text(json.dumps(summary,indent=2))
    (out/'catalog-public.json').write_text(json.dumps(catalog,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(summary))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('sql',type=Path)
    parser.add_argument('out',type=Path)
    args = parser.parse_args()
    prepare(args.sql,args.out)
