"""awspds_mosaic.handlers.mosaics: create mosaics."""

from typing import Any, Tuple

import json

from awspds_mosaic.utils import get_tilejson
from awspds_mosaic.landsat.stac import stac_to_mosaicJSON

from cogeo_mosaic.backends import MosaicBackend

from loguru import logger

from lambda_proxy.proxy import API
from lambda_proxy_cache.proxy import get_hash

app = API(name="awspds-mosaic-landsat-mosaic", debug=True)


@app.route("/create", methods=["POST"], cors=True, tag=["mosaic"])
def create(
    body: str,
    url: str,
    minzoom: int = 7,
    maxzoom: int = 12,
    optimized_selection: bool = False,
    maximum_items_per_tile: int = 20,
    stac_collection_limit: int = 500,
    seasons: str = None,
    tile_format: str = "png",
    tile_scale: int = 1,
    **kwargs: Any,
) -> Tuple[str, str, str]:
    """Handle /create requests."""
    body = json.loads(body)
    logger.debug(body)

    minzoom = int(minzoom)
    maxzoom = int(maxzoom)
    if isinstance(optimized_selection, str):
        optimized_selection = (
            False if optimized_selection in ["False", "false"] else True
        )

    if seasons:
        seasons = seasons.split(",")
    else:
        seasons = ["spring", "summer", "autumn", "winter"]

    maximum_items_per_tile = int(maximum_items_per_tile)
    stac_collection_limit = int(stac_collection_limit)

    mosaicid = get_hash(
        body=body,
        minzoom=minzoom,
        maxzoom=maxzoom,
        optimized_selection=optimized_selection,
        maximum_items_per_tile=maximum_items_per_tile,
        stac_collection_limit=stac_collection_limit,
        seasons=seasons,
    )

    # Replace {mosaicid} template in url
    if "{mosaicid}" in url:
        url = url.replace("{mosaicid}", mosaicid)

    # Load mosaic if it already exists
    try:
        with MosaicBackend(url) as mosaic:
            mosaic_def = dict(mosaic.mosaic_def)

        return get_tilejson(
            mosaic_def,
            url,
            tile_scale,
            tile_format,
            host=app.host,
            path="/tiles",
            **kwargs,
        )

    except Exception:
        pass

    body["query"].update({"eo:platform": {"eq": "landsat-8"}})

    mosaic_def = stac_to_mosaicJSON(
        body,
        minzoom=minzoom,
        maxzoom=maxzoom,
        optimized_selection=optimized_selection,
        maximum_items_per_tile=maximum_items_per_tile,
        stac_collection_limit=stac_collection_limit,
        seasons=seasons,
    )

    with MosaicBackend(url, mosaic_def=mosaic_def) as mosaic:
        mosaic.upload()

    return get_tilejson(
        mosaic_def, url, tile_scale, tile_format, host=app.host, path="/tiles", **kwargs
    )


@app.route(
    "/info", methods=["GET"], cors=True, tag=["mosaic"],
)
def info(url: str) -> Tuple[str, str, str]:
    """Handle /info requests."""
    if url is None:
        return ("NOK", "text/plain", "Missing 'URL' parameter")

    with MosaicBackend(url) as mosaic:
        mosaic_def = dict(mosaic.mosaic_def)

    return ("OK", "application/json", json.dumps(mosaic_def))


@app.route("/favicon.ico", methods=["GET"], cors=True, tag=["other"])
def favicon() -> Tuple[str, str, str]:
    """Favicon."""
    return ("EMPTY", "text/plain", "")
