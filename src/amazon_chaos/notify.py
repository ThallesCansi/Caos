"""Avisos opcionais no Telegram; falhas de envio nunca interrompem o pipeline."""

import os

import requests


def telegram(text):
    token, chat = os.environ.get("TG_TOKEN"), os.environ.get("TG_CHAT_ID")
    if not token or not chat:
        return False
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat, "text": text, "disable_web_page_preview": "true"},
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        # Só o tipo do erro: a mensagem da exceção inclui a URL com o token.
        print(f"Aviso: Telegram indisponível ({type(error).__name__})", flush=True)
        return False
    return True


def reporter(send_telegram=True):
    def report(text):
        print(text, flush=True)
        if send_telegram:
            telegram(text)

    return report
