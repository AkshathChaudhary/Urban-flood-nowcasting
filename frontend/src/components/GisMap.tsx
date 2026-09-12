import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import { 
  fetchRoadNetwork, 
  fetchFloodHotspots, 
  fetchFloodGrid, 
  fetchDemGrid,
  queryPointDepth,
  fetchDrainageNodes,
  fetchDrainageEdges
} from '../services/api';
import type { RouteResult } from '../services/api';
import { ZoomIn, ZoomOut, Compass, Info, Mountain, X } from 'lucide-react';

interface GisMapProps {
  currentCity: string;
  currentTimeStep: number;
  showRoads: boolean;
  showHotspots: boolean;
  showFloodHeatmap: boolean;
  showDrainagePipes?: boolean;
  showDemTerrain?: boolean;
  routeResult?: RouteResult | null;
  alternatives?: RouteResult[];
  activeRouteIndex?: number;
  onSelectRouteIndex?: (index: number) => void;
  originCoords?: [number, number] | null;
  destinationCoords?: [number, number] | null;
  originName?: string;
  destinationName?: string;
  onMapClick?: (lat: number, lng: number) => void;
  onDrainageSummaryLoaded?: (surchargingCount: number) => void;
  drainageRefreshKey?: number;
  simulationKey?: number;
}

export const GisMap: React.FC<GisMapProps> = ({
  currentCity,
  currentTimeStep,
  showRoads,
  showHotspots,
  showFloodHeatmap,
  showDrainagePipes = false,
  showDemTerrain = false,
  routeResult,
  alternatives = [],
  activeRouteIndex = 0,
  onSelectRouteIndex,
  originCoords,
  destinationCoords,
  originName,
  destinationName,
  onMapClick,
  onDrainageSummaryLoaded,
  drainageRefreshKey = 0,
  simulationKey = 0,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const roadsLayerRef = useRef<L.GeoJSON | null>(null);
  const hotspotsLayerRef = useRef<L.LayerGroup | null>(null);
  const rawHotspotsRef = useRef<Array<{ lat: number; lng: number; z: string; name: string }>>([]);
  const floodRasterLayerRef = useRef<L.ImageOverlay | null>(null);
  const demRasterLayerRef = useRef<L.ImageOverlay | null>(null);
  const boundsRectangleRef = useRef<L.Rectangle | null>(null);
  const routeLayerRef = useRef<L.LayerGroup | null>(null);
  const waypointsLayerRef = useRef<L.LayerGroup | null>(null);
  const drainagePipesLayerRef = useRef<L.GeoJSON | null>(null);
  const drainageNodesLayerRef = useRef<L.LayerGroup | null>(null);
  const inspectMarkerRef = useRef<L.CircleMarker | null>(null);

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [roadCount, setRoadCount] = useState<number>(0);
  const [hotspotCount, setHotspotCount] = useState<number>(0);
  const [drainagePipeCount, setDrainagePipeCount] = useState<number>(0);
  const [activePeakDepth, setActivePeakDepth] = useState<number>(0);
  const [demMeta, setDemMeta] = useState<{ min: number; max: number; mean: number } | null>(null);
  const [isLegendOpen, setIsLegendOpen] = useState<boolean>(false);

  const isKolkata = currentCity.toLowerCase() === 'kolkata';
  const centerLat = isKolkata ? 22.5535 : 19.069;
  const centerLon = isKolkata ? 88.4115 : 72.859;
  const zoomLevel = isKolkata ? 12 : 14;

  // Exact Domain Bounding Coordinates
  const degLat = 2000.0 / 111320.0; // ~0.017965 degrees
  const degLon = 2000.0 / (111320.0 * Math.cos((19.06 * Math.PI) / 180)); // ~0.019007 degrees
  const simulationBounds: L.LatLngBoundsExpression = isKolkata
    ? [[22.5050, 88.3850], [22.6020, 88.4380]]
    : [
        [19.0600, 72.8500],
        [19.0600 + degLat, 72.8500 + degLon],
      ];

  // 1. Initialize Leaflet Map (Recreated or updated when city changes)
  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (mapInstanceRef.current) {
      mapInstanceRef.current.remove();
      mapInstanceRef.current = null;
    }
    roadsLayerRef.current = null;
    hotspotsLayerRef.current = null;
    floodRasterLayerRef.current = null;
    demRasterLayerRef.current = null;
    drainagePipesLayerRef.current = null;
    drainageNodesLayerRef.current = null;
    routeLayerRef.current = null;
    waypointsLayerRef.current = null;
    inspectMarkerRef.current = null;

    const map = L.map(mapContainerRef.current, {
      center: [centerLat, centerLon],
      zoom: zoomLevel,
      maxZoom: 20,
      zoomControl: false,
      attributionControl: false,
      preferCanvas: true,
    });

    const canvasRenderer = L.canvas({ padding: 0.5 });

    // Create dedicated GIS layer stacking panes to avoid z-index collisions
    map.createPane('demPane');
    map.getPane('demPane')!.style.zIndex = '250';

    map.createPane('floodPane');
    map.getPane('floodPane')!.style.zIndex = '320';

    map.createPane('drainagePane');
    map.getPane('drainagePane')!.style.zIndex = '400';

    map.createPane('roadsPane');
    map.getPane('roadsPane')!.style.zIndex = '450';

    map.createPane('hotspotsPane');
    map.getPane('hotspotsPane')!.style.zIndex = '480';

    map.createPane('routesPane');
    map.getPane('routesPane')!.style.zIndex = '520';

    map.createPane('waypointsPane');
    map.getPane('waypointsPane')!.style.zIndex = '550';

    // Labels pane — sits above ALL data layers so place names are always visible
    map.createPane('labelsPane');
    map.getPane('labelsPane')!.style.zIndex = '600';
    map.getPane('labelsPane')!.style.pointerEvents = 'none';

    // ArcGIS World Dark Gray Base with overzooming for street-level inspection (no API key required)
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
      maxNativeZoom: 16,
      maxZoom: 20,
      attribution: 'Esri, HERE, Garmin, &copy; OpenStreetMap contributors',
    }).addTo(map);
    // Reference labels overlay — pinned above flood/DEM/roads via labelsPane so names stay readable
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}', {
      maxNativeZoom: 16,
      maxZoom: 20,
      pane: 'labelsPane',
    }).addTo(map);

    // Simulation Domain Boundary Polygon
    const rect = L.rectangle(simulationBounds, {
      color: '#06B6D4',
      weight: 2,
      dashArray: '6, 6',
      fillColor: '#06B6D4',
      fillOpacity: 0.03,
    }).addTo(map);
    boundsRectangleRef.current = rect;

    // Hotspot Layer Group
    const hotspotsGroup = L.layerGroup().addTo(map);
    hotspotsLayerRef.current = hotspotsGroup;

    // Waypoints Layer Group (Always active on top)
    const waypointsGroup = L.layerGroup().addTo(map);
    waypointsLayerRef.current = waypointsGroup;

    // Route Layer Group
    const routesGroup = L.layerGroup().addTo(map);
    routeLayerRef.current = routesGroup;

    // Interactive Click Point Depth Inspection
    map.on('click', async (e: L.LeafletMouseEvent) => {
      const { lat, lng } = e.latlng;
      if (onMapClick) onMapClick(lat, lng);

      const inBounds = isKolkata
        ? (lat >= 22.5050 && lat <= 22.6020 && lng >= 88.3850 && lng <= 88.4380)
        : (lat >= 19.0600 && lat <= 19.0600 + degLat && lng >= 72.8500 && lng <= 72.8500 + degLon);

      if (inBounds) {
        const pointData = await queryPointDepth(lat, lng, currentCity);
        if (pointData && mapInstanceRef.current) {
          if (inspectMarkerRef.current) {
            inspectMarkerRef.current.setLatLng([lat, lng]);
          } else {
            inspectMarkerRef.current = L.circleMarker([lat, lng], {
              radius: 7,
              color: '#38BDF8',
              fillColor: '#0284C7',
              weight: 2.5,
              fillOpacity: 0.8,
            }).addTo(mapInstanceRef.current);
          }

          const currentDepth = pointData.depth_m_at_horizon[currentTimeStep] || 0.0;
          const currentStreetDepth = pointData.street_depth_m_at_horizon[currentTimeStep] || 0.0;

          const hazardBadge = 
            pointData.hazard_level === 'IMPASSABLE'
              ? '<span style="background: rgba(220, 38, 38, 0.2); color: #F87171; border: 1px solid rgba(220, 38, 38, 0.4); padding: 2px 8px; border-radius: 9999px; font-weight: 700;">IMPASSABLE</span>'
              : pointData.hazard_level === 'CAUTION'
              ? '<span style="background: rgba(245, 158, 11, 0.2); color: #FBBF24; border: 1px solid rgba(245, 158, 11, 0.4); padding: 2px 8px; border-radius: 9999px; font-weight: 700;">CAUTION</span>'
              : '<span style="background: rgba(34, 197, 94, 0.2); color: #4ADE80; border: 1px solid rgba(34, 197, 94, 0.4); padding: 2px 8px; border-radius: 9999px; font-weight: 700;">CLEAR</span>';

          const horizons = Object.keys(pointData.depth_m_at_horizon).map(Number).sort((a, b) => a - b);
          const progressionBars = horizons.map(h => {
            const d = pointData.depth_m_at_horizon[h] || 0;
            const barH = Math.min(30, Math.max(2, Math.round(d * 40)));
            const isCurrent = h === currentTimeStep;
            return `
              <div style="display: flex; flex-direction: column; align-items: center; gap: 2px;">
                <div style="height: 30px; width: 14px; background: rgba(51, 65, 85, 0.4); border-radius: 3px; display: flex; align-items: flex-end;">
                  <div style="width: 100%; height: ${barH}px; background: ${d > 0.3 ? '#EF4444' : d > 0.15 ? '#F59E0B' : '#06B6D4'}; border-radius: 3px;"></div>
                </div>
                <span style="font-size: 8px; font-family: monospace; color: ${isCurrent ? '#38BDF8' : '#64748B'}; font-weight: ${isCurrent ? '700' : '400'};">T+${h}</span>
              </div>
            `;
          }).join('');

          L.popup({
            className: 'custom-glass-popup',
            maxWidth: 320,
          })
            .setLatLng([lat, lng])
            .setContent(`
              <div style="font-family: 'Inter', sans-serif; padding: 6px; color: #F8FAFC; background: #0E1223; border-radius: 12px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; border-bottom: 1px solid rgba(51, 65, 85, 0.5); padding-bottom: 6px;">
                  <span style="font-weight: 700; font-size: 13px; color: #38BDF8;">POINT HYDRODYNAMICS</span>
                  ${hazardBadge}
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; font-size: 11px; margin-bottom: 8px;">
                  <div>Elevation: <b style="color: #34D399;">${pointData.elevation_m}m</b></div>
                  <div>Water Depth (T+${currentTimeStep}m): <b style="color: #38BDF8;">${currentDepth.toFixed(2)}m</b></div>
                  <div>Street Depth: <b style="color: ${currentStreetDepth > 0.3 ? '#EF4444' : '#F59E0B'};">${currentStreetDepth.toFixed(2)}m</b></div>
                  <div>Porosity: <b style="color: #94A3B8;">${pointData.porosity}</b></div>
                </div>
                <div style="font-size: 10px; color: #94A3B8; margin-bottom: 4px; font-family: monospace;">DEPTH PROGRESSION (0–180m):</div>
                <div style="display: flex; justify-content: space-between; padding-top: 4px; border-top: 1px solid rgba(51, 65, 85, 0.3);">
                  ${progressionBars}
                </div>
              </div>
            `)
            .openOn(mapInstanceRef.current);
        }
      }
    });

    mapInstanceRef.current = map;

    // Clustering handler for hotspots
    const renderHotspotsClustered = () => {
      const map = mapInstanceRef.current;
      if (!map || !hotspotsLayerRef.current) return;
      hotspotsLayerRef.current.clearLayers();
      if (!showHotspots || rawHotspotsRef.current.length === 0) return;

      const currentZoom = map.getZoom();
      // If zoomed in (zoom >= 14), render individual subtle markers
      if (currentZoom >= 14) {
        rawHotspotsRef.current.forEach(spot => {
          const circle = L.circleMarker([spot.lat, spot.lng], {
            pane: 'hotspotsPane',
            radius: 5,
            fillColor: '#F59E0B',
            color: '#D97706',
            weight: 1.5,
            opacity: 0.9,
            fillOpacity: 0.75,
          }).bindTooltip(`⚠️ ${spot.name}: ${spot.z}m hotspot`, {
            direction: 'top',
            className: 'custom-leaflet-tooltip',
          });
          hotspotsLayerRef.current?.addLayer(circle);
        });
      } else {
        // Grid clustering based on zoom level
        const gridSize = currentZoom <= 12 ? 0.007 : 0.0035;
        const clusters: Record<string, { latSum: number; lngSum: number; count: number; spots: typeof rawHotspotsRef.current }> = {};

        rawHotspotsRef.current.forEach(spot => {
          const cellX = Math.floor(spot.lng / gridSize);
          const cellY = Math.floor(spot.lat / gridSize);
          const key = `${cellX}_${cellY}`;
          if (!clusters[key]) {
            clusters[key] = { latSum: 0, lngSum: 0, count: 0, spots: [] };
          }
          clusters[key].latSum += spot.lat;
          clusters[key].lngSum += spot.lng;
          clusters[key].count += 1;
          clusters[key].spots.push(spot);
        });

        Object.values(clusters).forEach(c => {
          const avgLat = c.latSum / c.count;
          const avgLng = c.lngSum / c.count;

          if (c.count === 1) {
            const spot = c.spots[0];
            const marker = L.circleMarker([avgLat, avgLng], {
              pane: 'hotspotsPane',
              radius: 4,
              fillColor: '#F59E0B',
              color: '#D97706',
              weight: 1.5,
              opacity: 0.85,
              fillOpacity: 0.7,
            }).bindTooltip(`⚠️ ${spot.name}: ${spot.z}m`, {
              direction: 'top',
              className: 'custom-leaflet-tooltip',
            });
            hotspotsLayerRef.current?.addLayer(marker);
          } else {
            const clusterHtml = `
              <div style="
                display: flex;
                align-items: center;
                justify-content: center;
                width: 26px;
                height: 26px;
                border-radius: 9999px;
                background: rgba(245, 158, 11, 0.25);
                border: 1.5px solid #F59E0B;
                color: #FDE68A;
                font-family: monospace;
                font-size: 10px;
                font-weight: 700;
                box-shadow: 0 0 8px rgba(245, 158, 11, 0.35);
                cursor: pointer;
                backdrop-filter: blur(4px);
              ">
                ${c.count}
              </div>
            `;
            const icon = L.divIcon({
              html: clusterHtml,
              className: 'custom-hotspot-cluster',
              iconSize: [26, 26],
              iconAnchor: [13, 13],
            });

            const clusterMarker = L.marker([avgLat, avgLng], {
              icon,
              pane: 'hotspotsPane',
            }).bindTooltip(`${c.count} Hotspots (Click to zoom)`, {
              direction: 'top',
              className: 'custom-leaflet-tooltip',
            });

            clusterMarker.on('click', () => {
              map.setView([avgLat, avgLng], Math.min(16, map.getZoom() + 2), { animate: true });
            });

            hotspotsLayerRef.current?.addLayer(clusterMarker);
          }
        });
      }
    };

    map.on('zoomend', renderHotspotsClustered);

    // Load vector layers for the active city
    const loadVectors = async () => {
      setIsLoading(true);
      try {
        const roadData = await fetchRoadNetwork(currentCity);
        if (roadData && mapInstanceRef.current) {
          setRoadCount(roadData.features.length);
          const roadLayer = L.geoJSON(roadData as any, {
            pane: 'roadsPane',
            renderer: canvasRenderer,
            style: (feature: any) => {
              const ht = (feature?.properties?.highway_type || feature?.properties?.highway || '').toLowerCase();
              if (ht.includes('primary') || ht.includes('trunk') || ht.includes('motorway')) {
                return { color: '#94A3B8', weight: 2.2, opacity: 0.65 }; // Subtle crisp highway
              } else if (ht.includes('secondary')) {
                return { color: '#64748B', weight: 1.6, opacity: 0.45 }; // Secondary road
              } else if (ht.includes('tertiary')) {
                return { color: '#475569', weight: 1.2, opacity: 0.35 }; // Tertiary road
              }
              return { color: '#334155', weight: 0.8, opacity: 0.25 }; // Local street
            },
            onEachFeature: (feature: any, layer: any) => {
              const p = feature.properties || {};
              const name = p.name || 'Unnamed Street';
              const ht = p.highway_type || p.highway || 'road';
              const len = p.length_m ? `${p.length_m.toFixed(1)}m` : 'N/A';
              const elev = p.elevation_m ? `${p.elevation_m.toFixed(1)}m` : 'N/A';

              layer.bindPopup(`
                <div style="font-family: 'Inter', sans-serif; padding: 4px; color: #F8FAFC;">
                  <div style="font-weight: 700; font-size: 13px; color: #38BDF8; margin-bottom: 4px;">${name}</div>
                  <div style="font-size: 11px; color: #94A3B8; margin-bottom: 2px;">Type: <span style="color: #E2E8F0; text-transform: uppercase;">${ht}</span></div>
                  <div style="font-size: 11px; color: #94A3B8; margin-bottom: 2px;">Length: <span style="color: #E2E8F0;">${len}</span></div>
                  <div style="font-size: 11px; color: #94A3B8;">Terrain Elevation: <span style="color: #34D399; font-weight: 600;">${elev}</span></div>
                </div>
              `);

              layer.on({
                mouseover: (e: any) => {
                  e.target.setStyle({ weight: 3.5, opacity: 0.9, color: '#06B6D4' });
                },
                mouseout: (e: any) => {
                  roadLayer.resetStyle(e.target);
                },
              });
            },
          } as any);
          if (showRoads) roadLayer.addTo(mapInstanceRef.current);
          roadsLayerRef.current = roadLayer;
        }

        const hotspotData = await fetchFloodHotspots(currentCity);
        if (hotspotData && mapInstanceRef.current && hotspotsLayerRef.current) {
          const items: Array<{ lat: number; lng: number; z: string; name: string }> = [];
          hotspotData.features.forEach((feat) => {
            const coords = feat.geometry?.coordinates;
            if (coords && coords.length >= 2) {
              items.push({
                lat: coords[1],
                lng: coords[0],
                z: feat.properties?.elevation_m?.toFixed(1) || '3.2',
                name: feat.properties?.name || 'Depression',
              });
            }
          });
          rawHotspotsRef.current = items;
          setHotspotCount(items.length);
          renderHotspotsClustered();
        }

        // Subterranean Drainage Network (Conduits & Key Hydraulic Nodes)
        const [drainageEdges, drainageNodes] = await Promise.all([
          fetchDrainageEdges(currentCity),
          fetchDrainageNodes(currentCity),
        ]);

        if (drainageEdges && mapInstanceRef.current) {
          setDrainagePipeCount(drainageEdges.features.length);
          const pipeLayer = L.geoJSON(drainageEdges as any, {
            pane: 'drainagePane',
            renderer: canvasRenderer,
            style: (feature: any) => {
              const blk = feature?.properties?.blockage_pct || 0;
              const isOver = feature?.properties?.is_surcharging;
              return {
                color: isOver ? '#EF4444' : blk > 0.3 ? '#F59E0B' : '#10B981',
                weight: blk > 0.3 ? 3.8 : 2.6,
                dashArray: '6, 5',
                opacity: 0.95,
              };
            },
            onEachFeature: (feature: any, layer: any) => {
              const p = feature.properties || {};
              const id = p.id || 'Pipe';
              const dia = p.diameter_m ? `${(p.diameter_m * 1000).toFixed(0)}mm` : '600mm';
              const cap = p.effective_capacity_m3s ? `${p.effective_capacity_m3s.toFixed(2)} m³/s` : '1.5 m³/s';
              const blk = p.blockage_pct ? `${(p.blockage_pct * 100).toFixed(0)}%` : '0%';
              layer.bindPopup(`
                <div style="font-family: 'Inter', sans-serif; padding: 6px; color: #F8FAFC; background: #0F172A; border-radius: 8px; border: 1px solid rgba(16, 185, 129, 0.4);">
                  <div style="font-weight: 700; font-size: 13px; color: #10B981; margin-bottom: 4px;">CONDUIT: ${id}</div>
                  <div style="font-size: 11px; color: #94A3B8;">Diameter: <span style="color: #E2E8F0; font-weight: 600;">${dia}</span></div>
                  <div style="font-size: 11px; color: #94A3B8;">Manning Capacity: <span style="color: #38BDF8; font-weight: 600;">${cap}</span></div>
                  <div style="font-size: 11px; color: #94A3B8;">Debris Blockage: <span style="color: ${p.blockage_pct > 0.3 ? '#F59E0B' : '#34D399'}; font-weight: 600;">${blk}</span></div>
                </div>
              `);
            },
          } as any);
          if (showDrainagePipes) pipeLayer.addTo(mapInstanceRef.current);
          drainagePipesLayerRef.current = pipeLayer;
        }

        if (drainageNodes && mapInstanceRef.current) {
          const nodesGroup = L.layerGroup();
          let surcharges = 0;

          drainageNodes.features.forEach((feat) => {
            const coords = feat.geometry?.coordinates;
            if (coords && coords.length >= 2) {
              const lng = coords[0];
              const lat = coords[1];
              const p = feat.properties || {};
              const nodeType = p.type || 'inlet';
              const isOver = p.is_overflowing || (p.stress_ratio && p.stress_ratio >= 1.0);
              if (isOver) surcharges++;

              // ONLY create prominent markers for Outfalls and Surcharging junctions!
              // (Routine inlets are not rendered as solid circles to preserve crisp map visibility)
              if (isOver || nodeType === 'outfall') {
                const marker = L.circleMarker([lat, lng], {
                  pane: 'drainagePane',
                  radius: isOver ? 7.5 : 6.0,
                  color: isOver ? '#EF4444' : '#06B6D4',
                  fillColor: isOver ? '#DC2626' : '#0284C7',
                  weight: 2.5,
                  opacity: 1.0,
                  fillOpacity: 0.9,
                }).bindPopup(`
                  <div style="font-family: 'Inter', sans-serif; padding: 6px; color: #F8FAFC; background: #0F172A; border-radius: 8px;">
                    <div style="font-weight: 700; font-size: 13px; color: ${isOver ? '#EF4444' : '#38BDF8'}; margin-bottom: 4px;">
                      ${isOver ? '⚠️ SURCHARGING MANHOLE' : '🌊 CANAL / RIVER OUTFALL'} (${p.id})
                    </div>
                    <div style="font-size: 11px; color: #94A3B8;">Elevation: <span style="color: #E2E8F0;">${p.elevation_m}m</span></div>
                    <div style="font-size: 11px; color: #94A3B8;">Hydraulic Stress: <span style="color: ${isOver ? '#EF4444' : '#34D399'}; font-weight: 600;">${((p.stress_ratio || 0) * 100).toFixed(0)}%</span></div>
                    <div style="font-size: 11px; color: #94A3B8;">Stored Water: <span style="color: #38BDF8;">${p.current_water_m3 ? p.current_water_m3.toFixed(2) : '0'} m³</span></div>
                  </div>
                `);

                nodesGroup.addLayer(marker);
              }
            }
          });

          if (onDrainageSummaryLoaded) onDrainageSummaryLoaded(surcharges);
          if (showDrainagePipes) nodesGroup.addTo(mapInstanceRef.current);
          drainageNodesLayerRef.current = nodesGroup;
        }
      } catch (err) {
        console.error('Error loading GIS layers:', err);
      } finally {
        setIsLoading(false);
      }
    };

    loadVectors();

    return () => {
      map.remove();
      mapInstanceRef.current = null;
      roadsLayerRef.current = null;
      hotspotsLayerRef.current = null;
      floodRasterLayerRef.current = null;
      demRasterLayerRef.current = null;
      drainagePipesLayerRef.current = null;
      drainageNodesLayerRef.current = null;
      routeLayerRef.current = null;
      waypointsLayerRef.current = null;
      inspectMarkerRef.current = null;
    };
  }, [currentCity]);

  // Helper: Scientific continuous hydrodynamic colormap (Punchy, GIS-Publication Grade)
  // Kolkata max ~27cm, Mumbai max ~0.7m — colormap is vivid and clear for BOTH scales.
  const getFloodColor = (depth: number): [number, number, number, number] => {
    if (depth < 0.002) return [0, 0, 0, 0]; // Dry ground

    if (depth < 0.012) {
      // Film / surface sheen (2mm–12mm): luminous electric cyan sheen
      const t = (depth - 0.002) / 0.010;
      return [
        Math.round(6 + t * 8),
        Math.round(182 + t * 30),
        Math.round(230 + t * 25),
        Math.round(210 + t * 25),   // 210–235 alpha
      ];
    }
    if (depth < 0.035) {
      // Shallow ponding (12mm–35mm): Luminous cyan → electric sapphire blue
      const t = (depth - 0.012) / 0.023;
      return [
        Math.round(14 + t * (30 - 14)),
        Math.round(212 + t * (120 - 212)),
        Math.round(255),
        Math.round(235 + t * 15),   // 235–250 alpha
      ];
    }
    if (depth < 0.08) {
      // Street pooling (35mm–80mm): Electric sapphire → royal cobalt
      const t = (depth - 0.035) / 0.045;
      return [
        Math.round(30 + t * (75 - 30)),
        Math.round(120 + t * (60 - 120)),
        Math.round(255),
        250,
      ];
    }
    if (depth < 0.15) {
      // Ankle-deep (80mm–150mm): Cobalt → high-alert amber
      const t = (depth - 0.08) / 0.07;
      return [
        Math.round(75 + t * (245 - 75)),
        Math.round(60 + t * (158 - 60)),
        Math.round(255 + t * (11 - 255)),
        255,
      ];
    }
    if (depth < 0.30) {
      // Vehicle hazard (150mm–300mm): Amber → crimson hazard
      const t = (depth - 0.15) / 0.15;
      return [
        Math.round(245 + t * (235 - 245)),
        Math.round(158 + t * (35 - 158)),
        Math.round(11 + t * (35 - 11)),
        255,
      ];
    }
    // Severe submersion (>300mm): Crimson → electric magenta
    const t = Math.min(1.0, (depth - 0.30) / 0.30);
    return [
      Math.round(235 + t * (217 - 235)),
      Math.round(35 + t * (70 - 35)),
      Math.round(35 + t * (239 - 35)),
      255,
    ];
  };

  // Helper: DEM 3D Shaded Relief + Hypsometric Terrain Tinting
  // Helper: DEM 3D Shaded Relief + Hypsometric Terrain Tinting (Multi-Directional Swiss Illumination)
  const renderDemCanvas = (
    demGrid: number[][],
    minElev: number,
    maxElev: number,
    cellSizeM: number
  ): string => {
    const rows = demGrid.length;
    const cols = demGrid[0] ? demGrid[0].length : 0;
    if (!rows || !cols) return '';

    const baseCanvas = document.createElement('canvas');
    baseCanvas.width = cols;
    baseCanvas.height = rows;
    const baseCtx = baseCanvas.getContext('2d');
    if (!baseCtx) return '';

    const imgData = baseCtx.createImageData(cols, rows);
    const data = imgData.data;

    const elevSpan = Math.max(maxElev - minElev, 0.5);

    // Multi-directional solar illumination:
    // Light 1: Primary NW (315° azimuth, 45° elevation, weight 0.65)
    // Light 2: Secondary W/SW fill (240° azimuth, 35° elevation, weight 0.35)
    const az1 = (315 * Math.PI) / 180;
    const alt1 = (45 * Math.PI) / 180;
    const sinAlt1 = Math.sin(alt1);
    const cosAlt1 = Math.cos(alt1);

    const az2 = (240 * Math.PI) / 180;
    const alt2 = (35 * Math.PI) / 180;
    const sinAlt2 = Math.sin(alt2);
    const cosAlt2 = Math.cos(alt2);

    const zFactor = isKolkata ? 5.0 : 3.0; // Exaggeration tailored for Kolkata flat delta vs Mumbai hills

    // Geographic elevation accessor ensuring correct North-at-top canvas coordinates for both cities
    const getElev = (canvasR: number, canvasC: number) => {
      const cr = Math.max(0, Math.min(rows - 1, canvasR));
      const cc = Math.max(0, Math.min(cols - 1, canvasC));
      const actualR = isKolkata ? (rows - 1 - cr) : cr;
      return demGrid[actualR] ? (demGrid[actualR][cc] ?? minElev) : minElev;
    };

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const elev = getElev(r, c);
        const idx = (r * cols + c) * 4;

        // Neighbor slopes (using smoothed kernel for organic, realistic terrain borders)
        const left = getElev(r, c - 1);
        const right = getElev(r, c + 1);
        const top = getElev(r - 1, c);
        const bottom = getElev(r + 1, c);

        const dzdx = ((right - left) / (2 * cellSizeM)) * zFactor;
        const dzdy = ((bottom - top) / (2 * cellSizeM)) * zFactor;

        const slope = Math.atan(Math.sqrt(dzdx * dzdx + dzdy * dzdy));
        let aspect = Math.atan2(dzdy, -dzdx);
        if (aspect < 0) aspect += 2 * Math.PI;

        const shade1 = sinAlt1 * Math.cos(slope) + cosAlt1 * Math.sin(slope) * Math.cos(az1 - aspect);
        const shade2 = sinAlt2 * Math.cos(slope) + cosAlt2 * Math.sin(slope) * Math.cos(az2 - aspect);
        const blendedShade = Math.max(0.1, shade1 * 0.65 + shade2 * 0.35);

        // Soft, balanced lighting compression: highlights ridges without muddy pitch-black shadows
        const lighting = 0.72 + 0.48 * (blendedShade - 0.45);

        // Hypsometric normalized elevation [0, 1]
        const norm = Math.max(0, Math.min(1, (elev - minElev) / elevSpan));

        let rCol = 0, gCol = 0, bCol = 0;
        let alpha = 195; // Balanced translucent blend allowing roads & labels to shine through

        if (isKolkata) {
          // Curated aesthetic palette for Kolkata Gangetic Delta / EM Bypass / East Wetlands:
          if (elev <= 2.5) {
            // Canals (Kestopur, Circular, Eastern Drainage) & deep wetlands: Luminous deep aquatic teal/cyan
            const t = Math.max(0, (elev - minElev) / Math.max(2.5 - minElev, 0.1));
            rCol = Math.round(6 + t * (14 - 6));
            gCol = Math.round(130 + t * (165 - 130));
            bCol = Math.round(185 + t * (233 - 185));
            alpha = 215; // Water bodies slightly more opaque
          } else if (norm < 0.30) {
            // Low-lying marshes & retention wetlands: Serene emerald moss
            const t = (norm - 0.10) / 0.20;
            rCol = Math.round(15 + t * (20 - 15));
            gCol = Math.round(118 + t * (140 - 118));
            bCol = Math.round(110 + t * (90 - 110));
          } else if (norm < 0.60) {
            // Urban plains & residential flats (3.5m - 5.5m): Soft soothing sage/olive
            const t = (norm - 0.30) / 0.30;
            rCol = Math.round(45 + t * (115 - 45));
            gCol = Math.round(135 + t * (145 - 135));
            bCol = Math.round(95 + t * (85 - 95));
          } else if (norm < 0.85) {
            // Elevated arterial corridor & embankments (5.5m - 7.0m): Warm golden ochre/amber
            const t = (norm - 0.60) / 0.25;
            rCol = Math.round(165 + t * (205 - 165));
            gCol = Math.round(145 + t * (140 - 145));
            bCol = Math.round(80 + t * (70 - 80));
          } else {
            // Highest ground (Salt Lake / EM Bypass crests > 7.0m): Rich copper terracotta into mist pearl
            const t = (norm - 0.85) / 0.15;
            rCol = Math.round(205 + t * (225 - 205));
            gCol = Math.round(130 + t * (175 - 130));
            bCol = Math.round(75 + t * (160 - 75));
          }
        } else {
          // Curated aesthetic palette for Mumbai Coastal & Western Ghats Foothills:
          if (norm < 0.18) {
            // Mangrove coast / Mithi basin: Marine deep teal
            const t = norm / 0.18;
            rCol = Math.round(13 + t * (20 - 13));
            gCol = Math.round(115 + t * (140 - 115));
            bCol = Math.round(125 + t * (110 - 125));
          } else if (norm < 0.40) {
            // Low urban basin: Lush olive-green
            const t = (norm - 0.18) / 0.22;
            rCol = Math.round(25 + t * (85 - 25));
            gCol = Math.round(140 + t * (155 - 140));
            bCol = Math.round(85 + t * (65 - 85));
          } else if (norm < 0.65) {
            // Terraces & mid elevations: Golden sand to amber
            const t = (norm - 0.40) / 0.25;
            rCol = Math.round(145 + t * (195 - 145));
            gCol = Math.round(155 + t * (145 - 155));
            bCol = Math.round(65 + t * (55 - 65));
          } else if (norm < 0.85) {
            // High ridges: Warm sienna terra-cotta
            const t = (norm - 0.65) / 0.20;
            rCol = Math.round(195 + t * (190 - 195));
            gCol = Math.round(125 + t * (90 - 125));
            bCol = Math.round(55 + t * (45 - 55));
          } else {
            // Mountain summits: Rocky mist pearl-silver
            const t = (norm - 0.85) / 0.15;
            rCol = Math.round(190 + t * (235 - 190));
            gCol = Math.round(90 + t * (238 - 90));
            bCol = Math.round(45 + t * (242 - 45));
          }
        }

        // Apply sculpted multi-directional lighting
        data[idx] = Math.min(255, Math.max(0, Math.round(rCol * lighting)));
        data[idx + 1] = Math.min(255, Math.max(0, Math.round(gCol * lighting)));
        data[idx + 2] = Math.min(255, Math.max(0, Math.round(bCol * lighting)));
        data[idx + 3] = alpha;
      }
    }

    baseCtx.putImageData(imgData, 0, 0);

    // High-resolution bilinear smoothing for sharp, beautiful terrain rendering
    const targetW = Math.max(800, cols * 4);
    const targetH = Math.max(800, rows * 4);
    const smoothCanvas = document.createElement('canvas');
    smoothCanvas.width = targetW;
    smoothCanvas.height = targetH;
    const smoothCtx = smoothCanvas.getContext('2d');
    if (!smoothCtx) return '';

    smoothCtx.imageSmoothingEnabled = true;
    smoothCtx.imageSmoothingQuality = 'high';
    smoothCtx.drawImage(baseCanvas, 0, 0, targetW, targetH);

    return smoothCanvas.toDataURL();
  };

  // 2. Render Hydrodynamic 2D Flood Depth Raster (High-Resolution Bilinear Interpolated)
  useEffect(() => {
    if (!mapInstanceRef.current) return;

    const availableHorizons = [0, 30, 60, 90, 120, 180];
    const horizon = availableHorizons.reduce((prev, curr) => 
      Math.abs(curr - currentTimeStep) < Math.abs(prev - currentTimeStep) ? curr : prev
    );

    const loadFloodRaster = async () => {
      const gridResponse = await fetchFloodGrid(horizon, currentCity);
      if (!gridResponse || !mapInstanceRef.current) return;

      const { depth_grid, summary, rows, cols } = gridResponse;
      if (summary) setActivePeakDepth(summary.max_depth_m);

      const numRows = rows || depth_grid.length || (isKolkata ? 300 : 200);
      const numCols = cols || (depth_grid[0] ? depth_grid[0].length : (isKolkata ? 160 : 200));

      const baseCanvas = document.createElement('canvas');
      baseCanvas.width = numCols;
      baseCanvas.height = numRows;
      const baseCtx = baseCanvas.getContext('2d');
      if (!baseCtx) return;

      const imgData = baseCtx.createImageData(numCols, numRows);
      const data = imgData.data;

      for (let r = 0; r < numRows; r++) {
        for (let c = 0; c < numCols; c++) {
          // Ensure correct North-at-top canvas row mapping for Kolkata (which has row 0 at South)
          const gridR = isKolkata ? (numRows - 1 - r) : r;
          const depth = depth_grid[gridR] ? depth_grid[gridR][c] || 0 : 0;
          const idx = (r * numCols + c) * 4;
          const [red, green, blue, alpha] = getFloodColor(depth);
          data[idx] = red;
          data[idx + 1] = green;
          data[idx + 2] = blue;
          data[idx + 3] = alpha;
        }
      }

      baseCtx.putImageData(imgData, 0, 0);

      // High-resolution bilinear upsampling to eliminate chunky pixels
      const targetW = Math.max(800, numCols * 4);
      const targetH = Math.max(800, numRows * 4);
      const smoothCanvas = document.createElement('canvas');
      smoothCanvas.width = targetW;
      smoothCanvas.height = targetH;
      const smoothCtx = smoothCanvas.getContext('2d');
      if (!smoothCtx) return;

      smoothCtx.imageSmoothingEnabled = true;
      smoothCtx.imageSmoothingQuality = 'high';
      smoothCtx.drawImage(baseCanvas, 0, 0, targetW, targetH);

      const dataUrl = smoothCanvas.toDataURL();

      if (floodRasterLayerRef.current) {
        floodRasterLayerRef.current.setUrl(dataUrl);
        floodRasterLayerRef.current.setBounds(L.latLngBounds(simulationBounds as any));
        if (showFloodHeatmap && mapInstanceRef.current && !mapInstanceRef.current.hasLayer(floodRasterLayerRef.current)) {
          mapInstanceRef.current.addLayer(floodRasterLayerRef.current);
        }
      } else {
        const overlay = L.imageOverlay(dataUrl, simulationBounds, {
          opacity: 0.95,
          interactive: false,
          pane: 'floodPane',
        });
        if (showFloodHeatmap) {
          overlay.addTo(mapInstanceRef.current);
        }
        floodRasterLayerRef.current = overlay;
      }
    };

    loadFloodRaster();
  }, [currentTimeStep, currentCity, simulationKey]);

  // 2b. Load & Render DEM Elevation Terrain Raster
  useEffect(() => {
    if (!mapInstanceRef.current) return;

    let isMounted = true;

    const loadDem = async () => {
      const demRes = await fetchDemGrid(currentCity);
      if (!demRes || !isMounted || !mapInstanceRef.current) return;

      setDemMeta({
        min: demRes.min_elevation_m,
        max: demRes.max_elevation_m,
        mean: demRes.mean_elevation_m,
      });

      const dataUrl = renderDemCanvas(
        demRes.grid,
        demRes.min_elevation_m,
        demRes.max_elevation_m,
        demRes.cell_size_m
      );
      if (!dataUrl || !isMounted) return;

      const bounds = isKolkata
        ? [[22.5050, 88.3850], [22.6020, 88.4380]]
        : simulationBounds;

      if (demRasterLayerRef.current) {
        demRasterLayerRef.current.setUrl(dataUrl);
        demRasterLayerRef.current.setBounds(L.latLngBounds(bounds as any));
        if (showDemTerrain && mapInstanceRef.current && !mapInstanceRef.current.hasLayer(demRasterLayerRef.current)) {
          mapInstanceRef.current.addLayer(demRasterLayerRef.current);
        }
      } else {
        const overlay = L.imageOverlay(dataUrl, bounds as L.LatLngBoundsExpression, {
          opacity: 0.65,
          interactive: false,
          pane: 'demPane',
        });
        demRasterLayerRef.current = overlay;
      }

      if (showDemTerrain && demRasterLayerRef.current && mapInstanceRef.current) {
        if (!mapInstanceRef.current.hasLayer(demRasterLayerRef.current)) {
          mapInstanceRef.current.addLayer(demRasterLayerRef.current);
        }
      }
    };

    loadDem();

    return () => {
      isMounted = false;
    };
  }, [currentCity]);

  // Handle DEM Layer Visibility
  useEffect(() => {
    if (!mapInstanceRef.current || !demRasterLayerRef.current) return;
    if (showDemTerrain) {
      if (!mapInstanceRef.current.hasLayer(demRasterLayerRef.current)) {
        mapInstanceRef.current.addLayer(demRasterLayerRef.current);
      }
    } else {
      if (mapInstanceRef.current.hasLayer(demRasterLayerRef.current)) {
        mapInstanceRef.current.removeLayer(demRasterLayerRef.current);
      }
    }
  }, [showDemTerrain]);

  // Handle Layer Visibility Toggles
  useEffect(() => {
    if (!mapInstanceRef.current || !floodRasterLayerRef.current) return;
    if (showFloodHeatmap) {
      if (!mapInstanceRef.current.hasLayer(floodRasterLayerRef.current)) {
        mapInstanceRef.current.addLayer(floodRasterLayerRef.current);
      }
    } else {
      if (mapInstanceRef.current.hasLayer(floodRasterLayerRef.current)) {
        mapInstanceRef.current.removeLayer(floodRasterLayerRef.current);
      }
    }
  }, [showFloodHeatmap]);

  useEffect(() => {
    if (!mapInstanceRef.current || !roadsLayerRef.current) return;
    if (showRoads) {
      if (!mapInstanceRef.current.hasLayer(roadsLayerRef.current)) {
        mapInstanceRef.current.addLayer(roadsLayerRef.current);
      }
    } else {
      if (mapInstanceRef.current.hasLayer(roadsLayerRef.current)) {
        mapInstanceRef.current.removeLayer(roadsLayerRef.current);
      }
    }
  }, [showRoads]);

  useEffect(() => {
    if (!mapInstanceRef.current || !hotspotsLayerRef.current) return;
    if (showHotspots) {
      if (!mapInstanceRef.current.hasLayer(hotspotsLayerRef.current)) {
        mapInstanceRef.current.addLayer(hotspotsLayerRef.current);
      }
    } else {
      if (mapInstanceRef.current.hasLayer(hotspotsLayerRef.current)) {
        mapInstanceRef.current.removeLayer(hotspotsLayerRef.current);
      }
    }
  }, [showHotspots]);

  useEffect(() => {
    if (!mapInstanceRef.current) return;
    if (showDrainagePipes) {
      if (drainagePipesLayerRef.current && !mapInstanceRef.current.hasLayer(drainagePipesLayerRef.current)) {
        mapInstanceRef.current.addLayer(drainagePipesLayerRef.current);
      }
      if (drainageNodesLayerRef.current && !mapInstanceRef.current.hasLayer(drainageNodesLayerRef.current)) {
        mapInstanceRef.current.addLayer(drainageNodesLayerRef.current);
      }
    } else {
      if (drainagePipesLayerRef.current && mapInstanceRef.current.hasLayer(drainagePipesLayerRef.current)) {
        mapInstanceRef.current.removeLayer(drainagePipesLayerRef.current);
      }
      if (drainageNodesLayerRef.current && mapInstanceRef.current.hasLayer(drainageNodesLayerRef.current)) {
        mapInstanceRef.current.removeLayer(drainageNodesLayerRef.current);
      }
    }
  }, [showDrainagePipes]);

  // Re-fetch and update drainage pipes & nodes when blockage or network state changes
  useEffect(() => {
    if (!mapInstanceRef.current || drainageRefreshKey === 0) return;

    let isCancelled = false;
    const refreshDrainage = async () => {
      try {
        const [drainageEdges, drainageNodes] = await Promise.all([
          fetchDrainageEdges(currentCity),
          fetchDrainageNodes(currentCity),
        ]);

        if (isCancelled || !mapInstanceRef.current) return;

        // Clean up old layers
        if (drainagePipesLayerRef.current && mapInstanceRef.current.hasLayer(drainagePipesLayerRef.current)) {
          mapInstanceRef.current.removeLayer(drainagePipesLayerRef.current);
        }
        if (drainageNodesLayerRef.current && mapInstanceRef.current.hasLayer(drainageNodesLayerRef.current)) {
          mapInstanceRef.current.removeLayer(drainageNodesLayerRef.current);
        }

        if (drainageEdges) {
          setDrainagePipeCount(drainageEdges.features.length);
          const pipeLayer = L.geoJSON(drainageEdges as any, {
            pane: 'drainagePane',
            style: (feature: any) => {
              const blk = feature?.properties?.blockage_pct || 0;
              const isOver = feature?.properties?.is_surcharging;
              return {
                color: isOver ? '#EF4444' : blk > 0.3 ? '#F59E0B' : '#10B981',
                weight: blk > 0.3 ? 3.8 : 2.6,
                dashArray: '6, 5',
                opacity: 0.95,
              };
            },
            onEachFeature: (feature: any, layer: any) => {
              const p = feature.properties || {};
              const id = p.id || 'Pipe';
              const dia = p.diameter_m ? `${(p.diameter_m * 1000).toFixed(0)}mm` : '600mm';
              const cap = p.effective_capacity_m3s ? `${p.effective_capacity_m3s.toFixed(2)} m³/s` : '1.5 m³/s';
              const blk = p.blockage_pct ? `${(p.blockage_pct * 100).toFixed(0)}%` : '0%';
              layer.bindPopup(`
                <div style="font-family: 'Inter', sans-serif; padding: 6px; color: #F8FAFC; background: #0F172A; border-radius: 8px; border: 1px solid rgba(16, 185, 129, 0.4);">
                  <div style="font-weight: 700; font-size: 13px; color: #10B981; margin-bottom: 4px;">CONDUIT: ${id}</div>
                  <div style="font-size: 11px; color: #94A3B8;">Diameter: <span style="color: #E2E8F0; font-weight: 600;">${dia}</span></div>
                  <div style="font-size: 11px; color: #94A3B8;">Manning Capacity: <span style="color: #38BDF8; font-weight: 600;">${cap}</span></div>
                  <div style="font-size: 11px; color: #94A3B8;">Debris Blockage: <span style="color: ${p.blockage_pct > 0.3 ? '#F59E0B' : '#34D399'}; font-weight: 600;">${blk}</span></div>
                </div>
              `);
            },
          } as any);
          drainagePipesLayerRef.current = pipeLayer;
          if (showDrainagePipes) pipeLayer.addTo(mapInstanceRef.current);
        }

        if (drainageNodes) {
          const nodesGroup = L.layerGroup();
          let surcharges = 0;

          drainageNodes.features.forEach((feat) => {
            const coords = feat.geometry?.coordinates;
            if (coords && coords.length >= 2) {
              const lng = coords[0];
              const lat = coords[1];
              const p = feat.properties || {};
              const nodeType = p.type || 'inlet';
              const isOver = p.is_overflowing || (p.stress_ratio && p.stress_ratio >= 1.0);
              if (isOver) surcharges++;

              if (isOver || nodeType === 'outfall') {
                const marker = L.circleMarker([lat, lng], {
                  pane: 'drainagePane',
                  radius: isOver ? 7.5 : 6.0,
                  color: isOver ? '#EF4444' : '#06B6D4',
                  fillColor: isOver ? '#DC2626' : '#0284C7',
                  weight: 2.5,
                  opacity: 1.0,
                  fillOpacity: 0.9,
                }).bindPopup(`
                  <div style="font-family: 'Inter', sans-serif; padding: 6px; color: #F8FAFC; background: #0F172A; border-radius: 8px;">
                    <div style="font-weight: 700; font-size: 13px; color: ${isOver ? '#EF4444' : '#38BDF8'}; margin-bottom: 4px;">
                      ${isOver ? '⚠️ SURCHARGING MANHOLE' : '🌊 CANAL / RIVER OUTFALL'} (${p.id})
                    </div>
                    <div style="font-size: 11px; color: #94A3B8;">Elevation: <span style="color: #E2E8F0;">${p.elevation_m}m</span></div>
                    <div style="font-size: 11px; color: #94A3B8;">Hydraulic Stress: <span style="color: ${isOver ? '#EF4444' : '#34D399'}; font-weight: 600;">${((p.stress_ratio || 0) * 100).toFixed(0)}%</span></div>
                    <div style="font-size: 11px; color: #94A3B8;">Stored Water: <span style="color: #38BDF8;">${p.current_water_m3 ? p.current_water_m3.toFixed(2) : '0'} m³</span></div>
                  </div>
                `);

                nodesGroup.addLayer(marker);
              }
            }
          });

          drainageNodesLayerRef.current = nodesGroup;
          if (onDrainageSummaryLoaded) onDrainageSummaryLoaded(surcharges);
          if (showDrainagePipes) nodesGroup.addTo(mapInstanceRef.current);
        }
      } catch (err) {
        console.error('Error refreshing drainage layers:', err);
      }
    };

    refreshDrainage();
    return () => {
      isCancelled = true;
    };
  }, [drainageRefreshKey, currentCity, showDrainagePipes]);

  // 3. WAYPOINT PINS: Origin (Point A) and Destination (Point B)
  // Rendered INDEPENDENTLY of route calculation so selecting dropdowns immediately marks them!
  useEffect(() => {
    if (!mapInstanceRef.current) return;

    if (!waypointsLayerRef.current) {
      waypointsLayerRef.current = L.layerGroup().addTo(mapInstanceRef.current);
    } else {
      waypointsLayerRef.current.clearLayers();
    }

    // Origin Pin (Point A - Vivid Emerald)
    if (originCoords) {
      const iconA = L.divIcon({
        className: 'custom-route-pin-a',
        html: `
          <div style="position: relative; width: 34px; height: 34px; display: flex; align-items: center; justify-content: center;">
            <div style="position: absolute; inset: -4px; border-radius: 50%; background: rgba(16, 185, 129, 0.4); animation: ping 2s cubic-bezier(0, 0, 0.2, 1) infinite;"></div>
            <div style="
              width: 30px; height: 30px; border-radius: 50%;
              background: #10B981; border: 3px solid #FFFFFF;
              color: #020617; font-weight: 900; font-size: 14px;
              display: flex; align-items: center; justify-content: center;
              box-shadow: 0 0 20px rgba(16, 185, 129, 0.95);
              font-family: 'Inter', sans-serif;
            ">A</div>
          </div>
        `,
        iconSize: [34, 34],
        iconAnchor: [17, 17],
      });

      L.marker(originCoords, { icon: iconA })
        .bindTooltip(`📍 ORIGIN (A): ${originName || 'Point A'}`, {
          direction: 'top',
          permanent: true,
          className: 'custom-leaflet-tooltip font-bold text-emerald-300',
        })
        .addTo(waypointsLayerRef.current);
    }

    // Destination Pin (Point B - Vivid Crimson)
    if (destinationCoords) {
      const iconB = L.divIcon({
        className: 'custom-route-pin-b',
        html: `
          <div style="position: relative; width: 34px; height: 34px; display: flex; align-items: center; justify-content: center;">
            <div style="position: absolute; inset: -4px; border-radius: 50%; background: rgba(239, 68, 68, 0.4); animation: ping 2s cubic-bezier(0, 0, 0.2, 1) infinite;"></div>
            <div style="
              width: 30px; height: 30px; border-radius: 50%;
              background: #EF4444; border: 3px solid #FFFFFF;
              color: #FFFFFF; font-weight: 900; font-size: 14px;
              display: flex; align-items: center; justify-content: center;
              box-shadow: 0 0 20px rgba(239, 68, 68, 0.95);
              font-family: 'Inter', sans-serif;
            ">B</div>
          </div>
        `,
        iconSize: [34, 34],
        iconAnchor: [17, 17],
      });

      L.marker(destinationCoords, { icon: iconB })
        .bindTooltip(`🎯 DESTINATION (B): ${destinationName || 'Point B'}`, {
          direction: 'top',
          permanent: true,
          className: 'custom-leaflet-tooltip font-bold text-red-300',
        })
        .addTo(waypointsLayerRef.current);
    }

    // If both waypoints exist but no route yet, gently fit map to encompass both
    if (originCoords && destinationCoords && (!routeResult || !routeResult.geojson)) {
      const bounds = L.latLngBounds([originCoords, destinationCoords]);
      mapInstanceRef.current.fitBounds(bounds, { padding: [80, 80], maxZoom: 15 });
    }
  }, [originCoords, destinationCoords, originName, destinationName, routeResult]);

  // 4. ROUTE RENDERING: Primary Safest Route & Alternative Detours
  useEffect(() => {
    if (!mapInstanceRef.current) return;

    if (!routeLayerRef.current) {
      routeLayerRef.current = L.layerGroup().addTo(mapInstanceRef.current);
    } else {
      routeLayerRef.current.clearLayers();
    }

    const boundsList: L.LatLngBounds[] = [];

    // A. Render Alternative Routes (Subtle ghost traces by default; ONLY prominently highlighted on click)
    if (alternatives && alternatives.length > 0) {
      alternatives.forEach((alt, idx) => {
        if (!alt.geojson) return;
        const isSelected = activeRouteIndex === idx + 1;
        const altColor = idx === 0 ? '#F59E0B' : '#06B6D4';
        const altName = `ALTERNATIVE DETOUR ${idx + 1}`;

        // Glowing outer halo ONLY for the active clicked alternative
        if (isSelected) {
          L.geoJSON(alt.geojson as any, {
            style: {
              color: altColor,
              weight: 12,
              opacity: 0.45,
              lineCap: 'round',
              lineJoin: 'round',
            },
          }).addTo(routeLayerRef.current!);
        }

        const altLayer = L.geoJSON(alt.geojson as any, {
          style: {
            color: isSelected ? altColor : '#64748B',
            weight: isSelected ? 5.5 : 2.5,
            dashArray: isSelected ? '8, 5' : '4, 6',
            opacity: isSelected ? 1.0 : 0.25, // Unselected is subtle ghost trace
            lineCap: 'round',
          },
          onEachFeature: (_, layer) => {
            layer.bindPopup(`
              <div style="font-family: 'Inter', sans-serif; padding: 8px; color: #F8FAFC; background: #0E1223; border-radius: 12px; border: 1.5px solid ${altColor}; min-width: 210px;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
                  <span style="font-weight: 800; font-size: 13px; color: ${altColor};">${altName}</span>
                  <span style="font-size: 10px; background: ${isSelected ? 'rgba(245, 158, 11, 0.25)' : 'rgba(100, 116, 139, 0.25)'}; color: ${altColor}; padding: 2px 6px; border-radius: 9999px; font-weight: 700;">
                    ${isSelected ? 'ACTIVE FOCUS' : 'CLICK TO FOCUS'}
                  </span>
                </div>
                <div style="font-size: 11px; margin-bottom: 3px;">Distance: <b>${(alt.distance_m / 1000).toFixed(2)} km</b></div>
                <div style="font-size: 11px; margin-bottom: 3px;">Est. Time: <b>${alt.travel_time_min.toFixed(1)} min</b></div>
                <div style="font-size: 11px; margin-bottom: 3px;">Max Depth: <b style="color: ${alt.max_flood_depth_m > 0.15 ? '#F59E0B' : '#34D399'};">${(alt.max_flood_depth_m * 100).toFixed(1)} cm</b></div>
                <div style="font-size: 11px; color: ${altColor}; font-weight: 700; margin-top: 4px;">Status: ${alt.flood_risk} PASSAGE</div>
                <div style="font-size: 9px; color: #94A3B8; margin-top: 4px;">Secondary evacuation detour route</div>
              </div>
            `);
            layer.on({
              click: () => {
                if (onSelectRouteIndex) onSelectRouteIndex(idx + 1);
              },
              mouseover: (e) => {
                if (!isSelected) {
                  e.target.setStyle({ weight: 4.5, opacity: 0.85, color: altColor });
                }
              },
              mouseout: (e) => {
                if (!isSelected) {
                  altLayer.resetStyle(e.target);
                }
              }
            });
          },
        }).addTo(routeLayerRef.current!);

        if (isSelected) {
          altLayer.bringToFront();
          const b = altLayer.getBounds();
          if (b.isValid()) boundsList.push(b);
        }
      });
    }

    // B. Render Recommended Safest Route (Glowing Solid Emerald)
    if (routeResult && routeResult.geojson) {
      const isSelected = activeRouteIndex === 0;
      const routeGeoJson = routeResult.geojson;

      // Glowing outer halo ONLY when primary safest route is active focus
      if (isSelected) {
        L.geoJSON(routeGeoJson as any, {
          style: {
            color: '#10B981',
            weight: 12,
            opacity: 0.45,
            lineCap: 'round',
            lineJoin: 'round',
          },
        }).addTo(routeLayerRef.current);
      }

      // Inner crisp high-contrast core
      const coreLayer = L.geoJSON(routeGeoJson as any, {
        style: {
          color: isSelected ? '#34D399' : '#059669',
          weight: isSelected ? 5.0 : 3.0,
          opacity: isSelected ? 1.0 : 0.60,
          lineCap: 'round',
          lineJoin: 'round',
        },
        onEachFeature: (_, layer) => {
          layer.bindPopup(`
            <div style="font-family: 'Inter', sans-serif; padding: 6px; color: #F8FAFC; background: #0E1223; border-radius: 12px; border: 1.5px solid #10B981;">
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
                <span style="font-weight: 800; font-size: 13px; color: #34D399;">★ RECOMMENDED SAFEST ROUTE</span>
                <span style="font-size: 10px; background: rgba(16, 185, 129, 0.2); color: #34D399; padding: 2px 6px; border-radius: 9999px; font-weight: 700;">LOWEST FLOOD EXPOSURE</span>
              </div>
              <div style="font-size: 11px; margin-bottom: 3px;">Distance: <b>${(routeResult.distance_m / 1000).toFixed(2)} km</b></div>
              <div style="font-size: 11px; margin-bottom: 3px;">Travel Time: <b>${routeResult.travel_time_min.toFixed(1)} min</b></div>
              <div style="font-size: 11px; margin-bottom: 3px;">Max Flood Depth: <b style="color: ${routeResult.max_flood_depth_m > 0.15 ? '#F59E0B' : '#34D399'};">${(routeResult.max_flood_depth_m * 100).toFixed(1)} cm</b></div>
              <div style="font-size: 11px; color: #10B981; font-weight: 700; margin-top: 4px;">Hydrodynamic Risk: ${routeResult.flood_risk} PASSAGE</div>
              ${routeResult.roads_avoided?.length ? `<div style="font-size: 10px; color: #F87171; margin-top: 4px;">⚠️ Safely avoided ${routeResult.roads_avoided.length} submerged road segments</div>` : ''}
            </div>
          `);
          layer.on({
            click: () => {
              if (onSelectRouteIndex) onSelectRouteIndex(0);
            },
            mouseover: (e) => {
              e.target.setStyle({ weight: 6, opacity: 1.0 });
            },
            mouseout: (e) => {
              coreLayer.resetStyle(e.target);
            }
          });
        },
      }).addTo(routeLayerRef.current);

      if (isSelected) {
        coreLayer.bringToFront();
        const b = coreLayer.getBounds();
        if (b.isValid()) boundsList.push(b);
      }
    }

  }, [routeResult, alternatives, activeRouteIndex, onSelectRouteIndex]);

  // HUD Controls
  const handleZoomIn = () => mapInstanceRef.current?.zoomIn();
  const handleZoomOut = () => mapInstanceRef.current?.zoomOut();
  const handleRecenter = () => {
    if (mapInstanceRef.current) {
      mapInstanceRef.current.setView([centerLat, centerLon], zoomLevel, { animate: true });
    }
  };

  return (
    <div className="relative w-full h-full overflow-hidden">
      
      {/* Map DOM Container */}
      <div ref={mapContainerRef} className="w-full h-full z-0" />

      {/* Loading Overlay Badge */}
      {isLoading && (
        <div className="absolute top-4 left-4 z-20 flex items-center space-x-2 px-3.5 py-1.5 rounded-xl bg-slate-900/90 border border-cyan-500/40 text-xs text-cyan-300 backdrop-blur-md shadow-xl font-mono-num animate-pulse">
          <span className="h-2 w-2 rounded-full bg-cyan-400" />
          <span>INGESTING {currentCity.toUpperCase()} VECTOR ROADS & HOTSPOTS...</span>
        </div>
      )}

      {/* Consolidated Mission-Control Status Card (Top Left) */}
      {!isLoading && (
        <div className="absolute top-4 left-4 z-20 pointer-events-auto">
          <div className="rounded-2xl bg-slate-950/85 border border-slate-800/90 shadow-xl backdrop-blur-md px-3.5 py-2.5 flex items-center space-x-3 text-xs">
            <span className="h-2 w-2 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_6px_#22d3ee]" />
            <div className="flex flex-col">
              <div className="flex items-center space-x-1.5 font-bold tracking-wide text-slate-200">
                <span className="uppercase text-cyan-400 font-semibold">{currentCity}</span>
                <span className="text-slate-600">·</span>
                <span className="font-mono text-slate-300">{roadCount} roads</span>
                <span className="text-slate-600">·</span>
                <span className="font-mono text-amber-400">{hotspotCount} hotspots</span>
              </div>
              <div className="flex items-center space-x-1.5 text-[11px] text-slate-400 font-mono mt-0.5">
                <span>Forecast +{currentTimeStep}m</span>
                <span className="text-slate-600">·</span>
                <span>Peak depth <strong className={activePeakDepth > 0.3 ? 'text-rose-400' : activePeakDepth > 0.15 ? 'text-amber-400' : 'text-cyan-300'}>{activePeakDepth.toFixed(2)}m</strong></span>
                {showDrainagePipes && (
                  <>
                    <span className="text-slate-600">·</span>
                    <span className="text-emerald-400">{drainagePipeCount} pipes</span>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Floating MAP LEGEND Button & Popover (Bottom Left) */}
      <div className="absolute bottom-6 left-4 z-20 transition-all">
        {isLegendOpen && (
          <div className="mb-2 rounded-2xl bg-slate-950/92 border border-slate-800 shadow-2xl backdrop-blur-xl p-3.5 space-y-2.5 text-[11px] font-mono-num text-slate-300 w-72 max-h-80 overflow-y-auto animate-in fade-in slide-in-from-bottom-2 duration-150">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800/80 text-xs font-bold text-white">
              <span className="flex items-center space-x-1.5 text-cyan-400">
                <Info className="h-3.5 w-3.5" />
                <span>MAP SYMBOLOGY</span>
              </span>
              <button
                onClick={() => setIsLegendOpen(false)}
                className="text-slate-400 hover:text-white p-0.5 cursor-pointer"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>

            {/* Waypoints */}
            <div className="flex items-center justify-between">
              <span className="flex items-center space-x-2">
                <span className="h-3.5 w-3.5 rounded-full bg-emerald-500 border border-white flex items-center justify-center text-[8px] font-bold text-black">A</span>
                <span>Origin Waypoint</span>
              </span>
              <span className="text-emerald-400 font-bold">Point A</span>
            </div>

            <div className="flex items-center justify-between">
              <span className="flex items-center space-x-2">
                <span className="h-3.5 w-3.5 rounded-full bg-red-500 border border-white flex items-center justify-center text-[8px] font-bold text-white">B</span>
                <span>Destination Waypoint</span>
              </span>
              <span className="text-red-400 font-bold">Point B</span>
            </div>

            <div className="h-px bg-slate-800" />

            {/* Routes */}
            <div className="flex items-center justify-between">
              <span className="flex items-center space-x-2">
                <span className="h-1.5 w-5 rounded-full bg-emerald-400 shadow-[0_0_6px_#34d399]" />
                <span>★ Safest Route</span>
              </span>
              <span className="text-emerald-300 font-semibold">Emerald</span>
            </div>

            <div className="flex items-center justify-between">
              <span className="flex items-center space-x-2">
                <span className="h-1 w-5 border-b-2 border-dashed border-amber-400" />
                <span>Alternative Detour</span>
              </span>
              <span className="text-amber-400 font-semibold text-[10px]">Ghost line</span>
            </div>

            <div className="h-px bg-slate-800" />

            {/* Hydrodynamic Flood Depth Continuous Scale */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-[10px] text-slate-400">
                <span className="uppercase tracking-wider font-bold text-cyan-400">Hydrodynamic Depth (m)</span>
                <span className="text-slate-500 font-mono">Bilinear Raster</span>
              </div>
              <div className="h-2 w-full rounded-full bg-gradient-to-r from-cyan-400 via-sky-500 via-amber-400 via-red-500 to-fuchsia-600 shadow-inner" />
              <div className="flex items-center justify-between text-[9px] font-mono-num text-slate-400">
                <span>&lt;8cm (Shallow)</span>
                <span className="text-amber-400">15-30cm (Caution)</span>
                <span className="text-red-400">&gt;30cm (Severe)</span>
                <span className="text-fuchsia-400">&gt;50cm</span>
              </div>
            </div>

            {/* DEM Elevation Scale (Shown when DEM is active) */}
            {showDemTerrain && (
              <>
                <div className="h-px bg-slate-800" />
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-[10px] text-slate-400">
                    <span className="uppercase tracking-wider font-bold text-emerald-400 flex items-center space-x-1">
                      <Mountain className="h-3 w-3" />
                      <span>DEM Elevation (ASL)</span>
                    </span>
                    <span className="text-emerald-400/80 font-mono text-[9px]">
                      {demMeta ? `${demMeta.min.toFixed(1)}m – ${demMeta.max.toFixed(1)}m` : '3D Topo'}
                    </span>
                  </div>
                  <div className="h-2 w-full rounded-full bg-gradient-to-r from-emerald-600 via-lime-500 via-amber-500 via-orange-800 to-slate-100 shadow-inner" />
                  <div className="flex items-center justify-between text-[9px] font-mono-num text-slate-400">
                    <span className="text-emerald-400">Low (&lt;3m)</span>
                    <span className="text-amber-400">Terrace (5-10m)</span>
                    <span className="text-slate-200">Ridge (&gt;15m)</span>
                  </div>
                </div>
              </>
            )}

            <div className="h-px bg-slate-800" />

            {/* Hotspots and Subterranean Drainage */}
            <div className="flex items-center justify-between">
              <span className="flex items-center space-x-2">
                <span className="h-2.5 w-2.5 rounded-full bg-amber-500 border border-amber-600" />
                <span>Elevation Hotspots</span>
              </span>
              <span className="text-amber-400 text-[10px]">Clustered</span>
            </div>

            {showDrainagePipes && (
              <div className="flex items-center justify-between">
                <span className="flex items-center space-x-2">
                  <span className="h-1 w-5 border-b-2 border-dotted border-emerald-500" />
                  <span>Drainage Conduits</span>
                </span>
                <span className="text-emerald-400 font-mono text-[10px]">Active</span>
              </div>
            )}
          </div>
        )}

        <button
          onClick={() => setIsLegendOpen(!isLegendOpen)}
          className={`flex items-center space-x-2 px-3 py-1.5 rounded-xl border text-xs font-mono font-semibold backdrop-blur-md shadow-lg transition-all cursor-pointer ${
            isLegendOpen
              ? 'bg-cyan-950/80 border-cyan-500/50 text-cyan-300 shadow-cyan-950/50'
              : 'bg-slate-950/85 border-slate-800/90 text-slate-300 hover:text-white hover:border-slate-700'
          }`}
        >
          <Info className="h-3.5 w-3.5 text-cyan-400" />
          <span>Legend</span>
        </button>
      </div>

      {/* Floating HUD Map Control Buttons (Bottom Right) */}
      <div className="absolute bottom-6 right-6 z-20 flex flex-col space-y-2">
        <button
          onClick={handleRecenter}
          title={`Recenter ${currentCity} Bounds`}
          className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-900/90 border border-slate-800 text-slate-200 hover:bg-slate-800 hover:text-cyan-300 transition-all shadow-xl backdrop-blur-md cursor-pointer active:scale-95"
        >
          <Compass className="h-4 w-4" />
        </button>

        <button
          onClick={handleZoomIn}
          title="Zoom In"
          className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-900/90 border border-slate-800 text-slate-200 hover:bg-slate-800 hover:text-cyan-300 transition-all shadow-xl backdrop-blur-md cursor-pointer active:scale-95"
        >
          <ZoomIn className="h-4 w-4" />
        </button>

        <button
          onClick={handleZoomOut}
          title="Zoom Out"
          className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-900/90 border border-slate-800 text-slate-200 hover:bg-slate-800 hover:text-cyan-300 transition-all shadow-xl backdrop-blur-md cursor-pointer active:scale-95"
        >
          <ZoomOut className="h-4 w-4" />
        </button>
      </div>

    </div>
  );
};
