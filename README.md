# Bloco de Notas (Notepad-wind)

Editor de texto com a interface do Bloco de Notas do Windows 10, escrito em
Python + Tkinter (sem dependências externas).

![layout](https://img.shields.io/badge/interface-Windows%2010-blue)

## Executar

```bat
python notepad.py
python notepad.py arquivo.txt
```

O Python para Windows (python.org) já inclui o Tkinter.

## Gerar um .exe (opcional)

```bat
pip install pyinstaller
pyinstaller --onefile --windowed --name "BlocoDeNotas" notepad.py
```

O executável fica em `dist\BlocoDeNotas.exe`.

## Funcionalidades

- **Arquivo**: Novo, Nova Janela, Abrir, Salvar, Salvar como, Configurar página, Imprimir, Sair
- **Editar**: Desfazer, Recortar, Copiar, Colar, Excluir, Pesquisar com o Bing,
  Localizar / Localizar próxima (F3) / anterior (Shift+F3), Substituir, Ir para,
  Selecionar Tudo, Hora/Data (F5)
- **Formatar**: Quebra Automática de Linha, Fonte (família, estilo, tamanho)
- **Exibir**: Zoom (Ctrl+Mais / Ctrl+Menos / Ctrl+0 / Ctrl+roda do mouse), Barra de Status
- **Ajuda**: Exibir Ajuda, Enviar Comentários, Sobre
- Barra de status com linha/coluna, zoom, fim de linha (CRLF/LF/CR) e codificação
  (UTF-8, UTF-8 com BOM, UTF-16, ANSI) detectados automaticamente e preservados ao salvar
- Título com `*` quando há alterações e aviso para salvar antes de fechar
- Menu de contexto (botão direito)
- Preferências (fonte, quebra de linha, barra de status, tamanho da janela) salvas em
  `%APPDATA%\BlocoDeNotasPy\settings.json`
