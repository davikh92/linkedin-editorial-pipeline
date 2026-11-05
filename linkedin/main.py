"""
CLI de entrada do sistema de automacao de conteudo LinkedIn.


Comandos vivos (fluxo v2):
  python main.py fill-queue             — enche a fila: storyline + praticos (roda no PC)
  python main.py next-post              — gera 1 pratico com pesquisa fresca
  python main.py storyline              — gera e agenda uma temporada
  python main.py temporadas             — supervisao do banco de temporadas
                                          (--propor / --propor --salvar)
  python main.py publish                — publica agendados de hoje (GitHub Actions)
  python main.py diagnostico            — saude do pipeline (--strict p/ workflow)
  python main.py metricas               — medicao mensal (--mes YYYY-MM)
  python main.py review                 — abre o painel de revisao no navegador
  python main.py status                 — resumo do estado atual
  python main.py auth-linkedin          — renova o token do LinkedIn

Legado v1 (ciclo quinzenal / Airtable / API paga) removido em 01/09/2026:
new-cycle, end-cycle e schedule sairam junto com pipeline.py e scheduler.py.
"""
import sys
import io

# Força UTF-8 no stdout para evitar UnicodeEncodeError no Windows (cp1252)
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def main():
    args = sys.argv[1:]

    if not args:
        print(__doc__)
        return

    cmd = args[0]

    if cmd == "next-post":
        # Rolling v2: gera 1 post pratico com pesquisa fresca e agenda pra proxima seg/qua.
        # Flags: --dry-run (nao salva) | --date YYYY-MM-DD | --tipo "Pratico/Ferramenta"
        from rolling import run_next_post
        dry = "--dry-run" in args
        target = None
        tipo = None
        if "--date" in args:
            target = args[args.index("--date") + 1]
        if "--tipo" in args:
            tipo = args[args.index("--tipo") + 1]
        run_next_post(target_date=target, tipo=tipo, dry_run=dry)

    elif cmd == "storyline":
        # Gera e agenda uma temporada narrativa (2 capitulos/semana, ter/qui).
        # Flags: --dry-run (nao salva) | --season <chave> (forca uma temporada)
        from storyline import run_season
        dry = "--dry-run" in args
        season = None
        if "--season" in args:
            season = args[args.index("--season") + 1]
        run_season(season_key=season, dry_run=dry)

    elif cmd == "temporadas":
        # Supervisao do banco de temporadas: o que ja foi ao ar, o que esta na
        # fila e de onde vieram os fatos. Flag: --propor gera uma proposta nova
        # (pesquisa + verificacao + roteiro) e mostra, sem agendar nada.
        import storyline as sl
        if "--propor" in args:
            proposta = sl.propor_temporada(sl._pessoas_no_banco())
            if not proposta:
                print("\nNenhum candidato passou nos criterios.")
                return
            key, t = proposta
            print(f"\n=== PROPOSTA: {t['titulo']} ({key}) ===")
            print(f"Pessoa: {t['pessoa']}   |   risco: {t['risco_controversia']}")
            if t.get("controversia"):
                print(f"CONTROVERSIA: {t['controversia']}")
            print(f"\n{t['premissa']}\n")
            for i, c in enumerate(t["capitulos"], 1):
                print(f"--- capitulo {i} ---\n{c['angulo']}\n")
            print("Fontes:")
            for f in t["fontes"]:
                print(f"  - {f['fato'][:70]}\n    {f['fonte']}")
            if "--salvar" in args:
                sl._salvar_temporada(key, t)
                print("\nSalva na fila. Nenhum post foi gerado nem agendado.")
            else:
                print("\n(nada foi salvo — repita com --salvar para por na fila)")
            return

        banco = sl._carregar_banco()
        usadas = sl._chaves_usadas()
        if not banco:
            print("Banco vazio.")
            return
        print(f"{'chave':24} {'status':10} {'risco':7} fontes  pessoa")
        for key, t in banco.items():
            status = "publicada" if key in usadas else "na fila"
            print(f"{key[:24]:24} {status:10} {t.get('risco_controversia', '-'):7} "
                  f"{len(t.get('fontes', [])):6}  {t.get('pessoa', '(sem pessoa)')}")
        na_fila = [k for k in banco if k not in usadas]
        print(f"\n{len(na_fila)} na fila. O agente gera outra sozinho quando acabar.")

    elif cmd == "metricas":
        # Medicao MENSAL de performance (likes/comentarios via API) + perguntas
        # para ajustar o mix do mes seguinte. Flag: --mes YYYY-MM
        from metricas import rodar as metricas_rodar
        mes = args[args.index("--mes") + 1] if "--mes" in args else None
        metricas_rodar(mes)

    elif cmd == "diagnostico":
        # Checagem de saude do pipeline. --strict sai != 0 se precisa de acao
        # (o workflow semanal usa --strict: e-mail so quando ha algo a fazer).
        from diagnostico import rodar, imprimir
        resultados, precisa_acao = rodar()
        imprimir(resultados, precisa_acao)
        if "--strict" in args and precisa_acao:
            sys.exit(1)

    elif cmd == "fill-queue":
        # Enche a fila (buffer): storyline + praticos das proximas semanas.
        # Roda no PC do Davi via Task Scheduler. Flag: --semanas N (default 2)
        from agenda import fill_queue
        semanas = 2
        if "--semanas" in args:
            semanas = int(args[args.index("--semanas") + 1])
        fill_queue(semanas=semanas)

    elif cmd == "publish":
        from agents.agente_publicacao import run, PublicacaoError
        try:
            run()
        except PublicacaoError as e:
            # Sai com codigo != 0 para o GitHub Actions alertar por email
            print(f"\n[main] FALHA NA PUBLICACAO: {e}")
            sys.exit(1)

    elif cmd == "review":
        from review import generate
        import webbrowser
        cycle_arg = args[1] if len(args) > 1 else None
        path = generate(cycle_arg)
        webbrowser.open(f"file:///{path.replace(chr(92), '/')}")

    elif cmd == "generate-images":
        from agents.agente_imagem import run as img_run
        cycle_id = _get_current_cycle_id()
        if not cycle_id:
            print("Nenhum ciclo ativo.")
            sys.exit(1)
        img_run(cycle_id=cycle_id)

    elif cmd == "analytics":
        if len(args) < 2:
            print("Uso: python main.py analytics <cycle_id>")
            sys.exit(1)
        from agents.agente_analytics import run
        run(args[1])

    elif cmd == "advisor":
        if len(args) < 2:
            print("Uso: python main.py advisor <cycle_id>")
            sys.exit(1)
        from agents.agente_advisor import run
        run(args[1])

    elif cmd == "idea":
        if len(args) < 2:
            print("Uso: python main.py idea \"texto da ideia\"")
            sys.exit(1)
        ideia = " ".join(args[1:])
        cycle_id = _get_current_cycle_id()
        if not cycle_id:
            print("Nenhum ciclo ativo encontrado.")
            sys.exit(1)
        from agents.agente_redacao import run_for_human_idea
        from agents.agente_critico import run as critic_run
        post = run_for_human_idea(ideia, cycle_id)
        print(f"\nIdeia processada. Passando pelo Crítico...")
        critic_run(post_ids=[post["id"]], cycle_id=cycle_id)

    elif cmd == "auth-linkedin":
        from linkedin_client import authorize
        authorize()

    elif cmd == "status":
        _print_status()

    else:
        print(f"Comando desconhecido: {cmd}")
        print(__doc__)
        sys.exit(1)


def _get_current_cycle_id() -> str | None:
    import storage as nc
    cycle = nc.get_active_cycle()
    return cycle["id"] if cycle else None


def _print_status():
    import storage as nc
    from datetime import datetime, timezone
    from config import (
        STATUS_GERADO, STATUS_AGUARDANDO, STATUS_APROVADO,
        STATUS_AGENDADO, STATUS_PUBLICADO, STATUS_REPROVADO,
        TEMA_DISPONIVEL,
    )

    W = 56
    LINE = "─" * W

    def section(title):
        print(f"\n{LINE}")
        print(f"  {title}")
        print(LINE)

    def row(label, value, indent=2):
        pad = " " * indent
        print(f"{pad}{label:<28} {value}")

    print(f"\n{'═' * W}")
    print(f"  📊  LINKEDIN EDITORIAL — STATUS ATUAL")
    print(f"  {datetime.now(timezone.utc).strftime('%d/%m/%Y  %H:%M UTC')}")
    print(f"{'═' * W}")

    # ── Ciclo ativo ────────────────────────────────────────────
    section("🔄  CICLO ATIVO")
    cycle = nc.get_active_cycle()
    if not cycle:
        print("  Nenhum ciclo ativo.")
        print("  → Rode: python main.py new-cycle")
    else:
        f = cycle["fields"]
        cycle_id = cycle["id"]
        row("Nome:", f.get("Nome", cycle_id))
        row("Período:", f"{f.get('Data início','?')} → {f.get('Data fim','?')}")
        row("Total DMs:", str(f.get("Total DMs", 0)))
        row("Média impressões:", str(f.get("Média impressões", 0)))

        # ── Posts por status ───────────────────────────────────
        section("📝  POSTS DO CICLO")
        status_icons = {
            STATUS_GERADO:    ("🟡", "Gerado"),
            STATUS_REPROVADO: ("🔴", "Reprovado"),
            STATUS_AGUARDANDO:("🔵", "Aguardando aprovação"),
            STATUS_APROVADO:  ("🟢", "Aprovado"),
            STATUS_AGENDADO:  ("🟣", "Agendado"),
            STATUS_PUBLICADO: ("⚫", "Publicado"),
        }
        total_posts = 0
        for status, (icon, label) in status_icons.items():
            posts = nc.get_posts_by_status(status, cycle_id=cycle_id)
            if posts:
                total_posts += len(posts)
                row(f"{icon} {label}:", f"{len(posts)} post(s)")

        if total_posts == 0:
            print("  Nenhum post neste ciclo ainda.")
            print("  → O pipeline gera posts automaticamente no new-cycle.")

        # ── Posts aguardando aprovação (detalhe) ───────────────
        pendentes = nc.get_posts_by_status(STATUS_AGUARDANDO, cycle_id=cycle_id)
        if pendentes:
            section("✅  FILA DE APROVAÇÃO")
            for i, p in enumerate(pendentes, 1):
                titulo = p["fields"].get("Título interno", p["id"])[:48]
                linha  = (p["fields"].get("Linha") or "")[:30]
                cta    = "📣" if p["fields"].get("Tem CTA") else "  "
                print(f"  {i}. {cta} {titulo}")
                if linha:
                    print(f"      └─ {linha}")

        # ── Próximas publicações ───────────────────────────────
        agendados = nc.get_posts_by_status(STATUS_APROVADO, cycle_id=cycle_id)
        agendados += nc.get_posts_by_status(STATUS_AGENDADO, cycle_id=cycle_id)
        agendados.sort(key=lambda p: p["fields"].get("Data agendada") or "9999")
        if agendados:
            section("📅  PRÓXIMAS PUBLICAÇÕES")
            today = datetime.now(timezone.utc).date().isoformat()
            for p in agendados[:5]:
                f2 = p["fields"]
                data  = f2.get("Data agendada") or "—"
                past  = "⚠️ " if data != "—" and data < today else "   "
                titulo = (f2.get("Título interno") or p["id"])[:44]
                print(f"  {past}{data}  {titulo}")

    # ── Temas disponíveis ──────────────────────────────────────
    section("🔍  TEMAS DISPONÍVEIS")
    temas = nc.get_available_temas()
    if not temas:
        print("  Nenhum tema disponível.")
        print("  → O Agente Temas pesquisa no início de cada ciclo.")
    else:
        for t in temas[:8]:
            nome = (t["fields"].get("Tema") or "")[:44]
            rel  = t["fields"].get("Relevância") or 0
            linha = (t["fields"].get("Linha") or "")[:24]
            print(f"  ★{rel:.0f}  {nome}")
            if linha:
                print(f"       └─ {linha}")

    print(f"\n{'═' * W}\n")


if __name__ == "__main__":
    main()
