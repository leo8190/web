# Herramienta de muestras (rama `tools`, no se publica en la web)

Pedido de Leo (22 y 24/10/2026): a cada negocio que se contacta se le manda una página de muestra
personalizada, ya publicada en `https://web.leonardoapollonio.com/muestras/<slug>/`.

## Pasos

1. Clonar `leo8190/web` con acceso de escritura y traer esta herramienta:
   `git -C web fetch origin tools && git -C web show FETCH_HEAD:gen_muestras.py > gen_muestras.py`
2. Escribir `leads.json` (lista JSON) con un objeto por negocio (campos abajo).
3. `python3 gen_muestras.py leads.json web envios.jsonl`
   Crea `web/muestras/<slug>/index.html` por cada negocio válido y `envios.jsonl` con el mail listo
   (to, subject, body, htmlBody, url). Muestra los descartados con el motivo (país excluido, sin
   actividad en el último año, puntaje menor a 4, datos faltantes).
4. Publicar: en `web`, `git add muestras`, commit con
   `-c user.name="leo8190" -c user.email="leonardo23322@gmail.com"`, y
   `git push origin main` y `git push origin main:gh-pages`.
5. Verificar que cada `url` dé 200 (`curl -s -o /dev/null -w '%{http_code}' URL`; puede tardar
   1 o 2 minutos después del push; reintentar cada 30 s hasta 5 min). Mandar solo los que den 200.
6. Mandar cada línea de `envios.jsonl` con Gmail `send_message` (to, subject, body, htmlBody),
   sin cambiar los textos.

## Campos de cada negocio

Obligatorios:
- `name`, `town`, `country`, `email` (copiado exacto de la fuente), `lang` (`es`, `pt` o `en`).
- `newest_review_date`: fecha más nueva de una reseña o respuesta del dueño, `AAAA-MM-DD`
  (si es de hace más de un año, se descarta).
- `hook_sentence`: una oración en el idioma del negocio, solo con datos vistos en la fuente.
  Formatos:
  - es: `Vi <Negocio> en <Fuente>: N.° 5 de 120 restaurantes de <Ciudad>, con 4,7 y 312 opiniones.`
  - pt: `Vi o <Negócio> no <Fonte>: n.º 4 dos 29 restaurantes de <Cidade>, com nota 4,5 e 387 avaliações.`
  - en: `I came across <Business> on <Source>: #20 of 230 restaurants in <Town>, 4.7 with 231 reviews, and in August a guest wrote "The best curry in town!"`
  Si el ranking es flojo (peor que el 30 % de arriba), no lo pongas: solo puntaje y cantidad.
- `situation_sentence`: una de estas, según el caso:
  - es: `Pero no tienen página propia, y cuando alguien los busca encuentra solo esa ficha.` /
    `Pero cuando alguien los busca, el link de su sitio lleva a Facebook.` (o Instagram, o "a una página de enlaces")
  - pt: `Mas vocês não têm um site próprio, e quem procura encontra só essa página.` /
    `Mas o link do site de vocês leva ao Facebook.` (ou "ao Instagram", ou "a uma página de links")
  - en: `But your listing has no website, and I couldn't find one online.` /
    `But the website link on your listing goes to Facebook.` (or Instagram, or "a link-in-bio page")
  - Si el problema es otro y está verificado (dominio que no abre o en venta), describilo igual de corto.

Para la página (si un dato no está en la fuente, dejalo vacío; nunca inventar):
- `rating_source`: de dónde salen el puntaje y las reseñas (`TripAdvisor`, `Booksy`, `Google`...). Por defecto TripAdvisor.
- `rating` (número), `reviews_count` (número).
- `kind`: `food` (restaurantes, cafés, panaderías) o `service` (peluquerías, barberías, spas, talleres...).
- `business_type`: en el idioma del negocio, ej. "Restaurante", "Barbería", "Bakery".
- `cuisines`: lista corta de categorías; `features`: hasta 5 características de la ficha.
- `description`: una oración (máx. 20 palabras), primera persona del plural, sin superlativos inventados.
- `dishes` (o `services`): 3 a 6 platos, productos o servicios mencionados en la ficha o en reseñas.
- `quotes`: 2 o 3 citas textuales cortas (máx. 12 palabras), en el idioma original: `{"text": "...", "date": "2026-08"}`.
- `address`, `phone` (con código de país si aparece), `hours` (corto), `price_range`, `region`.
- `booking_url`: link de turnos que ya usan (Booksy, Vagaro, Fresha...), si existe.

## Qué hace sola la herramienta

- Botón de WhatsApp si el número es celular; botón de llamar si es fijo o si el negocio está en EE.UU. o Puerto Rico.
- Asunto: "Armé una página para <negocio>" / "Fiz um site de exemplo para <negócio>" / "I made a sample website for <business>".
- Mail sin ¿ ni ¡ de apertura, con firma enlazada a web.leonardoapollonio.com, dirección postal y la línea para darse de baja.
- La página dice arriba que es una muestra gratuita y tiene `noindex`.
- Descarta los países a los que nunca se les escribe: UE/EEE, Reino Unido, Suiza, Vietnam, Egipto,
  Filipinas, Sudáfrica, Marruecos, Kenia, Turquía, Japón, Corea, Singapur, Israel, Canadá, Australia,
  Nueva Zelanda e India.

## Sin seguimientos (regla vigente de Leo, 28/10/2026)

Un solo contacto inicial por negocio; ningún seguimiento a quien no respondió. El pedido del 24/10 de mandar
la muestra a los que no contestaron ya no vale. La herramienta descarta cualquier negocio con `"followup": true`.
Antes de mandar, revisar en Gmail que nunca se le haya escrito a esa dirección (`in:anywhere {to:a to:b ...}`).
