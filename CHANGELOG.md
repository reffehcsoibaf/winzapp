# Changelog — WinZapp (fork reffehcsoibaf)

Registro das modificações feitas sobre o WinZapp original
(gabrielhhaber/WinZapp_Python), a partir da versão em que começamos a
mexer no projeto.

## v2026.10.8.0 — TeleZapp: novo nome, versão por data e atualização do WPPConnect mais rápida

### Novidades
- O projeto passa a se chamar **TeleZapp** (fork do WinZapp, de Gabriel Haberkamp, que segue sendo creditado em Sobre e no README). Só muda o que a pessoa vê e ouve: títulos de janela, bandeja, notificações, mensagens, guia de uso, changelogs, README e propriedades do `.exe` (Nome do produto, Descrição, Empresa). `client/branding.py` guarda o nome em um lugar só e continua reconhecendo "WinZapp" onde o nome é comparado (conta salva com esse nome, janela de uma cópia que ainda não atualizou).
- Os **nomes técnicos ficam como estavam nesta versão**, de propósito, para quem está na 1.1.5.2 receber a atualização pelo atualizador de sempre: o executável `WinZapp.exe` e o `WinZapp.zip` (o atualizador antigo reabre o programa pelo nome do executável e procura o ZIP por esse nome), a linha `# winzapp-version:` do `SHA256SUMS.txt` (o atualizador antigo exige), a chave AppUserModelID, o valor de início automático, os nomes de mutex/IPC, a pasta de dados e o instalador. A troca desses nomes fica para uma versão seguinte, com migração.
- As versões passam a ser numeradas por data, `ano.mês.dia.N` (o último número só sobe se houver mais de uma versão no mesmo dia). O formato de quatro números é mantido porque o atualizador das versões já instaladas só entende quatro números; 2026 é maior que 1, então a ordem continua correta. A numeração antiga (até 1.1.5.2) não é alterada.

### Melhorias e correções (WPPConnect)

### Melhorias
- A atualização do servidor WPPConnect (e o "Forçar reinstalação") deixa de baixar o Chrome inteiro toda vez: a pasta `api/.cache`, onde o navegador fica, agora sobrevive à limpeza que a atualização faz (`_KEEP_RUNTIME` em `ui/dialogs/api_setup.py`), e o passo `puppeteer browsers install` encontra a versão já instalada e pula o download (se a versão nova precisar de outro Chrome, baixa só esse). Para isso ser seguro: antes do passo, qualquer build incompleto (sem `icudtl.dat`, sem executável) é removido, porque o puppeteer pula o download sempre que a pasta da versão existe, mesmo danificada; depois dele, só o build completo mais novo de cada plataforma fica, para a pasta não acumular um navegador por atualização. Lógica em `core/browser_cache_keep.py`.

### Correções
- Depois de atualizar o servidor WPPConnect e, em seguida, atualizar o próprio WinZapp, o app voltava a oferecer a mesma atualização do WPPConnect. O ZIP da versão traz o `api/package.json` do servidor embutido e o instalador (xcopy) o gravava por cima do instalado, trazendo de volta o número de versão antigo. Agora, antes de gravar o script do instalador, se o `package.json` instalado for estritamente mais novo que o do ZIP, o do ZIP é substituído por uma mescla: parte do instalado (que combina com o `node_modules` que já está no disco), mantém as dependências fixadas pelo WinZapp (`_PATCHED_DEPENDENCY_KEYS`, para a checagem de divergência da biblioteca continuar valendo) e acrescenta qualquer dependência nova do ZIP. O `dist/` continua vindo do ZIP, porque é por ele que as correções próprias do WinZapp chegam. Lógica em `core/update_keeps_server.py`, chamada de `updater._run_batch_installer`.

## v1.1.5.2 — Busca automática de atualizações com atraso

### Melhorias
- A busca automática de atualizações (Configurações > Geral > "Verificar atualizações automaticamente") não roda mais logo ao abrir o WinZapp: espera 10 minutos (a da WPPConnect, 11), para não coincidir com a conexão/sincronização, quando uma atualização ou reinício poderia corromper a sessão. Se ainda houver pareamento ou sincronização em andamento na hora, adia de 5 em 5 minutos (até 3 vezes). Com a caixa desmarcada continua sem buscar nada; "Buscar atualizações" no menu Ajuda continua imediato. Implementado em `MainWindow._startup_update_check` (`main.py`).

## v1.1.5.1 — Descrever (IA) nos status também com o player separado

### Correções
- O botão **Descrever** dos status não aparecia com "Mostrar os status em player separado" (Configurações > Interface) marcado: nesse modo o status abre no `MediaViewerDialog` genérico, e o botão só existia no visualizador embutido do `StatusPanel`. `MediaViewerDialog` ganhou um callback `on_describe` (mesmo padrão de `on_like`/`on_reply`, sem acoplar o diálogo ao `ai_providers`), e `status_panel.py` passou a compartilhar a chamada de IA entre os dois caminhos (`_run_status_ai_describe`). No player separado a mídia que o diálogo já baixou é reaproveitada, sem segundo download.

## v1.1.5.0 — Configurações do WhatsApp de volta (Privacidade + Nome), Descrever em Status, diálogos com OK, guia em 5 idiomas

Contexto: na v1.1.4.1 a janela "Configurações do WhatsApp" estava fora do menu (`_WA_SETTINGS_MENU_ENABLED = False`, desde a v1.1.2.1) porque os setters de privacidade do wa-js quebraram com a migração "Comet" do WhatsApp Web, e o campo Nome estava desabilitado (`_PROFILE_NAME_FIELD_ENABLED = False`) pelo mesmo motivo.

### Novidades
- O botão **Descrever** (IA), já disponível para imagens e vídeos nas mensagens, agora aparece também ao visualizar um status/stories de imagem ou vídeo, ao lado de "Salvar mídia como..." — mesmo pipeline (`ai_providers.describe_visual_media`), mesma janela de resultado navegável com perguntas de acompanhamento. Some automaticamente se nenhum provedor de IA estiver configurado.
- **Edição do nome do perfil** (Configurações do WhatsApp > Perfil), junto com recado e foto. Nunca tinha sido entregue: o campo estava desabilitado desde antes da v1.1.1.0.

### Melhorias
- Os diálogos de subseção de Configurações do WinZapp e a janela de Configurações do WhatsApp agora usam o botão OK em vez de Fechar, salvando ao fechar quando havia algo pendente — mesmo padrão em toda a aplicação.
- A tela "Sem atualizações disponíveis" agora mostra o número da versão instalada.
- O guia de uso (Ajuda > Guia de uso) agora existe também em inglês, espanhol, polonês e português de Portugal (`client/data/help_guide/<idioma>.html`); antes só existia em pt-BR. O trecho de Privacidade do guia em pt-BR também foi atualizado (agora descreve o funcionamento normal).

### Correções
- **Configurações do WhatsApp voltou ao menu e a Privacidade voltou a funcionar**: os seis setters `WPP.privacy.set*` falhavam com `setPrivacyForOneCategory is not a function` (issue upstream `wppconnect-team/wa-js#3658`), corrigido upstream pela PR #3632. O campo Nome falhava com `setPushname is not a function` (`wppconnect-team/wa-js#3659`), corrigido pela PR #3682. As duas correções ainda não estavam numa versão publicada do wa-js (a mais recente no npm é a 4.6.0).
- Removido o botão de depuração temporário da aba Privacidade e o método `debug_find_privacy_module` que ele chamava (era só um localizador de módulos internos; nunca esteve visível ao usuário, já que o menu estava escondido).

## v1.1.4.1 — provedores de IA configuráveis, convites de grupo e nomes de empresas verificadas

Esta versão permite escolher quais provedores de IA usar e em que ordem, e corrige convites de grupo que sumiam, nomes de empresas verificadas e transcrições de áudio que inventavam conteúdo.

### Novidades
- Provedores de IA configuráveis. Em Configurações > Transcrições e Descrições, agora dá para ativar ou desativar cada provedor (Gemini, OpenAI, Claude, Groq, OpenRouter) e escolher a ordem em que o WinZapp tenta cada um, com botões "Mover para cima" e "Mover para baixo". Antes, a única forma de tirar um provedor da lista de tentativas era apagar a chave dele.

### Melhorias
- O canal de atualizações alpha foi removido. A opção "Verificar atualizações alpha" saiu de Configurações > Geral — o WinZapp agora sempre atualiza para a versão estável mais recente.

### Correções
- Convites para entrar em um grupo, compartilhados numa conversa, deixavam de aparecer: a mensagem não gerava linha na conversa, não contava como não lida e não disparava notificação, como se nunca tivesse chegado. Agora aparece normalmente.
- Contas comerciais verificadas do WhatsApp (bancos, aplicativos de pagamento, concessionárias — como "99 Pay" ou "Verisure Brasil") apareciam na lista de conversas só com o número de telefone, sem nome. O WinZapp agora usa o nome verificado dessas contas quando não há nome nem apelido definido.
- A transcrição de áudio pelo Gemini às vezes completava trechos pouco claros com um palpite, em vez de admitir que não deu para entender. Agora ela é mais literal e, quando não consegue identificar um trecho, escreve "[inaudível]" em vez de inventar.

## v1.1.3.0 — mais provedores de IA (OpenAI, Claude, Groq e OpenRouter)

Esta versão traz mais provedores de IA para as transcrições e descrições.

### Novidades
- Mais provedores de IA. Além do Gemini, agora você pode usar OpenAI, Claude, Groq e OpenRouter para transcrever áudios e descrever imagens, figurinhas e PDFs. Cole a chave de quantos quiser em Configurações > Transcrições e Descrições: o WinZapp tenta um por vez, na ordem Gemini, OpenAI, Claude, Groq e OpenRouter, e só avisa que falhou se todos os configurados falharem. Nem todos fazem tudo: vídeo só o Gemini descreve; áudio só Gemini, OpenAI e Groq transcrevem; PDF todos leem, exceto a Groq. A Groq tem plano gratuito e a OpenRouter dá acesso a muitos modelos, inclusive gratuitos.

## v1.1.2.2 — ordem dos botões de IA e das versões em "Quais as novidades?"

Esta versão ajusta a ordem de dois botões e corrige a ordem das versões na tela "Quais as novidades?".

### Correções
- Ao dar Tab numa mensagem de imagem, vídeo ou PDF, o primeiro botão agora é o de Descrever/Transcrever (IA) — antes ele vinha depois de Abrir, Salvar e Baixar. Áudio já funcionava assim, por ser o único botão daquele tipo de mensagem.
- A tela "Quais as novidades?" sempre mostrou as versões da mais recente pra mais antiga, exceto por um trecho antigo do changelog (das versões 1.1.0.0 a 1.1.0.3) que ficou gravado na ordem contrária — quem atualizasse cruzando essas versões via as novidades fora de ordem. Corrigido.

## v1.1.2.1 — correção de segurança: troca do código de conversas trancadas

### Melhorias
- O guia de uso agora abre numa janela do próprio WinZapp (Edge/WebView2), em vez do navegador — mesma página, com menu lateral, busca e modo escuro. Sem o WebView2 instalado, abre no navegador como antes.
- Na tela de atualização disponível, o botão "Quais as novidades?" agora aparece sempre e mostra as novidades da versão que será instalada (antes vinha da versão já instalada, então podia mostrar novidades antigas ou nenhuma).

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

## v1.1.2.0 — figurinhas por IA, guia de uso, backup, limpeza de mídia e edição de perfil

Esta versão reúne tudo o que foi feito desde a fusão com a versão 1.1.1.0 do criador original: figurinhas transcritas por IA, um guia de uso dentro do próprio programa, backup e restauração de conversas, uma ferramenta de limpeza de mídia, edição de recado e foto de perfil, e uma lista de correções — entre elas, as mensagens de lista de opções de empresas que chegavam vazias ao WinZapp.

### Novidades
- Transcrição de figurinhas. A mesma descrição por IA que já existia para imagens agora também funciona em figurinhas, com um interruptor próprio em Configurações > Conversas > Transcrições e Descrições.
- Botão de IA (Transcrever/Descrever) ao lado de Abrir e Salvar. Áudio, imagem, figurinha, vídeo e PDF ganham esse botão no mesmo lugar dos demais botões de ação da mensagem — antes ele só existia no menu de contexto, e o áudio não tinha nenhum botão de ação até agora.
- Dados da mensagem em grupos, participante por participante. Os "Dados da mensagem" de uma mensagem de grupo agora mostram quem recebeu, leu e reproduziu, agrupados pela etapa mais avançada alcançada, em vez de só o total agregado.
- Busca na aba Conversas Arquivadas, igual à que já existia na lista principal.
- Guia de uso do WinZapp dentro do programa, acessível pelo menu Ajuda e também pela tela de pareamento.
- Mais opções de reação às mensagens. Além das 12 reações rápidas, um botão "Mais emojis…" abre o mesmo seletor completo, com busca, usado ao escrever uma mensagem.
- Backup e restauração de conversas. Um único arquivo (.wzbackup) guarda as conversas, mídias e configurações que você escolher, com senha opcional; restaurar sempre mescla com o que já existe, nunca sobrescreve.
- Ferramenta de limpeza de mídia em Configurações > Armazenamento: filtra por conversa, tipo de mídia e tamanho mínimo, mostra um resumo antes de apagar qualquer coisa, e só remove arquivos já baixados — nunca as mensagens.
- Edição do recado e da foto de perfil direto no WinZapp, sem precisar abrir o WhatsApp no celular.
- As mensagens de lista de opções de empresas (aqueles menus de "escolha uma opção" enviados pelo WhatsApp Business) às vezes chegavam vazias, sem nenhuma opção para escolher. O WinZapp agora busca o conteúdo direto no WhatsApp Web quando isso acontece — tanto ao receber a mensagem quanto ao navegar até ela pelo teclado — e volta a mostrar as opções normalmente, inclusive em mensagens que já tinham chegado vazias antes.

### Melhorias
- Configurações reorganizadas em menos abas: uma aba Conversas reúne os botões de Conversas bloqueadas por senha, Transcrições e Descrições, Reprodução de áudio e Chamadas; uma aba Sons reúne os ajustes de áudio e os sons de eventos.
- "Ver dados do contato" agora mostra o cartão inteiro — aniversário, empresa, telefones, e-mails e endereços com rótulo, sites e redes sociais — e não só nome e telefone.
- O item "Escolher conta…" do menu Contas só aparece quando há 10 ou mais contas pareadas; com menos, os atalhos diretos (Ctrl+Alt+1 a 9) já bastam.
- As atualizações automáticas agora verificam a assinatura do instalador antes de aplicá-lo.

### Correções
- O indicador de download de mídia ("processadas X de Y") inflava o total em contas com muito histórico e nunca parecia terminar. Agora conta só o que realmente vai ser baixado.
- As conversas de contatos bloqueados ficam realmente ocultas da lista e de Arquivadas — antes só recebiam um aviso "(bloqueado)" e continuavam aparecendo.
- A conexão parava de funcionar com frequência logo depois de o próprio WinZapp se atualizar, pedindo para parear de novo. Agora a atualização espera a sessão se desconectar de verdade antes de fechar o programa.
- Descrever uma foto que tinha legenda mas nenhum nome de arquivo próprio podia falhar.
- O aviso falado de que "o envio pode não funcionar" disparava por falhas em recursos de Status, mesmo quando enviar texto e mídia funcionava normalmente. Agora só avisa quando o essencial (texto ou mídia) falha de verdade.
- Contatos compartilhados exportados de iPhone/Mac com mais de um número às vezes não eram lidos corretamente.

## v1.1.1.0 — sessão sempre conectada: recuperação do perfil do navegador

Esta versão é sobre manter a sua conta conectada. O WinZapp passou a guardar uma cópia de segurança do perfil do navegador — que é onde a sua conexão com o WhatsApp realmente fica guardada — e a restaurá-la sozinho quando ela deixa de ser aceita, avisando o que aconteceu. Junto vieram as correções das situações que quebravam a sessão e faziam o programa pedir para parear de novo: desligar o computador, suspender e retomar, e o próprio programa reiniciando a conexão. Também chegaram a verificação ortográfica no campo de mensagem e as ações sobre links.

### Novidades
- Recuperação automática do perfil do navegador. A sua conexão com o WhatsApp fica guardada no perfil do navegador que o WinZapp usa por baixo, e quando esse perfil deixava de ser aceito só restava parear de novo. Agora o WinZapp guarda uma cópia de segurança dele, mantém também a cópia anterior, e restaura sozinho quando percebe que a conexão foi recusada — dizendo em voz alta que restaurou e que está reconectando. Ele nunca oferece de volta uma cópia que o WhatsApp já recusou, e quando não há nenhuma cópia aproveitável ele avisa claramente, em vez de deixar você offline sem explicação.
- Verificação ortográfica no campo de mensagem. Em Configurações você escolhe entre seguir a configuração de ortografia do próprio Windows (padrão), sempre ativada ou sempre desativada. Há também um som próprio para erro de ortografia, que pode ser configurado junto com os demais sons.
- Ações sobre links nas mensagens. Quando a mensagem tem links, o menu de contexto passa a oferecer Abrir link e Copiar link para o link que está em foco, e Ctrl+C copia esse link em vez da mensagem inteira.
- Aviso quando o navegador interno está incompleto. Se o navegador que o WinZapp usa para conectar ao WhatsApp não conseguir iniciar — em geral porque um antivírus removeu parte dele — o programa diz isso com todas as letras e explica o que fazer, em vez de parecer que o problema é o WhatsApp.
- Aviso de envio não confirmado. Quando o WhatsApp aceita uma mensagem mas não confirma a entrega, o WinZapp avisa para você conferir a conversa antes de reenviar, em vez de arriscar entregar a mesma mensagem duas vezes.

### Melhorias
- Iniciar junto com o Windows ficou muito mais rápido de conectar. O programa esperava a conexão só depois de já ter tentado usá-la, e passava um bom tempo mostrando "desconectado do WhatsApp" sem motivo. Agora ele espera tudo estar pronto antes de aparecer na bandeja.
- A lista de mensagens não é mais reconstruída inteira a cada minuto. Só as linhas que realmente mudaram são reescritas, então o leitor de tela deixa de reler a mensagem em que você está e o som de seleção não toca mais sozinho.
- Menos notificações de sincronização no seu celular. O WinZapp só pede histórico antigo ao telefone para conversas que você abriu, um pedido de cada vez, e para de pedir de vez quando a conversa já respondeu que não tem mais nada.
- Conversas que a sincronização tinha parado de olhar voltam a ser verificadas sozinhas, sem depender de você atualizar com F5.
- Em várias contas ao mesmo tempo, a atualização do WinZapp abre uma janela só, em vez de uma por conta.
- Áudio: o WinZapp pergunta ao microfone qual é a taxa de amostragem dele antes de tentar as taxas fixas, e a saída de som se recupera sozinha quando o dispositivo padrão muda ou é desconectado.
- Reações que chegaram enquanto a conversa estava fechada aparecem ao abri-la.
- Quebras de linha na caixa de mensagem agora podem ser navegadas normalmente pelo leitor de tela.
- Conexão com o WhatsApp atualizada (WPPConnect 2.10.21), incluindo correções de segurança, e o WinZapp percebe sozinho quando essa conexão ficou fora do padrão e precisa ser reinstalada.

### Correções
- Desligar o computador não quebra mais a sessão. O WinZapp fechava a conexão com o WhatsApp tarde demais no desligamento do Windows, quando o processo que a mantém já tinha sido encerrado — e o perfil voltava inutilizável, pedindo pareamento na próxima vez. Agora ele fecha tudo enquanto o Windows ainda está perguntando se pode desligar.
- Suspender o computador não quebra mais a sessão. Ao retomar, o WinZapp reiniciava a conexão sem esperar o navegador terminar de gravar o que tinha em mãos, e isso bastava para perder o pareamento. Agora ele espera.
- Responder a um status voltou a funcionar. A resposta falhava dizendo que não foi possível enviar.
- Uma falha de envio ambígua não gera mais mensagens duplicadas: quando não dá para saber se o WhatsApp recebeu, o WinZapp não reenvia por conta própria.
- Baixar documentos grandes voltou a ser possível. Arquivos de algumas centenas de megabytes anunciavam "baixando" e não produziam nada.
- O indicador de progresso de envio e download agora mostra a transferência que realmente está acontecendo, e não continua girando numa mensagem que já terminou nem aparece na linha errada.
- Cancelar ou fechar a tela de pareamento não apaga mais as suas conversas, e uma falha momentânea de autenticação ao abrir o programa também não. O histórico só é apagado quando outro número de telefone é realmente conectado — e nesse caso o WinZapp avisa.
- O QR-code só é anunciado quando está realmente na tela. O WinZapp dizia "o QR-code foi atualizado" antes de qualquer código ter sido exibido, o que fazia parecer que o código só aparecia na segunda tentativa. Agora a tela de pareamento avisa que o código está sendo gerado, anuncia quando ele aparece de fato, e diz quando não foi possível gerá-lo ou quando o código de pareamento expirou — em vez de ficar em silêncio ou anunciar uma atualização que não houve.
- Contagem de não lidas: conversas não voltam mais a aparecer como não lidas sem que tenha chegado mensagem nova.
- O caractere fantasma que aparecia no campo de mensagem ao voltar de outro programa com o NVDA ligado não aparece mais.
- Copiar uma mensagem de voz passou a funcionar.
- Conversas que apareciam com o número em vez do nome agora são resolvidas.
- Trocar de conta apaga corretamente as mídias da conta anterior, que antes podiam ficar para trás no computador.
- Mensagens de lista de opções de empresas (aqueles menus de "escolha uma opção" que o WhatsApp Business envia) às vezes chegavam vazias, sem nenhuma opção para selecionar. O WinZapp agora busca o conteúdo direto do WhatsApp Web quando isso acontece — tanto ao receber a mensagem quanto ao navegar até ela pelo teclado — e volta a mostrar as opções normalmente, mesmo em mensagens que já tinham chegado vazias antes.

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

## v1.1.0.0 — base original (upstream, sem modificações)

Ponto de partida: o WinZapp original, clonado direto do repositório
público de gabrielhhaber, antes de qualquer modificação nossa.
