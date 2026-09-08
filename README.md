# ATS Job Alert Pipeline

Pipeline diario de alertas de empleo, corriendo gratis en GitHub Actions,
con estado persistido como commits de git (sin base de datos externa).

Es una evolución de [Building a Zero-Cost Daily Job Alert Pipeline](https://dzone.com/articles/build-daily-job-alert-pipeline),
con tres mejoras principales sobre el original:

1. **Fuentes directas por ATS en vez de scraping de una tabla ajena.** El
   original hacía *regex parsing* de tablas markdown/HTML de un agregador
   de terceros, que fallaba en silencio si el formato cambiaba. Esta
   versión consulta directamente las APIs públicas de cada ATS
   (Greenhouse, Lever, Ashby, SmartRecruiters, Recruitee, Workable,
   Workday), con auto-descubrimiento por slug — no hay que mapear
   manualmente qué ATS usa cada empresa.
2. **Filtro por rol/keyword con scoring**, en vez de traer todo lo que
   aparece en la fuente. Las vacantes se puntúan contra tres familias de
   rol (Engineering Manager, Solutions/Platform Architect, Senior
   Software Engineer) y se ordenan por relevancia.
3. **Fallback por búsqueda de rol en fuente abierta.** Si la lista de
   empresas no trae resultados (o simplemente para ampliar el universo),
   el pipeline también busca directamente por keyword en agregadores
   públicos (Remotive, Arbeitnow), sin depender de que la empresa esté
   en la lista curada. Estos resultados se marcan aparte en el email —
   la decisión de compatibilidad queda del lado del usuario.

Además, mantiene lo que sí funcionaba bien del original: estado en git
(dedupe + ventana rodante de N días), idempotencia, y ahora una alarma
de salud de fuente (si un ATS que normalmente responde cae a 0, se
reporta como posible fallo, no como "no hay vacantes hoy").

## Estructura

```
ats-pipeline/
├── config.yaml                  # empresas objetivo + roles/keywords
├── requirements.txt
├── main.py                      # orquestador
├── src/
│   ├── ats_clients/
│   │   ├── base.py              # NormalizedJob (esquema común)
│   │   └── discovery.py         # auto-descubrimiento + normalización por ATS
│   ├── role_search.py           # fallback: búsqueda por rol en fuente abierta
│   ├── filter.py                # scoring por rol/keyword
│   ├── state.py                 # dedupe + ventana rodante (git-como-DB)
│   ├── health.py                # alarma de fuente en 0
│   └── notify.py                # email HTML
├── .github/workflows/daily.yml  # cron diario + commit de estado
├── seen_links.json              # estado (lo actualiza el propio workflow)
├── job_history.json             # estado
└── source_health.json           # estado
```

## Setup

1. Crea el repo en GitHub (vacío, sin README/gitignore desde la web para
   no chocar con los que ya trae esta carpeta) y súbele estos archivos:

   ```bash
   cd ats-pipeline
   git init
   git add .
   git commit -m "Initial commit: ATS job alert pipeline"
   git branch -M main
   git remote add origin https://github.com/<tu-usuario>/<tu-repo>.git
   git push -u origin main
   ```

   (Con GitHub CLI en vez de crear el repo desde la web:
   `gh repo create <tu-repo> --private --source=. --push`)

2. En GitHub, ve a *Settings → Secrets and variables → Actions* y crea:
   - `SMTP_HOST` (ej. `smtp.gmail.com`)
   - `SMTP_PORT` (ej. `587`)
   - `SMTP_USER` (tu correo)
   - `SMTP_PASS` (app password, no tu contraseña normal — para Gmail
     hay que generarlo en la configuración de seguridad de la cuenta)
   - `ALERT_TO` (a quién se envía el digest; puede ser el mismo `SMTP_USER`)
3. Al hacer push, el workflow ya queda registrado en la pestaña *Actions*
   del repo (no requiere ningún paso extra de "activación"). Corre solo
   a las 08:00 America/Bogota, y también puedes dispararlo manualmente
   desde *Actions → Daily Job Alert Pipeline → Run workflow*.
4. Verifica el primer run ahí mismo: si falla en el paso "Commit updated
   state" con un 403, revisa que el permiso `contents: write` del
   workflow no haya sido sobrescrito por una política de organización
   en *Settings → Actions → General → Workflow permissions*.

### Correrlo en local

```bash
pip install -r requirements.txt
export SMTP_HOST=smtp.gmail.com SMTP_PORT=587 SMTP_USER=... SMTP_PASS=... ALERT_TO=...
python main.py
```

## Empresas incluidas en `config.yaml`

Curadas con foco en empleabilidad desde Colombia, en cuatro grupos:

- **Fintech/SaaS consolidadas de LatAm**: Rappi, Addi, Bold, Habi,
  Truora, Finkargo, Akua, Siigo, Clara, Kavak, Nubank, Ualá, dLocal,
  Clip, MercadoLibre, VTEX, Despegar.
- **Edtech**: Platzi, Crehana.
- **Globales/EEUU con contratación confirmada en Colombia**: Twilio,
  Sezzle, Binance, CaseWare International (fintech canadiense de
  auditoría, con equipo de desarrollo activo en Bogotá/Medellín).
- **Consultoras/IT services con sede física en Colombia**: Globant,
  Encora, Endava, Nearsure, ThoughtWorks, Accenture, AspenView.

Cada entrada tiene un campo `confidence`:
- `confirmed`: se verificó manualmente el ATS y/o la contratación activa
  en Colombia durante la investigación de este proyecto.
- `candidate`: la empresa tiene señales fuertes de contratar en LatAm/Colombia
  (rondas recientes, presencia regional, reportes de Endeavor/unicornios),
  pero el ATS y la vigencia de vacantes las resuelve el `discovery` en
  cada corrida — no se verificaron manualmente una por una.

Puedes agregar más empresas a `config.yaml` con solo el slug; el
auto-descubrimiento intenta resolver el ATS solo. Si ninguna responde,
la empresa queda con 0 resultados y no rompe el pipeline (ver `health.py`).

## Roles/keywords

Definidos en `config.yaml` bajo `roles:` — actualmente Engineering
Manager, Solutions/Platform Architect y Senior Software Engineer.
Agregar un rol nuevo es solo agregar una entrada con su lista de
keywords; el scoring en `src/filter.py` es genérico.

## Qué no incluye (a propósito)

- ATS sin API pública confiable (SAP SuccessFactors, Oracle Taleo,
  Bizneo HR, JazzHR) — requerirían scraping HTML por empresa, más
  frágil; quedan fuera del alcance de este MVP.
- Autenticación/gestión de secretos más allá de variables de entorno de
  GitHub Actions — suficiente para un pipeline de un solo usuario.
