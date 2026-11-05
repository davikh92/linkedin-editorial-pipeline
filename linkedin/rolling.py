"""
rolling.py — pipeline ROLLING v2: gera 1 post por vez, ~24h antes de publicar.

Substitui o ciclo quinzenal em lote (pipeline.py, mantido como legado).
Motivo: conteudo de ferramenta/novidade morre em dias — gerar 8 posts no dia 1
e publicar ao longo de 15 dias entrega noticia velha.

Fluxo de uma execucao (roda dom/ter/qui de manha, via next-post.yml):
  1. Determina a proxima data de publicacao (seg/qua/sex) e o tipo do post
  2. Radar: pesquisa fresca (so tipo Pratico)
  3. Redacao: 1 post (Gemini, prompt v2)
  4. Critico: nota 0-10 com os 6 criterios; < 7 = reescreve na mesma chamada (Claude)
  5. Agenda o post para a data alvo (publish.yml publica as 11h15 BRT)

Mix semanal: seg = Pratico | qua = Pratico | sex = alterna Bastidor / Posicionamento
(semana ISO impar = Bastidor, par = Posicionamento) — ~60/25/15 na media.
"""
import re
import time
from datetime import datetime, date, timedelta, timezone

import storage as at
from llm_local import call_claude
from agents import agente_radar
from agents.agente_redacao import _parse_output
from agents.agente_critico import _extrair_nota, _extrair_revisao
from agents.agente_imagem import brief_valido
from config import STATUS_AGENDADO, FORMATO_TEXTO, FORMATO_IMAGEM, NOTA_MINIMA_APROVACAO
from prompts_v2 import (
    PROMPT_REDACAO_V2, PROMPT_CRITICO_V2, TIPO_PRATICO, CATEGORIAS_PRATICO,
)

# Dias de publicacao do PRATICO: seg e qua (a storyline ocupa ter e qui — ver storyline.py).
# Os praticos sao a metade automatica (radar + redacao fresca); a storyline e curada.
DIAS_PUBLICACAO = (0, 2)


def run_next_post(target_date: str = None, tipo: str = None, dry_run: bool = False) -> dict:
    """
    Gera e agenda o proximo post.
    target_date: 'YYYY-MM-DD' (default: proxima seg/qua/sex a partir de amanha)
    tipo: forca o tipo (default: derivado do dia da semana)
    dry_run: gera e imprime, mas NAO salva nem agenda
    """
    alvo = date.fromisoformat(target_date) if target_date else _proxima_data_publicacao()
    tipo = tipo or _tipo_do_dia(alvo)

    print(f"\n{'='*60}")
    print(f"  ROLLING v2 — proximo post")
    print(f"  Publica em: {alvo.isoformat()} ({_nome_dia(alvo)})  |  Tipo: {tipo}")
    print(f"{'='*60}\n")

    # Guard: ja existe post agendado para essa data?
    if not dry_run and _ja_agendado(alvo.isoformat()):
        print(f"[Rolling] Ja existe post agendado para {alvo.isoformat()} — nada a fazer.")
        return {}

    recentes = _posts_recentes(limite=12)

    # 1. Radar (so Pratico usa pesquisa fresca)
    pauta = None
    if tipo == TIPO_PRATICO:
        usadas = _ferramentas_recentes(dias=45)
        pauta = agente_radar.run(pautas_recentes=[t for t, _ in recentes],
                                 categoria=_categoria_do_dia(alvo))
        # Verificacao DURA: instrucao de prompt sozinha ja deixou passar a mesma
        # ferramenta com outro angulo (ChatGPT saiu 2x em 3 semanas). Se repetir,
        # pede outra pauta uma vez, explicitando o que esta proibido.
        repetida = _ferramenta_repetida(pauta, usadas)
        if repetida:
            print(f"[Rolling] Pauta repete '{repetida}' (usada nos ultimos 45 dias) "
                  f"— pedindo outra.")
            veto = sorted(usadas)
            pauta = agente_radar.run(
                pautas_recentes=[t for t, _ in recentes]
                + [f"PROIBIDO repetir estas ferramentas: {', '.join(veto)}"],
                categoria=_categoria_do_dia(alvo),
            )
            if _ferramenta_repetida(pauta, usadas):
                print("[Rolling] AVISO: segunda pauta tambem repete — seguindo assim mesmo.")
        print()

    # 2. Redacao
    copy, brief, meta = _redigir(tipo, pauta, recentes)
    copy = _limpar_copy(copy)
    titulo = _primeira_linha(copy)[:80] or (pauta or {}).get("pauta", tipo)[:80]
    print(f"[Rolling] Post redigido: {titulo[:60]}")

    # 3. Critico
    nota, feedback, copy_rev, brief_rev = _criticar(copy, tipo, brief)
    if copy_rev:
        copy = _limpar_copy(copy_rev)
        titulo = _primeira_linha(copy)[:80] or titulo
        if brief_rev is not None and brief_valido(brief_rev):
            brief = brief_rev
        print(f"[Rolling] Nota {nota:.0f}/10 — reescrito pelo critico.")
    else:
        print(f"[Rolling] Nota {nota:.0f}/10 — aprovado direto.")

    # descarta brief invalido (LLM inventou campos) — post sai sem imagem, nunca quebrada
    if brief and not brief_valido(brief):
        brief = None

    if dry_run:
        print("\n" + "-" * 60)
        print(copy)
        print("-" * 60)
        if brief:
            import json
            print(f"\n[BRIEF IMAGEM] {json.dumps(brief, ensure_ascii=False)}")
        print(f"\n[DRY RUN] Nada foi salvo. Publicaria em {alvo.isoformat()}.")
        return {"copy": copy, "brief": brief, "nota": nota, "data": alvo.isoformat()}

    # 4. Salva + agenda
    import json
    formato = meta.get("formato") or (FORMATO_IMAGEM if brief else FORMATO_TEXTO)
    record = at.create_post({
        "Titulo interno": titulo,
        "Copy":           copy,
        "Linha":          tipo,
        "Formato":        formato,
        "Tem CTA":        True,
        "Status":         STATUS_AGENDADO,
        "Data agendada":  alvo.isoformat(),
        "Origem":         "Rolling v2",
        "Feedback Critico": f"[NOTA {nota:.0f}/10]\n{feedback}",
        "Image Brief":    json.dumps(brief, ensure_ascii=False) if brief else "",
    })

    gerar_e_salvar_imagem(record["id"], brief)

    print(f"\n[Rolling] Post agendado para {alvo.isoformat()} (id {record['id'][:8]}...).")
    return {"post_id": record["id"], "data": alvo.isoformat(), "nota": nota, "tipo": tipo}


# ─── imagem ───────────────────────────────────────────────────────────────────

def gerar_e_salvar_imagem(post_id: str, brief: dict | None) -> str | None:
    """
    Gera a imagem AGORA, junto com o post, e guarda o caminho.

    Por que aqui e nao na hora de publicar: a imagem v2 depende de Node +
    Puppeteer + Chromium, que existem na maquina do Davi mas NAO no runner do
    GitHub Actions. Gerando na criacao, o PNG e commitado junto e o publish so
    faz upload do arquivo pronto. Se ficasse para a publicacao, cairia sempre
    no fallback Pillow (v1).

    Nunca levanta: post sem imagem ainda publica (so com texto).
    """
    if not brief:
        return None
    try:
        from agents.agente_imagem_v2 import gerar_imagem
        path = gerar_imagem(brief, post_id)
    except Exception as e:
        print(f"[Imagem] Falhou para {post_id[:8]}: {e}")
        return None

    if path:
        at.update_post(post_id, {"image_path": path})
    else:
        print(f"[Imagem] Sem imagem para {post_id[:8]} — post publica so com texto.")
    return path


# ─── agenda e mix ─────────────────────────────────────────────────────────────

def _proxima_data_publicacao(a_partir_de: date = None) -> date:
    """Proxima seg/qua/sex a partir de amanha (o post e gerado na vespera)."""
    d = (a_partir_de or datetime.now(timezone.utc).date()) + timedelta(days=1)
    while d.weekday() not in DIAS_PUBLICACAO:
        d += timedelta(days=1)
    return d


def _tipo_do_dia(d: date) -> str:
    """seg e qua = Pratico. A storyline (ter/qui) e gerada por storyline.py, nao aqui."""
    return TIPO_PRATICO


# Ferramentas que o radar tende a repetir. Nomes curtos e distintivos: comparar
# titulo/hook nao bastou — o mesmo ChatGPT voltou com outro angulo em 3 semanas.
_FERRAMENTAS = [
    "chatgpt", "gemini", "claude", "copilot", "canva", "notion", "whatsapp business",
    "meta ai", "instagram", "google planilhas", "google meu negocio", "excel",
    "midjourney", "capcut", "zapier", "make",
]


def _ferramentas_recentes(dias: int = 45) -> set[str]:
    """Ferramentas citadas em posts publicados/agendados na janela recente."""
    limite = (datetime.now(timezone.utc).date() - timedelta(days=dias)).isoformat()
    achadas: set[str] = set()
    for status in ("Publicado", "Agendado", "Aprovado"):
        for p in at.get_posts_by_status(status):
            f = p["fields"]
            if (f.get("Data agendada") or "") < limite:
                continue
            texto = f"{f.get('Copy','')} {f.get('Título interno','')}".lower()
            achadas.update(t for t in _FERRAMENTAS if t in texto)
    return achadas


def _ferramenta_repetida(pauta: dict | None, usadas: set[str]) -> str | None:
    """Nome da ferramenta que a pauta repete, ou None."""
    if not pauta or not usadas:
        return None
    texto = " ".join(str(pauta.get(k, "")) for k in
                     ("pauta", "novidade", "utilidade", "passo_a_passo")).lower()
    for t in usadas:
        if t in texto:
            return t
    return None


def _categoria_do_dia(d: date) -> dict:
    """
    Rotaciona a categoria do pratico de forma deterministica.

    Sem isso o radar escolhe sempre "ferramenta de IA nova" e o perfil vira
    noticiario de ChatGPT — perdendo a metade "sistemas/organizacao" da lente,
    que e justamente o servico do Davi. A rotacao usa semana ISO + slot da
    semana, entao dois posts da mesma semana caem em categorias diferentes.
    """
    semana = d.isocalendar()[1]
    slot = 0 if d.weekday() == 0 else 1        # seg = 0, qua = 1
    return CATEGORIAS_PRATICO[(semana * 2 + slot) % len(CATEGORIAS_PRATICO)]


def _nome_dia(d: date) -> str:
    return ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"][d.weekday()]


def _ja_agendado(data_iso: str) -> bool:
    for status in ("Agendado", "Aprovado"):
        for p in at.get_posts_by_status(status):
            if p["fields"].get("Data agendada") == data_iso:
                return True
    return False


def _posts_recentes(limite: int = 12) -> list[tuple[str, str]]:
    """Ultimos posts (titulo, hook) para anti-repeticao — publicados e agendados."""
    todos = []
    for status in ("Publicado", "Agendado", "Aprovado"):
        todos.extend(at.get_posts_by_status(status))
    todos.sort(key=lambda p: p["fields"].get("Data agendada") or "", reverse=True)
    out = []
    for p in todos[:limite]:
        f = p["fields"]
        titulo = f.get("Título interno") or f.get("Titulo interno") or ""
        hook = _primeira_linha(f.get("Copy", ""))
        out.append((titulo, hook))
    return out


# ─── redacao ──────────────────────────────────────────────────────────────────

def _redigir(tipo: str, pauta: dict | None, recentes: list[tuple[str, str]]):
    evitar = ""
    if recentes:
        lista = "\n".join(f"  - {t} | hook: {h}" for t, h in recentes if t or h)
        evitar = f"\n\nJA POSTADO RECENTEMENTE (nao repetir tema nem hook):\n{lista}"

    if pauta and pauta.get("pauta"):
        pauta_str = (
            f"PAUTA (pesquisa fresca de hoje):\n"
            f"Pauta: {pauta['pauta']}\n"
            f"Novidade: {pauta['novidade']}\n"
            f"Utilidade: {pauta['utilidade']}\n"
            f"Fatos reais (com fonte): {pauta['fatos']}\n"
            f"Passo a passo sugerido: {pauta['passo_a_passo']}\n"
            f"Angulo do Davi: {pauta['angulo_davi']}\n"
        )
    elif pauta:
        pauta_str = f"PAUTA (pesquisa fresca, texto bruto):\n{pauta.get('raw', '')}\n"
    else:
        pauta_str = (
            "SEM PAUTA EXTERNA — use material interno: os casos reais do Davi "
            "(Shake Dog, BabaSol, Flora Amazon) ou a construcao deste proprio sistema "
            "de conteudo com IA. Escolha o que render o post mais concreto.\n"
        )

    user_msg = (
        f"Tipo do post: {tipo}\n\n"
        f"{pauta_str}"
        f"{evitar}\n\n"
        f"Escreva o post."
    )

    raw = call_claude(PROMPT_REDACAO_V2, user_msg)
    return _parse_output(raw, "")


def _limpar_copy(copy: str) -> str:
    """
    Remove o que quebraria o post no LinkedIn (que nao renderiza markdown):
    blocos de codigo, **negrito**, _italico_, separadores ---, JSON, tags de secao
    perdidas e notas de auto-explicacao do modelo (meta-comentario sobre o proprio post).
    """
    copy = re.sub(r"```.*?```", "", copy, flags=re.DOTALL)          # code fences pareados
    copy = copy.replace("```", "")                                   # cercas soltas
    copy = re.sub(r"\{.*?\}", "", copy, flags=re.DOTALL)             # qualquer JSON vazado
    copy = re.sub(r"\[(?:IMAGEM|IMG|BRIEF|COPY|LINHA|FORMATO|CTA)[^\]]*\].*",
                  "", copy, flags=re.DOTALL | re.IGNORECASE)          # tags de secao e o que vem depois
    # Meta-comentario do modelo explicando as proprias escolhas. Nunca deveria
    # ir ao ar, mas o LLM anexa como paragrafo final nao marcado — ja apareceu
    # como "Nota de construcao:" e como "O que mudou e por que:". Corta a partir
    # de qualquer um desses cabecalhos ate o fim do texto.
    # Cada alternativa e: palavra-chave no inicio da linha + qualquer cauda sem
    # dois-pontos + dois-pontos. A cauda livre importa — a versao anterior exigia
    # a forma "Nota de <palavra>:" e deixou passar "Notas de construcao para
    # revisao:", que foi parar no fim de um capitulo pronto para publicar.
    _META = (
        r"\n\s*(?:"
        r"notas?\b[^\n:]{0,60}"
        r"|observa[çc][õo]es?\b[^\n:]{0,60}"
        r"|justificativas?\b[^\n:]{0,60}"
        r"|coment[áa]rios?\s+(?:do|da|sobre)\b[^\n:]{0,60}"
        r"|o\s+que\s+(?:mudou|mudei|melhorei|alterei)[^\n:]{0,60}"
        r"|por\s+que\s+(?:mudei|mudou|alterei)[^\n:]{0,60}"
        r"|mudan[çc]as?\s+(?:feitas|aplicadas)[^\n:]{0,60}"
        r"):.*$"
    )
    copy = re.sub(_META, "", copy, flags=re.DOTALL | re.IGNORECASE)
    copy = copy.replace("**", "").replace("__", "")
    copy = re.sub(r"^\s*(?:---+|\*\*\*+)\s*$", "", copy, flags=re.MULTILINE)
    copy = re.sub(r"\n{3,}", "\n\n", copy)                           # colapsa linhas vazias
    return copy.strip()


def _primeira_linha(copy: str) -> str:
    if not copy:
        return ""
    for linha in copy.split("\n"):
        l = linha.strip().lstrip("*#-[ ").strip()
        if l and not l.upper().startswith(("COPY", "SLIDE", "BRIEF", "TIPO")):
            return l[:120]
    return ""


# ─── critico ──────────────────────────────────────────────────────────────────

def _criticar(copy: str, tipo: str, brief: dict | None):
    """Uma chamada Claude (CLI): nota + reescrita se < 7. Retorna (nota, feedback, copy_rev|None, brief_rev|None)."""
    tem_imagem = "sim" if brief else "nao"
    user_msg = (
        f"Avalie o post abaixo (tipo: {tipo}, tem imagem: {tem_imagem}). "
        f"Se a nota for < {NOTA_MINIMA_APROVACAO:.0f}, reescreva na secao POST REVISADO.\n\n"
        f"---\n{copy}\n---"
    )
    output = call_claude(PROMPT_CRITICO_V2, user_msg).strip()
    nota = _extrair_nota(output)
    copy_rev, brief_rev = _extrair_revisao(output, "")
    feedback = re.split(r"POST REVISADO:", output, flags=re.IGNORECASE)[0].strip()
    return nota, feedback, copy_rev, brief_rev
