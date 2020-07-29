"""
landsat_mosaic_tiler:landsat_tiler.py

Custom landsat tiler to use cutline to remove broken overview edges
"""

import os
import sqlite3
from concurrent import futures
from pathlib import Path
from typing import Any, Dict, Sequence, Tuple, Union

import numpy
import rasterio
from landsat_mosaic_tiler.cutline import get_cutline
from rio_tiler import constants, reader
from rio_tiler.errors import InvalidBandName, TileOutsideBounds
from rio_tiler.io.landsat8 import (LANDSAT_BANDS, _convert, _landsat_get_mtl,
                                   landsat_parser)
from rio_tiler.utils import pansharpening_brovey, tile_exists
from rio_toa import toa_utils
from shapely import wkb


def find_wrs_db_path():
    lambda_root = os.getenv('LAMBDA_TASK_ROOT')
    if not lambda_root:
        return str((Path(__file__) / 'data' / 'wrs.db').resolve())

    return f'{lambda_root}/landsat_mosaic_tiler/data/wrs.db'


def get_wrs_geometry(db_path, pathrow):
    """Get scene geometry from SQLite DB of WRS geometries
    """
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        t = (pathrow, )
        c.execute('SELECT geometry FROM wrs2 WHERE pathrow=?', t)
        wkb_geom = c.fetchone()[0]
        return wkb.loads(wkb_geom)


# ['LC08_L1TP_036035_20190628_20190706_01_T1',
#  'LC08_L1TP_036034_20190815_20190821_01_T1',
#  'LC08_L1TP_037034_20190721_20190801_01_T1',
#  'LC08_L1TP_037035_20190705_20190719_01_T1']
#
# sceneid = 'LC08_L1TP_036035_20190628_20190706_01_T1'
# tile_x = x
# tile_y = y
# tile_z = z
# bands
# tilesize
# pan
# kwargs= {}
# wrs_db_path = 'data/wrs.db'

def tile(
        sceneid: str,
        tile_x: int,
        tile_y: int,
        tile_z: int,
        bands: Union[Sequence[str], str] = ["4", "3", "2"],
        tilesize: int = 256,
        pan: bool = False,
        **kwargs: Any,
) -> Tuple[numpy.ndarray, numpy.ndarray]:
    """
    Create mercator tile from Landsat-8 data.

    Attributes
    ----------
        sceneid : str
            Landsat sceneid. For scenes after May 2017,
            sceneid have to be LANDSAT_PRODUCT_ID.
        tile_x : int
            Mercator tile X index.
        tile_y : int
            Mercator tile Y index.
        tile_z : int
            Mercator tile ZOOM level.
        bands : tuple, str, optional (default: ("4", "3", "2"))
            Bands index for the RGB combination.
        tilesize : int, optional (default: 256)
            Output image size.
        pan : boolean, optional (default: False)
            If True, apply pan-sharpening.
        kwargs: dict, optional
            These will be passed to the 'rio_tiler.utils._tile_read' function.

    Returns
    -------
    data : numpy ndarray
    mask: numpy array

    """
    if isinstance(bands, str):
        bands = (bands, )

    for band in bands:
        if band not in LANDSAT_BANDS:
            raise InvalidBandName(
                "{} is not a valid Landsat band name".format(band))

    scene_params = landsat_parser(sceneid)

    meta: Dict = _landsat_get_mtl(sceneid)["L1_METADATA_FILE"]

    landsat_prefix = "{scheme}://{bucket}/{prefix}/{scene}".format(
        **scene_params)

    bounds = toa_utils._get_bounds_from_metadata(meta["PRODUCT_METADATA"])
    if not tile_exists(bounds, tile_z, tile_x, tile_y):
        raise TileOutsideBounds(
            "Tile {}/{}/{} is outside image bounds".format(
                tile_z, tile_x, tile_y))

    # Find geometry from wrs2 grid, to later create cutline
    wrs_db_path = find_wrs_db_path()
    pathrow = scene_params['path'] + scene_params['row']
    geom = get_wrs_geometry(wrs_db_path, pathrow)

    def worker(band: str):
        asset = f"{landsat_prefix}_B{band}.TIF"

        if band == "QA":
            nodata = 1
            resamp = "nearest"
        else:
            nodata = 0
            resamp = "bilinear"

        with rasterio.open(asset) as src_dst:
            # Create cutline
            # The cutline removes broken pixels along the edges of the overviews
            cutline = get_cutline(src_dst, geom)

            tile, mask = reader.tile(
                src_dst,
                tile_x,
                tile_y,
                tile_z,
                tilesize=tilesize,
                nodata=nodata,
                resampling_method=resamp,
                warp_vrt_option={'cutline': cutline},
                **kwargs)

        return tile, mask

    results = [worker(band) for band in bands]
    data = [x[0] for x in results]
    masks = [x[1] for x in results]
    data = numpy.concatenate(data)
    mask = numpy.all(masks, axis=0).astype(numpy.uint8) * 255
    return data, mask



    with futures.ThreadPoolExecutor(
            max_workers=constants.MAX_THREADS) as executor:
        data, masks = zip(*list(executor.map(worker, bands)))
        data = numpy.concatenate(data)
        mask = numpy.all(masks, axis=0).astype(numpy.uint8) * 255

        if pan:
            pan_data, mask = worker("8")
            data = pansharpening_brovey(data, pan_data, 0.2, pan_data.dtype)

        if bands[0] != "QA" or len(bands) != 1:
            for bdx, band in enumerate(bands):
                data[bdx] = _convert(data[bdx], band, meta)

        return data, mask
