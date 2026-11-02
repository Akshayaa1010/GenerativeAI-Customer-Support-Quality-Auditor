"""
Thin wrapper around the Groq API: one shared client plus helpers for the
three calls the app makes (transcribe audio, chat, chat that returns JSON).
"""

import json
import os

from groq import Groq

from backend import config

_client = None


def get_client() -> Groq:
    global _client
    if _client is None:
        if not config.GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not set. Add it to your .env file.")
        _client = Groq(api_key=config.GROQ_API_KEY, timeout=120, max_retries=2)
    return _client


def transcribe(audio_path: str, language: str | None = None) -> str:
    """Speech-to-text with Whisper. `language` is an ISO-639-1 code like 'en', or None to auto-detect."""
    with open(audio_path, "rb") as audio_file:
        response = get_client().audio.transcriptions.create(
            file=(os.path.basename(audio_path), audio_file.read()),
            model=config.GROQ_WHISPER_MODEL,
            language=language or None,
            temperature=0,
        )
    return response.text.strip()


def chat(prompt: str) -> str:
    response = get_client().chat.completions.create(
        model=config.GROQ_LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return response.choices[0].message.content.strip()


def chat_json(prompt: str) -> dict:
    """Ask the LLM for a JSON object and parse it."""
    response = get_client().chat.completions.create(
        model=config.GROQ_LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)
