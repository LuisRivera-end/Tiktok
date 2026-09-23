# Modelo de abandono temprano en Orange

El flujo [veta_modelado.ows](./veta_modelado.ows) usa los datos de `C:\Users\lelie\Downloads\veta_interactions.csv` para distinguir abandono temprano (`early_skip=1`) de finalización (`early_skip=0`). La exportación define abandono temprano como `skip` con `watch_ms < 2000`. En este CSV, los 1 888 eventos `skip` cumplen esa condición; no debe asumirse que todo `skip` futuro será temprano. El CSV original contiene 12 271 eventos de diversos tipos. Para modelar una decisión de visualización, se conservaron los 5 697 eventos terminales `skip` y `complete`.

## Archivos

- `veta_modelado.ows`: flujo de Orange con archivos de entrenamiento, prueba y datos completos; bosque aleatorio, regresión logística, Test and Score, matriz de confusión y ROC.
- `veta_terminal_train.tab` y `veta_terminal_test.tab`: partición de prueba por `session_id`. Las 373 sesiones de entrenamiento y 94 de prueba son distintas.
- `veta_terminal_all.tab`: todos los eventos terminales, con `early_skip` definido como objetivo en Orange.
- `veta_early_skip_model.pkcls`: modelo final compatible con **Load Model** de Orange, entrenado con todos los eventos terminales.
- `veta_early_skip_report.json`: métricas completas, distribución de clases y parámetros de evaluación.
- `model_veta.py`: script reproducible para regenerar estos archivos usando el Python incluido en Orange.

## Variables y evaluación

El modelo usa `user_role`, `user_region`, `video_region`, `category`, `audio_id`, `duration_s`, `is_ad` y `tags`. `duration_s` es `duration_ms / 1000`. Se excluyeron `event_type`, `watch_ms` y `completion_ratio` porque revelan lo ocurrido durante o después de la visualización; los identificadores tampoco se usan como predictores.

Se reservó el 20 % de las sesiones para una prueba independiente. Dentro del entrenamiento se usó validación cruzada de cuatro pliegues agrupada por sesión para elegir el modelo y el umbral de probabilidad. El bosque aleatorio fue el mejor por precisión promedio. Su umbral de clasificación es **0,24** para la clase `early_skip=1`.

| Métrica en 1 171 eventos de prueba | Resultado |
|---|---:|
| AUC ROC | 0,850 |
| Precisión promedio | 0,776 |
| Exactitud | 0,786 |
| Precisión para `early_skip=1` | 0,700 |
| Sensibilidad para `early_skip=1` | 0,731 |
| F1 para `early_skip=1` | 0,715 |

La matriz de confusión, con filas reales y columnas predichas en orden `0`, `1`, es `[[605, 135], [116, 315]]`. El archivo `.pkcls` devuelve probabilidades; para reproducir esta clasificación, marcar `early_skip=1` cuando su probabilidad sea al menos 0,24. El valor predeterminado de Orange puede usar 0,5 y producir otras cifras de precisión y sensibilidad.

Esta prueba mide sesiones nuevas dentro del mismo catálogo y población de usuarios. No demuestra todavía el desempeño con videos o usuarios completamente nuevos.

El generador de estos eventos sintéticos (`app.services.corpus.generate_events`) no llama a `rank_organic_feed`. Por eso, el cambio reciente del pipeline que descarta clips inelegibles antes de la recuperación y evita reciclar hashes duplicados no altera este CSV ni las métricas del clasificador. Sí puede cambiar qué clips entrega el feed; medir ese efecto requiere una evaluación aparte del recomendador.

Para revisar el trabajo, abra `veta_modelado.ows` en Orange. En **Test and Score**, elija la clase `1` para ver las métricas específicas de abandono. Los archivos `.tab` ya contienen la variable objetivo y los tipos de las columnas; no hace falta configurarlos de nuevo.
