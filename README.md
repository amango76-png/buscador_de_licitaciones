# Monitor de Licitaciones Médicas 🏥

Scraper automático que revisa COMPR.AR y Buenos Aires Compras todos los días a las 7am y genera un dashboard con licitaciones de descartables, tecnología médica, laboratorio y farmacia.

---

## Instalación (10 minutos)

### Paso 1 — Crear el repositorio en GitHub

1. Entrá a [github.com](https://github.com) con tu cuenta
2. Click en **New repository**
3. Nombre: `licitaciones-monitor`
4. Marcá **Private** (para que tus credenciales no sean públicas)
5. Click **Create repository**

### Paso 2 — Subir los archivos

Opción A — desde la web de GitHub:
1. Arrastrá todos los archivos de esta carpeta al repositorio
2. Respetá la estructura de carpetas (`.github/workflows/`, `data/`)

Opción B — desde la terminal (si tenés Git instalado):
```bash
cd licitaciones-monitor
git init
git add .
git commit -m "primer commit"
git remote add origin https://github.com/TU-USUARIO/licitaciones-monitor.git
git push -u origin main
```

### Paso 3 — Activar GitHub Pages (para ver el dashboard)

1. En tu repositorio → **Settings** → **Pages**
2. Source: **Deploy from a branch**
3. Branch: `main` / `/ (root)`
4. Click **Save**
5. En unos minutos tu dashboard estará en: `https://TU-USUARIO.github.io/licitaciones-monitor`

### Paso 4 — Probar el scraper manualmente

1. En tu repositorio → pestaña **Actions**
2. Click en **Monitor de Licitaciones — Scraping Diario**
3. Click en **Run workflow** → **Run workflow**
4. Esperá ~2 minutos y revisá que el archivo `data/licitaciones.json` se actualizó

---

## Cómo agregar un portal nuevo

### 1. Agregar al `scraper.py`

Copiá la función `scrape_portal_custom` y adaptala:

```python
def scrape_hospital_austral() -> list[dict]:
    licitaciones = []
    try:
        resp = requests.get("https://url-del-portal.com/licitaciones", timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(resp.text, "html.parser")
        # Adaptá el parsing a la estructura del portal
        tabla = soup.find("table")
        for fila in tabla.find_all("tr")[1:]:
            celdas = fila.find_all("td")
            nombre = celdas[1].get_text(strip=True)
            licitaciones.append({
                "nro": celdas[0].get_text(strip=True),
                "nombre": nombre,
                "tipo": "Licitación Privada",
                "apertura": celdas[2].get_text(strip=True),
                "organismo": "Hospital Austral",
                "estado": "abierto",
                "rubro": clasificar_rubro(nombre),
                "portalId": "hospital_austral",
                "url": "https://url-del-portal.com/licitaciones",
                "fechaCarga": date.today().isoformat(),
            })
    except Exception as e:
        print(f"[Hospital Austral] Error: {e}")
    return licitaciones
```

### 2. Llamarla desde `main()`

```python
# En la función main(), agregá:
print("  → Consultando Hospital Austral...")
austral = scrape_hospital_austral()
print(f"     {len(austral)} licitaciones encontradas")
todas.extend(austral)
```

### 3. Agregar el portal a la lista `PORTALES`

```python
PORTALES = [
    # ... los existentes ...
    {
        "id": "hospital_austral",
        "nombre": "Hospital Austral",
        "url": "https://url-del-portal.com",
        "color": "purple",
    },
]
```

### 4. Hacer commit y push

El workflow lo levantará automáticamente al día siguiente, o podés correrlo manualmente desde Actions.

---

## Personalizar palabras clave

Editá el diccionario `PALABRAS_CLAVE` en `scraper.py` para afinar la clasificación:

```python
PALABRAS_CLAVE = {
    "descartables": ["jeringa", "guante", ...],
    "tecmed": ["monitor", "ventilador", ...],
    "lab": ["reactivo", "centrífuga", ...],
    "farmacia": ["medicamento", "antibiótico", ...],
}
```

---

## Horario del scraping

El workflow corre automáticamente:
- **Lunes a viernes**: 7:00am hora Argentina
- **Sábados**: 8:00am hora Argentina

Para cambiar el horario, editá `.github/workflows/scraping-diario.yml`:
```yaml
- cron: "0 10 * * 1-5"   # 10:00 UTC = 7:00am AR (UTC-3)
```

---

## Estructura del proyecto

```
licitaciones-monitor/
├── scraper.py                          # Script principal de scraping
├── requirements.txt                    # Dependencias Python
├── index.html                          # Dashboard web
├── data/
│   └── licitaciones.json               # Datos generados por el scraper
└── .github/
    └── workflows/
        └── scraping-diario.yml         # Automatización GitHub Actions
```
