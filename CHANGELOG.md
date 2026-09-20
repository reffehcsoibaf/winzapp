# Changelog — WinZapp (fork reffehcsoibaf)

Registro das modificações feitas sobre o WinZapp original
(gabrielhhaber/WinZapp_Python), a partir da versão em que começamos a
mexer no projeto.

## v1.1.2.1 — correção de segurança: troca do código de conversas trancadas

### Correções
- **Falha de segurança corrigida**: a aba Privacidade (Configurações >
  Conversas > Conversas trancadas) permitia definir um novo código de
  conversas trancadas sem nunca precisar informar o código atual —
  bastava abrir Configurações (nada protege esse acesso) e digitar um
  código novo duas vezes para assumir o controle das conversas trancadas
  de outra pessoa, sem nunca ter sabido o código original.
- Agora, sempre que já existir um código configurado, trocar o código
  exige informar o código atual primeiro (verificado contra o hash salvo,
  nunca em texto puro). A primeira configuração (nenhum código definido
  ainda) continua sem exigir nada, como antes.
- **Recuperação de código esquecido**: como consequência do fechamento
  dessa brecha, esqueceu o código não é mais um "sem saída, mas também
  não é reversível às escondidas": desconectar a conta (Arquivo >
  Desconectar) e parear novamente — a única forma de recuperar a
  funcionalidade — apaga permanentemente todas as mensagens e mídias do
  WinZapp desta conta (a wipe que esse fluxo já fazia continua igual),
  e agora também limpa o código salvo, deixando a conta pronta para
  configurar um código novo. Conversas trancadas pelo próprio celular
  (`isLocked`) não são afetadas por nada disso — seguem controladas só
  pelo celular, e voltam a aparecer como trancadas no WinZapp assim que
  a conta ressincronizar, exatamente como chegam do WhatsApp.

### Correções (sincronização)
- **"Fica sincronizando pra sempre" num pareamento novo**: investigando um
  caso real, achamos que uma única leitura de "sessão desconectada" durante
  a espera do histórico recente (`wait_for_restarted_history_sync`) —
  causada por uma instabilidade passageira de conexão do lado do
  WhatsApp Web/wa-js, a mesma classe de bug já vista em Privacidade e
  Dados da mensagem — bastava pra abortar aquela rodada de sincronização
  inteira; o verificador de conexão então tentava tudo de novo do zero
  segundos depois, reiniciando o prazo de 10 minutos indefinidamente. Só
  mensagens novas chegando ao vivo davam a impressão de progresso; o
  histórico nunca era buscado. Agora é preciso confirmar "sessão foi
  embora" em duas leituras seguidas antes de desistir — uma instabilidade
  passageira já não derruba a rodada inteira.
- **Rede de segurança**: independente da causa, se uma sincronização
  completa (pareamento novo, ou F5) não terminar em cerca de 2 minutos, o
  WinZapp agora avisa por voz (só falado, sem alterar nada visualmente)
  que dá pra pressionar F5 pra atualizar a lista manualmente; se mesmo
  assim não terminar em mais um minuto, o próprio WinZapp faz isso
  automaticamente, uma única vez por travamento. Some sozinha assim que a
  sincronização realmente termina.

## v1.1.0.0 — base original (upstream, sem modificações)

Ponto de partida: o WinZapp original, clonado direto do repositório
público de gabrielhhaber, antes de qualquer modificação nossa.

## v1.1.0.3 — mensagens trancadas e confirmação de leitura em tempo real

### Novidades
- **Mensagens trancadas**: retomada a ideia abandonada na v1.1.0.1.
  Investigação mais profunda (com acesso ao app rodando ao vivo) revelou
  que o WhatsApp já sincroniza o estado de conversa trancada do celular
  num campo (`isLocked`) que o WPPConnect já retornava — algo que não
  tinha ficado claro só lendo o código-fonte das bibliotecas. Com isso:
  - Trancamento próprio do WinZapp: esconde uma conversa da lista
    principal, revelada digitando um código no campo de busca (mesmo
    comportamento do WhatsApp oficial).
  - Reconhece também as conversas trancadas de verdade pelo celular,
    escondendo-as igualmente — mas sem oferecer "destrancar" nessas, já
    que só o celular pode fazer isso.
  - Nova aba "Privacidade" em Configurações para definir/trocar o código.
  - Notificações e contador de não lidas não revelam remetente/texto de
    conversas trancadas.
  - O código é guardado como hash salgado (SHA-256), nunca em texto
    puro — o app só precisa confirmar o código digitado, nunca recuperá-lo.
- **Confirmação de leitura em tempo real**: ao abrir os detalhes de uma
  mensagem enviada, o WinZapp agora consulta o WhatsApp diretamente para
  saber quando foi entregue/lida/ouvida, em vez de depender só do que foi
  capturado localmente enquanto o app estava aberto.

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
- "Mensagens trancadas": inicialmente marcado como abandonado aqui, por
  concluirmos (via leitura estática do código) que o WPPConnect não
  expunha o estado de conversa trancada do celular. Essa conclusão estava
  incompleta — ver v1.1.0.3, onde a funcionalidade foi retomada e
  implementada.
- Integração com a API do Be My Eyes: não existe API pública pra
  terceiros: a empresa absorve o custo do provedor de IA por trás; sem
  isso, cada pessoa precisa da própria chave (como já fazemos com o
  Gemini).
- Função de "Reiniciar conexão do WhatsApp" pelo menu Arquivo: chegou a
  ser implementada, mas removida por falta de utilidade prática percebida
  no uso real.
