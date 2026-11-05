"""
Agente Imagem — gera imagens 1200x1200 com Pillow para posts do LinkedIn.

4 templates com identidade visual Davi Hoffmann / Operacao Certa:
  - numero-grande  : gradiente navy + circulos geometricos + numero dourado
  - tipografia     : gradiente + aspas decorativas gigantes + barra accent
  - comparacao     : gradiente + colunas com fills coloridos e badges
  - whatsapp-mock  : gradiente creme + frame de telefone com sombra

Fontes baixadas automaticamente e cacheadas em data/fonts/.
Saida: data/images/{post_id}.png
"""
import json
import math
import os
import urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# ─── cores da marca ──────────────────────────────────────────────────────────
NAVY    = (26,  39,  84)
NAVY_D  = (13,  20,  46)    # navy mais escuro — topo dos gradientes
CREME   = (245, 241, 234)
CREME_S = (225, 218, 202)   # creme mais escuro — topo dos gradientes creme
ACCENT  = (201, 183, 138)   # dourado principal
ACCENT_D= (158, 143, 103)   # dourado escuro para destaques secundarios
RED     = (179,  45,  45)
GREEN   = ( 68, 188, 110)   # verde vivo
ORANGE  = (228, 100,  52)   # laranja vivo
WA_BG   = (233, 228, 220)
WA_HDR  = (  7,  94,  84)
WHITE   = (255, 255, 255)
DARK    = ( 17,  17,  17)

SIZE = 1200

DATA_DIR  = Path(__file__).parent.parent / "data"
FONTS_DIR = DATA_DIR / "fonts"
IMG_DIR   = DATA_DIR / "images"

DATA_DIR.mkdir(exist_ok=True)
FONTS_DIR.mkdir(exist_ok=True)
IMG_DIR.mkdir(exist_ok=True)

# ─── URLs das fontes ─────────────────────────────────────────────────────────
_FONT_URLS = {
    "playfair-bold": "https://cdn.jsdelivr.net/gh/google/fonts@main/ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf",
    "playfair-reg":  "https://cdn.jsdelivr.net/gh/google/fonts@main/ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf",
    "inter-reg":     "https://github.com/rsms/inter/releases/download/v4.0/Inter-4.0.zip",
    "inter-bold":    "https://github.com/rsms/inter/releases/download/v4.0/Inter-4.0.zip",
    "inter-medium":  "https://github.com/rsms/inter/releases/download/v4.0/Inter-4.0.zip",
    "inter-semibold":"https://github.com/rsms/inter/releases/download/v4.0/Inter-4.0.zip",
}

_font_cache: dict[str, ImageFont.FreeTypeFont] = {}


def _first_existing(paths: list[str]) -> str | None:
    for p in paths:
        if Path(p).exists():
            return p
    return None


def _download_playfair(variant: str) -> Path | None:
    dest = FONTS_DIR / f"{variant}.ttf"
    if dest.exists():
        return dest
    url = "https://cdn.jsdelivr.net/gh/google/fonts@main/ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf"
    print("  [Font] Baixando Playfair Display...")
    try:
        urllib.request.urlretrieve(url, dest)
        return dest
    except Exception as e:
        print(f"  [Font] Falha ao baixar Playfair: {e}")
        dest.unlink(missing_ok=True)
        return None


def _download_inter_zip() -> bool:
    import zipfile
    zip_path = FONTS_DIR / "inter.zip"
    if any(FONTS_DIR.glob("Inter*.ttf")):
        return True
    url = "https://github.com/rsms/inter/releases/download/v4.0/Inter-4.0.zip"
    print("  [Font] Baixando Inter v4...")
    try:
        urllib.request.urlretrieve(url, zip_path)
        with zipfile.ZipFile(zip_path) as z:
            for member in z.namelist():
                fname = Path(member).name
                if (fname.endswith(".ttf")
                        and "InterDisplay" not in fname
                        and fname.startswith("Inter")):
                    target = FONTS_DIR / fname
                    if not target.exists():
                        target.write_bytes(z.read(member))
        zip_path.unlink(missing_ok=True)
        return True
    except Exception as e:
        print(f"  [Font] Falha ao baixar Inter: {e}")
        zip_path.unlink(missing_ok=True)
        return False


def _inter_path(weight: str) -> Path | None:
    candidates = {
        "reg":      ["Inter-Regular.ttf", "InterVariable.ttf", "Inter[wght].ttf"],
        "bold":     ["Inter-Bold.ttf",    "InterVariable.ttf", "Inter[wght].ttf"],
        "medium":   ["Inter-Medium.ttf",  "InterVariable.ttf", "Inter-Regular.ttf"],
        "semibold": ["Inter-SemiBold.ttf","InterVariable.ttf", "Inter-Bold.ttf"],
    }
    for fname in candidates.get(weight, ["InterVariable.ttf"]):
        p = FONTS_DIR / fname
        if p.exists():
            return p
    return None


def _font(name: str, size: int) -> ImageFont.ImageFont:
    cache_key = f"{name}:{size}"
    if cache_key in _font_cache:
        return _font_cache[cache_key]

    path_str: str | None = None
    is_playfair = name.startswith("playfair")
    weight_key  = name.split("-")[-1] if "-" in name else "reg"

    if is_playfair:
        for fname in ["playfair-bold.ttf", "playfair-reg.ttf", "PlayfairDisplay[wght].ttf"]:
            p = FONTS_DIR / fname
            if p.exists():
                path_str = str(p)
                break
        if not path_str:
            dl = _download_playfair(name)
            if dl:
                path_str = str(dl)
        if not path_str:
            sys_name = "georgiab.ttf" if "bold" in name else "georgia.ttf"
            path_str = _first_existing([
                f"C:/Windows/Fonts/{sys_name}",
                "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
            ])
    else:
        p = _inter_path(weight_key)
        if not p:
            _download_inter_zip()
            p = _inter_path(weight_key)
        if p:
            path_str = str(p)
        if not path_str:
            is_bold = weight_key in ("bold", "semibold")
            path_str = _first_existing([
                f"C:/Windows/Fonts/{'arialbd' if is_bold else 'arial'}.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ])

    if path_str:
        try:
            f = ImageFont.truetype(path_str, size)
            _font_cache[cache_key] = f
            return f
        except Exception as e:
            print(f"  [Font] Erro ao carregar {path_str}: {e}")

    return ImageFont.load_default()


# ─── helpers de composicao visual ─────────────────────────────────────────────

def _gradient_bg(color1: tuple, color2: tuple) -> Image.Image:
    """Gradiente vertical de color1 (topo) para color2 (base)."""
    img  = Image.new("RGB", (SIZE, SIZE))
    draw = ImageDraw.Draw(img)
    for y in range(SIZE):
        t = y / (SIZE - 1)
        c = tuple(int(color1[i] + (color2[i] - color1[i]) * t) for i in range(3))
        draw.line([(0, y), (SIZE - 1, y)], fill=c)
    return img


def _overlay_circle(img: Image.Image, cx: int, cy: int, radius: int,
                    color: tuple, opacity: float) -> Image.Image:
    """Sobrepoe circulo com transparencia real via RGBA alpha composite."""
    ov = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(ov).ellipse(
        [cx - radius, cy - radius, cx + radius, cy + radius],
        fill=(*color, int(opacity * 255)),
    )
    return Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")


def _overlay_text_alpha(img: Image.Image, text: str, font,
                        pos: tuple, color: tuple, opacity: float) -> Image.Image:
    """Desenha texto com transparencia real via RGBA alpha composite."""
    ov = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(ov).text(pos, text, font=font, fill=(*color, int(opacity * 255)))
    return Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")


# ─── utilitarios de desenho ───────────────────────────────────────────────────

def _brand_mark(draw: ImageDraw.ImageDraw, fg: tuple):
    """Marca 'Davi Hoffmann' no canto inferior direito."""
    font = _font("inter-reg", 22)
    text = "Davi Hoffmann"
    x = SIZE - 44
    y = SIZE - 52
    color = tuple(int(f * 0.55 + b * 0.45) for f, b in zip(fg, (0, 0, 0)))
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text((x - tw, y), text, font=font, fill=color)
    hx = x - tw - 30
    hy = y + 4
    pts = _hex_points(hx + 11, hy + 11, 11)
    draw.polygon(pts, outline=color, width=2)
    cx, cy = hx + 11, hy + 11
    top = pts[0]
    draw.line([cx, cy, top[0], top[1]], fill=color, width=1)
    draw.line([cx, cy, pts[2][0], pts[2][1]], fill=color, width=1)
    draw.line([cx, cy, pts[4][0], pts[4][1]], fill=color, width=1)


def _hex_points(cx, cy, r):
    return [
        (cx + r * math.sin(math.radians(60 * i - 90)),
         cy + r * math.cos(math.radians(60 * i - 90)))
        for i in range(6)
    ]


def _draw_text_wrap(draw, text, font, x, y, max_width, fill,
                    align="center", line_spacing=1.3):
    """Quebra texto e desenha multiplas linhas centradas em y."""
    words = text.split()
    lines = []
    current = []
    for word in words:
        test = " ".join(current + [word])
        bb = draw.textbbox((0, 0), test, font=font)
        if bb[2] - bb[0] > max_width and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))

    font_size = font.size if hasattr(font, "size") else 20
    line_h  = int(font_size * line_spacing)
    total_h = line_h * len(lines)
    cy = y - total_h // 2

    for line in lines:
        bb = draw.textbbox((0, 0), line, font=font)
        lw = bb[2] - bb[0]
        if align == "center":
            lx = x - lw // 2
        elif align == "right":
            lx = x - lw
        else:
            lx = x
        draw.text((lx, cy), line, font=font, fill=fill)
        cy += line_h

    return total_h


def _text_height(draw, text, font, max_width, line_spacing=1.3):
    """Calcula altura total do texto quebrado (sem desenhar)."""
    words = text.split()
    lines = []
    current = []
    for word in words:
        test = " ".join(current + [word])
        bb = draw.textbbox((0, 0), test, font=font)
        if bb[2] - bb[0] > max_width and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    font_size = font.size if hasattr(font, "size") else 20
    return int(font_size * line_spacing) * len(lines)


# ─── template: numero-grande ─────────────────────────────────────────────────

def _tmpl_numero_grande(brief: dict) -> Image.Image:
    """
    Gradiente navy escuro -> navy.
    Circulos geometricos sangrando pelas bordas.
    Numero em dourado (Playfair) + legenda em creme.
    brief: {"template":"numero-grande","numero":"61%","subtitulo":"...","subtitulo2":"..."}
    """
    numero    = brief.get("numero", "?")
    subtitulo = brief.get("subtitulo", "")
    sub2      = brief.get("subtitulo2", "")

    # ── Fundo + circulos geometricos ─────────────────────────────
    img = _gradient_bg(NAVY_D, NAVY)
    # Circulo dourado grande sangrando canto superior direito
    img = _overlay_circle(img, cx=SIZE + 100, cy=-100, radius=640, color=ACCENT,  opacity=0.13)
    # Circulo creme sangrando canto inferior esquerdo
    img = _overlay_circle(img, cx=-80,        cy=SIZE + 80, radius=340, color=CREME,   opacity=0.07)
    # Circulo accent secundario (textura lateral esquerda)
    img = _overlay_circle(img, cx=70,         cy=SIZE // 2, radius=190, color=ACCENT,  opacity=0.05)

    draw = ImageDraw.Draw(img)

    caption = " ".join(filter(None, [subtitulo, sub2]))

    # ── Tamanho de fonte dinamico ─────────────────────────────────
    n_len   = len(numero)
    tem_cap = bool(caption)
    if n_len <= 2:
        n_size = 420 if not tem_cap else 360
    elif n_len <= 3:
        n_size = 360 if not tem_cap else 300
    elif n_len <= 4:
        n_size = 290 if not tem_cap else 240
    else:
        n_size = 230

    fn   = _font("playfair-bold", n_size)
    bb   = draw.textbbox((0, 0), numero, font=fn)
    nw   = bb[2] - bb[0]
    bb_h = bb[3] - bb[1]

    # Playfair Display: descenders longos nao capturados por textbbox.
    # Fator 1.60 garante margem segura para qualquer combinacao de digitos/%.
    DESCENDER_FACTOR = 1.60
    num_visual_h = int(bb_h * DESCENDER_FACTOR)

    PAD = 120
    GAP = 80

    fc    = _font("inter-reg", 34)
    cap_h = _text_height(draw, caption, fc, 860) if caption else 0

    bloco_h = num_visual_h + (GAP + cap_h if caption else 0)
    area    = SIZE - 2 * PAD
    top_y   = PAD + max(0, (area - bloco_h) // 2)

    # Numero em dourado — maxima visibilidade no fundo navy
    nx = SIZE // 2 - nw // 2
    draw.text((nx, top_y), numero, font=fn, fill=ACCENT)

    if caption:
        # Divisor accent entre numero e legenda
        rule_y = top_y + num_visual_h + GAP // 2 - 2
        draw.rectangle([SIZE // 2 - 70, rule_y, SIZE // 2 + 70, rule_y + 3], fill=ACCENT)

        cap_top    = top_y + num_visual_h + GAP
        cap_center = cap_top + cap_h // 2
        _draw_text_wrap(draw, caption, fc, SIZE // 2, cap_center, 860, CREME, align="center")

    _brand_mark(draw, CREME)
    return img


# ─── template: tipografia ────────────────────────────────────────────────────

def _tmpl_tipografia(brief: dict) -> Image.Image:
    """
    Gradiente navy/creme + aspas decorativas gigantes (opacidade baixa) + barra accent vertical.
    brief: {"template":"tipografia","linha1":"...","linha2":"...","linha3":"...","fundo":"navy"}
    """
    fundo   = brief.get("fundo", "navy").lower()
    is_navy = fundo == "navy"

    img = _gradient_bg(NAVY_D, NAVY) if is_navy else _gradient_bg(CREME_S, CREME)
    fg      = CREME if is_navy else NAVY
    accent_c = ACCENT if is_navy else NAVY

    linha1 = brief.get("linha1", "")
    linha2 = brief.get("linha2", "")
    linha3 = brief.get("linha3", "")
    linhas = [l for l in [linha1, linha2, linha3] if l]

    if not linhas:
        draw = ImageDraw.Draw(img)
        _brand_mark(draw, fg)
        return img

    # Circulo geometrico canto inferior direito (textura)
    img = _overlay_circle(img, cx=SIZE + 80, cy=SIZE + 80, radius=520, color=accent_c, opacity=0.09)

    # Aspas decorativas gigantes (canto superior esquerdo, sangrando)
    fq  = _font("playfair-bold", 380)
    img = _overlay_text_alpha(img, "“", fq, (-50, -130), accent_c, opacity=0.18)

    draw = ImageDraw.Draw(img)

    # Tamanho de fonte adaptativo ao comprimento
    max_len = max(len(l) for l in linhas)
    if max_len <= 14:
        fsize = 108
    elif max_len <= 20:
        fsize = 86
    elif max_len <= 28:
        fsize = 68
    else:
        fsize = 54

    fp        = _font("playfair-bold", fsize)
    padding   = 110
    text_max_w = SIZE - 2 * padding
    line_gap  = int(fsize * 0.28)

    # Calcula altura total real (com quebras de linha)
    total_h = 0
    for linha in linhas:
        total_h += _text_height(draw, linha, fp, text_max_w) + line_gap
    total_h -= line_gap  # remove o ultimo gap

    y_start = SIZE // 2 - total_h // 2

    # Barra accent vertical a esquerda do bloco de texto
    bar_x = padding - 30
    draw.rectangle([bar_x, y_start - 10, bar_x + 6, y_start + total_h + 10], fill=ACCENT)

    cy = y_start
    for i, linha in enumerate(linhas):
        # Ultima linha em accent para hierarquia visual
        color = ACCENT if (i == len(linhas) - 1 and len(linhas) > 1) else fg
        lh = _text_height(draw, linha, fp, text_max_w)
        _draw_text_wrap(draw, linha, fp, SIZE // 2, cy + lh // 2, text_max_w, color, align="center")
        cy += lh + line_gap

    _brand_mark(draw, fg)
    return img


# ─── template: comparacao ────────────────────────────────────────────────────

def _tmpl_comparacao(brief: dict) -> Image.Image:
    """
    Gradiente navy + colunas com fills coloridos + badges de label vibrantes.
    brief: {
      "template":"comparacao",
      "titulo":"...",
      "esquerdo_label":"...", "esquerdo_itens":[...],
      "direito_label":"...",  "direito_itens":[...]
    }
    """
    titulo   = brief.get("titulo", "")
    e_label  = brief.get("esquerdo_label", "Antes")
    e_itens  = brief.get("esquerdo_itens", [])
    d_label  = brief.get("direito_label", "Depois")
    d_itens  = brief.get("direito_itens", [])

    img = _gradient_bg(NAVY_D, NAVY)
    # Circulo central grande (textura sutil)
    img = _overlay_circle(img, cx=SIZE // 2, cy=SIZE // 2, radius=720, color=ACCENT, opacity=0.04)
    # Circulo canto superior direito
    img = _overlay_circle(img, cx=SIZE + 60, cy=-60, radius=380, color=CREME, opacity=0.05)

    draw = ImageDraw.Draw(img)
    PAD  = 80

    # Titulo
    ft = _font("playfair-bold", 54)
    title_y = PAD + 20
    th = _text_height(draw, titulo, ft, SIZE - 2 * PAD)
    _draw_text_wrap(draw, titulo, ft, SIZE // 2, title_y + th // 2 + 10,
                    SIZE - 2 * PAD, CREME, align="center")
    title_bottom = title_y + th + 50

    # Linha accent abaixo do titulo
    rule_y = title_bottom - 18
    draw.rectangle([PAD, rule_y, SIZE - PAD, rule_y + 2], fill=ACCENT)

    # Colunas
    GAP   = 40
    col_w = (SIZE - 2 * PAD - GAP) // 2
    col_h = SIZE - title_bottom - PAD - 10
    l_x   = PAD
    r_x   = PAD + col_w + GAP

    def _draw_col(x, y, w, h, label, itens, label_color):
        # Fundo colorido sutil (blend da cor com navy escuro)
        fill_bg = tuple(int(label_color[i] * 0.09 + NAVY_D[i] * 0.91) for i in range(3))
        draw.rounded_rectangle([x, y, x + w, y + h], radius=18, fill=fill_bg)

        # Barra superior colorida (6px)
        draw.rounded_rectangle([x, y, x + w, y + 7], radius=4, fill=label_color)

        # Badge do label
        fl     = _font("inter-bold", 19)
        lbl_up = label.upper()
        bb_l   = draw.textbbox((0, 0), lbl_up, font=fl)
        lbl_w  = bb_l[2] - bb_l[0]
        lbl_h  = bb_l[3] - bb_l[1]
        bx, by = x + 30, y + 22
        bpad   = 10
        draw.rounded_rectangle(
            [bx - bpad, by - 6, bx + lbl_w + bpad, by + lbl_h + 6],
            radius=8, fill=label_color,
        )
        draw.text((bx, by), lbl_up, font=fl, fill=DARK)

        # Separador
        sep_y = by + lbl_h + 18
        sep_c = tuple(int(c * 0.22 + n * 0.78) for c, n in zip(CREME, NAVY_D))
        draw.line([x + 30, sep_y, x + w - 30, sep_y], fill=sep_c, width=1)

        # Itens
        fi     = _font("inter-reg", 23)
        item_y = sep_y + 20
        for item in itens[:5]:
            draw.text((x + 30, item_y), "— " + item, font=fi, fill=CREME)
            item_y += 46

    _draw_col(l_x, title_bottom, col_w, col_h, e_label, e_itens, ORANGE)
    _draw_col(r_x, title_bottom, col_w, col_h, d_label, d_itens, GREEN)

    _brand_mark(draw, CREME)
    return img


# ─── template: whatsapp-mock ─────────────────────────────────────────────────

def _tmpl_whatsapp_mock(brief: dict) -> Image.Image:
    """
    Gradiente creme + phone frame com sombra + mockup de chat WhatsApp.
    brief: {
      "template":"whatsapp-mock",
      "titulo":"...",
      "conversas":[{"nome":"...","mensagem":"...","tempo":"..."}]
    }
    """
    titulo    = brief.get("titulo", "")
    conversas = brief.get("conversas", [])

    # Fundo gradiente creme
    img = _gradient_bg(CREME_S, CREME)
    # Circulos navy como textura nos cantos
    img = _overlay_circle(img, cx=SIZE + 80, cy=SIZE + 80, radius=440, color=NAVY, opacity=0.06)
    img = _overlay_circle(img, cx=-60,       cy=-60,       radius=230, color=NAVY, opacity=0.04)

    draw = ImageDraw.Draw(img)
    PAD  = 80

    # Titulo
    ft = _font("playfair-bold", 52)
    title_y = PAD
    th = _text_height(draw, titulo, ft, SIZE - 2 * PAD, line_spacing=1.3)
    _draw_text_wrap(draw, titulo, ft, SIZE // 2, title_y + th // 2 + 10,
                    SIZE - 2 * PAD, NAVY, align="center")
    title_bottom = title_y + th + 60

    # Phone mockup
    phone_w = 760
    phone_x = (SIZE - phone_w) // 2
    hdr_h   = 72
    item_h  = 88
    n_convs = min(len(conversas), 5)
    phone_h = hdr_h + item_h * n_convs + 12

    remaining = SIZE - title_bottom - PAD
    gap_top   = max(40, (remaining - phone_h) // 2)
    phone_y   = title_bottom + gap_top

    # Sombra do phone (deslocada 10px diagonal)
    draw.rounded_rectangle(
        [phone_x + 10, phone_y + 10, phone_x + phone_w + 10, phone_y + phone_h + 10],
        radius=28, fill=(185, 175, 160),
    )

    # Fundo do phone
    draw.rounded_rectangle([phone_x, phone_y, phone_x + phone_w, phone_y + phone_h],
                            radius=28, fill=WA_BG)
    draw.rounded_rectangle([phone_x, phone_y, phone_x + phone_w, phone_y + phone_h],
                            radius=28, outline=(175, 168, 155), width=2)

    # Header
    draw.rounded_rectangle([phone_x, phone_y, phone_x + phone_w, phone_y + hdr_h],
                            radius=28, fill=WA_HDR)
    draw.rectangle([phone_x, phone_y + hdr_h - 28, phone_x + phone_w, phone_y + hdr_h],
                   fill=WA_HDR)

    fhdr  = _font("inter-semibold", 22)
    dot_x = phone_x + 26
    dot_y = phone_y + hdr_h // 2
    draw.ellipse([dot_x, dot_y - 6, dot_x + 12, dot_y + 6], fill=(74, 222, 128))
    draw.text((dot_x + 22, phone_y + hdr_h // 2 - 12),
              "WhatsApp Business  Online", font=fhdr, fill=WHITE)

    # Conversas
    conv_y      = phone_y + hdr_h
    fname       = _font("inter-semibold", 22)
    fmsg        = _font("inter-reg",      18)
    ftime       = _font("inter-bold",     16)
    avatar_font = _font("inter-bold",     22)

    for conv in conversas[:5]:
        nome     = conv.get("nome", "")
        mensagem = conv.get("mensagem", "")
        tempo    = conv.get("tempo", "")

        draw.rectangle([phone_x, conv_y, phone_x + phone_w, conv_y + item_h], fill=WHITE)
        draw.line([phone_x, conv_y + item_h - 1, phone_x + phone_w, conv_y + item_h - 1],
                  fill=(218, 212, 202), width=1)

        # Avatar
        av_x = phone_x + 26
        av_y = conv_y + item_h // 2
        draw.ellipse([av_x, av_y - 32, av_x + 64, av_y + 32], fill=(218, 210, 195))
        initials = "".join(p[0].upper() for p in nome.split()[:2]) if nome else "?"
        bb  = draw.textbbox((0, 0), initials, font=avatar_font)
        iw  = bb[2] - bb[0]
        draw.text((av_x + 32 - iw // 2, av_y - 13), initials, font=avatar_font, fill=NAVY)

        # Nome e mensagem
        tx = av_x + 78
        draw.text((tx, conv_y + 18), nome, font=fname, fill=DARK)
        msg_short = mensagem if len(mensagem) <= 45 else mensagem[:42] + "..."
        draw.text((tx, conv_y + 50), msg_short, font=fmsg, fill=(102, 102, 102))

        # Badge de tempo
        bb_t  = draw.textbbox((0, 0), tempo, font=ftime)
        tw    = bb_t[2] - bb_t[0]
        t_x   = phone_x + phone_w - 26 - tw
        bpad  = 6
        draw.rounded_rectangle(
            [t_x - bpad, conv_y + 28, t_x + tw + bpad,
             conv_y + 28 + (bb_t[3] - bb_t[1]) + bpad * 2],
            radius=12, fill=(248, 215, 215),
        )
        draw.text((t_x, conv_y + 31), tempo, font=ftime, fill=RED)

        conv_y += item_h

    _brand_mark(draw, NAVY)
    return img


# ─── template: passo-a-passo ─────────────────────────────────────────────────

def _tmpl_passo_a_passo(brief: dict) -> Image.Image:
    """
    Checklist numerado — o formato que gera salvamento (estrategia v2).
    Gradiente navy + titulo + passos numerados em cards + rodape opcional.
    brief: {"template":"passo-a-passo","titulo":"...","passos":["...","..."],"rodape":"..."}
    """
    titulo = brief.get("titulo", "")
    passos = [p for p in brief.get("passos", []) if p][:6]
    rodape = brief.get("rodape", "")

    img = _gradient_bg(NAVY_D, NAVY)
    img = _overlay_circle(img, cx=SIZE + 100, cy=-100, radius=520, color=ACCENT, opacity=0.10)
    img = _overlay_circle(img, cx=-80, cy=SIZE + 80, radius=320, color=CREME, opacity=0.06)

    draw = ImageDraw.Draw(img)
    PAD = 90

    # Titulo
    ft = _font("playfair-bold", 56)
    title_y = PAD
    th = _text_height(draw, titulo, ft, SIZE - 2 * PAD)
    _draw_text_wrap(draw, titulo, ft, SIZE // 2, title_y + th // 2 + 10,
                    SIZE - 2 * PAD, CREME, align="center")
    top = title_y + th + 55

    # Rodape (medido antes para centralizar os cards no espaco restante)
    fr = _font("inter-medium", 26)
    rodape_h = (_text_height(draw, rodape, fr, SIZE - 2 * PAD) + 40) if rodape else 0

    # Cards dos passos
    n = max(len(passos), 1)
    area_h = SIZE - top - PAD - rodape_h
    gap = 22
    card_h = min(118, (area_h - gap * (n - 1)) // n)
    y = top + max(0, (area_h - (card_h * n + gap * (n - 1))) // 2)

    fnum  = _font("playfair-bold", 46)
    fstep = _font("inter-medium", 30 if card_h >= 100 else 26)
    card_bg = tuple(int(CREME[i] * 0.10 + NAVY_D[i] * 0.90) for i in range(3))

    for i, passo in enumerate(passos, 1):
        x0, x1 = PAD, SIZE - PAD
        draw.rounded_rectangle([x0, y, x1, y + card_h], radius=16, fill=card_bg)
        draw.rounded_rectangle([x0, y, x0 + 8, y + card_h], radius=4, fill=ACCENT)

        # Numero dourado
        num = str(i)
        bb = draw.textbbox((0, 0), num, font=fnum)
        nx = x0 + 42
        draw.text((nx, y + card_h // 2 - (bb[3] - bb[1]) // 2 - bb[1]), num, font=fnum, fill=ACCENT)

        # Texto do passo (trunca se nao couber em 2 linhas)
        tx = nx + 62
        max_w = x1 - tx - 34
        texto = passo if len(passo) <= 70 else passo[:67] + "..."
        sh = _text_height(draw, texto, fstep, max_w)
        _draw_text_wrap(draw, texto, fstep, tx, y + card_h // 2, max_w, CREME, align="left")

        y += card_h + gap

    if rodape:
        ry = SIZE - PAD - rodape_h + 20
        rh = _text_height(draw, rodape, fr, SIZE - 2 * PAD)
        _draw_text_wrap(draw, rodape, fr, SIZE // 2, ry + rh // 2, SIZE - 2 * PAD, ACCENT, align="center")

    _brand_mark(draw, CREME)
    return img


# ─── dispatcher ──────────────────────────────────────────────────────────────

_TEMPLATES = {
    "numero-grande": _tmpl_numero_grande,
    "tipografia":    _tmpl_tipografia,
    "comparacao":    _tmpl_comparacao,
    "whatsapp-mock": _tmpl_whatsapp_mock,
    "passo-a-passo": _tmpl_passo_a_passo,
}

# Campos minimos que cada template precisa para renderizar algo util.
# Se faltam, o brief e invalido (o LLM inventou campos) — melhor sem imagem que imagem vazia.
_CAMPOS_OBRIGATORIOS = {
    "numero-grande": ["numero"],
    "tipografia":    ["linha1"],
    "comparacao":    ["esquerdo_itens", "direito_itens"],
    "whatsapp-mock": ["conversas"],
    "passo-a-passo": ["passos"],
}


def brief_valido(brief: dict) -> bool:
    """True se o brief tem template conhecido e os campos minimos preenchidos."""
    if not isinstance(brief, dict):
        return False
    tmpl = brief.get("template", "")
    obrig = _CAMPOS_OBRIGATORIOS.get(tmpl)
    if obrig is None:
        return False
    return all(brief.get(c) for c in obrig)


def generate_image(brief: dict | str, post_id: str) -> str | None:
    """
    Gera a imagem para o post e salva em data/images/{post_id}.png.
    brief pode ser dict ou JSON string.
    Retorna o caminho absoluto do arquivo gerado, ou None em caso de erro.
    """
    if isinstance(brief, str):
        try:
            brief = json.loads(brief)
        except json.JSONDecodeError as e:
            print(f"[Agente Imagem] Brief JSON invalido: {e}")
            return None

    if not brief:
        return None

    template = brief.get("template", "")
    fn = _TEMPLATES.get(template)
    if not fn:
        print(f"[Agente Imagem] Template desconhecido: '{template}'")
        return None

    if not brief_valido(brief):
        print(f"[Agente Imagem] Brief invalido para '{template}' "
              f"(faltam campos {_CAMPOS_OBRIGATORIOS.get(template)}) — post sai sem imagem.")
        return None

    print(f"[Agente Imagem] Gerando imagem '{template}' para post {post_id[:8]}...")
    try:
        img = fn(brief)
        out_path = IMG_DIR / f"{post_id}.png"
        img.save(str(out_path), "PNG", optimize=True)
        print(f"[Agente Imagem] Salvo: {out_path}")
        return str(out_path)
    except Exception as e:
        print(f"[Agente Imagem] Erro ao gerar imagem: {e}")
        import traceback; traceback.print_exc()
        return None


def run(posts: list[dict] = None, cycle_id: str = None) -> list[dict]:
    """
    Processa todos os posts do ciclo que possuem image_brief e ainda nao tem imagem.
    Retorna lista de {'post_id': ..., 'image_path': ...}.
    """
    import storage as at

    if posts is None:
        from config import STATUS_APROVADO, STATUS_GERADO, STATUS_AGENDADO, STATUS_REPROVADO
        posts = at.get_posts_by_status(STATUS_APROVADO, cycle_id=cycle_id)
        posts += at.get_posts_by_status(STATUS_GERADO,  cycle_id=cycle_id)
        posts += at.get_posts_by_status(STATUS_AGENDADO, cycle_id=cycle_id)
        posts += at.get_posts_by_status(STATUS_REPROVADO, cycle_id=cycle_id)

    resultados = []
    for post in posts:
        pid   = post["id"]
        brief = post["fields"].get("Image Brief") or post["fields"].get("image_brief", "")

        if not brief:
            continue

        out_path = IMG_DIR / f"{pid}.png"
        if out_path.exists():
            print(f"[Agente Imagem] Imagem ja existe para {pid[:8]}, pulando.")
            continue

        path = generate_image(brief, pid)
        if path:
            at.update_post(pid, {"image_path": path})
            resultados.append({"post_id": pid, "image_path": path})

    print(f"[Agente Imagem] {len(resultados)} imagem(ns) gerada(s).")
    return resultados


# ─── CLI de teste ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        {
            "template": "numero-grande",
            "numero": "74%",
            "subtitulo": "das PMEs nao tem processo documentado.",
            "subtitulo2": "O dono vira o manual.",
        },
        {
            "template": "numero-grande",
            "numero": "40",
            "subtitulo": "microdecisoes por dia no WhatsApp.",
            "subtitulo2": "Se voce precisa validar tudo, virou o gargalo.",
        },
        {
            "template": "tipografia",
            "linha1": "Voce nao precisa",
            "linha2": "trabalhar mais.",
            "linha3": "Precisa trabalhar certo.",
            "fundo": "navy",
        },
        {
            "template": "comparacao",
            "titulo": "Por fora parecem iguais. Por dentro, sao opostas.",
            "esquerdo_label": "Ocupada",
            "esquerdo_itens": ["Apaga incendio", "Agenda lotada", "Dono no WhatsApp 14h", "Time correndo"],
            "direito_label":  "Cresce",
            "direito_itens":  ["Constroi alavanca", "Agenda intencional", "Dono fora do op.", "Time autonomo"],
        },
        {
            "template": "whatsapp-mock",
            "titulo": "Quantas conversas voce tem com +24h sem resposta?",
            "conversas": [
                {"nome": "Carlos Ribeiro", "mensagem": "Ainda tem o produto X disponivel?",  "tempo": "ha 26h"},
                {"nome": "Mariana Silva",  "mensagem": "Pode me passar o orcamento?",         "tempo": "ha 31h"},
                {"nome": "Joao Ferreira",  "mensagem": "Quando posso retirar?",               "tempo": "ha 2d"},
                {"nome": "Ana Paula",      "mensagem": "Voces trabalham com prazo?",           "tempo": "ha 3d"},
            ],
        },
    ]

    for i, brief in enumerate(tests):
        path = generate_image(brief, f"test-{i:02d}-{brief['template']}")
        if path:
            print(f"OK: {path}")
