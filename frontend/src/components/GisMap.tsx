import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import { 
  fetchRoadNetwork, 
  fetchFloodHotspots, 
  fetchFloodGrid, 
  fetchDemGrid,
  queryPointDepth,
  fetchDrainageNodes,
  fetchDrainageEdges,
  fetchTrafficOverlay,
  fetchRoadPassabilityGrid,
  type RoadPassabilityItem
} from '../services/api';
import type { RouteResult } from '../services/api';
import type { TransportMode } from './RoutePanel';
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
  /** Live GPS coordinates from the browser — renders a pulsing blue dot */
  userLocation?: [number, number] | null;
  isNavigating?: boolean;
  navLocation?: [number, number] | null;
  navBearing?: number;
  navTraversedCoords?: [number, number][];
  navRemainingCoords?: [number, number][];
  isFollowMode?: boolean;
  onMapUserDrag?: () => void;
  showTrafficLayer?: boolean;
  trafficTileUrl?: string | null;
  trafficMode?: 'peak_monsoon' | 'live';
  selectedVehicle?: TransportMode;
  navViewMode?: '3d' | '2d';
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
  userLocation = null,
  isNavigating = false,
  navLocation,
  navBearing = 0,
  navTraversedCoords = [],
  navRemainingCoords = [],
  isFollowMode = true,
  onMapUserDrag,
  showTrafficLayer = false,
  trafficTileUrl,
  trafficMode = 'peak_monsoon',
  selectedVehicle = 'ambulance',
  navViewMode = '3d',
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
  const userLocationMarkerRef = useRef<L.Marker | null>(null);
  const navLayerRef = useRef<L.LayerGroup | null>(null);
  const trafficTileLayerRef = useRef<L.TileLayer | null>(null);
  const trafficVectorLayerRef = useRef<L.GeoJSON | null>(null);
  const trafficBottleneckMarkersLayerRef = useRef<L.LayerGroup | null>(null);
  const prevNavigatingRef = useRef<boolean>(false);

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [mapReadyKey, setMapReadyKey] = useState<number>(0);
  const [roadCount, setRoadCount] = useState<number>(0);
  const [hotspotCount, setHotspotCount] = useState<number>(0);
  const [drainagePipeCount, setDrainagePipeCount] = useState<number>(0);
  const [activePeakDepth, setActivePeakDepth] = useState<number>(0);
  const [demMeta, setDemMeta] = useState<{ min: number; max: number; mean: number } | null>(null);
  const [isLegendOpen, setIsLegendOpen] = useState<boolean>(false);

  const [passabilityMap, setPassabilityMap] = useState<Record<string, RoadPassabilityItem>>({});
  const [passabilityStats, setPassabilityStats] = useState<{ open: number; restricted: number; closed: number; total: number } | null>(null);
  const passabilityMapRef = useRef<Record<string, RoadPassabilityItem>>({});
  passabilityMapRef.current = passabilityMap;

  const getRoadStyle = (feature: any) => {
    const roadId = feature?.properties?.id;
    const pInfo = passabilityMapRef.current[roadId];
    if (pInfo) {
      if (pInfo.status === 'CLOSED') {
        return { color: '#EF4444', weight: 3.4, opacity: 0.95, dashArray: '5, 5' };
      } else if (pInfo.status === 'RESTRICTED') {
        return { color: '#F59E0B', weight: 2.6, opacity: 0.88 };
      } else {
        const ht = (feature?.properties?.highway_type || feature?.properties?.highway || '').toLowerCase();
        if (ht.includes('primary') || ht.includes('trunk') || ht.includes('motorway')) {
          return { color: '#10B981', weight: 2.4, opacity: 0.8 };
        }
        return { color: '#10B981', weight: 1.6, opacity: 0.6 };
      }
    }
    const ht = (feature?.properties?.highway_type || feature?.properties?.highway || '').toLowerCase();
    if (ht.includes('primary') || ht.includes('trunk') || ht.includes('motorway')) {
      return { color: '#94A3B8', weight: 2.2, opacity: 0.65 };
    } else if (ht.includes('secondary')) {
      return { color: '#64748B', weight: 1.6, opacity: 0.45 };
    } else if (ht.includes('tertiary')) {
      return { color: '#475569', weight: 1.2, opacity: 0.35 };
    }
    return { color: '#334155', weight: 0.8, opacity: 0.25 };
  };

  const generateRoadPopupHtml = (feature: any) => {
    const p = feature.properties || {};
    const roadId = p.id;
    const pInfo = passabilityMapRef.current[roadId];
    const name = p.name || 'Unnamed Street';
    const ht = p.highway_type || p.highway || 'road';
    const len = p.length_m ? `${p.length_m.toFixed(1)}m` : 'N/A';
    const elev = p.elevation_m ? `${p.elevation_m.toFixed(1)}m` : 'N/A';
    const depthCm = pInfo ? pInfo.depth_cm : 0;
    const status = pInfo?.status || (depthCm > 0 ? 'RESTRICTED' : 'OPEN');
    const speedKmh = pInfo ? pInfo.speed_kmh : (p.maxspeed_kmh || 40);
    const congestion = pInfo?.congestion || 'FREE_FLOW';
    const delayMult = pInfo?.delay_mult || 1.0;

    const statusBg = status === 'CLOSED' ? '#EF4444' : status === 'RESTRICTED' ? '#F59E0B' : '#10B981';
    const statusText = status === 'CLOSED' ? 'CLOSED / IMPASSABLE' : status === 'RESTRICTED' ? 'CAUTION / RESTRICTED' : 'OPEN / PASSABLE';

    return `
      <div style="font-family: 'Inter', system-ui, sans-serif; padding: 6px 4px; color: #F8FAFC; min-width: 250px;">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
          <span style="font-weight: 800; font-size: 13px; color: #38BDF8;">${name}</span>
          <span style="background: ${statusBg}22; color: ${statusBg}; border: 1px solid ${statusBg}55; font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 4px; text-transform: uppercase;">
            ${statusText}
          </span>
        </div>
        <div style="font-size: 11px; color: #94A3B8; margin-bottom: 6px;">
          Type: <span style="color: #E2E8F0; text-transform: uppercase; font-weight: 600;">${ht}</span> · Elev: <span style="color: #34D399; font-weight: 600;">${elev}</span> · Len: <span style="color: #E2E8F0;">${len}</span>
        </div>
        
        <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 8px; padding: 8px; margin: 8px 0;">
          <div style="display: flex; justify-content: space-between; margin-bottom: 4px; font-size: 11px;">
            <span style="color: #94A3B8;">Water Inundation (T+${currentTimeStep}m):</span>
            <span style="font-weight: 800; font-family: monospace; color: ${depthCm >= 30 ? '#EF4444' : depthCm >= 15 ? '#F59E0B' : '#38BDF8'};">${depthCm.toFixed(1)} cm</span>
          </div>
          <div style="display: flex; justify-content: space-between; font-size: 11px;">
            <span style="color: #94A3B8;">Vehicle Selected:</span>
            <span style="font-weight: 700; color: #38BDF8; text-transform: capitalize;">${selectedVehicle}</span>
          </div>
          <div style="display: flex; justify-content: space-between; font-size: 11px; margin-top: 4px;">
            <span style="color: #94A3B8;">Traffic Flow:</span>
            <span style="font-weight: 700; color: ${congestion === 'HEAVY' ? '#EF4444' : congestion === 'MODERATE' ? '#F59E0B' : '#10B981'};">
              ${speedKmh} km/h (${congestion}, ${delayMult}x)
            </span>
          </div>
        </div>

        <div style="font-size: 10px; font-weight: 700; color: #94A3B8; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.05em;">
          Vehicle Clearance Matrix
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px; font-size: 10px;">
          <div style="display: flex; align-items: center; justify-content: space-between; padding: 3px 6px; background: rgba(30, 41, 59, 0.6); border-radius: 4px;">
            <span>🚶 Pedestrian (12cm)</span>
            <span>${depthCm < 12 ? '✅' : '❌'}</span>
          </div>
          <div style="display: flex; align-items: center; justify-content: space-between; padding: 3px 6px; background: rgba(30, 41, 59, 0.6); border-radius: 4px;">
            <span>🚲 Bicycle (18cm)</span>
            <span>${depthCm < 18 ? '✅' : '❌'}</span>
          </div>
          <div style="display: flex; align-items: center; justify-content: space-between; padding: 3px 6px; background: rgba(30, 41, 59, 0.6); border-radius: 4px;">
            <span>🚗 Sedan/Car (30cm)</span>
            <span>${depthCm < 30 ? '✅' : '❌'}</span>
          </div>
          <div style="display: flex; align-items: center; justify-content: space-between; padding: 3px 6px; background: rgba(30, 41, 59, 0.6); border-radius: 4px;">
            <span>🚙 SUV (45cm)</span>
            <span>${depthCm < 45 ? '✅' : '❌'}</span>
          </div>
          <div style="display: flex; align-items: center; justify-content: space-between; padding: 3px 6px; background: rgba(30, 41, 59, 0.6); border-radius: 4px;">
            <span>🚑 Ambulance (45cm)</span>
            <span>${depthCm < 45 ? '✅' : '❌'}</span>
          </div>
          <div style="display: flex; align-items: center; justify-content: space-between; padding: 3px 6px; background: rgba(30, 41, 59, 0.6); border-radius: 4px;">
            <span>🚛 Rescue (60cm)</span>
            <span>${depthCm < 60 ? '✅' : '❌'}</span>
          </div>
        </div>
      </div>
    `;
  };

  // Query dynamic passability whenever city, horizon, vehicle, or traffic mode changes
  useEffect(() => {
    let isCancelled = false;
    const loadPassability = async () => {
      const data = await fetchRoadPassabilityGrid(
        currentCity,
        currentTimeStep,
        selectedVehicle,
        trafficMode
      );
      if (isCancelled || !data) return;

      setPassabilityMap(data.roads || {});
      setPassabilityStats({
        open: data.open_count,
        restricted: data.restricted_count,
        closed: data.closed_count,
        total: data.total_roads,
      });

      if (roadsLayerRef.current) {
        roadsLayerRef.current.setStyle((feature: any) => {
          const roadId = feature?.properties?.id;
          const pInfo = data.roads?.[roadId];
          if (pInfo) {
            if (pInfo.status === 'CLOSED') {
              return { color: '#EF4444', weight: 3.4, opacity: 0.95, dashArray: '5, 5' };
            } else if (pInfo.status === 'RESTRICTED') {
              return { color: '#F59E0B', weight: 2.6, opacity: 0.88 };
            } else {
              const ht = (feature?.properties?.highway_type || feature?.properties?.highway || '').toLowerCase();
              if (ht.includes('primary') || ht.includes('trunk') || ht.includes('motorway')) {
                return { color: '#10B981', weight: 2.4, opacity: 0.8 };
              }
              return { color: '#10B981', weight: 1.6, opacity: 0.6 };
            }
          }
          const ht = (feature?.properties?.highway_type || feature?.properties?.highway || '').toLowerCase();
          if (ht.includes('primary') || ht.includes('trunk') || ht.includes('motorway')) {
            return { color: '#94A3B8', weight: 2.2, opacity: 0.65 };
          }
          return { color: '#475569', weight: 1.2, opacity: 0.35 };
        });
      }
    };

    loadPassability();
    return () => {
      isCancelled = true;
    };
  }, [currentCity, currentTimeStep, selectedVehicle, trafficMode, simulationKey, mapReadyKey]);

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
    userLocationMarkerRef.current = null;
    trafficTileLayerRef.current = null;
    trafficVectorLayerRef.current = null;
    trafficBottleneckMarkersLayerRef.current = null;

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

    // TomTom Live Traffic Raster Flow Pane: Sits directly above roads
    map.createPane('trafficPane');
    map.getPane('trafficPane')!.style.zIndex = '455';

    // Monsoon Peak Bottlenecks Vector Pane: Sits above TomTom raster tiles but under hotspots/routes
    map.createPane('trafficVectorPane');
    map.getPane('trafficVectorPane')!.style.zIndex = '465';

    map.createPane('hotspotsPane');
    map.getPane('hotspotsPane')!.style.zIndex = '480';

    map.createPane('routesPane');
    map.getPane('routesPane')!.style.zIndex = '520';

    // Navigation Active Route HUD Pane: Sits above standard routes but under waypoints
    map.createPane('navPane');
    map.getPane('navPane')!.style.zIndex = '540';

    map.createPane('waypointsPane');
    map.getPane('waypointsPane')!.style.zIndex = '550';

    // Live user location pane — sits above waypoints so the blue dot is always visible
    map.createPane('userLocationPane');
    map.getPane('userLocationPane')!.style.zIndex = '580';

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

    // Navigation Dynamic HUD Layer Group
    const navGroup = L.layerGroup().addTo(map);
    navLayerRef.current = navGroup;

    // Notify parent if user manually pans/drags map (to unlock follow mode)
    map.on('dragstart', () => {
      if (onMapUserDrag) onMapUserDrag();
    });

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
    setMapReadyKey((prev) => prev + 1);

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
            style: (feature: any) => getRoadStyle(feature),
            onEachFeature: (feature: any, layer: any) => {
              layer.bindPopup(() => generateRoadPopupHtml(feature));

              layer.on({
                mouseover: (e: any) => {
                  e.target.setStyle({ weight: 4.0, opacity: 1.0, color: '#06B6D4' });
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
      userLocationMarkerRef.current = null;
      trafficTileLayerRef.current = null;
      trafficVectorLayerRef.current = null;
      navLayerRef.current = null;
    };
  }, [currentCity]);

  // LIVE USER LOCATION: Render/Update pulsing blue dot whenever GPS coords change
  useEffect(() => {
    if (!mapInstanceRef.current) return;

    if (!userLocation) {
      // Remove marker if location is lost
      if (userLocationMarkerRef.current) {
        mapInstanceRef.current.removeLayer(userLocationMarkerRef.current);
        userLocationMarkerRef.current = null;
      }
      return;
    }

    const [lat, lng] = userLocation;

    const blueDotIcon = L.divIcon({
      className: 'user-location-dot',
      html: `
        <div style="position: relative; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center;">
          <!-- Outer accuracy pulse ring -->
          <div style="
            position: absolute;
            width: 48px; height: 48px;
            border-radius: 50%;
            background: rgba(59, 130, 246, 0.15);
            border: 1.5px solid rgba(59, 130, 246, 0.35);
            top: 50%; left: 50%;
            transform: translate(-50%, -50%);
            animation: user-loc-pulse 2.5s ease-out infinite;
          "></div>
          <!-- Inner solid blue dot -->
          <div style="
            width: 16px; height: 16px;
            border-radius: 50%;
            background: #3B82F6;
            border: 3px solid #FFFFFF;
            box-shadow: 0 0 12px rgba(59, 130, 246, 0.9), 0 2px 8px rgba(0,0,0,0.5);
            position: relative; z-index: 1;
          "></div>
        </div>
      `,
      iconSize: [24, 24],
      iconAnchor: [12, 12],
    });

    if (userLocationMarkerRef.current) {
      userLocationMarkerRef.current.setLatLng([lat, lng]);
      userLocationMarkerRef.current.setIcon(blueDotIcon);
    } else {
      const marker = L.marker([lat, lng], {
        icon: blueDotIcon,
        pane: 'userLocationPane',
        interactive: true,
        title: 'Your live location',
        zIndexOffset: 1000,
      }).bindTooltip('📍 Your live location', {
        direction: 'top',
        className: 'custom-leaflet-tooltip font-bold text-blue-300',
        offset: [0, -12],
      });
      marker.addTo(mapInstanceRef.current);
      userLocationMarkerRef.current = marker;
    }
  }, [userLocation]);

  // ─────────────────────────────────────────────────────────────────────────
  // LIVE & SIMULATED TOMTOM TRAFFIC OVERLAY
  // ─────────────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!mapInstanceRef.current) return;
    let isCancelled = false;

    // A. Handle TomTom Live Raster Flow Tiles (Active city-wide whenever traffic layer is toggled ON)
    const shouldUseTomTomTiles = showTrafficLayer && Boolean(trafficTileUrl);
    if (shouldUseTomTomTiles && trafficTileUrl) {
      if (!trafficTileLayerRef.current) {
        trafficTileLayerRef.current = L.tileLayer(trafficTileUrl, {
          pane: 'trafficPane',
          opacity: 0.85,
          maxZoom: 22,
        });
      }
      if (!mapInstanceRef.current.hasLayer(trafficTileLayerRef.current)) {
        trafficTileLayerRef.current.addTo(mapInstanceRef.current);
      }
    } else {
      if (trafficTileLayerRef.current && mapInstanceRef.current.hasLayer(trafficTileLayerRef.current)) {
        mapInstanceRef.current.removeLayer(trafficTileLayerRef.current);
      }
    }

    // Initialize or clear bottleneck callout markers layer group
    if (!trafficBottleneckMarkersLayerRef.current) {
      trafficBottleneckMarkersLayerRef.current = L.layerGroup().addTo(mapInstanceRef.current);
    }
    trafficBottleneckMarkersLayerRef.current.clearLayers();

    // B. Handle Vector Traffic Flow Layer (Peak Monsoon Gridlock Bottlenecks or Fallback Live Overlay)
    const shouldUseVectorTraffic = showTrafficLayer && (trafficMode === 'peak_monsoon' || !trafficTileUrl);
    if (shouldUseVectorTraffic) {
      fetchTrafficOverlay(currentCity, trafficMode).then((data) => {
        if (isCancelled || !mapInstanceRef.current) return;
        if (trafficVectorLayerRef.current && mapInstanceRef.current.hasLayer(trafficVectorLayerRef.current)) {
          mapInstanceRef.current.removeLayer(trafficVectorLayerRef.current);
          trafficVectorLayerRef.current = null;
        }
        if (data && data.features && data.features.length > 0) {
          const isPeak = trafficMode === 'peak_monsoon';
          const tLayer = L.geoJSON(data as any, {
            pane: 'trafficVectorPane',
            style: (feature: any) => {
              const p = feature?.properties || {};
              const cLevel = p.traffic_congestion_level;
              const color = p.traffic_color || (cLevel === 'HEAVY' ? '#EF4444' : cLevel === 'MODERATE' ? '#F59E0B' : '#22C55E');
              const weight = cLevel === 'HEAVY' ? (isPeak ? 5.5 : 4.2) : cLevel === 'MODERATE' ? 3.8 : 2.4;
              const opacity = cLevel === 'HEAVY' ? 0.98 : cLevel === 'MODERATE' ? 0.88 : 0.70;
              return { color, weight, opacity, lineCap: 'round', lineJoin: 'round' };
            },
            onEachFeature: (feature: any, layer: any) => {
              const p = feature.properties || {};
              const name = p.name || 'Arterial Corridor';
              const cLevel = p.traffic_congestion_level || 'FREE_FLOW';
              const spd = p.traffic_current_speed_kmh ? `${p.traffic_current_speed_kmh.toFixed(1)} km/h` : 'N/A';
              const freeSpd = p.traffic_free_flow_speed_kmh ? `${p.traffic_free_flow_speed_kmh.toFixed(1)} km/h` : 'N/A';
              const delay = p.traffic_delay_factor ? `${p.traffic_delay_factor.toFixed(1)}x slowdown` : '1.0x';
              const corridor = p.traffic_corridor || 'Study Area Corridor';
              const badgeColor = cLevel === 'HEAVY' ? '#EF4444' : cLevel === 'MODERATE' ? '#F59E0B' : '#10B981';
              const badgeBg = cLevel === 'HEAVY' ? 'rgba(239, 68, 68, 0.2)' : cLevel === 'MODERATE' ? 'rgba(245, 158, 11, 0.2)' : 'rgba(16, 185, 129, 0.2)';

              layer.bindPopup(`
                <div style="font-family: 'Inter', sans-serif; padding: 6px; color: #F8FAFC; min-width: 220px;">
                  <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
                    <span style="font-size: 10px; font-weight: 700; text-transform: uppercase; padding: 2px 6px; border-radius: 6px; background: ${badgeBg}; color: ${badgeColor}; border: 1px solid ${badgeColor}40;">
                      ${cLevel.replace('_', ' ')}
                    </span>
                    <span style="font-size: 9px; font-family: monospace; color: #F59E0B; font-weight: 600;">${p.traffic_mode === 'peak_monsoon' ? '⚡ MONSOON PEAK GRIDLOCK' : 'TOMTOM LIVE'}</span>
                  </div>
                  <div style="font-weight: 700; font-size: 13px; color: #F8FAFC; margin-bottom: 2px;">${name}</div>
                  <div style="font-size: 11px; color: #38BDF8; margin-bottom: 6px; font-weight: 500;">${corridor}</div>
                  <div style="background: rgba(15, 23, 42, 0.7); border-radius: 8px; padding: 7px; font-size: 11px; border: 1px solid rgba(255,255,255,0.08);">
                    <div style="display: flex; justify-content: space-between; color: #CBD5E1; margin-bottom: 3px;">
                      <span>Simulated Speed:</span>
                      <strong style="color: ${badgeColor}; font-weight: 700;">${spd}</strong>
                    </div>
                    <div style="display: flex; justify-content: space-between; color: #94A3B8; margin-bottom: 3px;">
                      <span>Free-Flow Baseline:</span>
                      <span style="color: #E2E8F0;">${freeSpd}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; color: #94A3B8;">
                      <span>Congestion Delay:</span>
                      <strong style="color: #FCD34D;">${delay}</strong>
                    </div>
                  </div>
                </div>
              `);

              layer.on({
                mouseover: (e: any) => {
                  e.target.setStyle({ weight: 7.0, opacity: 1.0 });
                },
                mouseout: (e: any) => {
                  tLayer.resetStyle(e.target);
                },
              });
            },
          } as any);

          if (mapInstanceRef.current && showTrafficLayer) {
            tLayer.addTo(mapInstanceRef.current);
            trafficVectorLayerRef.current = tLayer;

            // Render prominent Bottleneck Callout Badges on the map for Peak Monsoon simulation
            if (isPeak && trafficBottleneckMarkersLayerRef.current) {
              const bottlenecks = currentCity.toLowerCase() === 'kolkata' ? [
                { lat: 22.560, lng: 88.405, title: 'Chingrighata EM Bypass', speed: '8.2 km/h', delay: '4.5x' },
                { lat: 22.595, lng: 88.395, title: 'Ultadanga HUDCO Bottleneck', speed: '9.5 km/h', delay: '4.0x' },
                { lat: 22.542, lng: 88.397, title: 'Science City Connector', speed: '14.0 km/h', delay: '2.8x' },
              ] : [
                { lat: 19.068, lng: 72.875, title: 'LBS Marg / Kurla Bottleneck', speed: '6.2 km/h', delay: '5.5x' },
                { lat: 19.073, lng: 72.865, title: 'CST Road / SCLR Corridor', speed: '11.4 km/h', delay: '3.6x' },
                { lat: 19.061, lng: 72.863, title: 'BKC Financial Core Crawl', speed: '16.8 km/h', delay: '2.4x' },
              ];

              bottlenecks.forEach((b) => {
                const bIcon = L.divIcon({
                  className: 'custom-traffic-bottleneck-badge',
                  html: `
                    <div style="
                      display: inline-flex; align-items: center;
                      background: rgba(15, 23, 42, 0.94);
                      border: 1.5px solid rgba(239, 68, 68, 0.85);
                      box-shadow: 0 0 14px rgba(239, 68, 68, 0.6), inset 0 0 6px rgba(239, 68, 68, 0.2);
                      border-radius: 9999px;
                      padding: 2px 8px;
                      color: #F8FAFC;
                      font-size: 10px;
                      font-family: monospace;
                      font-weight: 700;
                      white-space: nowrap;
                      cursor: pointer;
                      backdrop-filter: blur(4px);
                    ">
                      <span style="display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #EF4444; margin-right: 5px; box-shadow: 0 0 6px #EF4444; animation: ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;"></span>
                      <span>${b.title}: <strong style="color: #FCA5A5;">${b.speed}</strong> <span style="color: #FCD34D;">(${b.delay})</span></span>
                    </div>
                  `,
                  iconSize: [160, 24],
                  iconAnchor: [80, 12],
                });

                L.marker([b.lat, b.lng], {
                  icon: bIcon,
                  pane: 'trafficVectorPane',
                }).addTo(trafficBottleneckMarkersLayerRef.current!);
              });
            }
          }
        }
      });
    } else {
      if (trafficVectorLayerRef.current && mapInstanceRef.current.hasLayer(trafficVectorLayerRef.current)) {
        mapInstanceRef.current.removeLayer(trafficVectorLayerRef.current);
        trafficVectorLayerRef.current = null;
      }
      if (trafficBottleneckMarkersLayerRef.current) {
        trafficBottleneckMarkersLayerRef.current.clearLayers();
      }
    }

    return () => {
      isCancelled = true;
    };
  }, [showTrafficLayer, trafficTileUrl, trafficMode, currentCity, mapReadyKey]);

  // ─────────────────────────────────────────────────────────────────────────
  // TURN-BY-TURN NAVIGATION HUD & VEHICLE TRACKER
  // ─────────────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!mapInstanceRef.current) return;

    if (!navLayerRef.current) {
      navLayerRef.current = L.layerGroup().addTo(mapInstanceRef.current);
    }
    navLayerRef.current.clearLayers();

    if (!isNavigating || !navLocation) {
      if (prevNavigatingRef.current && mapInstanceRef.current) {
        prevNavigatingRef.current = false;
        mapInstanceRef.current.setView([centerLat, centerLon], zoomLevel, { animate: true });
      }
      return;
    }

    const [vLng, vLat] = navLocation;
    const justStartedNav = isNavigating && !prevNavigatingRef.current;
    prevNavigatingRef.current = true;

    // A. Render Traversed Route Path (Subtle muted slate trace behind the car)
    if (navTraversedCoords && navTraversedCoords.length >= 2) {
      const latLngs = navTraversedCoords.map(([lng, lat]) => [lat, lng] as [number, number]);
      L.polyline(latLngs, {
        pane: 'navPane',
        color: '#475569',
        weight: 6,
        opacity: 0.6,
        lineCap: 'round',
        lineJoin: 'round',
      }).addTo(navLayerRef.current);
    }

    // B. Render Remaining Active Navigation Path (Google Maps Real-Time Traffic Color Coded)
    if (navRemainingCoords && navRemainingCoords.length >= 2) {
      const activeRoute = activeRouteIndex === 0 ? routeResult : alternatives[activeRouteIndex - 1] || routeResult;
      const trafficSegments = activeRoute?.traffic_segments;

      // Base high-contrast under-glow
      const fullLatLngs = navRemainingCoords.map(([lng, lat]) => [lat, lng] as [number, number]);
      L.polyline(fullLatLngs, {
        pane: 'navPane',
        color: '#0F172A',
        weight: 11,
        opacity: 0.85,
        lineCap: 'round',
        lineJoin: 'round',
      }).addTo(navLayerRef.current);

      if (trafficSegments && trafficSegments.length > 0) {
        // Render each traffic segment with Google Maps colors directly on top of navPane
        trafficSegments.forEach((tseg) => {
          const tColor =
            tseg.congestion_level === 'HEAVY'
              ? '#EF4444' // Red (Heavy Traffic)
              : tseg.congestion_level === 'MODERATE'
              ? '#F59E0B' // Amber / Orange (Moderate Congestion)
              : tseg.is_flood_affected
              ? '#06B6D4' // Cyan (Flood-avoidance detour corridor)
              : '#22C55E'; // Green (Free Flow)

          const pts = tseg.coordinates.map(([lng, lat]) => [lat, lng] as [number, number]);
          if (pts.length >= 2) {
            L.polyline(pts, {
              pane: 'navPane',
              color: tColor,
              weight: 6.5,
              opacity: 0.98,
              lineCap: 'round',
              lineJoin: 'round',
            }).addTo(navLayerRef.current!);
          }
        });
      } else {
        // Fallback if no segments: crisp green
        L.polyline(fullLatLngs, {
          pane: 'navPane',
          color: '#22C55E',
          weight: 6.5,
          opacity: 0.98,
          lineCap: 'round',
          lineJoin: 'round',
        }).addTo(navLayerRef.current);
      }
    }

    // C. Render 3D Google Maps Vehicle Avatar (Headlight Beam + Ground Drop Shadow + 3D Puck)
    const heading = Math.round(navBearing || 0);
    const vehicleIcon = L.divIcon({
      className: 'custom-nav-vehicle-marker-3d',
      html: `
        <div style="position: relative; width: 72px; height: 72px; display: flex; align-items: center; justify-content: center; transform: rotate(${heading}deg); transform-style: preserve-3d; transition: transform 0.25s cubic-bezier(0.2, 0.8, 0.2, 1); pointer-events: none;">
          
          <!-- Forward Headlight / Field-of-View Cone -->
          <div style="
            position: absolute;
            bottom: 36px;
            left: calc(50% - 28px);
            width: 56px;
            height: 64px;
            background: linear-gradient(to top, rgba(56, 189, 248, 0.65), rgba(56, 189, 248, 0.2) 55%, transparent 100%);
            clip-path: polygon(30% 100%, 70% 100%, 100% 0%, 0% 0%);
            pointer-events: none;
            filter: drop-shadow(0 0 10px rgba(56, 189, 248, 0.65));
          "></div>

          <!-- Asphalt Drop Shadow -->
          <div style="
            position: absolute;
            width: 34px;
            height: 34px;
            border-radius: 50%;
            background: rgba(0, 0, 0, 0.75);
            filter: blur(4px);
            transform: translateY(6px);
          "></div>

          <!-- Outer Radar Pulse Wave -->
          <div style="
            position: absolute;
            inset: 16px;
            border-radius: 50%;
            background: rgba(14, 165, 233, 0.45);
            animation: ping 1.8s cubic-bezier(0, 0, 0.2, 1) infinite;
          "></div>

          <!-- 3D Vehicle Puck (Google Maps Navigation Chevron Style) -->
          <div style="
            position: relative;
            width: 36px;
            height: 36px;
            border-radius: 50%;
            background: radial-gradient(circle at 35% 35%, #38BDF8, #0284C7 70%, #0369A1 100%);
            border: 3px solid #FFFFFF;
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.7), 0 0 18px rgba(56, 189, 248, 0.95);
            display: flex;
            align-items: center;
            justify-content: center;
          ">
            <!-- Forward Chevron Arrow -->
            <svg width="18" height="18" viewBox="0 0 24 24" fill="#FFFFFF" style="filter: drop-shadow(0 1px 2px rgba(0,0,0,0.6));">
              <path d="M12 2L21 19L19.5 20.5L12 17L4.5 20.5L3 19L12 2Z"/>
            </svg>
          </div>
        </div>
      `,
      iconSize: [72, 72],
      iconAnchor: [36, 36],
    });

    L.marker([vLat, vLng], { icon: vehicleIcon, pane: 'navPane' })
      .bindTooltip('🚗 Live Vehicle Position', {
        direction: 'top',
        className: 'custom-leaflet-tooltip font-bold text-cyan-300',
        offset: [0, -14],
      })
      .addTo(navLayerRef.current);

    // 🚀 AUTOMATIC CAMERA ZOOM:
    // When navigation is launched, fly and zoom directly into the pointer at street level (zoom 17)!
    if (justStartedNav && mapInstanceRef.current) {
      mapInstanceRef.current.flyTo([vLat, vLng], 17, {
        animate: true,
        duration: 1.2,
      });
    } else if (isFollowMode && mapInstanceRef.current) {
      const currentZoom = mapInstanceRef.current.getZoom();
      if (currentZoom < 16) {
        mapInstanceRef.current.setView([vLat, vLng], 17, { animate: true });
      } else {
        mapInstanceRef.current.panTo([vLat, vLng], { animate: true, duration: 0.4 });
      }
    }
  }, [isNavigating, navLocation, navBearing, navTraversedCoords, navRemainingCoords, isFollowMode]);

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
      return demGrid[cr] ? (demGrid[cr][cc] ?? minElev) : minElev;
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
          const depth = depth_grid[r] ? depth_grid[r][c] || 0 : 0;
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
      const floodBounds = (gridResponse as any).bounds || simulationBounds;

      if (floodRasterLayerRef.current) {
        floodRasterLayerRef.current.setUrl(dataUrl);
        floodRasterLayerRef.current.setBounds(L.latLngBounds(floodBounds as any));
        if (showFloodHeatmap && mapInstanceRef.current && !mapInstanceRef.current.hasLayer(floodRasterLayerRef.current)) {
          mapInstanceRef.current.addLayer(floodRasterLayerRef.current);
        }
      } else {
        const overlay = L.imageOverlay(dataUrl, floodBounds as L.LatLngBoundsExpression, {
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
  }, [currentTimeStep, currentCity, simulationKey, mapReadyKey]);

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

      const bounds = demRes.bounds || (isKolkata
        ? [[22.5050, 88.3850], [22.6020, 88.4380]]
        : simulationBounds);

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
  }, [currentCity, mapReadyKey]);

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

      const markerA = L.marker(originCoords, { icon: iconA });
      if (!isNavigating) {
        markerA.bindTooltip(`📍 A · ${originName || 'Origin'}`, {
          direction: 'top',
          permanent: false,
          className: 'custom-leaflet-tooltip font-bold text-emerald-300',
        });
      }
      markerA.addTo(waypointsLayerRef.current);
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

      const markerB = L.marker(destinationCoords, { icon: iconB });
      if (!isNavigating) {
        markerB.bindTooltip(`🎯 B · ${destinationName || 'Destination'}`, {
          direction: 'top',
          permanent: false,
          className: 'custom-leaflet-tooltip font-bold text-red-300',
        });
      }
      markerB.addTo(waypointsLayerRef.current);
    }
  }, [originCoords, destinationCoords, originName, destinationName, routeResult, isNavigating]);

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
  const handleCenterOnUser = () => {
    if (mapInstanceRef.current && userLocation) {
      mapInstanceRef.current.setView(userLocation, 16, { animate: true });
    }
  };

  // Invalidate Leaflet size when entering/exiting navigation or switching 3D/2D
  useEffect(() => {
    const timer = setTimeout(() => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.invalidateSize();
      }
    }, 150);
    return () => clearTimeout(timer);
  }, [isNavigating, navViewMode]);

  return (
    <div className="relative w-full h-full overflow-hidden" style={{ perspective: '1200px' }}>
      
      {/* Map DOM Container - Driver 3D Tilt in Navigation Mode */}
      <div
        ref={mapContainerRef}
        className="w-full h-full z-0"
        style={{
          transform:
            isNavigating && navViewMode === '3d'
              ? `rotateX(26deg) rotateZ(${-(navBearing || 0)}deg) scale(1.28) translateY(-5%)`
              : 'none',
          transformOrigin: '50% 75%',
          transition: isNavigating && navViewMode === '3d'
            ? 'transform 0.35s cubic-bezier(0.2, 0.8, 0.2, 1)'
            : 'transform 0.6s cubic-bezier(0.25, 1, 0.5, 1)',
          willChange: 'transform',
        }}
      />

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
                {passabilityStats && (
                  <>
                    <span className="text-slate-600">·</span>
                    <span className="inline-flex items-center space-x-1 font-mono text-[10px]">
                      <span className="text-emerald-400 font-bold">● {passabilityStats.open}</span>
                      {passabilityStats.restricted > 0 && (
                        <span className="text-amber-400 font-bold">● {passabilityStats.restricted}</span>
                      )}
                      {passabilityStats.closed > 0 && (
                        <span className="text-rose-400 font-bold">● {passabilityStats.closed}</span>
                      )}
                    </span>
                  </>
                )}
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

            {/* Traffic Flow Congestion Telemetry Scale */}
            {showTrafficLayer && (
              <>
                <div className="h-px bg-slate-800" />
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-[10px] text-slate-400">
                    <span className="uppercase tracking-wider font-bold text-amber-400 flex items-center space-x-1">
                      <span>Traffic Flow ({trafficMode === 'peak_monsoon' ? 'Monsoon Rush Sim' : 'TomTom Live'})</span>
                    </span>
                    <span className="text-amber-400/90 font-mono text-[9px]">Speed Telemetry</span>
                  </div>
                  <div className="grid grid-cols-3 gap-1 text-[9px]">
                    <div className="flex items-center space-x-1 p-1 rounded bg-emerald-950/40 border border-emerald-500/30 text-emerald-300">
                      <span className="h-2 w-2 rounded-full bg-emerald-400 shrink-0" />
                      <span>Free Flow</span>
                    </div>
                    <div className="flex items-center space-x-1 p-1 rounded bg-amber-950/40 border border-amber-500/30 text-amber-300">
                      <span className="h-2 w-2 rounded-full bg-amber-400 shrink-0" />
                      <span>Moderate</span>
                    </div>
                    <div className="flex items-center space-x-1 p-1 rounded bg-red-950/40 border border-red-500/30 text-red-300">
                      <span className="h-2 w-2 rounded-full bg-red-500 shrink-0 animate-pulse" />
                      <span>Heavy Gridlock</span>
                    </div>
                  </div>
                </div>
              </>
            )}

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

            {userLocation && (
              <>
                <div className="h-px bg-slate-800" />
                <div className="flex items-center justify-between">
                  <span className="flex items-center space-x-2">
                    <span className="h-3.5 w-3.5 rounded-full bg-blue-500 border-2 border-white shadow-[0_0_6px_#3B82F6]" />
                    <span>Your Live Location</span>
                  </span>
                  <span className="text-blue-400 font-bold animate-pulse">GPS LIVE</span>
                </div>
              </>
            )}

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
        {/* Live Location Button — only shown when GPS is active */}
        {userLocation && (
          <button
            onClick={handleCenterOnUser}
            title="Center on your live location"
            className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600/90 border border-blue-400/60 text-white hover:bg-blue-500 transition-all shadow-xl shadow-blue-900/50 backdrop-blur-md cursor-pointer active:scale-95 animate-pulse"
          >
            <span className="text-base leading-none">📍</span>
          </button>
        )}

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
