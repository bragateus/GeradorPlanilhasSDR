"""Modelos de dados simples usados em toda a aplicação.

Mantidos separados da UI para que a lógica de negócio não dependa
de nada relacionado a Qt/Tkinter/etc.
"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class AppConfig:
    """Configurações persistidas em config.json."""
    ultimo_arquivo_base: str = ""
    pasta_destino_padrao: str = ""
    pasta_controle: str = ""  # se vazio, usa uma subpasta ao lado da base
    quantidade_padrao: int = 400
    coluna_chave: str = ""  # se vazio, detecta automaticamente
    lista_status: List[str] = field(default_factory=lambda: [
        "Sem contato/Não atende", "Retorno", "Sem demanda", "Lead",
        "Nº não existe/Interlix", "Sem abertura", "Lead + Reunião",
        "Já cliente", "Oportunidade aberta", "Sem viabilidade", "GOV",
        "Contrato mais 6 meses", "Empresa baixada", "Contato por email",
        "Sem Interesse", "Whatsapp",
    ])


@dataclass
class ResultadoGeracao:
    """Resultado de uma geração de planilha, usado para exibir feedback e logar."""
    nome_arquivo: str
    caminho_arquivo: str
    quantidade_extraida: int
    quantidade_disponivel_restante: int
    usuario: str
    uf: str
    tipo_base: str
