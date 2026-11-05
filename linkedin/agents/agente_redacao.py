"""
Agente Redacao — gera o copy completo de cada post a partir de um tema.
Usa Gemini Flash para geracao de texto (mais barato / gratuito).
Tambem processa ideias brutas do Davi (posts humanos).
"""
import re
import json
import time
import storage as at
from llm_client import call_gemini
from config import (
    PROMPT_REDACAO_SISTEMA, STATUS_GERADO, POSTS_PER_CYCLE,
    FORMATO_TEXTO, FORMATO_IMAGEM, FORMATO_CARROSSEL,
)

# Distribuicao por ciclo: 3 texto+imagem + 2 texto puro
# Carrossel REMOVIDO — LinkedIn API nao suporta carrossel nativo (exigiria PDF).
# Publicaria so o intro text, sem os slides — confuso e incompleto.
_FORMATO_CICLO = [
    FORMATO_IMAGEM,  # 0
    FORMATO_IMAGEM,  # 1
    FORMATO_IMAGEM,  # 2
    FORMATO_TEXTO,   # 3
    FORMATO_TEXTO,   # 4
]


def run(cycle_id: str, temas: list[dict] = None) -> list[dict]:
    """
    Gera posts para todos os temas disponiveis no ciclo.
    Retorna lista de registros de posts criados.
    """
    print("[Agente Redacao] Iniciando geracao de posts...")

    if temas is None:
        temas = at.get_available_temas(cycle_id=cycle_id)

    temas = temas[:POSTS_PER_CYCLE]
    posts_criados = []
    angulos_usados = []   # hooks + teses ja escritos neste ciclo (anti-redundancia)

    for i, tema_record in enumerate(temas):
        at.mark_tema_em_uso(tema_record["id"])
        f = tema_record["fields"]
        tema_str = f.get("Tema", "")
        linha    = f.get("Linha", "")
        angulo   = f.get("Angulo sugerido", f.get("Ângulo sugerido", ""))

        if not tema_str:
            continue

        # CTA obrigatorio em todos os posts (fase laboratorio)
        formato = _FORMATO_CICLO[i % len(_FORMATO_CICLO)]

        # Anti-redundancia: informa o redator dos angulos ja usados no ciclo
        evitar = ""
        if angulos_usados:
            lista = "\n".join(f"  - {a}" for a in angulos_usados)
            evitar = (
                f"\n\nJA ESCRITO NESTE CICLO (use um angulo DIFERENTE — nao repita "
                f"a mesma tese, hook ou frase-nucleo):\n{lista}"
            )

        user_msg = (
            f"Tema: {tema_str}\n"
            f"Linha: {linha}\n"
            f"Formato: {formato}\n"
            f"CTA: Sim\n"
            f"Notas adicionais: {angulo}"
            f"{evitar}"
        )

        raw_output = call_gemini(
            system=PROMPT_REDACAO_SISTEMA,
            user=user_msg,
            max_tokens=4000,
        )
        time.sleep(5)  # 5s entre posts — respeita limite free tier Gemini (15 RPM)

        copy, brief, meta = _parse_output(raw_output, formato)

        # Registra o hook (1a linha significativa) para o proximo post evitar
        hook = _primeira_linha(copy)
        if hook:
            angulos_usados.append(hook)

        post_record = at.create_post({
            "Titulo interno": tema_str[:80],
            "Copy":           copy,
            "Linha":          meta.get("linha", linha),
            "Formato":        meta.get("formato", formato),
            "Tem CTA":        meta.get("cta", True),
            "Status":         STATUS_GERADO,
            "Origem":         "Agente",
            "Ciclo":          [cycle_id],
            "Tema":           [tema_record["id"]],
            "Image Brief":    json.dumps(brief, ensure_ascii=False) if brief else "",
        })

        posts_criados.append(post_record)
        template = brief.get("template", "sem imagem") if brief else "sem imagem"
        print(f"  [+] Post gerado: {tema_str[:55]}... [{formato} / {template}]")

    print(f"[Agente Redacao] {len(posts_criados)} posts gerados.")
    return posts_criados


def run_for_human_idea(ideia: str, cycle_id: str) -> dict:
    """Processa uma ideia bruta do Davi e gera um post completo."""
    print(f"[Agente Redacao] Processando ideia do Davi: {ideia[:60]}...")

    user_msg = (
        f"Ideia bruta do Davi (transformar em post):\n{ideia}\n\n"
        f"Escolha o melhor formato e linha. CTA sim."
    )

    raw_output = call_gemini(
        system=PROMPT_REDACAO_SISTEMA,
        user=user_msg,
        max_tokens=4000,
    )

    copy, brief, meta = _parse_output(raw_output, "")

    record = at.create_post({
        "Titulo interno": ideia[:80],
        "Copy":           copy,
        "Linha":          meta.get("linha", "Construcao de sistemas e operacao"),
        "Formato":        meta.get("formato", FORMATO_TEXTO),
        "Tem CTA":        meta.get("cta", True),
        "Status":         STATUS_GERADO,
        "Origem":         "Davi",
        "Ciclo":          [cycle_id],
        "Notas Davi":     f"Ideia original: {ideia}",
        "Image Brief":    json.dumps(brief, ensure_ascii=False) if brief else "",
    })

    print("[Agente Redacao] Post humano criado.")
    return record


# ─── anti-redundancia ─────────────────────────────────────────────────────────

def _primeira_linha(copy: str) -> str:
    """Retorna a primeira linha nao-vazia da copy (o hook), para anti-redundancia."""
    if not copy:
        return ""
    # Pula marcadores e pega o primeiro texto real
    for linha in copy.split("\n"):
        l = linha.strip().lstrip("*#-[ ").strip()
        if l and not l.upper().startswith(("COPY", "SLIDE", "BRIEF", "TIPO")):
            return l[:120]
    return ""


# ─── parsers ──────────────────────────────────────────────────────────────────

def _parse_output(raw: str, formato_hint: str) -> tuple[str, dict | None, dict]:
    """
    Separa: copy limpo | brief JSON da imagem | metadados.
    Retorna (copy, brief_dict_ou_None, meta_dict).
    """
    brief = _extract_brief(raw)

    # Remove o bloco do brief do raw antes de extrair metadados
    raw_sem_brief = re.sub(
        r"\[BRIEF DA IMAGEM JSON\].*?(\{.*?\})\s*",
        "", raw, flags=re.DOTALL
    )

    meta = {}
    linha_m   = re.search(r"\[LINHA:\s*(.+?)\]",   raw_sem_brief, re.IGNORECASE)
    formato_m = re.search(r"\[FORMATO:\s*(.+?)\]", raw_sem_brief, re.IGNORECASE)
    cta_m     = re.search(r"\[CTA:\s*(.+?)\]",     raw_sem_brief, re.IGNORECASE)
    funcao_m  = re.search(r"\[FUNCAO:\s*(.+?)\]",  raw_sem_brief, re.IGNORECASE)

    if linha_m:   meta["linha"]   = linha_m.group(1).strip()
    if formato_m: meta["formato"] = formato_m.group(1).strip()
    if cta_m:
        cta_val = cta_m.group(1).strip().lower()
        meta["cta"] = cta_val in ("sim", "yes", "true", "1")
    if funcao_m:  meta["funcao"]  = funcao_m.group(1).strip()

    # Remove todos os metadados da copy
    copy = re.sub(
        r"\[(?:LINHA|FORMATO|CTA|FUNCAO|TIPO|PONTE):[^\]]+\]",
        "", raw_sem_brief, flags=re.IGNORECASE
    )
    # Remove secao COPY DO POST / BRIEF DA IMAGEM se estiver no texto
    copy = re.sub(r"\[COPY DO POST\]", "", copy, flags=re.IGNORECASE)
    copy = re.sub(r"\[BRIEF DA IMAGEM.*?\].*", "", copy, flags=re.DOTALL | re.IGNORECASE)
    copy = copy.strip()

    return copy, brief, meta


def _extract_brief(raw: str) -> dict | None:
    """
    Extrai o JSON do brief de imagem do output do Gemini.
    O Gemini pode colocar o JSON em varios formatos:
      - Apos [BRIEF DA IMAGEM JSON]
      - Dentro de bloco ```json ... ```
      - Apos separador ***
      - Qualquer JSON com campo "template"
    """
    # 1) Marcador explicito [BRIEF DA IMAGEM JSON]
    section = re.search(
        r"\[BRIEF DA IMAGEM JSON\]\s*(\{.*?\})",
        raw, flags=re.DOTALL | re.IGNORECASE
    )
    if section:
        try:
            return json.loads(section.group(1))
        except json.JSONDecodeError:
            pass

    # 2) Bloco ```json { ... } ```
    code_block = re.search(r"```json\s*(\{.*?\})\s*```", raw, re.DOTALL | re.IGNORECASE)
    if code_block:
        try:
            data = json.loads(code_block.group(1))
            if data.get("template") in ("numero-grande", "tipografia", "comparacao", "whatsapp-mock", "passo-a-passo"):
                return data
        except json.JSONDecodeError:
            pass

    # 3) JSON apos separador *** ou ---
    after_sep = re.search(r"(?:\*{3,}|-{3,})\s*\n\s*(\{.*?\})", raw, re.DOTALL)
    if after_sep:
        try:
            data = json.loads(after_sep.group(1))
            if data.get("template") in ("numero-grande", "tipografia", "comparacao", "whatsapp-mock", "passo-a-passo"):
                return data
        except json.JSONDecodeError:
            pass

    # 4) Fallback: qualquer JSON com campo "template" valido
    for match in re.finditer(r'\{[^{}]*"template"\s*:[^{}]*\}', raw, re.DOTALL):
        try:
            data = json.loads(match.group())
            if data.get("template") in ("numero-grande", "tipografia", "comparacao", "whatsapp-mock", "passo-a-passo"):
                return data
        except json.JSONDecodeError:
            continue

    return None
