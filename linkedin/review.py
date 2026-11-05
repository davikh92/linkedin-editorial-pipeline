"""
review.py — gera data/review.html com todos os posts do ciclo ativo.

Mostra copy limpa + imagem lado a lado para revisao antes de publicar.

Uso:
  python review.py
  python review.py <cycle_id>
"""
import sys
import json
import base64
import re
import webbrowser
from pathlib import Path
from datetime import datetime, timezone

DATA_DIR = Path(__file__).parent / "data"


def _img_b64(path: str) -> str | None:
    p = Path(path) if path else None
    if not p or not p.exists():
        return None
    with open(p, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _clean_copy(raw: str, formato: str = "") -> str:
    """Extrai apenas o texto publicavel do post, removendo notas internas e slides."""
    if not raw:
        return ""

    # Para carrossel: pega so o [COPY DO POST] (intro text que vai ao LinkedIn)
    # Os slides sao exibidos separadamente por _render_slides()
    if "[COPY DO POST]" in raw:
        match = re.search(
            r"\[COPY DO POST\](.*?)(?:SLIDE\s+\d|SLIDE\s+1:|^\s*SLIDE|\[SLIDES\]|\[BRIEF|\[TIPO|---|\Z)",
            raw, re.DOTALL | re.IGNORECASE | re.MULTILINE
        )
        if match:
            raw = match.group(1).strip()
        else:
            # fallback: pega ate primeiro SLIDE X:
            partes = re.split(r"\n\s*SLIDE\s+\d", raw, flags=re.IGNORECASE)
            raw = partes[0].replace("[COPY DO POST]", "").strip()

    # Corta tudo a partir de SLIDE 1: (caso nao tenha marcador [COPY DO POST])
    raw = re.split(r"\n\s*SLIDE\s+1\s*:", raw, maxsplit=1, flags=re.IGNORECASE)[0]

    # Remove linhas de metadata/instrucao interna
    linhas = raw.split("\n")
    limpas = []
    skip_block = False
    for linha in linhas:
        linha_strip = linha.strip()
        if any(linha_strip.startswith(x) for x in [
            "**DUAS PERGUNTAS", "**Pergunta 1", "**Pergunta 2",
            "**PERGUNTA 1", "**PERGUNTA 2", "Antes de escrever",
            "# CARROSSEL", "## Duas perguntas", "## OUTPUT",
            "[TIPO:", "[FUNCAO:", "[PONTE:", "[FUNCAO", "---",
            "```", "##[", "**[TIPO", "* [TIPO", "  [TIPO",
        ]):
            skip_block = True
        if skip_block:
            if linha_strip == "":
                skip_block = False
            continue
        limpas.append(linha)

    texto = "\n".join(limpas).strip()
    texto = re.sub(r"```[\s\S]*?```", "", texto)
    texto = re.sub(r"\[.*?\]", "", texto)
    texto = re.sub(r"\*\*(DUAS|Pergunta|PERGUNTA|POSTURA|FORMATO).*", "", texto)
    return texto.strip()


def _render_slides(raw: str) -> str:
    """Para posts carrossel: extrai slides e renderiza como cards visuais."""
    slides = re.findall(
        r"SLIDE\s+(\d+)[:\s-]*\n(.*?)(?=\nSLIDE\s+\d|\Z)",
        raw, re.DOTALL | re.IGNORECASE
    )
    if not slides:
        return ""

    cards = []
    for num, conteudo in slides:
        # Extrai campos Texto/Fundo/Visual
        texto_m = re.search(r"Texto:\s*(.+?)(?=Fundo:|Visual:|\Z)", conteudo, re.DOTALL | re.IGNORECASE)
        fundo_m = re.search(r"Fundo:\s*(\w+)", conteudo, re.IGNORECASE)
        fundo = fundo_m.group(1).lower() if fundo_m else "creme"
        texto = texto_m.group(1).strip() if texto_m else conteudo.strip()

        bg = "#1a2754" if "navy" in fundo else "#f5f1ea"
        cor = "#f5f1ea" if "navy" in fundo else "#1a2754"
        cards.append(
            f'<div style="display:inline-block;min-width:200px;max-width:260px;'
            f'vertical-align:top;background:{bg};color:{cor};padding:16px 18px;'
            f'border-radius:10px;font-size:12px;line-height:1.5;margin:4px">'
            f'<div style="font-size:10px;opacity:.6;margin-bottom:6px">SLIDE {num}</div>'
            f'{texto.replace(chr(10),"<br>")}</div>'
        )
    return (
        '<div style="margin-top:14px;padding:12px;background:#f8fafc;'
        'border-radius:8px;border:1px dashed #cbd5e1">'
        '<div style="font-size:11px;color:#64748b;margin-bottom:8px">▸ SLIDES DO CARROSSEL</div>'
        + "".join(cards) + "</div>"
    )


def _md_to_html(text: str) -> str:
    """Converte markdown basico para HTML."""
    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # Italic
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    # Quebras de linha
    text = text.replace("\n", "<br>")
    return text


def _status_badge(status: str) -> str:
    cores = {
        "Aprovado":               ("#22c55e", "#fff"),
        "Agendado":               ("#8b5cf6", "#fff"),
        "Publicado":              ("#0ea5e9", "#fff"),
        "Gerado":                 ("#f59e0b", "#000"),
        "Reprovado pelo Critico": ("#ef4444", "#fff"),
        "Reprovado":              ("#ef4444", "#fff"),
    }
    bg, fg = cores.get(status, ("#6b7280", "#fff"))
    return (f'<span style="background:{bg};color:{fg};padding:3px 10px;'
            f'border-radius:20px;font-size:12px;font-weight:600">{status}</span>')


def generate(cycle_id: str = None) -> str:
    with open(DATA_DIR / "posts.json", encoding="utf-8") as f:
        all_posts = json.load(f)

    if not cycle_id:
        with open(DATA_DIR / "ciclo_ativo.json", encoding="utf-8") as f:
            ciclo = json.load(f)
        cycle_id  = ciclo.get("id", "")
        cycle_name = ciclo.get("nome", cycle_id)
    else:
        cycle_name = cycle_id

    posts = [p for p in all_posts if p.get("ciclo_id") == cycle_id]
    posts.sort(key=lambda p: p.get("data_agendada") or "9999")

    now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    # ── cards ─────────────────────────────────────────────────────────
    cards = []
    for i, p in enumerate(posts, 1):
        status    = p.get("status", "?")
        titulo    = p.get("titulo", "Sem titulo").replace("**", "")
        formato   = p.get("formato", "")
        copy_raw   = p.get("copy", "")
        copy_clean = _clean_copy(copy_raw, formato)
        copy_html  = _md_to_html(copy_clean)
        slides_html = _render_slides(copy_raw) if "carrossel" in formato.lower() else ""
        data      = p.get("data_agendada", "—")
        linha     = p.get("linha", "")
        img_path  = p.get("image_path", "")
        brief_raw = p.get("image_brief", "")
        li_urn    = p.get("linkedin_post_id", "")

        # --- Imagem ---
        img_html = ""
        if img_path:
            b64 = _img_b64(img_path)
            if b64:
                img_html = f'''
                <div style="flex:0 0 300px">
                  <img src="data:image/png;base64,{b64}"
                       style="width:300px;height:300px;object-fit:cover;
                              border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,.15)">
                  <div style="text-align:center;font-size:11px;color:#94a3b8;margin-top:6px">
                    {Path(img_path).name}
                  </div>
                </div>'''

        if not img_html and brief_raw:
            try:
                brief = json.loads(brief_raw)
                tmpl  = brief.get("template", "?")
                numero = brief.get("numero", "")
                linha1 = brief.get("linha1", brief.get("subtitulo", ""))
                preview_txt = f"<b>{numero}</b><br>{linha1}" if numero else linha1
                img_html = f'''
                <div style="flex:0 0 300px;display:flex;align-items:center;justify-content:center;
                            width:300px;height:300px;background:#1a2754;border-radius:12px;
                            flex-direction:column;gap:10px;padding:20px;text-align:center">
                  <span style="font-size:13px;color:#8b9dc3;text-transform:uppercase;
                               letter-spacing:1px">template</span>
                  <span style="font-size:22px;font-weight:700;color:#f5f1ea">{tmpl}</span>
                  <span style="font-size:13px;color:#c4b8a0;margin-top:4px">{preview_txt}</span>
                  <span style="font-size:11px;color:#64748b;margin-top:8px;
                               background:rgba(255,255,255,.08);padding:4px 10px;border-radius:20px">
                    imagem nao gerada
                  </span>
                </div>'''
            except Exception:
                pass

        if not img_html:
            img_html = '''
            <div style="flex:0 0 300px;display:flex;align-items:center;justify-content:center;
                        width:300px;height:300px;background:#f8fafc;border-radius:12px;
                        border:2px dashed #e2e8f0">
              <span style="color:#94a3b8;font-size:13px">Sem imagem</span>
            </div>'''

        # --- Link LinkedIn ---
        li_link = ""
        if li_urn:
            post_num = li_urn.split(":")[-1]
            li_link = (f'<a href="https://www.linkedin.com/feed/update/{li_urn}/" '
                       f'target="_blank" style="font-size:12px;color:#0ea5e9;'
                       f'text-decoration:none">Ver no LinkedIn →</a>')

        # --- Feedback reprovado ---
        feedback = p.get("feedback_critico", "") or p.get("Feedback Critico", "")
        feedback_html = ""
        if feedback and "Reprovado" in status:
            fb_short = feedback[:400].replace("\n", "<br>")
            feedback_html = f'''
            <div style="margin-top:16px;padding:14px 16px;background:#fef2f2;
                        border-left:4px solid #ef4444;border-radius:6px;
                        font-size:13px;color:#7f1d1d">
              <b>Feedback do Critico:</b><br><br>{fb_short}...
            </div>'''

        cards.append(f'''
        <div style="background:#fff;border-radius:16px;padding:28px;margin-bottom:24px;
                    box-shadow:0 1px 4px rgba(0,0,0,.08);border:1px solid #e2e8f0">

          <!-- Cabecalho -->
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;flex-wrap:wrap">
            <span style="font-size:20px;font-weight:700;color:#1a2754">#{i}</span>
            <span style="font-size:15px;font-weight:600;color:#1e293b;flex:1">{titulo}</span>
            {_status_badge(status)}
          </div>

          <div style="font-size:12px;color:#64748b;margin-bottom:20px;
                      display:flex;gap:16px;flex-wrap:wrap;align-items:center">
            <span>📅 <b>{data}</b></span>
            <span>📄 {formato}</span>
            <span>🏷️ {linha}</span>
            {li_link}
          </div>

          <!-- Copy + Imagem -->
          <div style="display:flex;gap:28px;align-items:flex-start;flex-wrap:wrap">

            <div style="flex:1;min-width:280px;font-size:14px;line-height:1.8;
                        color:#334155;font-family:Georgia,serif;
                        max-height:360px;overflow-y:auto;padding-right:8px">
              {copy_html}
              {slides_html}
            </div>

            {img_html}

          </div>

          {feedback_html}

        </div>''')

    cards_html = "\n".join(cards)

    total      = len(posts)
    aprovados  = sum(1 for p in posts if p.get("status") in ("Aprovado","Agendado","Publicado"))
    com_img    = sum(1 for p in posts if p.get("image_path") and Path(p["image_path"]).exists())
    reprovados = sum(1 for p in posts if "Reprovado" in p.get("status",""))

    html = f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Revisao LinkedIn — {cycle_name}</title>
  <style>
    * {{ box-sizing:border-box; margin:0; padding:0 }}
    body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
            background:#f1f5f9; color:#1e293b; padding:32px 24px }}
    ::-webkit-scrollbar {{ width:6px }}
    ::-webkit-scrollbar-thumb {{ background:#cbd5e1; border-radius:3px }}
    .container {{ max-width:1060px; margin:0 auto }}
    .header {{ background:linear-gradient(135deg,#0f172a,#1a2754,#2d3f7c);
               border-radius:16px; padding:32px; color:#f5f1ea; margin-bottom:32px }}
    .stats {{ display:flex; gap:16px; margin-top:24px; flex-wrap:wrap }}
    .stat {{ background:rgba(255,255,255,.1); border-radius:10px;
             padding:14px 24px; text-align:center; min-width:100px }}
    .stat-num {{ font-size:30px; font-weight:700 }}
    .stat-lbl {{ font-size:12px; opacity:.7; margin-top:2px }}
  </style>
</head>
<body>
<div class="container">

  <div class="header">
    <div style="font-size:12px;opacity:.6;text-transform:uppercase;
                letter-spacing:1px;margin-bottom:8px">LinkedIn — Revisao do Ciclo</div>
    <h1 style="font-size:28px;font-weight:700">{cycle_name}</h1>
    <div style="font-size:13px;opacity:.5;margin-top:6px">Gerado em {now}</div>
    <div class="stats">
      <div class="stat">
        <div class="stat-num">{total}</div>
        <div class="stat-lbl">Posts</div>
      </div>
      <div class="stat">
        <div class="stat-num" style="color:#86efac">{aprovados}</div>
        <div class="stat-lbl">Aprovados</div>
      </div>
      <div class="stat">
        <div class="stat-num" style="color:#c4b5fd">{com_img}</div>
        <div class="stat-lbl">Com imagem</div>
      </div>
      <div class="stat">
        <div class="stat-num" style="color:#fca5a5">{reprovados}</div>
        <div class="stat-lbl">Reprovados</div>
      </div>
    </div>
  </div>

  {cards_html}

</div>
</body>
</html>'''

    out = DATA_DIR / "review.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[Review] Gerado: {out}")
    return str(out)


if __name__ == "__main__":
    cycle_id = sys.argv[1] if len(sys.argv) > 1 else None
    path = generate(cycle_id)
    webbrowser.open(f"file:///{path.replace(chr(92), '/')}")
    print("[Review] Abrindo no navegador...")
