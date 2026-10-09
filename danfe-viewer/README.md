# DANFE Viewer

Programa para **Windows** que abre o XML da NF-e (modelo 55), mostra o **DANFE** na tela com zoom e rolagem,
**imprime** e **salva em PDF**. Feito em Python (PySide6) para ser fácil de estudar e evoluir.

> A experiência de uso (zoom, rolagem, impressão) foi inspirada no KPDF View, mas **nenhum código dele foi usado**.
> Este projeto é independente do restante do repositório (que é uma biblioteca Kotlin para Android/iOS).

## Como instalar (uma vez só)

1. Instale o Python 3.11 ou mais novo em <https://www.python.org/downloads/>.
   **Na primeira tela do instalador, marque "Add python.exe to PATH".**
2. Nesta pasta, dê dois cliques em **`instalar.bat`**. Ele baixa as bibliotecas (precisa de internet).
3. Pronto. Dê dois cliques em **`abrir.bat`**.

## Como usar

| Ação | Como |
|---|---|
| Abrir XML | `Ctrl+O`, ou arraste o arquivo para a janela, ou arraste o XML sobre `abrir.bat` |
| Vários XMLs | selecione vários no diálogo: cada um abre numa aba |
| Zoom | `Ctrl` + roda do mouse, botões **Zoom +/−**, `Ctrl+0` largura, `Ctrl+9` folha inteira, `Ctrl+1` 100% |
| Mover | arraste com o mouse, roda do mouse, `PgUp`/`PgDn` |
| Salvar PDF | `Ctrl+S` (o nome sugerido é `DANFE_<chave de acesso>.pdf`) |
| Imprimir | `Ctrl+P` (escolha a impressora, ou "Microsoft Print to PDF") |

### Converter sem abrir a janela (útil para muitos arquivos)

```bat
.venv\Scripts\activate
python -m danfe_viewer --pdf-dir C:\PDFs  C:\xmls\*.xml
python -m danfe_viewer --pdf saida.pdf nota.xml
```

### Gerar um `.exe`

Dê dois cliques em `gerar_exe.bat`. O programa fica em `dist\DANFE-Viewer\` (copie a pasta inteira).

## O que o DANFE contém

Canhoto, identificação do emitente, código de barras (Code 128) e chave de acesso, protocolo de autorização,
destinatário, fatura/duplicatas, cálculo do imposto, transportador/volumes, tabela de produtos (com lote/validade
e informação adicional do item), ISSQN (quando houver) e dados adicionais. Notas grandes continuam em várias folhas
(cabeçalho repetido, "FOLHA n/N"). Marca d'água para **homologação**, **cancelada**, **denegada** e **sem protocolo**.

## Como o código está organizado (para quando você estudar Python)

```
danfe_viewer/
  core/formatting.py   formata CNPJ, datas, valores em "1.234,56"...
  core/xmlload.py      lê o XML com segurança e tira os namespaces
  nfe/model.py         "fichas" (dataclasses) que guardam os dados da nota
  nfe/parser.py        XML  ->  ficha (Nfe)
  nfe/danfe.py         ficha (Nfe)  ->  PDF (ReportLab)   <- aqui está o layout
  documents.py         escolhe o tratamento pelo tipo do XML (NF-e, CT-e, ...)
  cli.py               modo linha de comando
  ui/                  janela, visualizador (pdf_view.py) e impressão (printing.py)
tests/                 testes automáticos:  python -m pytest
```

O caminho de uma nota: `xmlload` lê → `parser` monta o `Nfe` → `danfe` desenha o PDF → `ui/pdf_view` mostra
(com `pypdfium2`) → `ui/printing` imprime. A janela mostra o **mesmo PDF** que será salvo, então o que você vê é o que sai.

### Para adicionar CT-e, MDF-e ou NFC-e

Crie um pacote ao lado de `nfe/` (`parser` + `render`) e registre-o em `_BUILDERS` no `documents.py`.
A janela e a linha de comando não precisam mudar. Hoje esses tipos mostram uma mensagem clara de "ainda não implementado".

## Limitações conhecidas (seja prudente em produção)

- **Ainda não implementados:** NFC-e (modelo 65), CT-e (DACTE) e MDF-e (DAMDFE).
- **Contingência (tpEmis ≠ 1):** só mostra o aviso no quadro do protocolo; o segundo código de barras do DANFE
  em contingência **não** foi implementado.
- **Bloco "IBS / CBS (informativo)":** mostra os totais que vêm no XML (reforma tributária). Não é um quadro
  oficial do leiaute que eu tenha conferido; confirme com seu contador/ERP e, se preciso, desligue (`_draw_first_blocks`).
- **O leiaute segue o Manual de Orientação do Contribuinte (Anexo II)** conforme meu conhecimento, mas **não foi
  homologado/auditado** por contador ou pela SEFAZ. Compare com o DANFE do seu ERP antes de usar como documento oficial.
- **Não valida a assinatura digital** nem consulta a SEFAZ: apenas confere o dígito verificador da chave e se há protocolo.
- Testado em Linux (testes automáticos + simulação da janela) com 5 XMLs reais; **ainda não testado em Windows nem
  com impressora física**. A impressão é rasterizada a até 600 dpi e ajustada à área imprimível da impressora.

## Desenvolvimento

```bat
.venv\Scripts\activate
python -m pip install -r requirements-dev.txt
python -m pytest
```

Os XMLs reais ficam em `samples/` e **não vão para o Git** (têm dados fiscais de terceiros).
