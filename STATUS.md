# Status da campanha Raze Geradores

Atualizado em 07/10/2026, 12h, com a planilha de prospecção do dia. Publicado no GitHub Pages em 07/10.

## Onde ver

- Relatório do cliente: https://espartabranding.github.io/crm-esparta-raze-geradores/cliente/
- Painel do SDR: https://espartabranding.github.io/crm-esparta-raze-geradores/

Os dois são abertos a quem tem o link. O relatório do cliente é só leitura: não deixa mover cartão nem editar a evolução. O mesmo relatório pode ser entregue em arquivo: é o `docs/cliente/index.html`, que abre sozinho no navegador.

## Campanha em 07/10

40 contas da planilha `Raze-prospeccao-RJ-consolidado-07-10.xlsx`, ligadas por Rodrigo (Esparta) em nome da Raze. Entram no CRM por `importar_planilha.py`, com identificador `x1` a `x40`.

| Etapa no kanban | Contas |
|---|---|
| Retorno combinado | 5 (4 com retorno agendado e 1 aguardando retorno) |
| Apresentar a proposta personalizada | 14 (13 com contato feito, identificação do responsável e apresentação da empresa enviada; e a DataCorpore, com contato indicado) |
| Localizar o responsável | 14 (3 não atenderam e 11 sem resultado registrado) |
| Encerrada sem negócio | 3 (retiradas: Le Buffet, PACLIMED, Oncomed) |
| Não abordada | 4 (Niemeyer 101 com telefone inválido; NIG Barra; Policlínica de Botafogo; laboratório da UFRJ, com recomendação de retirar) |

Nenhuma proposta foi enviada ainda: o que a planilha chama de "Proposta enviada" foi o contato com identificação do responsável e a apresentação da empresa.

Próximos passos por data: 17 contas na quinta, 08/10; 15 na sexta, 09/10; 1 na terça, 13/10 (Centro Médico Pró-Cardíaco). O que a planilha marcava para a tarde de 07/10 foi para 08/10; "ligar novamente" sem data foi para 08/10 nas contas de prioridade A e para 09/10 nas de prioridade B.

Seis contas estão marcadas como de grande porte ou de rede, a validar com a Raze: Centro Empresarial Rio, Torre Almirante, Shopping Downtown, RB1, Sheraton e Croma Oncologia; o Centro Médico Pró-Cardíaco pertence a grupo hospitalar.

## O que existe

- **Painel:** só o Kanban e os contatos. O Kanban tem uma coluna por etapa (não abordada, localizar o responsável, retorno combinado, abordar por canais de apoio, apresentar a proposta personalizada, proposta enviada, proposta aceita, encerrada sem negócio), com o campo "Evolução até esta etapa" em cada cartão. A lista de leads abre a ficha de cada conta, com o contato, os dados da empresa e o histórico.
- **Carteira:** 568 contas: as 40 da campanha, 263 da lista de indústria e cadeia fria (`incluir_lista.py`, a partir de `leads_cadeia_fria_300_raze.csv`; 37 das 300 linhas não entraram por repetirem telefone, nome ou CNPJ) e 265 da base do Rio de Janeiro e região metropolitana, estas montadas por `montar_carteira.py` a partir das listas do `Painel_Raze`: 87 condomínios, 59 supermercados e cadeia fria, 40 administradoras de condomínios, 40 de saúde, 32 postos de combustível e 7 de comércio e centros comerciais. Ordem: 15 na semana 1, 15 na semana 2, 9 em "validar dados antes" e 226 na base.
- **Playbook e catálogo:** `playbook.json` e `catalogo.json` estão escritos para a Raze (seis segmentos, sete soluções, objeções e qualificações), mas as telas Playbook, Soluções, Inteligência, Tarefas e Segmentação e a aba Ligação estão desligadas. Não há propostas visuais.

## Limitações da carteira

- Nenhuma conta tem pesquisa individual, decisor identificado nem sinal de compra: os dados vêm do Google Maps, da Receita e do CNES.
- Só 16 dos 87 condomínios têm o número de domicílios; nos demais o porte vem das avaliações do Google.
- 14 contas (redes de supermercado e postos) só têm 0800.
- Entre as 40 administradoras há empresas que não são administradoras (SN Shopping, Jaguaré/Allos, Basileia SPE, CBRE, C 37/Calper).
- "ION Intelligent Center" (semana 1) e "Office Tower" (semana 2) têm nome de prédio comercial; conferir antes de ligar.
- Telefones da saúde vêm do CNES sem padrão; os de DDD presumido estão marcados no campo de sinal.

## Pendências

- Criar a campanha da Raze no Callix e preencher `.env` (token e número da campanha).
- Confirmar com a Raze os 26 itens de `a_confirmar` do playbook, a começar pelo preço do Diagnóstico de prontidão, pelos municípios atendidos e pelo nome do responsável técnico.
- Logotipo da Raze em branco para a barra lateral (hoje o nome vai escrito).

## Como atualizar

1. Com planilha nova: `uv run python importar_planilha.py "caminho.xlsx"`. Com lista nova de leads para prospectar: `uv run python incluir_lista.py "caminho.csv"` (entram como não abordadas). Se a base for refeita com `montar_carteira.py`, rodar os dois de novo depois. Sem planilha, registrar o resultado de cada contato em `tentativas.json` (conta, quando, nota, qualificacao, etapa, conversou). Etapas mudadas no kanban e textos escritos em "Evolução até esta etapa" ficam só no navegador de quem mexeu.
2. `uv run python painel.py` regenera o painel e o relatório do cliente em `docs/`; com o Callix configurado, `uv run python main.py` sincroniza antes.
