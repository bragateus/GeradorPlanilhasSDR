"""Carrega/salva config.json ao lado do executável/script.

Guardar isso fora do código-fonte permite mudar a lista de status do
dropdown, pastas padrão, etc. sem precisar editar/recompilar o programa.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict

from core.models import AppConfig

NOME_ARQUIVO_CONFIG = "config.json"


def _caminho_config() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), NOME_ARQUIVO_CONFIG)


def carregar_config() -> AppConfig:
    caminho = _caminho_config()
    if not os.path.exists(caminho):
        cfg = AppConfig()
        salvar_config(cfg)
        return cfg
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            dados = json.load(f)
        cfg = AppConfig(**{**asdict(AppConfig()), **dados})
        return cfg
    except (json.JSONDecodeError, TypeError):
        # config corrompido -> volta ao padrão sem derrubar o app
        return AppConfig()


def salvar_config(cfg: AppConfig) -> None:
    caminho = _caminho_config()
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(asdict(cfg), f, ensure_ascii=False, indent=2)
