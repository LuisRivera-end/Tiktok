# MMoE v2 simulado en Orange

Abra `flujo.ows` para explorar las predicciones reservadas de finalización,
interacción, continuidad y clic. Las tablas contienen respectivamente 2 872,
2 872, 2 740 y 718 filas con etiquetas observadas. `resumen.json` enlaza el
flujo con el SHA-256 del CSV de `data/synthetic` y confirma que el origen es
`simulated` y la activación está desautorizada.

Las columnas `p_*` son salidas del MMoE, no entradas para reentrenarlo sobre
las mismas filas. Consulte `data/synthetic/README.md` para reproducir el
conjunto y `apps/api/artifacts/generated/mmoe/report.json` para las métricas
completas generadas localmente.
