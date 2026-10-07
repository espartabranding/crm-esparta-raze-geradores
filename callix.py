"""Cliente mínimo da API do Callix (JSON:API)."""

import time
from collections.abc import Iterator
from datetime import datetime, timedelta

import httpx

INCLUDES = {
    "campaign_completed_calls": "campaign,campaign_contact,qualification,agent,transcriptions",
    "campaign_missed_calls": "campaign,campaign_contact",
}
# Limite padrão da API: 10 requisições por minuto por rota.
PAUSA_ENTRE_REQUISICOES = 6.5
PAGINA = 5000
JANELA_MAXIMA = {"campaign_missed_calls": timedelta(hours=24)}


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


class Callix:
    def __init__(self, token: str, subdominio: str = "esparta") -> None:
        self.base = f"https://{subdominio}.callix.com.br"
        self.http = httpx.Client(
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/vnd.api+json",
            },
            timeout=120,
        )

    def _get(self, url: str, params: dict | None = None) -> httpx.Response:
        if url.startswith("/"):
            url = self.base + url
        while True:
            resp = self.http.get(url, params=params)
            if resp.status_code == 429:
                time.sleep(float(resp.headers.get("Retry-After", "60")) + 1)
                continue
            resp.raise_for_status()
            time.sleep(PAUSA_ENTRE_REQUISICOES)
            return resp

    def chamadas(
        self, recurso: str, campanha_id: int, inicio: datetime, fim: datetime
    ) -> Iterator[dict]:
        """Chamadas de uma campanha no período (UTC, máximo de 31 dias).

        Cada item traz `id`, `attributes` e `relacionados`, um dicionário com os
        atributos das entidades incluídas (contato, qualificação, agente etc.).
        """
        # A rota de não completadas só aceita janelas de até 24 horas.
        janela = JANELA_MAXIMA.get(recurso, fim - inicio)
        while inicio < fim:
            proximo = min(inicio + janela, fim)
            yield from self._pagina(recurso, campanha_id, inicio, proximo)
            inicio = proximo

    def _pagina(
        self, recurso: str, campanha_id: int, inicio: datetime, fim: datetime
    ) -> Iterator[dict]:
        offset = 0
        while True:
            corpo = self._get(
                f"/api/v1/{recurso}",
                {
                    "filter[campaign]": campanha_id,
                    "filter[started_at]": f"{_iso(inicio)},{_iso(fim)}",
                    "include": INCLUDES[recurso],
                    "page[limit]": PAGINA,
                    "page[offset]": offset,
                },
            ).json()
            incluidos = {
                (i["type"], str(i["id"])): i.get("attributes", {})
                for i in corpo.get("included", [])
            }

            def resolver(ref: dict, incluidos: dict = incluidos) -> dict:
                return {"id": ref["id"], **incluidos.get((ref["type"], str(ref["id"])), {})}

            dados = corpo.get("data", [])
            for item in dados:
                relacionados = {}
                for nome, rel in (item.get("relationships") or {}).items():
                    ref = rel.get("data")
                    if isinstance(ref, dict):
                        relacionados[nome] = resolver(ref)
                    elif ref:
                        relacionados[nome] = [resolver(r) for r in ref]
                yield {
                    "id": int(item["id"]),
                    "attributes": item.get("attributes", {}),
                    "relacionados": relacionados,
                }
            if len(dados) < PAGINA:
                return
            offset += PAGINA

    def audio(self, audio_link: str) -> bytes:
        """Gravação da chamada em MP3."""
        return self._get(audio_link).content
