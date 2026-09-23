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


def search_jobicy(query: str) -> list[NormalizedJob]:
    """
    Jobicy SÍ expone un campo estructurado de elegibilidad geográfica
    (jobGeo: "USA", "Europe", "Anywhere", etc.), a diferencia de Arbeitnow
    que solo trae texto libre + un booleano remote. Por eso reemplaza a
    Arbeitnow en el fallback -- ver location_filter.py, que evalúa jobGeo
    igual que evalúa location.
    """
    jobs = []
    try:
        r = requests.get(
            "https://jobicy.com/api/v2/remote-jobs",
            params={"count": 50, "tag": query},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            for job in r.json().get("jobs", []):
                jobs.append(NormalizedJob(
                    company=job.get("companyName", ""),
                    ats="jobicy",
                    title=job.get("jobTitle", ""),
                    url=job.get("url", ""),
                    location=job.get("jobGeo", ""),
                    department=job.get("jobIndustry", ""),
                    posted_at=job.get("pubDate", ""),
                    raw_id=str(job.get("id", "")),
                    source="role_search",
                    remote_flag=True,  # Jobicy es un board exclusivamente remoto
                ))
    except (requests.RequestException, ValueError):
        pass
    return jobs


def search_arbeitnow(query: str) -> list[NormalizedJob]:
    """
    DEPRECADO en run_role_search (ver más abajo): Arbeitnow es un board
    centrado en Europa y solo expone texto libre de ubicación + un
    booleano remote, sin ningún campo de elegibilidad geográfica real --
    "remote": true casi siempre significa "remoto dentro de la UE/un país
    específico", no remoto global, y esa restricción vive en la
    descripción completa, no en ningún campo que podamos leer barato.
    Se deja la función por si en el futuro se quiere usar con un
    location_filter más estricto (ej. exigir coincidencia positiva
    explícita en vez de aceptar por defecto).
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
                    remote_flag=job.get("remote"),
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

    Arbeitnow se dejó fuera de esta combinación (ver search_arbeitnow) --
    Jobicy cubre el mismo tipo de fuente pero con datos de elegibilidad
    geográfica confiables.
    """
    results: list[NormalizedJob] = []
    seen_urls = set()

    for role, cfg in role_keywords.items():
        keywords = cfg.get("keywords", [])
        if not keywords:
            continue
        anchor = keywords[0]

        for job in search_remotive(anchor) + search_jobicy(anchor):
            if job.url in seen_urls:
                continue
            seen_urls.add(job.url)
            results.append(job)

    return results
