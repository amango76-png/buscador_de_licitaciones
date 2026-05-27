"""
Monitor de Licitaciones - Scraper
Corre diariamente via GitHub Actions.
"""

import requests
from bs4 import BeautifulSoup
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
    {"id": "comprar",  "nombre": "COMPR.AR",   "url": "https://comprar.gob.ar",                          "color": "blue"},
    {"id": "garrahan", "nombre": "Garrahan",   "url": "https://compras.garrahan.gov.ar/Licitaciones/Llamado", "color": "coral"},
]

OUTPUT_FILE = Path("data/licitaciones.json")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def clasificar_rubro(texto: str) -> str:
    t = texto.lower()
    for rubro, palabras in PALABRAS_CLAVE.items():
        for p in palabras:
            if p in t:
                return rubro
    return "otros"

def fmt_fecha(raw: str) -> str:
    if not raw or raw == "None":
        return raw
    for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"]:
        try:
            return datetime.strptime(raw[:19], fmt[:len(raw[:19])]).strftime("%d/%m/%Y %H:%M")
        except Exception:
            continue
    return raw

def hacer_item(nro, nombre, tipo, apertura, organismo, estado, portalId, url) -> dict:
    return {
        "nro": str(nro or ""),
        "nombre": str(nombre or ""),
        "tipo": str(tipo or ""),
        "apertura": fmt_fecha(str(apertura or "")),
        "organismo": str(organismo or ""),
        "estado": estado,
        "rubro": clasificar_rubro(str(nombre or "") + " " + str(tipo or "")),
        "portalId": portalId,
        "url": url,
        "fechaCarga": date.today().isoformat(),
    }

# ─────────────────────────────────────────────
# COMPR.AR
# ─────────────────────────────────────────────

def scrape_comprar() -> list:
    licitaciones = []

    # API datos.gob.ar — dataset ONC procesos de compra
    endpoints = [
        "https://datos.gob.ar/api/3/action/datastore_search?resource_id=4b7447cb-3140-4c8e-a1c1-4a4288e3c0e1&limit=200",
        "https://datos.gob.ar/api/3/action/datastore_search?resource_id=27e9bc62-3ac9-4bca-9098-34ae42e5fd1e&limit=200",
    ]

    for url in endpoints:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            data = resp.json()
            records = data.get("result", {}).get("records", [])
            print(f"     COMPR.AR API: {len(records)} registros")
            for r in records:
                if not isinstance(r, dict):
                    continue
                nombre = r.get("objeto_del_proceso") or r.get("descripcion") or r.get("nombre_proceso") or ""
                if not nombre:
                    continue
                estado_raw = str(r.get("estado_proceso") or r.get("estado") or "").lower()
                if "publicad" in estado_raw or "llamad" in estado_raw:
                    estado = "nuevo"
                elif "abiert" in estado_raw:
                    estado = "abierto"
                else:
                    estado = "proximo"
                licitaciones.append(hacer_item(
                    nro       = r.get("numero_proceso") or r.get("nro_proceso") or r.get("id_proceso"),
                    nombre    = nombre,
                    tipo      = r.get("tipo_proceso") or r.get("clase_proceso"),
                    apertura  = r.get("fecha_apertura") or r.get("fecha_publicacion"),
                    organismo = r.get("unidad_operativa_de_contrataciones") or r.get("organismo"),
                    estado    = estado,
                    portalId  = "comprar",
                    url       = "https://comprar.gob.ar",
                ))
            if licitaciones:
                break
        except Exception as e:
            print(f"     COMPR.AR error ({url[-40:]}): {e}")

    print(f"     Total COMPR.AR: {len(licitaciones)}")
    return licitaciones

# ─────────────────────────────────────────────
# GARRAHAN
# ─────────────────────────────────────────────

def scrape_garrahan() -> list:
    licitaciones = []
    url = "https://compras.garrahan.gov.ar/Licitaciones/Llamado"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(resp.text, "html.parser")
        tabla = soup.find("table")
        if not tabla:
            print("     Garrahan: sin tabla en la página")
            return []
        filas = tabla.find_all("tr")[2:]  # saltar 2 filas de encabezado
        for fila in filas:
            celdas = fila.find_all("td")
            if len(celdas) < 5:
                continue
            anio     = celdas[0].get_text(strip=True)
            tipo     = celdas[1].get_text(strip=True)
            nro      = celdas[2].get_text(strip=True)
            nombre   = celdas[3].get_text(strip=True)
            apertura = celdas[4].get_text(strip=True)
            hora     = celdas[5].get_text(strip=True) if len(celdas) > 5 else ""
            if not nombre:
                continue
            link_tag = fila.find("a")
            link = url
            if link_tag and link_tag.get("href"):
                href = link_tag["href"]
                link = href if href.startswith("http") else "https://compras.garrahan.gov.ar" + href
            licitaciones.append(hacer_item(
                nro       = f"{anio}-{nro}",
                nombre    = nombre,
                tipo      = tipo,
                apertura  = f"{apertura} {hora}".strip(),
                organismo = "Hospital Garrahan",
                estado    = "proximo",
                portalId  = "garrahan",
                url       = link,
            ))
        print(f"     Garrahan: {len(licitaciones)} licitaciones")
    except Exception as e:
        print(f"     Garrahan error: {e}")
    return licitaciones

# ─────────────────────────────────────────────
# PLANTILLA PARA NUEVO PORTAL
# ─────────────────────────────────────────────
# Para agregar un portal nuevo:
# 1. Copiá esta función y renombrala
# 2. Adaptá la URL y el parsing
# 3. Llamala desde main()
# 4. Agregá el portal a la lista PORTALES arriba

def scrape_portal_nuevo(nombre_portal: str, url: str, portal_id: str) -> list:
    licitaciones = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(resp.text, "html.parser")
        tabla = soup.find("table")
        if not tabla:
            return []
        for fila in tabla.find_all("tr")[1:]:
            celdas = fila.find_all("td")
            if len(celdas) < 3:
                continue
            nombre = celdas[0].get_text(strip=True)
            if not nombre:
                continue
            licitaciones.append(hacer_item(
                nro=celdas[1].get_text(strip=True) if len(celdas) > 1 else "",
                nombre=nombre,
                tipo="",
                apertura=celdas[2].get_text(strip=True) if len(celdas) > 2 else "",
                organismo=nombre_portal,
                estado="proximo",
                portalId=portal_id,
                url=url,
            ))
    except Exception as e:
        print(f"     {nombre_portal} error: {e}")
    return licitaciones

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Iniciando scraping...")
    todas = []

    print("  → Consultando COMPR.AR...")
    todas.extend(scrape_comprar())

    print("  → Consultando Hospital Garrahan...")
    todas.extend(scrape_garrahan())

    # Verificar que todos los items son dicts válidos
    todas = [l for l in todas if isinstance(l, dict) and l.get("nombre")]

    # Ordenar: médicos primero, luego por estado
    orden_rubro  = {"descartables": 0, "tecmed": 1, "lab": 2, "farmacia": 3, "otros": 4}
    orden_estado = {"nuevo": 0, "proximo": 1, "abierto": 2}
    todas.sort(key=lambda x: (orden_rubro.get(x["rubro"], 9), orden_estado.get(x["estado"], 9)))

    medicos = [l for l in todas if l["rubro"] != "otros"]
    print(f"\n  ✓ Total: {len(todas)} licitaciones ({len(medicos)} de rubros médicos)")
    for rubro in ["descartables", "tecmed", "lab", "farmacia", "otros"]:
        n = len([l for l in todas if l["rubro"] == rubro])
        if n:
            print(f"    {rubro}: {n}")

    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps({
            "actualizacion": datetime.now().isoformat(),
            "total": len(todas),
            "licitaciones": todas,
            "portales": PORTALES,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"  ✓ Guardado en {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
