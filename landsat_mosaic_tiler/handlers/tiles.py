"""landsat_mosaic_tiler.handlers.tiles: handle request for landsat mosaic."""
import io
import json
import os
from typing import Any, BinaryIO, Tuple

import mercantile
import numpy
from landsat_mosaic_tiler.pixel_methods import pixSel
from landsat_mosaic_tiler.utils import get_tilejson, post_process_tile
from cogeo_mosaic.backends import MosaicBackend
from lambda_proxy.proxy import API
from PIL import Image
from rasterio.transform import from_bounds
from rio_tiler.colormap import cmap
from rio_tiler.profiles import img_profiles
from rio_tiler.utils import render
from rio_tiler_pds.landsat.aws import L8Reader

app = API(name="landsat-mosaic-tiler-tiles", debug=False)


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
    bands: str = "",
    expr: str = None,
    pixel_selection: str = "first",
) -> Tuple[str, str, BinaryIO]:
    """Handle tile requests."""
    if url is None:
        return ("NOK", "text/plain", "Missing 'URL' parameter")

    if expr and bands:
        return ("NOK", "text/plain", "Cannot pass both expr and bands")

    tilesize = 256 * scale

    pixel_selection = pixSel.get(pixel_selection, pixSel['first'])
    with MosaicBackend(url, reader=L8Reader) as mosaic:
        (tile, mask), assets_used = mosaic.tile(x, y, z,
            pixel_selection=pixel_selection(),
            tilesize=tilesize,
            bands=tuple(bands.split(",")),
            expression=expr)

    if tile is None:
        return ("EMPTY", "text/plain", "empty tiles")

    assets_str = json.dumps(assets_used, separators=(",", ":"))
    return_kwargs = {"custom_headers": {"X-ASSETS": assets_str}}

    sio = io.BytesIO()
    # NOTE: this currently omits the mask!
    numpy.save(sio, tile)
    sio.seek(0)
    return ("OK", "application/x-binary", sio.getvalue(), return_kwargs)


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
    bands: str = "",
    expr: str = None,
    rescale: str = None,
    color_ops: str = None,
    color_map: str = None,
    pan: bool = False,
    pixel_selection: str = "first",
) -> Tuple[str, str, BinaryIO]:
    """Handle tile requests."""
    if url is None:
        return ("NOK", "text/plain", "Missing 'URL' parameter")

    if expr and bands:
        return ("NOK", "text/plain", "Cannot pass both expr and bands")

    tilesize = 256 * scale

    pixel_selection = pixSel.get(pixel_selection, pixSel['first'])
    with MosaicBackend(url, reader=L8Reader) as mosaic:
        (tile, mask), assets_used = mosaic.tile(x, y, z,
            pixel_selection=pixel_selection(),
            tilesize=tilesize,
            bands=tuple(bands.split(",")),
            expression=expr)

    if tile is None:
        return ("EMPTY", "text/plain", "empty tiles")

    if color_map:
        color_map = cmap.get(color_map)

    assets_str = json.dumps(assets_used, separators=(",", ":"))
    return_kwargs = {"custom_headers": {"X-ASSETS": assets_str}}

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
        return ("OK", f"image/{ext}", sio.getvalue(), return_kwargs)

    rtile = post_process_tile(tile, mask, rescale=rescale, color_formula=color_ops)

    if ext == "bin":
        # Flatten in Row-major order
        buf = rtile.tobytes(order='C')
        return ("OK", "application/x-binary", buf, return_kwargs)

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
        return_kwargs,
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
