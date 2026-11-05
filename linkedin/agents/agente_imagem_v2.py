"""
agente_imagem_v2.py — imagens do LinkedIn em 3 camadas (substitui o Pillow do v1).

  1. FUNDO   — foto gerada pelo Gemini image (sem nenhum texto na cena)
  2. OVERLAY — texto real em HTML/CSS (templates/post-overlay.html)
  3. RENDER  — screenshot 1200x1200 via Puppeteer (render_image.js)

Por que assim: modelo de imagem nao escreve texto legivel. Separando as camadas,
o fundo ganha realismo fotografico e a tipografia fica nitida e sob nosso controle.

Consome o MESMO `image_brief` que o redator ja gera hoje — nenhuma mudanca de prompt
e necessaria. Se o brief trouxer o campo opcional `cena`, ele vira o prompt do fundo;
senao, cai num banco de cenas coerentes com a marca.

Credencial: GOOGLE_API_KEY (a GEMINI_API_KEY do free tier nao tem cota de imagem).
"""
import base64
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

import requests

_BASE = Path(__file__).parent.parent
IMG_DIR = _BASE / "data" / "images"
RENDER_JS = _BASE / "render_image.js"

MODELO_IMAGEM = "gemini-3.1-flash-image"
_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO_IMAGEM}:generateContent"

# Frase anti-texto: sem ela o modelo tenta "ajudar" e escreve garranchos ilegiveis.
# Nunca induzir texto no prompt (nada de "list", "notes", "screen showing", "sign").
_ANTI_TEXTO = (
    "Absolutely no text, no letters, no words, no writing, no numbers, "
    "no signage, no labels anywhere in the image."
)
_ESTILO = (
    "cinematic editorial photography, deep navy blue and warm golden tones, "
    "soft directional light, shallow depth of field, subtle film grain, "
    "premium and restrained mood, no people's faces visible"
)

# Cenas coerentes com o publico (dono de negocio pequeno) e com a marca.
_BANCO_CENAS = [
    "an early morning small shop counter, wooden surface, a laptop half closed, a cup of coffee steaming",
    "a small workshop bench with tools neatly arranged, warm lamp light, end of the workday",
    "a quiet corner of a small restaurant before opening, chairs on tables, light through the window",
    "a small retail store stockroom, boxes stacked neatly on shelves",
    "a home office desk of a business owner at night, a single warm lamp, a closed notebook",
    "a delivery counter of a small business, packages ready, morning light",
    "an empty small office meeting corner, two chairs, plants, soft window light",
    "a craftsman's hands resting on a wooden workbench, warm side light",
]


def _api_key() -> str:
    key = os.environ.get("GOOGLE_API_KEY") or ""
    if not key:
        raise RuntimeError(
            "GOOGLE_API_KEY nao configurada — necessaria para gerar o fundo das imagens."
        )
    return key


# 503 (modelo sobrecarregado) e 429 (cota momentanea) sao transitorios e
# acontecem na pratica — sem retry, um deles deixa o post sem imagem de vez.
_RETRIABLE = {429, 500, 502, 503, 504}
_ESPERAS = [10, 30, 60]


def gerar_fundo(cena: str, timeout: int = 180) -> bytes:
    """Gera a foto de fundo (PNG bytes). Retenta erros transitorios."""
    prompt = f"{cena}. {_ESTILO}. {_ANTI_TEXTO}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": "1:1"},
        },
    }
    headers = {"Content-Type": "application/json", "x-goog-api-key": _api_key()}

    ultimo = ""
    for tentativa, espera in enumerate([0] + _ESPERAS, start=1):
        if espera:
            print(f"  [Imagem v2] Erro temporario — aguardando {espera}s "
                  f"(tentativa {tentativa})...")
            time.sleep(espera)
        try:
            resp = requests.post(_URL, headers=headers, json=payload, timeout=timeout)
        except requests.RequestException as e:
            ultimo = type(e).__name__
            continue

        if resp.status_code in _RETRIABLE:
            ultimo = f"HTTP {resp.status_code}"
            continue
        if resp.status_code != 200:
            raise RuntimeError(f"Gemini image HTTP {resp.status_code}: {resp.text[:200]}")

        for parte in resp.json()["candidates"][0]["content"]["parts"]:
            if "inlineData" in parte:
                return base64.b64decode(parte["inlineData"]["data"])
        ultimo = "resposta sem imagem"

    raise RuntimeError(f"Gemini image falhou apos {len(_ESPERAS) + 1} tentativas: {ultimo}")


def _escolher_cena(brief: dict, semente: str) -> str:
    """Usa a cena do brief se houver; senao escolhe do banco de forma estavel."""
    cena = (brief.get("cena") or "").strip()
    if cena:
        return cena
    idx = sum(ord(c) for c in semente) % len(_BANCO_CENAS)
    return _BANCO_CENAS[idx]


def _brief_para_overlay(brief: dict) -> dict:
    """Traduz o brief do redator (formato v1) para os campos do template HTML."""
    t = brief.get("template", "")

    if t == "numero-grande":
        return {
            "template": t,
            "numero": brief.get("numero", ""),
            "headline": brief.get("subtitulo", ""),
            "subtext": brief.get("subtitulo2", ""),
        }

    if t == "tipografia":
        linhas = [brief.get(k, "") for k in ("linha1", "linha2", "linha3")]
        linhas = [l for l in linhas if l]
        return {
            "template": t,
            "headline": " ".join(linhas[:2]),
            "subtext": linhas[2] if len(linhas) > 2 else "",
        }

    if t == "passo-a-passo":
        return {
            "template": t,
            "kicker": "passo a passo",
            "headline": brief.get("titulo", ""),
            "passos": brief.get("passos", []),
            "subtext": brief.get("rodape", ""),
        }

    if t == "comparacao":
        esq = brief.get("esquerdo_itens", []) or []
        dir_ = brief.get("direito_itens", []) or []
        return {
            "template": t,
            "headline": brief.get("titulo", ""),
            "passos": [f"{brief.get('esquerdo_label','Antes')}: {i}" for i in esq[:2]]
                      + [f"{brief.get('direito_label','Depois')}: {i}" for i in dir_[:2]],
        }

    # fallback: usa o que houver de texto no brief
    return {
        "template": t or "generico",
        "headline": brief.get("titulo") or brief.get("linha1") or "",
        "subtext": brief.get("subtitulo") or "",
    }


def gerar_imagem(brief: dict | str, post_id: str) -> str | None:
    """
    Gera a imagem final do post. Retorna o caminho do PNG, ou None em falha.
    Nunca levanta — falha de imagem nao pode derrubar a publicacao do post.
    """
    if isinstance(brief, str):
        try:
            brief = json.loads(brief)
        except json.JSONDecodeError:
            print(f"[Imagem v2] Brief invalido para {post_id[:8]}")
            return None
    if not brief:
        return None

    overlay = _brief_para_overlay(brief)
    if not (overlay.get("headline") or overlay.get("numero") or overlay.get("passos")):
        print(f"[Imagem v2] Brief sem conteudo textual para {post_id[:8]}")
        return None

    cena = _escolher_cena(brief, semente=post_id + brief.get("template", ""))
    print(f"[Imagem v2] {post_id[:8]} — gerando fundo...")

    try:
        fundo = gerar_fundo(cena)
    except Exception as e:
        print(f"[Imagem v2] Falha ao gerar fundo: {e}")
        return None

    overlay["bgDataUri"] = "data:image/png;base64," + base64.b64encode(fundo).decode()

    IMG_DIR.mkdir(parents=True, exist_ok=True)
    saida = IMG_DIR / f"{post_id}.png"

    payload_path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8",
                                         delete=False) as f:
            json.dump(overlay, f, ensure_ascii=False)
            payload_path = f.name

        proc = subprocess.run(
            ["node", str(RENDER_JS), payload_path, str(saida)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=180,
        )
        if proc.returncode != 0:
            print(f"[Imagem v2] Puppeteer falhou: {(proc.stderr or '')[:200]}")
            return None
    except FileNotFoundError:
        print("[Imagem v2] 'node' nao encontrado no PATH.")
        return None
    except subprocess.TimeoutExpired:
        print("[Imagem v2] Timeout no Puppeteer.")
        return None
    finally:
        if payload_path:
            Path(payload_path).unlink(missing_ok=True)

    print(f"[Imagem v2] Salvo: {saida}")
    return str(saida)


if __name__ == "__main__":
    # Teste rapido: python agents/agente_imagem_v2.py
    from dotenv import load_dotenv
    load_dotenv(_BASE.parent / ".env", encoding="utf-8", override=True)

    exemplos = [
        ({"template": "numero-grande", "numero": "R$0",
          "subtitulo": "o que pago por mes",
          "subtitulo2": "pela maquina que publica por mim"}, "demo-numero"),
        ({"template": "tipografia", "linha1": "Este post",
          "linha2": "nao fui eu que escrevi.",
          "linha3": "Foi uma IA que montei."}, "demo-tipografia"),
        ({"template": "passo-a-passo", "titulo": "Como a maquina funciona",
          "passos": ["Pesquisa o que esta novo", "Escreve o post",
                     "Critica e manda reescrever", "Publica na hora certa"],
          "rodape": "4 robos. Custo zero."}, "demo-passos"),
    ]
    for brief, pid in exemplos:
        gerar_imagem(brief, pid)
