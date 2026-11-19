# Proyecto semestral PMD — Red de buses Gran Concepción

Procesamiento Masivo de Datos · USM 2026-2 · Prof. Diego Ramírez · Paralelo 701
Integrantes: Javier Fernández · Benjamín Medina

Pipeline que combina dos familias: **Geoespacial (PostGIS)** sobre el GTFS estático
de la red RED/TransApp del Gran Concepción, y **Streaming (Redis/Upstash)** sobre la
telemetría en vivo de la misma API. Todo en **SRID 5361** (SIRGAS-Chile / UTM 19S),
como pide el curso.

## 0. Qué hay en esta carpeta

| Archivo | Qué hace |
|---|---|
| `docker-compose.yml` | Levanta PostGIS (Postgres 16 + PostGIS 3.4) |
| `cargar.py` | ETL: carga `gtfs/stop.csv` y `gtfs/shape.csv` a PostGIS, en 5361, con índices GiST + ANALYZE |
| `consultas.py` | Corre consultas espaciales de ejemplo + un `EXPLAIN ANALYZE` |
| `rutas.txt` | Las 190 rutas reales (una por línea), generadas directo desde `route.csv` — no editar a mano |
| `verificar_rutas.py` | Verifica cuáles rutas tienen buses activos ahora mismo (diagnóstico manual) |
| `collect.py` | Recolector de telemetría en vivo → Redis (Upstash). Ya corregido: usa direcciones `I`/`R` |
| `.github/workflows/collect.yml` | Cron que corre `collect.py` cada 10 min en GitHub Actions |
| `.env.example` | Plantilla de la variable `UPSTASH_REDIS_URL` (no subir el `.env` real) |
| `gtfs/` | Acá van `stop.csv`, `route.csv`, `shape.csv` (no se versionan, ver `.gitignore`) |
| `resultados/` | Salidas de `consultas.py` |

## 1. Reproducir desde cero (parte PostGIS)

Requisitos: Docker y Python 3.8+.

**Paso 1 — poner los datos fuente en `gtfs/`:**
Copia ahí `stop.csv`, `route.csv` y `shape.csv` (vienen de `gtfs_concepcion.zip`, el feed
estático de la red RED/TransApp Gran Concepción — zona `f083f24e-7fee-4fdc-9520-dbbdae877f07`).

**Paso 2 — levantar PostGIS y cargar:**
```bash
docker compose up -d --wait
pip install psycopg2-binary
python cargar.py
```
`cargar.py` crea las tablas `paraderos` (Point) y `rutas_trazado` (LineString), transforma
todo a SRID 5361, crea los índices GiST, corre `ANALYZE` y termina con `VALIDACIÓN OK`
(o falla explicando qué faltó — no hay que editar nada a mano).

**Paso 3 — correr las consultas:**
```bash
python consultas.py
```
Imprime paraderos cercanos a un punto, el top 10 de rutas más largas, y el plan de
ejecución (`EXPLAIN ANALYZE`) de la consulta de cercanía — para mostrar qué índice se usa.

**Consola SQL directa:** `docker compose exec db psql -U pmd -d transporte`
**Apagar:** `docker compose down` (los datos quedan) · `docker compose down -v` (borra todo)

## 2. Reproducir desde cero (parte Streaming)

**Paso 1 — crear la base Redis en Upstash** (gratis): https://upstash.com → Redis → crear
database → copiar la URL de conexión (`rediss://...`).

**Paso 2 — probar localmente:**
```bash
pip install requests redis
export UPSTASH_REDIS_URL="rediss://default:...@....upstash.io:..."
python collect.py
```
Debería imprimir `Eventos insertados en este ciclo: N` con N > 0 en horario de operación
de buses (día, no madrugada).

**Paso 3 — automatizar con GitHub Actions:**
1. En el repo de GitHub: Settings → Secrets and variables → Actions → New repository secret
   → nombre `UPSTASH_REDIS_URL`, valor la URL de Upstash.
2. Subir `.github/workflows/collect.yml` (ya incluido acá) — corre solo cada 10 min.
3. Verificar en la pestaña **Actions** que las corridas salgan en verde.
4. Importante: GitHub desactiva automáticamente un cron si el repo lleva 60+ días sin
   actividad. Si en algún momento ven "This scheduled workflow is disabled", hay que
   reactivarlo a mano desde esa misma pestaña, o simplemente hacer un commit.

## 3. Fuentes y versión

| Fuente | Qué es | Zona |
|---|---|---|
| GTFS estático RED/TransApp | `stop.csv` (2.256 paraderos), `route.csv` (190 rutas / 560 variantes), `shape.csv` (~19.000 puntos de trazado) | Gran Concepción, `public_id f083f24e-7fee-4fdc-9520-dbbdae877f07` |
| API en vivo (no oficial, reverse-engineered) | `synoptic/machines` — posición, patente, bearing de cada bus activo | Misma zona |

## 4. Decisiones

- **SRID.** Todo se transforma a 5361 al cargar (`ST_Transform` desde 4326), como pide el curso.
- **`rutas_trazado` por `shape_id`.** Cada combinación ruta+dirección (`<ruta>_<I|R>`) es una
  fila con su propia `LineString`, construida ordenando los puntos de `shape.csv` por `sequence`
  (equivalente a `shape_pt_sequence` del GTFS estándar).
- **Qué es un "paradero".** Se cargan todos los de `stop.csv` que tienen `stop_lat`/`stop_lon`
  válidos; los que no, se descartan y se cuentan en el log de `cargar.py`.
- **Riesgo principal y mitigación.** La fuente de telemetría en vivo es una API no oficial —
  por eso el proyecto se apoya principalmente en el GTFS estático (familia PostGIS, datos
  garantizados) y trata el streaming como familia complementaria.

## 5. Qué no funcionó (y se corrigió)

- `collect.py` llamaba a la API con direcciones `["I", "V"]`. La API solo acepta `I` (Ida) y
  `R` (Retorno) — `"V"` no existe, así que la mitad de las llamadas nunca trajo datos desde que
  empezó la automatización. Corregido a `["I", "R"]`.
- Un `rutas.txt` generado por IA (dos veces, de dos formas distintas) traía nombres de ruta
  inventados que no existen en `route.csv` real, y le faltaban rutas reales. Se reemplazó por
  uno generado directo desde `route.csv` (190 líneas, verificado).
