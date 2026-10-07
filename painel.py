"""Gera o painel da Raze Geradores: contas do plano de prospecção + ligações do Callix."""

import json
import re
import sqlite3
import unicodedata
from pathlib import Path

import conversa

RAIZ = Path(__file__).parent
DADOS = RAIZ / "data"

DESLIGAMENTO = {
    1: "Cliente desligou",
    2: "Operador desligou",
    3: "Sistema desligou",
    4: "Interrupção",
    5: "Callback",
    6: "Limite de tempo",
    7: "Supervisor",
    8: "Transferência para WhatsApp",
}


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", sem_acento.lower()).strip()


def _conta_da_chamada(contas: list[dict], attrs: dict, contato: dict) -> dict | None:
    """Casa a chamada com uma conta do plano pelo nome da empresa."""
    textos = [attrs.get("contact_label"), *contato.values()]
    candidatos = {f" {_normalizar(t)} " for t in textos if isinstance(t, str)}
    # Nomes mais longos primeiro, para um nome curto não capturar a conta errada.
    for conta in sorted(contas, key=lambda c: -len(c["empresa"])):
        nome = f" {_normalizar(conta['empresa'])} "
        if any(nome in c for c in candidatos):
            return conta
    return None


def _conversa(linha: sqlite3.Row) -> dict | None:
    """Transcrição por turnos, métricas e avaliação da conversa, quando já processada."""
    if not linha["turnos"]:
        return None
    return {
        "origem": linha["origem"],
        "turnos": json.loads(linha["turnos"]),
        "metricas": json.loads(linha["metricas"]),
        "analise": json.loads(linha["analise"]) if linha["analise"] else None,
    }


def _chamada(linha: sqlite3.Row) -> dict:
    attrs = json.loads(linha["atributos"])
    rel = json.loads(linha["relacionados"])
    qualificacao = rel.get("qualification", {})
    transcricao = next(iter(rel.get("transcriptions") or []), {})
    return {
        "id": linha["id"],
        "completada": linha["tipo"] == "campaign_completed_calls",
        "inicio": attrs.get("started_at"),
        "falado": attrs.get("service_duration") or 0,
        "telefone": attrs.get("destination_phone"),
        "rotulo": attrs.get("contact_label"),
        "qualificacao": qualificacao.get("name"),
        "sucesso": bool(qualificacao.get("success")),
        "agente": rel.get("agent", {}).get("name"),
        "nota": attrs.get("note"),
        "desligamento": DESLIGAMENTO.get(attrs.get("hangup_cause")),
        "audio": f"audio/{linha['audio_arquivo']}" if linha["audio_arquivo"] else None,
        "resumo": transcricao.get("summary"),
        "conversa": _conversa(linha),
        "contato": {
            k: v
            for k, v in rel.get("campaign_contact", {}).items()
            if v and k not in ("id", "created_at", "updated_at")
        },
    }


def _ofertas(conta: dict, regras: list[dict]) -> list[dict]:
    """Produtos sugeridos para a conta, com a situação de cada um no catálogo."""
    ofertas = []
    for principal, nomes in ((True, conta["produtos"]), (False, conta["complementares"])):
        for nome in nomes:
            regra = next((r for r in regras if r["contem"] in _normalizar(nome)), None)
            ofertas.append(
                {
                    "nome": nome,
                    "principal": principal,
                    "situacao": regra["situacao"] if regra else "nao_conferido",
                    "nota": regra["nota"] if regra else "",
                }
            )
    return ofertas


def _analise(conta_id: str) -> dict | None:
    """Pesquisa da empresa, gravada em analises/<id>.json."""
    arquivo = RAIZ / "analises" / f"{conta_id}.json"
    if not arquivo.exists():
        return None
    analise = json.loads(arquivo.read_text(encoding="utf-8"))
    # Nomes que vêm só do quadro societário do CNPJ não são contato de compra: ficam de fora.
    analise["decisores"] = [
        d for d in analise.get("decisores") or [] if "societ" not in d.get("cargo", "").lower()
    ]
    return analise


def montar(db: sqlite3.Connection, plano: dict, catalogo: dict, playbook: dict) -> dict:
    db.row_factory = sqlite3.Row
    # Proposta visual de cada conta, gravada por ofertas.py.
    arquivo = RAIZ / "propostas.json"
    propostas = json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else {}
    contas = [
        {
            **c,
            "chamadas": [],
            "proposta": propostas.get(c["id"]),
            "ofertas": _ofertas(c, catalogo["regras"]),
            "analise": _analise(c["id"]),
        }
        for c in plano["contas"]
    ]
    avulsas = []
    db.execute(conversa.SCHEMA)
    consulta = """
        SELECT c.*, v.origem, v.turnos, v.metricas, v.analise
        FROM chamadas c LEFT JOIN conversas v ON v.tipo = c.tipo AND v.id = c.id
        ORDER BY c.iniciada_em DESC
    """
    # Antes da primeira sincronização com o Callix a tabela de chamadas não existe: o painel sai só com a carteira.
    tem_chamadas = db.execute("SELECT 1 FROM sqlite_master WHERE name = 'chamadas'").fetchone()
    for linha in db.execute(consulta) if tem_chamadas else []:
        chamada = _chamada(linha)
        conta = _conta_da_chamada(contas, json.loads(linha["atributos"]), chamada["contato"])
        (conta["chamadas"] if conta else avulsas).append(chamada)
    # Tentativas anotadas à mão (ligação feita fora do Callix ou ainda não sincronizada).
    manuais = RAIZ / "tentativas.json"
    por_id = {c["id"]: c for c in contas}
    for t in json.loads(manuais.read_text(encoding="utf-8")) if manuais.exists() else []:
        # O registro de uma conta que saiu da carteira continua no arquivo, mas não entra no painel.
        if t["conta"] not in por_id:
            continue
        por_id[t["conta"]]["chamadas"].insert(
            0,
            {
                "id": f"manual-{t['quando']}",
                "completada": t.get("conversou", False),
                "inicio": t["quando"],
                "falado": 0,
                "telefone": None,
                "rotulo": "Registro manual",
                "qualificacao": t.get("qualificacao"),
                "sucesso": False,
                "agente": t.get("agente"),
                "nota": t["nota"],
                "etapa": t.get("etapa"),
                "prazo": t.get("prazo"),
                "desligamento": None,
                "audio": None,
                "resumo": None,
                "conversa": None,
                "contato": {},
            },
        )
    return {
        "eixos": plano["eixos"],
        "catalogo": catalogo,
        "playbook": playbook,
        "contas": contas,
        "avulsas": avulsas,
    }


def _para_cliente(dados: dict) -> dict:
    """Relatório do cliente: CRM, esteiras e dados das empresas, sem o material interno.

    Saem o playbook (roteiros, objeções, perguntas em aberto), o catálogo e as ressalvas
    de trabalho de cada conta. Do playbook fica só o necessário para nomear as esteiras
    e a solução de entrada de cada segmento.
    """
    playbook = dados["playbook"]
    enxuto = {
        "esteiras": playbook["esteiras"],
        "solucoes": playbook["solucoes"],
        "segmentos": {
            nome: {"ofertas": [{"solucao": o["solucao"]} for o in seg["ofertas"]]}
            for nome, seg in playbook["segmentos"].items()
        },
    }
    contas = []
    for conta in dados["contas"]:
        analise = conta["analise"]
        if analise:
            analise = {**analise, "ressalvas": [], "motivo_da_ligacao": "", "perguntas_especificas": []}
        contas.append({**conta, "analise": analise, "ofertas": []})
    return {**dados, "modo": "cliente", "playbook": enxuto, "catalogo": {}, "contas": contas}


def gerar(db_arquivo: Path, saida: Path) -> None:
    plano = json.loads((RAIZ / "contas.json").read_text(encoding="utf-8"))
    catalogo = json.loads((RAIZ / "catalogo.json").read_text(encoding="utf-8"))
    playbook = json.loads((RAIZ / "playbook.json").read_text(encoding="utf-8"))
    db_arquivo.parent.mkdir(exist_ok=True)
    db = sqlite3.connect(db_arquivo)
    completo = montar(db, plano, catalogo, playbook)
    modelo = (RAIZ / "painel_modelo.html").read_text(encoding="utf-8")

    def pagina_de(dados: dict) -> str:
        return modelo.replace("__DADOS__", json.dumps(dados, ensure_ascii=False).replace("</", "<\\/"))

    pagina = pagina_de(completo)
    saida.write_text(pagina, encoding="utf-8")
    # Cópia completa em docs/, que é a pasta servida pelo GitHub Pages. Pede aos buscadores que não a indexem.
    if saida.parent == DADOS:
        (RAIZ / "docs").mkdir(exist_ok=True)
        (RAIZ / "docs" / "index.html").write_text(
            pagina.replace("<head>", '<head><meta name="robots" content="noindex, nofollow">', 1),
            encoding="utf-8",
        )
        # Relatório do cliente, em docs/cliente/ e ao lado do painel local.
        cliente = pagina_de(_para_cliente(completo))
        saida.with_name("relatorio_cliente.html").write_text(cliente, encoding="utf-8")
        (RAIZ / "docs" / "cliente").mkdir(exist_ok=True)
        (RAIZ / "docs" / "cliente" / "index.html").write_text(
            cliente.replace("<head>", '<head><meta name="robots" content="noindex, nofollow">', 1),
            encoding="utf-8",
        )
    # Versão para publicar como link: a hospedagem acrescenta o esqueleto da página por conta própria.
    miolo = re.sub(r"<!DOCTYPE html>|</?html[^>]*>|</?head>|</?body>|<meta[^>]*>", "", pagina)
    saida.with_name(saida.stem + "_link.html").write_text(miolo.strip(), encoding="utf-8")


if __name__ == "__main__":
    gerar(DADOS / "crm.db", DADOS / "painel.html")
    print(f"Painel gerado em {DADOS / 'painel.html'}")
