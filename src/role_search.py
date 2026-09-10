"""
Mecanismo de respaldo pedido explícitamente: si la lista de empresas no
arroja resultados (o para ampliar el universo más allá de esa lista),
buscamos directamente por rol/keyword en agregadores públicos que sí
soportan búsqueda por texto libre, sin depender de conocer la empresa
de antemano.

Importante: estas fuentes NO pasan por el allowlist de ATS conocidos,
así que la decisión de si una vacante es relevante/compatible queda
por cuenta del usuario -- este módulo amplía las posibilidades, no
reemplaza el filtro por empresa ni el scoring de src/filter.py (que
igual se les aplica).

Fuentes usadas (ambas públicas, sin API key, documentadas):
  - Remotive   https://remotive.com/api/remote-jobs?search=<query>
  - Arbeitnow  https://www.arbeitnow.com/api/job-board-api
"""
import requests

from ats_clients.base import NormalizedJob

TIMEOUT = 10


def search_remotive(query: str) -> list[NormalizedJob]:
    jobs = []
    try:
        r = requests.get(
            "https://remotive.com/api/remote-jobs",
            params={"search": query},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            for job in r.json().get("jobs", []):
                jobs.append(NormalizedJob(
                    company=job.get("company_name", ""),
                    ats="remotive",
                    title=job.get("title", ""),
                    url=job.get("url", ""),
                    location=job.get("candidate_required_location", ""),
                    department=job.get("category", ""),
                    posted_at=job.get("publication_date", ""),
                    raw_id=str(job.get("id", "")),
                    source="role_search",
                    remote_flag=True,  # Remotive es un board exclusivamente remoto
                ))
    except (requests.RequestException, ValueError):
        pass
    return jobs


def search_arbeitnow(query: str) -> list[NormalizedJob]:
    """
    Arbeitnow no soporta filtro por query en la URL pública; se trae el
    board completo (paginado) y se filtra localmente por título. El board
    es pequeño-mediano así que esto es barato.
    """
    jobs = []
    query_lc = query.lower()
    try:
        r = requests.get("https://www.arbeitnow.com/api/job-board-api", timeout=TIMEOUT)
        if r.status_code == 200:
            for job in r.json().get("data", []):
                title = job.get("title", "")
                if query_lc not in title.lower():
                    continue
                jobs.append(NormalizedJob(
                    company=job.get("company_name", ""),
                    ats="arbeitnow",
                    title=title,
                    url=job.get("url", ""),
                    location=", ".join(job.get("location", "").split(",")) if job.get("location") else "",
                    department="",
                    posted_at=str(job.get("created_at", "")),
                    raw_id=job.get("slug", ""),
                    source="role_search",
                    remote_flag=job.get("remote"),  # Arbeitnow SÍ reporta esto -- antes se ignoraba
                ))
    except (requests.RequestException, ValueError):
        pass
    return jobs


def run_role_search(role_keywords: dict) -> list[NormalizedJob]:
    """
    role_keywords: el dict "roles" de config.yaml, ej.
      {"engineering_manager": {"keywords": [...]}, ...}

    Se usa como query solo la keyword "ancla" de cada rol (la primera de
    la lista) para no saturar de llamadas a los agregadores; el scoring
    fino contra todas las keywords se aplica después, igual que a las
    vacantes de empresa (ver src/filter.py). El filtro de ubicación/remoto
    se aplica aparte, en src/location_filter.py, sobre el resultado
    combinado de ambas fuentes.
    """
    results: list[NormalizedJob] = []
    seen_urls = set()

    for role, cfg in role_keywords.items():
        keywords = cfg.get("keywords", [])
        if not keywords:
            continue
        anchor = keywords[0]

        for job in search_remotive(anchor) + search_arbeitnow(anchor):
            if job.url in seen_urls:
                continue
            seen_urls.add(job.url)
            results.append(job)

    return results
