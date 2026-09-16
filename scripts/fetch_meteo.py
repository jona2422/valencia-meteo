#!/usr/bin/env python3
"""Vigilancia meteorologica e hidrologica de la Comunitat Valenciana.

Enfoque: lluvia intensa e inundacion. Solo biblioteca estandar, sin API keys.

Fuentes:
  - MeteoAlarm  -> avisos oficiales de AEMET en formato CAP, por zona (EMMA_ID).
  - Open-Meteo  -> precipitacion, CAPE, viento, presion en 28 puntos de vigilancia.
  - Open-Meteo Flood (GloFAS) -> caudal de rio y su percentil de retorno.
  - Open-Meteo Marine -> temperatura del mar, el combustible de una DANA.
  - Multi-modelo ECMWF / ICON-EU / AROME -> dispersion entre modelos = incertidumbre.
  - GDACS y prensa valenciana -> impacto real en el terreno.

Si una fuente falla se omite y el resto continua.
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
TIMEOUT = 45

# Las 11 zonas de aviso de AEMET en la Comunitat Valenciana (codigos EMMA_ID),
# mas las 6 zonas costeras. Filtrar por codigo y no por texto evita que se cuelen
# avisos de Almeria por coincidencias de nombre.
ZONAS = {
    "ES246": "Interior norte de Valencia", "ES247": "Litoral norte de Valencia",
    "ES248": "Interior sur de Valencia",   "ES249": "Litoral sur de Valencia",
    "ES242": "Interior norte de Castellón", "ES243": "Litoral norte de Castellón",
    "ES244": "Interior sur de Castellón",  "ES245": "Litoral sur de Castellón",
    "ES239": "Litoral norte de Alicante",  "ES240": "Interior de Alicante",
    "ES241": "Litoral sur de Alicante",
    "ES863": "Costa · Litoral sur de Valencia", "ES864": "Costa · Litoral norte de Valencia",
    "ES865": "Costa · Litoral sur de Castellón", "ES866": "Costa · Litoral norte de Castellón",
    "ES861": "Costa · Litoral sur de Alicante",  "ES862": "Costa · Litoral norte de Alicante",
}
# A que zona de aviso de AEMET pertenece cada punto de vigilancia. Sin este
# cruce el mapa sale verde mientras la cabecera dice naranja, porque el nivel del
# punto solo miraria la lluvia modelada e ignoraria el aviso oficial.
# El corte norte/sur en Valencia va aproximadamente por el Xuquer.
PUNTO_ZONA = {
    "valencia": "ES247", "paiporta": "ES247", "catarroja": "ES247",
    "alfafar": "ES247", "sedavi": "ES247", "massanassa": "ES247",
    "torrent": "ES247", "picanya": "ES247", "aldaia": "ES247", "sagunt": "ES247",
    "chiva": "ES246", "cheste": "ES246", "buñol": "ES246",
    "utiel": "ES246", "requena": "ES246", "llíria": "ES246",
    "algemesi": "ES249", "alzira": "ES249", "carlet": "ES249",
    "sueca": "ES249", "cullera": "ES249", "gandia": "ES249",
    "xativa": "ES248", "ontinyent": "ES248",
    "castello": "ES245", "alacant": "ES241", "denia": "ES239", "orihuela": "ES241",
}

NIVEL = {"green": 0, "yellow": 1, "orange": 2, "red": 3}
NIVEL_ES = {0: "verde", 1: "amarillo", 2: "naranja", 3: "rojo"}

# Escala de intensidad de precipitacion de AEMET, en mm/h.
INTENSIDAD = [(0.1, "sin lluvia"), (2, "débil"), (15, "moderada"),
              (30, "fuerte"), (60, "muy fuerte"), (10**9, "torrencial")]

# Umbrales de acumulado en 12 h (mm) usados por AEMET en el litoral mediterraneo.
UMBRAL_12H = {"amarillo": 40, "naranja": 80, "rojo": 120}
# Umbrales de intensidad horaria (mm/h).
UMBRAL_1H = {"amarillo": 15, "naranja": 30, "rojo": 60}

salud = []


def anota(fuente, ok, detalle=""):
    salud.append({"fuente": fuente, "ok": ok, "detalle": str(detalle)[:200]})
    print("  [%s] %s %s" % ("ok " if ok else "FALLA", fuente, detalle if not ok else ""))


class _Redirect(urllib.request.HTTPRedirectHandler):
    http_error_308 = urllib.request.HTTPRedirectHandler.http_error_301


_OPENER = urllib.request.build_opener(_Redirect)


def fetch(url, accept="*/*", intentos=3):
    ultimo = None
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Accept": accept,
                "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            })
            with _OPENER.open(req, timeout=TIMEOUT) as r:
                return r.read()
        except Exception as e:
            ultimo = e
            time.sleep(2 + 3 * i)
    raise ultimo


def fetch_json(url, intentos=3):
    return json.loads(fetch(url, "application/json", intentos).decode("utf-8", "replace"))


def cargar(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def guardar(nombre, obj):
    with open(os.path.join(DATA, nombre), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def intensidad(mmh):
    if mmh is None:
        return "sin dato"
    for techo, etiqueta in INTENSIDAD:
        if mmh < techo:
            return etiqueta
    return "torrencial"


def nivel_por_lluvia(mm_1h, mm_12h):
    """Traduce lluvia a nivel de aviso con los umbrales que usa AEMET."""
    n = 0
    for etiqueta, valor in (("amarillo", 1), ("naranja", 2), ("rojo", 3)):
        if (mm_1h or 0) >= UMBRAL_1H[etiqueta] or (mm_12h or 0) >= UMBRAL_12H[etiqueta]:
            n = max(n, valor)
    return n


def suma(valores):
    return round(sum(v for v in valores if v is not None), 1)


# --------------------------------------------------------------------------- #
# 1. Avisos oficiales (AEMET via MeteoAlarm, formato CAP)

def avisos():
    d = fetch_json("https://feeds.meteoalarm.org/api/v1/warnings/feeds-spain")
    ahora = datetime.now(timezone.utc)
    salida, por_zona = [], {}

    for w in d.get("warnings", []):
        a = w.get("alert", {})
        for i in a.get("info", []):
            if (i.get("language") or "").lower().startswith("en"):
                continue
            par = {p.get("valueName"): p.get("value") for p in i.get("parameter", [])}
            nivel_txt = (par.get("awareness_level") or "")
            color = "green"
            for c in NIVEL:
                if c in nivel_txt:
                    color = c
            tipo = (par.get("awareness_type") or "").split(";")[-1].strip()

            zonas = []
            for area in i.get("area", []):
                for gc in area.get("geocode", []):
                    if gc.get("valueName") == "EMMA_ID" and gc.get("value") in ZONAS:
                        zonas.append(gc["value"])
            if not zonas:
                continue

            try:
                fin = datetime.fromisoformat(i["expires"])
                ini = datetime.fromisoformat(i["onset"])
            except Exception:
                continue
            if fin < ahora:                    # ya caducado
                continue

            item = {
                "zonas": sorted(set(zonas)),
                "zonas_nombre": [ZONAS[z] for z in sorted(set(zonas))],
                "nivel": NIVEL.get(color, 0),
                "color": color,
                "tipo": tipo,
                "evento": i.get("event", ""),
                "desc": (i.get("headline") or "").strip(),
                "inicio": i["onset"],
                "fin": i["expires"],
                "activo": ini <= ahora <= fin,
            }
            if item["nivel"] == 0:             # los verdes son ruido: no son aviso
                continue
            salida.append(item)
            for z in item["zonas"]:
                if item["activo"] or ini <= ahora + timedelta(hours=36):
                    por_zona[z] = max(por_zona.get(z, 0), item["nivel"])

    # AEMET emite un aviso por zona, asi que el mismo fenomeno llega repetido 8 o
    # 10 veces. Se fusionan los que coinciden en tipo, nivel y horario: una sola
    # entrada con todas sus zonas se lee mucho mejor en una emergencia.
    fusion = {}
    for a in salida:
        k = (a["tipo"], a["nivel"], a["inicio"], a["fin"])
        if k in fusion:
            f = fusion[k]
            f["zonas"] = sorted(set(f["zonas"]) | set(a["zonas"]))
            f["zonas_nombre"] = sorted(set(f["zonas_nombre"]) | set(a["zonas_nombre"]))
            f["activo"] = f["activo"] or a["activo"]
        else:
            fusion[k] = dict(a)

    agrupados = sorted(fusion.values(),
                       key=lambda x: (-x["nivel"], not x["activo"], x["inicio"]))
    return agrupados, por_zona


# --------------------------------------------------------------------------- #
# 2. Situacion en cada punto de vigilancia

VARS_H = ("precipitation,precipitation_probability,cape,convective_inhibition,"
          "wind_speed_10m,wind_gusts_10m,wind_direction_10m,pressure_msl,"
          "relative_humidity_2m,dew_point_2m,temperature_2m")


def observacion(puntos, por_zona=None):
    lats = ",".join("%.4f" % p["lat"] for p in puntos)
    lons = ",".join("%.4f" % p["lon"] for p in puntos)
    url = ("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
           "&hourly=%s"
           "&daily=precipitation_sum,precipitation_hours,wind_gusts_10m_max"
           "&current=precipitation,temperature_2m,wind_speed_10m,wind_gusts_10m,"
           "wind_direction_10m,pressure_msl,relative_humidity_2m"
           "&timezone=Europe%%2FMadrid&forecast_days=3&past_days=1"
           % (lats, lons, VARS_H))
    datos = fetch_json(url)
    if isinstance(datos, dict):
        datos = [datos]

    salida = []
    for p, d in zip(puntos, datos):
        h = d.get("hourly", {})
        tiempos = h.get("time", [])
        lluvia = h.get("precipitation", [])
        ahora_local = datetime.now(timezone.utc) + timedelta(hours=2)
        marca = ahora_local.strftime("%Y-%m-%dT%H:00")
        try:
            k = tiempos.index(marca)
        except ValueError:
            k = min(range(len(tiempos)), key=lambda j: abs(
                (datetime.fromisoformat(tiempos[j]) - ahora_local.replace(tzinfo=None)).total_seconds()
            )) if tiempos else 0

        cur = d.get("current", {})
        prev12 = suma(lluvia[max(0, k - 11):k + 1])
        prev24 = suma(lluvia[max(0, k - 23):k + 1])
        sig6 = suma(lluvia[k + 1:k + 7])
        sig12 = suma(lluvia[k + 1:k + 13])
        sig24 = suma(lluvia[k + 1:k + 25])
        pico = max([(v or 0) for v in lluvia[k:k + 25]] or [0])

        capes = [c for c in h.get("cape", [])[k:k + 13] if c is not None]
        dirs = h.get("wind_direction_10m", [])
        dir_now = cur.get("wind_direction_10m")
        # Flujo de levante (E/SE): el aire humedo del Mediterraneo choca con el
        # relieve y dispara la lluvia orografica. Es la senal clasica de peligro.
        levante = dir_now is not None and 45 <= dir_now <= 135

        nivel_ahora = nivel_por_lluvia(cur.get("precipitation"), prev12)
        nivel_prev = nivel_por_lluvia(pico, max(sig12, sig24 * 0.7))
        zona = PUNTO_ZONA.get(p["id"], "")
        nivel_oficial = (por_zona or {}).get(zona, 0)

        salida.append({
            "id": p["id"], "nombre": p["nombre"], "comarca": p["comarca"],
            "cuenca": p["cuenca"], "prio": p["prio"], "lat": p["lat"], "lon": p["lon"],
            "lluvia_ahora": cur.get("precipitation"),
            "intensidad": intensidad(cur.get("precipitation")),
            "temp": cur.get("temperature_2m"),
            "humedad": cur.get("relative_humidity_2m"),
            "presion": cur.get("pressure_msl"),
            "viento": cur.get("wind_speed_10m"),
            "racha": cur.get("wind_gusts_10m"),
            "viento_dir": dir_now,
            "levante": levante,
            "acum_12h": prev12, "acum_24h": prev24,
            "prev_6h": sig6, "prev_12h": sig12, "prev_24h": sig24,
            "pico_mmh": round(pico, 1),
            "cape": round(max(capes), 0) if capes else None,
            "zona": zona,
            "zona_nombre": ZONAS.get(zona, ""),
            "nivel_oficial": nivel_oficial,
            "nivel_lluvia": max(nivel_ahora, nivel_prev),
            # Manda lo mas alto: el aviso de AEMET o lo que dice la propia lluvia.
            "nivel": max(nivel_ahora, nivel_prev, nivel_oficial),
            "serie": [round(v or 0, 1) for v in lluvia[max(0, k - 6):k + 25]],
            "serie_desde": tiempos[max(0, k - 6)] if tiempos else "",
        })
    return salida


# --------------------------------------------------------------------------- #
# 3. Caudal de rio (GloFAS). El percentil de retorno dice si el caudal previsto
#    es normal o excepcional para ese punto.

# Por debajo de este caudal (m3/s) el cociente contra el caudal habitual no es
# informativo: son arroyos practicamente secos.
CAUDAL_MINIMO = 5.0

RIOS = [
    ("Túria · València", 39.4699, -0.3763), ("Xúquer · Alzira", 39.1508, -0.4358),
    ("Magro · Carlet", 39.2242, -0.5194), ("Serpis · Gandia", 38.9675, -0.1817),
    ("Palància · Sagunt", 39.6797, -0.2769), ("Millars · Castelló", 39.9864, -0.0513),
    ("Segura · Orihuela", 38.0850, -0.9450), ("Xúquer · Cullera", 39.1642, -0.2519),
]


def caudales():
    lats = ",".join("%.4f" % r[1] for r in RIOS)
    lons = ",".join("%.4f" % r[2] for r in RIOS)
    d = fetch_json("https://flood-api.open-meteo.com/v1/flood?latitude=%s&longitude=%s"
                   "&daily=river_discharge,river_discharge_max&forecast_days=7&past_days=2"
                   % (lats, lons))
    if isinstance(d, dict):
        d = [d]
    salida = []
    for (nombre, la, lo), r in zip(RIOS, d):
        dia = r.get("daily", {})
        q = [v for v in dia.get("river_discharge", []) if v is not None]
        if not q:
            continue
        base = sorted(q)[len(q) // 2]
        pico = max(q)
        factor = round(pico / base, 2) if base else None
        # Un rio que pasa de 0.05 a 0.4 m3/s da un factor x8 que no significa nada:
        # con caudales minimos el cociente se dispara por ruido numerico. Para que
        # cuente como crecida hace falta ademas un caudal absoluto apreciable.
        significativo = pico >= CAUDAL_MINIMO
        if not significativo:
            nivel = 0
        elif factor and factor >= 5:
            nivel = 3
        elif factor and factor >= 3:
            nivel = 2
        elif factor and factor >= 1.8:
            nivel = 1
        else:
            nivel = 0
        salida.append({
            "nombre": nombre, "lat": la, "lon": lo,
            "fechas": dia.get("time", []),
            "caudal": [None if v is None else round(v, 2) for v in dia.get("river_discharge", [])],
            "actual": round(q[0], 2), "pico": round(pico, 2),
            # Cuanto se sale el pico de lo habitual de estos dias.
            "factor": factor,
            "significativo": significativo,
            "nivel": nivel,
        })
    return salida


# --------------------------------------------------------------------------- #
# 4. Dispersion entre modelos: si ECMWF, ICON y AROME no coinciden, la
#    prevision es incierta y conviene decirlo.

# AROME de Meteo-France queda fuera de dominio sobre Valencia (devuelve horas sin
# dato y totales irreales), asi que no entra. Estos cuatro si la cubren.
MODELOS = "ecmwf_ifs025,icon_eu,gfs_seamless,ukmo_seamless"
MODELO_NOMBRE = {"ecmwf_ifs025": "ECMWF", "icon_eu": "ICON-EU",
                 "gfs_seamless": "GFS", "ukmo_seamless": "UKMO"}


def modelos():
    d = fetch_json("https://api.open-meteo.com/v1/forecast?latitude=39.4699&longitude=-0.3763"
                   "&hourly=precipitation&models=" + MODELOS +
                   "&timezone=Europe%2FMadrid&forecast_days=3")
    h = d.get("hourly", {})
    series = {}
    for k, v in h.items():
        if k.startswith("precipitation_"):
            series[k.replace("precipitation_", "")] = [
                None if x is None else round(x, 2) for x in v]
    totales = {k: suma(v[:48]) for k, v in series.items()}
    vals = [v for v in totales.values() if v is not None]
    return {
        "horas": h.get("time", []),
        "series": series,
        "nombres": MODELO_NOMBRE,
        "totales_48h": totales,
        "minimo": min(vals) if vals else None,
        "maximo": max(vals) if vals else None,
        # Cuanto se separan los modelos entre si. Mucha separacion = prevision
        # poco fiable, y eso hay que decirlo en vez de dar una cifra falsa.
        "dispersion": round(max(vals) - min(vals), 1) if len(vals) > 1 else 0,
    }


def mar():
    d = fetch_json("https://marine-api.open-meteo.com/v1/marine?latitude=39.45&longitude=-0.28"
                   "&hourly=sea_surface_temperature,wave_height&timezone=Europe%2FMadrid"
                   "&forecast_days=2")
    h = d.get("hourly", {})
    sst = [v for v in h.get("sea_surface_temperature", []) if v is not None]
    olas = [v for v in h.get("wave_height", []) if v is not None]
    return {"sst": round(sst[0], 1) if sst else None,
            "sst_max": round(max(sst), 1) if sst else None,
            "ola": round(olas[0], 2) if olas else None,
            "ola_max": round(max(olas), 2) if olas else None}


# --------------------------------------------------------------------------- #
# 5. Impacto real: alertas globales de inundacion y prensa valenciana.

def localname(t):
    return t.rsplit("}", 1)[-1].lower()


def child_text(el, names):
    for ch in el:
        if localname(ch.tag) in names:
            t = (ch.text or "").strip()
            if t:
                return t
    return ""


def item_link(item):
    for ch in item:
        if localname(ch.tag) == "link":
            href = ch.get("href")
            if href:
                return href
            if (ch.text or "").strip():
                return ch.text.strip()
    return ""


def parse_date(s):
    if not s:
        return None
    try:
        dt = parsedate_to_datetime(s.strip())
        return (dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt).astimezone(timezone.utc)
    except Exception:
        pass
    try:
        dt = datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
        return (dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt).astimezone(timezone.utc)
    except Exception:
        return None


IMG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.I)


def parse_feed(raw):
    items, fuente = [], ""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return fuente, items
    for el in root.iter():
        if localname(el.tag) in ("channel", "feed"):
            for ch in el:
                if localname(ch.tag) == "title" and (ch.text or "").strip():
                    fuente = ch.text.strip()
                    break
        if fuente:
            break
    for el in root.iter():
        if localname(el.tag) not in ("item", "entry"):
            continue
        t = child_text(el, {"title"})
        link = item_link(el)
        if not (t and link):
            continue
        img = ""
        for ch in el.iter():
            if localname(ch.tag) in ("thumbnail", "content", "enclosure"):
                u = ch.get("url")
                if u and (ch.get("medium") == "image" or (ch.get("type") or "").startswith("image")
                          or re.search(r"\.(jpe?g|png|webp)", u, re.I)):
                    img = u
                    break
        if not img:
            for ch in el.iter():
                if localname(ch.tag) in ("description", "encoded", "summary"):
                    m = IMG_RE.search(ch.text or "")
                    if m:
                        img = m.group(1)
                        break
        items.append({"title": t, "link": link, "image": img,
                      "dt": parse_date(child_text(el, {"pubdate", "published", "updated", "date"}))})
    return fuente, items


# Palabras que marcan una noticia como relevante para esta vigilancia.
CLAVE = re.compile(
    r"\b(dana|gota fría|gota fria|lluvia|lluvias|tormenta|torment|temporal|inunda|"
    r"riada|barranc|barranco|desbord|granizo|pedrisco|aemet|alerta|aviso (rojo|naranja|amarillo)|"
    r"emergenc|112|evacua|anega|precipitac|caudal|embals|tromba|diluvi|es alert|"
    r"crecida|cauce|rambla|pluvi)", re.I)

VALENCIA = re.compile(
    r"\b(valencia|valència|castell[oó]|alicante|alacant|paiporta|catarroja|torrent|"
    r"chiva|utiel|requena|algemes[ií]|alzira|gandia|gandía|sagunt|sagunto|x[aà]tiva|"
    r"ontinyent|ribera|horta|safor|marina alta|marina baixa|vega baja|comunitat|"
    r"comunidad valenciana|p[aa][ií]s valenci|albufera|t[uú]ria|x[uú]quer|j[uú]car|magro)", re.I)


def noticias():
    fuentes = cargar(os.path.join(HERE, "fuentes.json"), {}).get("feeds", [])
    NOMBRES = {
        "www.lasprovincias.es": "Las Provincias", "www.eldiario.es": "elDiario.es CV",
        "apuntmedia.es": "À Punt", "valenciaplaza.com": "Valencia Plaza",
        "api2.rtve.es": "RTVE", "www.20minutos.es": "20minutos",
        "www.levante-emv.com": "Levante-EMV", "www.europapress.es": "Europa Press",
        "www.gdacs.org": "GDACS",
    }
    todas, relevantes = [], []
    for url in fuentes:
        host = urllib.parse.urlparse(url).hostname or url
        try:
            _, items = parse_feed(fetch(url, "application/rss+xml, application/xml, */*"))
            if not items:
                raise ValueError("sin items")
            for it in items[:60]:
                fila = {
                    "title": it["title"], "link": it["link"], "image": it["image"],
                    "source": NOMBRES.get(host, host),
                    "date": it["dt"].isoformat() if it["dt"] else "",
                }
                todas.append(fila)
                texto = it["title"]
                if CLAVE.search(texto) and (VALENCIA.search(texto) or "gdacs" not in host):
                    if host == "www.gdacs.org" and not VALENCIA.search(texto) \
                            and not re.search(r"spain|españa", texto, re.I):
                        continue
                    relevantes.append(fila)
            anota("prensa " + NOMBRES.get(host, host), True)
        except Exception as e:
            anota("prensa " + NOMBRES.get(host, host), False, e)

    vistos, limpio = set(), []
    for n in sorted(relevantes, key=lambda x: x["date"], reverse=True):
        k = n["title"].lower()[:70]
        if k in vistos:
            continue
        vistos.add(k)
        limpio.append(n)
    return limpio, sorted(todas, key=lambda x: x["date"], reverse=True)[:60]


# --------------------------------------------------------------------------- #

def main():
    os.makedirs(DATA, exist_ok=True)
    ahora = datetime.now(timezone.utc)
    puntos = cargar(os.path.join(HERE, "puntos.json"), {}).get("puntos", [])

    try:
        avs, por_zona = avisos()
        anota("avisos AEMET (MeteoAlarm)", True)
    except Exception as e:
        avs, por_zona = [], {}
        anota("avisos AEMET (MeteoAlarm)", False, e)

    try:
        obs = observacion(puntos, por_zona)
        anota("Open-Meteo (%d puntos)" % len(puntos), True)
    except Exception as e:
        obs = []
        anota("Open-Meteo", False, e)

    try:
        rios = caudales()
        rios.sort(key=lambda r: (-r["nivel"], -(r["pico"] or 0)))
        anota("caudales GloFAS", True)
    except Exception as e:
        rios = []
        anota("caudales GloFAS", False, e)

    try:
        mods = modelos()
        anota("multi-modelo", True)
    except Exception as e:
        mods = {}
        anota("multi-modelo", False, e)

    try:
        estado_mar = mar()
        anota("mar (SST/oleaje)", True)
    except Exception as e:
        estado_mar = {}
        anota("mar", False, e)

    noti, todas = noticias()

    # Nivel general: lo mas alto entre el aviso oficial y lo que dice la lluvia.
    nivel_oficial = max(por_zona.values()) if por_zona else 0
    nivel_obs = max([o["nivel"] for o in obs], default=0)
    nivel = max(nivel_oficial, nivel_obs)

    lloviendo = [o for o in obs if (o["lluvia_ahora"] or 0) >= 0.1]
    criticos = sorted([o for o in obs if o["nivel"] >= 1],
                      key=lambda x: (-x["nivel"], -(x["acum_12h"] or 0),
                                     -(x["prev_24h"] or 0)))

    resumen = {
        "nivel": nivel,
        "nivel_texto": NIVEL_ES[nivel],
        "nivel_oficial": nivel_oficial,
        "avisos_activos": sum(1 for a in avs if a["activo"]),
        "avisos_total": len(avs),
        "lloviendo": len(lloviendo),
        "puntos": len(obs),
        "max_acum_12h": max([o["acum_12h"] or 0 for o in obs], default=0),
        "max_prev_24h": max([o["prev_24h"] or 0 for o in obs], default=0),
        "max_cape": max([o["cape"] or 0 for o in obs], default=0),
        "levante": sum(1 for o in obs if o["levante"]),
        "zona_mas_expuesta": (max(obs, key=lambda o: (o["acum_12h"] or 0))["nombre"]
                              if obs else None),
        "zonas_con_aviso": sum(1 for o in obs if o["nivel_oficial"] >= 1),
        "origen_nivel": ("aviso oficial de AEMET" if nivel_oficial >= nivel_obs
                         else "lluvia observada y prevista"),
        "sst": estado_mar.get("sst"),
        "dispersion_modelos": mods.get("dispersion"),
    }

    hist = cargar(os.path.join(DATA, "history.json"), [])
    hist.append({"t": ahora.isoformat(), "nivel": nivel,
                 "lloviendo": len(lloviendo),
                 "max12": resumen["max_acum_12h"],
                 "avisos": resumen["avisos_activos"]})
    hist = hist[-3000:]

    guardar("alerts.json", {"updated": ahora.isoformat(), "items": avs, "por_zona": por_zona,
                            "zonas": ZONAS})
    guardar("obs.json", {"updated": ahora.isoformat(), "items": obs})
    guardar("rivers.json", {"updated": ahora.isoformat(), "items": rios})
    guardar("models.json", {"updated": ahora.isoformat(), **mods})
    guardar("sea.json", {"updated": ahora.isoformat(), **estado_mar})
    guardar("news.json", {"updated": ahora.isoformat(), "items": noti[:50], "todas": todas})
    guardar("history.json", hist)
    guardar("meta.json", {
        "updated": ahora.isoformat(),
        "resumen": resumen,
        "fuentes_ok": sum(1 for s in salud if s["ok"]),
        "fuentes_total": len(salud),
        "salud": salud,
        "umbrales": {"1h": UMBRAL_1H, "12h": UMBRAL_12H},
    })

    ok = sum(1 for s in salud if s["ok"])
    print("\nNIVEL: %s · %d avisos activos · %d puntos con lluvia · max 12h %.1f mm · CAPE %d"
          % (NIVEL_ES[nivel].upper(), resumen["avisos_activos"], len(lloviendo),
             resumen["max_acum_12h"], resumen["max_cape"]))
    print("fuentes %d/%d · %d noticias relevantes" % (ok, len(salud), len(noti)))

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write("nivel=%d\n" % nivel)
            f.write("alerta=%d\n" % (1 if salud and ok < len(salud) * 0.5 else 0))
            f.write("salud=%d/%d\n" % (ok, len(salud)))


if __name__ == "__main__":
    main()
