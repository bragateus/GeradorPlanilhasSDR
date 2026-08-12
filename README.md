# Gerador de Planilhas SDR (v2)

Reescrita do gerador de planilhas de contatos, com foco em:
não perder a base, não repetir contatos em extrações futuras, ter
histórico de tudo que foi gerado, e um visual moderno (PySide6) fácil
de mexer sem tocar na lógica.

## Como rodar

```bash
pip install -r requirements.txt
python main.py
```

Não precisa de internet nem abre nenhuma porta/conexão de rede — é 100%
local (só lê/escreve arquivos em disco). Por isso não há conflito com
VPN, firewall ou proxy da empresa.

## O que mudou em relação à versão anterior

### 1. A base original nunca é alterada
Antes, o programa reescrevia a planilha-base inteira a cada extração
(removendo as linhas já usadas). Isso é o maior risco de perda de dados
do script antigo, e o "backup" que ele tentava fazer nunca era
realmente executado.

Agora o programa **só lê** a base (`pandas.read_excel`). Nada nunca é
escrito de volta nela. Quem controla quais contatos já foram extraídos
é um banco SQLite pequeno (`controle_sdr.db`), guardado numa subpasta
`.sdr_controle` ao lado do arquivo base — ou seja, na mesma pasta de
rede da empresa. Mesmo que o programa trave, tenha erro, ou seja
fechado no meio de uma extração, a base fica intacta.

### 2. Não repete contatos entre extrações
Cada extração consulta o `controle_sdr.db` para saber quais chaves
(coluna `Documento`/`CNPJ`/`CPF`, detectada automaticamente, ou um hash
da linha como último recurso) já foram usadas antes — mesmo em execuções
anteriores, em dias diferentes. Só os contatos ainda não extraídos
entram na nova planilha.

Como esse controle é baseado numa chave de identificação (não na
posição da linha), mesmo que a empresa mande uma base atualizada com
contatos novos no meio, o programa continua sabendo o que já foi
extraído.

### 3. Nomes de arquivo sempre únicos
Cada planilha gerada leva data + hora + segundos no nome, e o programa
verifica se já existe um arquivo com esse nome antes de salvar (nesse
caso, adiciona um sufixo `(1)`, `(2)`, etc.). Nunca sobrescreve
silenciosamente um arquivo já gerado.

### 4. Histórico completo
Todo arquivo gerado fica registrado no mesmo `controle_sdr.db`, com
data/hora, nome do arquivo, base usada, usuário, UF, tipo e quantidade.
Dá pra consultar isso a qualquer momento pelo botão **"Ver Histórico"**
na interface — não depende mais só do log da sessão atual (que se
perdia ao fechar o programa).

### 5. Menos I/O, interface não trava
- A formatação da coluna de documento e o dropdown de "Status" agora
  são aplicados **antes** de salvar (uma única escrita), em vez de
  salvar → reabrir → salvar de novo.
- Carregar a base e gerar a planilha rodam numa thread separada
  (`QThread`), então a janela não congela enquanto lê/grava arquivos
  na pasta de rede.

### 6. Sem imagens/links externos
Removida toda a parte de carregar ícones do LinkedIn/GitHub (que
estava dando erro de imagem não encontrada). O app não faz nenhuma
chamada de rede — só um rodapé de texto simples.

### 7. Visual modernizado e fácil de re-estilizar
A interface foi refeita em **PySide6** (Qt), com todo o visual isolado
em `ui/style.qss` — um arquivo de estilo separado da lógica. Pra mudar
cores, fontes, espaçamentos, etc., basta editar esse `.qss`; nada na
lógica de negócio (`core/`) precisa mudar.

### 8. Configurável sem editar código
`config.json` (gerado automaticamente no primeiro uso, ao lado do
`main.py`) guarda: último arquivo base usado, pasta de destino, pasta
de controle, quantidade padrão, nome da coluna-chave (se quiser forçar
manualmente) e a lista de opções do dropdown de Status. Dá pra editar
esse arquivo direto (é um JSON simples) sem tocar em nenhum `.py`.

## Estrutura do projeto

```
GeradorSDR/
├── main.py                 # ponto de entrada
├── config.py                # carregar/salvar config.json
├── requirements.txt
├── core/                     # lógica de negócio (sem nenhuma dependência de UI)
│   ├── models.py             # dataclasses (AppConfig, ResultadoGeracao)
│   ├── excel_service.py      # ler base, gerar planilha de saída, formatação
│   └── control_store.py      # SQLite: contatos já extraídos + histórico
└── ui/                       # interface gráfica (PySide6)
    ├── main_window.py        # janela principal (só layout/eventos)
    ├── workers.py             # QThread workers (não travam a UI)
    └── style.qss              # visual — edite aqui sem medo
```

A separação `core/` (lógica pura) vs `ui/` (interface) foi proposital:
dá pra trocar de PySide6 para outra coisa no futuro (ou até criar uma
versão web) reaproveitando 100% do `core/` sem reescrever nada da regra
de negócio.

## Uso em outra máquina / compartilhar depois

Hoje é uso individual, mas para facilitar compartilhar depois:

1. Copie a pasta `GeradorSDR` inteira para a outra máquina (ou
   distribua via um `.exe` gerado com PyInstaller — veja abaixo).
2. Aponte o "Arquivo base" para o mesmo arquivo na pasta de rede da
   empresa. Como o `controle_sdr.db` fica **ao lado da base** (não na
   máquina local), o histórico e o controle de "já extraído" já valem
   automaticamente para quem também apontar pra essa base — sem
   precisar copiar nada manualmente.
3. **Atenção**: o controle atual não trata uso *simultâneo* por duas
   pessoas ao mesmo tempo (não era um requisito agora). Se no futuro
   isso passar a acontecer, dá pra evoluir o SQLite para lidar com
   concorrência (ele já suporta transações, só precisaria de um pouco
   de tratamento de retry em caso de lock).

### Gerando um .exe (opcional, para não precisar instalar Python na outra máquina)

```bash
pip install pyinstaller
pyinstaller --noconsole --onefile --name GeradorSDR main.py
```

O executável fica em `dist/GeradorSDR.exe`. Leve, sem instalar nada
além do próprio `.exe` — e continua sem nenhuma dependência de rede.
