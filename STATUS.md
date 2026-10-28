# Status da campanha Raze Geradores

Carteira com 609 contas: 80 em andamento e 529 não abordadas (posição de 28/10, com a prospecção de 27/10). Publicado no GitHub Pages, com o relatório do cliente também entregue em arquivo HTML.

## Onde ver

- Relatório do cliente: https://espartabranding.github.io/crm-esparta-raze-geradores/cliente/
- Painel do SDR: https://espartabranding.github.io/crm-esparta-raze-geradores/

Os dois são abertos a quem tem o link. O relatório do cliente é só leitura: não deixa mover cartão nem editar a evolução. O mesmo relatório pode ser entregue em arquivo: é o `docs/cliente/index.html`, que abre sozinho no navegador.

## Campanha: contatos de 05/10

40 contas da planilha `Raze-prospeccao-RJ-consolidado-07-10.xlsx`, ligadas por Rodrigo (Esparta) em nome da Raze. Os contatos entram no CRM com a data de segunda-feira, 05/10, e o painel não mostra a data em que foi gerado. Entram no CRM por `importar_planilha.py`, com identificador `x1` a `x40`.

| Etapa no kanban | Contas |
|---|---|
| Retorno combinado | 5 (4 com retorno agendado e 1 aguardando retorno) |
| Apresentar a proposta personalizada | 14 (13 com contato feito, identificação do responsável e apresentação da empresa enviada; e a DataCorpore, com contato indicado) |
| Localizar o responsável | 14 (3 não atenderam e 11 sem resultado registrado) |
| Encerrada sem negócio | 3 (retiradas: Le Buffet, PACLIMED, Oncomed) |
| Não abordada | 4 (Niemeyer 101 com telefone inválido; NIG Barra; Policlínica de Botafogo; laboratório da UFRJ, com recomendação de retirar) |

Nenhuma proposta foi enviada ainda: o que a planilha chama de "Proposta enviada" foi o contato com identificação do responsável e a apresentação da empresa.

Próximos passos por data: 17 contas na quinta, 08/10; 15 na sexta, 09/10; 1 na terça, 13/10 (Centro Médico Pró-Cardíaco). O que a planilha marcava para o próprio dia foi para 08/10; "ligar novamente" sem data foi para 08/10 nas contas de prioridade A e para 09/10 nas de prioridade B.

Seis contas estão marcadas como de grande porte ou de rede, a validar com a Raze: Centro Empresarial Rio, Torre Almirante, Shopping Downtown, RB1, Sheraton e Croma Oncologia; o Centro Médico Pró-Cardíaco pertence a grupo hospitalar.

## Prospecção de 26/10

32 contatos registrados em `tentativas.json`, com relatório em `analises/`:

- **E-mail (7):** segundo contato com o Diagnóstico de Prontidão para Centro Empresarial Rio, Torre Almirante, Shopping Downtown, Viña del Mar, La Reverence, Studio 188 e AMI (x1, x2, x3, x5, x6, x8, x9). Retorno em 28/10. Nefroclin e as duas Placi ficam para depois.
- **WhatsApp Lote 01 (11):** condomínios w1 a w11, 10 entregues e 1 só enviado (Ed. Cidade de Veneza, um tique). Barra Village Lakes e Everglades podem ser número de corretor ou imobiliária. Ainda sem resposta registrada.
- **LinkedIn (14 convites):** em São Lucas (r13), APSA (r19, dois convites) e 11 contas novas (l1 a l11).

## Prospecção de 27/10

20 contatos registrados em `tentativas.json`, com os dois relatórios do dia em `analises/` (`Relatorio_Prospeccao_Raze_27-10-2026.pdf` e `Raze_Convites_LinkedIn_2026-10-27.pdf`):

- **WhatsApp Lote 02 (10 condomínios, w12 a w21):** 5 enviadas pelo WhatsApp Business da Raze, com o Diagnóstico de Prontidão e o pedido de indicação do responsável pelo gerador (no Angra dos Reis, também o plano de manutenção 24h). 4 entregues (Angra dos Reis – Bloco 8, Barra Soleil Résidence, Reserva do Rio Grande e The Claridge), com follow-up em 29/10; o Jardim das Rosas ficou em um tique. Os outros 5 números não têm WhatsApp (Alvor, Pero Lopes de Souza, Água Marinha, Barodin e Julimar) e vão para ligação. No Barra Soleil, o nome no Google não bate com a razão social do CNPJ (Le Byblos).
- **LinkedIn (10 convites):** Estasa (r16, Anna Carolina Chazan) e 9 contas novas (l12 a l20): PCA, José Orlando Ribeiro (síndico profissional), Union Suítes, Super Centro de Exames, HU Clementino Fraga Filho (UFRJ), Hapvida NotreDame, Seara (Duque de Caxias), Grupo Cataratas e Gilson Pinheiro (Nilópolis). O HU da UFRJ é órgão público, como o laboratório da UFRJ; a Seara de Duque de Caxias pode ser a mesma operação do Swift CD (f127).

A lista de convites de 27/10 tem 45 convites pendentes, 35 deles marcados como enviados antes. Desses 35, só 12 estão no CRM, registrados em 26/10; os outros 23 não. Dois convites registrados em 26/10, Rafael Cavalcanti (Bradesco Seguros, l6) e Denise Barabana (Ancar, l8), não aparecem na lista.

Depois do Lote 02, sobram 20 condomínios com celular: 9 na base `condominios_com_google_raze.csv` (Painel_Raze), 10 já na carteira como não abordados (r68, r80, r91, r98, r99, r101, r108, r113, r229, r233) e o Pontal Oceânico (`lugares_raze.csv`, número possivelmente de imobiliária).

## O que existe

- **Painel:** só o Kanban e os contatos. O Kanban tem uma coluna por etapa (não abordada, localizar o responsável, retorno combinado, abordar por canais de apoio, apresentar a proposta personalizada, proposta enviada, proposta aceita, encerrada sem negócio), com o campo "Evolução até esta etapa" em cada cartão. A lista de leads abre a ficha de cada conta, com o contato, os dados da empresa e o histórico.
- **Carteira:** 568 contas: as 40 da campanha, 263 da lista de indústria e cadeia fria (`incluir_lista.py`, a partir de `leads_cadeia_fria_300_raze.csv`; 37 das 300 linhas não entraram por repetirem telefone, nome ou CNPJ) e 265 da base do Rio de Janeiro e região metropolitana, estas montadas por `montar_carteira.py` a partir das listas do `Painel_Raze`: 87 condomínios, 59 supermercados e cadeia fria, 40 administradoras de condomínios, 40 de saúde, 32 postos de combustível e 7 de comércio e centros comerciais. Ordem: 15 na semana 1, 15 na semana 2, 9 em "validar dados antes" e 226 na base.
- **Celular:** o painel foi ajustado para telas de 390 px e de 820 px (abas da ficha em duas linhas, kanban deslizando coluna a coluna). O teste foi por retrato de tela, não em aparelho.
- **Playbook e catálogo:** `playbook.json` e `catalogo.json` estão escritos para a Raze (seis segmentos, sete soluções, objeções e qualificações), mas as telas Playbook, Soluções, Inteligência, Tarefas e Segmentação e a aba Ligação estão desligadas. Não há propostas visuais.

## Limitações da carteira

- Nenhuma conta tem pesquisa individual, decisor identificado nem sinal de compra: os dados vêm do Google Maps, da Receita e do CNES.
- Só 16 dos 87 condomínios têm o número de domicílios; nos demais o porte vem das avaliações do Google.
- 14 contas (redes de supermercado e postos) só têm 0800.
- Entre as 40 administradoras há empresas que não são administradoras (SN Shopping, Jaguaré/Allos, Basileia SPE, CBRE, C 37/Calper).
- "ION Intelligent Center" (semana 1) e "Office Tower" (semana 2) têm nome de prédio comercial; conferir antes de ligar.
- Telefones da saúde vêm do CNES sem padrão; os de DDD presumido estão marcados no campo de sinal.

## Pendências

- Follow-up em 29/10 nos 4 condomínios do Lote 02 com mensagem entregue; reenviar ao Jardim das Rosas e ao Ed. Cidade de Veneza (Lote 01), ambos em um tique; acompanhar as respostas do Lote 01.
- Ligar para os 5 condomínios do Lote 02 sem WhatsApp (w15 a w18 e w21).
- Registrar os 23 convites no LinkedIn enviados antes de 27/10 que não estão no CRM, e acompanhar os aceites dos 24 registrados.
- Preparar o WhatsApp Lote 03.
- Cobrar os 7 e-mails de 26/10 em 28/10.
- Retornos atrasados de outubro: 17 contas com prazo em 08/10, 8 em 09/10 e o Centro Médico Pró-Cardíaco em 13/10 continuam sem novo registro.
- Validar com a Raze se entram na campanha as contas de grande porte ou de rede (Centro Empresarial Rio, Torre Almirante, Shopping Downtown, RB1, Sheraton, Croma Oncologia e Centro Médico Pró-Cardíaco).
- Decidir a retirada do laboratório da UFRJ (órgão público, contratação por licitação) e achar o telefone real do Niemeyer 101.
- Na lista de cadeia fria, 110 das 263 contas têm o telefone marcado como "a validar" no campo de sinal (celular sem o nono dígito, número de outra UF ou de preenchimento).
- Abrir o painel em um celular para confirmar o toque e a rolagem do kanban.
- Criar a campanha da Raze no Callix e preencher `.env` (token e número da campanha).
- Confirmar com a Raze os 26 itens de `a_confirmar` do playbook, a começar pelo preço do Diagnóstico de prontidão, pelos municípios atendidos e pelo nome do responsável técnico.
- Logotipo da Raze em branco para a barra lateral (hoje o nome vai escrito).

## Como atualizar

1. Com planilha nova: `uv run python importar_planilha.py "caminho.xlsx"`. Com lista nova de leads para prospectar: `uv run python incluir_lista.py "caminho.csv"` (entram como não abordadas). Se a base for refeita com `montar_carteira.py`, rodar os dois de novo depois. Sem planilha, registrar o resultado de cada contato em `tentativas.json` (conta, quando, nota, qualificacao, etapa, conversou). Etapas mudadas no kanban e textos escritos em "Evolução até esta etapa" ficam só no navegador de quem mexeu.
2. `uv run python painel.py` regenera o painel e o relatório do cliente em `docs/`; com o Callix configurado, `uv run python main.py` sincroniza antes.
