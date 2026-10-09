# Audio to Text — plano de portfólio

## Objetivo

Transformar a pequena ferramenta Tkinter em um aplicativo desktop local demonstrável para notas de voz em português brasileiro. A primeira entrega deve mostrar um fluxo compreensível, recuperação de erros e utilidade após fechar o aplicativo, preservando a transcrição local com faster-whisper e o carregamento do modelo sob demanda.

## Estado inicial

Checkout `portfolio-audio-to-text`, baseado em `78eefe9`. O projeto contém um aplicativo Python único e README; não há AGENTS.md neste checkout. A interface inicial possui texto, gravação, contador e cópia. Usa mono 16 kHz, modelo `base` em CPU/int8, VAD e idioma português. O histórico existe apenas na sessão; erros substituem o texto e não há exportação. Não há instalador nem suíte de testes. Há risco de chamadas Tkinter a partir do worker e de exceções ao interromper o áudio.

## Primeira fatia

1. Melhorar a interface desktop existente, com hierarquia visual, histórico selecionável e área de leitura.
2. Tornar explícitos pronto, gravação, carregamento do modelo, transcrição e erro; impedir gravações concorrentes e preservar notas diante de falhas.
3. Persistir notas localmente em JSON, com escrita atômica, tratamento de falhas, exclusão confirmada e exportação Markdown.
4. Oferecer `--demo` com conteúdo fictício e armazenamento separado. Esse modo não acessa microfone nem carrega o modelo.
5. Documentar execução, privacidade, limites e roteiro de validação manual. Fazer somente revisão estática e checks de sintaxe/dependências; não criar nem executar testes.

## Critérios de entrega

- Aplicativo continua em Python/Tkinter; nenhuma migração para React/Electron.
- Modelo faster-whisper inicializado somente quando a primeira transcrição real é solicitada; processamento permanece local após o download.
- Interface comunica o estado e oferece instrução acionável em falhas sem apagar transcrições anteriores.
- Histórico recuperável após reinício, com dados fictícios separados dos dados reais; falhas de armazenamento não são tratadas como sucesso.
- Usuário pode selecionar, copiar, apagar e exportar uma nota em Markdown.
- Nenhuma captura real de áudio, acesso a microfone ou conversa real nesta execução.
- Sintaxe dos módulos verificada; limitações de validação GUI, dispositivo, download e inferência registradas honestamente.
- Somente este checkout é modificado; nenhum push, merge, deploy, publicação, alteração de GitHub/Obsidian ou ativação da tela do Orca.

## Próximas etapas (planejadas)

Estas etapas dependem de validação manual da primeira fatia pelo Felipe e ficam fora desta entrega.

| Etapa | Resultado esperado | Critério para iniciar/entregar |
| --- | --- | --- |
| Importação de áudio | Selecionar arquivo e transcrever com o mesmo pipeline local | Primeira fatia validada; formatos/limites definidos, erros claros e nenhuma cópia permanente de áudio por padrão |
| Atalho global | Iniciar/parar gravação com ação explícita do usuário | Permissões macOS avaliadas, indicador de captura sempre visível e conflito de atalhos resolvido |
| Instalador macOS | Aplicativo empacotado com instruções de modelo e permissões | Execução em máquina limpa validada; assinatura/distribuição e licença decididas antes de publicar |
| GIF curto | Demonstração de 10–20 segundos do fluxo de notas e exportação | Usar somente `--demo` e dados fictícios; revisar legibilidade e ausência de informações pessoais |

## Validação e continuidade

A revisão e os resultados dos checks desta sessão serão registrados em `docs/VALIDATION.md`. A validação manual deve incluir gravação com participação explícita do usuário, primeiro carregamento do modelo, transcrição vazia, falha de dispositivo, reinício do histórico, exclusão, exportação e fechamento durante trabalho. Não há comprovação desses fluxos reais por checks de sintaxe.

Worker Orca iniciado no mesmo checkout para a implementação Python; coordenador responsável pelo plano, README e revisão. Manter as sessões disponíveis para retomada, sem ativar a tela.

## Estado ao fim desta fatia

Implementados: interface desktop em português, estados explícitos, fila de eventos, histórico persistente selecionável, exclusão confirmada, cópia, exportação Markdown atômica e modo fictício `--demo` com histórico separado. Adicionados módulo de histórico, requirements e documentação de execução/validação. faster-whisper local e carregamento sob demanda preservados.

Revisão estática, compilação dos dois módulos Python, `pip check` e `git diff --check` passaram. Não foram executados testes nem GUI/áudio; o Python disponível não possui `_tkinter`. Portanto a entrega está implementada e revisada, mas os critérios de comportamento/aparência ainda dependem do roteiro manual pelo Felipe. As próximas etapas permanecem planejadas.
