"""
consultas.py — corre las consultas espaciales y muestra el plan (EXPLAIN ANALYZE)
de al menos una de ellas, como pide la pauta del curso.
"""
import psycopg2

DB = dict(host="localhost", port=5432, dbname="transporte", user="pmd", password="pmd_pass")

Q_CERCANOS = """
-- Paraderos a <=300 m de un punto (plaza de ejemplo en Concepcion), en SRID 5361 (metrico, sin ::geography)
SELECT stop_id, name, ROUND(ST_Distance(paraderos.geom, pt.geom)::numeric, 1) AS distancia_m
FROM paraderos, (SELECT ST_Transform(ST_SetSRID(ST_MakePoint(-73.0503, -36.8270), 4326), 5361) AS geom) pt
WHERE ST_DWithin(paraderos.geom, pt.geom, 300)
ORDER BY distancia_m;
"""

Q_LARGO_RUTAS = """
-- Largo real (m) de cada trazado de ruta, ya en metros porque 5361 es metrico
SELECT route_name, direction, ROUND(ST_Length(geom)::numeric) AS largo_m
FROM rutas_trazado
ORDER BY largo_m DESC
LIMIT 10;
"""

def main():
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()

    print("== Paraderos cercanos a un punto (<=300 m) ==")
    cur.execute(Q_CERCANOS)
    for row in cur.fetchall():
        print(row)

    print("\n== Top 10 rutas mas largas (m) ==")
    cur.execute(Q_LARGO_RUTAS)
    for row in cur.fetchall():
        print(row)

    print("\n== Plan de ejecucion (EXPLAIN ANALYZE) de la consulta de cercania ==")
    cur.execute("EXPLAIN ANALYZE " + Q_CERCANOS)
    for row in cur.fetchall():
        print(row[0])

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
