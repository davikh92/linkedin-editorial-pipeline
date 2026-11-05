"""
Agente Analytics — coleta métricas dos posts publicados.

Limitação do LinkedIn API para perfis pessoais:
  Impressões e alcance NÃO estão disponíveis via API.
  O que a API fornece: curtidas, comentários, compartilhamentos.
  Davi precisa inserir impressões manualmente no Airtable.

Roda quinzenalmente ao fim de cada ciclo.
"""
import storage as at
from linkedin_client import LinkedInClient


def run(cycle_id: str) -> list[dict]:
    """
    Coleta métricas para todos os posts publicados do ciclo.
    Retorna lista de registros de métricas criados/atualizados.
    """
    print(f"[Agente Analytics] Coletando métricas do ciclo {cycle_id}...")

    posts = at.get_published_posts(cycle_id)
    if not posts:
        print("[Agente Analytics] Nenhum post publicado neste ciclo.")
        return []

    client = LinkedInClient()
    resultados = []

    for post in posts:
        record_id = post["id"]
        fields = post["fields"]
        titulo = fields.get("titulo_interno", record_id)
        post_urn = fields.get("linkedin_post_id", "")

        stats = {"curtidas": 0, "comentarios": 0, "compartilhamentos": 0}
        if post_urn:
            try:
                stats = client.get_post_stats(post_urn)
            except Exception as e:
                print(f"  [WARN] Não foi possível obter stats de {titulo[:40]}: {e}")

        metricas_fields = {
            "curtidas": stats["curtidas"],
            "comentarios": stats["comentarios"],
            "compartilhamentos": stats["compartilhamentos"],
            # impressoes e alcance: inserção manual pelo Davi no Airtable
        }

        record = at.upsert_metricas(record_id, metricas_fields)
        resultados.append(record)

        print(f"  [{titulo[:40]}] curtidas={stats['curtidas']} comentarios={stats['comentarios']}")

    print(f"[Agente Analytics] {len(resultados)} registros de métricas atualizados.")
    print("[Agente Analytics] Lembrete: inserir impressões manualmente no Airtable (não disponível via API).")
    return resultados
