"""awspds-mosaic.handlers.landsat: handle request for landsat mosaic."""

from typing import Any, BinaryIO, Tuple

import os
import io

import numpy

import mercantile
from rasterio.transform import from_bounds

from rio_tiler.colormap import get_colormap
from rio_tiler.utils import expression as expressionTiler, render
from rio_tiler.profiles import img_profiles
from rio_tiler.io.landsat8 import tile as landsatTiler
from rio_tiler_mosaic.mosaic import mosaic_tiler

from cogeo_mosaic.backends import MosaicBackend

from awspds_mosaic.utils import post_process_tile, get_tilejson
from awspds_mosaic.pixel_methods import pixSel

from PIL import Image

from lambda_proxy.proxy import API

app = API(name="awspds-mosaic-landsat-tiles", debug=False)


@app.route(
    "/tilejson.json",
    methods=["GET"],
    cors=True,
    payload_compression_method="gzip",
    binary_b64encode=True,
    tag=["metadata"],
    cache_control=os.getenv("CACHE_CONTROL", None),
)
def tilejson(
    url: str, tile_format="png", tile_scale: int = 1, **kwargs: Any
) -> Tuple[str, str, str]:
    """
    Handle /tilejson.json requests.

    Note: All the querystring parameters are translated to function keywords
    and passed as string value by lambda_proxy
    """
    if url is None:
        return ("NOK", "text/plain", "Missing 'URL' parameter")

    with MosaicBackend(url) as mosaic:
        mosaic_def = dict(mosaic.mosaic_def)

    return get_tilejson(
        mosaic_def, url, tile_scale, tile_format, host=app.host, path="/tiles", **kwargs
    )


@app.route(
    "/<int:z>/<int:x>/<int:y>.npy",
    methods=["GET"],
    cors=True,
    payload_compression_method="gzip",
    binary_b64encode=True,
    tag=["tiles"],
    cache_control=os.getenv("CACHE_CONTROL", None),
)
@app.route(
    "/<int:z>/<int:x>/<int:y>@<int:scale>x.npy",
    methods=["GET"],
    cors=True,
    payload_compression_method="gzip",
    binary_b64encode=True,
    tag=["tiles"],
    cache_control=os.getenv("CACHE_CONTROL", None),
)
def npy_tiles(
    url: str,
    z: int,
    x: int,
    y: int,
    scale: int = 1,
    bands: str = None,
    expr: str = None,
    pixel_selection: str = "first",
) -> Tuple[str, str, BinaryIO]:
    """Handle tile requests."""
    if url is None:
        return ("NOK", "text/plain", "Missing 'URL' parameter")

    with MosaicBackend(url) as mosaic:
        assets = mosaic.tile(x, y, z)

    if not assets:
        return ("EMPTY", "text/plain", f"No assets found for tile {z}-{x}-{y}")

    tilesize = 256 * scale

    pixel_selection = pixSel[pixel_selection]
    if expr is not None:
        results = mosaic_tiler(
            assets,
            x,
            y,
            z,
            expressionTiler,
            pixel_selection=pixel_selection(),
            expr=expr,
            tilesize=tilesize,
        )

    elif bands is not None:
        results = mosaic_tiler(
            assets,
            x,
            y,
            z,
            landsatTiler,
            pixel_selection=pixel_selection(),
            bands=tuple(bands.split(",")),
            tilesize=tilesize,
        )
    else:
        return ("NOK", "text/plain", "No bands nor expression given")

    sio = io.BytesIO()
    numpy.save(sio, results)
    sio.seek(0)
    return ("OK", "application/x-binary", sio.getvalue())


@app.route(
    "/<int:z>/<int:x>/<int:y>.<ext>",
    methods=["GET"],
    cors=True,
    payload_compression_method="gzip",
    binary_b64encode=True,
    tag=["tiles"],
    cache_control=os.getenv("CACHE_CONTROL", None),
)
@app.route(
    "/<int:z>/<int:x>/<int:y>@<int:scale>x.<ext>",
    methods=["GET"],
    cors=True,
    payload_compression_method="gzip",
    binary_b64encode=True,
    tag=["tiles"],
    cache_control=os.getenv("CACHE_CONTROL", None),
)
def tiles(
    url: str,
    z: int,
    x: int,
    y: int,
    scale: int = 1,
    ext: str = "png",
    bands: str = None,
    expr: str = None,
    rescale: str = None,
    color_ops: str = None,
    color_map: str = None,
    pan: bool = False,
    pixel_selection: str = "first",
) -> Tuple[str, str, BinaryIO]:
    """Handle tile requests."""
    with MosaicBackend(url) as mosaic:
        assets = mosaic.tile(x, y, z)

    if not assets:
        return ("EMPTY", "text/plain", f"No assets found for tile {z}-{x}-{y}")

    tilesize = 256 * scale

    pixel_selection = pixSel[pixel_selection]
    if expr is not None:
        tile, mask = mosaic_tiler(
            assets,
            x,
            y,
            z,
            expressionTiler,
            pixel_selection=pixel_selection(),
            expr=expr,
            tilesize=tilesize,
            pan=pan,
        )

    elif bands is not None:
        tile, mask = mosaic_tiler(
            assets,
            x,
            y,
            z,
            landsatTiler,
            pixel_selection=pixel_selection(),
            bands=tuple(bands.split(",")),
            tilesize=tilesize,
            pan=pan,
        )
    else:
        return ("NOK", "text/plain", "No bands nor expression given")

    if tile is None:
        return ("EMPTY", "text/plain", "empty tiles")

    if color_map:
        color_map = get_colormap(color_map, format="gdal")

    if ext == "gif":
        frames = []
        options = img_profiles.get("png", {})
        for i in range(len(tile)):
            img = post_process_tile(
                tile[i].copy(), mask[i].copy(), rescale=rescale, color_formula=color_ops
            )
            frames.append(
                Image.open(
                    io.BytesIO(
                        render(
                            img,
                            mask[i],
                            img_format="png",
                            colormap=color_map,
                            **options,
                        )
                    )
                )
            )
        sio = io.BytesIO()
        frames[0].save(
            sio,
            "gif",
            save_all=True,
            append_images=frames[1:],
            duration=300,
            loop=0,
            optimize=True,
        )
        sio.seek(0)
        return ("OK", f"image/{ext}", sio.getvalue())

    rtile = post_process_tile(tile, mask, rescale=rescale, color_formula=color_ops)

    driver = "jpeg" if ext == "jpg" else ext
    options = img_profiles.get(driver, {})

    if ext == "tif":
        ext = "tiff"
        driver = "GTiff"
        tile_bounds = mercantile.xy_bounds(mercantile.Tile(x=x, y=y, z=z))
        options = dict(
            crs={"init": "EPSG:3857"},
            transform=from_bounds(*tile_bounds, tilesize, tilesize),
        )

    return (
        "OK",
        f"image/{ext}",
        render(rtile, mask, img_format=driver, colormap=color_map, **options),
    )


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
