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
   públicos (Remotive, Jobicy), sin depender de que la empresa esté
   en la lista curada. Estos resultados se marcan aparte en el digest —
   la decisión de compatibilidad queda del lado del usuario.

Además, mantiene lo que sí funcionaba bien del original: estado en git
(dedupe + ventana rodante de N días), idempotencia, y ahora una alarma
de salud de fuente (si un ATS que normalmente responde cae a 0, se
reporta como posible fallo, no como "no hay vacantes hoy").

La entrega es 100% nativa de GitHub: el digest se publica como
comentario en un Issue fijo del propio repo usando el `GITHUB_TOKEN`
que Actions ya provee en cada run — sin SMTP, sin app passwords, sin
ninguna credencial de cuenta personal.

Un filtro de ubicación/remoto (`src/location_filter.py`) descarta
vacantes en ciudades/países fuera de la región que tampoco aceptan
remoto — se aplica por igual a las vacantes de empresa y a las del
fallback por rol, ver la sección "Filtro de ubicación" más abajo.

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
│   └── notify.py                # publica el digest como comentario en un Issue de GitHub
├── .github/workflows/daily.yml  # cron diario + commit de estado
├── seen_links.json              # estado (lo actualiza el propio workflow)
├── job_history.json             # estado
├── source_health.json           # estado
└── digest_issue.json            # estado: número del issue fijo del digest
```

## Setup

1. Clona el proyecto, o crea el repo en GitHub (vacío, sin README/gitignore desde la web para no chocar con los que ya trae este proyecto) y súbele estos archivos:

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

2. Confirma los permisos del token: en el repo, ve a *Settings → Actions
   → General → Workflow permissions* y verifica que esté en "Read and
   write permissions". El workflow ya declara `permissions: contents:
   write` e `issues: write` explícitamente, pero una política de
   organización puede sobrescribirlo a nivel repo.
3. Activa **Watch → All Activity** (o al menos "Issues") en la página
   principal del repo. Así, cada comentario nuevo en el issue fijo
   "📋 Job Alerts — Log diario" te llega por correo o por la app de
   GitHub -- no hay ningún email que el pipeline gestione directamente,
   y por lo tanto **no hay secrets que crear**: `GITHUB_TOKEN` lo
   inyecta Actions automáticamente en cada run.
4. Al hacer push, el workflow ya queda registrado en la pestaña *Actions*
   del repo. Corre solo a las 08:00 America/Bogota, y también puedes
   dispararlo manualmente desde *Actions → Daily Job Alert Pipeline →
   Run workflow*.
5. Verifica el primer run ahí mismo: si falla con un 403 al crear el
   issue o al hacer push del estado, es el mismo punto del paso 2 --
   revisa "Workflow permissions" a nivel repo u organización.

### Correrlo en local

Fuera de Actions, `GITHUB_TOKEN`/`GITHUB_REPOSITORY` no existen solos --
necesitas un Personal Access Token con scope `repo` (o, más acotado,
`issues:write` si usas un fine-grained token) y exportar el nombre del
repo a mano:

```bash
pip install -r requirements.txt
export GITHUB_TOKEN=ghp_xxx
export GITHUB_REPOSITORY=tu-usuario/tu-repo
python main.py
```

## Empresas incluidas en `config.yaml`

Curadas con foco en empleabilidad desde Colombia, en cuatro grupos:

- **Fintech/SaaS consolidadas de LatAm**: Rappi, Addi, Bold, Habi,
  Truora, Finkargo, Akua, Siigo, Clara, Kavak, Nubank, Ualá, dLocal,
  Clip, MercadoLibre, VTEX, Despegar.
- **Edtech**: Platzi, Crehana.
- **Globales/EEUU**: Twilio, Sezzle, Binance, CaseWare International.
- **Consultoras/IT**: Globant,
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

## Filtro de ubicación

`config.yaml` bajo `location_filter:` controla qué vacantes se
consideran compatibles geográficamente, aplicado a ambas fuentes
(empresas y búsqueda por rol) antes del scoring por rol. Se evalúa
contra `location` + `department` combinados, porque varias empresas
globales codifican la región real en el nombre del equipo (ej. "APAC
Engineering") en vez de en la ubicación:

- `allow_keywords`: si el texto combinado contiene alguna (ej.
  "remote", "latam", "colombia", "anywhere"), se acepta.
- `exclude_keywords`: si contiene alguna (ej. "us only", "onsite",
  "hybrid", o un país/ciudad concreto como "india", "germany"), se
  descarta sin importar lo demás.
- Ubicación+departamento vacíos → se acepta (muchas vacantes remotas
  legítimas no lo especifican).
- Cualquier otro caso (una ciudad/país específico que no matcheó
  nada) → se descarta.

Es un filtro con substrings, sin distinguir mayúsculas — ajusta las
listas directamente en `config.yaml` si ves falsos positivos o
negativos.

**Fallback:** Remotive y Jobicy.

**Fuentes evaluadas y descartadas** (sin API pública gratuita
verificable): Tecla, Magneto365, Torre.ai, Indeed.

## Qué no incluye (a propósito)

- ATS sin API pública confiable (SAP SuccessFactors, Oracle Taleo,
  Bizneo HR, JazzHR) — requerirían scraping HTML por empresa, más
  frágil; quedan fuera del alcance de este MVP.
- LinkedIn — no tiene API pública de vacantes y prohíbe explícitamente
  el scraping en sus términos de servicio; la única vía legítima es
  LinkedIn Talent Solutions, que requiere ser partner aprobado.
- Cualquier secret o credencial externa — la entrega usa únicamente
  el `GITHUB_TOKEN` que Actions inyecta solo, sin SMTP ni API keys de
  terceros que gestionar o rotar.
