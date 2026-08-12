"""Metadados do autor — marca d'água discreta espalhada pelo app.

Centralizado aqui para facilitar atualização sem caçar strings pelo código.
"""
from __future__ import annotations

VERSAO = "2.0"
INICIAIS = "mbl"
NOME = "Mateus Braga Lima"

GITHUB = "https://github.com/bragateus"
LINKEDIN = "https://www.linkedin.com/in/mateus-braga-lima"

# Identificador curto gravado no SQLite (.sdr_controle) e nas propriedades do Excel
STAMP = f"SDR/{INICIAIS}/{VERSAO}"
