"""
Filtro por rol/keyword. No es un filtro binario: cada vacante se puntúa
contra cada familia de rol (config.yaml -> roles) y se conserva el mejor
match, junto con su score, para poder ordenar el email por relevancia
en vez de solo incluir/excluir.

También aplica el filtro de ubicación/remoto (src/location_filter.py)
antes de puntuar -- se descarta primero por geografía, y solo lo que
pasa ese filtro se puntúa por rol.
"""
from location_filter import is_location_compatible


def score_job(title: str, roles_cfg: dict, exclude_keywords: list) -> tuple[str, int]:
    """
    Devuelve (mejor_rol, score). score = 0 significa que no matcheó
    ninguna keyword positiva -> se descarta en filter_and_rank.
    """
    title_lc = title.lower()

    for kw in exclude_keywords:
        if kw.lower() in title_lc:
            return "", -1  # excluido explícitamente

    best_role, best_score = "", 0
    for role, cfg in roles_cfg.items():
        score = sum(1 for kw in cfg.get("keywords", []) if kw.lower() in title_lc)
        if score > best_score:
            best_role, best_score = role, score

    return best_role, best_score


def filter_and_rank(jobs: list, roles_cfg: dict, exclude_keywords: list, location_cfg: dict = None) -> list:
    """
    Anota cada NormalizedJob con .matched_role y .score (atributos
    dinámicos, no forman parte del dataclass para no acoplar filter.py
    a ats_clients.base), descarta los excluidos por ubicación/rol, y
    ordena por score descendente.
    """
    location_cfg = location_cfg or {}
    ranked = []
    for job in jobs:
        if not is_location_compatible(job.location, job.remote_flag, location_cfg, job.department):
            continue

        role, score = score_job(job.title, roles_cfg, exclude_keywords)
        if score <= 0:
            continue
        job.matched_role = role
        job.score = score
        ranked.append(job)

    ranked.sort(key=lambda j: j.score, reverse=True)
    return ranked
