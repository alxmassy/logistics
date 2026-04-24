import { useMemo, useCallback } from 'react';
import { Source, Layer, useMap } from 'react-map-gl/mapbox';
import { useShipmentStore } from '@/store/useShipmentStore';
import { getModeIcon } from '@/lib/utils';

/**
 * ShipmentLayer renders all active shipments as clustered points on the map.
 * Uses Mapbox GL's built-in clustering for performance with hundreds of shipments.
 */
export default function ShipmentLayer({ onShipmentClick, mapRef }) {
  const shipments = useShipmentStore((s) => s.shipments);
  const { current: map } = useMap();

  // Convert shipments map to GeoJSON FeatureCollection
  const geojsonData = useMemo(() => {
    const features = Object.values(shipments)
      .filter((s) => s.current_lat_lon)
      .map((s) => ({
        type: 'Feature',
        properties: {
          shipment_id: s.shipment_id,
          transport_mode: s.transport_mode,
          priority_tier: s.priority_tier,
          carrier: s.carrier,
          expected_eta: s.expected_eta,
          icon: getModeIcon(s.transport_mode),
        },
        geometry: {
          type: 'Point',
          coordinates: [s.current_lat_lon.lon, s.current_lat_lon.lat],
        },
      }));

    return {
      type: 'FeatureCollection',
      features,
    };
  }, [shipments]);

  // Handle click on the layer
  const handleClick = useCallback(
    (e) => {
      if (!e.features?.length) return;
      const feature = e.features[0];

      // If it's a cluster, zoom in
      if (feature.properties.cluster) {
        const clusterId = feature.properties.cluster_id;
        const source = map?.getSource('shipments-source');
        if (source) {
          source.getClusterExpansionZoom(clusterId, (err, zoom) => {
            if (!err && map) {
              map.easeTo({
                center: feature.geometry.coordinates,
                zoom: zoom + 1,
                duration: 500,
              });
            }
          });
        }
        return;
      }

      // Individual shipment click
      const sid = feature.properties.shipment_id;
      const shipment = shipments[sid];
      if (shipment && onShipmentClick) {
        onShipmentClick(shipment);
      }
    },
    [map, shipments, onShipmentClick]
  );

  // Register click handler on the map
  useMemo(() => {
    if (map) {
      map.on('click', 'shipment-points', handleClick);
      map.on('click', 'shipment-clusters', handleClick);
      return () => {
        map.off('click', 'shipment-points', handleClick);
        map.off('click', 'shipment-clusters', handleClick);
      };
    }
  }, [map, handleClick]);

  return (
    <Source
      id="shipments-source"
      type="geojson"
      data={geojsonData}
      cluster={true}
      clusterMaxZoom={14}
      clusterRadius={50}
    >
      {/* Cluster circles */}
      <Layer
        id="shipment-clusters"
        type="circle"
        filter={['has', 'point_count']}
        paint={{
          'circle-color': [
            'step',
            ['get', 'point_count'],
            '#3b82f6',  // blue for small clusters
            10,
            '#eab308',  // yellow for medium
            30,
            '#ef4444',  // red for large
          ],
          'circle-radius': [
            'step',
            ['get', 'point_count'],
            18,
            10, 24,
            30, 32,
          ],
          'circle-opacity': 0.85,
          'circle-stroke-width': 2,
          'circle-stroke-color': 'rgba(255, 255, 255, 0.15)',
        }}
      />

      {/* Cluster count labels */}
      <Layer
        id="shipment-cluster-count"
        type="symbol"
        filter={['has', 'point_count']}
        layout={{
          'text-field': '{point_count_abbreviated}',
          'text-font': ['DIN Pro Medium', 'Arial Unicode MS Bold'],
          'text-size': 12,
        }}
        paint={{
          'text-color': '#ffffff',
        }}
      />

      {/* Individual shipment points */}
      <Layer
        id="shipment-points"
        type="circle"
        filter={['!', ['has', 'point_count']]}
        paint={{
          'circle-color': [
            'match',
            ['get', 'transport_mode'],
            'SEA', '#3b82f6',
            'AIR', '#a855f7',
            'ROAD', '#22c55e',
            '#64748b',
          ],
          'circle-radius': 7,
          'circle-opacity': 0.9,
          'circle-stroke-width': 2,
          'circle-stroke-color': [
            'match',
            ['get', 'priority_tier'],
            'HIGH', '#ef4444',
            'STANDARD', '#eab308',
            'rgba(255, 255, 255, 0.3)',
          ],
        }}
      />

      {/* Shipment mode labels */}
      <Layer
        id="shipment-labels"
        type="symbol"
        filter={['!', ['has', 'point_count']]}
        layout={{
          'text-field': ['get', 'icon'],
          'text-size': 14,
          'text-offset': [0, -1.5],
          'text-allow-overlap': false,
        }}
        minzoom={5}
      />
    </Source>
  );
}
