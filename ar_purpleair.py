"""Média horária de PM2,5 por município do Amazonas, a partir dos sensores PurpleAir
(os mesmos exibidos pelo Selva/UEA). Roda a cada 30 min no GitHub Actions e grava ar.json.
Critérios: sensor externo; leitura na última hora; confiança >= 50%; os dois canais sem
defeito (channel_flags = 0); média de 60 min > 0. Classificação pela legenda do Selva/UEA."""
import json, os, time, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

AQUI = os.path.dirname(os.path.abspath(__file__))
MUN = json.load(open(os.path.join(AQUI, "mun.json"), encoding="utf-8"))
SEDES = json.load(open(os.path.join(AQUI, "sedes.json"), encoding="utf-8"))
SELVA = [(25, "Boa"), (50, "Moderada"), (75, "Ruim"), (125, "Muito Ruim"), (float("inf"), "Péssimo")]


def dentro_anel(x, y, anel):
    dentro, j = False, len(anel) - 1
    for i in range(len(anel)):
        xi, yi = anel[i]; xj, yj = anel[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            dentro = not dentro
        j = i
    return dentro


def municipio(lon, lat):
    for f in MUN["features"]:
        g = f["geometry"]
        polis = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        for p in polis:
            if dentro_anel(lon, lat, p[0]) and not any(dentro_anel(lon, lat, h) for h in p[1:]):
                return SEDES[f["properties"]["codarea"]][0]
    return None


def main():
    q = dict(fields="latitude,longitude,last_seen,pm2.5_10minute,confidence,channel_flags",
             location_type="0", nwlng="-73.9", nwlat="2.3", selng="-56.0", selat="-9.9", max_age="7200")
    req = urllib.request.Request("https://api.purpleair.com/v1/sensors?" + urllib.parse.urlencode(q),
                                 headers={"X-API-Key": os.environ["PURPLEAIR_KEY"]})
    d = json.load(urllib.request.urlopen(req, timeout=60))
    F, agora = d["fields"], d["data_time_stamp"]
    por_mun = {}
    for linha in d["data"]:
        s = dict(zip(F, linha))
        pm = s["pm2.5_10minute"]
        if pm is None or pm <= 0 or s["confidence"] < 50 or s["channel_flags"] != 0 or agora - s["last_seen"] > 3600:
            continue
        m = municipio(s["longitude"], s["latitude"])
        if m:
            por_mun.setdefault(m, []).append(pm)
    saida = {}
    for m, v in sorted(por_mun.items()):
        media = round(sum(v) / len(v), 1)
        saida[m] = {"pm": media, "n": len(v), "nivel": next(n for lim, n in SELVA if media <= lim)}
    quando = datetime.fromtimestamp(agora, timezone(timedelta(hours=-4))).strftime("%Y-%m-%dT%H:%M")
    json.dump({"quando": quando, "fonte": "PurpleAir (rede Selva/UEA)", "M": saida},
              open(os.path.join(AQUI, "ar.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(quando, len(saida), "municípios;", "Manaus:", saida.get("Manaus"))


if __name__ == "__main__":
    main()
