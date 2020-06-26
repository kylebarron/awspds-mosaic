import { TileLayer } from "@deck.gl/geo-layers";
import {
  RasterLayer,
  combineBands,
  pansharpenBrovey
} from "@kylebarron/deck.gl-raster";
import { getLandsatUrl } from "./util";
import { imageUrlsToTextures } from "./webgl-util";

export function LandsatTileLayer(props) {
  const {
    gl,
    // Bug in TileLayer? with minZoom=7, zoom 7 tiles are loaded when map is at
    // zoom >= 6.
    minZoom = 7,
    maxZoom = 12,
    id = "landsat-tile-layer",
    mosaicUrl,
    color_ops,
    rgbBands
  } = props || {};

  return new TileLayer({
    id,
    minZoom,
    maxZoom,
    getTileData: args =>
      getTileData(
        Object.assign(args, {
          gl,
          mosaicUrl,
          color_ops,
          rgbBands
        })
      ),
    renderSubLayers,
    maxRequests: 6
  });
}

async function getTileData(options) {
  const { gl, x, y, z, mosaicUrl, color_ops, rgbBands = [4, 3, 2] } =
    options || {};

  const modules = [combineBands];
  let imagePan;
  if (z >= 12) {
    const panUrl = getLandsatUrl({ x, y, z, bands: 8, mosaicUrl, color_ops });
    imagePan = imageUrlsToTextures(gl, panUrl);
    modules.push(pansharpenBrovey);
  }

  // Load landsat urls
  const urls = [
    getLandsatUrl({ x, y, z, bands: rgbBands[0], mosaicUrl, color_ops }),
    getLandsatUrl({ x, y, z, bands: rgbBands[1], mosaicUrl, color_ops }),
    getLandsatUrl({ x, y, z, bands: rgbBands[2], mosaicUrl, color_ops })
  ];

  const imageBands = imageUrlsToTextures(gl, urls);
  await Promise.all([imagePan, imageBands]);

  return { imageBands: await imageBands, imagePan: await imagePan, modules };
}

function renderSubLayers(props) {
  const {
    bbox: { west, south, east, north }
  } = props.tile;
  const { modules, ...moduleProps } = props.data;

  return new RasterLayer(props, {
    modules,
    moduleProps,
    bounds: [west, south, east, north]
  });
}
