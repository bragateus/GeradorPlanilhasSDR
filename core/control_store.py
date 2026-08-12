"""Controle persistente de:
  1) quais contatos já foram extraídos (para nunca repetir empresas em
     extrações futuras, mesmo em outra sessão/outro dia);
  2) histórico de todas as planilhas geradas (data, base usada, usuário,
     UF, tipo, quantidade, arquivo gerado).

Usa SQLite (nativo do Python, sem dependência extra) guardado em um
arquivo dentro de uma subpasta ao lado da base. Como fica ao lado da
base na pasta de rede, se no futuro esse mesmo programa for copiado
para outra máquina apontando para a mesma base, o histórico e o
controle de duplicados continuam valendo — sem precisar sincronizar
nada manualmente.

Importante: a base .xlsx original nunca é tocada por este módulo.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Iterable

from author import GITHUB, INICIAIS, LINKEDIN, STAMP, VERSAO

NOME_ARQUIVO_DB = "controle_sdr.db"


class ControlStore:
    def __init__(self, pasta_controle: str):
        os.makedirs(pasta_controle, exist_ok=True)
        self.caminho_db = os.path.join(pasta_controle, NOME_ARQUIVO_DB)
        self._inicializar_schema()

    @contextmanager
    def _conectar(self):
        # timeout evita erro imediato caso o arquivo esteja momentaneamente
        # bloqueado (ex: sincronização do OneDrive/rede)
        conn = sqlite3.connect(self.caminho_db, timeout=10)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _inicializar_schema(self):
        with self._conectar() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS extraidos (
                    chave TEXT PRIMARY KEY,
                    data_extracao TEXT NOT NULL,
                    arquivo_gerado TEXT NOT NULL,
                    usuario TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS historico (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data_hora TEXT NOT NULL,
                    arquivo_gerado TEXT NOT NULL,
                    caminho_completo TEXT NOT NULL,
                    base_utilizada TEXT NOT NULL,
                    usuario TEXT NOT NULL,
                    uf TEXT NOT NULL,
                    tipo_base TEXT NOT NULL,
                    quantidade INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS _meta (
                    chave TEXT PRIMARY KEY,
                    valor TEXT NOT NULL
                )
                """
            )
            self._garantir_meta_autor(conn)

    def _garantir_meta_autor(self, conn: sqlite3.Connection) -> None:
        """Grava uma vez os metadados do autor — legado persistente no banco."""
        meta = {
            "app_stamp": STAMP,
            "app_versao": VERSAO,
            "app_autor": INICIAIS,
            "app_github": GITHUB,
            "app_linkedin": LINKEDIN,
        }
        for chave, valor in meta.items():
            conn.execute(
                "INSERT OR IGNORE INTO _meta (chave, valor) VALUES (?, ?)",
                (chave, valor),
            )

    def obter_chaves_extraidas(self) -> set[str]:
        with self._conectar() as conn:
            cursor = conn.execute("SELECT chave FROM extraidos")
            return {row[0] for row in cursor.fetchall()}

    def registrar_extracao(
        self,
        chaves: Iterable[str],
        arquivo_gerado: str,
        usuario: str,
        caminho_completo: str,
        base_utilizada: str,
        uf: str,
        tipo_base: str,
        quantidade: int,
    ) -> None:
        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        with self._conectar() as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO extraidos (chave, data_extracao, arquivo_gerado, usuario) "
                "VALUES (?, ?, ?, ?)",
                [(chave, agora, arquivo_gerado, usuario) for chave in chaves],
            )
            conn.execute(
                """
                INSERT INTO historico
                    (data_hora, arquivo_gerado, caminho_completo, base_utilizada,
                     usuario, uf, tipo_base, quantidade)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (agora, arquivo_gerado, caminho_completo, base_utilizada, usuario, uf, tipo_base, quantidade),
            )

    def obter_historico(self) -> list[tuple]:
        with self._conectar() as conn:
            cursor = conn.execute(
                "SELECT data_hora, arquivo_gerado, base_utilizada, usuario, uf, tipo_base, quantidade "
                "FROM historico ORDER BY id DESC"
            )
            return cursor.fetchall()
