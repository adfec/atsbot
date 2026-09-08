"""
Auto-descubrimiento de ATS (Nivel 1: APIs JSON públicas sin auth) y
normalización de cada respuesta al esquema común NormalizedJob.

No se mantiene un mapa manual "empresa -> ATS": se prueba cada probe en
orden y se usa el primero que responda. Esto es justo lo que discutimos
como mejora sobre el artículo original (regex sobre una tabla ajena vs.
consultar cada ATS directamente).
"""
import requests

from .base import NormalizedJob

TIMEOUT = 8


def _get(url, **kwargs):
    try:
        r = requests.get(url, timeout=TIMEOUT, **kwargs)
        if r.status_code == 200:
            return r.json()
    except (requests.RequestException, ValueError):
        return None
    return None


# --- Probes Nivel 1 -----------------------------------------------------

def probe_greenhouse(slug: str):
    data = _get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
    if data and "jobs" in data:
        return "greenhouse", data["jobs"]
    return None


def probe_lever(slug: str):
    data = _get(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    if isinstance(data, list) and data:
        return "lever", data
    return None


def probe_ashby(slug: str):
    data = _get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    if data and "jobs" in data:
        return "ashby", data["jobs"]
    return None


def probe_smartrecruiters(slug: str):
    data = _get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings")
    if data and "content" in data:
        return "smartrecruiters", data["content"]
    return None


def probe_recruitee(slug: str):
    data = _get(f"https://{slug}.recruitee.com/api/offers/")
    if data and "offers" in data:
        return "recruitee", data["offers"]
    return None


def probe_workable(slug: str):
    data = _get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}")
    if data and "jobs" in data:
        return "workable", data["jobs"]
    return None


LEVEL_1_PROBES = [
    probe_greenhouse,
    probe_lever,
    probe_ashby,
    probe_smartrecruiters,
    probe_recruitee,
    probe_workable,
]


def probe_workday(tenant_path: str):
    """
    Workday no es descubrible solo por slug (el tenant, ej. wd12, no es
    adivinable). tenant_path viene de config.yaml, con forma:
    "empresa.wd12.myworkdayjobs.com/Sitio_jobs"
    """
    host, _, site = tenant_path.partition("/")
    url = f"https://{host}/wday/cxs/{host.split('.')[0]}/{site}/jobs"
    try:
        r = requests.post(url, json={"limit": 20, "offset": 0}, timeout=TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            if "jobPostings" in data:
                return "workday", data["jobPostings"]
    except (requests.RequestException, ValueError):
        pass
    return None


def discover(slug: str):
    """Prueba los ATS de Nivel 1 en orden. Devuelve (ats_name, raw_jobs) o None."""
    for probe in LEVEL_1_PROBES:
        result = probe(slug)
        if result:
            return result
    return None


# --- Normalización por ATS ----------------------------------------------

def normalize(company: str, ats: str, raw_jobs) -> list[NormalizedJob]:
    normalizer = _NORMALIZERS.get(ats)
    if not normalizer:
        return []
    return [normalizer(company, job) for job in raw_jobs]


def _norm_greenhouse(company, job):
    return NormalizedJob(
        company=company, ats="greenhouse",
        title=job.get("title", ""),
        url=job.get("absolute_url", ""),
        location=(job.get("location") or {}).get("name", ""),
        department=", ".join(d.get("name", "") for d in job.get("departments", [])),
        posted_at=job.get("updated_at", ""),
        raw_id=str(job.get("id", "")),
    )


def _norm_lever(company, job):
    categories = job.get("categories", {}) or {}
    return NormalizedJob(
        company=company, ats="lever",
        title=job.get("text", ""),
        url=job.get("hostedUrl", ""),
        location=categories.get("location", ""),
        department=categories.get("team", ""),
        posted_at=str(job.get("createdAt", "")),
        raw_id=str(job.get("id", "")),
    )


def _norm_ashby(company, job):
    return NormalizedJob(
        company=company, ats="ashby",
        title=job.get("title", ""),
        url=job.get("jobUrl", ""),
        location=job.get("location", ""),
        department=job.get("department", ""),
        posted_at=job.get("publishedAt", ""),
        raw_id=str(job.get("id", "")),
    )


def _norm_smartrecruiters(company, job):
    location = job.get("location", {}) or {}
    loc_str = ", ".join(filter(None, [location.get("city"), location.get("country")]))
    return NormalizedJob(
        company=company, ats="smartrecruiters",
        title=job.get("name", ""),
        url=job.get("ref", ""),
        location=loc_str,
        department=(job.get("department") or {}).get("label", ""),
        posted_at=job.get("releasedDate", ""),
        raw_id=str(job.get("id", "")),
    )


def _norm_recruitee(company, job):
    return NormalizedJob(
        company=company, ats="recruitee",
        title=job.get("title", ""),
        url=job.get("careers_url", ""),
        location=job.get("location", ""),
        department=job.get("department", ""),
        posted_at=job.get("published_at", ""),
        raw_id=str(job.get("id", "")),
    )


def _norm_workable(company, job):
    return NormalizedJob(
        company=company, ats="workable",
        title=job.get("title", ""),
        url=job.get("url", ""),
        location=job.get("location", {}).get("location_str", "") if isinstance(job.get("location"), dict) else "",
        department=job.get("department", ""),
        posted_at=job.get("published_on", ""),
        raw_id=str(job.get("shortcode", "")),
    )


def _norm_workday(company, job):
    return NormalizedJob(
        company=company, ats="workday",
        title=job.get("title", ""),
        url=job.get("externalPath", ""),
        location=job.get("locationsText", ""),
        department="",
        posted_at=job.get("postedOn", ""),
        raw_id=str(job.get("bulletFields", [""])[0] if job.get("bulletFields") else ""),
    )


_NORMALIZERS = {
    "greenhouse": _norm_greenhouse,
    "lever": _norm_lever,
    "ashby": _norm_ashby,
    "smartrecruiters": _norm_smartrecruiters,
    "recruitee": _norm_recruitee,
    "workable": _norm_workable,
    "workday": _norm_workday,
}
