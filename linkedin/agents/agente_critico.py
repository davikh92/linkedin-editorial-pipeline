"""
Agente Critico — avalia E corrige em UMA chamada Claude.

Fluxo (self-refine de chamada unica):
  1. Claude recebe o post e da NOTA 0-10
  2. Se NOTA >= 7  -> aprova como esta (Claude so carimba)
  3. Se NOTA <  7  -> Claude ja devolve a versao corrigida na MESMA resposta
                      (secao POST REVISADO), publicavel. Sem 2a chamada, sem Gemini.

Por que chamada unica: 1 chamada Claude em vez de 3 (avaliar + Gemini reescrever +
reavaliar). Mais barato, mais simples, e quem corrige e o Claude (qualidade > Gemini).
Posts < 7 ficam marcados 'REVISAR' para supervisao do Davi, mas ja com a versao melhor.
"""
import re
import time
import anthropic
import storage as at
from agents.agente_redacao import _parse_output
from config import (
    ANTHROPIC_API_KEY, MODEL, PROMPT_CRITICO_SISTEMA,
    STATUS_APROVADO, STATUS_GERADO, NOTA_MINIMA_APROVACAO,
)


def run(post_ids: list[str] = None, cycle_id: str = None) -> dict:
    """
    Avalia e corrige posts 'Gerado' em uma passada.
    Retorna {'aprovados': [...], 'supervisao': [...]} — supervisao = nota < 7 (revisar).
    """
    print("[Agente Critico] Avaliando e corrigindo por nota...")

    if post_ids:
        posts = [at.get_post(pid) for pid in post_ids]
        posts = [p for p in posts if p]
    else:
        posts = at.get_posts_by_status(STATUS_GERADO, cycle_id=cycle_id)

    if not posts:
        print("[Agente Critico] Nenhum post para avaliar.")
        return {"aprovados": [], "supervisao": []}

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    aprovados, supervisao = [], []

    for post in posts:
        record_id = post["id"]
        f         = post["fields"]
        copy      = f.get("Copy", "")
        titulo    = f.get("Título interno", f.get("Titulo interno", record_id))
        tem_cta   = f.get("Tem CTA", False)
        formato   = f.get("Formato", "Texto + imagem")

        if not copy.strip():
            print(f"  [SKIP] {titulo[:55]} — copy vazio.")
            continue

        nota, feedback, copy_revisada, brief_novo = _avaliar_e_corrigir(
            client, copy, tem_cta, formato, tema=titulo
        )

        # Usa a versao revisada se o Claude devolveu uma
        copy_final = copy_revisada or copy
        precisa_super = nota < NOTA_MINIMA_APROVACAO

        if precisa_super and copy_revisada:
            print(f"  [{nota:.0f}/10] {titulo[:48]} — corrigido pelo critico")
        elif precisa_super:
            print(f"  [{nota:.0f}/10] {titulo[:48]} — REVISAR (sem correcao)")
        else:
            print(f"  [{nota:.0f}/10] {titulo[:48]} — aprovado direto")

        prefixo = f"NOTA {nota:.0f}/10"
        if precisa_super:
            prefixo += " — REVISAR antes de publicar"

        update = {
            "Copy":             copy_final,
            "Status":           STATUS_APROVADO,
            "Feedback Critico": f"[{prefixo}]\n{feedback}",
        }
        if brief_novo is not None:
            import json
            update["Image Brief"] = json.dumps(brief_novo, ensure_ascii=False)
        at.update_post(record_id, update)

        (supervisao if precisa_super else aprovados).append(record_id)
        time.sleep(4)  # espaca chamadas Claude

    print(f"[Agente Critico] {len(aprovados)} aprovados direto, "
          f"{len(supervisao)} corrigidos/revisar.")
    return {"aprovados": aprovados, "supervisao": supervisao}


def _avaliar_e_corrigir(client, copy, tem_cta, formato, tema=""):
    """
    Uma chamada Claude: avalia + (se nota<7) reescreve.
    Retorna (nota, feedback, copy_revisada|None, brief_novo|None).
    """
    cta_note = "Este post DEVE ter CTA ativo." if tem_cta else "Verifique se a ausencia de CTA e adequada."
    tema_note = f"Tema planejado (a copy DEVE ser sobre isto): {tema}\n\n" if tema else ""
    user_msg = (
        f"Avalie e de nota ao post abaixo. Se a nota for < 7, "
        f"reescreva-o corrigido na secao POST REVISADO.\n\n"
        f"{tema_note}"
        f"Formato do post: {formato}\n\n---\n{copy}\n---\n\n{cta_note}"
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,  # espaco p/ avaliacao + post revisado
        system=[{
            "type": "text",
            "text": PROMPT_CRITICO_SISTEMA,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": user_msg}],
    )
    output = "\n".join(b.text for b in response.content if hasattr(b, "text")).strip()

    nota = _extrair_nota(output)
    copy_revisada, brief_novo = _extrair_revisao(output, formato)
    # feedback = tudo antes do POST REVISADO
    feedback = re.split(r"POST REVISADO:", output, flags=re.IGNORECASE)[0].strip()
    return nota, feedback, copy_revisada, brief_novo


def _extrair_nota(texto: str) -> float:
    """Extrai 'NOTA: X'. Retorna 5.0 se nao achar (neutro = vai pra revisao)."""
    m = re.search(r"NOTA:\s*([0-9]+(?:[.,][0-9]+)?)", texto, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1).replace(",", "."))
        except ValueError:
            pass
    if "STATUS: APROVADO" in texto.upper():
        return 8.0
    return 5.0


def _extrair_revisao(texto: str, formato: str):
    """Extrai a copy revisada (apos 'POST REVISADO:') e o brief. Retorna (copy|None, brief|None)."""
    m = re.search(r"POST REVISADO:\s*(.+)", texto, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return None, None
    bloco = m.group(1).strip()
    if not bloco:
        return None, None
    # reusa o parser do redator p/ separar copy limpa + brief JSON
    copy, brief, _meta = _parse_output(bloco, formato)
    return (copy or None), brief
