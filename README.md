# Veta

Prototipo escolar del pipeline de recomendación (sourcing → filtro → ranking multiobjetivo → diversidad) y de la subasta publicitaria descrita como trabajo futuro en el Capítulo V. **No se publica a internet.** Corre en el laboratorio: Docker o máquinas locales.

PostgreSQL guarda usuarios, clips y campañas. MongoDB guarda telemetría (reproducciones, skips, likes, impresiones de anuncio) y el perfil caliente del usuario.

## Por qué este frontend (y no otro)

| Pieza | Elección | Por qué |
|---|---|---|
| Empaquetado | **pnpm** + Vite | Un lockfile rápido; el frontend es un workspace, el API es Python. |
| Estilos | **Tailwind CSS v4** | Tokens en CSS (`@theme`): tinta de escenario, cobre de atención, teal de laboratorio. No usamos un kit tipo Chakra/MUI: esos skins se ven iguales en cualquier demo. |
| Motion | **GSAP + `@gsap/react`** | El feed es una coreografía (snap vertical, doble toque, corazón, hold-to-pause). GSAP permite pausar, revertir y respetar `prefers-reduced-motion` con `duration: 0`. Los botones usan transiciones CSS cortas, no otra librería. |
| App | **React 19 + React Router** | SPA. No hace falta SSR: el entorno nunca sale del laboratorio. |
| Layout | Móvil / tablet / escritorio | En el teléfono el clip es pantalla completa. En tablet/escritorio el escenario 9:16 convive con el carril “por qué este paquete”. |

La retención no es solo el MMoE. El producto retiene si:

- el siguiente clip llega con un gesto (rueda, swipe, `J`/`K`);
- un like estalla en el acto;
- mantener pulsado pausa el corte (el tiempo deja de contar);
- una barra de cobre muestra cuánto llevas en la sesión;
- un skip < 2 s se escribe en Mongo y empuja el vector **lejos** de ese tema.

## Cómo arrancar

### Todo con Docker (presentación)

```bash
docker compose up --build
```

Abre [http://127.0.0.1:8080](http://127.0.0.1:8080). API en [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### Local (desarrollo)

PostgreSQL y Mongo van **dentro** de Docker y no se publican en el host (así no chocan con un Mongo que ya tengas en 27017). El API y Vite sí corren en tu máquina:

```bash
docker compose up postgres mongo
cd apps/api
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

Si quieres el API fuera de Docker, publica las bases añadiendo puertos en `docker-compose.override.yml` (`5432:5432` y `27017:27017`) solo si esos puertos están libres. Si no, usa el stack completo (`docker compose up --build`) y abre el puerto 8080.

```bash
cd apps\web
pnpm install
pnpm dev
```

Vite (5173) proxifica `/api` al backend cuando el API corre en 8000.

Cuentas semilla (clave `veta1234`):

- `viewer@veta.local`
- `creator@veta.local`
- `advertiser@veta.local`
- `admin@veta.local`

## Tests

```bash
cd apps/api
pytest

cd ../web
pnpm test
pnpm test:e2e
```

- **pytest:** fórmula del Cap. III, penalización Y5>0.70, cold-start, diversidad, subasta sin presupuesto, veto por abandono, skip que aleja el vector.
- **Vitest:** pantalla de entrada.
- **Playwright:** la puerta de entrada en Chrome escritorio, iPad y Pixel.

## Orange Data Mining

Instalado en el equipo de la estadía. Guía en [`orange/README.md`](orange/README.md). El Laboratorio de la app exporta `veta_interactions.csv`.

## Lectura del tablero BI

El tablero usa los eventos de los últimos 7 días, hasta 20 000 filas (las más recientes si se alcanza el límite). Conserva los eventos para el desglose por tipo, pero agrupa `play` y su cierre por usuario, sesión, clip y posición para medir una reproducción una sola vez. Las acciones sociales reales no agregan reproducciones; la simulación registra una reproducción por evento generado.

- **Progreso medio:** promedio de `completion_ratio` de las reproducciones del corte, acotado entre 0 y 1.
- **Abandono antes de 2 s:** reproducciones cuyo evento de cierre es `skip` con `watch_ms < 2000`, dividido entre reproducciones.
- **Minutos vistos por usuario:** suma del tiempo visto de cada reproducción, dividida entre los usuarios con reproducción del corte.
- **Eventos:** total de filas de telemetría del corte, incluidas acciones sociales e impresiones. Por eso puede ser mayor que el número de reproducciones.

Los filtros de región usan la región del **clip** y los de categoría usan la categoría del clip. El CSV para Orange conserva la granularidad original de evento y puede incluir hasta 50 000 filas históricas; no tiene la misma ventana que el tablero.

## Fuera de alcance

Mensajería, pagos, visión por computadora de moderación, federated learning, y cualquier despliegue público. El SLO de 45 ms del reporte es de un clúster EPYC simulado; aquí se **mide** la latencia del ranking y se muestra en el carril lateral.
