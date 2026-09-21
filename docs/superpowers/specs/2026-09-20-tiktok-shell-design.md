# Veta: shell tipo TikTok (comentarios, compartir, follows, formato, telemetría)

Fecha: 2026-09-20  
Proyecto: laboratorio escolar. No hay producción.  
Enfoque: un solo shell TikTok sobre la SPA actual (Postgres entidades + Mongo telemetría).

## 1. Problema

El feed ya hace snap vertical y like, pero se ve laboratorio (sidebar, “por qué este paquete”). No hay comentarios, compartir, seguir, bandeja ni perfil. El evento `share` existe en el perfil caliente y nadie lo dispara. `Follow` está en Postgres sin API. Los hashtags viajan en `videos.tags` y no mueven `topic_affinity`.

Objetivo: que Veta se use como una app de clips (Inicio / Amigos / + / Bandeja / Yo) y que cada gesto nuevo deje rastro en Mongo y en el ranking. Laboratorio y Anuncios siguen existiendo, escondidos en Yo ⋯.

## 2. Fuera de alcance

- Respuestas anidadas a comentarios, duetos, live, DMs reales.
- Sensor de orientación del teléfono (el landscape móvil es un botón).
- Página de búsqueda de hashtags.
- WhatsApp u otras redes; el “enviar” es a usuarios semilla.
- BI en el camino del feed. Orange sigue siendo CSV batch.
- Renombrar tablas/API de campañas (`/campaigns` se queda). Solo cambia la etiqueta a **Anuncios**.

## 3. Decisiones de producto (cerradas)

| Tema | Elección |
|---|---|
| Cromado del feed | Overlay TikTok: Para ti / Siguiendo, riel derecho, sin sidebar |
| Barra | Inicio · Amigos · + · Bandeja · Yo |
| Comentarios | Hoja real, Postgres, semilla, eventos `comment_open` / `comment` |
| Compartir | Hoja: enviar a semilla (Bandeja) o copiar enlace; `share_open` / `share` |
| Yo | Perfil con grilla de clips; Lab y Anuncios en menú ⋯ |
| Amigos | Grafo `follows` real; feed de followees; `follow` en Mongo |
| Escritorio | Marco centrado según aspecto del archivo (9:16 o 16:9), no a todo el monitor |
| Móvil landscape | Botón de rotar en el clip (no sensor) |
| Pujas | Se llama **Anuncios** |
| Publicar | Archivo + título + descripción + hashtags + categoría |
| Hashtags | Pesan en `topic_affinity` y en sourcing `topic` |

## 4. Arquitectura

Una SPA, un `Shell` nuevo. Rutas de consumo:

| UI | Ruta | Contenido |
|---|---|---|
| Inicio | `/` | `FeedStage` con `lane=foryou` o `following` (tabs superiores) |
| Amigos | `/amigos` | Mismo `FeedStage`, `lane=friends` |
| + | `/upload` | Publicar (creador/admin) |
| Bandeja | `/bandeja` | Lista de recados |
| Yo | `/yo` | Perfil + grilla |
| Clip directo | `/clip/:id` | Un clip en el escenario (enlace copiado) |
| Laboratorio | `/lab` | Igual que hoy; solo desde Yo ⋯ |
| Anuncios | `/anuncios` | La página que hoy es `/campaigns`; redirigir `/campaigns` → `/anuncios` |

El ranking no llama a Lab ni a Orange. `GET /feed` acepta `lane=foryou|following|friends`.

**Stores**

- Postgres: usuarios, videos (más `width`, `height`), `follows` (ya existe), `comments`, `inbox_items`.
- Mongo: `events` y `user_profiles_online` como hoy, con tipos y contadores nuevos.
- Archivos: volumen `media/` ya montado en Docker. El API sirve `GET /media/{filename}` (path sandbox, solo ese directorio).

Esquema Postgres: el arranque ya hace `create_all`; tablas nuevas aparecen al reiniciar el API. No hay Alembic.

## 5. Componentes de UI

### 5.1 Shell

- Sin sidebar. Fondo `void`.
- Barra inferior de 5 tabs **dentro del marco** (también en escritorio).
- Escritorio (≥1024px): el marco se centra. Ancho máximo del marco 420px si el clip es vertical; si es horizontal, ancho máximo 720px y altura 9/16 de ese ancho. El vacío alrededor no es clicable como feed.
- Móvil: el marco es `100dvh` × 100%.

GSAP sigue siendo el único dueño de `yPercent` de los slides. React no pone `transform` inline. El progreso del clip se pinta por ref, no con `setState` cada 250 ms. (Regresión ya vista: póster negro a partir del segundo clip.)

### 5.2 FeedStage / riel

Orden del riel, arriba → abajo:

1. Avatar del creador. Si no hay `Follow`, badge `+`. Tap: `POST /follows` + evento `follow`.
2. Like (doble toque igual).
3. Comentarios (cuenta). Abre hoja.
4. Compartir (número de `inbox_items` de ese video; copiar enlace no suma). Abre hoja.
5. Botón rotar: visible si `width < 1024`. No se muestra en el marco automático de escritorio.

Caption: título, `@creador`, audio, hashtags clicables (tags del video excepto el token `seed`).

Clip `kind=ad`: chip “Patrocinado”.

### 5.3 Formato y rotar

- Aspecto = `width / height` del video. `≥ 1.2` → horizontal (marco 16:9). Si no → vertical (9:16).
- Catálogo sintético (sin archivo): `1080×1920`, vertical.
- Subida: el cliente lee `videoWidth` / `videoHeight` / `duration` del `<video>` local y los manda en el FormData (`width`, `height`, `duration_ms`). Si faltan, el API asume 1080×1920 y 14000 ms.
- Si hay `media_path`, el escenario pone `<video>` (`object-fit: contain`, loop, muted autoplay del activo) encima del póster. Si el archivo falla, se queda el póster.
- Botón rotar (móvil): estado `forcedLandscape`. El área del clip pasa a una caja 16:9 letterboxed dentro del retrato; riel y tabs siguen en retrato. No rota el documento entero. Segundo toque vuelve a 9:16.

### 5.4 Hojas

**Comentarios:** panel inferior ~55vh, asidero para cerrar, lista (autor, texto, hora relativa), input 1–240 caracteres. Semilla al seed. Abrir → `comment_open`. Enviar → `POST /videos/{id}/comments` y luego evento `comment`. Si el POST falla, el texto se queda en el input y un status “no se guardó, reintenta”. No se dispara el evento.

**Compartir:** avatares de hasta 6 usuarios semilla distintos del actual (creators + Lía). Elegir uno → `POST /inbox` + `share`. “Copiar enlace” copia `{origin}/clip/{id}` y dispara `share`. Abrir hoja → `share_open`. Enviarte a ti mismo: no crea recado; copiar sí.

### 5.5 Amigos y Siguiendo

Misma función de ranking, catálogo recortado a `creator_id ∈ followees`.

- `lane=following` (tab superior en Inicio).
- `lane=friends` (tab Amigos).

No hay segundo algoritmo. Vacío: “Sigue a alguien desde el + del avatar”. Para ti no se vacía.

### 5.6 Bandeja

Lista: avatar, nombre, título del clip, hace cuánto. Tap → `/clip/:id`. Vacío: “Nadie te ha mandado un corte”.

### 5.7 Yo

Avatar, nombre, rol, recuento de clips propios, recuento de follows. Grilla 3 columnas de pósters propios (tap → `/clip/:id`). Menú ⋯: Laboratorio, Anuncios, Salir.

### 5.8 Publicar

Campos: archivo mp4/webm (opcional), título (obligatorio), descripción, hashtags (texto libre), categoría (select actual).

Hashtags al enviar: partir por espacio o coma, quitar `#`, minúsculas, `[a-z0-9-]`, máx. 24 caracteres, máx. 8 tags. Se guardan en `videos.tags` (categoría no se duplica como tag salvo que el usuario la escriba).

Viewer: el + no envía; texto “esta cuenta no publica”. Creador/admin: POST multipart a `/videos`.

## 6. API

### 6.1 Feed

`GET /feed?lane=foryou|following|friends`

- `foryou`: pipeline actual + recycle si `kept < final_k` (últimos 8 ids siguen bloqueados).
- `following` / `friends`: igual, catálogo filtrado a followees. Si no hay followees, `items: []`.
- Cada `video` incluye `tags`, `width`, `height`, `media_url` (null o ruta de API `/media/{filename}`; el cliente pide `${BASE}/media/{filename}`), `comment_count`, `share_count` (inbox de ese video), `followee` (bool).

`GET /clip` no existe. `GET /videos/{id}` hidrata `/clip/:id` como escenario de **un** item, sin volver a rankear.

### 6.2 Comentarios

- `GET /videos/{id}/comments` → lista cronológica.
- `POST /videos/{id}/comments` `{ "body": "..." }` auth. 400 si vacío o >240.

### 6.3 Follows

- `POST /follows` `{ "followee_id": "..." }` 201 o 200 si ya existía. 400 si es uno mismo.
- `DELETE /follows/{followee_id}` 204.

### 6.4 Bandeja

- `GET /inbox` recados del usuario actual, más recientes primero.
- `POST /inbox` `{ "to_user_id", "video_id" }` 201. 400 si `to_user_id` es el actual.

### 6.5 Videos

`POST /videos` FormData: `title`, `category`, `description`, `hashtags` (string), `file`, `width`, `height`, `duration_ms`. Solo creator/admin. Guarda archivo en `media_dir` con nombre `{user_id}-{uuid}{suffix}`. `media_path` = ese filename, no una ruta absoluta (el valor actual a veces guarda path de host; las subidas nuevas no).

`GET /media/{filename}`: `FileResponse` desde `media_dir`. Cualquier `..` o separador de ruta extra → 404.

`GET /videos/{id}` ya existe; añade `width`, `height`, `tags`, `comment_count`, `share_count`.

### 6.6 Eventos

`POST /events` no cambia de forma. Tipos nuevos válidos: `comment_open`, `comment`, `share_open`, `share`, `follow`, `hashtag_tap`.

`hashtag_tap` lleva `context.hashtag` (string ya normalizado). Si falta, el evento se guarda pero no mueve affinity de tag.

El router de eventos carga el `Video` y pasa `tags` a `apply_event`.

## 7. Telemetría y ranking

### 7.1 `apply_event`

Firma efectiva: `(profile, event, embedding, category, audio_id, tags: list[str])`.

`POSITIVE` pasa a incluir `comment`, `share` (ya estaba), `follow`, `hashtag_tap`. No incluye `comment_open` ni `share_open`.

Tasas de vector (`LEARNING_RATES`):

| tipo | lr |
|---|---|
| like | 0.14 |
| share | 0.16 |
| comment | 0.12 |
| follow | 0.10 |
| hashtag_tap | 0.06 |
| complete | 0.08 (igual) |
| skip | 0.12 (igual) |

Affinity, evento positivo (excepto `hashtag_tap`): categoría `+0.08` (comment `+0.07`, share `+0.09`, follow `+0.05`, like `+0.08`) y **cada tag** el mismo delta. Cap 1.0.

`hashtag_tap`: el tag de `context.hashtag` `+0.10`; categoría `+0.03`.

Skip < 2 s: categoría y cada tag `−0.06`, piso 0.

`comment_open` / `share_open`: solo contadores, sin vector ni affinity.

Contadores 24 h nuevos: `comments`, `shares`, `follows`, `hashtag_taps`, `comment_opens`, `share_opens` (enteros, default 0). Like/skip/complete siguen.

### 7.2 Sourcing `topic`

```
score = 0.55 * cat + 0.25 * audio + 0.20 * hashtag_overlap
hashtag_overlap = (# tags del video presentes en topic_affinity) / max(# tags, 1)
```

Antes era 0.7 / 0.2 / 0.1 y el 0.1 casi nunca disparaba porque el perfil no tenía claves de tag.

Tocar un hashtag no navega a otra ruta: dispara el evento y el **siguiente** `GET /feed` (al pedir más o al recargar el paquete) usa el perfil ya actualizado.

### 7.3 Lab y Orange

`GET /lab/metrics` añade: `comments`, `shares`, `follows`, `hashtag_taps`, `comment_opens`, `share_opens` (conteos 7 días).

CSV `veta_interactions.csv`: columna nueva `tags` (tags del video unidos por `|`). `event_type` ya existe y cubrirá los tipos nuevos.

Simulador: una fracción baja de eventos puede ser `comment` / `share` / `follow` / `hashtag_tap` para que el lab no quede en ceros tras `POST /lab/sim`.

### 7.4 Seed

`seed_if_empty` no corre si ya hay usuarios (el lab Docker actual). Hace falta `seed_social_if_empty`: si `comments` y `follows` están vacíos, inserta:

- 2–3 comentarios en videos de ciencia/música (autores: Lía, Mar, Taller Norte).
- `Follow`: Lía Viewer → Mar Cantera.
- No reescribe tags de videos ya creados.

Instalación nueva (`seed_if_empty`): además de `[category, "seed"]`, 1–2 tags por categoría (`laboratorio`, `corto`, `veta`). El caption **no muestra** el token `seed`.

## 8. Flujo de datos (un gesto)

1. UI manda el POST de entidad (comentario, follow, inbox) **antes** del evento, salvo like (like ya es solo evento + `ExplicitLike` en el ingest).
2. Si la entidad falla, no se llama a `/events`.
3. `/events` escribe Mongo, `apply_event` al perfil caliente, y los side effects actuales (like explícito, `play_count`).
4. El feed siguiente lee el perfil. No hay cola, ni BI, ni Orange en este camino.

Like se queda como está (evento primero, `ExplicitLike` en el ingest) para no romper lo que ya funciona.

## 9. Errores y vacíos

| Caso | UI |
|---|---|
| Red caída al comentar/compartir | Status en la hoja, texto no se borra |
| Viewer en + | “Esta cuenta no publica” |
| Amigos / Siguiendo sin follows | Vacío con CTA al avatar |
| Bandeja vacía | “Nadie te ha mandado un corte” |
| Archivo de video ilegible | Póster; aspecto 9:16 |
| Recado a uno mismo | 400; la UI no ofrece el propio avatar |
| Feed agotado por `already_seen` | Recycle (ya especificado en pipeline) |
| `/clip/:id` inexistente | “Ese corte no está en el catálogo” + volver a Inicio |

## 10. Testing

**pytest**

- comment / share / follow suben affinity de categoría y de cada tag, con los deltas de §7.1.
- hashtag_tap sube más el tag que la categoría.
- skip < 2 s baja tags.
- comment_open / share_open no cambian vector ni affinity.
- Recycle: catálogo todo-visto → feed no vacío, excluye los 8 más recientes.
- POST video con width/height los persiste; sin ellos, 1080×1920.

**Vitest**

- Parser de hashtags: `#A #B,C` → `["a","b","c"]`, recorta a 8, tira inválidos.
- Viewer: el submit de + no llama a fetch.

**Playwright** (cuenta nueva, desktop + un proyecto móvil)

- Riel visible: like, comentario, compartir, seguir.
- Comentar, recargar, el texto sigue.
- Compartir a semilla; en otra sesión de ese usuario, Bandeja muestra el recado.
- Seguir → Amigos deja de estar vacío.
- Tap de hashtag: el paquete siguiente incluye más items con ese tag (assert sobre `data-tags` o caption).
- Escritorio: el escenario activo está en un marco, no a 100% del viewport de 1440.
- Ocho `j` seguidos: slide activo `translateY ≈ 0` y póster visible (regresión GSAP).

No se testea giro físico ni Orange GUI. CSV: un test de API que la primera línea contiene `tags`.

## 11. Criterio de hecho

Un jurado con `viewer@veta.local` puede: ver Para ti a pantalla de teléfono; comentar; compartir a Mar y ver el recado en Bandeja; seguir y abrir Amigos; tocar un hashtag y notar el feed; abrir Yo ⋯ Laboratorio y ver conteos de comment/share/follow/hashtag; publicar (cuenta creador) un mp4 con hashtags y que el marco salga 16:9 si el archivo es apaisado.

## 12. Unidades (para el plan)

1. Persistencia: Comment, InboxItem, width/height, media serve, seed.
2. Telemetría: apply_event + topic overlap + lab metrics/CSV + tests.
3. Feed lanes following/friends + follows API.
4. Shell TikTok + FeedStage riel/hojas/marco/rotar (preservar GSAP).
5. Bandeja, Yo, Publicar, Anuncios (rename), clip route.
6. Playwright de los gestos.
