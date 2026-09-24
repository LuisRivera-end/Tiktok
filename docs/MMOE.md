# MMoE y campañas medibles

## Uso de la aplicación

- Registro / Yo: género opcional, editable o retirable. Hombre, Mujer, Otra identidad,
  Prefiero no decirlo y Sin especificar. Solo se usa lo declarado.
- Un anunciante puede subir su video desde Publicar y crear una campaña en Anuncios.
  Configure enlace, puja CPC simulada, presupuesto diario, categorías, etiquetas y audiencia.
- Todos incluye cuentas sin respuesta. Una audiencia específica exige coincidencia declarada
  y los demás filtros. La ausencia de dato no se infiere como Hombre o Mujer.
- Visitar sitio abre el destino y registra un clic único por exposición. El gasto es simulado.
  Anuncios muestra resultados, audiencia, presupuesto y pausa/activación. Actualizar resultados
  vuelve a consultar el periodo seleccionado.
- Laboratorio incluye métricas por exposición/género. Los administradores pueden exportar
  `veta_exposures_real.csv`; el CSV antiguo por evento sigue disponible.
- En el origen `Simulado`, Laboratorio genera en memoria 2 400 exposiciones reproducibles de
  60 perfiles ficticios durante cinco días. No lee usuarios, videos, eventos ni exposiciones
  almacenados; tampoco escribe registros. La exportación de ese origen contiene solo filas
  sintéticas y no se usa para aprobar un modelo de producción.
- Laboratorio muestra a los administradores la preparación del MMoE: usuarios, sesiones,
  días, campañas, etiquetas maduras por objetivo y razones concretas para seguir recopilando.

## Identidad y medición

`GET /feed?session_id=...` emite una decisión por candidato entregado, vigente dos horas.
`POST /exposures` registra un UUID de exposición y valida decisión, usuario, video y género.
El acceso directo a un clip también valida elegibilidad y captura características previas.
Una vuelta al video es otra exposición. Las sesiones se separan tras 30 minutos sin actividad.

`POST /events` acepta `event_id`, `exposure_id`, `event_ts`, `watch_ms`, `coverage_ms` y eventos
impression/play/heartbeat/close/like/share/comment/follow. Los clientes nuevos requieren ambos
UUID. Los viejos siguen como legacy y quedan fuera del dataset MMoE. Se conserva la primera
carga de cada event_id y las reducciones usan máximos/flags, de modo que reintentos y orden
de llegada no incrementen resultados. El perfil caliente se reconstruye desde una base
legacy congelada y las últimas 5000 exposiciones; esto también evita duplicar sus efectos.

El reproductor mide avance efectivo con el video visible y reproduciéndose, y une intervalos
para cobertura. Adelantos, pausas, buffering y pestaña oculta no añaden tiempo; un póster sin
video no genera reproducciones ficticias. Hay un cierre por exposición y heartbeat cada 5 s.
Si se pierde el cierre al terminar abruptamente el navegador, se enmascaran resultados desconocidos.
Los relojes del cliente deben estar dentro de cinco minutos del servidor.

Características y género se congelan al decidir. Cambiar el perfil renueva el feed; no reescribe
exposiciones pasadas. La selección de género se usa como categoría, nunca escala numérica.
Para predicción, Prefiero no decirlo y Sin especificar comparten ausencia; analítica los distingue.

## Campañas

La estimación de clic usa exposiciones reales maduras de siete días y suavizado jerárquico:
global Beta(1,19), campaña, creatividad y segmento declarado; cada nivel aporta 20 observaciones
equivalentes de su padre. El 5% inicial es un prior, no una tasa medida. La selección es
90% máximo `bid_cents * p_click` y 10% uniforme entre elegibles; se registra la probabilidad.
El eCPM se expresa en centavos por mil impresiones (`1000 * bid_cents * p_click`).

Primer anuncio desde posición 3, seis orgánicos entre anuncios, máximo dos por paquete,
una exposición por campaña/sesión, ocho por usuario/campaña/hora. El veto de retención usa
la fórmula existente con tasas suavizadas observadas, mínimo 100 observaciones y umbral 0,62.
Los rechazos se conservan en las trazas por targeting, frecuencia, presupuesto o retención.

`POST /campaigns/click` valida propiedad de la exposición y ventana de 24 horas. Una transacción
PostgreSQL bloquea la campaña, deduplica por exposición y actualiza gasto diario + ledger + outbox.
La fecha presupuestaria usa America/Mexico_City. Un clic tardío sin saldo cuenta, pero no se cobra.
El outbox replica a Mongo; un trabajador reintenta cada 10 segundos. Las métricas también lo drenan.
Las impresiones del periodo se seleccionan por fecha de inicio; el gasto, por fecha del clic.
El endpoint de métricas solo acepta propietario o administrador.

## Entrenar y comparar

Desde `apps/api`, instalar el extra de entrenamiento (la API sirve mediante NumPy, sin PyTorch):

```powershell
.venv/Scripts/python.exe -m pip install -e '.[dev,ml]'
.venv/Scripts/python.exe -m app.ml.train artifacts/exposures_real.csv --output artifacts/mmoe
```

El archivo debe ser la exportación por exposición, nunca el CSV antiguo por evento.
Antes de entrenar, se puede revisar el CSV sin PyTorch:

```powershell
.venv/Scripts/python.exe -m app.ml.readiness artifacts/exposures_real.csv
```

El mismo diagnóstico está disponible en `GET /lab/exposures/readiness` para administradores.
Los datos con etiquetas inmaduras, sin ambas clases o sin cortes temporales útiles producen
`readiness.json` con estado insuficiente y un desglose de las carencias. No se rellenan
etiquetas ni se activan pesos para evitar este resultado.

Para reproducir la verificación sintética, separada de las bases de la aplicación:

```powershell
.venv/Scripts/python.exe -m app.ml.demo artifacts/demo/exposures.csv
.venv/Scripts/python.exe -m app.ml.train artifacts/demo/exposures.csv --output artifacts/demo/mmoe --origin simulated --epochs 25
```

El conjunto nuevo y versionado `data/synthetic/mmoe_v2_exposures.csv` cubre 100 perfiles,
24 días y cinco campañas. Su [generación, procedencia y resultados](../data/synthetic/README.md)
están documentados junto al manifiesto SHA-256. Se usa únicamente para desarrollo; su
`origin=simulated` mantiene desactivada la promoción incluso si una métrica mejora.

El MMoE tiene cuatro expertos [64,32], cuatro compuertas y torres [16,1]. Tareas:
finalización >=90% de cobertura; like/share completado; siguiente video visto >=2 s iniciado
dentro de 60 s; clic (solo anuncios). Maduración: 24 h. Clic de salida enmascara continuidad.
Pérdida binaria enmascarada por tarea, Adam 0,001, lotes de 128, paciencia de 5 épocas.

Se reserva 20% de usuarios. El resto se separa temporalmente por sesiones 70/15/15 y se purgan
ventanas de etiquetas que atraviesen cortes. Transformaciones se ajustan solo con entrenamiento.
Los usuarios reservados se evalúan únicamente en el periodo final. Los IDs son metadatos.

Se entrenan variantes con/sin género y baselines de tasas suavizadas, regresión logística y bosque.
La selección usa validación; incluir género exige beneficio validado. `report.json` contiene
log-loss, PR-AUC, ROC-AUC, Brier, calibración, cortes por género/campaña/cold-start, intervalos
bootstrap por usuario (500 réplicas), comparación NDCG con la fórmula previa sobre exposiciones
observadas, paquetes/configuración, semilla y hash. NDCG offline no demuestra mejora causal del feed.

`model.json` contiene pesos y encoder portables; los CSV `*_predictions.csv` preservan las
particiones. `orange/modelos/mmoe/prepare_orange.py` crea las tablas y flujo de inspección.

## Activación y retorno

Configurar en `.env` (Docker Compose los propaga):

```dotenv
CONTENT_MODEL_MODE=shadow
ADS_MODEL_MODE=shadow
MMOE_MODEL_PATH=artifacts/mmoe/model.json
```

Recrear la API con `docker compose up -d api`. El directorio local `apps/api/artifacts` está montado
solo lectura. El modo inicial es `heuristic`; `shadow` registra predicciones sin cambiar selección.
`mmoe` solo activa cada consumidor si el artefacto real tiene aprobación calculada. Se exige
mejora de log-loss con intervalo del 95% inferior a cero y PR-AUC no inferior al baseline, tanto
en prueba temporal como en usuarios reservados. Para contenido deben pasar sus tres tareas;
para anuncios, clic. Una variante con género exige evidencia adicional frente a la variante sin él.
Con menos de diez usuarios o cien observaciones/10 resultados de cada clase no se aprueba la tarea.
Un artefacto simulado nunca se activa, aunque se solicite `mmoe`.
Para anuncios se exigen al menos dos campañas. El servidor también exige que
`readiness.json` indique una evaluación terminada y coincida en versión y hash con `model.json`.
Al iniciar un nuevo entrenamiento, el estado pasa a `evaluating`; si falla, un modelo anterior
no vuelve a activarse inadvertidamente. Tras obtener un artefacto aprobado, úsese primero
`shadow` y compruébense sus predicciones y latencia antes de solicitar `mmoe`.

Contenido usa 0,5 finalización + 0,2 interacción + 0,3 continuidad, conservando ajustes contextuales,
filtros y diversidad. Publicidad usa p_click. `predictions` y `model_version` distinguen estos
resultados de los antiguos y1…y5, que siguen siendo puntuaciones heurísticas.
Modelo ausente, incompatible o no finito: fallback registrado. Volver a `heuristic` revierte selección.

## Verificación

```powershell
# Desde apps/api
.venv/Scripts/python.exe -m pytest -q
# Desde la raíz
pnpm test:web
pnpm build:web
pnpm --filter veta-web exec playwright test --workers=2
docker compose cp apps/api/scripts/verify_stack.py api:/tmp/verify_stack.py
docker compose exec -e PYTHONPATH=/app api python /tmp/verify_stack.py
```

La última prueba usa un esquema PostgreSQL y una base Mongo temporales; los elimina al terminar.
Comprueba segmentación, concurrencia de CPC, duplicados, outbox, historia y permisos sin alterar
las campañas existentes. Las pruebas nuevas de interfaz usan respuestas controladas; el backend
completo se verifica por separado en el stack real. La validación real de mejoras de CTR necesita
nuevas exposiciones maduras y una comparación controlada con usuarios.
