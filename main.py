"""
Orquesta el pipeline completo:
  1. Para cada empresa en config.yaml: discovery/fetch de su ATS
  2. Fallback: búsqueda por rol en agregadores públicos (src/role_search.py)
  3. Filtro/scoring por rol-keyword (src/filter.py)
  4. Dedupe + ventana rodante (src/state.py) -- el commit del JSON lo hace
     el workflow de GitHub Actions, no este script
  5. Alarmas de salud de fuente (src/health.py)
  6. Email con el resumen del día (src/notify.py)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import yaml

from ats_clients import discovery
from filter import filter_and_rank
import health
import notify
import role_search
import state


def load_config():
    with open("config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def fetch_company_jobs(company_cfg: dict, health_state: dict, alarms: list):
    slug = company_cfg["slug"]

    if company_cfg.get("ats") == "workday":
        result = discovery.probe_workday(company_cfg["workday_tenant"])
    else:
        result = discovery.discover(slug)

    if not result:
        alarm = health.check_and_update(slug, 0, health_state)
        if alarm:
            alarms.append(alarm)
        return []

    ats_name, raw_jobs = result
    alarm = health.check_and_update(slug, len(raw_jobs), health_state)
    if alarm:
        alarms.append(alarm)

    return discovery.normalize(slug, ats_name, raw_jobs)


def main():
    config = load_config()
    roles_cfg = config["roles"]
    exclude_kw = config.get("exclude_keywords", [])
    location_cfg = config.get("location_filter", {})
    max_days = config.get("rolling_window_days", 10)

    seen, history = state.load_state()
    health_state = health.load_health()
    alarms: list[str] = []

    # 1. Empresas objetivo
    all_company_jobs = []
    for company_cfg in config["companies"]:
        all_company_jobs.extend(fetch_company_jobs(company_cfg, health_state, alarms))

    ranked_company_jobs = filter_and_rank(all_company_jobs, roles_cfg, exclude_kw, location_cfg)

    # 2. Fallback por rol (fuente abierta, no depende de la lista de empresas)
    ranked_role_search_jobs = []
    if config.get("role_search", {}).get("enabled", True):
        raw_role_jobs = role_search.run_role_search(roles_cfg)
        ranked_role_search_jobs = filter_and_rank(raw_role_jobs, roles_cfg, exclude_kw, location_cfg)

    # 3. Dedupe + ventana rodante (cada fuente actualiza el mismo estado)
    seen, history, new_company_jobs = state.update_state(
        seen, history, ranked_company_jobs, max_days
    )
    seen, history, new_role_search_jobs = state.update_state(
        seen, history, ranked_role_search_jobs, max_days
    )

    state.persist(seen, history)
    health.save_health(health_state)

    # 4. Notificación
    if new_company_jobs or new_role_search_jobs or alarms:
        md_body = notify.render_digest_markdown(new_company_jobs, new_role_search_jobs, alarms)
        notify.post_digest(
            subject=f"Alertas de empleo — {len(new_company_jobs)} empresas / "
                    f"{len(new_role_search_jobs)} por rol",
            markdown_body=md_body,
        )
        print(f"Enviado: {len(new_company_jobs)} de empresas, "
              f"{len(new_role_search_jobs)} por rol, {len(alarms)} alarmas.")
    else:
        print("Sin novedades hoy, no se envía email.")


if __name__ == "__main__":
    main()
