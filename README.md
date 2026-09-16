# VIGILÀNCIA — lluvia e inundación en la Comunitat Valenciana

Panel de seguimiento en tiempo real de lluvia, tormentas e inundación en Valencia,
Castellón y Alicante. Estático, sin servidor y sin API keys: un robot de GitHub Actions
corre **cada 15 minutos**, escribe JSON en `data/` y GitHub Pages sirve el sitio.

**En vivo:** https://jona2422.github.io/valencia-meteo/

> Herramienta de seguimiento, **no una fuente oficial**. En una emergencia manda siempre
> AEMET, el 112 de la Generalitat y Emergencias GVA.

## Qué mira

| Vista | Contenido |
|---|---|
| **Ahora** | Nivel general, mapa de situación, zonas más expuestas, avisos en vigor, ingredientes atmosféricos |
| **Avisos AEMET** | Avisos oficiales por zona, agrupados y con horario |
| **Zonas** | Los 28 puntos de vigilancia con acumulados, previsión, pico e inestabilidad |
| **Ríos** | Caudal previsto y cuánto se sale de lo normal |
| **Modelos** | ECMWF, ICON-EU, GFS y UKMO comparados: su desacuerdo mide la incertidumbre |
| **Noticias** | Prensa valenciana filtrada + accesos a cuentas oficiales de X |

## Fuentes

| Fuente | Aporta |
|---|---|
| **AEMET** vía MeteoAlarm (CAP) | Avisos oficiales por zona (EMMA_ID) |
| **Open-Meteo** | Precipitación, CAPE, viento, presión en 28 puntos |
| **Open-Meteo Flood** (GloFAS/Copernicus) | Caudal de 8 puntos de río |
| **Open-Meteo Marine** | Temperatura del mar y oleaje |
| Las Provincias, Levante-EMV, elDiario CV, À Punt, Valencia Plaza, RTVE, Europa Press, 20minutos | Impacto real |
| **GDACS** | Alertas globales de inundación |

Ninguna necesita clave. Si una falla, se omite y la corrida continúa.

## Criterio meteorológico

**Umbrales de aviso** (los que usa AEMET en el litoral mediterráneo):

| Nivel | Intensidad | Acumulado 12 h |
|---|---|---|
| Amarillo | 15 mm/h | 40 mm |
| Naranja | 30 mm/h | 80 mm |
| Rojo | 60 mm/h | 120 mm |

El nivel de cada punto es **el mayor** entre el aviso oficial de AEMET para su zona y lo que
indica la lluvia medida y prevista. Así el panel nunca queda por debajo del aviso oficial,
pero puede subir por encima si la lluvia real lo justifica.

**Los 28 puntos** se eligieron por cuenca, no por población: incluyen las cabeceras de
barranco (Chiva, Cheste) que alimentan l'Horta Sud, y los municipios golpeados por la DANA
del 29 de octubre de 2024.

**Ingredientes que se vigilan**: temperatura del mar (la humedad disponible), CAPE
(la inestabilidad) y flujo de levante (el mecanismo que empuja el aire húmedo contra el
relieve). Cuando coinciden los tres y la tormenta se queda quieta sobre una cuenca es
cuando se desborda un barranco.

## Limitaciones conocidas

- **GloFAS es un modelo global de malla amplia.** Sirve para tendencia, no sustituye a los
  aforos del **SAIH del Júcar**, que miden en tiempo real y son la referencia oficial. El
  SAIH no expone una API pública, por eso no está integrado.
- **AROME de Météo-France queda fuera de dominio** sobre Valencia (devuelve horas sin dato);
  se excluyó a propósito para no dar cifras irreales.
- **X no tiene API gratuita**, así que la vista de noticias enlaza a cuentas y búsquedas
  en lugar de incrustar publicaciones.
- Ningún modelo global resuelve una tormenta de pocos kilómetros: pueden acertar el día y
  fallar el sitio por 20 km.

## Correr en local

```sh
python3 scripts/fetch_meteo.py    # baja datos a data/
python3 -m http.server 8877       # abrir http://localhost:8877
```
