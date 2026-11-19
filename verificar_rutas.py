"""
Verifica cuáles rutas del Gran Concepcion tienen buses activos AHORA MISMO
segun el endpoint synoptic/machines de la API TransApp/DTPR.

Uso:
    python verificar_rutas.py

Requiere:
    pip install requests

Lee route.csv (del GTFS descargado) para sacar la lista de rutas+direccion,
le pregunta a la API por cada una, y al final imprime un resumen +
lo guarda en un CSV para que puedan elegir con cuales rutas quedarse.
"""

import csv
import time
import requests
from datetime import datetime

# ---------- Configuracion ----------
ZONE_ID = "f083f24e-7fee-4fdc-9520-dbbdae877f07"  # Gran Concepcion
BASE_URL = f"https://phone.dtpr.transapp.cl/v7/phone/{ZONE_ID}/synoptic/machines"
GTFS_ROUTE_CSV = "route.csv"       # ajusta la ruta si esta en otra carpeta
PAUSA_SEGUNDOS = 1.5                # pausa entre requests para no saturar la API

HEADERS = {
    "Os-type": "Android",
    "App-Version": "2.5.1",
    "Accept": "application/json",
}


def obtener_rutas_unicas(path_csv):
    """Lee route.csv y devuelve una lista de tuplas (route_name, direction) sin repetir."""
    rutas = set()
    with open(path_csv, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            rutas.add((row["route_name"], row["direction"]))
    return sorted(rutas)


def consultar_ruta(route_name, direction):
    """Llama a synoptic/machines para una ruta+direccion. Devuelve la cantidad de buses activos."""
    params = {"route": route_name, "direction": direction}
    try:
        r = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        buses = data.get("machines", [])
        return len(buses), buses
    except Exception as e:
        print(f"  [error] {route_name} {direction}: {e}")
        return -1, []


def main():
    rutas = obtener_rutas_unicas(GTFS_ROUTE_CSV)
    ahora = datetime.now()
    salida_csv = f"estado_rutas_{ahora.strftime('%Y%m%d_%H%M')}.csv"

    print(f"Corrida: {ahora.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Verificando {len(rutas)} combinaciones de ruta+direccion...\n")

    resultados = []
    for i, (route_name, direction) in enumerate(rutas, start=1):
        cantidad, buses = consultar_ruta(route_name, direction)
        estado = "ACTIVA" if cantidad > 0 else ("SIN DATOS" if cantidad == 0 else "ERROR")
        print(f"[{i}/{len(rutas)}] {route_name:8s} dir={direction}  -> {estado} ({cantidad} buses)")
        resultados.append({
            "route_name": route_name,
            "direction": direction,
            "buses_activos": cantidad,
        })
        time.sleep(PAUSA_SEGUNDOS)

    # Guardar CSV de salida (un archivo por corrida, con fecha/hora en el nombre)
    with open(salida_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["route_name", "direction", "buses_activos"])
        writer.writeheader()
        writer.writerows(resultados)

    # Resumen final
    activas = [r for r in resultados if r["buses_activos"] > 0]
    activas.sort(key=lambda r: r["buses_activos"], reverse=True)

    print("\n=== RESUMEN ===")
    print(f"Hora de la corrida: {ahora.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Rutas con al menos 1 bus activo: {len(activas)} de {len(rutas)}")
    print("\nTop 10 rutas con mas buses activos ahora:")
    for r in activas[:10]:
        print(f"  {r['route_name']:8s} dir={r['direction']}  -> {r['buses_activos']} buses")

    print(f"\nResultado completo guardado en: {salida_csv}")
    print("Tip: corre este script varias veces en distintos horarios del dia")
    print("(ej. 8am, 1pm, 6pm, 10pm) y compara los CSV para ver que rutas")
    print("tienen actividad consistente durante el dia, no solo en un momento.")


if __name__ == "__main__":
    main()
