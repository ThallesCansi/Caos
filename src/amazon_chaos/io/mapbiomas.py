"""MapBiomas Cobertura (coleção 11) e Fogo (coleção 5) lidos dos COGs públicos (D-012).

Nada é baixado inteiro: `preprocess.zonal.class_areas` lê por HTTP só as janelas que
cobrem a região e devolve a área de cada classe em cada célula. As versões das coleções
ficam nos endereços abaixo e no manifesto de cada tabela.
"""

from __future__ import annotations

BUCKET = "https://storage.googleapis.com/mapbiomas-public/initiatives/brasil/"
PRODUCTS = {
    # classes de cobertura e uso (legenda da coleção 11)
    "cobertura": "collection11/lulc/coverage/brazil_coverage/brazil_coverage-col11_{year}.tif",
    # número de anos com fogo entre 1985 e o ano indicado
    "frequencia_fogo": ("collection_10/fire-col5/mapbiomas_fire_collection5_fire_frequency_v1/"
                        "fire_frequency_1985_{year}.tif"),
    # ano do último fogo até o ano indicado (0 = sem fogo desde 1985)
    "ultimo_fogo": ("collection_10/fire-col5/mapbiomas_fire_collection5_year_last_fire_v1/"
                    "year_last_fire_{year}.tif"),
}
COLLECTIONS = {"cobertura": "MapBiomas Cobertura e Uso, coleção 11",
               "frequencia_fogo": "MapBiomas Fogo, coleção 5",
               "ultimo_fogo": "MapBiomas Fogo, coleção 5"}

FOREST = [3, 6]
AGRO = [9, 14, 15, 18, 19, 20, 21, 35, 36, 39, 40, 41, 46, 47, 48, 62]
WATER = [31, 33]
NOT_OBSERVED = [0, 27]  # sem dados / não observado


def url(product: str, year: int) -> str:
    return BUCKET + PRODUCTS[product].format(year=year)
