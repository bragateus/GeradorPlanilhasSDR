"""Workers que rodam em thread separada da UI.

Ler uma base grande de uma pasta de rede, ou gerar/salvar uma planilha,
pode demorar alguns segundos. Rodando isso numa QThread, a janela
continua respondendo (não trava) enquanto o trabalho acontece.
"""
from __future__ import annotations

import os

from PySide6.QtCore import QThread, Signal

from core import excel_service
from core.control_store import ControlStore


class CarregarBaseWorker(QThread):
    sucesso = Signal(object, str)  # df, caminho
    erro = Signal(str)

    def __init__(self, caminho_arquivo: str):
        super().__init__()
        self.caminho_arquivo = caminho_arquivo

    def run(self):
        try:
            df = excel_service.carregar_base(self.caminho_arquivo)
            self.sucesso.emit(df, self.caminho_arquivo)
        except Exception as e:
            self.erro.emit(str(e))


class GerarPlanilhaWorker(QThread):
    sucesso = Signal(object)  # ResultadoGeracao
    erro = Signal(str)

    def __init__(self, df_base, arquivo_base: str, pasta_destino: str,
                 pasta_controle: str, usuario: str, uf: str, tipo_base: str,
                 quantidade: int, lista_status: list[str], coluna_chave_config: str):
        super().__init__()
        self.df_base = df_base
        self.arquivo_base = arquivo_base
        self.pasta_destino = pasta_destino
        self.pasta_controle = pasta_controle
        self.usuario = usuario
        self.uf = uf
        self.tipo_base = tipo_base
        self.quantidade = quantidade
        self.lista_status = lista_status
        self.coluna_chave_config = coluna_chave_config

    def run(self):
        try:
            store = ControlStore(self.pasta_controle)
            coluna_chave = excel_service.detectar_coluna_chave(self.df_base, self.coluna_chave_config)
            chaves_todas = excel_service.calcular_chaves(self.df_base, coluna_chave)
            ja_extraidos = store.obter_chaves_extraidas()

            disponiveis_mask = ~chaves_todas.isin(ja_extraidos)
            df_disponivel = self.df_base[disponiveis_mask].reset_index(drop=True)
            chaves_disponiveis = chaves_todas[disponiveis_mask].reset_index(drop=True)

            if len(df_disponivel) < self.quantidade:
                self.erro.emit(
                    f"Não há contatos novos suficientes na base.\n"
                    f"Disponíveis (ainda não extraídos): {len(df_disponivel)}\n"
                    f"Solicitado: {self.quantidade}"
                )
                return

            df_sdr = df_disponivel.head(self.quantidade).copy()
            chaves_sdr = chaves_disponiveis.head(self.quantidade).tolist()

            nome_base = os.path.splitext(os.path.basename(self.arquivo_base))[0]
            caminho_saida = excel_service.gerar_nome_arquivo(
                self.pasta_destino, self.tipo_base, self.uf, self.usuario
            )

            excel_service.gerar_planilha_saida(
                df_sdr=df_sdr,
                caminho_saida=caminho_saida,
                lista_status=self.lista_status,
                coluna_chave=coluna_chave,
                usuario=self.usuario,
                uf=self.uf,
                tipo_base=self.tipo_base,
                nome_base=nome_base,
            )

            store.registrar_extracao(
                chaves=chaves_sdr,
                arquivo_gerado=os.path.basename(caminho_saida),
                usuario=self.usuario,
                caminho_completo=caminho_saida,
                base_utilizada=nome_base,
                uf=self.uf,
                tipo_base=self.tipo_base,
                quantidade=len(df_sdr),
            )

            from core.models import ResultadoGeracao
            restantes = len(df_disponivel) - len(df_sdr)
            resultado = ResultadoGeracao(
                nome_arquivo=os.path.basename(caminho_saida),
                caminho_arquivo=caminho_saida,
                quantidade_extraida=len(df_sdr),
                quantidade_disponivel_restante=restantes,
                usuario=self.usuario,
                uf=self.uf,
                tipo_base=self.tipo_base,
            )
            self.sucesso.emit(resultado)
        except Exception as e:
            self.erro.emit(str(e))
