"""Explicit mapping where provider episode numbers differ from TMDB season numbering.

Only description lookup changes. Playback/download coordinates remain untouched.
No filler filter is applied: the owner's latest instruction includes every episode.
"""
from providers.vimeus import ImportFailure

SHIPPUDEN_SEASON_COUNTS = (32,21,18,17,24,31,8,24,21,25,21,33,20,25,28,13,11,21,20,87)
NARUTO_SEASON_COUNTS = (52,52,54,62)


def metadata_episode(tmdb_id, season, episode, available_numbers=()):
    tmdb_id=int(tmdb_id)
    if tmdb_id not in (31910,46260) or season==0:return episode
    counts=SHIPPUDEN_SEASON_COUNTS if tmdb_id==31910 else NARUTO_SEASON_COUNTS
    if not 1<=season<=len(counts):
        raise ImportFailure('Temporada de Naruto fuera del mapa verificado.')
    offset=sum(counts[:season-1])
    relative=episode-offset if tmdb_id==31910 else episode
    if not 1<=relative<=counts[season-1]:
        raise ImportFailure('La numeración de Naruto cambió; revisa el mapa antes de importar.')
    absolute=offset+relative
    # Live TMDB currently returns absolute numbering for both titles. Also
    # handle a season-relative snapshot, but never match by row order.
    if absolute in available_numbers or not available_numbers:return absolute
    if min(available_numbers)==1 and max(available_numbers)<=counts[season-1]:return relative
    return absolute
