import React from "react";
import DeckGL from "@deck.gl/react";
import { MapboxLayer } from "@deck.gl/mapbox";
// import { PostProcessEffect } from '@deck.gl/core';
import { StaticMap } from "react-map-gl";
import { LandsatTileLayer } from "./landsat-tile";
// import { vibrance } from '@luma.gl/shadertools';
import { getViewStateFromHash } from "./util";

import "./App.css";

const mapStyle = require("./style.json");

// const vibranceEffect = new PostProcessEffect(vibrance, {
//   amount: 1,
// });

const initialViewState = {
  longitude: -112.1861,
  latitude: 36.1284,
  zoom: 11.5,
  pitch: 0,
  bearing: 0,
  maxPitch: 85
};

export default class App extends React.Component {
  state = {
    gl: null,
    viewState: {
      ...initialViewState,
      ...getViewStateFromHash(
        typeof window !== "undefined" ? window.location.hash : ""
      )
    }
  };

  // DeckGL and mapbox will both draw into this WebGL context
  _onWebGLInitialized = gl => {
    this.setState({ gl });
  };

  _onMapLoad = () => {
    const map = this._map;
    const deck = this._deck;

    // This id has to match the id of the Deck layer
    map.addLayer(
      new MapboxLayer({ id: "landsat-tile-layer", deck }),
      "aeroway_fill"
    );
  };

  onViewStateChange = ({ viewState }) => {
    this.setState({ viewState });
  };

  render() {
    const { gl, viewState} = this.state;
    const landsatMosaicUrl = 'dynamodb://us-west-2/landsat8-2015-spring';

    const layers = [
      new LandsatTileLayer({
        id: "landsat-tile-layer",
        gl,
        mosaicUrl: landsatMosaicUrl,
        rgbBands: [4, 3, 2]
      })
    ];

    return (
      <DeckGL
        ref={ref => {
          this._deck = ref && ref.deck;
        }}
        layers={layers}
        viewState={viewState}
        onViewStateChange={this.onViewStateChange}
        controller
        onWebGLInitialized={this._onWebGLInitialized}
        glOptions={{ stencil: true }}
      >
        {gl && (
          <StaticMap
            ref={ref => {
              this._map = ref && ref.getMap();
            }}
            gl={gl}
            onLoad={this._onMapLoad}
            mapStyle={mapStyle}
            mapOptions={{ hash: true }}
          />
        )}
      </DeckGL>
    );
  }
}
