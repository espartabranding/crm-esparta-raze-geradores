"""Operação de WhatsApp da Raze Geradores: ponto fixo, registro no CRM e relatório diário.

O estado da operação fica em operacao/whatsapp/estado.json, dentro do repositório do CRM.
Qualquer sessão nova (WhatsApp Web em aba anônima, outro computador, outra conversa com o Claude)
começa por `status` e sabe exatamente onde a operação parou.

Comandos (rodar na raiz do repositório):
    python operacao/whatsapp/whatsapp.py status [--data AAAA-MM-DD] [--json]
    python operacao/whatsapp/whatsapp.py registrar CONTA RESULTADO [--nota TEXTO] [--prazo AAAA-MM-DD]
                                                   [--contato NOME] [--quando ISO] [--publicar]
    python operacao/whatsapp/whatsapp.py relatorio [--data AAAA-MM-DD]
    python operacao/whatsapp/whatsapp.py publicar [--mensagem TEXTO]
    python operacao/whatsapp/whatsapp.py incluir LOTE.csv --lote L04 [--situacao a_enviar]
    python operacao/whatsapp/whatsapp.py liberar [CONTAS...] [--lote L03] [--motivo TEXTO]
    python operacao/whatsapp/whatsapp.py segurar [CONTAS...] [--lote L03] [--motivo TEXTO]

CONTA é o id do CRM (w12, r68, x4) ou a chave da fila (ex.: L03-01) para quem ainda não está no CRM;
nesse caso a conta é criada no contas.json no primeiro registro.

RESULTADO: enviado, entregue, 1tique, sem_whatsapp, resposta_automatica, respondeu, contato_obtido,
material_enviado, followup, recusou, nao_contatar, numero_errado.

O relatório em PDF precisa do reportlab (no Windows: `uv run --with reportlab python ...`).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent
ESTADO = AQUI / "estado.json"
DIARIO = AQUI / "diario"
TENTATIVAS = RAIZ / "tentativas.json"
CONTAS = RAIZ / "contas.json"
ANALISES = RAIZ / "analises"
FUSO = timezone(timedelta(hours=-3))

# resultado -> qualificação no CRM, etapa do kanban, conversou, situação na fila, próximo passo, dias úteis até o prazo
RESULTADOS: dict[str, tuple[str, str, bool, str, str, int | None]] = {
    "enviado": ("WhatsApp enviado", "tentar", False, "enviado", "Conferir a entrega e fazer o 2º toque se não houver resposta", 2),
    "entregue": ("WhatsApp entregue", "tentar", False, "entregue", "2º toque se não houver resposta", 2),
    "1tique": ("WhatsApp enviado (1 tique)", "tentar", False, "1_tique", "Reenviar a mensagem", 1),
    "sem_whatsapp": ("Número sem WhatsApp", "tentar", False, "sem_whatsapp", "Ligar (Camile/Fluke) ou buscar outro contato", 1),
    "resposta_automatica": ("Resposta automática", "tentar", False, "resposta_automatica", "Responder pedindo o contato do responsável", 1),
    "respondeu": ("Respondeu", "apresentar", True, "respondeu", "Dar sequência à conversa", 0),
    "contato_obtido": ("Contato do responsável obtido", "apresentar", True, "contato_obtido", "Abordar o responsável indicado", 1),
    "material_enviado": ("Material enviado", "apresentar", True, "material_enviado", "Confirmar o recebimento do material", 2),
    "followup": ("Follow-up por WhatsApp", "tentar", False, "followup", "Ligar se não houver resposta", 3),
    "recusou": ("Recusou", "encerrada", True, "recusou", "Não contatar mais", None),
    "nao_contatar": ("Pediu para não contatar", "encerrada", True, "nao_contatar", "Não contatar mais", None),
    "numero_errado": ("Número errado", "tentar", False, "numero_errado", "Buscar outro contato", 1),
}

ROTULO = {
    "a_enviar": "A enviar",
    "segurar": "Em espera",
    "confirmar": "Conferir dado antes",
    "material_pendente": "Material pendente",
    "enviado": "Enviado",
    "entregue": "Entregue, sem resposta",
    "1_tique": "Não entregue (1 tique)",
    "followup": "Follow-up enviado",
    "sem_whatsapp": "Sem WhatsApp",
    "resposta_automatica": "Resposta automática",
    "respondeu": "Respondeu",
    "contato_obtido": "Contato obtido",
    "material_enviado": "Material enviado",
    "recusou": "Recusou",
    "nao_contatar": "Não contatar",
    "numero_errado": "Número errado",
}

ENCERRADAS = {"recusou", "nao_contatar"}
MAX_TOQUES = 3  # depois do 3º toque sem resposta, o WhatsApp sai de cena e a conta vai para ligação


# ---------------------------------------------------------------- arquivos

def ler_json(caminho: Path):
    return json.loads(caminho.read_text(encoding="utf-8"))


def gravar_json(caminho: Path, dados, indent: int | None = 1) -> None:
    """Gravação atômica: um arquivo interrompido no meio nunca substitui o anterior.
    Mantém o formato dos arquivos do CRM (tentativas.json com indent 1, contas.json compacto, sem quebra no fim)."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=caminho.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        json.dump(dados, f, ensure_ascii=False, indent=indent)
    os.replace(tmp, caminho)


def agora() -> datetime:
    return datetime.now(FUSO).replace(microsecond=0)


def somar_dias_uteis(inicio: date, dias: int) -> date:
    d = inicio
    while dias > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            dias -= 1
    return d


def br(d: str | date | None) -> str:
    if not d:
        return "—"
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    return d.strftime("%d/%m")


# ---------------------------------------------------------------- estado

def carregar_estado() -> dict:
    if not ESTADO.exists():
        sys.exit("estado.json não encontrado em operacao/whatsapp/. Rode a partir do repositório do CRM.")
    return ler_json(ESTADO)


def achar(estado: dict, chave: str) -> dict | None:
    for item in estado["fila"]:
        if item.get("conta") == chave or item.get("chave") == chave:
            return item
    return None


def acoes_do_dia(estado: dict, hoje: date) -> dict[str, list[dict]]:
    """Separa a fila no que fazer hoje, na ordem em que deve ser feito."""
    grupos: dict[str, list[dict]] = {
        "responder": [], "material": [], "reenviar": [], "followup": [], "novos": [],
        "voz": [], "espera": [], "conferir": [], "esgotados": [],
    }
    for it in estado["fila"]:
        s = it["situacao"]
        prazo = date.fromisoformat(it["prazo"]) if it.get("prazo") else None
        vencido = prazo is None or prazo <= hoje
        if s in ENCERRADAS:
            continue
        if s in ("respondeu", "contato_obtido", "resposta_automatica"):
            grupos["responder"].append(it)
        elif s == "material_pendente":
            grupos["material"].append(it)
        elif s == "1_tique":
            grupos["reenviar"].append(it)
        elif s in ("enviado", "entregue", "followup", "material_enviado"):
            if it.get("toques", 0) >= MAX_TOQUES:
                grupos["esgotados"].append(it)
            elif vencido:
                grupos["followup"].append(it)
        elif s in ("sem_whatsapp", "numero_errado"):
            grupos["voz"].append(it)
        elif s == "a_enviar":
            grupos["novos"].append(it)
        elif s == "segurar":
            grupos["espera"].append(it)
        elif s == "confirmar":
            grupos["conferir"].append(it)
    grupos["followup"].sort(key=lambda i: (i.get("prazo") or "", i.get("ordem", 0)))
    grupos["novos"].sort(key=lambda i: i.get("ordem", 0))
    return grupos


TITULOS = {
    "responder": "1. Responder primeiro (quem já falou com a Raze)",
    "material": "2. Enviar o material prometido",
    "reenviar": "3. Reenviar (mensagem não entregue)",
    "followup": "4. Follow-up vencido (entregue, sem resposta)",
    "novos": "5. Primeira mensagem (fila liberada, na ordem)",
    "voz": "Fora do WhatsApp: ligação (Camile/Fluke) ou outro contato",
    "esgotados": "Fora do WhatsApp: 3 toques sem resposta, passar para ligação",
    "espera": "Em espera (não enviar até decisão)",
    "conferir": "Conferir o dado antes de enviar",
}


def cmd_status(args) -> None:
    estado = carregar_estado()
    hoje = date.fromisoformat(args.data) if args.data else agora().date()
    grupos = acoes_do_dia(estado, hoje)
    if args.json:
        print(json.dumps({"hoje": hoje.isoformat(), "ultima_sessao": estado.get("ultima_sessao"),
                          "grupos": {k: [i.get("conta") or i.get("chave") for i in v] for k, v in grupos.items()}},
                         ensure_ascii=False, indent=1))
        return
    u = estado.get("ultima_sessao") or {}
    print(f"PONTO FIXO · WhatsApp Raze · hoje {hoje.strftime('%d/%m/%Y')}")
    print(f"Estado gravado em {estado.get('atualizado_em', '—')}")
    if u.get("ultimo_registro"):
        r = u["ultimo_registro"]
        print(f"Última sessão: {br(u.get('data'))}, {u.get('registros', 0)} registro(s). Parou em: "
              f"{r['nome']} ({r['conta']}) -> {ROTULO.get(r['situacao'], r['situacao'])}")
    else:
        print("Última sessão: nenhum registro feito por este script ainda.")
    for chave, titulo in TITULOS.items():
        itens = grupos[chave]
        if not itens:
            continue
        print(f"\n{titulo} [{len(itens)}]")
        for it in itens:
            ident = it.get("conta") or it.get("chave")
            extra = f" · prazo {br(it.get('prazo'))}" if it.get("prazo") else ""
            obs = f" · {it['obs']}" if it.get("obs") else ""
            print(f"  - {ident:7} {it['nome']} · {it.get('telefone', '')} · {it.get('tipo', '')} · "
                  f"toques {it.get('toques', 0)}{extra}{obs}")
    contagem: dict[str, int] = {}
    for it in estado["fila"]:
        contagem[it["situacao"]] = contagem.get(it["situacao"], 0) + 1
    print("\nBase no WhatsApp: " + " · ".join(f"{ROTULO.get(k, k)} {v}" for k, v in sorted(contagem.items())))


# ---------------------------------------------------------------- registro

def criar_conta(item: dict) -> str:
    """Abre no CRM a conta de quem estava só na fila (mesmo formato das contas w22 a w27)."""
    plano = ler_json(CONTAS)
    ids = [c["id"] for c in plano["contas"]]
    n = max(int(i[1:]) for i in ids if i.startswith("w") and i[1:].isdigit()) + 1
    novo = f"w{n}"
    residencial = item.get("tipo", "condominio") == "condominio"
    plano["contas"].append({
        "id": novo,
        "empresa": item["nome"],
        "cidade": item.get("municipio", "Rio de Janeiro"),
        "bairro": item.get("bairro", ""),
        "segmento": item.get("segmento", "Condomínios"),
        "fit": [2, 2, 2, 2],
        "onda": "c1",
        "ader": [10, 8, 8, 9, 7, 5],
        "produtos": ["Diagnóstico de Prontidão", "Manutenção preventiva contratada",
                     "Laudo de autovistoria predial e de abrangência", "Ensaios de desempenho sob carga"],
        "complementares": ["SLA de emergência e apoio à decisão (dossiê de assembleia)",
                           "Relatório técnico e histórico de tendência"],
        "angulo": "",
        "gancho": "Quando o gerador do condomínio é testado, o ensaio é feito com carga e fica registrado em laudo?",
        "telefone": item.get("telefone", ""),
        "site": "", "email": "", "contato": "",
        "porte": item.get("porte", ""),
        "perfil": [item["perfil"]] if item.get("perfil") else [],
        "sinal": f"Conta aberta pela operação de WhatsApp ({br(agora().date())}), ainda sem pesquisa individual. "
                 + (f"WhatsApp publicado no site oficial ({item['fonte']})." if item.get("fonte")
                    else "Celular da ficha do Google Maps, não confirmado em outra fonte."),
        "fontes": [],
        "proximo": "",
        "combo": "P1 Prontidão Residencial" if residencial else "",
        "combo_secundario": "",
        **({"cnpj": item["cnpj"]} if item.get("cnpj") else {}),
    })
    gravar_json(CONTAS, plano, indent=None)
    return novo


def cmd_registrar(args) -> None:
    if args.resultado not in RESULTADOS:
        sys.exit(f"Resultado inválido: {args.resultado}. Use um de: {', '.join(RESULTADOS)}")
    if args.resultado in ("respondeu", "contato_obtido", "resposta_automatica", "recusou") and not args.nota:
        sys.exit("Para resposta, recusa ou contato obtido, use --nota com o que a pessoa disse e o próximo passo.")
    estado = carregar_estado()
    item = achar(estado, args.conta)
    if not item:
        sys.exit(f"{args.conta} não está na fila do estado.json. Inclua a conta na fila antes de registrar.")
    quando = datetime.fromisoformat(args.quando) if args.quando else agora()
    if quando.tzinfo is None:
        quando = quando.replace(tzinfo=FUSO)
    qualif, etapa, conversou, situacao, proximo, dias = RESULTADOS[args.resultado]
    prazo = args.prazo or (somar_dias_uteis(quando.date(), dias).isoformat() if dias is not None else None)

    if not item.get("conta"):
        item["conta"] = criar_conta(item)
    conta = item["conta"]
    # Conta como toque toda mensagem nova. Não conta: reenvio de mensagem que não chegou (1 tique)
    # e a simples atualização de "enviado" para "entregue" da mesma mensagem.
    toque = args.resultado in ("enviado", "entregue", "1tique", "followup", "material_enviado")
    antes = item["situacao"]
    mesma_msg = (antes == "1_tique" and args.resultado in ("enviado", "entregue", "1tique")) or (
        args.resultado == "entregue" and item["situacao"] == "enviado"
        and item.get("ultimo_toque") == quando.date().isoformat())
    if toque and not mesma_msg:
        item["toques"] = item.get("toques", 0) + 1
        item["ultimo_toque"] = quando.date().isoformat()
    if args.contato:
        item["contato"] = args.contato

    nota = args.nota or (
        f"WhatsApp em {br(quando.date())}: {qualif}, número {item.get('telefone', '')}. "
        f"Próximo passo: {proximo.lower()}" + (f", em {br(prazo)}." if prazo else ".")
    )
    registro = {"conta": conta, "quando": quando.isoformat(), "qualificacao": qualif, "nota": nota,
                "etapa": etapa, "conversou": conversou, "prazo": prazo}

    tentativas = ler_json(TENTATIVAS)
    tentativas.append(registro)
    gravar_json(TENTATIVAS, tentativas)

    item.update({"situacao": situacao, "prazo": prazo, "proximo": proximo, "ultima_acao": quando.isoformat()})
    dia = quando.date().isoformat()
    ultima = estado.get("ultima_sessao") or {}
    estado["ultima_sessao"] = {
        "data": dia,
        "registros": (ultima.get("registros", 0) + 1) if ultima.get("data") == dia else 1,
        "ultimo_registro": {"conta": conta, "nome": item["nome"], "situacao": situacao, "quando": quando.isoformat()},
    }
    estado["atualizado_em"] = agora().isoformat()
    gravar_json(ESTADO, estado)

    DIARIO.mkdir(parents=True, exist_ok=True)
    with (DIARIO / f"{dia}.jsonl").open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({**registro, "nome": item["nome"], "bairro": item.get("bairro", ""),
                            "tipo": item.get("tipo", ""), "resultado": args.resultado, "antes": antes,
                            "lote": item.get("lote", ""), "toques": item.get("toques", 0)},
                           ensure_ascii=False) + "\n")
    print(f"Registrado: {item['nome']} ({conta}) -> {ROTULO[situacao]}; prazo {br(prazo)}.")
    if args.publicar:
        publicar(f"WhatsApp {br(quando.date())}: {item['nome']} ({conta}) {ROTULO[situacao].lower()}")


# ---------------------------------------------------------------- fila

def cmd_incluir(args) -> None:
    """Inclui um lote novo na fila a partir de um CSV no formato dos lotes (separador ;)."""
    import csv
    estado = carregar_estado()
    plano = {c["id"]: c for c in ler_json(CONTAS)["contas"]}
    linhas = list(csv.DictReader(open(args.csv, encoding="utf-8-sig"), delimiter=";"))
    base = max((i.get("ordem", 0) for i in estado["fila"]), default=0)
    novos = 0
    for n, l in enumerate(linhas, 1):
        conta = (l.get("conta_no_crm") or "").strip()
        conta = conta if conta in plano else None
        tel = l.get("whatsapp") or (plano[conta]["telefone"] if conta else "")
        dup = any((conta and i.get("conta") == conta) or i.get("telefone") == tel for i in estado["fila"])
        if dup:
            print(f"  já na fila, pulado: {l.get('nome')} {tel}")
            continue
        estado["fila"].append({
            "ordem": base + n, "chave": f"{args.lote}-{n:02d}", "conta": conta, "lote": args.lote,
            "nome": l.get("nome") or (plano[conta]["empresa"] if conta else ""), "telefone": tel,
            "bairro": l.get("bairro", ""), "municipio": l.get("municipio", "Rio de Janeiro"),
            "tipo": l.get("tipo", "condominio"), "segmento": plano[conta]["segmento"] if conta else (l.get("segmento") or "Condomínios"),
            "cnpj": "".join(ch for ch in l.get("cnpj", "") if ch.isdigit()),
            "perfil": ", ".join(x for x in [l.get("razao_social", ""), l.get("endereco", "")] if x),
            "situacao": "confirmar" if (l.get("observacao") or "").strip() else args.situacao,
            "obs": (l.get("observacao") or "").strip(), "toques": 0, "prazo": None, "proximo": "Primeira mensagem",
            **({"fonte": l["fonte"].strip()} if (l.get("fonte") or "").strip() else {}),
        })
        novos += 1
    estado["atualizado_em"] = agora().isoformat()
    gravar_json(ESTADO, estado)
    print(f"{novos} contas incluídas na fila como {args.lote}.")


def cmd_mudar(args) -> None:
    """liberar: em espera/conferir -> a enviar. segurar: a enviar -> em espera. Aceita contas, chaves ou --lote."""
    estado = carregar_estado()
    destino = "a_enviar" if args.cmd == "liberar" else "segurar"
    origem = {"segurar", "confirmar"} if destino == "a_enviar" else {"a_enviar"}
    mudou = []
    for it in estado["fila"]:
        alvo = (args.lote and it.get("lote") == args.lote and it["situacao"] != "confirmar") or \
               (it.get("conta") in args.itens or it.get("chave") in args.itens)
        if alvo and it["situacao"] in origem:
            it["situacao"] = destino
            if args.motivo:
                it["obs"] = args.motivo
            mudou.append(it["nome"])
    estado["atualizado_em"] = agora().isoformat()
    gravar_json(ESTADO, estado)
    print(f"{len(mudou)} conta(s) -> {ROTULO[destino]}: " + ", ".join(mudou))


# ---------------------------------------------------------------- publicação

def publicar(mensagem: str) -> None:
    """Regenera o painel e manda o estado e o CRM para o GitHub (o ponto fixo fica disponível em qualquer sessão)."""
    def rodar(*cmd: str, ok: bool = False) -> subprocess.CompletedProcess:
        r = subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True)
        if r.returncode and not ok:
            sys.exit(f"Falhou: {' '.join(cmd)}\n{r.stdout}\n{r.stderr}")
        return r
    rodar(sys.executable, "painel.py")
    rodar("git", "add", "tentativas.json", "contas.json", "docs", "operacao", "analises")
    if not rodar("git", "diff", "--cached", "--quiet", ok=True).returncode:
        print("Nada novo para publicar.")
        return
    rodar("git", "commit", "-m", mensagem)
    if rodar("git", "push", ok=True).returncode:
        rodar("git", "pull", "--rebase")
        rodar("git", "push")
    print("Publicado no GitHub: estado, CRM e painel atualizados.")


def cmd_publicar(args) -> None:
    publicar(args.mensagem or f"Atualiza a operação de WhatsApp ({br(agora().date())})")


# ---------------------------------------------------------------- relatório

def _fontes():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    pares = [("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
             ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf")]
    for normal, negrito in pares:
        if Path(normal).exists() and Path(negrito).exists():
            pdfmetrics.registerFont(TTFont("Base", normal))
            pdfmetrics.registerFont(TTFont("Base-Bold", negrito))
            return "Base", "Base-Bold"
    return "Helvetica", "Helvetica-Bold"


MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
         "outubro", "novembro", "dezembro"]


import re as _re

# O relatório vai ao cliente como trabalho da equipe comercial da Raze. Nada de processo interno,
# ferramenta, automação, fonte de pesquisa ou dado pessoal. A ordem importa: frases longas antes das curtas.
_CLIENTE = [
    (r",? com autorização do Rodrigo", ""),
    (r"\s*\((?:o robô|o atendimento)[^)]*\)", ""),
    (r"\s*\((?:a|o) do CNES[^)]*\)", " (a unidade com gerador)"),
    (r"\s*\([^)]*(?:CNPJ|Receita|CNES)[^)]*\)", ""),
    (r"encerrou o atendimento automático em (\d\d/\d\d) por falta de interação", r"encerrou o atendimento eletrônico em \1 sem encaminhar a um atendente"),
    (r"\s*por (?:falta de interação|inatividade)", ""),
    (r"respondeu em (\d\d/\d\d) com assistente de IA que exige consentimento automático com os termos de uso e a política de privacidade para seguir",
     r"respondeu em \1 com atendimento eletrônico que pede cadastro prévio"),
    (r"; o robô exige [^.]*\.", "; o canal atende apenas condôminos cadastrados."),
    (r"\bo robô transferiu\b", "a mensagem foi transferida"),
    (r"\bo robô\b", "o atendimento eletrônico"),
    (r"\brobôs?\b", "atendimento eletrônico"),
    (r"A Raze não seguiu sem autorização\. ", ""),
    (r"decidir se aceita seguir pela (\w+) ou ligar", r"seguir pelo atendimento comercial (\1) ou ligar"),
    (r"\bCPF\b,?\s*", ""),
    (r"\bCNES\b", "cadastro oficial"),
    (r"\b[Qq]ualificar na conversa\b", "confirmar na conversa"),
    (r"\bSem prova de gerador: ", ""),
]


def para_cliente(texto: str, nome: str = "") -> str:
    t = texto or ""
    t = _re.sub(r"^[^:]{0,60}(respondeu|Resposta automática[^:]*) em \d\d/\d\d: ", "", t)
    if nome:  # tira o prefixo repetido "Imodata: ..." quando a nota já começa com o nome da conta
        t = _re.sub(r"^" + _re.escape(nome.split()[0]) + r"[^:]{0,25}:\s*", "", t)
    for a, b in _CLIENTE:
        t = _re.sub(a, b, t)
    return _re.sub(r"\s{2,}", " ", t).strip()


def cmd_relatorio(args) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, PageTemplate, Paragraph,
                                    Spacer, Table, TableStyle)

    estado = carregar_estado()
    dia = date.fromisoformat(args.data) if args.data else agora().date()
    arq = DIARIO / f"{dia.isoformat()}.jsonl"
    regs = [json.loads(l) for l in arq.read_text(encoding="utf-8").splitlines() if l.strip()] if arq.exists() else []

    F, FB = _fontes()
    PRETO, AMARELO, CINZA, CLARO = colors.HexColor("#111111"), colors.HexColor("#F5B800"), colors.HexColor("#5A5A5A"), colors.HexColor("#F3F3F3")
    h2 = ParagraphStyle("h2", fontName=FB, fontSize=12.5, leading=16, spaceBefore=10, spaceAfter=6, textColor=PRETO)
    body = ParagraphStyle("b", fontName=F, fontSize=9.2, leading=13, textColor=PRETO)
    cel = ParagraphStyle("c", fontName=F, fontSize=8.4, leading=11)
    celb = ParagraphStyle("cb", parent=cel, fontName=FB)
    kpi_n = ParagraphStyle("kn", fontName=FB, fontSize=20, leading=23)
    kpi_t = ParagraphStyle("kt", fontName=F, fontSize=7.8, leading=10, textColor=CINZA)
    data_ext = f"{dia.day} de {MESES[dia.month - 1]} de {dia.year}"

    def cabecalho(c, doc):
        w, h = A4
        c.saveState()
        c.setFillColor(PRETO); c.rect(0, h - 34 * mm, w, 34 * mm, fill=1, stroke=0)
        c.setFillColor(AMARELO); c.rect(0, h - 34 * mm, w, 1.2 * mm, fill=1, stroke=0)
        c.setFont(FB, 7.5); c.drawString(18 * mm, h - 12 * mm, "RAZE GERADORES · PROSPECÇÃO ATIVA · WHATSAPP")
        c.setFillColor(colors.white); c.setFont(FB, 18); c.drawString(18 * mm, h - 21 * mm, "Relatório de WhatsApp")
        c.setFont(F, 8.5); c.drawString(18 * mm, h - 27.5 * mm, f"{data_ext} · Rio de Janeiro e região metropolitana")
        c.setFillColor(CINZA); c.setFont(F, 7.2)
        c.drawString(18 * mm, 10 * mm, "Raze Geradores · Continuidade de energia crítica · Rio de Janeiro e região metropolitana")
        c.drawRightString(w - 18 * mm, 10 * mm, str(doc.page))
        c.restoreState()

    def tabela(linhas, larguras):
        dados = [[Paragraph(str(x), celb if i == 0 else cel) for x in l] for i, l in enumerate(linhas)]
        t = Table(dados, colWidths=[x * mm for x in larguras], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), CLARO), ("LINEBELOW", (0, 0), (-1, 0), 0.8, PRETO),
            ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor("#DDDDDD")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ]))
        return t

    # Uma linha por conta: ação de abertura do dia e resultado final do dia.
    def acao(r):
        res, antes = r["resultado"], r.get("antes", "")
        if res == "material_enviado": return "Material"
        if res in ("respondeu", "contato_obtido", "resposta_automatica", "recusou", "nao_contatar"): return "Resposta"
        if res == "followup": return "Acompanhamento"
        if antes == "1_tique": return "Reenvio"
        if res == "sem_whatsapp": return "Checagem"
        if antes in ("a_enviar", "segurar", "confirmar", ""): return "1ª mensagem"
        return "Atualização"
    por_conta: dict[str, dict] = {}
    for r in regs:
        if r["conta"] not in por_conta:
            por_conta[r["conta"]] = {"nome": r["nome"], "bairro": r.get("bairro", ""), "acoes": [], "final": r}
        pc = por_conta[r["conta"]]
        pc["acoes"].append(acao(r))
        pc["final"] = r
    linhas_dia = list(por_conta.values())
    ENVIO = {"enviado", "entregue", "1tique", "followup", "material_enviado"}
    enviados = [p for p in linhas_dia if any(x["resultado"] in ENVIO for x in regs if x["nome"] == p["nome"])]
    RESP = ("respondeu", "contato_obtido", "resposta_automatica", "recusou", "nao_contatar", "numero_errado")
    respostas = list({r["conta"]: r for r in regs if r["resultado"] in RESP}.values())
    indicados = [p for p in linhas_dia if any(x["resultado"] == "contato_obtido" or "indicou" in x.get("nota", "").lower()
                                              for x in regs if x["conta"] == p["final"]["conta"])]
    sem_wa = [p for p in linhas_dia if p["final"]["resultado"] == "sem_whatsapp"]
    primeiras = [p for p in linhas_dia if p["acoes"][0] == "1ª mensagem"]
    materiais = [p for p in linhas_dia if p["acoes"][0] == "Material"]
    reenvios = [p for p in linhas_dia if p["acoes"][0] == "Reenvio"]
    acompanha = [p for p in linhas_dia if p["acoes"][0] == "Acompanhamento"]

    def pl(n, um, varios):
        return f"{n} {um if n == 1 else varios}"

    s = []
    kpis = [(len(enviados), "mensagens enviadas"), (len(respostas), "respostas recebidas"),
            (len([r for r in respostas if r["resultado"] != "resposta_automatica"]), "respostas de pessoas"),
            (len(sem_wa), "números sem WhatsApp")]
    k = Table([[Paragraph(str(n), kpi_n) for n, _ in kpis], [Paragraph(t, kpi_t) for _, t in kpis]],
              colWidths=[43.5 * mm] * 4)
    k.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 2, AMARELO), ("TOPPADDING", (0, 0), (-1, 0), 6)]))
    s += [k, Spacer(1, 6)]

    s.append(Paragraph("Resumo", h2))
    if regs:
        detalhe = []
        if materiais: detalhe.append(pl(len(materiais), "apresentação enviada a quem a pediu", "apresentações enviadas a quem as pediu"))
        if reenvios: detalhe.append(pl(len(reenvios), "mensagem reenviada", "mensagens reenviadas"))
        if primeiras: detalhe.append(pl(len(primeiras), "primeira mensagem", "primeiras mensagens"))
        if acompanha: detalhe.append(pl(len(acompanha), "mensagem de acompanhamento", "mensagens de acompanhamento"))
        if respostas: detalhe.append(pl(len(respostas), "resposta recebida", "respostas recebidas"))
        if sem_wa: detalhe.append(pl(len(sem_wa), "número sem WhatsApp, encaminhado", "números sem WhatsApp, encaminhados") + " para ligação")
        s.append(Paragraph(f"Em {dia.strftime('%d/%m/%Y')}, a equipe comercial da Raze Geradores fez contato com "
                           f"{pl(len(linhas_dia), 'empresa', 'empresas')} por WhatsApp"
                           + (": " + ", ".join(detalhe) if detalhe else "") + ".", body))
    else:
        s.append(Paragraph(f"Não houve ação de WhatsApp registrada em {dia.strftime('%d/%m/%Y')}.", body))

    if linhas_dia:
        # Três grupos: quem respondeu, quem ainda está no prazo de responder e quem não respondeu.
        RESPONDEU = {"respondeu", "contato_obtido", "resposta_automatica", "recusou", "nao_contatar"}
        SEM_RETORNO = {"sem_whatsapp", "numero_errado", "1tique"}
        hist = {}  # resultados de cada conta em todos os dias até o do relatório
        for arq_d in sorted(DIARIO.glob("*.jsonl")):
            if arq_d.stem <= dia.isoformat():
                for l in arq_d.read_text(encoding="utf-8").splitlines():
                    if l.strip():
                        r0 = json.loads(l); hist.setdefault(r0["conta"], []).append(r0)

        def grupo(p):
            rs = hist.get(p["final"]["conta"], [])
            if any(x["resultado"] in RESPONDEU for x in rs):
                return "respondeu"
            if p["final"]["resultado"] in SEM_RETORNO:
                return "sem_retorno"
            datas = [x["quando"][:10] for x in rs] + primeiro_crm.get(p["final"]["conta"], [])
            primeira = min(datas) if datas else dia.isoformat()
            return "sem_retorno" if primeira < dia.isoformat() else "aguardando"

        # O diário começou em 09/11; os contatos de outubro estão no CRM (tentativas.json).
        primeiro_crm = {}
        for t in json.loads((RAIZ / "tentativas.json").read_text(encoding="utf-8")):
            if "WhatsApp" in (t.get("qualificacao", "") + t.get("canal", "")):
                primeiro_crm.setdefault(t["conta"], []).append(t["quando"][:10])

        TITULOS = [("respondeu", "Empresas que responderam"),
                   ("aguardando", "Aguardando resposta (contato feito no dia)"),
                   ("sem_retorno", "Não responderam (seguem por nova tentativa ou telefone)")]
        for chave, titulo in TITULOS:
            grupo_p = [p for p in linhas_dia if grupo(p) == chave]
            if not grupo_p:
                continue
            linhas = [["Empresa", "Bairro", "Ação", "Resultado", "Próximo passo"]]
            for p in grupo_p:
                r = p["final"]
                it = achar(estado, r["conta"]) or {}
                acoes = " + ".join(dict.fromkeys(p["acoes"]))
                linhas.append([f"<b>{p['nome']}</b>", p["bairro"], acoes, para_cliente(RESULTADOS[r["resultado"]][0]),
                               f"{para_cliente(it.get('proximo', RESULTADOS[r['resultado']][4]))} ({br(it.get('prazo'))})"])
            s.append(Paragraph(f"{titulo} · {len(grupo_p)}", h2))
            s.append(tabela(linhas, [40, 23, 33, 32, 46]))

    if respostas:
        bloco = [Paragraph("Respostas e contatos", h2)]
        for r in respostas:
            nota = para_cliente(r["nota"], r["nome"])
            bloco.append(Paragraph(f"<b>{r['nome']}</b>: {nota}", body))
            bloco.append(Spacer(1, 3))
        s.append(KeepTogether(bloco))

    contagem: dict[str, int] = {}
    for it in estado["fila"]:
        contagem[it["situacao"]] = contagem.get(it["situacao"], 0) + 1
    ordem = ["respondeu", "contato_obtido", "resposta_automatica", "material_enviado", "material_pendente", "entregue",
             "followup", "enviado", "1_tique", "sem_whatsapp", "numero_errado", "a_enviar", "segurar", "confirmar",
             "recusou", "nao_contatar"]
    # Telefones que a própria empresa confirmou (respondeu em nome dela ou indicou o número).
    conf = [(it["nome"], t["numero"], t["como"]) for it in estado["fila"] for t in it.get("telefones_confirmados", [])]
    if conf:
        linhas = [["Empresa", "Telefone", "Confirmação"]]
        anterior = None
        for nome, num, como in conf:
            linhas.append([f"<b>{nome}</b>" if nome != anterior else "", num, como])
            anterior = nome
        s.append(Paragraph(f"Telefones confirmados pelas empresas · {len({c[0] for c in conf})} empresas", h2))
        s.append(tabela(linhas, [62, 30, 82]))

    # Para o cliente: situação de toda empresa já contatada, pela última ação registrada.
    # Quem saiu da lista ativa depois do contato continua contado como contatado.
    internos = {"a_enviar", "segurar", "confirmar"}
    contagem = {}
    ultimo = {}
    for arq_d in sorted(DIARIO.glob("*.jsonl")):
        if arq_d.stem > dia.isoformat():
            continue
        for l in arq_d.read_text(encoding="utf-8").splitlines():
            if l.strip():
                r = json.loads(l); ultimo[r["conta"]] = RESULTADOS[r["resultado"]][3]
    for it in estado["fila"]:
        sit = it["situacao"]
        if sit in internos:
            sit = ultimo.get(it.get("conta")) or ultimo.get(it["chave"]) or sit
        if sit not in internos:
            contagem[sit] = contagem.get(sit, 0) + 1
    ordem = [k for k in ordem if k not in internos]
    linhas = [["Situação", "Empresas"]] + [[para_cliente(ROTULO[k]), str(contagem[k])] for k in ordem if contagem.get(k)]
    total = sum(contagem.get(k, 0) for k in ordem)
    linhas.append(["<b>Total de empresas já contatadas</b>", f"<b>{total}</b>"])
    s.append(KeepTogether([Paragraph("Situação das empresas contatadas", h2), tabela(linhas, [120, 54])]))

    g = acoes_do_dia(estado, somar_dias_uteis(dia, 1))
    passos = []
    if g["responder"]: passos.append(f"Dar sequência a {pl(len(g['responder']), 'conversa aberta', 'conversas abertas')}: " + ", ".join(i["nome"] for i in g["responder"][:6]) + ".")
    if g["material"]: passos.append(f"Enviar o material prometido a {pl(len(g['material']), 'conta', 'contas')}: " + ", ".join(i["nome"] for i in g["material"]) + ".")
    if g["reenviar"]: passos.append(f"Reenviar {pl(len(g['reenviar']), 'mensagem não entregue', 'mensagens não entregues')}.")
    if g["followup"]: passos.append(f"Acompanhamento de {pl(len(g['followup']), 'conta', 'contas')} com mensagem entregue e sem resposta.")
    if g["novos"]: passos.append(f"Primeiro contato com mais {pl(min(len(g['novos']), 15), 'empresa selecionada', 'empresas selecionadas')}.")
    if g["voz"] or g["esgotados"]: passos.append(f"Ligar para {pl(len(g['voz']) + len(g['esgotados']), 'empresa', 'empresas')} sem WhatsApp ou sem resposta após três mensagens.")
    if g["espera"]: passos.append("Ampliar a prospecção para novas empresas do perfil da Raze.")
    if passos:
        s.append(KeepTogether([Paragraph(f"Próximos passos · {br(somar_dias_uteis(dia, 1))}", h2)] +
                              [Paragraph("• " + p, body) for p in passos]))

    ANALISES.mkdir(exist_ok=True)
    saida = ANALISES / f"Relatorio_WhatsApp_Raze_{dia.strftime('%d-%m-%Y')}.pdf"
    doc = BaseDocTemplate(str(saida), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                          topMargin=42 * mm, bottomMargin=18 * mm, title=f"Relatório de WhatsApp · Raze Geradores · {br(dia)}")
    doc.addPageTemplates([PageTemplate(id="p", frames=[Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")], onPage=cabecalho)])
    doc.build(s)
    print(saida)


# ---------------------------------------------------------------- linha de comando

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("status"); a.add_argument("--data"); a.add_argument("--json", action="store_true"); a.set_defaults(f=cmd_status)
    a = sub.add_parser("registrar"); a.add_argument("conta"); a.add_argument("resultado")
    a.add_argument("--nota"); a.add_argument("--prazo"); a.add_argument("--contato"); a.add_argument("--quando")
    a.add_argument("--publicar", action="store_true"); a.set_defaults(f=cmd_registrar)
    a = sub.add_parser("relatorio"); a.add_argument("--data"); a.set_defaults(f=cmd_relatorio)
    a = sub.add_parser("publicar"); a.add_argument("--mensagem"); a.set_defaults(f=cmd_publicar)
    a = sub.add_parser("incluir"); a.add_argument("csv"); a.add_argument("--lote", required=True)
    a.add_argument("--situacao", default="segurar", choices=["segurar", "a_enviar"]); a.set_defaults(f=cmd_incluir)
    for nome in ("liberar", "segurar"):
        a = sub.add_parser(nome); a.add_argument("itens", nargs="*"); a.add_argument("--lote"); a.add_argument("--motivo")
        a.set_defaults(f=cmd_mudar)
    args = p.parse_args()
    args.f(args)


if __name__ == "__main__":
    main()
