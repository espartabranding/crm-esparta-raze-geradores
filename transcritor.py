"""Transcreve gravações de ligação com o vocabulário de cada conta e marca as palavras duvidosas.

Roda com o Python do Esparta Transcribe, a partir da pasta dele, para reaproveitar
o carregamento do modelo e a separação de falantes já instalados:

    venv\\Scripts\\python.exe <projeto>\\transcritor.py <pasta_audio> <pasta_saida> --vocabulario v.json
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.getcwd())

import falantes
import transcrever
from faster_whisper import WhisperModel

# Abaixo desta probabilidade a palavra é marcada para conferência no áudio.
DUVIDA = 0.5
ABRE, FECHA = "⟦", "⟧"


def _numero(rotulo: str) -> int:
    fim = rotulo.split()[-1]
    return int(fim) if fim.isdigit() else 1


def transcrever_arquivo(modelo, arquivo: Path, vocabulario: str | None) -> list[dict]:
    segmentos, _ = modelo.transcribe(
        str(arquivo),
        language="pt",
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        condition_on_previous_text=False,
        word_timestamps=True,
        # Nomes da conta, do agente e dos produtos: onde o modelo mais erra.
        hotwords=vocabulario or None,
        # Descarta texto "inventado" em trechos longos de silêncio ou ruído.
        hallucination_silence_threshold=2.0,
    )
    palavras, confianca = [], {}
    for seg in segmentos:
        for w in seg.words or []:
            palavras.append((w.start, w.end, w.word))
            confianca[w.start, w.end] = w.probability
    if not palavras:
        return []
    try:
        turnos = falantes.diarizar(arquivo, 2)
    except falantes.DiarizacaoFalhou:
        turnos = [(0, palavras[-1][1], "SPEAKER_00")]

    falas = []
    for f in falantes.alinhar(palavras, turnos):
        marcado = "".join(
            f" {ABRE}{p.strip()}{FECHA}" if confianca[ini, fim] < DUVIDA else p
            for ini, fim, p in f["palavras"]
        )
        falas.append(
            {
                "ini": f["inicio"],
                "fim": f["fim"],
                "falante": _numero(f["falante"]),
                "texto": " ".join("".join(p for _, _, p in f["palavras"]).split()),
                "marcado": " ".join(marcado.split()),
            }
        )
    return falas


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("audio", type=Path)
    ap.add_argument("saida", type=Path)
    ap.add_argument("--vocabulario", type=Path, help="JSON {id da chamada: termos separados por vírgula}")
    args = ap.parse_args()

    vocabulario = json.loads(args.vocabulario.read_text(encoding="utf-8")) if args.vocabulario else {}
    args.saida.mkdir(parents=True, exist_ok=True)
    pendentes = [a for a in sorted(args.audio.glob("*.mp3")) if not (args.saida / f"{a.stem}.json").exists()]
    if not pendentes:
        return
    if falantes.status() != "ok":
        sys.exit("Separação de falantes indisponível: " + falantes.MENSAGENS_STATUS[falantes.status()])

    transcrever.preparar_gpu()
    modelo, _ = transcrever.carregar_modelo(WhisperModel, "large-v3")
    for arquivo in pendentes:
        falas = transcrever_arquivo(modelo, arquivo, vocabulario.get(arquivo.stem))
        (args.saida / f"{arquivo.stem}.json").write_text(
            json.dumps(falas, ensure_ascii=False), encoding="utf-8"
        )
        print(f"{arquivo.name}: {len(falas)} falas")


if __name__ == "__main__":
    main()
