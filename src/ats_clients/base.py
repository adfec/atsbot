"""Esquema común al que se normaliza cada ATS."""
from dataclasses import dataclass, field


@dataclass
class NormalizedJob:
    company: str
    ats: str
    title: str
    url: str
    location: str = ""
    department: str = ""
    posted_at: str = ""              # ISO date si el ATS lo publica; si no, queda vacío
    description_snippet: str = ""
    raw_id: str = field(default="")  # id nativo del ATS, para dedupe estable
    source: str = "company"          # "company" (lista objetivo) o "role_search" (fallback)

    def dedupe_key(self) -> str:
        # Preferimos el id nativo del ATS cuando existe; si no, caemos a la URL.
        return f"{self.ats}:{self.company}:{self.raw_id or self.url}"
