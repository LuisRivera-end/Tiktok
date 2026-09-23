# Modelos de recomendación exploratorios en Orange

Estos archivos usan `C:\Users\lelie\Downloads\veta_interactions.csv`, exportado del laboratorio de Veta. **Puntúan candidatos para ordenar posibles siguientes categorías o videos**. El CSV no contiene `ts` ni `feed_position`, por lo que no registra la secuencia verificable de videos y no permite entrenar una etiqueta de «el siguiente video real».

## Qué abrir en Orange

| Carpeta | Flujo | Resultado |
|---|---|---|
| `categoria/` | `flujo.ows` | Probabilidad de completar un video de una categoría candidata. Se pueden ordenar las categorías por esta probabilidad. |
| `video/` | `flujo.ows` | Probabilidad de completar un video candidato con su categoría, región, audio, duración y gustos previos. |
| `publicidad/` | `flujo.ows` | Exploración de respuestas a la única campaña y un puntaje de afinidad orgánica. No hay modelo publicitario supervisado validado. |

La sesión de Orange que estaba abierta se guardó como `sesion_previa_usuario.ows`. Cada flujo nuevo tiene un widget **File** para entrenamiento, otro para prueba y un **Test and Score** configurado con usuarios de prueba separados. En `categoria/` y `video/`, `model.pkcls` carga el modelo final con **Load Model**. `resultados.json` contiene las métricas y la lista de variables. `all.tab`, `train.tab` y `test.tab` conservan tipos y objetivo para Orange.

## Datos y preparación

- CSV original: **12 271 filas**. Hay **5 040 duplicados exactos** entre sus 17 columnas. El exportador no incluye ID de evento, hora ni posición.
- El exportador de la aplicación ya se actualizó para añadir `event_id`, `event_ts` y `feed_position` **en descargas futuras**. El archivo usado en estos experimentos sigue teniendo 17 columnas; se necesita una descarga nueva y suficientes interacciones nuevas para entrenar y evaluar una secuencia real.
- Para categorías y videos se conservaron los eventos `complete` y `skip` **orgánicos simulados** con día `0` a `4` al final de `session_id`. Había 4 874 filas elegibles. Se colapsaron observaciones indistinguibles del simulador repetido mediante usuario, día, video, tipo de evento, tiempo visto y duración: quedaron 2 308. El día 0 sirve para crear historial; los días 1–4 aportan **1 800 filas de entrenamiento/evaluación** de 80 usuarios.
- Objetivo `complete_response`: `1` si el evento fue `complete`, `0` si fue `skip`. Es una aproximación de retención por exposición observada. `heartbeat`, acciones sociales e impresiones quedan fuera porque no equivalen a una decisión final de completar o saltar.
- Los gustos de cada fila solo usan eventos orgánicos de **días anteriores del mismo usuario**. Se calculan tasas suavizadas de finalización por categoría, región y en total, junto con el volumen de historial. Ningún evento del día objetivo entra en sus propias variables.
- `event_type`, `watch_ms`, `completion_ratio`, `early_skip`, los identificadores y `campaign_id` se excluyen de los predictores. Los identificadores permanecen como metadatos para auditoría.

Se reservaron **16 usuarios completos** para prueba y 64 para entrenamiento; ninguno aparece en ambos conjuntos. La elección entre bosque aleatorio y regresión logística se hizo con validación cruzada agrupada por usuario dentro del entrenamiento. El modelo final en `.pkcls` se volvió a ajustar con las 1 800 filas; para revisar rendimiento use `test.tab` y las métricas del modelo entrenado solo con `train.tab`, como hace **Test and Score**.

## Resultados medidos

| Tarea | Filas de prueba | AUC ROC | Exactitud | Referencia sencilla |
|---|---:|---:|---:|---:|
| Categoría candidata | 389 | 0,727 | 0,715 | 0,656 si siempre se predice la clase mayoritaria |
| Video candidato | 389 | 0,979 | 0,913 | 0,897 con la sola regla «misma región» |

Ambos resultados provienen de **datos del simulador**, no de una prueba del feed en producción. En particular, el generador hace que la coincidencia de región explique gran parte de la finalización; por eso el AUC del video puede verse alto sin demostrar una mejora real de retención. La evaluación cubre usuarios no vistos en entrenamiento, pero usa el mismo catálogo sintético y exposiciones observadas. Tampoco mide si elegir el primer video del ranking supera al algoritmo actual: faltan candidatos no mostrados, sus probabilidades de exposición y una comparación A/B.

Al abrir el flujo, **Test and Score** vuelve a entrenar el bosque con la configuración de Orange y puede mostrar diferencias pequeñas por la semilla aleatoria (por ejemplo, AUC ~0,726 para categoría y ~0,977 para video). Los valores de la tabla proceden del script reproducible y de `resultados.json`.

## Publicidad

El CSV tiene **una campaña, un video publicitario y 77 impresiones de anuncio**. De 81 eventos terminales de anuncio quedaron 61 observaciones distinguibles. Solo **dos usuarios** aportan finalizaciones positivas. Con estos datos, un clasificador que «elija la siguiente publicidad» tendría una evaluación engañosa y no podría comparar campañas.

Además, los 81 eventos terminales superan las 77 impresiones registradas: el export no da un ID de impresión para reconciliarlos uno a uno. Por eso tampoco se calcula una tasa publicitaria fiable a partir de esas dos cuentas.

`publicidad/afinidad.tab` y su flujo muestran un puntaje transparente:

`0,7 × tasa suavizada de finalización orgánica de la categoría + 0,3 × tasa suavizada orgánica general`.

Es **afinidad exploratoria**, no una probabilidad de clic, compra o retención del anuncio. El CSV tampoco permite demostrar que el historial orgánico ocurrió antes de cada impresión publicitaria. El puntaje no sustituye las reglas de la subasta actual: campañas activas, presupuesto, segmentación, frecuencia, repetición y puja. Para entrenar un modelo publicitario habría que registrar varias campañas y creatividades, `impression_id`, momento de exposición, usuario, candidato elegible, posición, clic, tiempo visto y retención posterior, además de suficientes respuestas por usuario y campaña.

## Ejemplo de «siguiente» candidato

`ejemplo_ranking.json` puntúa para un usuario del CSV **15 categorías, 174 videos que no había visto y la única campaña** como si fuera el día 5. Lo genera `ejemplo_recomendaciones.py`. Filtra IDs de video vistos en el CSV; el export no contiene estado activo, bloqueos ni `content_hash`, por lo que este ejemplo no puede aplicar todos los filtros recientes de `app.recsys.pipeline`. Tampoco ejecuta diversidad, cupos, puja ni límites de frecuencia. Los valores del modelo de categoría y video son probabilidades estimadas de completar **un candidato expuesto**; el valor publicitario es solo una escala de afinidad.

## Reproducir

Desde `E:\Tiktok`:

```powershell
& 'C:\Users\lelie\AppData\Local\Programs\Orange\python.exe' orange/modelos/construir_modelos.py
& 'C:\Users\lelie\AppData\Local\Programs\Orange\python.exe' orange/modelos/ejemplo_recomendaciones.py
```

El `resumen.json` guarda el SHA-256 del CSV para detectar si se vuelve a exportar otra versión. Si el CSV cambia, ejecute ambos scripts y revise de nuevo métricas, campañas y condiciones de calidad. Abrir los `.ows` no modifica el algoritmo del feed en vivo.
