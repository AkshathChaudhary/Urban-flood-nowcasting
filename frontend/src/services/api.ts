export interface RoadSummary {
  total_nodes: number;
  total_directed_edges: number;
  total_unique_road_segments: number;
  total_length_km: number;
  highway_type_breakdown: Record<string, number>;
  vehicle_clearance_specs_m: Record<string, number>;
}

export interface GeoJSONFeature {
  type: 'Feature';
  geometry: {
    type: 'LineString' | 'Point' | 'Polygon';
    coordinates: any;
  };
  properties: Record<string, any>;
}

export interface GeoJSONFeatureCollection {
  type: 'FeatureCollection';
  features: GeoJSONFeature[];
  metadata?: Record<string, any>;
}

export interface HorizonSummary {
  horizon_minutes: number;
  max_depth_m: number;
  mean_depth_m: number;
  flooded_cells_15cm: number;
  flooded_cells_30cm: number;
  surface_water_volume_m3: number;
}

export interface FloodForecastOverview {
  scenario: string;
  horizons: number[];
  summaries: Record<string, HorizonSummary>;
  total_rain_volume_m3: number;
  total_infiltrated_volume_m3: number;
  total_absorbed_volume_m3: number;
  total_overflow_volume_m3: number;
}

export interface FloodGridResponse {
  scenario: string;
  horizon_minutes: number;
  rows: number;
  cols: number;
  cell_size_m: number;
  origin_lat: number;
  origin_lon: number;
  summary: HorizonSummary;
  depth_grid: number[][];
}

export interface DemGridResponse {
  city: string;
  rows: number;
  cols: number;
  cell_size_m: number;
  min_elevation_m: number;
  max_elevation_m: number;
  mean_elevation_m: number;
  bounds: number[][];
  grid: number[][];
}

export interface PointDepthResponse {
  lat: number;
  lon: number;
  row: number;
  col: number;
  elevation_m: number;
  depth_m_at_horizon: Record<string, number>;
  street_depth_m_at_horizon: Record<string, number>;
  porosity: number;
  hazard_level: 'CLEAR' | 'CAUTION' | 'IMPASSABLE';
}

export interface Landmark {
  id: string;
  name: string;
  category: string;
  lat: number;
  lon: number;
  elevation_m: number;
  description: string;
}

export interface DestinationsCatalog {
  city: string;
  pilot_basin: string;
  destinations: Landmark[];
  total_destinations: number;
}

export interface RouteRequest {
  src_lat: number;
  src_lon: number;
  dst_lat: number;
  dst_lon: number;
  vehicle_type: string;
  time_horizon_min: number;
  include_alternatives?: boolean;
  traffic_mode?: 'peak_monsoon' | 'live';
}

export interface RouteSegment {
  u: string;
  v: string;
  id: string;
  name: string;
  highway_type: string;
  length_m: number;
  maxspeed_kmh: number;
  flood_depth_m: number;
  status: string;
  current_speed_kmh?: number;
  free_flow_speed_kmh?: number;
  congestion_level?: 'FREE_FLOW' | 'MODERATE' | 'HEAVY' | 'BLOCKED';
  traffic_delay_s?: number;
}

export interface TrafficSegment {
  coordinates: [number, number][];
  congestion_level: 'FREE_FLOW' | 'MODERATE' | 'HEAVY' | 'BLOCKED';
  current_speed_kmh: number;
  is_flood_affected: boolean;
}

export interface RouteResult {
  route_found: boolean;
  vehicle_type: string;
  distance_m: number;
  travel_time_s: number;
  travel_time_min: number;
  free_flow_travel_time_min?: number;
  traffic_delay_min?: number;
  traffic_status?: string;
  traffic_mode?: string;
  max_flood_depth_m: number;
  avg_flood_depth_m: number;
  flood_risk: string;
  segment_count: number;
  roads_traversed: RouteSegment[];
  roads_avoided: RouteSegment[];
  traffic_segments?: TrafficSegment[];
  geojson: GeoJSONFeature;
}

export interface TrafficConfig {
  is_live_tomtom_active: boolean;
  traffic_tile_url: string | null;
  traffic_service_mode: string;
  supported_modes?: string[];
  default_mode?: string;
  supported_features: string[];
}

export const fetchTrafficConfig = async (): Promise<TrafficConfig | null> => {
  try {
    const res = await fetch('/api/route/traffic/config');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn('Could not fetch /api/route/traffic/config:', err);
    return null;
  }
};

export const fetchTrafficOverlay = async (
  city: string = 'mumbai',
  traffic_mode: string = 'peak_monsoon'
): Promise<GeoJSONFeatureCollection | null> => {
  try {
    const res = await fetch(
      `/api/route/traffic/overlay?city=${encodeURIComponent(city)}&traffic_mode=${encodeURIComponent(traffic_mode)}`
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn('Could not fetch /api/route/traffic/overlay:', err);
    return null;
  }
};

export interface RouteResponse {
  route_found: boolean;
  vehicle_type: string;
  time_horizon_min: number;
  primary_route: RouteResult;
  alternatives: RouteResult[];
  alternatives_count: number;
}

export const fetchRoadsSummary = async (city: string = 'mumbai'): Promise<RoadSummary | null> => {
  try {
    const res = await fetch(`/api/roads/summary?city=${encodeURIComponent(city)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn('Could not fetch /api/roads/summary:', err);
    return null;
  }
};

export const fetchRoadNetwork = async (city: string = 'mumbai', highwayType?: string): Promise<GeoJSONFeatureCollection | null> => {
  try {
    let url = `/api/roads/network?city=${encodeURIComponent(city)}`;
    if (highwayType) {
      url += `&highway_type=${encodeURIComponent(highwayType)}`;
    }
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn('Could not fetch /api/roads/network:', err);
    return null;
  }
};

export const fetchFloodHotspots = async (city: string = 'mumbai'): Promise<GeoJSONFeatureCollection | null> => {
  try {
    const res = await fetch(`/api/roads/hotspots?city=${encodeURIComponent(city)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn('Could not fetch /api/roads/hotspots:', err);
    return null;
  }
};

export const fetchFloodOverview = async (city: string = 'mumbai'): Promise<FloodForecastOverview | null> => {
  try {
    const res = await fetch(`/api/flood-forecast?city=${encodeURIComponent(city)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn(`Could not fetch /api/flood-forecast for ${city}:`, err);
    return null;
  }
};

const gridCache: Record<string, FloodGridResponse> = {};
const demCache: Record<string, DemGridResponse> = {};

export const clearFloodGridCache = () => {
  Object.keys(gridCache).forEach((k) => delete gridCache[k]);
};

export const fetchFloodGrid = async (minutes: number, city: string = 'mumbai'): Promise<FloodGridResponse | null> => {
  const cacheKey = `${city.toLowerCase()}_${minutes}`;
  if (gridCache[cacheKey]) {
    return gridCache[cacheKey];
  }
  try {
    const res = await fetch(`/api/flood-forecast/${minutes}?city=${encodeURIComponent(city)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data: FloodGridResponse = await res.json();
    gridCache[cacheKey] = data;
    return data;
  } catch (err) {
    console.warn(`Could not fetch /api/flood-forecast/${minutes} for ${city}:`, err);
    return null;
  }
};

export const fetchDemGrid = async (city: string = 'mumbai'): Promise<DemGridResponse | null> => {
  const cacheKey = city.toLowerCase();
  if (demCache[cacheKey]) {
    return demCache[cacheKey];
  }
  try {
    const res = await fetch(`/api/dem/grid?city=${encodeURIComponent(city)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data: DemGridResponse = await res.json();
    demCache[cacheKey] = data;
    return data;
  } catch (err) {
    console.warn(`Could not fetch /api/dem/grid for ${city}:`, err);
    return null;
  }
};

export const queryPointDepth = async (lat: number, lon: number, city: string = 'mumbai'): Promise<PointDepthResponse | null> => {
  try {
    const res = await fetch(`/api/flood-forecast/point/query?lat=${lat}&lon=${lon}&city=${encodeURIComponent(city)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn(`Could not query point depth at [${lat}, ${lon}] for ${city}:`, err);
    return null;
  }
};

export interface HistoricalPreset {
  id: string;
  date_str: string;
  start_hour: number;
  title: string;
  description: string;
  peak_mmh: number;
}

export interface ScenarioDetails {
  title: string;
  description: string;
  peak_intensity_mmh: number | null;
  mode: 'live' | 'historical' | 'demo';
}

export interface ScenariosResponse {
  scenarios: string[];
  details: Record<string, ScenarioDetails>;
  historical_presets: {
    mumbai: HistoricalPreset[];
    kolkata: HistoricalPreset[];
  };
}

export interface SimulateRequestPayload {
  city?: string;
  scenario: string;
  horizon_minutes?: number;
  dt_seconds?: number;
  lat?: number;
  lon?: number;
  date_str?: string;
  start_hour?: number;
}

export const fetchSupportedScenarios = async (): Promise<ScenariosResponse | null> => {
  try {
    const res = await fetch('/api/scenarios');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn('Could not fetch /api/scenarios:', err);
    return null;
  }
};

export const runSimulation = async (payload: SimulateRequestPayload): Promise<FloodForecastOverview> => {
  clearFloodGridCache();
  const res = await fetch('/api/simulate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errJson = await res.json().catch(() => ({}));
    throw new Error(errJson.detail || `HTTP ${res.status}`);
  }
  return await res.json();
};

export const fetchDestinationsCatalog = async (city: string = 'mumbai'): Promise<DestinationsCatalog | null> => {
  try {
    const res = await fetch(`/api/route/destinations?city=${encodeURIComponent(city)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn('Could not fetch /api/route/destinations:', err);
    return null;
  }
};

export const calculateFloodRoute = async (req: RouteRequest): Promise<RouteResponse | null> => {
  try {
    const res = await fetch('/api/route', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn('Could not calculate flood route:', err);
    return null;
  }
};

export interface DrainageSummary {
  total_nodes: number;
  total_edges: number;
  inlet_nodes: number;
  outfall_nodes: number;
  junction_nodes: number;
  current_water_stored_m3: number;
  total_discharged_m3: number;
  average_blockage_pct?: number;
}

export interface DrainageNodeProperties {
  id: string;
  type: 'inlet' | 'junction' | 'outfall';
  elevation_m: number;
  capacity_m3s: number;
  current_water_m3: number;
  stress_ratio: number;
  is_overflowing: boolean;
  coordinates: [number, number];
}

export interface DrainageEdgeProperties {
  id: string;
  from_node: string;
  to_node: string;
  diameter_m: number;
  length_m: number;
  slope: number;
  blockage_pct: number;
  effective_capacity_m3s: number;
}

export const fetchDrainageSummary = async (city: string = 'mumbai'): Promise<DrainageSummary | null> => {
  try {
    const res = await fetch(`/api/drainage/summary?city=${encodeURIComponent(city)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn(`Could not fetch /api/drainage/summary for ${city}:`, err);
    return null;
  }
};

export const fetchDrainageNodes = async (city: string = 'mumbai', nodeType?: string): Promise<GeoJSONFeatureCollection | null> => {
  try {
    let url = `/api/drainage/nodes?city=${encodeURIComponent(city)}`;
    if (nodeType) url += `&node_type=${encodeURIComponent(nodeType)}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn(`Could not fetch /api/drainage/nodes for ${city}:`, err);
    return null;
  }
};

export const fetchDrainageEdges = async (city: string = 'mumbai'): Promise<GeoJSONFeatureCollection | null> => {
  try {
    const res = await fetch(`/api/drainage/edges?city=${encodeURIComponent(city)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn(`Could not fetch /api/drainage/edges for ${city}:`, err);
    return null;
  }
};

export const updatePipeBlockage = async (blockagePct: number, edgeId?: string, city: string = 'mumbai'): Promise<any> => {
  try {
    const res = await fetch(`/api/drainage/blockage?city=${encodeURIComponent(city)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ blockage_pct: blockagePct, edge_id: edgeId }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn('Could not update pipe blockage:', err);
    return null;
  }
};

export const resetDrainageNetwork = async (city: string = 'mumbai'): Promise<boolean> => {
  try {
    const res = await fetch(`/api/drainage/reset?city=${encodeURIComponent(city)}`, { method: 'POST' });
    return res.ok;
  } catch (err) {
    console.warn('Could not reset drainage network:', err);
    return false;
  }
};

export const createFloodWebSocket = (
  onMessage: (data: any) => void,
  onStatusChange?: (status: 'connected' | 'connecting' | 'disconnected') => void,
  city: string = 'mumbai'
): (() => void) => {
  let ws: WebSocket | null = null;
  let isClosedManually = false;
  let reconnectTimeout: any = null;

  const connect = () => {
    if (onStatusChange) onStatusChange('connecting');
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.port === '5173' ? '127.0.0.1:8000' : window.location.host;
    const wsUrl = `${protocol}//${host}/ws/flood-updates?city=${encodeURIComponent((city || 'mumbai').toLowerCase())}`;

    try {
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        if (onStatusChange) onStatusChange('connected');
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          onMessage(payload);
        } catch (e) {
          console.warn('Malformed WS message:', e);
        }
      };

      ws.onerror = (err) => {
        console.warn('WebSocket error:', err);
      };

      ws.onclose = () => {
        if (onStatusChange) onStatusChange('disconnected');
        if (!isClosedManually) {
          reconnectTimeout = setTimeout(connect, 4000);
        }
      };
    } catch (err) {
      console.warn('WebSocket connection error:', err);
      if (!isClosedManually) {
        reconnectTimeout = setTimeout(connect, 4000);
      }
    }
  };

  connect();

  return () => {
    isClosedManually = true;
    if (reconnectTimeout) clearTimeout(reconnectTimeout);
    if (ws) ws.close();
  };
};

