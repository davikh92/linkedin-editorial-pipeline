"""
Agente Advisor — le os dados do ciclo encerrado e gera relatorio de aprendizado.
Retroalimenta as decisoes do proximo ciclo.
Roda ao fim de cada ciclo quinzenal.

Usa Gemini Flash (custo zero) para geracao do relatorio.
"""
from datetime import datetime, timedelta, timezone
import storage as at
from llm_client import call_gemini
from config import PROMPT_ADVISOR_SISTEMA


def run(cycle_id: str) -> str:
    """
    Gera relatorio do ciclo e salva no registro do ciclo.
    Retorna o texto do relatorio.
    """
    print(f"[Agente Advisor] Gerando relatorio do ciclo {cycle_id}...")

    cycle = at.get_cycle(cycle_id)
    if not cycle:
        print("[Agente Advisor] Ciclo nao encontrado.")
        return ""

    cycle_fields = cycle.get("fields", {})
    cycle_name   = cycle_fields.get("nome", cycle_id)

    posts = at.get_published_posts(cycle_id)
    if not posts:
        print("[Agente Advisor] Sem dados suficientes para analise.")
        return ""

    posts_data = []
    for p in posts:
        f = p["fields"]
        posts_data.append({
            "titulo":   f.get("Título interno", f.get("Titulo interno", "")),
            "copy":     f.get("Copy", ""),
            "linha":    f.get("Linha", ""),
            "formato":  f.get("Formato", ""),
            "tem_cta":  f.get("Tem CTA", False),
            "data":     f.get("Data publicação", f.get("data_publicacao", "")),
        })

    posts_summary = "\n\n".join([
        f"POST: {p['titulo']}\n"
        f"Data: {p['data']} | Linha: {p['linha']} | Formato: {p['formato']} | CTA: {'sim' if p['tem_cta'] else 'nao'}\n"
        f"Copy (primeiros 300 chars):\n{p['copy'][:300]}..."
        for p in posts_data
    ])

    next_cycle_start = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%d/%m/%Y")

    user_msg = (
        f"Ciclo: {cycle_name}\n"
        f"Periodo: {cycle_fields.get('inicio', '')} a {cycle_fields.get('fim', '')}\n"
        f"Proximo ciclo comeca em: {next_cycle_start}\n"
        f"Total de posts publicados: {len(posts)}\n\n"
        f"DADOS DOS POSTS:\n{posts_summary}\n\n"
        f"Nota: metricas de impressoes/engajamento precisam ser inseridas manualmente "
        f"via LinkedIn Analytics (API nao disponibiliza para perfis pessoais)."
    )

    try:
        relatorio = call_gemini(
            system=PROMPT_ADVISOR_SISTEMA,
            user=user_msg,
            max_tokens=2000,
            temperature=0.5,
        )
    except Exception as e:
        print(f"[Agente Advisor] Erro ao chamar Gemini: {e}")
        return ""

    at.update_cycle(cycle_id, {"relatorio_advisor": relatorio})

    print(f"[Agente Advisor] Relatorio gerado e salvo no ciclo {cycle_name}.")
    print("\n" + "=" * 60)
    print(relatorio)
    print("=" * 60 + "\n")

    return relatorio
