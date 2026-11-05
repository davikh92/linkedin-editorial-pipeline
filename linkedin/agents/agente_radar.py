"""
Agente Radar — pesquisa fresca ANTES de cada post (arquitetura rolling v2).

Substitui o agente_temas do fluxo antigo. Diferencas:
  - Roda por post (24h antes de publicar), nao uma vez por ciclo quinzenal
  - Busca o que saiu de NOVO nos ultimos 7 dias (ferramentas, atualizacoes, truques)
  - Entrega UMA pauta pronta, com fatos reais e passo a passo sugerido

So e chamado para posts do tipo Pratico/Ferramenta — bastidor e posicionamento
usam material interno (HISTORICO + este proprio sistema).
"""
import re
from llm_local import call_claude
from prompts_v2 import PROMPT_RADAR_SISTEMA


def run(pautas_recentes: list[str] = None, categoria: dict = None) -> dict:
    """
    Pesquisa e retorna a melhor pauta (via Claude CLI local + web search).

    categoria: um item de CATEGORIAS_PRATICO (prompts_v2). Sem ela, o radar cai
    sempre em "ferramenta de IA nova" e o perfil vira noticiario de ChatGPT.
    Retorna dict: {pauta, novidade, utilidade, fatos, passo_a_passo, angulo_davi, raw}
    """
    recentes = pautas_recentes or []
    recentes_str = "\n".join(f"- {p}" for p in recentes) if recentes else "Nenhuma ainda."

    if categoria:
        print(f"[Agente Radar] Categoria: {categoria['titulo']}")
        cat_str = (
            f"CATEGORIA DESTA PAUTA: {categoria['titulo']}\n"
            f"O que se espera: {categoria['briefing']}\n\n"
        )
    else:
        print("[Agente Radar] Pesquisando (sem categoria definida)...")
        cat_str = ""

    user_message = (
        f"{cat_str}"
        "Pesquise na web (use a ferramenta WebSearch) dentro da categoria acima, "
        "pensando em dono de negocio pequeno no Brasil (2-20 funcionarios).\n\n"
        f"Pautas ja usadas recentemente (NAO repetir, nem a mesma ferramenta com "
        f"outro angulo):\n{recentes_str}\n\n"
        "Entregue UMA pauta no formato especificado."
    )

    raw = call_claude(PROMPT_RADAR_SISTEMA, user_message, web_search=True).strip()
    pauta = _parse(raw)
    pauta["raw"] = raw

    if pauta.get("pauta"):
        print(f"[Agente Radar] Pauta: {pauta['pauta'][:80]}")
    else:
        print("[Agente Radar] AVISO: nao foi possivel parsear a pauta — usando texto bruto.")
    return pauta


def _parse(text: str) -> dict:
    # Tolera markdown na saida ("**PAUTA:**") e separadores
    text = text.replace("**", "")
    text = re.sub(r"^\s*---+\s*$", "", text, flags=re.MULTILINE)
    return {
        "pauta":         _field(text, "PAUTA"),
        "novidade":      _field(text, "NOVIDADE"),
        "utilidade":     _field(text, "UTILIDADE"),
        "fatos":         _field(text, "FATOS"),
        "passo_a_passo": _field(text, "PASSO A PASSO SUGERIDO"),
        "angulo_davi":   _field(text, "ANGULO DAVI"),
    }


def _field(text: str, label: str) -> str:
    pattern = rf"{re.escape(label)}:\s*(.+?)(?=\n[A-Z][A-Z ]+:|\Z)"
    m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""
