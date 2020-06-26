"""landsat_mosaic_tiler.utils: utility functions."""

import hashlib
import json
from typing import Any, Tuple
from urllib.parse import urlencode

import numpy
from rio_color.operations import parse_operations
from rio_color.utils import scale_dtype, to_math_type
from rio_tiler.utils import linear_rescale


def get_tilejson(mosaic_def, url, tile_scale, tile_format, host, path="", **kwargs):
    """Construct tilejson definition

    Note, this is mostly copied from a PR to cogeo-mosaic-tiler. Could be imported from
    there in the future.
    """
    bounds = mosaic_def["bounds"]
    center = [
        (bounds[0] + bounds[2]) / 2,
        (bounds[1] + bounds[3]) / 2,
        mosaic_def["minzoom"],
    ]

    kwargs.update({"url": url})

    if tile_format in ["pbf", "mvt"]:
        tile_url = f"{host}{path}/{{z}}/{{x}}/{{y}}.{tile_format}"
    elif tile_format in ["png", "jpg", "webp", "tif", "npy"]:
        tile_url = f"{host}{path}/{{z}}/{{x}}/{{y}}@{tile_scale}x.{tile_format}"
    else:
        tile_url = f"{host}{path}/{{z}}/{{x}}/{{y}}@{tile_scale}x"

    qs = urlencode(list(kwargs.items()))
    if qs:
        tile_url += f"?{qs}"

    meta = {
        "bounds": bounds,
        "center": center,
        "maxzoom": mosaic_def["maxzoom"],
        "minzoom": mosaic_def["minzoom"],
        "name": url,
        "tilejson": "2.1.0",
        "tiles": [tile_url],
    }
    return ("OK", "application/json", json.dumps(meta))


def get_hash(**kwargs: Any) -> str:
    """Create hash from dict."""
    return hashlib.sha224(
        json.dumps(kwargs, sort_keys=True, default=str).encode()
    ).hexdigest()


def post_process_tile(
    tile: numpy.ndarray,
    mask: numpy.ndarray,
    rescale: str = None,
    color_formula: str = None,
) -> Tuple[numpy.ndarray, numpy.ndarray]:
    """Tile data post processing."""
    if rescale:
        rescale_arr = (tuple(map(float, rescale.split(","))),) * tile.shape[0]
        for bdx in range(tile.shape[0]):
            tile[bdx] = numpy.where(
                mask,
                linear_rescale(
                    tile[bdx], in_range=rescale_arr[bdx], out_range=[0, 255]
                ),
                0,
            )
        tile = tile.astype(numpy.uint8)

    if color_formula:
        if issubclass(tile.dtype.type, numpy.floating):
            tile = tile.astype(numpy.int16)

        # make sure one last time we don't have
        # negative value before applying color formula
        tile[tile < 0] = 0
        for ops in parse_operations(color_formula):
            tile = scale_dtype(ops(to_math_type(tile)), numpy.uint8)

    return tile
