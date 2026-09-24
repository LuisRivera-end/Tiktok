# MMoE: inspección en Orange

Abra `flujo.ows`. Cada File está conectado a una tabla para finalización,
interacción, continuidad o clic publicitario. Las filas son únicamente de
prueba temporal y usuarios reservados, y se excluyen las etiquetas desconocidas.

**La entrega inicial es SIMULADA**. `resumen.json` identifica el origen, hash,
modelo elegido y autorización de activación. El entrenamiento en Python compara
con tasas suavizadas, regresión logística y bosque; Orange inspecciona sus salidas.
Las columnas `p_*` son predicciones, no variables para reentrenar contra la misma etiqueta.
El género histórico está como metadato para revisar grupos.

Desde la raíz del repositorio, después de entrenar:

```powershell
& 'C:/Users/lelie/AppData/Local/Programs/Orange/python.exe' orange/modelos/mmoe/prepare_orange.py
```

Para un entrenamiento real, pasar `--model-dir apps/api/artifacts/mmoe` y un
`--output` diferente si se desea conservar la demostración. No se modifican los
flujos anteriores de categoría, video o publicidad ni la sesión abierta.

Consulte `docs/MMOE.md` en la raíz para preparar exposiciones, entrenar y activar
modo sombra. Las métricas completas y calibración están en el `report.json` del
directorio de entrenamiento; las tablas de Orange no sustituyen esa evaluación.
