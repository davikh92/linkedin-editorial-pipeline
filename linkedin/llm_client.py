"""
llm_client.py — wrapper unificado para LLMs.

Gemini Flash (gratuito) → redacao, critico, advisor
Claude Sonnet           → temas (precisa de web_search nativo Anthropic)
"""
import time
import requests
from config import GEMINI_API_KEY, GEMINI_MODEL

GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

# Esperas progressivas em segundos para retry em caso de 429 / 503
_RETRY_DELAYS = [15, 30, 60]
_RETRIABLE_CODES = {429, 503}  # quota esgotada e sobrecarga temporária


def call_gemini(system: str, user: str, max_tokens: int = 2000, temperature: float = 0.7) -> str:
    """
    Chama Gemini Flash e retorna o texto da resposta.
    Em caso de 429 (quota), aguarda e tenta novamente até 3x.
    Levanta RuntimeError se esgotar as tentativas.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY nao configurada. Adicione no .env e nos secrets do GitHub.")

    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": GEMINI_API_KEY,
    }
    payload = {
        "systemInstruction": {
            "parts": [{"text": system}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user}]
            }
        ],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": temperature,
        },
    }

    last_error = None
    for attempt, delay in enumerate([0] + _RETRY_DELAYS, start=1):
        if delay:
            print(f"  [Gemini] Erro temporário — aguardando {delay}s antes da tentativa {attempt}...")
            time.sleep(delay)

        resp = requests.post(GEMINI_URL, headers=headers, json=payload, timeout=60)

        if resp.status_code in _RETRIABLE_CODES:
            last_error = f"Gemini API erro {resp.status_code}: {resp.text[:300]}"
            continue  # tenta novamente

        if resp.status_code != 200:
            raise RuntimeError(f"Gemini API erro {resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Resposta inesperada da Gemini: {data}") from e

    raise RuntimeError(f"Gemini esgotou {len(_RETRY_DELAYS) + 1} tentativas. Ultimo erro: {last_error}")
