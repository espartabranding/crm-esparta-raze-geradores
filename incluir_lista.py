"""Inclui na carteira uma lista de leads do Painel Raze, como contas ainda não abordadas.

Lê um CSV no formato das listas consolidadas do Painel Raze (por exemplo `leads_cadeia_fria_300_raze.csv`) e põe
cada linha em contas.json, na onda "base", com identificador f1, f2... Conta que já está na carteira (mesmo CNPJ,
mesmo nome ou mesmo telefone) não entra de novo. Rodar outra vez substitui as contas "f" e deixa o resto como está.

Os dados são os da Receita: não há pesquisa individual, decisor nem sinal de compra. O fit sai de regra fixa:
- carga que não pode cair: 3 (indústria e cadeia fria);
- exigência de norma: 3 quando a régua do Painel Raze marca obrigação de ter gerador, senão 2;
- porte: 3 com capital social de R$ 10 milhões ou mais, 2 de R$ 1 milhão ou mais, 1 abaixo disso;
- acesso ao decisor: 1 com telefone duvidoso, 3 com telefone e e-mail de domínio próprio, 2 nos demais casos.

Uso: uv run python incluir_lista.py "C:\\caminho\\da\\lista.csv"
"""

import csv
import json
import re
import sys
from pathlib import Path

from montar_carteira import caixa_normal, dominio_de, dominio_proprio, sem_acento, telefone

RAIZ = Path(__file__).parent
PADRAO = Path.home() / "Desktop/Projetos_Claude/Painel_Raze/painel_raze/output/prospeccao/leads_cadeia_fria_300_raze.csv"
SEGMENTO = "Indústria e cadeia fria"
COMBO = "P3 Prontidão Industrial"
PRODUTOS = ["Diagnóstico de Prontidão", "Ensaios de desempenho sob carga", "Manutenção preventiva contratada", "Relatório técnico e histórico de tendência"]
COMPLEMENTARES = ["SLA de emergência e apoio à decisão (dossiê de assembleia)", "Prontuário de Instalações Elétricas — NR-10"]
RECEITA = "https://solucoes.receita.fazenda.gov.br/servicos/cnpjreva/cnpjreva_solicitacao.asp"


def _chave(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", sem_acento(texto or "").lower()).strip()


def _fone(texto: str) -> str:
    return re.sub(r"\D", "", texto or "")[-10:]


def _conta(linha: dict, n: int) -> dict:
    fone, duvida = telefone(linha["telefone"], linha["municipio"])
    capital = int(float(linha["capital_social"] or 0))
    obriga = linha["obriga_a_ter_gerador"] == "S"
    email = linha["email"].lower()
    porte = 3 if capital >= 10_000_000 else 2 if capital >= 1_000_000 else 1
    acesso = 1 if duvida else 3 if dominio_proprio(dominio_de(email)) else 2
    # Aderência por eixo: parte do perfil de cadeia fria e acompanha o porte e a exigência de norma.
    ader = [9, 9, 8, 6, 8, 6]
    if porte == 3:
        ader = [10, 10, 8, 6, 9, 6]
    elif porte == 1:
        ader = [9, 8, 7, 6, 7, 6]
    if obriga:
        ader[3] += 1
    socios = [s.strip() for s in linha["socios"].split("·") if s.strip()][:3]
    cidade, bairro = linha["municipio"], caixa_normal(linha["bairro"])
    return {
        "id": f"f{n}", "empresa": caixa_normal(linha["nome"]), "cidade": cidade, "bairro": bairro, "segmento": SEGMENTO,
        "fit": [3, 3 if obriga else 2, porte, acesso], "onda": "base", "ader": ader, "produtos": PRODUTOS, "complementares": COMPLEMENTARES,
        "angulo": f"Atividade na Receita: {linha['atividade'].lower()}." + (" A régua de conformidade do Painel Raze aponta norma que exige gerador (vigência a confirmar)." if obriga else ""),
        "gancho": "Há registro do último ensaio do gerador feito sob carga?",
        "telefone": fone, "site": "", "email": email, "cnpj": linha["cnpj"],
        "porte": f"{linha['porte']} na Receita; capital social de R$ {capital:,}".replace(",", ".") if capital else f"{linha['porte']} na Receita",
        "perfil": [f"{linha['atividade']}, em {bairro}, {cidade}. Empresa aberta em {linha['desde'][:4]}."],
        "sinal": " ".join(x for x in (
            "Conta da lista de cadeia fria, ainda sem pesquisa individual.",
            f"{linha['n_regras']} regras de conformidade mapeadas na régua do Painel Raze.",
            f"Na Receita: {'; '.join(caixa_normal(s) for s in socios)}." if socios else "",
            f"Outro telefone: {linha['telefone_2']}." if linha["telefone_2"] else "",
            f"Contato a validar: {duvida}." if duvida else "") if x),
        "fontes": [{"t": "Receita Federal", "u": RECEITA}], "proximo": "Não abordada", "combo": COMBO, "combo_secundario": "",
    }


def incluir(lista: Path) -> None:
    carteira = json.loads((RAIZ / "contas.json").read_text(encoding="utf-8"))
    resto = [c for c in carteira["contas"] if not c["id"].startswith("f")]
    cnpjs = {c.get("cnpj") for c in resto if c.get("cnpj")}
    nomes = {_chave(c["empresa"]) for c in resto}
    fones = {_fone(c.get("telefone")) for c in resto if c.get("telefone")}
    novas, repetidas = [], 0
    with lista.open(encoding="utf-8-sig", newline="") as arquivo:
        for linha in csv.DictReader(arquivo, delimiter=";"):
            conta = _conta(linha, len(novas) + 1)
            if conta["cnpj"] in cnpjs or _chave(conta["empresa"]) in nomes or (_fone(conta["telefone"]) and _fone(conta["telefone"]) in fones):
                repetidas += 1
                continue
            cnpjs.add(conta["cnpj"])
            nomes.add(_chave(conta["empresa"]))
            fones.add(_fone(conta["telefone"]))
            novas.append(conta)
    carteira["contas"] = resto + novas
    (RAIZ / "contas.json").write_text(json.dumps(carteira, ensure_ascii=False), encoding="utf-8")
    print(f"{len(novas)} contas incluídas ({repetidas} já estavam na carteira ou repetidas na lista); carteira com {len(carteira['contas'])} contas.")


if __name__ == "__main__":
    incluir(Path(sys.argv[1]) if len(sys.argv) > 1 else PADRAO)
