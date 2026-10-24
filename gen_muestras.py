#!/usr/bin/env python3
"""Genera páginas de muestra personalizadas (ES/PT/EN) y el mail que acompaña a cada una.

Uso:  python3 gen_muestras.py leads.json <raíz_del_repo_web> envios.jsonl
  - leads.json: lista JSON (o un JSON por línea) con los campos de README.md.
  - Escribe <raíz>/muestras/<slug>/index.html por cada lead válido.
  - Escribe envios.jsonl: una línea por mail (to, subject, body, htmlBody, url, slug, name, town, country, lang).
  - Muestra en pantalla los válidos y los descartados con el motivo. No manda nada.
"""
import datetime
import hashlib
import html
import json
import os
import re
import sys
import unicodedata
import urllib.parse

BASE_URL = "https://web.leonardoapollonio.com/muestras/"
SIGNATURE_URL = "https://web.leonardoapollonio.com"
ADDRESS = "Fray Justo Santa María de Oro 2567, 6° C, C1425 CABA, Argentina"

PALETTES = [("#b5452b", "#e09a3e"), ("#0f5e7a", "#2aa3b8"), ("#8a5a2b", "#3f8f9a"),
            ("#2e6b3f", "#8fae3e"), ("#7a2e5e", "#d0743c"), ("#1f4e79", "#d99a2b"),
            ("#5b3a8a", "#d65a7a"), ("#2f6f6a", "#d9a53a")]

MONTHS = {
    "es": ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"],
    "pt": ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"],
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
}


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s.lower()).strip()


# Países a los que nunca se les escribe (pedido de Leo, 22/10/2026: países con leyes antispam
# que piden permiso previo). Se compara por palabra completa contra el campo "country".
EXCLUDED = [
    "union europea", "european union", "ue", "eu", "eee", "eea",
    "alemania", "germany", "austria", "belgica", "belgium", "bulgaria", "chipre", "cyprus", "croacia", "croatia",
    "dinamarca", "denmark", "eslovaquia", "slovakia", "eslovenia", "slovenia", "espana", "spain", "estonia",
    "finlandia", "finland", "francia", "france", "grecia", "greece", "hungria", "hungary", "irlanda", "ireland",
    "italia", "italy", "letonia", "latvia", "lituania", "lithuania", "luxemburgo", "luxembourg", "malta",
    "paises bajos", "holanda", "netherlands", "polonia", "poland", "portugal", "republica checa", "chequia",
    "czech republic", "czechia", "rumania", "romania", "suecia", "sweden", "islandia", "iceland", "liechtenstein",
    "noruega", "norway", "martinica", "martinique", "guadalupe", "guadeloupe", "guayana francesa", "french guiana",
    "reunion", "mayotte", "saint-martin", "saint martin", "san martin",
    "reino unido", "united kingdom", "uk", "inglaterra", "england", "escocia", "scotland", "gales", "wales",
    "irlanda del norte", "northern ireland", "gran bretana", "great britain",
    "suiza", "switzerland", "vietnam", "viet nam", "egipto", "egypt", "filipinas", "philippines",
    "sudafrica", "south africa", "marruecos", "morocco", "kenia", "kenya", "turquia", "turkey", "turkiye",
    "japon", "japan", "corea", "korea", "singapur", "singapore", "israel", "canada", "australia",
    "nueva zelanda", "new zealand", "india",
]

CC = {  # código de país para WhatsApp/teléfono cuando el número no trae "+"
    "mexico": "52", "colombia": "57", "ecuador": "593", "bolivia": "591", "peru": "51", "chile": "56",
    "argentina": "54", "uruguay": "598", "paraguay": "595", "el salvador": "503", "nicaragua": "505",
    "guatemala": "502", "costa rica": "506", "panama": "507", "honduras": "504", "belice": "501", "belize": "501",
    "brasil": "55", "brazil": "55", "republica dominicana": "1", "dominican republic": "1",
    "usa": "1", "puerto rico": "1", "jamaica": "1", "grenada": "1", "granada": "1", "dominica": "1", "barbados": "1",
    "trinidad y tobago": "1", "trinidad and tobago": "1", "bahamas": "1",
    "san vicente y las granadinas": "1", "saint vincent and the grenadines": "1",
    "tailandia": "66", "thailand": "66", "malasia": "60", "malaysia": "60", "camboya": "855", "cambodia": "855",
    "laos": "856", "indonesia": "62", "sri lanka": "94", "nepal": "977",
    "ghana": "233", "namibia": "264", "mozambique": "258", "malawi": "265", "zambia": "260",
    "uganda": "256", "ruanda": "250", "rwanda": "250", "tanzania": "255",
}
TRUNK0 = {"66", "60", "855", "856", "62", "94", "977", "233", "264", "265", "260", "256", "250", "255", "55", "51", "598", "54"}
# En EE.UU. y Puerto Rico casi nadie usa WhatsApp para negocios: botón de llamar.
CALL_FIRST = {"usa", "puerto rico"}


def ckey(country):
    """Nombre de país normalizado; todas las formas de EE.UU. pasan a "usa"."""
    c = norm(country)
    if c.startswith(("estados unidos", "united states", "ee.uu", "ee. uu", "eeuu", "usa", "u.s.")):
        return "usa"
    return c

MOBILE = {  # código -> (regla de celular, largos válidos del número nacional)
    "57": (lambda n: len(n) == 10 and n[0] == "3", (10,)),
    "502": (lambda n: len(n) == 8 and n[0] in "345", (8,)),
    "503": (lambda n: len(n) == 8 and n[0] in "67", (8,)),
    "504": (lambda n: len(n) == 8 and n[0] in "3789", (8,)),
    "505": (lambda n: len(n) == 8 and n[0] in "578", (8,)),
    "506": (lambda n: len(n) == 8 and n[0] in "678", (8,)),
    "507": (lambda n: len(n) == 8 and n[0] == "6", (7, 8)),
    "591": (lambda n: len(n) == 8 and n[0] in "67", (7, 8)),
    "593": (lambda n: len(n) == 9 and n[0] == "9", (8, 9)),
    "51": (lambda n: len(n) == 9 and n[0] == "9", (8, 9)),
    "56": (lambda n: len(n) == 9 and n[0] == "9", (9,)),
    "598": (lambda n: len(n) == 8 and n[0] == "9", (8,)),
    "54": (lambda n: len(n) == 11 and n[0] == "9", (10, 11)),
    "62": (lambda n: n[:1] == "8" and 9 <= len(n) <= 12, (8, 9, 10, 11)),
    "94": (lambda n: len(n) == 9 and n[0] == "7", (9,)),
    "60": (lambda n: n[:1] == "1" and len(n) in (9, 10), (8, 9, 10)),
    "66": (lambda n: len(n) == 9 and n[0] in "689", (8, 9)),
    "258": (lambda n: len(n) == 9 and n[:2] in ("82", "83", "84", "85", "86", "87"), (8, 9)),
    "264": (lambda n: len(n) == 9 and n[:2] in ("81", "83", "84", "85"), (8, 9)),
}

T = {
    "es": dict(htmllang="es", banner="Muestra gratuita preparada por Leonardo Apollonio · sin compromiso",
               badge="★ {r} en {src} · {n} opiniones", wa="Escríbenos por WhatsApp", call="Llámanos",
               book="Reserva tu turno", maps="Cómo llegar", about="Lo que nos define",
               fav_food="Lo más pedido", fav_service="Nuestros servicios", revs="Lo que dicen nuestros clientes",
               revcap="Reseña en {src}", photos="Fotos", photo_ph="Aquí van sus fotos", info="Horario y ubicación",
               hours="Horario", addr="Dirección", tel="Teléfono", booking="Turnos", price="Precios",
               hours_wa="Consúltanos por WhatsApp", hours_tel="Llámanos para consultar el horario",
               hours_maps="Consulta nuestros horarios en Google Maps",
               footer="Muestra hecha por Leonardo Apollonio, desarrollador web",
               title="{name} | {type} en {town}", wa_text="Hola, los vi en su página web",
               default_type="Restaurante"),
    "pt": dict(htmllang="pt-BR", banner="Exemplo gratuito feito por Leonardo Apollonio · sem compromisso",
               badge="★ {r} no {src} · {n} avaliações", wa="Fale com a gente no WhatsApp", call="Ligue para nós",
               book="Agende seu horário", maps="Como chegar", about="O que nos define",
               fav_food="Os mais pedidos", fav_service="Nossos serviços", revs="O que dizem nossos clientes",
               revcap="Avaliação no {src}", photos="Fotos", photo_ph="Aqui vão suas fotos", info="Horário e localização",
               hours="Horário", addr="Endereço", tel="Telefone", booking="Agendamento", price="Preços",
               hours_wa="Fale com a gente pelo WhatsApp", hours_tel="Ligue para saber o horário",
               hours_maps="Veja nossos horários no Google Maps",
               footer="Exemplo feito por Leonardo Apollonio, desenvolvedor web",
               title="{name} | {type} em {town}", wa_text="Olá, vi o site de vocês",
               default_type="Restaurante"),
    "en": dict(htmllang="en", banner="Free sample made by Leonardo Apollonio · no strings attached",
               badge="★ {r} on {src} · {n} reviews", wa="Message us on WhatsApp", call="Call us",
               book="Book an appointment", maps="Get directions", about="What we're about",
               fav_food="Guest favorites", fav_service="Our services", revs="What our guests say",
               revs_service="What our clients say",
               revcap="{src} review", photos="Photos", photo_ph="Your photos here", info="Hours & location",
               hours="Hours", addr="Address", tel="Phone", booking="Booking", price="Prices",
               hours_wa="Message us for today's hours", hours_tel="Call us for today's hours",
               hours_maps="See our hours on Google Maps",
               footer="Sample made by Leonardo Apollonio, web developer",
               title="{name} | {type} in {town}", wa_text="Hi, I found you on your website",
               default_type="Restaurant"),
}

PARTS = {  # qué tiene la muestra, para el mail
    "es": dict(rev="sus mejores reseñas", rating="su puntaje de {src}", food="lo más pedido",
               service="sus servicios", maps="cómo llegar", conj=" y "),
    "pt": dict(rev="as melhores avaliações", rating="a nota de vocês no {src}", food="os mais pedidos",
               service="os serviços de vocês", maps="como chegar", conj=" e "),
    "en": dict(rev="your best reviews", rating="your {src} rating", food="guest favorites",
               service="your services", maps="directions", conj=" and "),
}

EMAIL = {
    "es": dict(
        subject="Armé una página para {name}",
        lines=["Hola, cómo están?", "", "Me llamo Leonardo Apollonio, soy desarrollador de software y hago páginas web para negocios.", "",
               "{hook} {situation}", "",
               "Así que les armé una muestra de cómo podría quedar su página, con {parts}:",
               "{url}", "",
               "Es gratis y sin compromiso. Si les gusta, la termino con sus fotos y su propio dominio; si no, no pasa nada.", "",
               "Saludos,", "Leonardo Apollonio", "Desarrollador web", "{sig}", ADDRESS, "",
               'Si prefieren que no les escriba más, respondan "no" y listo.']),
    "pt": dict(
        subject="Fiz um site de exemplo para {name}",
        lines=["Olá, tudo bem?", "", "Meu nome é Leonardo Apollonio, sou desenvolvedor de software e faço sites para negócios.", "",
               "{hook} {situation}", "",
               "Por isso montei um exemplo de como poderia ficar o site de vocês, com {parts}:",
               "{url}", "",
               "É grátis e sem compromisso. Se gostarem, eu termino com as fotos de vocês e um domínio próprio; se não, tudo bem.", "",
               "Abraço,", "Leonardo Apollonio", "Desenvolvedor web", "{sig}", ADDRESS, "",
               'Se preferirem não receber mais mensagens minhas, é só responder "não".']),
    "en": dict(
        subject="I made a sample website for {name}",
        lines=["Hi there,", "", "My name is Leonardo Apollonio. I'm a software developer and I build websites for small businesses.", "",
               "{hook} {situation}", "",
               "So I put together a free sample of how your website could look, with {parts}:",
               "{url}", "",
               "It's free and there's no commitment. If you like it, I can finish it with your photos and your own domain; if not, no problem at all.", "",
               "Leonardo Apollonio", "Web developer", "{sig}", ADDRESS, "",
               "If you'd rather not hear from me again, just reply \"no\" and I won't write again."]),
}


EMAIL_FOLLOWUP = {  # para negocios a los que ya se les escribió antes sin muestra (pedido de Leo, 24/10/2026)
    "es": dict(
        subject="Muestra de página para {name}",
        lines=["Hola, cómo están?", "",
               "Hace poco les escribí por una página web para {name}. Para que se den una idea, ya les armé una muestra con {parts}:",
               "{url}", "",
               "Es gratis y sin compromiso. Si les gusta, la termino con sus fotos y su propio dominio; si no, no pasa nada.", "",
               "Saludos,", "Leonardo Apollonio", "Desarrollador web", "{sig}", ADDRESS, "",
               'Si prefieren que no les escriba más, respondan "no" y listo.']),
    "pt": dict(
        subject="Site de exemplo para {name}",
        lines=["Olá, tudo bem?", "",
               "Há pouco tempo escrevi para vocês sobre um site para {name}. Para vocês terem uma ideia, já montei um exemplo com {parts}:",
               "{url}", "",
               "É grátis e sem compromisso. Se gostarem, eu termino com as fotos de vocês e um domínio próprio; se não, tudo bem.", "",
               "Abraço,", "Leonardo Apollonio", "Desenvolvedor web", "{sig}", ADDRESS, "",
               'Se preferirem não receber mais mensagens minhas, é só responder "não".']),
    "en": dict(
        subject="Sample website for {name}",
        lines=["Hi there,", "",
               "I wrote to you recently about a website for {name}. To give you a better idea, I went ahead and built a free sample with {parts}:",
               "{url}", "",
               "It's free and there's no commitment. If you like it, I can finish it with your photos and your own domain; if not, no problem at all.", "",
               "Leonardo Apollonio", "Web developer", "{sig}", ADDRESS, "",
               "If you'd rather not hear from me again, just reply \"no\" and I won't write again."]),
}


def slugify(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.lower()).strip("-")
    return re.sub(r"-+", "-", s)[:60].strip("-")


def esc(s):
    return html.escape(str(s or ""), quote=True)


def excluded_country(country):
    c = norm(country)
    return any(re.search(r"(?<![a-z])" + re.escape(x) + r"(?![a-z])", c) for x in EXCLUDED)


def fmt_rating(r, lang):
    try:
        v = float(str(r).replace(",", "."))
    except Exception:
        return ""
    s = f"{v:.1f}"
    return s.replace(".", ",") if lang in ("es", "pt") else s


def fmt_n(n, lang):
    try:
        v = int(re.sub(r"[^0-9]", "", str(n)))
    except Exception:
        return ""
    s = f"{v:,}"
    return s.replace(",", ".") if lang in ("es", "pt") else s


def month_label(d, lang):
    m = re.match(r"(\d{4})-(\d{1,2})", str(d or ""))
    if not m:
        return ""
    y, mo = int(m.group(1)), int(m.group(2))
    return f"{MONTHS[lang][mo - 1]} {y}" if 1 <= mo <= 12 else ""


def wa_number(phone, country):
    p = str(phone or "").strip()
    digits = re.sub(r"\D", "", p)
    if not digits:
        return ""
    if p.startswith("+"):
        return digits
    if p.startswith("00"):
        return digits[2:]
    cc = CC.get(ckey(country), "")
    if not cc:
        return ""
    if cc == "1":
        return digits if len(digits) == 11 and digits.startswith("1") else ("1" + digits if len(digits) == 10 else "")
    if digits.startswith(cc) and len(digits) > len(cc) + 6:
        return digits
    if cc in TRUNK0 and digits.startswith("0"):
        digits = digits[1:]
    return cc + digits


def contact(phone, country):
    """("wa", número) si es celular, ("tel", número) si es fijo o país de llamada, ("", "") si no sirve."""
    num = wa_number(phone, country)
    if not num:
        return "", ""
    c = ckey(country)
    cc = CC.get(c, "")
    if c in CALL_FIRST:
        return ("tel", num) if len(num) == 11 and num.startswith("1") else ("", "")
    if cc == "55" and num.startswith("55"):
        nat = num[2:]
        if len(nat) == 10 and nat[2] in "6789":  # celular viejo sin el 9 inicial
            nat = nat[:2] + "9" + nat[2:]
        if len(nat) == 11 and nat[2] == "9":
            return "wa", "55" + nat
        return ("tel", "55" + nat) if len(nat) == 10 else ("", "")
    if cc in MOBILE and num.startswith(cc):
        nat = num[len(cc):]
        ok, lens = MOBILE[cc]
        if ok(nat):
            return "wa", num
        return ("tel", num) if len(nat) in lens else ("", "")
    return "wa", num


def validate(raw, existing_slugs, seen_emails, today):
    """Devuelve (lead_normalizado, None) o (None, motivo)."""
    L = dict(raw)
    L["followup"] = bool(L.get("followup"))
    need = ["name", "town", "country", "email", "lang"] + ([] if L["followup"] else ["hook_sentence", "situation_sentence"])
    for k in need:
        if not str(L.get(k) or "").strip():
            return None, f"falta {k}"
    L["name"] = str(L["name"]).strip()
    L["email"] = em = str(L["email"]).strip().lower()
    if not re.fullmatch(r"[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}", em):
        return None, "email raro"
    if em in seen_emails:
        return None, "email repetido en la tanda"
    if L["lang"] not in T:
        return None, "lang tiene que ser es, pt o en"
    if excluded_country(L["country"]):
        return None, "país excluido"
    d = str(L.get("newest_review_date") or "")
    m = re.match(r"(\d{4})-(\d{2})(?:-(\d{2}))?", d)
    if not m:
        return None, "falta newest_review_date (AAAA-MM-DD)"
    dd = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3) or 28))
    if (today - dd).days > 365:
        return None, f"sin actividad en el último año ({d})"
    if str(L.get("rating") or "").strip():
        try:
            if float(str(L["rating"]).replace(",", ".")) < 4.0:
                return None, "puntaje menor a 4"
        except Exception:
            return None, "rating ilegible"
    lang = L["lang"]
    h = str(L.get("hook_sentence") or "").strip()
    if lang in ("es", "pt"):
        h = re.sub(r"(?<![\d.])(\d)\.(\d)(?![\d.])", r"\1,\2", h)
    if h and not h.endswith((".", "!", "?", '"', "”")):
        h += "."
    L["hook_sentence"] = h
    s = str(L.get("situation_sentence") or "").strip()
    L["situation_sentence"] = s if (not s or s.endswith((".", "!", "?"))) else s + "."
    L["quotes"] = [q for q in (L.get("quotes") or [])
                   if isinstance(q, dict) and str(q.get("text") or "").strip() and len(str(q["text"]).split()) <= 15][:3]
    L["dishes"] = [x.strip() for x in (L.get("dishes") or L.get("services") or [])
                   if isinstance(x, str) and 0 < len(x.strip()) <= 45][:6]
    L["kind"] = "service" if str(L.get("kind") or "").strip().lower() in ("service", "servicio", "servicios") else "food"
    L["rating_source"] = str(L.get("rating_source") or "TripAdvisor").strip()
    bu = str(L.get("booking_url") or "").strip()
    L["booking_url"] = bu if re.match(r"https?://", bu) else ""
    if not L.get("slug"):
        base, town = slugify(L["name"]), slugify(L["town"])
        btoks = set(base.split("-"))
        same = town and (town in base or any(len(t) > 3 and t in btoks for t in town.split("-")))
        slug = (base if same else f"{base}-{town}")[:60].strip("-")
        k, s2 = 2, slug
        while s2 in existing_slugs:
            s2 = f"{slug}-{k}"
            k += 1
        L["slug"] = s2
    existing_slugs.add(L["slug"])
    seen_emails.add(em)
    return L, None


def build_page(L):
    lang = L["lang"]
    t = T[lang]
    src = L["rating_source"]
    acc, acc2 = PALETTES[int(hashlib.md5(L["slug"].encode()).hexdigest(), 16) % len(PALETTES)]
    name, town = L["name"], L["town"].strip()
    region = str(L.get("region") or "").strip()
    place = f"{town}, {region}" if region and region.lower() != town.lower() else town
    btype = str(L.get("business_type") or "").strip() or t["default_type"]
    desc = str(L.get("description") or "").strip()
    r, n = fmt_rating(L.get("rating"), lang), fmt_n(L.get("reviews_count"), lang)
    badge = t["badge"].format(r=r, n=n, src=src) if r and n else ""
    kind, num = contact(L.get("phone"), L.get("country"))
    wa_url = f"https://wa.me/{num}?text={urllib.parse.quote(t['wa_text'])}" if kind == "wa" else ""
    tel_url = f"tel:+{num}" if kind == "tel" else ""
    book_url = L["booking_url"]
    q_addr = ", ".join(x for x in [name, str(L.get("address") or "").strip() or town, str(L.get("country") or "")] if x)
    maps_url = "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(q_addr)
    tags = [c for c in (L.get("cuisines") or []) if c][:4] + [f for f in (L.get("features") or []) if f][:5]
    dishes, quotes = L["dishes"], L["quotes"]
    hours = str(L.get("hours") or "").strip()
    addr = str(L.get("address") or "").strip()
    phone_disp = str(L.get("phone") or "").strip() if (wa_url or tel_url) else ""
    price = str(L.get("price_range") or "").strip()

    cta = []
    if book_url:
        cta.append(f'<a class="btn wa" href="{esc(book_url)}">{esc(t["book"])}</a>')
    if wa_url:
        cta.append(f'<a class="btn {"ghost" if book_url else "wa"}" href="{esc(wa_url)}">{esc(t["wa"])}</a>')
    elif tel_url:
        cta.append(f'<a class="btn {"ghost" if book_url else "wa"}" href="{esc(tel_url)}">{esc(t["call"])}</a>')
    cta.append(f'<a class="btn ghost" href="{esc(maps_url)}">{esc(t["maps"])}</a>')

    sec = []
    if tags:
        sec.append(f'<section><div class="wrap"><h2>{esc(t["about"])}</h2><div class="tags">'
                   + "".join(f"<span>{esc(x)}</span>" for x in tags) + "</div></div></section>")
    if dishes:
        fav = t["fav_service"] if L["kind"] == "service" else t["fav_food"]
        sec.append(f'<section><div class="wrap"><h2>{esc(fav)}</h2><ul class="menu">'
                   + "".join(f"<li>{esc(d)}</li>" for d in dishes) + "</ul></div></section>")
    if quotes:
        figs = []
        for q in quotes:
            mlab = month_label(q.get("date"), lang) if str(q.get("date") or "")[:7] >= "2025-06" else ""
            cap = t["revcap"].format(src=src) + (f", {mlab}" if mlab else "")
            qt = str(q["text"]).strip().strip('"').strip("“”").strip()
            if qt and qt[0].islower():
                qt = "…" + qt
            figs.append(f'<figure><blockquote>“{esc(qt)}”</blockquote><figcaption>{esc(cap)}</figcaption></figure>')
        revs = t.get("revs_service", t["revs"]) if L["kind"] == "service" else t["revs"]
        sec.append(f'<section><div class="wrap"><h2>{esc(revs)}</h2><div class="revs">' + "".join(figs) + "</div></div></section>")
    tiles = "".join(f'<div class="tile t{i}"><span>{esc(t["photo_ph"])}</span></div>' for i in range(1, 7))
    sec.append(f'<section><div class="wrap"><h2>{esc(t["photos"])}</h2><div class="grid">{tiles}</div></div></section>')
    fallback = t["hours_wa"] if wa_url else (t["hours_tel"] if tel_url else t["hours_maps"])
    left = f'<h3>{esc(t["hours"])}</h3><p>{esc(hours or fallback)}</p>'
    if price:
        left += f'<h3>{esc(t["price"])}</h3><p>{esc(price)}</p>'
    left += f'<h3>{esc(t["addr"])}</h3><p>{esc(addr or place)}<br><a href="{esc(maps_url)}">{esc(t["maps"])}</a></p>'
    right = ""
    if wa_url:
        right += (f'<h3>WhatsApp</h3><p><a href="{esc(wa_url)}">{esc(phone_disp)}</a></p>'
                  f'<p><a class="btn wa" href="{esc(wa_url)}">{esc(t["wa"])}</a></p>')
    elif tel_url:
        right += (f'<h3>{esc(t["tel"])}</h3><p><a href="{esc(tel_url)}">{esc(phone_disp)}</a></p>'
                  f'<p><a class="btn wa" href="{esc(tel_url)}">{esc(t["call"])}</a></p>')
    if book_url:
        right += f'<h3>{esc(t["booking"])}</h3><p><a class="btn wa" href="{esc(book_url)}">{esc(t["book"])}</a></p>'
    sec.append(f'<section><div class="wrap"><h2>{esc(t["info"])}</h2><div class="info"><div>{left}</div><div>{right}</div></div></div></section>')
    if wa_url:
        float_btn = f'<a class="btn wa float" href="{esc(wa_url)}">WhatsApp</a>'
    elif book_url:
        float_btn = f'<a class="btn wa float" href="{esc(book_url)}">{esc(t["book"])}</a>'
    else:
        float_btn = ""
    title = t["title"].format(name=name, type=btype, town=town)

    return f"""<!doctype html>
<html lang="{t['htmllang']}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,800&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>
:root{{--bg:#fbf7f1;--ink:#231a12;--muted:#6d5d4e;--card:#fff;--line:#eadfce;--acc:{acc};--acc2:{acc2};}}
@media (prefers-color-scheme:dark){{:root{{--bg:#16110c;--ink:#f3ebe0;--muted:#bfae9b;--card:#211a13;--line:#3a2e22;}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 Inter,system-ui,sans-serif}}
a{{color:inherit}}.wrap{{max-width:1040px;margin:0 auto;padding:0 20px}}
.banner{{background:var(--ink);color:var(--bg);text-align:center;font-size:13px;padding:8px 16px}}
.banner a{{color:var(--bg)}}
header.hero{{background:linear-gradient(135deg,var(--acc),var(--acc2));color:#fff;padding:72px 0 64px;position:relative;overflow:hidden}}
header.hero:after{{content:"";position:absolute;inset:0;background:radial-gradient(circle at 85% 20%,rgba(255,255,255,.18),transparent 45%),radial-gradient(circle at 10% 90%,rgba(0,0,0,.18),transparent 50%)}}
.hero .wrap{{position:relative;z-index:1}}
.kicker{{text-transform:uppercase;letter-spacing:.14em;font-size:13px;opacity:.9;margin:0}}
h1{{font-family:Fraunces,Georgia,serif;font-weight:800;font-size:clamp(36px,7vw,72px);line-height:1.04;margin:10px 0 14px;overflow-wrap:anywhere}}
.tagline{{font-size:clamp(17px,2.4vw,21px);max-width:620px;margin:0 0 18px;opacity:.95}}
.badge{{display:inline-block;background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.35);border-radius:999px;padding:6px 14px;font-weight:600;margin:0 0 26px}}
.cta{{display:flex;flex-wrap:wrap;gap:12px}}
.btn{{display:inline-block;text-decoration:none;font-weight:600;border-radius:12px;padding:13px 20px}}
.btn.wa{{background:#25D366;color:#073b1d}}.btn.ghost{{border:1.5px solid rgba(255,255,255,.8);color:#fff}}
section{{padding:56px 0;border-bottom:1px solid var(--line)}}
h2{{font-family:Fraunces,Georgia,serif;font-size:clamp(26px,4vw,36px);margin:0 0 20px}}
.tags{{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}}.tags span{{background:var(--card);border:1px solid var(--line);border-radius:999px;padding:4px 12px;font-size:14px;color:var(--muted)}}
ul.menu{{list-style:none;padding:0;margin:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}}
ul.menu li{{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--acc);border-radius:10px;padding:14px 16px;font-weight:600}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}
.tile{{aspect-ratio:4/3;border-radius:12px;display:flex;align-items:flex-end;padding:10px;color:#fff;font-size:13px;background:linear-gradient(160deg,var(--acc2),var(--acc))}}
.tile.t2,.tile.t5{{background:linear-gradient(200deg,var(--acc),#3a2a1c)}}.tile.t3,.tile.t4{{background:linear-gradient(120deg,#3a2a1c,var(--acc2))}}
.tile span{{background:rgba(0,0,0,.35);border-radius:6px;padding:2px 8px}}
.revs{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}}
figure{{margin:0;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px}}
blockquote{{margin:0 0 10px;font-family:Fraunces,Georgia,serif;font-size:19px;line-height:1.35}}
figcaption{{color:var(--muted);font-size:14px}}
.info{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}.info h3{{margin:0 0 6px;font-size:15px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}}
.info p{{margin:0 0 18px}}
.info .btn.ghost{{border-color:var(--ink);color:var(--ink)}}
footer{{padding:32px 0 96px;text-align:center;color:var(--muted);font-size:14px}}
.float{{position:fixed;right:16px;bottom:16px;z-index:5;box-shadow:0 6px 20px rgba(0,0,0,.25)}}
@media (max-width:700px){{.grid{{grid-template-columns:repeat(2,1fr)}}.info{{grid-template-columns:1fr}}header.hero{{padding:56px 0 48px}}}}
</style>
</head>
<body>
<div class="banner">{esc(t['banner'])} · <a href="{SIGNATURE_URL}">web.leonardoapollonio.com</a></div>
<header class="hero"><div class="wrap">
<p class="kicker">{esc(btype)} · {esc(place)}</p>
<h1>{esc(name)}</h1>
{f'<p class="tagline">{esc(desc)}</p>' if desc else ''}
{f'<p class="badge">{esc(badge)}</p>' if badge else ''}
<div class="cta">{''.join(cta)}</div>
</div></header>
<main>
{chr(10).join(sec)}
</main>
<footer>{esc(t['footer'])} · <a href="{SIGNATURE_URL}">web.leonardoapollonio.com</a></footer>
{float_btn}
</body></html>
"""


def parts_text(L):
    p = PARTS[L["lang"]]
    items = [p["rev"] if L["quotes"] else p["rating"].format(src=L["rating_source"])]
    if L["dishes"]:
        items.append(p["service"] if L["kind"] == "service" else p["food"])
    items.append(p["maps"])
    return ", ".join(items[:-1]) + p["conj"] + items[-1]


def build_email(L, url):
    e = (EMAIL_FOLLOWUP if L.get("followup") else EMAIL)[L["lang"]]
    subj = e["subject"].format(name=L["name"])
    vals = dict(hook=L["hook_sentence"], situation=L["situation_sentence"], url=url, parts=parts_text(L))
    body = [ln.format(sig="web.leonardoapollonio.com", name=L["name"], **vals) for ln in e["lines"]]
    hb = []
    for ln in e["lines"]:
        if ln == "{url}":
            hb.append(f'<a href="{esc(url)}">{esc(url)}</a>')
        elif ln == "{sig}":
            hb.append(f'<a href="{SIGNATURE_URL}">web.leonardoapollonio.com</a>')
        else:
            hb.append(esc(ln.format(sig="", name=L["name"], **vals)))
    return subj, "\n".join(body), '<div dir="ltr">' + "<br>\n".join(hb) + "</div>"


def load_leads(path):
    txt = open(path, encoding="utf-8").read().strip()
    if txt.startswith("["):
        return json.loads(txt)
    return [json.loads(l) for l in txt.splitlines() if l.strip()]


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    leads, root, out_path = load_leads(sys.argv[1]), sys.argv[2], sys.argv[3]
    mdir = os.path.join(root, "muestras")
    existing = set(os.listdir(mdir)) if os.path.isdir(mdir) else set()
    seen, ok, bad = set(), [], []
    today = datetime.date.today()
    for raw in leads:
        L, why = validate(raw, existing, seen, today)
        if why:
            bad.append((raw.get("name"), raw.get("email"), why))
        else:
            ok.append(L)
    with open(out_path, "w", encoding="utf-8") as out:
        for L in ok:
            url = BASE_URL + L["slug"] + "/"
            d = os.path.join(mdir, L["slug"])
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
                f.write(build_page(L))
            subj, body, hb = build_email(L, url)
            out.write(json.dumps(dict(to=L["email"], subject=subj, body=body, htmlBody=hb, url=url, slug=L["slug"],
                                      name=L["name"], town=L["town"], country=L["country"], lang=L["lang"],
                                      followup=L["followup"]),
                                 ensure_ascii=False) + "\n")
    print(f"válidos: {len(ok)} · descartados: {len(bad)}")
    for L in ok:
        print(f"  OK  {L['name']} | {L['town']}, {L['country']} | {L['email']} | {BASE_URL}{L['slug']}/")
    for b in bad:
        print(f"  NO  {b[0]} | {b[1]} | {b[2]}")


if __name__ == "__main__":
    main()
