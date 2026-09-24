# Datos simulados MMoE v2

`mmoe_v2_exposures.csv` es un conjunto **sintético** para desarrollar y comprobar
el entrenamiento multitarea. No son impresiones de personas ni campañas reales.
Cada fila es una exposición; `exposure_id` es único y los cuatro resultados
(`complete`, `engage`, `continue`, `click`) llevan su propia máscara de observación.
`origin=simulated` en todas las filas impide usarlo para aprobar el modelo servido.

El archivo contiene 19 200 exposiciones, 100 perfiles, 2 400 sesiones y 24 días
UTC (1–24 de mayo de 2026). Hay 4 800 impresiones distribuidas entre cinco
campañas ficticias. Se generaron 9 654 finalizaciones, 3 253 interacciones,
15 092 continuaciones observadas y 812 clics publicitarios. Las cantidades exactas,
distribución de género, máscaras, particiones y SHA-256 están en
`mmoe_v2_exposures.manifest.json`.

El generador usa semilla `20260924`: preferencias por categoría, duración de
10/15/20 segundos, dos espacios de anuncio por sesión y resultados muestreados.
Los perfiles de género son etiquetas sintéticas repartidas para probar la
segmentación; no se infieren de usuarios ni se interpreta una diferencia como
efecto causal. Todas las exposiciones se cierran en la simulación. El conjunto
no representa pérdidas de telemetría, estacionalidad real, pujas reales ni
comportamiento de una población de usuarios. Los datos no se insertan en MongoDB
ni se mezclan con `artifacts/exposures_real.csv`.

Para regenerarlo desde `apps/api`:

```powershell
.venv/Scripts/python.exe -m app.ml.generate ../../data/synthetic/mmoe_v2_exposures.csv
.venv/Scripts/python.exe -m app.ml.train ../../data/synthetic/mmoe_v2_exposures.csv --output artifacts/generated/mmoe --origin simulated --epochs 25
```

La evaluación reservó 20 usuarios y separó los restantes por tiempo:
10 112 filas de entrenamiento, 1 664 de validación, 2 304 de prueba temporal
y 568 de usuarios reservados en el periodo final. Hay menos filas que en el CSV
porque se purgan ventanas de etiquetas y los usuarios reservados anteriores
al periodo de prueba. El resultado escogió `without_gender`; ni contenido ni
anuncios superaron el criterio de activación. La regresión logística fue el
baseline elegido para las cuatro tareas. Esto verifica que el sistema puede
rechazar un MMoE aunque entrene correctamente.

Para reproducir la inspección en Orange desde la raíz:

```powershell
& 'C:/Users/lelie/AppData/Local/Programs/Orange/python.exe' orange/modelos/mmoe/prepare_orange.py --model-dir apps/api/artifacts/generated/mmoe --output orange/modelos/mmoe/generated_v2
```

El flujo resultante está en `orange/modelos/mmoe/generated_v2/flujo.ows`.
Las tablas muestran solo predicciones de prueba temporal y usuarios reservados.
La evaluación completa está en `apps/api/artifacts/generated/mmoe/report.json`
después de entrenar; ese directorio se ignora en Git y se reproduce con el
comando anterior. La aprobación con datos reales sigue requiriendo nuevas
exposiciones auténticas y un experimento controlado.
