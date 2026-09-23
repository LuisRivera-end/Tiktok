# Orange Data Mining — Veta

El laboratorio exporta interacciones para Orange. Veta no calcula PCA ni k-Means: Orange sigue siendo la herramienta de escritorio.

## Cómo cargar los datos

1. Arranca la API (`docker compose up` o uvicorn local).
2. Entra con `viewer@veta.local` / `veta1234`.
3. Ve a **Laboratorio**. **Correr simulador** sigue escribiendo la pasada grande (80 × 5 × 8). **Inyectar ~1000 para Orange** añade una pasada aparte, de unas 1000 filas, sin borrar la anterior.
4. Pulsa **Descargar CSV para Orange**. El archivo es UTF-8, una fila por evento.
5. En Orange abre el widget **File** y elige `veta_interactions.csv`.

## Canalización

```
File (veta_interactions.csv)
  → Correlations   (watch_ms vs completion_ratio)
  → PCA            (2 componentes)
  → k-Means        (k = 4)
  → Scatter Plot
  → Test and Score (early_skip como clase)
```

`user_region` y `video_region` quedan como columnas discretas. No hace falta renombrarlas: el encabezado ya trae esos nombres (un prefijo de tipo de Orange, como `D#user_region`, solo si el widget File lo añade al mismo nombre).

## Columnas

| Columna | Uso |
|---|---|
| `user_region` | región de la cuenta, discreta |
| `video_region` | región del clip, discreta |
| `watch_ms` | correlación con `completion_ratio` |
| `duration_ms` | duración del clip |
| `completion_ratio` | correlación con `watch_ms` |
| `early_skip` | clase: 1 solo si el evento es `skip` y `watch_ms` < 2000 |
| `category` | categoría del clip |
| `event_type` | tipo de interacción |

Otras columnas del mismo archivo (`user_id`, `audio_id`, `is_ad`, `tags`) se pueden dejar como metadatos.

No copies cifras de un reporte anterior. Mide lo que salga de **este** CSV y de la mesa de señales del Laboratorio, incluido el desglose por región.
