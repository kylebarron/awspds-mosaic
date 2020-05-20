"""awspds_mosaic.handlers.mosaics: create mosaics."""

import json
import os
from datetime import datetime
from typing import Any, Tuple

from awspds_mosaic.utils import get_hash, get_tilejson
from cogeo_mosaic.backends import MosaicBackend
from lambda_proxy.proxy import API

from landsat_cogeo_mosaic.mosaic import features_to_mosaicJSON
from landsat_cogeo_mosaic.stac import search
from landsat_cogeo_mosaic.util import filter_season

app = API(name="awspds-mosaic-landsat-mosaic", debug=True)


@app.route("/create", methods=["POST"], cors=True, tag=["mosaic"])
def create(
    url: str,
    bounds: str,
    min_cloud: float = 0,
    max_cloud: float = 100,
    min_date='2013-01-01',
    max_date= datetime.strftime(datetime.today(), "%Y-%m-%d"),
    period: str = None,
    period_qty: int = 1,
    seasons: str = None,
    minzoom: int = 7,
    maxzoom: int = 12,
    quadkey_zoom: int = 8,
    tile_format: str = "jpg",
    tile_scale: int = 1,
    **kwargs: Any,
) -> Tuple[str, str, str]:
    """Handle /create requests.

    Args:
        - bounds: Comma-separated bounding box: "west, south, east, north"
        - min_cloud: Minimum cloud percentage
        - max_cloud: Maximum cloud percentage
        - min_date: Minimum date, inclusive
        - max_date: Maximum date, inclusive
        - period: Time period. If provided, overwrites `max-date` with the given period after `min-date`. Choice of 'day', 'week', 'month', 'year'
        - period_qty: Number of periods to apply after `min-date`. Only applies if `period` is provided
        - seasons, can provide multiple. Choice of 'spring', 'summer', 'autumn', 'winter'
    """
    period_choices = ['day', 'week', 'month', 'year']
    if period not in period_choices:
        return ("NOK", "text/plain", f"Period must be one of {period_choices}")

    min_cloud = float(min_cloud)
    max_cloud = float(max_cloud)
    minzoom = int(minzoom)
    maxzoom = int(maxzoom)
    bounds = tuple(map(float, bounds.split(',')))

    if seasons:
        seasons = seasons.split(",")
    else:
        seasons = None

    mosaicid = get_hash(
        bounds=bounds,
        min_cloud=min_cloud,
        max_cloud=max_cloud,
        min_date=min_date,
        max_date=max_date,
        period=period,
        period_qty=period_qty,
        minzoom=minzoom,
        maxzoom=maxzoom,
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

    features = search(
        bounds=bounds,
        min_cloud=min_cloud,
        max_cloud=max_cloud,
        min_date=min_date,
        max_date=max_date,
        period=period,
        period_qty=period_qty)

    if seasons:
        features = filter_season(features, seasons)

    if not features:
        return ("NOK", "text/plain", "No assets found for query")

    mosaic_def = features_to_mosaicJSON(
        features=features,
        quadkey_zoom=quadkey_zoom,
        minzoom=minzoom,
        maxzoom=maxzoom)

    with MosaicBackend(url, mosaic_def=mosaic_def) as mosaic:
        mosaic.upload()

    return get_tilejson(
        mosaic_def, url, tile_scale, tile_format, host=app.host, path="/tiles", **kwargs
    )


@app.route(
    "/info",
    methods=["GET"],
    cors=True,
    tag=["mosaic"],
    cache_control=os.getenv("CACHE_CONTROL", None),
)
def info(url: str) -> Tuple[str, str, str]:
    """Handle /info requests."""
    if url is None:
        return ("NOK", "text/plain", "Missing 'URL' parameter")

    with MosaicBackend(url) as mosaic:
        mosaic_def = dict(mosaic.mosaic_def)

    return ("OK", "application/json", json.dumps(mosaic_def))


@app.route(
    "/favicon.ico",
    methods=["GET"],
    cors=True,
    tag=["other"],
    cache_control=os.getenv("CACHE_CONTROL", None),
)
def favicon() -> Tuple[str, str, str]:
    """Favicon."""
    return ("EMPTY", "text/plain", "")
