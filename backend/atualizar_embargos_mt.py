import json
import os
import tempfile
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

import geopandas as gpd


URL_LIMITE_MT = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/estados/51"
    "?formato=application/vnd.geo+json&qualidade=minima"
)
CAMINHO_SAIDA = (
    Path(__file__).resolve().parent.parent / "gis_data" / "processed" / "embargos.geojson"
)


def descarregar_geojson(url: str, destino: Path) -> None:
    if not url.startswith("https://"):
        raise ValueError("A URL da fonte de dados deve usar HTTPS.")

    pedido = Request(url, headers={"User-Agent": "husai-carbon-mt-data-updater/1.0"})
    try:
        with urlopen(pedido, timeout=120) as resposta, destino.open("wb") as arquivo:
            arquivo.write(resposta.read())
    except URLError as erro:
        raise RuntimeError(f"Falha ao descarregar dados de {url}: {erro}") from erro


def filtrar_embargos_mt(
    caminho_fonte: Path,
    caminho_limite: Path,
    caminho_saida: Path,
) -> int:
    embargos = gpd.read_file(caminho_fonte)
    limite_mt = gpd.read_file(caminho_limite)
    if embargos.empty or embargos.geometry.isna().all():
        raise ValueError("A fonte de embargos não contém geometrias.")
    if limite_mt.empty or limite_mt.geometry.isna().all():
        raise ValueError("O arquivo do limite de Mato Grosso não contém geometrias.")
    if embargos.crs is None:
        embargos = embargos.set_crs("EPSG:4326")
    if limite_mt.crs is None:
        limite_mt = limite_mt.set_crs("EPSG:4326")

    embargos = embargos[embargos.geometry.notna() & ~embargos.geometry.is_empty].copy()
    if embargos.empty:
        filtrados = embargos
    else:
        limite = limite_mt.to_crs("EPSG:5880").geometry.union_all()
        embargos = embargos.to_crs("EPSG:5880")
        embargos.geometry = embargos.geometry.make_valid()
        embargos = embargos[~embargos.geometry.is_empty]
        filtrados = gpd.clip(embargos, limite)
        filtrados = filtrados[filtrados.geometry.notna() & ~filtrados.geometry.is_empty]
        filtrados = filtrados.to_crs("EPSG:4326")

    caminho_saida.parent.mkdir(parents=True, exist_ok=True)
    geojson = json.loads(filtrados.to_json(to_wgs84=True))
    caminho_temporario = caminho_saida.with_suffix(caminho_saida.suffix + ".tmp")
    caminho_temporario.write_text(
        json.dumps(geojson, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    caminho_temporario.replace(caminho_saida)
    return len(filtrados)


def main() -> None:
    url_fonte = os.environ.get("MT_EMBARGOS_GEOJSON_URL", "").strip()
    url_limite = os.environ.get("MT_LIMITE_GEOJSON_URL", "").strip() or URL_LIMITE_MT
    if not url_fonte:
        raise RuntimeError(
            "Configure a variável de repositório MT_EMBARGOS_GEOJSON_URL "
            "com a URL HTTPS do GeoJSON de embargos."
        )

    with tempfile.TemporaryDirectory() as diretorio_temporario:
        temporario = Path(diretorio_temporario)
        caminho_fonte = temporario / "embargos.geojson"
        caminho_limite = temporario / "limite_mt.geojson"
        descarregar_geojson(url_fonte, caminho_fonte)
        descarregar_geojson(url_limite, caminho_limite)
        quantidade = filtrar_embargos_mt(
            caminho_fonte,
            caminho_limite,
            CAMINHO_SAIDA,
        )

    print(f"GeoJSON atualizado com {quantidade} geometria(s) recortada(s) ao estado de MT.")


if __name__ == "__main__":
    main()
