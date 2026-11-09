# Operação de WhatsApp · Raze Geradores

Ponto fixo da prospecção por WhatsApp. Qualquer sessão nova (WhatsApp Web em aba anônima, outro computador, outra conversa com o Claude) começa aqui e sabe exatamente onde a operação parou.

| Arquivo | O que guarda |
|---|---|
| `estado.json` | A fila inteira da operação: cada conta, situação, número de toques, prazo e próximo passo, mais a última sessão e onde ela parou |
| `diario/AAAA-MM-DD.jsonl` | Tudo o que foi registrado em cada dia (base do relatório diário) |
| `whatsapp.py` | Os comandos abaixo |

## Comandos (na raiz do repositório)

```
python operacao/whatsapp/whatsapp.py status                  # onde parei e o que fazer hoje, na ordem
python operacao/whatsapp/whatsapp.py registrar w12 entregue  # depois de CADA mensagem
python operacao/whatsapp/whatsapp.py registrar w2 respondeu --nota "o que a pessoa disse e o próximo passo"
python operacao/whatsapp/whatsapp.py publicar                # regenera o painel e manda tudo para o GitHub
python operacao/whatsapp/whatsapp.py relatorio               # PDF do dia em analises/
python operacao/whatsapp/whatsapp.py liberar --lote L03      # tira um lote da espera
python operacao/whatsapp/whatsapp.py incluir lote.csv --lote L04
```

Resultados: `enviado`, `entregue`, `1tique`, `sem_whatsapp`, `resposta_automatica`, `respondeu`, `contato_obtido`, `material_enviado`, `followup`, `recusou`, `nao_contatar`, `numero_errado`.

Cada `registrar` grava na hora o `estado.json`, o diário do dia e um registro em `tentativas.json` (o CRM). O painel só muda depois de `publicar`. Contas da fila que ainda não estão no CRM (chave `L03-01` etc.) ganham um id `w` no primeiro registro.

No Windows, o relatório precisa do reportlab: `uv run --with reportlab python operacao/whatsapp/whatsapp.py relatorio`.
