/**
 * Get color operations string for landsat bands
 * @param {Number} nBands Number of bands
 */
function landsatColorOps(nBands) {
  const colorBands = "RGB".slice(0, nBands);
  let colorStr = `gamma ${colorBands} 3.5, sigmoidal ${colorBands} 15 0.35`;

  if (nBands === 3) {
    colorStr += ", saturation 1.7";
  }
  return colorStr;
}

/**
 * Get URL including query string to fetch Landsat tile
 * @param {object} options:
 * bands: array of band numbers
 * mosaicUrl: url to mosaicJSON, parsed by backend
 * x: mercator tile x
 * y: mercator tile y
 * z: mercator tile z
 * color_ops: Custom color_ops rio-color string
 */
export function getLandsatUrl(options) {
  const { bands, mosaicUrl, x, y, z, color_ops } = options || {};
  const bandsArray = Array.isArray(bands) ? bands : [bands];
  const params = new URLSearchParams({
    bands: bandsArray.join(","),
    color_ops: color_ops || landsatColorOps(bandsArray.length),
    url: mosaicUrl
  });
  let baseUrl = `https://us-west-2-lambda.kylebarron.dev/landsat/tiles/${z}/${x}/${y}@2x.jpg?`;
  return baseUrl + params.toString();
}

/**
 * Get ViewState from page URL hash
 * Note: does not necessarily return all viewState fields
 * @param {string} hash Page URL hash
 */
export function getViewStateFromHash(hash) {
  if (!hash || hash.charAt(0) !== "#") {
    return {};
  }

  // Split the hash into an array of numbers
  let hashArray = hash
    // Remove # symbol
    .substring(1)
    .split("/")
    .map(Number);

  // Remove non-numeric values
  hashArray = hashArray.map(val => (Number.isFinite(val) && val) || null);

  // Order of arguments:
  // https://docs.mapbox.com/mapbox-gl-js/api/
  const [zoom, latitude, longitude, bearing, pitch] = hashArray;
  const viewState = {
    bearing,
    latitude,
    longitude,
    pitch,
    zoom
  };

  // Delete null keys
  // https://stackoverflow.com/a/38340730
  Object.keys(viewState).forEach(
    key => viewState[key] == null && delete viewState[key]
  );

  return viewState;
}
