"""
Corrige el punto ciego del artículo original: un parser/fuente que
empieza a devolver 0 resultados de golpe no debe tratarse como
"no hay vacantes hoy", sino como una posible falla silenciosa.

Se guarda un historial corto de conteos por fuente (source_health.json,
también committeado como parte del patrón git-como-DB) y se compara el
run de hoy contra el promedio reciente.
"""
import json
from pathlib import Path

HEALTH_PATH = Path("source_health.json")
LOOKBACK_RUNS = 7
ZERO_ALARM_THRESHOLD = 3  # promedio mínimo de runs previos para que un 0 hoy dispare alarma


def load_health() -> dict:
    if not HEALTH_PATH.exists():
        return {}
    try:
        return json.loads(HEALTH_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_health(health: dict):
    HEALTH_PATH.write_text(json.dumps(health, indent=2, ensure_ascii=False), encoding="utf-8")


def check_and_update(source_name: str, today_count: int, health: dict) -> str | None:
    """
    Actualiza el historial de la fuente y devuelve un mensaje de alarma
    (str) si hoy vino en 0 pero el promedio reciente era saludable, o
    None si todo está normal.
    """
    history = health.get(source_name, [])
    avg_recent = sum(history) / len(history) if history else 0

    alarm = None
    if today_count == 0 and avg_recent >= ZERO_ALARM_THRESHOLD:
        alarm = (
            f"'{source_name}' devolvió 0 vacantes hoy, pero venía promediando "
            f"{avg_recent:.1f} en los últimos {len(history)} runs. Posible cambio "
            f"de formato/endpoint upstream -- revisar el cliente de este ATS."
        )

    history.append(today_count)
    health[source_name] = history[-LOOKBACK_RUNS:]
    return alarm
