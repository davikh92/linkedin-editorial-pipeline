"""
llm_local.py — chama o Claude pelo CLI local (plano Claude Code), nao pela API paga.

Substitui anthropic.Anthropic e call_gemini no fluxo v2. Usa a MESMA autenticacao
do `claude` que a rotina de comentarios ja usa — custo incremental zero (plano).
Roda no PC do Davi (Task Scheduler). So a publicacao continua via API (GitHub Actions).

O CLI e invocado em modo headless (`-p`) com saida JSON; lemos o campo `result`.
Rodamos a partir de um diretorio neutro para o CLI nao carregar o CLAUDE.md do projeto
(que poluiria o system prompt de redacao).

Detalhes de plataforma (Windows) resolvidos aqui:
  - subprocess.run nao resolve PATHEXT para um nome sem extensao (diferente do cmd.exe)
    — resolvemos o caminho completo do binario (claude.CMD) uma vez, via shutil.which.
  - O shim .CMD do npm passa pelo limite de linha de comando do cmd.exe (~8191 chars).
    O CEREBRO_V2 embutido nos prompts de sistema estoura isso facilmente — por isso o
    system prompt vai para um arquivo temporario (--system-prompt-file) e o user message
    vai por stdin, nunca como argumento posicional.
"""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

CLAUDE_BIN = shutil.which("claude") or "claude"
_NEUTRAL_CWD = tempfile.gettempdir()

# Modelo padrao do fluxo v2. Plano cobre — priorizamos qualidade (Sonnet) sobre custo.
MODEL_PADRAO = "claude-sonnet-4-6"

# Variaveis de auth que, se presentes, fazem o CLI ignorar o login do plano.
# O config.py faz load_dotenv() e joga ANTHROPIC_API_KEY em os.environ; como o
# subprocesso herda o ambiente, o `claude` passava a tentar a API paga e
# abortava com "claude.ai connectors are disabled because ANTHROPIC_API_KEY
# ... takes precedence over your claude.ai login" (exit 1). Foi o que derrubou
# a geracao do pratico de 19/08.
_VARS_AUTH_CONFLITANTES = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
)


def _ambiente_limpo() -> dict:
    """Ambiente do subprocesso sem as credenciais que competem com o plano."""
    env = os.environ.copy()
    for var in _VARS_AUTH_CONFLITANTES:
        env.pop(var, None)
    return env


def call_claude(system: str, user: str, model: str = MODEL_PADRAO,
                web_search: bool = False, timeout: int = 420) -> str:
    """
    Chama o Claude CLI headless e retorna o texto da resposta (campo 'result' do JSON).
    Levanta RuntimeError em falha (timeout, exit != 0, is_error, auth).
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", encoding="utf-8", delete=False
    ) as f:
        f.write(system)
        system_prompt_path = f.name

    cmd = [
        CLAUDE_BIN, "-p",
        "--system-prompt-file", system_prompt_path,
        "--output-format", "json",
        "--model", model,
        "--dangerously-skip-permissions",
    ]
    if web_search:
        cmd += ["--allowed-tools", "WebSearch"]

    try:
        proc = subprocess.run(
            cmd, input=user, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            cwd=_NEUTRAL_CWD, timeout=timeout,
            env=_ambiente_limpo(),
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"claude CLI timeout ({timeout}s)")
    except FileNotFoundError:
        raise RuntimeError(f"claude CLI nao encontrado (procurado: {CLAUDE_BIN!r}) — "
                           f"instale/logue o Claude Code.")
    finally:
        Path(system_prompt_path).unlink(missing_ok=True)

    if proc.returncode != 0:
        raise RuntimeError(f"claude CLI exit {proc.returncode}: {(proc.stderr or '')[:300]}")

    out = (proc.stdout or "").strip()
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        # fallback: em text-mode o CLI devolve o texto cru
        if out:
            return out
        raise RuntimeError(f"claude CLI saida vazia/invalida: {(proc.stderr or '')[:200]}")

    if data.get("is_error"):
        raise RuntimeError(f"claude CLI erro (status {data.get('api_error_status','?')}): "
                           f"{str(data.get('result', ''))[:300]}")
    return str(data.get("result", "")).strip()
