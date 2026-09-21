# Orange Data Mining — Veta

El Capítulo III del reporte usa Orange para correlación, PCA y K-Means **antes** de defender el ranking. Veta no reemplaza Orange: exporta el mismo tipo de tabla.

## Cómo cargar los datos

1. Arranca la API (`docker compose up` o uvicorn local).
2. Entra con `viewer@veta.local` / `veta1234`.
3. Ve a **Laboratorio** y pulsa **Correr simulador** (genera eventos sintéticos en Mongo).
4. Pulsa **Descargar CSV para Orange**.
5. En Orange: *File* → elige `veta_interactions.csv`.

## Canalización sugerida (Cap. III)

```
File (veta_interactions.csv)
  → Select Columns
  → Continuize / Impute
  → Correlations   (watch_ms vs completion_ratio)
  → PCA            (2 componentes)
  → k-Means        (k = 4)
  → Scatter Plot
  → Test and Score (si clasificas early_skip)
```

Columnas útiles:

| Columna | Uso en Orange |
|---|---|
| `watch_ms`, `completion_ratio` | correlación de retención |
| `early_skip` | clase de abandono < 2 s |
| `category` | color en scatter / diversidad |
| `is_ad` | comparar retención con y sin anuncio |
| `user_id` | agrupar perfiles |

No copies los números 58.7 min / AUC 0.912 del reporte. Mide los que salgan de **este** CSV.
