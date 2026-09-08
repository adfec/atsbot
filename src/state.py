"""
Mismo patrón que el artículo original: dos archivos JSON committeados
por el propio workflow (ver .github/workflows/daily.yml), git como DB.

  seen_links.json  -> set plano de toda dedupe_key ya vista, solo para dedupe
  job_history.json -> ventana rodante (rolling_window_days) por categoría,
                       cada entrada con first_seen para poder expirar

Este módulo solo lee/escribe los JSON en disco; el commit/push lo hace
el workflow de GitHub Actions, igual que en el artículo original.
"""
import json
from datetime import datetime
from pathlib import Path

SEEN_LINKS_PATH = Path("seen_links.json")
JOB_HISTORY_PATH = Path("job_history.json")


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_state():
    seen = set(load_json(SEEN_LINKS_PATH, []))
    history = load_json(JOB_HISTORY_PATH, {})
    return seen, history


def cleanup_old_jobs(history: dict, max_days: int) -> dict:
    """Idéntico en espíritu al del artículo original: expira por first_seen."""
    today = datetime.now().date()
    cleaned = {}
    for category, jobs in history.items():
        cleaned[category] = []
        for job in jobs:
            first_seen = job.get("first_seen")
            if not first_seen:
                continue
            try:
                seen_date = datetime.fromisoformat(first_seen).date()
            except ValueError:
                continue
            if (today - seen_date).days <= max_days:
                cleaned[category].append(job)
    return cleaned


def update_state(seen: set, history: dict, new_jobs: list, max_days: int):
    """
    new_jobs: lista de NormalizedJob ya filtrados/puntuados (con
    .matched_role y .score ya anotados por src/filter.py).

    Devuelve (seen_actualizado, history_actualizado, jobs_realmente_nuevos)
    -- estos últimos son los que van al "novedades de hoy" del email,
    a diferencia de los que ya estaban en la ventana rodante.
    """
    today_iso = datetime.now().date().isoformat()
    brand_new = []

    for job in new_jobs:
        key = job.dedupe_key()
        category = job.matched_role or "sin_categoria"
        history.setdefault(category, [])

        if key not in seen:
            seen.add(key)
            brand_new.append(job)
            history[category].append({
                "first_seen": today_iso,
                "title": job.title,
                "company": job.company,
                "url": job.url,
                "location": job.location,
                "score": job.score,
                "source": job.source,
                "dedupe_key": key,
            })

    history = cleanup_old_jobs(history, max_days)
    return seen, history, brand_new


def persist(seen: set, history: dict):
    save_json(SEEN_LINKS_PATH, sorted(seen))
    save_json(JOB_HISTORY_PATH, history)
