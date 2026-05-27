"""
Monitor de Licitaciones - Scraper
Consulta COMPR.AR y BAC buscando licitaciones de rubros médicos.
Corre diariamente via GitHub Actions.
"""

import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime, date
from pathlib import Path

# ─────────────────────────────────────────────
# CONFIGURACIÓN — editá esto a tu gusto
# ─────────────────────────────────────────────

PALABRAS_CLAVE = {
    "descartables": [
        "descartable", "jeringa", "aguja", "guante", "cateter", "catéter",
        "sonda", "tubo", "drenaje", "apósito", "aposito", "venda", "gasa",
        "sutura", "bisturi", "bisturí", "bata", "barbijo", "mascara", "máscara",
        "set de infusion", "set de infusión", "llave de tres vias", "llave de tres vías",
    ],
    "tecmed": [
        "equipo medico", "equipo médico", "monitor", "ventilador", "respirador",
        "desfibrilador", "ecógrafo", "ecografo", "tomógrafo", "tomografo",
        "resonancia", "rayos x", "rayos", "electrocardiografo", "electrocardiógrafo",
        "autoclave", "esterilizador", "laparoscopio", "endoscopio", "camilla",
        "silla de ruedas", "nebulizador", "oximetro", "oxímetro", "pulsioximetro",
        "bomba de infusion", "bomba de infusión", "incubadora", "lampara cialitica",
    ],
    "lab": [
        "reactivo", "laboratorio", "analizador", "centrifuga", "centrífuga",
        "microscopio", "tubos de ensayo", "pipeta", "cultivo", "microbiologia",
        "microbiología", "hematologia", "hematología", "bioquimica", "bioquímica",
        "tiras reactivas", "glucometro", "glucómetro", "hemograma", "urinalisis",
        "medio de cultivo", "agar", "suero", "plasma",
    ],
    "farmacia": [
        "farmacia", "medicamento", "fármaco", "farmaco", "antibiotico", "antibiótico",
        "vacuna", "insulina", "oncologico", "oncológico", "hemoderivado",
        "albumina", "solución fisiológica", "solucion fisiologica",
        "suero glucosado", "anestesico", "anestésico", "analgesico", "analgésico",
        "antipiretico", "antihipertensivo", "insumo farmacéutico", "insumo farmaceutico",
    ],
}

PORTALES = [
    {
        "id": "comprar",
        "nombre": "COMPR.AR",
        "url": "https://comprar.gob.ar",
        "color": "blue",
    },
    {
        "id": "bac",
        "nombre": "Buenos Aires Compras",
        "url": "https://buenosairescompras.gob.ar",
        "color": "teal",
    },
]

OUTPUT_FILE = Path("data/licitaciones.json")

# ─────────────────────────────────────────────
# CLASIFICACIÓN POR RUBRO
# ─────────────────────────────────────────────

def clasificar_rubro(texto: str) -> str:
    texto_lower = texto.lower()
    for rubro, palabras in PALABRAS_CLAVE.items():
        for p in palabras:
            if p in texto_lower:
                return rubro
    return "otros"

# ─────────────────────────────────────────────
# SCRAPER COMPR.AR
# ─────────────────────────────────────────────

def scrape_comprar() -> list[dict]:
    """
    Consulta la búsqueda pública de COMPR.AR (no requiere login).
    Busca procesos con apertura próxima.
    """
    licitaciones = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    # URL pública de procesos con apertura próxima
    url = "https://comprar.gob.ar/Compras.aspx?qs=W1HXHGH+OSd9IYRU8enSvp5OQMH2Cz3mU9hZi+A0aECfB+EWQF0rkIibVfzexIYx"

    try:
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        tabla = soup.find("table", {"id": lambda x: x and "gv" in x.lower()})
        if not tabla:
            # Intentar encontrar cualquier tabla con datos de procesos
            tablas = soup.find_all("table")
            for t in tablas:
                if t.find("tr") and len(t.find_all("tr")) > 3:
                    tabla = t
                    break

        if tabla:
            filas = tabla.find_all("tr")[1:]  # saltar header
            for fila in filas:
                celdas = fila.find_all("td")
                if len(celdas) >= 4:
                    nro = celdas[0].get_text(strip=True)
                    nombre = celdas[1].get_text(strip=True)
                    tipo = celdas[2].get_text(strip=True) if len(celdas) > 2 else ""
                    apertura = celdas[3].get_text(strip=True) if len(celdas) > 3 else ""
                    organismo = celdas[4].get_text(strip=True) if len(celdas) > 4 else ""

                    link_tag = celdas[0].find("a")
                    link = ""
                    if link_tag and link_tag.get("href"):
                        href = link_tag["href"]
                        if href.startswith("http"):
                            link = href
                        else:
                            link = f"https://comprar.gob.ar/{href.lstrip('/')}"

                    rubro = clasificar_rubro(nombre + " " + tipo)

                    licitaciones.append({
                        "nro": nro,
                        "nombre": nombre,
                        "tipo": tipo,
                        "apertura": apertura,
                        "organismo": organismo,
                        "estado": "proximo",
                        "rubro": rubro,
                        "portalId": "comprar",
                        "url": link or "https://comprar.gob.ar",
                        "fechaCarga": date.today().isoformat(),
                    })

    except Exception as e:
        print(f"[COMPR.AR] Error: {e}")

    # Si no se pudo raspar, buscar por palabras clave via URL de búsqueda
    if not licitaciones:
        licitaciones = scrape_comprar_busqueda()

    return licitaciones


def scrape_comprar_busqueda() -> list[dict]:
    """Búsqueda por palabras clave en COMPR.AR como fallback."""
    licitaciones = []
    headers = {"User-Agent": "Mozilla/5.0"}
    terminos_busqueda = ["medicamento", "laboratorio", "descartable", "reactivo", "farmacia"]

    for termino in terminos_busqueda[:2]:  # limitar para no sobrecargar
        try:
            url = f"https://comprar.gob.ar/Compras.aspx?qs=W1HXHGH+OSd9IYRU8enSvmPvNk8N7sYMFiWUh6UELZ0="
            resp = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(resp.text, "html.parser")
            # parsear resultados...
        except Exception as e:
            print(f"[COMPR.AR búsqueda '{termino}'] Error: {e}")

    return licitaciones


# ─────────────────────────────────────────────
# SCRAPER BAC (Buenos Aires Compras)
# ─────────────────────────────────────────────

def scrape_bac() -> list[dict]:
    """
    Consulta el portal de datos abiertos de BAC.
    No requiere login.
    """
    licitaciones = []
    headers = {"User-Agent": "Mozilla/5.0"}

    # API de datos abiertos GCBA
    url = "https://data.buenosaires.gob.ar/api/3/action/datastore_search"
    params = {
        "resource_id": "98b1b484-1a6f-42d3-bf97-8a8bc0748701",  # dataset BAC convocatorias
        "limit": 100,
        "sort": "fecha_apertura desc",
    }

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=20)
        data = resp.json()
        records = data.get("result", {}).get("records", [])

        for r in records:
            nombre = r.get("objeto_contratacion", r.get("nombre", ""))
            nro = r.get("nro_proceso", r.get("numero_proceso", ""))
            tipo = r.get("tipo_proceso", r.get("modalidad", ""))
            apertura = r.get("fecha_apertura", "")
            organismo = r.get("reparticion", r.get("organismo", ""))
            estado_raw = r.get("estado", "").lower()

            if "abiert" in estado_raw:
                estado = "abierto"
            elif "publicad" in estado_raw or "convocad" in estado_raw:
                estado = "nuevo"
            else:
                estado = "proximo"

            rubro = clasificar_rubro(nombre + " " + tipo)

            licitaciones.append({
                "nro": str(nro),
                "nombre": nombre,
                "tipo": tipo,
                "apertura": apertura,
                "organismo": organismo,
                "estado": estado,
                "rubro": rubro,
                "portalId": "bac",
                "url": "https://buenosairescompras.gob.ar",
                "fechaCarga": date.today().isoformat(),
            })

    except Exception as e:
        print(f"[BAC] Error API datos abiertos: {e}")
        # Fallback: scraping directo
        licitaciones = scrape_bac_directo()

    return licitaciones


def scrape_bac_directo() -> list[dict]:
    """Scraping directo de BAC como fallback."""
    licitaciones = []
    try:
        url = "https://buenosairescompras.gob.ar/LCMQ/LicitacionesAbiertas.aspx"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(resp.text, "html.parser")
        tabla = soup.find("table")
        if tabla:
            for fila in tabla.find_all("tr")[1:]:
                celdas = fila.find_all("td")
                if len(celdas) >= 3:
                    nombre = celdas[1].get_text(strip=True) if len(celdas) > 1 else ""
                    rubro = clasificar_rubro(nombre)
                    licitaciones.append({
                        "nro": celdas[0].get_text(strip=True),
                        "nombre": nombre,
                        "tipo": celdas[2].get_text(strip=True) if len(celdas) > 2 else "",
                        "apertura": celdas[3].get_text(strip=True) if len(celdas) > 3 else "",
                        "organismo": celdas[4].get_text(strip=True) if len(celdas) > 4 else "",
                        "estado": "abierto",
                        "rubro": rubro,
                        "portalId": "bac",
                        "url": "https://buenosairescompras.gob.ar",
                        "fechaCarga": date.today().isoformat(),
                    })
    except Exception as e:
        print(f"[BAC directo] Error: {e}")
    return licitaciones


# ─────────────────────────────────────────────
# AGREGAR NUEVO PORTAL (plantilla)
# ─────────────────────────────────────────────

def scrape_portal_custom(portal: dict) -> list[dict]:
    """
    Plantilla para agregar un portal nuevo.
    Copiá esta función, renombrala y adaptá la URL y el parsing.
    """
    licitaciones = []
    try:
        resp = requests.get(portal["url"], timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(resp.text, "html.parser")
        # TODO: adaptá el parsing a la estructura del portal
        # tabla = soup.find("table", {"class": "..."})
        # ...
    except Exception as e:
        print(f"[{portal['nombre']}] Error: {e}")
    return licitaciones


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Iniciando scraping...")

    todas = []

    # COMPR.AR
    print("  → Consultando COMPR.AR...")
    comprar = scrape_comprar()
    print(f"     {len(comprar)} licitaciones encontradas")
    todas.extend(comprar)

    # BAC
    print("  → Consultando Buenos Aires Compras...")
    bac = scrape_bac()
    print(f"     {len(bac)} licitaciones encontradas")
    todas.extend(bac)

    # Ordenar: primero las de rubro médico, después por estado
    orden_rubro = {"descartables": 0, "tecmed": 1, "lab": 2, "farmacia": 3, "otros": 4}
    orden_estado = {"nuevo": 0, "proximo": 1, "abierto": 2}
    todas.sort(key=lambda x: (
        orden_rubro.get(x["rubro"], 9),
        orden_estado.get(x["estado"], 9),
    ))

    # Estadísticas
    rubros_medicos = [l for l in todas if l["rubro"] != "otros"]
    print(f"\n  Total: {len(todas)} licitaciones ({len(rubros_medicos)} de rubros médicos)")

    # Guardar
    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    output = {
        "actualizacion": datetime.now().isoformat(),
        "total": len(todas),
        "licitaciones": todas,
        "portales": PORTALES,
    }
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"  ✓ Guardado en {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
