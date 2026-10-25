# Prints From Internet — Content Scout

MVP de recolha para revisão humana. Nunca publica no Instagram, não descarrega imagens e não replica ficheiros de terceiros. A galeria mostra pré-visualizações remotas e liga sempre à publicação Reddit e ao media original.

## Preparação

1. Cria um repositório GitHub privado e envia o conteúdo desta pasta.
2. Na área de aplicações Reddit, cria uma aplicação para este bot e obtém as credenciais OAuth.
3. Em **Settings → Secrets and variables → Actions**, cria os Secrets `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `TELEGRAM_TOKEN` e `TELEGRAM_ID`.
4. Em **Variables**, cria `REDDIT_USER_AGENT`, por exemplo `github:prints-from-internet:v1.0 (by /u/teu_utilizador)`, e `PFI_GALLERY_URL` depois de ativares GitHub Pages.
5. Em **Settings → Pages**, publica a pasta `/docs` a partir do ramo principal. Mantém o repositório privado se a fila de revisão não deve ser pública.
6. Executa **PFI content scout → Run workflow** uma vez para testar. Depois corre diariamente às 09:15 UTC.

## O que rever

Cada candidato permanece no máximo 48 horas. O bot consulta de novo a Reddit API antes de manter um candidato; se o post deixar de estar disponível, elimina os respetivos dados locais. Antes de usar qualquer imagem, confirma direitos, licença, crédito e autorização na fonte.

## Ajustar as fontes

Edita `config/sources.json`. Começa com poucas comunidades e só aceita domínios de media explicitamente listados. Não adiciones fontes que não tenhas autorização para consultar ou reutilizar.

## Alertas Telegram

O Telegram recebe apenas uma mensagem com a contagem e a ligação para a galeria. Não recebe nem arquiva imagens. Se removeres `TELEGRAM_TOKEN` e `TELEGRAM_ID`, a recolha e a galeria continuam a funcionar sem alertas.
