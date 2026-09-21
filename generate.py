import os
import json
import datetime
import requests

from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).parent
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

TOKEN = os.environ.get("TMDB_API_TOKEN") or os.environ.get("TMDB_API_KEY")

if not TOKEN:
    raise SystemExit("Ajoutez TMDB_API_TOKEN dans les secrets GitHub.")

HEAD = {
    "Authorization": f"Bearer {TOKEN}",
    "accept": "application/json",
}

API = "https://api.themoviedb.org/3"
IMG = "https://image.tmdb.org/t/p/original"

OUT = ROOT / "wallpapers"
OUT.mkdir(exist_ok=True)


def get(path, **params):
    r = requests.get(
        API + path,
        headers=HEAD,
        params=params,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def font(size, bold=False):
    if bold:
        path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    else:
        path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

    return ImageFont.truetype(path, size)


def providers(kind, mid):
    """Retourne les plateformes streaming disponibles en France."""

    data = get(
        f"/{kind}/{mid}/watch/providers"
    ).get("results", {}).get("FR", {})

    names = []

    for bucket in ("flatrate", "free", "ads"):
        for provider in data.get(bucket, []):
            name = provider.get("provider_name")

            if name and name not in names:
                names.append(name)

    return names


def discover(kind):
    """
    Recherche les sorties récentes sur plusieurs pages TMDB.
    Les résultats sont demandés directement en français.
    """

    today = datetime.date.today()
    start = today - datetime.timedelta(days=CFG["days_back"])

    if kind == "movie":
        datefield = "primary_release_date"
    else:
        datefield = "first_air_date"

    results = []

    # 5 pages = jusqu'à 100 films + 100 séries
    for page in range(1, 6):

        print(
            f"Recherche TMDB "
            f"{'films' if kind == 'movie' else 'séries'} "
            f"- page {page}"
        )

        data = get(
            f"/discover/{kind}",
            language="fr-FR",
            region="FR",
            sort_by="popularity.desc",
            page=page,
            **{
                f"{datefield}.gte": str(start),
                f"{datefield}.lte": str(today),
            },
        )

        results.extend(data.get("results", []))

        if page >= data.get("total_pages", 1):
            break

    print(
        f"{len(results)} "
        f"{'films' if kind == 'movie' else 'séries'} "
        f"trouvés avant filtrage"
    )

    return results


def wrap(draw, text, fnt, max_width, max_lines=3):
    words = text.split()

    lines = []
    current = ""

    for word in words:

        test = (current + " " + word).strip()

        bbox = draw.textbbox(
            (0, 0),
            test,
            font=fnt,
        )

        width = bbox[2] - bbox[0]

        if width <= max_width:
            current = test

        else:
            if current:
                lines.append(current)

            current = word

            if len(lines) >= max_lines:
                break

    if current and len(lines) < max_lines:
        lines.append(current)

    if len(lines) == max_lines:
        reconstructed = " ".join(lines)

        if len(reconstructed) < len(text):
            lines[-1] = lines[-1].rstrip(" .") + "…"

    return lines


def make(item, kind, prov):
    """Génère un wallpaper 3840x2160 adapté à Projectivy."""

    backdrop = item.get("backdrop_path")

    if not backdrop:
        return None

    response = requests.get(
        IMG + backdrop,
        timeout=30,
    )
    response.raise_for_status()

    im = Image.open(
        BytesIO(response.content)
    ).convert("RGB")

    W = CFG["width"]
    H = CFG["height"]

    scale = max(
        W / im.width,
        H / im.height,
    )

    im = im.resize(
        (
            int(im.width * scale),
            int(im.height * scale),
        ),
        Image.Resampling.LANCZOS,
    )

    left = (im.width - W) // 2
    top = (im.height - H) // 2

    im = im.crop(
        (
            left,
            top,
            left + W,
            top + H,
        )
    )


    # ---------------------------------------------------------
# Dégradé horizontal derrière les informations.
#
# Gauche : sombre pour rendre le texte lisible.
# Droite : totalement transparente pour retrouver
#          progressivement la luminosité du backdrop.
# ---------------------------------------------------------

overlay = Image.new(
    "RGBA",
    (W, H),
    (0, 0, 0, 0),
)

od = ImageDraw.Draw(overlay)

# Jusqu'ici, le fond reste bien sombre.
dark_until = 1050

# À partir de cette position, le backdrop retrouve
# complètement sa luminosité.
fade_until = 2350

# Opacité maximale à gauche.
max_alpha = 205

for x in range(0, fade_until, 8):

    if x <= dark_until:
        alpha = max_alpha

    else:
        progress = (
            (x - dark_until)
            / (fade_until - dark_until)
        )

        # Courbe douce plutôt qu'un dégradé linéaire.
        progress = progress * progress * (3 - 2 * progress)

        alpha = int(
            max_alpha * (1 - progress)
        )

    od.rectangle(
        (x, 0, x + 8, 900),
        fill=(0, 0, 0, alpha),
    )

im = Image.alpha_composite(
    im.convert("RGBA"),
    overlay,
)

    draw = ImageDraw.Draw(im)

    # ---------------------------------------------------------
    # Zone texte
    # ---------------------------------------------------------

    x = 180
    y = 100

    title = (
        item.get("title")
        or item.get("name")
        or "Sans titre"
    )

    date = (
        item.get("release_date")
        or item.get("first_air_date")
        or ""
    )

    year = date[:4] if date else ""

    # Titre : taille adaptative pour éviter les débordements
    title_size = 112

    if len(title) > 25:
        title_size = 90

    if len(title) > 40:
        title_size = 72

    draw.text(
        (x, y),
        title,
        font=font(title_size, True),
        fill="white",
        stroke_width=2,
        stroke_fill=(0, 0, 0, 180),
    )

    y += 135

    media_type = (
        "FILM"
        if kind == "movie"
        else "SÉRIE"
    )

    rating = item.get(
        "vote_average",
        0,
    )

    meta = (
        f"{year}   •   "
        f"{media_type}   •   "
        f"★ {rating:.1f}/10"
    )

    draw.text(
        (x, y),
        meta,
        font=font(42, True),
        fill=(245, 245, 245),
    )

    y += 70

    overview = (
        item.get("overview")
        or "Synopsis français indisponible."
    )

    synopsis_font = font(40)

    for line in wrap(
        draw,
        overview,
        synopsis_font,
        1650,
        3,
    ):
        draw.text(
            (x, y),
            line,
            font=synopsis_font,
            fill=(245, 245, 245),
        )

        y += 52

    y += 22

    draw.text(
        (x, y),
        "DISPONIBLE EN FRANCE",
        font=font(30, True),
        fill=(255, 210, 70),
    )

    y += 43

    provider_text = " • ".join(prov[:4])

    draw.text(
        (x, y),
        provider_text,
        font=font(36, True),
        fill="white",
    )

    # Attribution discrète
    draw.text(
        (x, 820),
        "Disponibilités : données TMDB / JustWatch",
        font=font(22),
        fill=(210, 210, 210),
    )

    filename = (
        f"{'film' if kind == 'movie' else 'serie'}"
        f"-{item['id']}.jpg"
    )

    im.convert("RGB").save(
        OUT / filename,
        "JPEG",
        quality=92,
        optimize=True,
    )

    return filename


def main():

    chosen = []

    stats = {
        "sans_backdrop": 0,
        "sans_synopsis": 0,
        "sans_titre": 0,
        "sans_provider_fr": 0,
        "retenus": 0,
    }

    # ---------------------------------------------------------
    # FILMS + SÉRIES
    # ---------------------------------------------------------

    for kind in ("movie", "tv"):

        items = discover(kind)

        for item in items:

            # Backdrop obligatoire
            if not item.get("backdrop_path"):
                stats["sans_backdrop"] += 1
                continue

            # Synopsis français
            overview = (
                item.get("overview")
                or ""
            ).strip()

            if len(overview) < 30:
                stats["sans_synopsis"] += 1
                continue

            # Titre
            title = (
                item.get("title")
                or item.get("name")
                or ""
            ).strip()

            if not title:
                stats["sans_titre"] += 1
                continue

            # Plateforme française obligatoire
            try:
                prov = providers(
                    kind,
                    item["id"],
                )

            except Exception as exc:
                print(
                    "Erreur providers :",
                    title,
                    exc,
                )
                continue

            if not prov:
                stats["sans_provider_fr"] += 1
                continue

            # -------------------------------------------------
            # Plateformes prioritaires
            # -------------------------------------------------

            if CFG.get("providers"):

                wanted = [
                    p
                    for p in prov
                    if any(
                        wanted_name.lower()
                        in p.lower()
                        for wanted_name
                        in CFG["providers"]
                    )
                ]

                # Si une plateforme préférée est trouvée,
                # on n'affiche que celle(s)-ci.
                # Sinon le contenu reste accepté puisqu'il
                # est tout de même disponible en France.
                if wanted:
                    prov = wanted

            print(
                "RETENU :",
                title,
                "->",
                ", ".join(prov),
            )

            chosen.append(
                (
                    item,
                    kind,
                    prov,
                )
            )

            stats["retenus"] += 1

    # ---------------------------------------------------------
    # Diagnostic
    # ---------------------------------------------------------

    print("")
    print("===== RÉSUMÉ DU FILTRAGE =====")

    for key, value in stats.items():
        print(f"{key}: {value}")

    print("==============================")
    print("")

    # ---------------------------------------------------------
    # Classement
    # ---------------------------------------------------------

    chosen.sort(
        key=lambda t: (
            t[0].get("popularity", 0),
            t[0].get("vote_count", 0),
        ),
        reverse=True,
    )

    chosen = chosen[
        : CFG["max_wallpapers"]
    ]

    print(
        f"{len(chosen)} contenus sélectionnés "
        f"pour génération"
    )

    # ---------------------------------------------------------
    # Nettoyer les anciens wallpapers
    # ---------------------------------------------------------

    for old_file in OUT.glob("*.jpg"):
        old_file.unlink()

    # ---------------------------------------------------------
    # Génération
    # ---------------------------------------------------------

    feed = []

    public_base = os.environ.get(
        "PUBLIC_BASE_URL",
        "https://example.invalid",
    ).rstrip("/")

    for item, kind, prov in chosen:

        title = (
            item.get("title")
            or item.get("name")
            or ""
        )

        try:

            filename = make(
                item,
                kind,
                prov,
            )

            if not filename:
                continue

            feed.append(
                {
                    "location": "France",
                    "title": title,
                    "author": "TMDB / JustWatch",
                    "url_img": (
                        f"{public_base}/"
                        f"wallpapers/{filename}"
                    ),
                }
            )

            print(
                "WALLPAPER OK :",
                title,
            )

        except Exception as exc:

            print(
                "ERREUR WALLPAPER :",
                title,
                exc,
            )

    # ---------------------------------------------------------
    # JSON OVERFLIGHT
    # ---------------------------------------------------------

    with open(
        ROOT / "wallpapers.json",
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            feed,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print("")
    print(
        f"{len(feed)} wallpapers générés."
    )


if __name__ == "__main__":
    main()
