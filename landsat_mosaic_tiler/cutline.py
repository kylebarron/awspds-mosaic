"""landsat_mosaic_tiler.cutline: Generate cutline for image."""

from rasterio.crs import CRS
from rasterio.warp import transform_geom
from shapely import wkt
from shapely.geometry import Polygon, box, mapping, shape
from shapely.ops import transform

# import rasterio
# src = 's3://landsat-pds/c1/L8/037/034/LC08_L1TP_037034_20200707_20200707_01_RT/LC08_L1TP_037034_20200707_20200707_01_RT_B1.TIF'
# r = rasterio.open(src)
# pathrow = '0'
# sceneid = 'LC08_L1TP_037034_20200707_20200707_01_RT'
# r.bounds
# transform_bounds
# Visualize(box(*transform_bounds(r.crs, CRS.from_epsg(4326), *r.bounds)))


def reproject_geom(geom, from_crs, to_crs):
    return shape(transform_geom(from_crs, to_crs, mapping(geom)))


def to_local_coords(geom, r):
    return reproject_geom(geom, from_crs=CRS.from_epsg(4326), to_crs=r.crs)


def to_image_coords(geom, r):
    return transform(r.index, geom)


def get_cutline(r, geom: Polygon):
    """Get cutline to invalid edge pixels from image

    Cutline is in **image** coordinates.

    Args:
        - r: opened rasterio dataset
        - geom: Polygon in WGS84 of valid part of the image
    """
    # Convert geom to source's local CRS
    geom_local = to_local_coords(geom, r)

    # Convert geom to image coordinates
    geom_image_coords = to_image_coords(geom_local, r)

    # Intersect with image
    image_bounds = box(0, 0, r.width, r.height)
    cutline = geom_image_coords.intersection(image_bounds)
    return wkt.dumps(cutline)
