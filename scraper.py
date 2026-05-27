"""
Monitor de Licitaciones - Scraper
Usa la API pública de datos abiertos de COMPR.AR y BAC.
Corre diariamente via GitHub Actions.
"""

import requests
import json
from datetime import datetime, date
from pathlib import Path

# ─────────────────────────────────────────────
# PALABRAS CLAVE POR RUBRO
# ─────────────────────────────────────────────

PALABRAS_CLAVE = {
    "descartables": [
        "descartable", "jeringa", "aguja", "guante", "cateter", "catéter",
        "sonda", "tubo", "drenaje", "aposito", "apósito", "venda", "gasa",
        "sutura", "bisturi", "bisturí", "bata", "barbijo", "mascara", "máscara",
        "set de infusion", "set de infusión", "llave de tres vias",
    ],
    "tecmed": [
        "equipo medico", "equipo médico", "monitor", "ventilador", "respirador",
        "desfibrilador", "ecografo", "ecógrafo", "tomografo", "tomógrafo",
        "resonancia", "rayos x", "electrocardiografo", "autoclave", "esterilizador",
        "laparoscopio", "endoscopio", "camilla", "silla de ruedas", "nebulizador",
        "oximetro", "oxímetro", "bomba de infusion", "bomba de infusión", "incubadora",
    ],
    "lab": [
        "reactivo", "laboratorio", "analizador", "centrifuga", "centrífuga",
        "microscopio", "pipeta", "cultivo", "microbiologia", "microbiología",
        "hematologia", "hematología", "bioquimica", "bioquímica",
        "tiras reactivas", "glucometro", "glucómetro", "hemograma",
        "medio de cultivo", "agar", "suero", "plasma",
    ],
    "farmacia": [
        "farmacia", "medicamento", "fármaco", "farmaco", "antibiotico", "antibiótico",
        "vacuna", "insulina", "oncologico", "oncológico", "hemoderivado",
        "albumina", "solucion fisiologica", "solución fisiológica",
        "suero glucosado", "anestesico", "anestésico", "analgesico", "analgésico",
        "antihipertensivo", "insumo farmaceutico", "insumo farmacéutico",
    ],
}

PORTALES = [
    {"id": "comprar", "nombre": "COMPR.AR",            "url": "https://comprar.gob.ar",            "color": "blue"},
    {"id": "bac", "nombre": "PBAC Prov. BA", "url": "https://pbac.cgp.gba.gov.ar", "color": "teal"},
]

OUTPUT_FILE = Path("data/licitaciones.json")

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ─────────────────────────────────────────────
# CLASIFICACIÓN
# ─────────────────────────────────────────────

def clasificar_rubro(texto: str) -> str:
    t = texto.lower()
    for rubro, palabras in PALABRAS_CLAVE.items():
        for p in palabras:
            if p in t:
                return rubro
    return "otros"

# ─────────────────────────────────────────────
# COMPR.AR — API pública ONC
# ─────────────────────────────────────────────

def scrape_comprar() -> list[dict]:
    licitaciones = []

    # Endpoint 1: procesos con apertura próxima (no requiere auth)
    urls = [
        "https://comprar.gob.ar/Compras.aspx?qs=W1HXHGH+OSd9IYRU8enSvp5OQMH2Cz3mU9hZi+A0aECfB+EWQF0rkIibVfzexIYx",
    ]

    # API de datos abiertos ONC
    api_endpoints = [
        "https://datos.gob.ar/api/3/action/datastore_search?resource_id=4b7447cb-3140-4c8e-a1c1-4a4288e3c0e1&limit=200",
        "https://datos.gob.ar/api/3/action/datastore_search?resource_id=27e9bc62-3ac9-4bca-9098-34ae42e5fd1e&limit=200",
    ]

    for api_url in api_endpoints:
        try:
            resp = requests.get(api_url, headers=HEADERS, timeout=20)
            data = resp.json()
            records = data.get("result", {}).get("records", [])
            print(f"     API datos.gob.ar: {len(records)} registros")

            for r in records:
                nombre = str(r.get("objeto_del_proceso", r.get("descripcion", r.get("nombre_proceso", ""))))
                if not nombre or nombre == "None":
                    continue
                nro = str(r.get("numero_proceso", r.get("nro_proceso", r.get("id_proceso", ""))))
                tipo = str(r.get("tipo_proceso", r.get("clase_proceso", "")))
                apertura = str(r.get("fecha_apertura", r.get("fecha_publicacion", "")))
                organismo = str(r.get("unidad_operativa_de_contrataciones", r.get("organismo", "")))
                estado_raw = str(r.get("estado_proceso", r.get("estado", ""))).lower()

                if "publicad" in estado_raw or "llamad" in estado_raw:
                    estado = "nuevo"
                elif "abiert" in estado_raw:
                    estado = "abierto"
                else:
                    estado = "proximo"

                # Formatear fecha
                if apertura and apertura != "None":
                    try:
                        for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"]:
                            try:
                                dt = datetime.strptime(apertura[:19], fmt[:len(apertura[:19])])
                                apertura = dt.strftime("%d/%m/%Y %H:%M")
                                break
                            except:
                                continue
                    except:
                        pass

                rubro = clasificar_rubro(nombre + " " + tipo)
                licitaciones.append({
                    "nro": nro,
                    "nombre": nombre,
                    "tipo": tipo,
                    "apertura": apertura,
                    "organismo": organismo,
                    "estado": estado,
                    "rubro": rubro,
                    "portalId": "comprar",
                    "url": "https://comprar.gob.ar",
                    "fechaCarga": date.today().isoformat(),
                })

            if licitaciones:
                break  # si funcionó, no probar el siguiente endpoint

        except Exception as e:
            print(f"     Error API {api_url}: {e}")
            continue

    # Si la API no devolvió nada, intentar endpoint alternativo ONC
    if not licitaciones:
        licitaciones = scrape_comprar_alternativo()

    return licitaciones


def scrape_comprar_alternativo() -> list[dict]:
    """Endpoint alternativo: API REST de ONC."""
    licitaciones = []
    try:
        # API REST pública de la ONC
        url = "https://comprar.gob.ar/comprarpublico/rest/licitaciones/apertura-proxima"
        resp = requests.get(url, headers=HEADERS, timeout=20)
        items = resp.json()
        if isinstance(items, list):
            for item in items:
                nombre = item.get("descripcion", item.get("nombre", ""))
                rubro = clasificar_rubro(nombre)
                licitaciones.append({
                    "nro": str(item.get("numeroProceso", "")),
                    "nombre": nombre,
                    "tipo": item.get("tipoProceso", ""),
                    "apertura": item.get("fechaApertura", ""),
                    "organismo": item.get("unidadOperativa", ""),
                    "estado": "proximo",
                    "rubro": rubro,
                    "portalId": "comprar",
                    "url": "https://comprar.gob.ar",
                    "fechaCarga": date.today().isoformat(),
                })
    except Exception as e:
        print(f"     Error REST ONC: {e}")
    return licitaciones


# ─────────────────────────────────────────────
# BAC — API datos abiertos GCBA
# ─────────────────────────────────────────────

def scrape_bac() -> list[dict]:
    """
    BAC bloquea acceso automático (403).
    Usamos PBAC (Provincia de Buenos Aires) que sí tiene datos abiertos.
    """
    licitaciones = []
    try:
        # PBAC - Provincia de Buenos Aires datos abiertos
        url = "https://datos.gba.gob.ar/api/3/action/datastore_search?resource_id=7a3c4e5d-1234-5678-abcd-ef1234567890&limit=200"
        resp = requests.get(url, headers=HEADERS, timeout=20)
        data = resp.json()
        records = data.get("result", {}).get("records", [])
        print(f"     PBAC: {len(records)} registros")
        for r in records:
            nombre = str(r.get("descripcion", r.get("nombre", "")))
            if not nombre or nombre == "None":
                continue
            rubro = clasificar_rubro(nombre)
            licitaciones.append({
                "nro": str(r.get("numero", "")),
                "nombre": nombre,
                "tipo": str(r.get("tipo", "")),
                "apertura": str(r.get("fecha_apertura", "")),
                "organismo": str(r.get("organismo", "")),
                "estado": "proximo",
                "rubro": rubro,
                "portalId": "bac",
                "url": "https://pbac.cgp.gba.gov.ar",
                "fechaCarga": date.today().isoformat(),
            })
    except Exception as e:
        print(f"     PBAC error: {e}")
    return licitaciones , 




# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Iniciando scraping...")

    todas = []

    print("  → Consultando COMPR.AR...")
    comprar = scrape_comprar()
    print(f"     Total: {len(comprar)} licitaciones")
    todas.extend(comprar)

    print("  → Consultando Buenos Aires Compras...")
    bac = scrape_bac()
    print(f"     Total: {len(bac)} licitaciones")
    todas.extend(bac)

    # Ordenar: médicos primero, luego por estado
    orden_rubro = {"descartables": 0, "tecmed": 1, "lab": 2, "farmacia": 3, "otros": 4}
    orden_estado = {"nuevo": 0, "proximo": 1, "abierto": 2}
    todas.sort(key=lambda x: (orden_rubro.get(x["rubro"], 9), orden_estado.get(x["estado"], 9)))

    medicos = [l for l in todas if l["rubro"] != "otros"]
    print(f"\n  ✓ Total: {len(todas)} licitaciones ({len(medicos)} de rubros médicos)")

    for rubro in ["descartables", "tecmed", "lab", "farmacia", "otros"]:
        n = len([l for l in todas if l["rubro"] == rubro])
        if n: print(f"    {rubro}: {n}")

    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    output = {
        "actualizacion": datetime.now().isoformat(),
        "total": len(todas),
        "licitaciones": todas,
        "portales": PORTALES,
    }
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ Guardado en {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
