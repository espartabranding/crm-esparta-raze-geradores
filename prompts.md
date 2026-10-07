# Prompts da Raze Geradores

Prompts prontos para usar em qualquer conversa com o Claude. Cada um carrega o contexto de que precisa. Troque só o que está entre chaves.

## 1. Abordagem para uma conta nova

```
Você vai escrever a abordagem de primeira ligação para uma conta.

Quem vende: Raze Geradores (Raze Engenharia), do Rio de Janeiro. Não vende nem aluga gerador: faz a engenharia de prontidão do sistema de energia de emergência (grupo gerador, quadro de transferência, subestação e nobreak) de condomínios, unidades de saúde, indústria e cadeia fria e comércio, na cidade do Rio e região metropolitana. Venda consultiva.
O método tem sete etapas: abrangência, inspeção do conjunto, banco de cargas, partida cronometrada, autonomia medida, tendência registrada e ART com laudos.
Objetivo da ligação: combinar o Diagnóstico de prontidão, serviço técnico com preço definido e abatido no contrato caso ele seja fechado.
Plano B: nome e canal direto de quem responde pelo gerador, a data do próximo vencimento (autovistoria, inspeção, assembleia) e permissão para enviar a proposta.

Só pode oferecer o que está no portfólio: Diagnóstico de prontidão; ensaios de desempenho sob carga; manutenção preventiva contratada; manutenção corretiva e retrofit de QTA; laudo de autovistoria predial; conformidade RDC 50 para estabelecimentos de saúde; Prontuário de Instalações Elétricas (NR-10); relatório técnico e histórico de tendência; SLA de emergência e dossiê de assembleia.
Planos: Prontidão Residencial (condomínios), Hospitalar (saúde), Industrial (indústria e cadeia fria) e Comercial (comércio, sob demanda).

Limites que não se quebram:
- Não prometa transferência de risco ou de responsabilidade legal, nem resultado absoluto ("nunca vai parar"). ART e laudo são prova de diligência.
- Não cite preço, prazo de SLA, cliente atendido nem concorrente: nada disso está confirmado.
- Não use "custo acessível", "orçamento gratuito" nem "agende uma visita".
- Norma só pelo que ela diz. No Rio é Certificado de Aprovação do CBMERJ, não "AVCB"; a autovistoria na capital é de 5 em 5 anos. Na dúvida, não cite norma.
- Falha do cliente (apagão, autuação) é sinal de momento, nunca abertura da conversa.

Conta: {empresa}, {segmento}, {bairro e cidade}. O que se sabe: {porte, sinal, site}.
Telefone é de {central, portaria ou direto}.

Escreva, em português do Brasil e no jeito que se fala ao telefone no Rio:
1. A fala para a recepção ou a portaria, se o telefone não for direto: uma pergunta pedindo quem responde pelo gerador e pela manutenção predial.
2. A abertura com quem decide, em até 10 segundos: cumprimento, nome, quem é e de onde, e o anúncio de que há uma proposta objetiva.
3. A proposta, em até três frases: a situação típica do segmento; "A Raze propõe..."; uma pergunta aberta.
4. Três perguntas de qualificação, na ordem (a primeira: se há registro do último ensaio do gerador feito sob carga).
5. A oferta: o Diagnóstico de prontidão como entrada e o plano do segmento, uma frase cada.
6. As duas objeções mais prováveis nesta conta, com resposta.
7. O pedido final e o plano B, com data.

Registro corporativo, fluido e propositivo: sem "a gente", "pra", "né", diminutivo ou gíria, e sem pedir desculpa por ligar. O pedido final começa por "Proponho o seguinte:". Nada com cara de tradução do inglês ("você não esperava minha ligação", "talvez você possa me ajudar").
Se faltar informação para alguma parte, diga o que falta em vez de inventar.
```

## 2. Resumo pós-ligação para o CRM

```
A partir da transcrição abaixo, de uma ligação de prospecção da Raze Geradores (engenharia de prontidão de sistemas de energia de emergência, Rio de Janeiro), preencha os campos do CRM. Use só o que foi dito; onde não houver informação, escreva "não informado".

Transcrição: {transcrição}

Campos:
- Falou com (nome e cargo):
- Quem responde pelo gerador e pela manutenção (nome, cargo, canal direto):
- O sistema de emergência (gerador, QTA, subestação, nobreak; potência, se dita):
- Quem mantém hoje e como (contrato, chamado avulso, equipe própria):
- Último ensaio sob carga e último laudo (datas, se ditas):
- Próximo vencimento (autovistoria, inspeção, assembleia, auditoria):
- Objeções ditas, com as palavras do cliente:
- Próximo passo combinado e data:
- Qualificação do Callix:
- Etapa do kanban (tentar, retornar, canal, apresentar, aguardando, ganha, encerrada):
- Linha pronta para o tentativas.json (conta, quando, qualificacao, nota, etapa, conversou):
```

## 3. Avaliação de uma ligação

```
Avalie a ligação abaixo para ajudar o agente a melhorar.

Contexto: a Raze Geradores, do Rio de Janeiro, faz a engenharia de prontidão do sistema de energia de emergência: ensaio sob carga, partida cronometrada, autonomia medida e laudo com ART. O objetivo da ligação era combinar o Diagnóstico de prontidão ou, com a recepção, sair com o nome e o canal de quem responde pelo gerador.

Transcrição: {transcrição}

Responda:
1. O objetivo foi atingido? Qual foi o próximo passo combinado, com data?
2. Três acertos, com a fala do agente que os mostra.
3. Três pontos a melhorar, cada um com a fala como foi dita e como poderia ter sido dita, em registro corporativo e natural.
4. O agente fez o cliente descrever a situação com as palavras dele antes de falar da solução?
5. Algum limite foi quebrado (promessa de transferência de risco, resultado garantido, preço ou prazo não confirmado, norma citada errada, abertura pela falha do cliente)? Cite a fala.
6. Nota de 0 a 100 e a justificativa em duas linhas.
```
