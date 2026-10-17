import argparse
from pathlib import Path

import geopandas as gpd


def verificar_sobreposicao(
    caminho_car: str | Path,
    caminho_embargos: str | Path,
) -> gpd.GeoDataFrame:
    """Retorna os registros de embargo que intersectam o polígono do CAR."""
    car = gpd.read_file(caminho_car)
    embargos = gpd.read_file(caminho_embargos)

    if car.empty or car.geometry.isna().all():
        raise ValueError(f"O arquivo CAR não contém geometrias: {caminho_car}")
    if embargos.empty or embargos.geometry.isna().all():
        raise ValueError(f"O arquivo de embargos não contém geometrias: {caminho_embargos}")
    if car.crs is None:
        raise ValueError(f"O arquivo CAR não informa o sistema de coordenadas: {caminho_car}")
    if embargos.crs is None:
        raise ValueError(
            f"O arquivo de embargos não informa o sistema de coordenadas: {caminho_embargos}"
        )

    geometrias_car = car.geometry.dropna()
    geometrias_car = geometrias_car[~geometrias_car.is_empty]
    if geometrias_car.empty:
        raise ValueError(f"O arquivo CAR não contém geometrias válidas: {caminho_car}")
    if not geometrias_car.geom_type.isin(["Polygon", "MultiPolygon"]).all():
        raise ValueError(f"O arquivo CAR deve conter apenas polígonos: {caminho_car}")

    poligono_car = geometrias_car.union_all()
    embargos = embargos.to_crs(car.crs)

    geometrias_embargos = embargos.geometry
    return embargos.loc[
        geometrias_embargos.notna()
        & ~geometrias_embargos.is_empty
        & geometrias_embargos.intersects(poligono_car)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verifica quais embargos GeoJSON intersectam o polígono de um CAR."
    )
    parser.add_argument("car", type=Path, help="Caminho do arquivo vetorial do CAR")
    parser.add_argument("embargos", type=Path, help="Caminho do arquivo GeoJSON de embargos")
    args = parser.parse_args()

    sobreposicoes = verificar_sobreposicao(args.car, args.embargos)
    if sobreposicoes.empty:
        print("Nenhuma sobreposição encontrada.")
    else:
        print(f"Sobreposição encontrada com {len(sobreposicoes)} registro(s) de embargo.")


if __name__ == "__main__":
    main()
