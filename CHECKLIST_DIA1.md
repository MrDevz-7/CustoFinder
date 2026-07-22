# Checklist — Día 1: Fundaciones de Backend

- [x] Estructura de carpetas creada (`api/`, `database/`, `scrapers/`,
      `analyzer/`, `tracker/`, `scheduler/`)
- [x] Docker Compose con Postgres para desarrollo local (archivo listo;
      probado equivalente con Postgres 16 nativo dentro del entorno de
      construcción — ver informe de cierre para el detalle)
- [x] `requirements.txt` completo y venv funcionando
- [x] `.env.example` documentado
- [x] Modelos SQLAlchemy completos (`Business`, `Lead`, `CompetitorInfo`,
      `PipelineEvent`, `SearchRun`)
- [x] Alembic inicializado + primera migración generada y aplicada
      (verificado contra Postgres real: 5 tablas + `alembic_version`)
- [ ] Cuenta de Google Cloud con Places API (New) habilitada + API key
      — **pendiente, requiere que tú la crees con tu cuenta de Google
      Cloud** (instrucciones en README.md)
- [x] `discover_businesses()` implementado y validado con datos simulados
      de la forma real de la API (sin acceso de red a Google desde este
      entorno de construcción — ver informe de cierre)
- [x] `POST /api/search` probado end-to-end contra Postgres real
      (SearchRun creado, upsert de Business sin duplicados, conteos
      correctos) — con datos simulados, pendiente de repetir con tu
      API key real
- [x] `GET /api/health` respondiendo (200 OK, verificado con curl)
- [x] `README.md` de setup desde cero
- [x] Informe de cierre de día para el PM
