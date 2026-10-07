"""Traz para o CRM a planilha de prospecção da Raze (as contas trabalhadas e o status de cada uma).

Lê as abas "Abordagens — Não hospitalares", "Abordagens — Clínicas" e "Painel de status" e:
- põe as contas da planilha em contas.json, com identificador x1, x2... e a onda "c1" (campanha em andamento);
- grava em tentativas.json o resultado do contato de cada uma, com a etapa do kanban e o prazo do próximo passo.
  O contato é registrado na segunda-feira da semana da planilha.

Regra do prazo (pedida em 07/10): o que estava para "à tarde" ou para o próprio dia da planilha vai para o dia
útil seguinte; "ligar novamente" sem data vai para o dia útil seguinte nas contas de prioridade A e para o
outro dia útil nas de prioridade B. Datas que a planilha já traz no futuro são mantidas.

Rodar de novo substitui as contas "x" e os registros delas; o resto da carteira e dos registros fica como está.
Uso: uv run python importar_planilha.py "C:\\caminho\\da\\planilha.xlsx"
"""

import json
import re
import sys
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import openpyxl

RAIZ = Path(__file__).parent
PADRAO = Path.home() / "Desktop" / "Raze-prospeccao-RJ-consolidado-07-10.xlsx"

# Plano da planilha -> plano do CRM, serviços sugeridos e aderência por eixo (mesma ordem de `eixos` em contas.json).
PLANOS = {
    "hospitalar": ("P2 Prontidão Hospitalar", "Saúde", [9, 9, 8, 9, 8, 5],
                   ["Diagnóstico de Prontidão", "Ensaios de desempenho sob carga", "Conformidade RDC 50 para estabelecimentos de saúde", "Manutenção preventiva contratada"]),
    "industrial": ("P3 Prontidão Industrial", "Indústria e cadeia fria", [9, 9, 8, 6, 9, 6],
                   ["Diagnóstico de Prontidão", "Ensaios de desempenho sob carga", "Manutenção preventiva contratada", "Relatório técnico e histórico de tendência"]),
    "comercial": ("P4 Prontidão Comercial", "Comércio e centros comerciais", [8, 7, 7, 7, 6, 5],
                  ["Diagnóstico de Prontidão", "Manutenção preventiva contratada", "Laudo de autovistoria predial e de abrangência"]),
}
HOTELARIA = ("hotel", "evento", "buffet", "estudio")

# Status da planilha -> etapa do kanban, qualificação do Callix e se houve conversa.
STATUS = {
    # Em 07/10 o que a planilha chama de "proposta enviada" foi o contato com identificação do responsável e a
    # apresentação da empresa; a proposta ainda está por apresentar.
    "proposta enviada": ("apresentar", "Enviar material", True),
    "retorno agendado": ("retornar", "Retornar em data combinada", True),
    "contato indicado": ("apresentar", "Indicou outro contato", True),
    "aguardando retorno": ("retornar", "Recepção passou informação", True),
    "nao atendeu": ("tentar", "Não atendeu / caixa postal", False),
    "sem resultado registrado": ("tentar", "", False),
    "retirado": ("encerrada", "", False),
}
DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]


def _chave(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", sem_acento.lower()).strip()


def _util(dia: date, passos: int = 1) -> date:
    while passos:
        dia += timedelta(days=1)
        if dia.weekday() < 5:
            passos -= 1
    return dia


def _telefone(texto: str) -> tuple[str, str]:
    """O primeiro número, no formato do CRM, e os demais como vieram."""
    partes = [p.strip() for p in re.split(r";", texto or "") if p.strip()]
    if not partes:
        return "", ""
    digitos = re.sub(r"\D", "", partes[0])
    if len(digitos) in (10, 11) and not digitos.startswith("0"):
        primeiro = f"({digitos[:2]}) {digitos[2:-4]}-{digitos[-4:]}"
    else:
        primeiro = partes[0]
    return primeiro, "; ".join(partes[1:])


def _linhas(aba) -> list[dict]:
    """Linhas de uma aba cujo cabeçalho começa por "Empresa" ou por "#"."""
    linhas = list(aba.iter_rows(values_only=True))
    inicio = next(i for i, l in enumerate(linhas) if l and l[0] in ("Empresa", "#"))
    cabecalho = [str(c) if c is not None else "" for c in linhas[inicio]]
    return [dict(zip(cabecalho, ["" if v is None else str(v).strip() for v in l], strict=False)) for l in linhas[inicio + 1:] if l and l[0] not in (None, "")]


def importar(planilha: Path) -> None:
    livro = openpyxl.load_workbook(planilha, data_only=True)
    posicao = re.search(r"(\d{2})/(\d{2})/(\d{4})", str(livro["Painel de status"]["A2"].value))
    hoje = date(int(posicao[3]), int(posicao[2]), int(posicao[1]))
    amanha, depois = _util(hoje), _util(hoje, 2)
    # Os contatos são registrados na segunda-feira da semana da planilha; a posição da planilha só serve para os prazos.
    contato_em = hoje - timedelta(days=hoje.weekday())
    fichas = {}
    for nome in ("Abordagens — Não hospitalares", "Abordagens — Clínicas"):
        for linha in _linhas(livro[nome]):
            fichas[_chave(linha["Empresa"])] = linha

    carteira = json.loads((RAIZ / "contas.json").read_text(encoding="utf-8"))
    novas, registros = [], []
    for n, st in enumerate(_linhas(livro["Painel de status"]), 1):
        ficha = fichas.get(_chave(st["Empresa"]), {})
        plano = next(v for k, v in PLANOS.items() if k in _chave(st["Plano Raze"]))
        tipo = st["Segmento"]
        segmento = "Hotelaria e eventos" if any(p in _chave(tipo) for p in HOTELARIA) else plano[1]
        telefone, outros = _telefone(st["Telefone"])
        invalido = "invalido" in _chave(st["Observações"])
        contato = "" if _chave(st["Contato / decisor"]) in ("", "sem nome") or "sem nome" in _chave(st["Contato / decisor"]) else st["Contato / decisor"]
        email = ficha.get("E-mail", "") or next(iter(re.findall(r"[\w.+-]+@[\w.-]+\.\w+", st["Canal e destino"])), "")
        grande = "grande porte" in _chave(st["Observações"])
        saude = plano[1] == "Saúde"
        fit = [3 if saude or "industrial" in _chave(plano[0]) else 2, 3 if saude else 2, 3 if grande else 2, 1 if invalido else 3 if contato or email else 2]
        fonte = ficha.get("Fonte", "")
        id_conta = f"x{n}"
        novas.append({
            "id": id_conta, "empresa": st["Empresa"], "cidade": "Rio de Janeiro", "bairro": st["Bairro"], "segmento": segmento,
            "fit": fit, "onda": "c1", "ader": plano[2], "produtos": plano[3], "complementares": ["SLA de emergência e apoio à decisão (dossiê de assembleia)"],
            "angulo": ficha.get("Evidência de gerador") or ficha.get("Evidência") or "", "gancho": ficha.get("3. Pergunta de descoberta", ""),
            "telefone": "" if invalido else telefone, "site": fonte if fonte.startswith("http") and "datasus" not in fonte else "",
            "email": email, "contato": contato, "porte": "Grande porte" if grande else "a confirmar",
            "perfil": [f"{tipo} em {st['Bairro']}, Rio de Janeiro." + (f" {ficha['Endereço']}." if ficha.get("Endereço") else "")],
            "sinal": " ".join(x for x in (f"Prioridade {ficha['Prioridade']} na planilha." if ficha.get("Prioridade") else "", st["Observações"],
                                            f"Outros telefones: {outros}." if outros else "") if x),
            "fontes": [{"t": urlparse(fonte).hostname.removeprefix("www."), "u": fonte}] if fonte.startswith("http") else [],
            "proximo": st["Próxima ação"] or "Não abordada", "combo": plano[0], "combo_secundario": "",
        })

        situacao = _chave(st["Status"])
        if situacao not in STATUS:
            continue  # "Não contatado": fica na coluna de não abordadas
        etapa, qualificacao, conversou = STATUS[situacao]
        # O "à tarde" era do dia da planilha; com o prazo remarcado, sai do texto.
        acao, quando = re.sub(r"\s+à tarde$", "", st["Próxima ação"]), _chave(st["Data"])
        # Prazo do próximo passo, pela regra descrita no topo do arquivo.
        marcada = re.search(r"(\d{2}) (\d{2}) (\d{4})", quando)
        prazo = date(int(marcada[3]), int(marcada[2]), int(marcada[1])) if marcada else None
        if etapa == "encerrada":
            prazo = None
        elif prazo is None:
            prazo = amanha if etapa != "tentar" or ficha.get("Prioridade", "A") == "A" else depois
        elif prazo <= hoje:
            prazo = amanha
        if situacao == "proposta enviada":
            partes = ["Contato feito e apresentação da empresa enviada." + (f" Responsável identificado: {contato}." if contato else " Responsável ainda sem nome.")]
        else:
            partes = ["Retirada da campanha." if etapa == "encerrada" else st["Status"] + "."]
            if contato:
                partes.append(f"Contato: {contato}.")
        if st["Canal e destino"]:
            partes.append(f"Canal: {st['Canal e destino']}.")
        if prazo:
            partes.append(f"Próximo passo: {acao[0].lower() + acao[1:]}, em {prazo:%d/%m} ({DIAS[prazo.weekday()]}).")
        if st["Observações"]:
            partes.append(st["Observações"])
        registros.append({"conta": id_conta, "quando": datetime(contato_em.year, contato_em.month, contato_em.day, 15, 0).isoformat() + "+00:00", "qualificacao": qualificacao,
                          "nota": " ".join(partes), "etapa": etapa, "conversou": conversou, **({"prazo": prazo.isoformat()} if prazo else {})})

    # As contas da planilha entram na frente; uma conta da base com o mesmo nome ou o mesmo telefone sai, para não duplicar.
    nomes = {_chave(c["empresa"]) for c in novas}
    fones = {re.sub(r"\D", "", c["telefone"]) for c in novas if c["telefone"]}
    resto = [c for c in carteira["contas"] if not c["id"].startswith("x") and _chave(c["empresa"]) not in nomes and re.sub(r"\D", "", c.get("telefone") or "")[-10:] not in {f[-10:] for f in fones}]
    carteira["contas"] = novas + resto
    (RAIZ / "contas.json").write_text(json.dumps(carteira, ensure_ascii=False), encoding="utf-8")
    arquivo = RAIZ / "tentativas.json"
    antigos = [t for t in json.loads(arquivo.read_text(encoding="utf-8")) if not t["conta"].startswith("x")] if arquivo.exists() else []
    arquivo.write_text(json.dumps(antigos + registros, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(novas)} contas da planilha, {len(registros)} com contato registrado; carteira com {len(carteira['contas'])} contas.")


if __name__ == "__main__":
    importar(Path(sys.argv[1]) if len(sys.argv) > 1 else PADRAO)
