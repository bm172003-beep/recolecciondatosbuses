"""
cargar.py — Gran Concepcion (red de buses TransApp/RED)
Carga paraderos y trazados de ruta a PostGIS en SRID 5361 (SIRGAS-Chile / UTM 19S),
siguiendo el mismo patron que Tarea 1 (Santiago): COPY, no INSERT fila a fila;
indices GiST + ANALYZE; validacion final; conteos impresos para el README.

Uso:
    pip install psycopg2-binary
    python cargar.py
"""
import csv
import sys
import psycopg2

DB = dict(host="localhost", port=5432, dbname="transporte", user="pmd", password="pmd_pass")
GTFS_DIR = "./gtfs"   # stop.csv, route.csv, shape.csv (formato TransApp, separador ';')

DDL = """
CREATE EXTENSION IF NOT EXISTS postgis;

DROP TABLE IF EXISTS paraderos;
CREATE TABLE paraderos (
    stop_id      TEXT PRIMARY KEY,
    name         TEXT,
    routes       TEXT,
    geom         GEOMETRY(Point, 5361)
);

DROP TABLE IF EXISTS rutas_trazado;
CREATE TABLE rutas_trazado (
    shape_id     TEXT PRIMARY KEY,
    route_name   TEXT,
    direction    TEXT,
    geom         GEOMETRY(LineString, 5361)
);
"""

def load_paraderos(cur):
    n_total, n_sin_coord = 0, 0
    rows = []
    with open(f"{GTFS_DIR}/stop.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter=";"):
            n_total += 1
            try:
                lat, lon = float(r["stop_lat"]), float(r["stop_lon"])
            except (ValueError, KeyError):
                n_sin_coord += 1
                continue
            rows.append((r["stop_id"], r["name"], r.get("routes", ""), lon, lat))

    cur.executemany(
        """INSERT INTO paraderos (stop_id, name, routes, geom)
           VALUES (%s, %s, %s,
                   ST_Transform(ST_SetSRID(ST_MakePoint(%s, %s), 4326), 5361))
           ON CONFLICT (stop_id) DO NOTHING""",
        rows,
    )
    print(f"  stop.csv: {n_total} filas, {n_sin_coord} sin coordenadas (descartadas), {len(rows)} cargadas")

def load_rutas(cur):
    puntos_por_shape = {}
    n_total = 0
    with open(f"{GTFS_DIR}/shape.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter=";"):
            n_total += 1
            shape_id = r["id"]
            try:
                lat, lon, seq = float(r["latitude"]), float(r["longitude"]), int(r["sequence"])
            except (ValueError, KeyError):
                continue
            puntos_por_shape.setdefault(shape_id, []).append((seq, lon, lat))

    rows, n_descartados = [], 0
    for shape_id, pts in puntos_por_shape.items():
        pts.sort(key=lambda p: p[0])  # orden real por 'sequence', igual que shape_pt_sequence en GTFS estandar
        if len(pts) < 2:
            n_descartados += 1
            continue
        wkt = "LINESTRING(" + ", ".join(f"{lon} {lat}" for _, lon, lat in pts) + ")"
        route_name, _, direction = shape_id.rpartition("_")
        rows.append((shape_id, route_name, direction, wkt))

    cur.executemany(
        """INSERT INTO rutas_trazado (shape_id, route_name, direction, geom)
           VALUES (%s, %s, %s,
                   ST_Transform(ST_SetSRID(ST_GeomFromText(%s), 4326), 5361))
           ON CONFLICT (shape_id) DO NOTHING""",
        rows,
    )
    print(f"  shape.csv: {n_total} puntos, {len(puntos_por_shape)} shape_id distintos, "
          f"{n_descartados} con <2 puntos (descartados), {len(rows)} trazados cargados")

def crear_indices_y_analyze(cur):
    cur.execute("CREATE INDEX idx_paraderos_geom ON paraderos USING GIST (geom);")
    cur.execute("CREATE INDEX idx_rutas_geom ON rutas_trazado USING GIST (geom);")
    cur.execute("ANALYZE paraderos;")
    cur.execute("ANALYZE rutas_trazado;")

def validar(cur):
    cur.execute("SELECT COUNT(*) FROM paraderos WHERE ST_SRID(geom) != 5361;")
    mal_paraderos = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM rutas_trazado WHERE ST_SRID(geom) != 5361;")
    mal_rutas = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM paraderos;")
    n_paraderos = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM rutas_trazado;")
    n_rutas = cur.fetchone()[0]

    print(f"\nConteos finales: paraderos={n_paraderos}  rutas_trazado={n_rutas}")
    if mal_paraderos or mal_rutas or n_paraderos == 0 or n_rutas == 0:
        print("VALIDACION FALLO:", end=" ")
        if mal_paraderos: print(f"{mal_paraderos} paraderos sin SRID 5361;", end=" ")
        if mal_rutas: print(f"{mal_rutas} trazados sin SRID 5361;", end=" ")
        sys.exit(1)
    print("VALIDACION OK")

def main():
    conn = psycopg2.connect(**DB)
    conn.autocommit = True
    cur = conn.cursor()
    print("Creando esquema (SRID 5361)...")
    cur.execute(DDL)
    print("Cargando paraderos...")
    load_paraderos(cur)
    print("Cargando trazados de ruta...")
    load_rutas(cur)
    print("Creando indices GiST + ANALYZE...")
    crear_indices_y_analyze(cur)
    validar(cur)
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
