# CRM Esparta — Raze Geradores

Mesa de ligação da campanha de prospecção da Raze Geradores (engenharia de prontidão de sistemas de energia de emergência, Rio de Janeiro e região metropolitana): um kanban da campanha e a ficha de contato de cada conta, com os dados das chamadas feitas no Callix.

A estrutura é a mesma do `CRM_Esparta_SempreTech`. O conteúdo da Raze vem do site (razegeradores.com.br) e do projeto `Painel_Raze` (régua de negócio, legislação e listas de prospecção).

## O que faz

- Gera o painel do SDR e o relatório do cliente, com o Kanban (uma coluna por etapa, com a evolução de cada conta) e a lista de leads, cada um com a ficha de contato e o histórico.
- Busca as ligações da campanha no Callix (dados, qualificação e gravação), transcreve e avalia cada conversa.

## Como rodar

1. `uv sync`
2. `uv run python montar_carteira.py` monta `contas.json` a partir das listas do `Painel_Raze` (só quando a lista mudar).
3. `uv run python painel.py` gera o painel em `docs/index.html` e o relatório do cliente em `docs/cliente/index.html`.
4. Depois de criar a campanha no Callix: copie `.env.example` para `.env`, preencha o token e o número da campanha, e use `uv run python main.py` para sincronizar, transcrever, avaliar e regenerar o painel.

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `montar_carteira.py` | Monta a carteira a partir das listas de prospecção |
| `contas.json` | As contas, com fit, aderência e plano de entrada |
| `playbook.json` | Soluções, roteiros por segmento, objeções e qualificações (pronto; as telas que o mostram estão desligadas) |
| `catalogo.json` | Portfólio da Raze (idem) |
| `painel.py`, `painel_modelo.html` | Geração do painel |
| `tentativas.json` | Contatos registrados à mão (conta, quando, nota, qualificacao, etapa, conversou) |
| `analises/` | Pesquisa individual de cada conta, quando houver |
| `main.py`, `callix.py`, `conversa.py`, `transcritor.py` | Sincronização com o Callix, transcrição e avaliação |
| `prompts.md` | Prompts prontos para abordagem, resumo e avaliação |
| `STATUS.md` | Estado da campanha e pendências |

## Dados fora do repositório

`.env` (token) e `data/` (banco, gravações, transcrições e painel local) não são versionados: contêm segredo e dados pessoais.
