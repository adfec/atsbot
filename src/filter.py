"""
Filtro por rol/keyword. No es un filtro binario: cada vacante se puntúa
contra cada familia de rol (config.yaml -> roles) y se conserva el mejor
match, junto con su score, para poder ordenar el email por relevancia
en vez de solo incluir/excluir.
"""


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


def filter_and_rank(jobs: list, roles_cfg: dict, exclude_keywords: list) -> list:
    """
    Anota cada NormalizedJob con .matched_role y .score (atributos
    dinámicos, no forman parte del dataclass para no acoplar filter.py
    a ats_clients.base), descarta los excluidos/sin match, y ordena por
    score descendente.
    """
    ranked = []
    for job in jobs:
        role, score = score_job(job.title, roles_cfg, exclude_keywords)
        if score <= 0:
            continue
        job.matched_role = role
        job.score = score
        ranked.append(job)

    ranked.sort(key=lambda j: j.score, reverse=True)
    return ranked
