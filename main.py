"""Sincroniza as ligações de uma campanha do Callix para um banco local."""

import argparse
import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

import conversa
from callix import Callix
from painel import gerar as gerar_painel

DADOS = Path(__file__).parent / "data"
AUDIOS = DADOS / "audio"

SCHEMA = """
CREATE TABLE IF NOT EXISTS chamadas (
    id INTEGER NOT NULL,
    tipo TEXT NOT NULL,
    campanha_id INTEGER NOT NULL,
    iniciada_em TEXT,
    telefone TEXT,
    tempo_falado INTEGER,
    qualificacao TEXT,
    agente TEXT,
    audio_arquivo TEXT,
    atributos TEXT NOT NULL,
    relacionados TEXT NOT NULL,
    PRIMARY KEY (tipo, id)
)
"""


def salvar(db: sqlite3.Connection, tipo: str, campanha_id: int, chamada: dict) -> None:
    attrs, rel = chamada["attributes"], chamada["relacionados"]
    db.execute(
        """
        INSERT INTO chamadas (id, tipo, campanha_id, iniciada_em, telefone, tempo_falado,
                              qualificacao, agente, atributos, relacionados)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (tipo, id) DO UPDATE SET
            qualificacao = excluded.qualificacao,
            atributos = excluded.atributos,
            relacionados = excluded.relacionados
        """,
        (
            chamada["id"],
            tipo,
            campanha_id,
            attrs.get("started_at"),
            attrs.get("destination_phone"),
            attrs.get("service_duration"),
            rel.get("qualification", {}).get("name"),
            rel.get("agent", {}).get("name"),
            json.dumps(attrs, ensure_ascii=False),
            json.dumps(rel, ensure_ascii=False),
        ),
    )


def baixar_audios(db: sqlite3.Connection, callix: Callix) -> int:
    AUDIOS.mkdir(parents=True, exist_ok=True)
    pendentes = db.execute(
        "SELECT id, atributos FROM chamadas "
        "WHERE tipo = 'campaign_completed_calls' AND audio_arquivo IS NULL"
    ).fetchall()
    baixados = 0
    for chamada_id, atributos in pendentes:
        attrs = json.loads(atributos)
        if not attrs.get("has_audio") or not attrs.get("audio_link"):
            continue
        arquivo = AUDIOS / f"{chamada_id}.mp3"
        arquivo.write_bytes(callix.audio(attrs["audio_link"]))
        db.execute(
            "UPDATE chamadas SET audio_arquivo = ? WHERE tipo = ? AND id = ?",
            (arquivo.name, "campaign_completed_calls", chamada_id),
        )
        db.commit()
        baixados += 1
    return baixados


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dias", type=int, default=7, help="janela de busca (máx. 31)")
    parser.add_argument("--sem-audio", action="store_true", help="não baixar as gravações")
    parser.add_argument(
        "--sem-analise", action="store_true", help="não transcrever nem avaliar as conversas"
    )
    args = parser.parse_args()
    if not 1 <= args.dias <= 31:
        parser.error("--dias deve estar entre 1 e 31 (limite da API do Callix)")

    load_dotenv()
    callix = Callix(os.environ["CALLIX_TOKEN"], os.environ.get("CALLIX_SUBDOMINIO", "esparta"))
    campanha_id = int(os.environ["CALLIX_CAMPANHA_ID"])

    DADOS.mkdir(exist_ok=True)
    db = sqlite3.connect(DADOS / "crm.db")
    db.execute(SCHEMA)

    fim = datetime.now(UTC)
    inicio = fim - timedelta(days=args.dias)
    for tipo in ("campaign_completed_calls", "campaign_missed_calls"):
        total = 0
        for chamada in callix.chamadas(tipo, campanha_id, inicio, fim):
            salvar(db, tipo, campanha_id, chamada)
            total += 1
        db.commit()
        print(f"{tipo}: {total} chamadas")

    if not args.sem_audio:
        print(f"áudios baixados: {baixar_audios(db, callix)}")

    if not args.sem_analise:
        playbook = json.loads((DADOS.parent / "playbook.json").read_text(encoding="utf-8"))
        feitas = conversa.processar(db, DADOS, playbook)
        print(f"conversas transcritas: {feitas['transcritas']}, avaliadas: {feitas['avaliadas']}")

    db.close()
    gerar_painel(DADOS / "crm.db", DADOS / "painel.html")
    print(f"painel atualizado: {DADOS / 'painel.html'}")


if __name__ == "__main__":
    main()
