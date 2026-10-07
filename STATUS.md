# Status da campanha Raze Geradores

Criado em 07/10/2026, a partir da estrutura do `CRM_Esparta_SempreTech`. Ainda não publicado e sem nenhum contato registrado.

## O que existe

- **Painel:** só o Kanban e os contatos. O Kanban tem uma coluna por etapa (não abordada, localizar o responsável, retorno combinado, abordar por canais de apoio, apresentar a proposta personalizada, proposta enviada, proposta aceita, encerrada sem negócio), com o campo "Evolução até esta etapa" em cada cartão. A lista de leads abre a ficha de cada conta, com o contato, os dados da empresa e o histórico.
- **Carteira:** 265 contas do Rio de Janeiro e região metropolitana, montadas por `montar_carteira.py` a partir das listas do `Painel_Raze`: 87 condomínios, 59 supermercados e cadeia fria, 40 administradoras de condomínios, 40 de saúde, 32 postos de combustível e 7 de comércio e centros comerciais. Ordem: 15 na semana 1, 15 na semana 2, 9 em "validar dados antes" e 226 na base.
- **Playbook e catálogo:** `playbook.json` e `catalogo.json` estão escritos para a Raze (seis segmentos, sete soluções, objeções e qualificações), mas as telas Playbook, Soluções, Inteligência, Tarefas e Segmentação e a aba Ligação estão desligadas. Não há propostas visuais.

## Limitações da carteira

- Nenhuma conta tem pesquisa individual, decisor identificado nem sinal de compra: os dados vêm do Google Maps, da Receita e do CNES.
- Só 16 dos 87 condomínios têm o número de domicílios; nos demais o porte vem das avaliações do Google.
- 14 contas (redes de supermercado e postos) só têm 0800.
- Entre as 40 administradoras há empresas que não são administradoras (SN Shopping, Jaguaré/Allos, Basileia SPE, CBRE, C 37/Calper).
- "ION Intelligent Center" (semana 1) e "Office Tower" (semana 2) têm nome de prédio comercial; conferir antes de ligar.
- Telefones da saúde vêm do CNES sem padrão; os de DDD presumido estão marcados no campo de sinal.

## Pendências

- Publicar: criar o repositório no GitHub e ligar o GitHub Pages (o painel já sai em `docs/`).
- Criar a campanha da Raze no Callix e preencher `.env` (token e número da campanha).
- Confirmar com a Raze os 26 itens de `a_confirmar` do playbook, a começar pelo preço do Diagnóstico de prontidão, pelos municípios atendidos e pelo nome do responsável técnico.
- Logotipo da Raze em branco para a barra lateral (hoje o nome vai escrito).

## Como atualizar

1. Registrar o resultado de cada contato em `tentativas.json` (conta, quando, nota, qualificacao, etapa, conversou). Etapas mudadas no kanban e textos escritos em "Evolução até esta etapa" ficam só no navegador de quem mexeu.
2. `uv run python painel.py` regenera o painel e o relatório do cliente em `docs/`; com o Callix configurado, `uv run python main.py` sincroniza antes.
