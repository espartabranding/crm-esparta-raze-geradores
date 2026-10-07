"""Monta a carteira de contas da Raze Geradores (contas.json) para o painel de ligação.

Lê as listas de prospecção em CSV (pasta em ORIGEM, trocável pela variável de
ambiente RAZE_PROSPECCAO) e grava contas.json ao lado deste script, no formato
que o painel lê: {"eixos": [...], "contas": [...]}, UTF-8, em uma linha.

Uso:  python montar_carteira.py

QUEM ENTRA
  1. lugares_raze.csv: confere == "S" e com telefone. Condominios -> "Condomínios"
     (categoria "Centro comercial" vai para "Comércio e centros comerciais": é
     condomínio comercial); Postos -> "Postos de combustível"; Comercio de
     supermercado, atacadista, mercado, hortifruti e alimentos -> "Supermercados e
     cadeia fria"; demais -> "Comércio e centros comerciais". Categoria de
     imobiliária é descartada.
  2. carteiras_de_administradoras_raze.csv: as 40 com mais prédios no foco, com
     nome e telefone -> "Administradoras de condomínios".
  3. saude_criticidade_raze.csv: privado ou filantrópico, criticidade >= 4, com
     telefone, município na praça -> as 40 de maior criticidade (desempate por
     leitos) -> "Saúde". Sai quem o CNES marca como privado mas é público pelo
     próprio dado (e-mail .gov.br ou "municipal" no nome).
  Deduplicação por CNPJ e por nome + telefone.

PONTUAÇÃO (determinística; nenhum fato é inventado)
  fit = [carga que não pode cair, exigência de norma, porte, acesso ao decisor], 1 a 3
    carga   Saúde: 3 com UTI ou centro cirúrgico, senão 2. Supermercados: 3.
            Condomínios: 3 com 300+ domicílios, senão 2. Administradoras e
            comércio: 2. Postos: 2.
    norma   Saúde: 3. Condomínios: 3 com 100+ domicílios, senão 2.
            Administradoras: 3 com 10+ prédios no foco, senão 2. Supermercados e
            comércio: 2. Postos: 1 (sem obrigação legal levantada).
    porte   Saúde por leitos (150 / 50). Condomínios por domicílios (300 / 100)
            ou, sem esse dado, por avaliações no Google (200 / 30).
            Administradoras por prédios na carteira (40 / 10). Supermercados por
            avaliações (1000 / 200). Comércio e postos por avaliações (500 / 100).
    acesso  1 = contato duvidoso: casamento "só endereço", 0800, telefone de
            outra UF (do Google ou da Receita), número fora do padrão ou DDD
            presumido. 3 = telefone bom e e-mail ou site próprios (não
            compartilhados com outra conta, nem de provedor ou rede social).
            2 = só o telefone.
  ader = base do segmento (ADER_BASE), na ordem de EIXOS, com ajuste pelo fit:
    porte 3: +1 em diagnóstico, ensaio e SLA; porte 1: -1 em ensaio, preventiva
    e SLA; norma 3: +1 em laudos; carga 3: +1 em ensaio. Limite de 0 a 10.
  onda
    s1 e s2: cotas de COTA_ONDA por segmento (5 administradoras, 5 condomínios,
    3 saúde, 2 supermercados em cada), só contas no foco, com contato não
    duvidoso e sem repetir telefone, ordenadas por soma do fit e depois pelo dado de porte.
    validar: até 10 contas com contato duvidoso e carga + norma + porte >= 7,
    no máximo 3 por segmento. O resto é base.
"""

import csv
import json
import os
import re
import unicodedata
from collections import Counter
from pathlib import Path

ORIGEM = Path(os.environ.get(
    "RAZE_PROSPECCAO",
    r"C:\Users\Rodrigo\Desktop\Projetos_Claude\Painel_Raze\painel_raze\output\prospeccao",
))
SAIDA = Path(__file__).with_name("contas.json")

EIXOS = ["Diagnóstico de prontidão", "Ensaio sob carga", "Manutenção preventiva",
         "Laudos e conformidade", "SLA de emergência", "Corretiva e retrofit de QTA"]

CONDO, ADM, SAUDE = "Condomínios", "Administradoras de condomínios", "Saúde"
FRIO, COMERCIO, POSTO = ("Supermercados e cadeia fria", "Comércio e centros comerciais",
                         "Postos de combustível")
# Ordem do ICP da Raze: canal e condomínio, saúde, cadeia fria; o resto é oportunista.
ORDEM_ICP = [ADM, CONDO, SAUDE, FRIO, COMERCIO, POSTO]

COMBO = {CONDO: "P1 Prontidão Residencial", ADM: "P1 Prontidão Residencial",
         SAUDE: "P2 Prontidão Hospitalar", FRIO: "P3 Prontidão Industrial",
         COMERCIO: "P4 Prontidão Comercial", POSTO: "P4 Prontidão Comercial"}

DIAG = "Diagnóstico de Prontidão"
ENSAIO = "Ensaios de desempenho sob carga"
PREV = "Manutenção preventiva contratada"
CORR = "Manutenção corretiva e retrofit de QTA"
AUTOV = "Laudo de autovistoria predial e de abrangência"
RDC50 = "Conformidade RDC 50 para estabelecimentos de saúde"
NR10 = "Prontuário de Instalações Elétricas — NR-10"
RELAT = "Relatório técnico e histórico de tendência"
SLA = "SLA de emergência e apoio à decisão (dossiê de assembleia)"

# (produtos, complementares) por segmento; todo produtos começa pelo diagnóstico.
SERVICOS = {
    CONDO: ([DIAG, PREV, AUTOV], [ENSAIO, SLA, RELAT]),
    ADM: ([DIAG, PREV, AUTOV, SLA], [ENSAIO, RELAT, CORR]),
    SAUDE: ([DIAG, ENSAIO, RDC50, PREV], [SLA, RELAT, NR10]),
    FRIO: ([DIAG, ENSAIO, PREV], [NR10, SLA, RELAT]),
    COMERCIO: ([DIAG, PREV, AUTOV], [ENSAIO, NR10, SLA]),
    POSTO: ([DIAG, PREV], [CORR, RELAT]),
}

# Aderência de base por segmento, na ordem de EIXOS.
ADER_BASE = {
    CONDO: [9, 6, 8, 8, 6, 5],
    ADM: [9, 6, 9, 8, 7, 5],
    SAUDE: [9, 8, 8, 9, 9, 6],
    FRIO: [9, 7, 8, 6, 8, 6],
    COMERCIO: [8, 6, 7, 7, 6, 5],
    POSTO: [7, 4, 6, 3, 5, 4],
}

COTA_ONDA = {ADM: 5, CONDO: 5, SAUDE: 3, FRIO: 2}  # por onda (s1 e s2): 15 contas
MAX_VALIDAR, MAX_VALIDAR_SEGMENTO = 10, 3
TOP_ADM, TOP_SAUDE, CRITICIDADE_MINIMA = 40, 40, 4

PRACA = {"Rio de Janeiro", "Niterói", "São Gonçalo", "Duque de Caxias", "Nova Iguaçu",
         "São João de Meriti", "Belford Roxo", "Nilópolis", "Mesquita", "Queimados",
         "Japeri", "Magé", "Guapimirim", "Itaboraí", "Maricá", "Tanguá", "Rio Bonito",
         "Cachoeiras de Macacu", "Itaguaí", "Seropédica", "Paracambi", "Petrópolis"}
DDD_RJ = {"21", "22", "24"}
DDD_MUNICIPIO = {"Petrópolis": "24"}  # os demais municípios da praça usam 21

CATEGORIA_FRIO = ("supermercado", "atacad", "mercado", "hortifruti", "agricola", "alimento",
                  "mercearia", "acougue", "frigorifico")
CATEGORIA_FORA = ("imobiliaria",)
NAO_E_SITE = ("instagram.com", "facebook.com", "wa.me", "linktr.ee", "whatsapp.com")
PROVEDORES = {"gmail.com", "gmail.com.br", "yahoo.com.br", "yahoo.com", "hotmail.com",
              "outlook.com", "ig.com.br", "uol.com.br", "terra.com.br", "bol.com.br",
              "globo.com", "infolink.com.br", "uninet.com.br", "mundivox.com.br",
              "compuland.com.br"}
TERCEIROS = ("contab", "contador", "oabrj")  # domínio do contador ou do advogado
BAIRRO_INVALIDO = {"frente"}

SIGLAS = {"CIPA", "APSA", "BNI", "CBRE", "SPE", "AVR", "PMA", "CHN", "HNSA", "SA", "S.A.",
          "S/A", "RJ", "HFLEX", "4D", "SMS", "UTI", "II", "III", "ME", "EPP"}
MINUSCULAS = {"de", "da", "do", "das", "dos", "e", "em", "na", "no"}
ACENTOS = {
    "administracao": "Administração", "condominios": "Condomínios", "condominio": "Condomínio",
    "imoveis": "Imóveis", "servicos": "Serviços", "tecnicos": "Técnicos", "negocios": "Negócios",
    "gestao": "Gestão", "imobiliaria": "Imobiliária", "imobiliarios": "Imobiliários",
    "precisao": "Precisão", "maua": "Mauá", "pacifica": "Pacífica", "eficacia": "Eficácia",
    "solucoes": "Soluções", "participacoes": "Participações", "consorcio": "Consórcio",
    "atlantida": "Atlântida", "locacao": "Locação", "intermediacao": "Intermediação",
    "saude": "Saúde", "sao": "São", "clinica": "Clínica", "clinicas": "Clínicas",
    "clinico": "Clínico", "gloria": "Glória", "lucia": "Lúcia", "fatima": "Fátima",
    "jose": "José", "goncalo": "Gonçalo", "iguacu": "Iguaçu", "itaguai": "Itaguaí",
    "niteroi": "Niterói", "meier": "Méier", "beneficencia": "Beneficência",
    "petropolis": "Petrópolis", "assistencia": "Assistência", "medica": "Médica",
    "cardiaco": "Cardíaco", "universitario": "Universitário", "antonio": "Antônio",
    "lourenco": "Lourenço", "providencia": "Providência", "jacarepagua": "Jacarepaguá",
    "humaita": "Humaitá", "gavea": "Gávea", "taua": "Tauá", "cristovao": "Cristóvão",
    "basileia": "Basileia", "botanico": "Botânico", "california": "Califórnia",
    "paraiso": "Paraíso", "valparaiso": "Valparaíso", "icarai": "Icaraí", "inga": "Ingá",
    "sebastiao": "Sebastião", "conceicao": "Conceição", "joao": "João", "tres": "Três",
    "ortopedico": "Ortopédico", "cirurgica": "Cirúrgica", "coracao": "Coração",
    "oncologico": "Oncológico", "psiquiatrica": "Psiquiátrica", "nilopolis": "Nilópolis",
    "itaborai": "Itaboraí", "marica": "Maricá", "andarai": "Andaraí", "grajau": "Grajaú",
    "pediatrico": "Pediátrico", "dor": "D'Or", "jaguare": "Jaguaré", "sindica": "Síndica",
    "patricia": "Patrícia", "guimaraes": "Guimarães", "recrerio": "Recreio", "evangelico": "Evangélico", "israelita": "Israelita",
}


# ---------------------------------------------------------------- utilitários

def ler(arquivo):
    with open(ORIGEM / arquivo, encoding="utf-8-sig", newline="") as f:
        return [{k: (v or "").strip() for k, v in linha.items()}
                for linha in csv.DictReader(f, delimiter=";")]


def sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower())
                   if unicodedata.category(c) != "Mn")


def inteiro(valor):
    try:
        return int(float(valor.replace(",", ".")))
    except ValueError:
        return 0


def milhar(n):
    return f"{n:,}".replace(",", ".")


def plural(n, um, varios):
    return f"{milhar(n)} {um if n == 1 else varios}"


def caixa_normal(texto):
    """Nome em caixa alta da Receita ou do CNES -> caixa normal, com os acentos
    das palavras do dicionário ACENTOS."""
    saida = []
    for i, palavra in enumerate(texto.split()):
        nucleo = palavra.strip(".,()-")
        chave = sem_acento(nucleo)
        if chave in ACENTOS and nucleo:
            palavra = palavra.replace(nucleo, ACENTOS[chave])
        elif palavra.upper() in SIGLAS or nucleo.upper() in SIGLAS:
            palavra = palavra.upper()
        elif i and chave in MINUSCULAS:
            palavra = palavra.lower()
        elif nucleo.isalpha() and not re.search(r"[aeiouy]", chave):
            palavra = palavra.upper()  # sem vogal: sigla
        else:
            palavra = palavra.capitalize()
        saida.append(palavra)
    return " ".join(saida)


def telefone(bruto, municipio="Rio de Janeiro"):
    """Devolve (telefone formatado, motivo da dúvida ou "")."""
    d = re.sub(r"\D", "", bruto)
    if d.startswith("55") and len(d) >= 12:
        d = d[2:]
    if d.startswith("55") and len(d) == 10 and bruto.startswith("+55"):
        d = d[2:]  # "+55 42590230": sem DDD
    if d.startswith("0800") or (d.startswith("800") and len(d) == 10):
        d = d[-10:] if d.startswith("800") else d[1:]
        return f"0800 {d[3:6]} {d[6:]}", "0800 de central de atendimento"
    d = d.lstrip("0")
    motivo = ""
    if len(d) in (8, 9):
        d = DDD_MUNICIPIO.get(municipio, "21") + d
        motivo = "DDD presumido pelo município"
    if len(d) not in (10, 11):
        return bruto, "número fora do padrão"
    ddd, numero = d[:2], d[2:]
    if ddd not in DDD_RJ:
        motivo = motivo or "telefone de outra UF"
    elif len(set(numero)) <= 2:
        motivo = "número de preenchimento"
    elif len(numero) == 8 and numero[0] not in "2345":
        motivo = "celular sem o nono dígito"
    elif len(numero) == 9 and numero[0] != "9":
        motivo = "número fora do padrão"
    return f"({ddd}) {numero[:-4]}-{numero[-4:]}", motivo


def dominio_de(url_ou_email):
    d = url_ou_email.lower().split("@")[-1]
    d = re.sub(r"^https?://", "", d).split("/")[0].split("?")[0]
    return re.sub(r"^www\.", "", d)


def dominio_proprio(d):
    return bool(d) and d not in PROVEDORES and not any(t in d for t in TERCEIROS) \
        and not any(n in d for n in NAO_E_SITE)


def lista(itens):
    return ", ".join(itens[:-1]) + (" e " if len(itens) > 1 else "") + itens[-1] if itens else ""


def faixa(valor, alto, medio):
    return 3 if valor >= alto else 2 if valor >= medio else 1


def no_bairro(bairro, cidade):
    return f"no bairro {bairro}, {cidade}" if bairro else f"em {cidade}"


def sinal_google(avaliacoes, nota):
    base = "Conta da base, ainda sem pesquisa individual."
    if avaliacoes:
        base += f" No Google: {plural(avaliacoes, 'avaliação', 'avaliações')}"
        base += f", nota {nota.replace('.', ',')}." if nota else "."
    return base


# ------------------------------------------------------------------- fontes

def contas_de_lugares():
    linhas = [l for l in ler("lugares_raze.csv") if l["confere"] == "S" and l["telefone"]]
    condominios = ler("condominios_com_google_raze.csv")
    domicilios = {}
    for c in condominios:  # casa por CNPJ; o link do Google é a segunda chave
        n = inteiro(c["domicilios_no_predio"])
        for chave in (c["cnpj"], c["link_google"]):
            if chave and n:
                domicilios.setdefault(chave, n)
    # Site ou e-mail que aparece em mais de uma conta é canal de rede, não do local.
    repetidos = Counter()
    for l in linhas:
        repetidos.update({dominio_de(l["site"])} if l["site"] else set())
        repetidos.update({e.strip().lower() for e in l["emails"].split(",") if e.strip()})

    contas = []
    for l in linhas:
        categoria = sem_acento(l["categoria"])
        if any(t in categoria for t in CATEGORIA_FORA):
            continue
        if l["segmento"] == "Postos":
            segmento = POSTO
        elif l["segmento"] == "Condominios":
            segmento = COMERCIO if "comercial" in categoria else CONDO
        elif any(t in categoria for t in CATEGORIA_FRIO):
            segmento = FRIO
        else:
            segmento = COMERCIO

        fone, duvida = telefone(l["telefone"], l["cidade"])
        if duvida:  # 0800 ou número ruim: usa um telefone local de outros_telefones, se houver
            for outro in l["outros_telefones"].split(","):
                fone2, duvida2 = telefone(outro, l["cidade"]) if outro.strip() else ("", "x")
                if not duvida2:
                    fone, duvida = fone2, ""
                    break
        if l["casamento"] == "só endereço":
            duvida = duvida or "CNPJ casado só pelo endereço"
        _, duvida_receita = telefone(l["telefone_receita"]) if l["telefone_receita"] else ("", "")
        if duvida_receita == "telefone de outra UF":
            duvida = duvida or "telefone da Receita em outra UF (matriz)"

        site = l["site"] if l["site"] and not any(n in l["site"] for n in NAO_E_SITE) else ""
        emails = [e.strip().lower() for e in l["emails"].split(",") if e.strip()]
        canal_proprio = (site and repetidos[dominio_de(site)] == 1) or \
            any(repetidos[e] == 1 and dominio_proprio(dominio_de(e)) for e in emails)

        avaliacoes = inteiro(l["avaliacoes"])
        dom = domicilios.get(l["cnpj"]) or domicilios.get(l["link"]) or 0
        if segmento != CONDO:
            dom = 0
        bairro = l["bairro"]
        if re.search(r"\d", bairro) or sem_acento(bairro) in BAIRRO_INVALIDO:
            bairro = ""
        onde = no_bairro(bairro, l["cidade"])
        google = f"{plural(avaliacoes, 'avaliação', 'avaliações')} no Google" if avaliacoes else ""

        if segmento == CONDO:
            carga, norma = (3 if dom >= 300 else 2), (3 if dom >= 100 else 2)
            porte = faixa(dom, 300, 100) if dom else faixa(avaliacoes, 200, 30)
            porte_txt = f"{plural(dom, 'domicílio', 'domicílios')} no prédio" if dom else "a confirmar"
            if dom:
                angulo = (f"Prédio com {plural(dom, 'domicílio', 'domicílios')}: elevadores, bombas e áreas "
                          "comuns dependem da energia de emergência, e a gestão precisa de registro "
                          "medido de que o sistema sustenta essa carga.")
            else:
                angulo = (f"Condomínio residencial {onde}: elevadores e bombas dependem da energia de "
                          "emergência, e o ensaio sob carga com laudo é o registro de que o sistema responde.")
            gancho = ("Quando o gerador do condomínio é testado, o ensaio é feito com carga e fica registrado em laudo?"
                      if porte == 3 else "Há registro do último ensaio do gerador do condomínio feito sob carga?")
        elif segmento == FRIO:
            carga, norma, porte = 3, 2, faixa(avaliacoes, 1000, 200)
            porte_txt = {"ME": "Microempresa (Receita)", "EPP": "Empresa de pequeno porte (Receita)",
                         "Demais": "Acima de pequeno porte (Receita)"}.get(l["porte"], "a confirmar")
            angulo = (f"{l['categoria']} {onde}" + (f", com {google}" if google else "") +
                      ": refrigeração e perecíveis dependem da energia de emergência, e a autonomia "
                      "medida em ensaio mostra por quanto tempo a loja se sustenta.")
            gancho = ("Há registro de quanto tempo o gerador sustenta a refrigeração da loja em operação?"
                      if porte >= 2 else "Há registro do último ensaio do gerador da loja feito sob carga?")
        elif segmento == COMERCIO:
            carga, norma, porte = 2, 2, faixa(avaliacoes, 500, 100)
            porte_txt = "a confirmar"
            angulo = (f"{l['categoria']} {onde}" + (f", com {google}" if google else "") +
                      ": elevadores, climatização e salas dependem da energia de emergência do "
                      "edifício, e o ensaio sob carga registra se ela sustenta a operação.")
            gancho = "Há registro do último ensaio do gerador do edifício feito sob carga?"
        else:
            carga, norma, porte = 2, 1, faixa(avaliacoes, 500, 100)
            porte_txt = {"ME": "Microempresa (Receita)", "EPP": "Empresa de pequeno porte (Receita)",
                         "Demais": "Acima de pequeno porte (Receita)"}.get(l["porte"], "a confirmar")
            angulo = (f"Posto de combustível {onde}: bombas, pista e loja dependem de energia para "
                      "operar, e a prontidão medida mostra se o sistema de emergência assume a carga.")
            gancho = "O posto conta com gerador para manter bombas e loja em operação durante uma falta de energia?"

        acesso = 1 if duvida else 3 if canal_proprio else 2
        detalhe = porte_txt if dom else google
        conta = {
            "empresa": l["nome"], "cidade": l["cidade"], "segmento": segmento,
            "fit": [carga, norma, porte, acesso],
            "angulo": angulo, "gancho": gancho, "telefone": fone, "site": site, "porte": porte_txt,
            "perfil": [f"{l['categoria']} {onde}" + (f", com {detalhe}" if detalhe else "") + "."],
            "sinal": sinal_google(avaliacoes, l["nota"]),
            "fontes": [{"t": "Google Maps", "u": l["link"]}] if l["link"] else [],
            "cnpj": l["cnpj"], "bairro": bairro, "email": emails[0] if emails else "",
            "_foco": l["foco"] == "S", "_duvida": duvida, "_peso": (dom, avaliacoes),
        }
        contas.append(conta)
    return contas


def contas_de_administradoras():
    linhas = [l for l in ler("carteiras_de_administradoras_raze.csv")
              if l["administradora"] and l["telefone"]]
    linhas.sort(key=lambda l: (-inteiro(l["predios_no_foco"]), -inteiro(l["predios"]), l["administradora"]))
    contas = []
    for l in linhas[:TOP_ADM]:
        predios, no_foco = inteiro(l["predios"]), inteiro(l["predios_no_foco"])
        fone, duvida = telefone(l["telefone"])
        proprio = dominio_proprio(l["dominio"])
        carteira = f"{plural(predios, 'prédio', 'prédios')}, {milhar(no_foco)} em bairros de foco"
        bairros = lista([caixa_normal(b.strip()) for b in l["bairros"].split(",")[:3] if b.strip()])
        contas.append({
            "empresa": caixa_normal(l["administradora"]), "cidade": "Rio de Janeiro", "segmento": ADM,
            "fit": [2, 3 if no_foco >= 10 else 2, faixa(predios, 40, 10),
                    1 if duvida else 3 if proprio and l["email"] else 2],
            "angulo": (f"Carteira de {plural(predios, 'prédio', 'prédios')}, {milhar(no_foco)} em bairros de foco: "
                       "um padrão único de prontidão medida e documentada atende todos os condomínios "
                       "administrados e dá lastro às assembleias."),
            "gancho": ("Como a administradora acompanha hoje a prontidão dos geradores dos prédios da carteira?"
                       if predios >= 10 else
                       "Os condomínios que a empresa administra têm registro de ensaio do gerador feito sob carga?"),
            "telefone": fone, "site": f"https://{l['dominio']}" if proprio else "",
            "porte": f"{plural(predios, 'prédio', 'prédios')} na carteira levantada",
            "perfil": [f"Administradora de condomínios no Rio de Janeiro, com carteira levantada de {carteira}"
                       + (f"; atuação em {bairros}." if bairros else ".")],
            "sinal": f"Conta da base, ainda sem pesquisa individual. Na carteira levantada: {carteira}.",
            "fontes": [{"t": l["dominio"], "u": f"https://{l['dominio']}"}] if l["dominio"] else [],
            "cnpj": l["cnpj_administradora"], "bairro": "", "email": l["email"].lower(),
            "_foco": no_foco > 0, "_duvida": duvida, "_peso": (no_foco, predios),
        })
    return contas


def contas_de_saude():
    linhas = []
    for l in ler("saude_criticidade_raze.csv"):
        publico = l["email"].lower().endswith(".gov.br") or "municipal" in sem_acento(l["nome"])
        if l["setor"] in ("privado", "filantrópico") and inteiro(l["criticidade"]) >= CRITICIDADE_MINIMA \
                and l["telefone"] and l["municipio"] in PRACA and not publico:
            linhas.append(l)
    linhas.sort(key=lambda l: (-inteiro(l["criticidade"]), -inteiro(l["leitos"]), l["nome"]))
    linhas = linhas[:TOP_SAUDE]
    repetidos = Counter(l["email"].lower() for l in linhas if l["email"])
    contas = []
    for l in linhas:
        leitos, uti, crit = inteiro(l["leitos"]), inteiro(l["uti"]), inteiro(l["criticidade"])
        cirurgico, plantao = l["centro_cirurgico"] == "S", l["plantao_24h"] == "S"
        fone, duvida = telefone(l["telefone"], l["municipio"])
        email = l["email"].lower()
        proprio = email and repetidos[email] == 1 and dominio_proprio(dominio_de(email))
        dados = [plural(leitos, "leito", "leitos")] if leitos else []
        if uti:
            dados.append(f"{milhar(uti)} de UTI")
        if cirurgico:
            dados.append("centro cirúrgico")
        if plantao:
            dados.append("plantão 24h")
        dados_txt = lista(dados)
        bairro = caixa_normal(l["bairro"])
        tipo = l["tipo"].capitalize()
        critica = uti or cirurgico
        contas.append({
            "empresa": caixa_normal(l["nome"]), "cidade": l["municipio"], "segmento": SAUDE,
            "fit": [3 if critica else 2, 3, faixa(leitos, 150, 50), 1 if duvida else 3 if proprio else 2],
            "angulo": (f"{tipo} com {dados_txt}: " if dados_txt else f"{tipo}: ") +
                      ("a energia de emergência sustenta área crítica, e a prontidão precisa estar "
                       "comprovada por ensaio sob carga, partida cronometrada e laudo." if critica else
                       "a energia de emergência sustenta a assistência, e o ensaio sob carga com laudo "
                       "documenta a prontidão do sistema."),
            "gancho": ("Como o hospital registra hoje os ensaios do gerador sob carga e o tempo de partida?"
                       if critica else "Há registro do último ensaio do gerador feito sob carga?"),
            "telefone": fone, "site": "",
            "porte": plural(leitos, "leito", "leitos") + (f", {milhar(uti)} de UTI" if uti else "") if leitos else "a confirmar",
            "perfil": [f"{tipo} {l['setor']} {no_bairro(bairro, l['municipio'])}"
                       + (f", com {dados_txt}" if dados_txt else "") + " (CNES)."],
            "sinal": ("Conta da base, ainda sem pesquisa individual. No CNES: criticidade "
                      f"{crit} de 6" + (f", {dados_txt}." if dados_txt else ".")),
            "fontes": [{"t": "CNES", "u": "https://cnes.datasus.gov.br/"}],
            "cnpj": l["cnpj"], "bairro": bairro, "email": email,
            "_foco": l["foco"] == "S", "_duvida": duvida, "_peso": (crit, leitos),
        })
    return contas


# ---------------------------------------------------------------- montagem

def deduplicar(contas):
    vistos_cnpj, vistos_nome_fone, unicas = set(), set(), []
    for c in contas:
        chave = (sem_acento(c["empresa"]), re.sub(r"\D", "", c["telefone"]))
        if (c["cnpj"] and c["cnpj"] in vistos_cnpj) or chave in vistos_nome_fone:
            continue
        vistos_cnpj.add(c["cnpj"])
        vistos_nome_fone.add(chave)
        unicas.append(c)
    return unicas


def aderencia(conta):
    carga, norma, porte, _ = conta["fit"]
    a = list(ADER_BASE[conta["segmento"]])
    if porte == 3:
        a[0] += 1; a[1] += 1; a[4] += 1
    if porte == 1:
        a[1] -= 1; a[2] -= 1; a[4] -= 1
    if norma == 3:
        a[3] += 1
    if carga == 3:
        a[1] += 1
    return [max(0, min(10, x)) for x in a]


def prioridade(conta):
    """Ordem dentro do segmento: foco, soma do fit, dado de porte, nome."""
    return (not conta["_foco"], -sum(conta["fit"]), tuple(-x for x in conta["_peso"]), conta["empresa"])


def definir_ondas(contas):
    for c in contas:
        c["onda"] = "base"
    for segmento, cota in COTA_ONDA.items():
        aptas, fones = [], set()
        for c in sorted(contas, key=prioridade):  # mesma central telefônica entra uma vez só
            if c["segmento"] == segmento and c["_foco"] and not c["_duvida"] and c["telefone"] not in fones:
                aptas.append(c)
                fones.add(c["telefone"])
        for c in aptas[:cota]:
            c["onda"] = "s1"
        for c in aptas[cota:2 * cota]:
            c["onda"] = "s2"
    duvidosas = sorted((c for c in contas if c["_duvida"] and sum(c["fit"][:3]) >= 7),
                       key=lambda c: (-sum(c["fit"][:3]), ORDEM_ICP.index(c["segmento"]), prioridade(c)))
    por_segmento, escolhidas = Counter(), 0
    for c in duvidosas:
        if escolhidas < MAX_VALIDAR and por_segmento[c["segmento"]] < MAX_VALIDAR_SEGMENTO:
            c["onda"] = "validar"
            por_segmento[c["segmento"]] += 1
            escolhidas += 1


def montar():
    contas = deduplicar(contas_de_administradoras() + contas_de_lugares() + contas_de_saude())
    definir_ondas(contas)
    contas.sort(key=lambda c: (["s1", "s2", "validar", "base"].index(c["onda"]),
                               ORDEM_ICP.index(c["segmento"]), prioridade(c)))
    carteira = []
    for i, c in enumerate(contas, 1):
        produtos, complementares = (list(x) for x in SERVICOS[c["segmento"]])
        if c["segmento"] == CONDO and c["fit"][2] == 3:  # prédio grande: ensaio entra na oferta
            produtos.append(ENSAIO)
            complementares.remove(ENSAIO)
        if c["_duvida"]:
            c["sinal"] += f" Contato a confirmar: {c['_duvida']}."
        conta = {
            "id": f"r{i}", "empresa": c["empresa"], "cidade": c["cidade"], "segmento": c["segmento"],
            "fit": c["fit"], "onda": c["onda"], "ader": aderencia(c),
            "produtos": produtos, "complementares": complementares,
            "angulo": c["angulo"], "gancho": c["gancho"], "telefone": c["telefone"], "site": c["site"],
            "porte": c["porte"], "perfil": c["perfil"], "sinal": c["sinal"], "fontes": c["fontes"],
            "proximo": "Não abordada", "combo": COMBO[c["segmento"]], "combo_secundario": "",
        }
        conta.update({k: c[k] for k in ("cnpj", "bairro", "email") if c[k]})
        carteira.append(conta)
    return carteira


def main():
    carteira = montar()
    SAIDA.write_text(json.dumps({"eixos": EIXOS, "contas": carteira}, ensure_ascii=False), encoding="utf-8")
    print(f"{len(carteira)} contas gravadas em {SAIDA}")
    for rotulo, campo in (("Por segmento", "segmento"), ("Por onda", "onda")):
        print(rotulo + ": " + ", ".join(f"{k} {v}" for k, v in Counter(c[campo] for c in carteira).items()))


if __name__ == "__main__":
    main()
