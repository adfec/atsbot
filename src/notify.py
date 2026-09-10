"""
Entrega 100% nativa de GitHub: en vez de SMTP, se publica el digest como
comentario en un Issue fijo del repo, usando el GITHUB_TOKEN que Actions
ya provee en cada run -- sin secrets nuevos, sin credencial externa.
GitHub te notifica por correo/app si tienes "Watch" activado en el repo.
"""
import json
import os
from pathlib import Path

import requests

DIGEST_ISSUE_STATE_PATH = Path("digest_issue.json")
DIGEST_ISSUE_TITLE = "📋 Job Alerts — Log diario"
API_ROOT = "https://api.github.com"


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _load_issue_number():
    if not DIGEST_ISSUE_STATE_PATH.exists():
        return None
    try:
        return json.loads(DIGEST_ISSUE_STATE_PATH.read_text(encoding="utf-8")).get("issue_number")
    except (json.JSONDecodeError, OSError):
        return None


def _save_issue_number(issue_number: int):
    DIGEST_ISSUE_STATE_PATH.write_text(
        json.dumps({"issue_number": issue_number}, indent=2), encoding="utf-8"
    )


def _get_or_create_issue(repo: str, token: str) -> int:
    issue_number = _load_issue_number()
    if issue_number:
        return issue_number

    # Si el state se perdiera pero el issue ya existe, se busca por título
    # antes de crear uno nuevo -- evita duplicados.
    r = requests.get(
        f"{API_ROOT}/repos/{repo}/issues",
        params={"state": "all", "per_page": 100},
        headers=_headers(token), timeout=10,
    )
    if r.status_code == 200:
        for issue in r.json():
            if issue.get("title") == DIGEST_ISSUE_TITLE:
                _save_issue_number(issue["number"])
                return issue["number"]

    r = requests.post(
        f"{API_ROOT}/repos/{repo}/issues",
        json={
            "title": DIGEST_ISSUE_TITLE,
            "body": "Log automático del pipeline de alertas de empleo. "
                    "Cada corrida agrega un comentario nuevo aquí.",
        },
        headers=_headers(token), timeout=10,
    )
    r.raise_for_status()
    issue_number = r.json()["number"]
    _save_issue_number(issue_number)
    return issue_number


def _render_job_row(job) -> str:
    role_label = (job.matched_role or "sin categoría").replace("_", " ").title()
    return (
        f"- **{job.title}** — {job.company} ({job.location or 'ubicación no especificada'})\n"
        f"  _{role_label} · score {job.score} · vía {job.ats}_\n"
        f"  {job.url}"
    )


def render_digest_markdown(company_jobs: list, role_search_jobs: list, alarms: list) -> str:
    parts = []

    if alarms:
        parts.append("### ⚠ Alarmas de salud de fuente\n")
        parts.extend(f"- {a}" for a in alarms)
        parts.append("")

    parts.append(f"### Vacantes nuevas — empresas objetivo ({len(company_jobs)})\n")
    if company_jobs:
        parts.extend(_render_job_row(j) for j in company_jobs)
    else:
        parts.append("_Sin novedades hoy en la lista de empresas._")

    parts.append(f"\n### Búsqueda por rol — fuente abierta ({len(role_search_jobs)})\n")
    parts.append(
        "_Vienen de agregadores públicos filtrados solo por título/keyword, "
        "no por una lista de empresas verificadas. La relevancia y "
        "compatibilidad quedan a tu criterio._\n"
    )
    if role_search_jobs:
        parts.extend(_render_job_row(j) for j in role_search_jobs)
    else:
        parts.append("_Sin novedades hoy en búsqueda por rol._")

    return "\n".join(parts)


def post_digest(subject: str, markdown_body: str):
    """Requiere GITHUB_TOKEN y GITHUB_REPOSITORY -- ambos ya los inyecta
    Actions automáticamente, no hay secrets que crear."""
    token = os.environ["GITHUB_TOKEN"]
    repo = os.environ["GITHUB_REPOSITORY"]

    issue_number = _get_or_create_issue(repo, token)
    body = f"## {subject}\n\n{markdown_body}"

    r = requests.post(
        f"{API_ROOT}/repos/{repo}/issues/{issue_number}/comments",
        json={"body": body},
        headers=_headers(token), timeout=10,
    )
    r.raise_for_status()
