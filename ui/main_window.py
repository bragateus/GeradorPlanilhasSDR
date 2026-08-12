"""Janela principal (PySide6). Só cuida de layout/eventos de UI.

Toda a lógica de negócio mora em core/*.py e roda em background através
de ui/workers.py — a janela nunca lê/escreve planilhas diretamente, só
aciona os workers e reage aos sinais deles. Isso facilita reestilizar a
interface (ou até trocar de framework) no futuro sem tocar em nada da
lógica de extração/geração de arquivos.
"""
from __future__ import annotations

import os
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QGroupBox, QFileDialog, QMessageBox,
    QPlainTextEdit, QSpinBox, QProgressBar, QTableWidget, QTableWidgetItem,
    QDialog, QDialogButtonBox,
)

from author import GITHUB, INICIAIS, LINKEDIN, NOME, STAMP, VERSAO

from config import carregar_config, salvar_config
from core.control_store import ControlStore
from ui.workers import CarregarBaseWorker, GerarPlanilhaWorker


class JanelaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gerador de Planilhas SDR")
        self.resize(720, 640)

        self.cfg = carregar_config()

        # ultimo_arquivo_base no config guarda o caminho do ÚLTIMO ARQUIVO usado
        self.arquivo_base: str | None = self.cfg.ultimo_arquivo_base or None
        if self.arquivo_base and not os.path.exists(self.arquivo_base):
            self.arquivo_base = None
        self.df_base = None
        self.pasta_destino: str | None = self.cfg.pasta_destino_padrao or None

        # Guarda referências fortes a QThreads em andamento. Importante:
        # nunca sobrescrever um único atributo com uma nova QThread antes da
        # anterior terminar — se a antiga perder a última referência Python
        # enquanto ainda está rodando, o Qt derruba o processo
        # ("QThread: Destroyed while thread is still running"). Por isso
        # usamos uma lista e só removemos o worker quando ele sinaliza
        # `finished`.
        self._workers_ativos: list = []

        self._montar_ui()

        if self.arquivo_base:
            self._iniciar_carregamento_base(self.arquivo_base)
        if self.pasta_destino:
            self.label_pasta.setText(self.pasta_destino)
            self.label_pasta.setObjectName("labelStatusOk")

    # ---------------------------------------------------------------- UI --
    def _montar_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(12)

        titulo = QLabel("Gerador de Planilhas SDR")
        titulo.setObjectName("tituloApp")
        subtitulo = QLabel("Extração de contatos para SDR")
        subtitulo.setObjectName("subtituloApp")
        layout.addWidget(titulo)
        layout.addWidget(subtitulo)

        # --- Grupo: arquivos ---
        grupo_arquivos = QGroupBox("Base e destino")
        grid = QGridLayout(grupo_arquivos)

        self.label_arquivo = QLabel("Nenhum arquivo selecionado")
        self.label_arquivo.setObjectName("labelStatusPendente")
        self.btn_arquivo = QPushButton("Selecionar base (.xlsx)")
        self.btn_arquivo.clicked.connect(self.selecionar_arquivo)
        grid.addWidget(QLabel("Arquivo base:"), 0, 0)
        grid.addWidget(self.label_arquivo, 0, 1)
        grid.addWidget(self.btn_arquivo, 0, 2)

        self.label_pasta = QLabel("Nenhuma pasta selecionada")
        self.label_pasta.setObjectName("labelStatusPendente")
        self.btn_pasta = QPushButton("Selecionar pasta destino")
        self.btn_pasta.clicked.connect(self.selecionar_pasta)
        grid.addWidget(QLabel("Pasta de destino:"), 1, 0)
        grid.addWidget(self.label_pasta, 1, 1)
        grid.addWidget(self.btn_pasta, 1, 2)

        self.label_info = QLabel("")
        grid.addWidget(self.label_info, 2, 0, 1, 3)

        layout.addWidget(grupo_arquivos)

        # --- Grupo: configurações do SDR ---
        grupo_sdr = QGroupBox("Configurações da extração")
        grid2 = QGridLayout(grupo_sdr)

        self.entry_nome_sdr = QLineEdit()
        grid2.addWidget(QLabel("Nome do usuário:"), 0, 0)
        grid2.addWidget(self.entry_nome_sdr, 0, 1)

        self.entry_uf = QLineEdit()
        self.entry_uf.setMaxLength(2)
        grid2.addWidget(QLabel("UF do estado:"), 1, 0)
        grid2.addWidget(self.entry_uf, 1, 1)

        self.entry_tipo_base = QLineEdit()
        grid2.addWidget(QLabel("Tipo da base:"), 2, 0)
        grid2.addWidget(self.entry_tipo_base, 2, 1)

        self.spin_quantidade = QSpinBox()
        self.spin_quantidade.setRange(1, 1_000_000)
        self.spin_quantidade.setValue(self.cfg.quantidade_padrao)
        grid2.addWidget(QLabel("Quantidade de contatos:"), 3, 0)
        grid2.addWidget(self.spin_quantidade, 3, 1)

        layout.addWidget(grupo_sdr)

        # --- Botões de ação ---
        linha_botoes = QHBoxLayout()
        self.btn_gerar = QPushButton("Gerar Planilha SDR")
        self.btn_gerar.setObjectName("botaoPrimario")
        self.btn_gerar.clicked.connect(self.gerar_planilha_sdr)
        self.btn_estatisticas = QPushButton("Ver Estatísticas")
        self.btn_estatisticas.clicked.connect(self.mostrar_estatisticas)
        self.btn_historico = QPushButton("Ver Histórico")
        self.btn_historico.clicked.connect(self.mostrar_historico)
        linha_botoes.addWidget(self.btn_gerar)
        linha_botoes.addWidget(self.btn_estatisticas)
        linha_botoes.addWidget(self.btn_historico)
        layout.addLayout(linha_botoes)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # indeterminado
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # --- Log ---
        grupo_log = QGroupBox("Log de atividades")
        layout_log = QVBoxLayout(grupo_log)
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        layout_log.addWidget(self.log_text)
        layout.addWidget(grupo_log, stretch=1)

        linha_rodape = QHBoxLayout()
        texto_rodape = QLabel("Uso interno — extração e controle de contatos SDR")
        texto_rodape.setObjectName("rodapeTexto")
        marca = QLabel(f"v{VERSAO} · {INICIAIS}")
        marca.setObjectName("marcaAutor")
        marca.setCursor(Qt.PointingHandCursor)
        marca.setToolTip("Clique para mais informações")
        marca.mouseReleaseEvent = lambda _e: self._mostrar_sobre()  # type: ignore[method-assign]
        linha_rodape.addWidget(texto_rodape)
        linha_rodape.addStretch()
        linha_rodape.addWidget(marca)
        layout.addLayout(linha_rodape)

    def _mostrar_sobre(self):
        dialogo = QDialog(self)
        dialogo.setWindowTitle("Sobre")
        dialogo.setFixedWidth(340)
        layout = QVBoxLayout(dialogo)

        titulo = QLabel("Gerador de Planilhas SDR")
        titulo.setObjectName("tituloApp")
        versao = QLabel(f"Versão {VERSAO}")
        versao.setObjectName("subtituloApp")
        autor = QLabel(
            f'Desenvolvido por {NOME}<br>'
            f'<a href="{GITHUB}">GitHub</a> · '
            f'<a href="{LINKEDIN}">LinkedIn</a>'
        )
        autor.setObjectName("sobreAutor")
        autor.setOpenExternalLinks(True)
        autor.setTextFormat(Qt.RichText)
        autor.setTextInteractionFlags(Qt.TextBrowserInteraction)
        stamp = QLabel(STAMP)
        stamp.setObjectName("sobreStamp")

        layout.addWidget(titulo)
        layout.addWidget(versao)
        layout.addSpacing(8)
        layout.addWidget(autor)
        layout.addWidget(stamp)

        botoes = QDialogButtonBox(QDialogButtonBox.Close)
        botoes.rejected.connect(dialogo.close)
        botoes.accepted.connect(dialogo.close)
        layout.addWidget(botoes)

        dialogo.exec()

    # ------------------------------------------------------------ util --
    def log(self, mensagem: str):
        hora = datetime.now().strftime("%H:%M:%S")
        self.log_text.appendPlainText(f"[{hora}] {mensagem}")

    def pasta_controle_atual(self) -> str:
        if self.cfg.pasta_controle:
            return self.cfg.pasta_controle
        if self.arquivo_base:
            return os.path.join(os.path.dirname(self.arquivo_base), ".sdr_controle")
        return ".sdr_controle"

    def _travar_ui(self, travado: bool):
        self.btn_gerar.setEnabled(not travado)
        self.btn_estatisticas.setEnabled(not travado)
        self.btn_arquivo.setEnabled(not travado)
        self.btn_pasta.setEnabled(not travado)
        self.progress.setVisible(travado)

    def _iniciar_worker(self, worker):
        """Mantém uma referência forte ao worker até ele terminar de fato.

        Nunca guarde a QThread só num atributo simples que possa ser
        reatribuído — se a QThread antiga perder a última referência
        Python enquanto o run() ainda está executando, o Qt derruba o
        processo. Guardando numa lista e só removendo no sinal
        `finished`, isso nunca acontece, mesmo que duas operações se
        sobreponham.
        """
        self._workers_ativos.append(worker)

        def _limpar():
            if worker in self._workers_ativos:
                self._workers_ativos.remove(worker)

        worker.finished.connect(_limpar)
        worker.start()

    # ------------------------------------------------------ seleção base --
    def selecionar_arquivo(self):
        arquivo, _ = QFileDialog.getOpenFileName(
            self, "Selecionar arquivo Excel base", "", "Excel files (*.xlsx *.xls)"
        )
        if not arquivo:
            return
        self._iniciar_carregamento_base(arquivo)

    def _iniciar_carregamento_base(self, arquivo: str):
        self._travar_ui(True)
        self.log(f"Carregando base: {os.path.basename(arquivo)} ...")
        worker = CarregarBaseWorker(arquivo)
        worker.sucesso.connect(self._base_carregada)
        worker.erro.connect(self._erro_carregar_base)
        self._iniciar_worker(worker)

    def _base_carregada(self, df, caminho):
        self._travar_ui(False)
        self.df_base = df
        self.arquivo_base = caminho
        nome = os.path.basename(caminho)
        self.label_arquivo.setText(nome)
        self.label_arquivo.setObjectName("labelStatusOk")
        self.log(f"Base carregada: {nome} ({len(df)} contatos no total)")
        self.cfg.ultimo_arquivo_base = caminho
        salvar_config(self.cfg)
        self._atualizar_info_contatos()

    def _erro_carregar_base(self, mensagem: str):
        self._travar_ui(False)
        QMessageBox.critical(self, "Erro", f"Erro ao carregar arquivo:\n{mensagem}")
        self.log(f"❌ Erro ao carregar base: {mensagem}")

    def selecionar_pasta(self):
        pasta = QFileDialog.getExistingDirectory(self, "Selecionar pasta de destino")
        if not pasta:
            return
        self.pasta_destino = pasta
        self.label_pasta.setText(pasta)
        self.label_pasta.setObjectName("labelStatusOk")
        self.cfg.pasta_destino_padrao = pasta
        salvar_config(self.cfg)
        self.log(f"Pasta de destino selecionada: {pasta}")

    def _atualizar_info_contatos(self):
        if self.df_base is None or not self.arquivo_base:
            return
        try:
            store = ControlStore(self.pasta_controle_atual())
            from core import excel_service
            coluna_chave = excel_service.detectar_coluna_chave(self.df_base, self.cfg.coluna_chave)
            chaves = excel_service.calcular_chaves(self.df_base, coluna_chave)
            ja_extraidos = store.obter_chaves_extraidas()
            disponiveis = (~chaves.isin(ja_extraidos)).sum()
            self.label_info.setText(
                f"Total na base: {len(self.df_base)}  |  Já extraídos anteriormente: "
                f"{len(self.df_base) - disponiveis}  |  Disponíveis agora: {disponiveis}"
            )
        except Exception as e:
            self.log(f"⚠️ Não foi possível calcular contatos disponíveis: {e}")

    # ---------------------------------------------------------- geração --
    def gerar_planilha_sdr(self):
        if self.df_base is None:
            QMessageBox.warning(self, "Aviso", "Primeiro selecione um arquivo base")
            return
        if not self.pasta_destino:
            QMessageBox.warning(self, "Aviso", "Primeiro selecione uma pasta de destino")
            return
        nome_sdr = self.entry_nome_sdr.text().strip()
        if not nome_sdr:
            QMessageBox.warning(self, "Aviso", "Digite o nome do usuário")
            return
        uf = self.entry_uf.text().strip().upper()
        if not uf:
            QMessageBox.warning(self, "Aviso", "Digite a UF do estado")
            return
        tipo_base = self.entry_tipo_base.text().strip()
        if not tipo_base:
            QMessageBox.warning(self, "Aviso", "Digite o Tipo da base")
            return
        quantidade = self.spin_quantidade.value()

        self._travar_ui(True)
        self.log(f"Gerando planilha para {nome_sdr} - {uf} ({quantidade} contatos)...")

        worker = GerarPlanilhaWorker(
            df_base=self.df_base,
            arquivo_base=self.arquivo_base,
            pasta_destino=self.pasta_destino,
            pasta_controle=self.pasta_controle_atual(),
            usuario=nome_sdr,
            uf=uf,
            tipo_base=tipo_base,
            quantidade=quantidade,
            lista_status=self.cfg.lista_status,
            coluna_chave_config=self.cfg.coluna_chave,
        )
        worker.sucesso.connect(self._planilha_gerada)
        worker.erro.connect(self._erro_gerar_planilha)
        self._iniciar_worker(worker)

    def _planilha_gerada(self, resultado):
        self._travar_ui(False)
        self.log(f" Planilha criada: {resultado.nome_arquivo}")
        self.log(f" {resultado.quantidade_extraida} contatos extraídos para {resultado.usuario} - {resultado.uf}")
        self.log(f" Restam {resultado.quantidade_disponivel_restante} contatos disponíveis (não extraídos ainda)")
        self._atualizar_info_contatos()
        self.entry_nome_sdr.clear()

        resposta = QMessageBox.information(
            self, "Sucesso",
            f"Planilha criada com sucesso!\n\n"
            f"Arquivo: {resultado.nome_arquivo}\n"
            f"Usuário: {resultado.usuario} - {resultado.uf}\n"
            f"Contatos extraídos: {resultado.quantidade_extraida}\n"
            f"Contatos disponíveis restantes: {resultado.quantidade_disponivel_restante}",
        )
        abrir = QMessageBox.question(
            self, "Abrir Pasta", "Deseja abrir a pasta do arquivo gerado?"
        )
        if abrir == QMessageBox.Yes:
            self._abrir_pasta(resultado.caminho_arquivo)

    def _erro_gerar_planilha(self, mensagem: str):
        self._travar_ui(False)
        QMessageBox.warning(self, "Aviso", mensagem)
        self.log(f"⚠️ {mensagem}")

    def _abrir_pasta(self, caminho_arquivo: str):
        pasta = os.path.dirname(os.path.abspath(caminho_arquivo))
        try:
            if os.name == "nt":
                os.startfile(pasta)  # Windows
            elif os.uname().sysname == "Darwin":
                os.system(f'open "{pasta}"')
            else:
                os.system(f'xdg-open "{pasta}"')
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível abrir a pasta:\n{e}")

    # -------------------------------------------------------- estatísticas --
    def mostrar_estatisticas(self):
        if self.df_base is None:
            QMessageBox.warning(self, "Aviso", "Primeiro selecione um arquivo base")
            return
        colunas = ", ".join(self.df_base.columns)
        texto = f"Total de contatos: {len(self.df_base)}\nColunas disponíveis: {colunas}\n\n"
        texto += "Contatos preenchidos (primeiras 5 colunas):\n"
        for col in self.df_base.columns[:5]:
            texto += f"- {col}: {self.df_base[col].count()} preenchidos\n"
        QMessageBox.information(self, "Estatísticas", texto)

    # ------------------------------------------------------------ histórico --
    def mostrar_historico(self):
        try:
            store = ControlStore(self.pasta_controle_atual())
            registros = store.obter_historico()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível ler o histórico:\n{e}")
            return

        dialogo = QDialog(self)
        dialogo.setWindowTitle("Histórico de planilhas geradas")
        dialogo.resize(820, 420)
        layout = QVBoxLayout(dialogo)

        tabela = QTableWidget()
        colunas = ["Data/Hora", "Arquivo Gerado", "Base Utilizada", "Usuário", "UF", "Tipo", "Qtd"]
        tabela.setColumnCount(len(colunas))
        tabela.setHorizontalHeaderLabels(colunas)
        tabela.setRowCount(len(registros))
        for i, linha in enumerate(registros):
            for j, valor in enumerate(linha):
                tabela.setItem(i, j, QTableWidgetItem(str(valor)))
        tabela.resizeColumnsToContents()
        layout.addWidget(tabela)

        botoes = QDialogButtonBox(QDialogButtonBox.Close)
        botoes.rejected.connect(dialogo.close)
        botoes.accepted.connect(dialogo.close)
        layout.addWidget(botoes)

        dialogo.exec()


def rodar_app():
    app = QApplication.instance() or QApplication([])
    caminho_qss = os.path.join(os.path.dirname(os.path.abspath(__file__)), "style.qss")
    if os.path.exists(caminho_qss):
        with open(caminho_qss, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    janela = JanelaPrincipal()
    janela.show()
    app.exec()
