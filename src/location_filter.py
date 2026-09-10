"""
Filtra vacantes por compatibilidad geográfica. Se aplica por igual a las
vacantes de empresas objetivo y a las del fallback por rol -- ninguna de
las dos fuentes traía este chequeo antes (bug: role_search.py declaraba
un parámetro remote_only que nunca se usaba en el cuerpo de la función).

Política (todas las listas son configurables en config.yaml, sección
location_filter):
  1. Si remote_flag es explícitamente False (ej. Arbeitnow lo reporta) -> rechaza.
  2. Si el texto de ubicación contiene alguna exclude_keyword
     (ej. "us only", "onsite") -> rechaza, sin importar remote_flag.
  3. Si contiene alguna allow_keyword (ej. "remote", "latam", "colombia") -> acepta.
  4. Si el campo de ubicación viene vacío -> acepta (muchas vacantes remotas
     legítimas simplemente no lo especifican; preferimos no perderlas).
  5. Cualquier otro caso (una ciudad/país específico que no matcheó nada) ->
     rechaza -- es justo el ruido que se reportó (ciudades fuera de la
     región que tampoco aceptan remoto).
"""


def is_location_compatible(location: str, remote_flag, cfg: dict) -> bool:
    if not cfg.get("enabled", True):
        return True

    if remote_flag is False:
        return False

    location_lc = (location or "").lower().strip()

    exclude_kw = cfg.get("exclude_keywords", [])
    if any(kw.lower() in location_lc for kw in exclude_kw):
        return False

    allow_kw = cfg.get("allow_keywords", [])
    if any(kw.lower() in location_lc for kw in allow_kw):
        return True

    if not location_lc:
        return True

    return False
