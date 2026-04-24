import { useMemo } from 'react';
import { Source, Layer } from 'react-map-gl/mapbox';
import { useThreatStore } from '@/store/useThreatStore';
import { getThreatColor } from '@/lib/utils';

/**
 * ThreatPolygonLayer renders colored geopolitical polygons on the map
 * for weather, congestion, and infrastructure threats.
 */
export default function ThreatPolygonLayer() {
  const threats = useThreatStore((s) => s.threats);

  // Group threats by type for consistent styling
  const { weatherData, congestionData, infraData } = useMemo(() => {
    const weather = [];
    const congestion = [];
    const infra = [];

    Object.values(threats).forEach((threat) => {
      if (!threat.impact_polygon || threat.impact_polygon.length < 3) return;

      const coordinates = threat.impact_polygon.map((p) => [p.lon, p.lat]);
      // Close the polygon
      if (
        coordinates.length > 0 &&
        (coordinates[0][0] !== coordinates[coordinates.length - 1][0] ||
          coordinates[0][1] !== coordinates[coordinates.length - 1][1])
      ) {
        coordinates.push([...coordinates[0]]);
      }

      const feature = {
        type: 'Feature',
        properties: {
          threat_id: threat.threat_id,
          threat_type: threat.threat_type,
          severity: threat.severity,
        },
        geometry: {
          type: 'Polygon',
          coordinates: [coordinates],
        },
      };

      switch (threat.threat_type?.toUpperCase()) {
        case 'WEATHER':
          weather.push(feature);
          break;
        case 'CONGESTION':
          congestion.push(feature);
          break;
        case 'INFRASTRUCTURE':
          infra.push(feature);
          break;
        default:
          weather.push(feature);
      }
    });

    return {
      weatherData: { type: 'FeatureCollection', features: weather },
      congestionData: { type: 'FeatureCollection', features: congestion },
      infraData: { type: 'FeatureCollection', features: infra },
    };
  }, [threats]);

  const weatherColors = getThreatColor('WEATHER');
  const congestionColors = getThreatColor('CONGESTION');
  const infraColors = getThreatColor('INFRASTRUCTURE');

  return (
    <>
      {/* Weather threats — Red */}
      <Source id="weather-threats" type="geojson" data={weatherData}>
        <Layer
          id="weather-fill"
          type="fill"
          paint={{
            'fill-color': weatherColors.fill,
            'fill-opacity': [
              'interpolate', ['linear'], ['get', 'severity'],
              1, 0.1,
              10, 0.35,
            ],
          }}
        />
        <Layer
          id="weather-stroke"
          type="line"
          paint={{
            'line-color': weatherColors.stroke,
            'line-width': 2,
            'line-dasharray': [2, 2],
            'line-opacity': 0.8,
          }}
        />
      </Source>

      {/* Congestion threats — Orange */}
      <Source id="congestion-threats" type="geojson" data={congestionData}>
        <Layer
          id="congestion-fill"
          type="fill"
          paint={{
            'fill-color': congestionColors.fill,
            'fill-opacity': [
              'interpolate', ['linear'], ['get', 'severity'],
              1, 0.1,
              10, 0.35,
            ],
          }}
        />
        <Layer
          id="congestion-stroke"
          type="line"
          paint={{
            'line-color': congestionColors.stroke,
            'line-width': 2,
            'line-dasharray': [2, 2],
            'line-opacity': 0.8,
          }}
        />
      </Source>

      {/* Infrastructure threats — Yellow */}
      <Source id="infra-threats" type="geojson" data={infraData}>
        <Layer
          id="infra-fill"
          type="fill"
          paint={{
            'fill-color': infraColors.fill,
            'fill-opacity': [
              'interpolate', ['linear'], ['get', 'severity'],
              1, 0.1,
              10, 0.35,
            ],
          }}
        />
        <Layer
          id="infra-stroke"
          type="line"
          paint={{
            'line-color': infraColors.stroke,
            'line-width': 2,
            'line-dasharray': [2, 2],
            'line-opacity': 0.8,
          }}
        />
      </Source>
    </>
  );
}
