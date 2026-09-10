# Changelog — WinZapp (fork reffehcsoibaf)

Registro das modificações feitas sobre o WinZapp original
(gabrielhhaber/WinZapp_Python), a partir da versão em que começamos a
mexer no projeto.

## v1.1.0.0 — base original (upstream, sem modificações)

Ponto de partida: o WinZapp original, clonado direto do repositório
público de gabrielhhaber, antes de qualquer modificação nossa.

## v1.1.0.2 — correções de IA e feedback de progresso

### Correções
- Corrigido: descrever vídeos (e outros arquivos maiores) às vezes dava
  erro `FAILED_PRECONDITION` / "File ... is not in an ACTIVE state". O
  Gemini precisa de um tempo pra processar arquivos enviados por upload
  antes de poder analisá-los — o código agora espera esse processamento
  terminar (até 90s) antes de usar o arquivo.

### Melhorias
- Aviso falado a cada ~8 segundos ("Ainda processando com o Gemini...")
  enquanto qualquer pedido de transcrição/descrição/conversão está em
  andamento — cobre o envio do arquivo, o processamento do Gemini e a
  geração da resposta, incluindo as perguntas de acompanhamento em
  imagem/vídeo.

## v1.1.0.1 — primeira leva de modificações

### Novidades de acessibilidade (IA via Gemini)
- Nova aba **"Transcrições e Descrições"** em Configurações: liga/desliga
  os recursos de IA, campo para a chave de API do Gemini, e opções
  separadas para transcrever áudio, descrever imagens, descrever vídeos e
  converter PDF em texto acessível.
- Menu de contexto das mensagens: **"Transcrever"** (áudio), **"Descrever"**
  (imagem/vídeo) e **"Converter em texto acessível"** (PDF).
- Janela de resultado navegável por setas, com botão para copiar tudo.
- Para imagem/vídeo: campo de pergunta de acompanhamento (ex.: perguntar o
  preço de um produto específico num encarte que a descrição geral não
  detalhou).
- Corrigido: arquivos `.m4a` (e outros formatos de áudio menos comuns,
  como `.amr`/`.aac`) eram rejeitados pelo Gemini por tipo de arquivo não
  reconhecido pelo Python — agora tratados corretamente.
- Corrigido: transcrever mensagens de voz dava erro de "não foi possível
  baixar a mídia", porque elas ficam guardadas numa pasta/formato
  diferente (`voice_messages/*.msv`) do resto das mídias
  (`media/*.wzmedia`) — o código de transcrição usava o caminho errado.

### Instalação e primeira execução
- Instalações novas vêm com **atualizações automáticas desligadas** por
  padrão.
- As três perguntas do primeiro uso (API personalizada, início automático
  com o Windows, atalho de teclado global) não aparecem mais por padrão —
  continuam disponíveis manualmente nas Configurações pra quem quiser.
- Download automático de mídia: prazo padrão reduzido de 30 para 1 dia.

### Sincronização
- Progresso falado a cada ~5 segundos durante a sincronização de
  conversas ("Sincronizando conversas: X de Y") e o download de mídias
  ("Baixando mídia: X de Y processadas, Z baixadas").

### Empacotamento (build)
- Ajustado `build.py` para funcionar com uma versão do Node.js LTS
  embutida — evita um bug de instalação de dependências visto com a
  versão "Current" mais recente do Node.
- Decisão registrada: **não** empacotar a `node_modules` (~600MB) dentro
  do instalador/portátil — prioriza um arquivo menor pra baixar, aceitando
  uma etapa de instalação de dependências na primeira abertura.

### Investigado, mas não implementado / abandonado
- "Mensagens trancadas" (senha revelada na busca, como o WhatsApp
  oficial): abandonado — o WPPConnect não expõe esse estado, e uma
  implementação própria não teria a mesma segurança do recurso original.
- Integração com a API do Be My Eyes: não existe API pública pra
  terceiros: a empresa absorve o custo do provedor de IA por trás; sem
  isso, cada pessoa precisa da própria chave (como já fazemos com o
  Gemini).
- Função de "Reiniciar conexão do WhatsApp" pelo menu Arquivo: chegou a
  ser implementada, mas removida por falta de utilidade prática percebida
  no uso real.
