import React, { useState, useEffect, useRef, useMemo } from 'react';
import { 
  Play, 
  Pause, 
  RotateCcw, 
  Layers, 
  Eye, 
  EyeOff, 
  Mountain,
  CloudRain,
  Radio,
  Calendar,
  Zap,
  Sliders, 
  X, 
  CheckCircle2, 
  Loader2, 
  ChevronRight,
  ChevronDown,
  ChevronLeft,
  Clock,
  Waves,
  Navigation,
  GitFork
} from 'lucide-react';
import { GisMap } from './GisMap';
import { RoutePanel, type TransportMode } from './RoutePanel';
import { DrainagePanel } from './DrainagePanel';
import { NavigationHud } from './NavigationHud';
import {
  generateTurnByTurnSteps,
  calculateBearing,
  calculateDistanceMeters,
  getMinDistanceToRouteMeters,
  navigationVoice,
  type NavigationStep,
} from '../services/navigation';
import { 
  fetchRoadsSummary, 
  fetchFloodOverview, 
  fetchDestinationsCatalog, 
  calculateFloodRoute,
  fetchDrainageSummary,
  updatePipeBlockage,
  resetDrainageNetwork,
  createFloodWebSocket,
  runSimulation,
  fetchSupportedScenarios,
  clearFloodGridCache,
  fetchTrafficConfig,
  computeCorridorRoute,
} from '../services/api';
import type { 
  RoadSummary, 
  FloodForecastOverview, 
  HorizonSummary, 
  Landmark, 
  RouteResult, 
  ScenariosResponse,
  DrainageSummary,
  TrafficConfig,
} from '../services/api';

interface CommandCenterViewProps {
  currentCity: string;
  onCityChange?: (city: string) => void;
  initialScenario?: string;
}

export const CommandCenterView: React.FC<CommandCenterViewProps> = ({ currentCity, onCityChange, initialScenario }) => {
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [currentTimeStep, setCurrentTimeStep] = useState<number>(0); // default to T+0m baseline dry state
  const [hasCalculatedRoute, setHasCalculatedRoute] = useState<boolean>(false);
  const [showFloodHeatmap, setShowFloodHeatmap] = useState<boolean>(true);
  const [showDrainagePipes, setShowDrainagePipes] = useState<boolean>(false); // default OFF to avoid cluttered green lines
  const [showRoadGrid, setShowRoadGrid] = useState<boolean>(true);
  const [showHotspots, setShowHotspots] = useState<boolean>(true);
  const [showDemTerrain, setShowDemTerrain] = useState<boolean>(false);
  const [showTrafficLayer, setShowTrafficLayer] = useState<boolean>(true);
  const [trafficConfig, setTrafficConfig] = useState<TrafficConfig | null>(null);
  const [trafficMode, setTrafficMode] = useState<'peak_monsoon' | 'live'>('peak_monsoon');
  const [selectedVehicle, setSelectedVehicle] = useState<TransportMode>('ambulance');
  
  // Navigation & Drawer State
  const [navViewMode, setNavViewMode] = useState<'3d' | '2d'>('3d');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState<boolean>(false);
  const [isAdvancedConfigOpen, setIsAdvancedConfigOpen] = useState<boolean>(false);
  const [isTelemetryOpen, setIsTelemetryOpen] = useState<boolean>(false);
  const [showTimelineBar, setShowTimelineBar] = useState<boolean>(true);

  // Simulation Intelligence State
  const [isSimModalOpen, setIsSimModalOpen] = useState<boolean>(false);
  const [simMode, setSimMode] = useState<'live' | 'historical' | 'demo'>('historical');
  const [selectedScenario, setSelectedScenario] = useState<string>('cloudburst');
  const [selectedHistoricalPreset, setSelectedHistoricalPreset] = useState<string>('');
  const [customDate, setCustomDate] = useState<string>('');
  const [customStartHour, setCustomStartHour] = useState<number>(11);
  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const [simStatusMsg, setSimStatusMsg] = useState<string>('');
  const [scenariosMeta, setScenariosMeta] = useState<ScenariosResponse | null>(null);

  const [roadSummary, setRoadSummary] = useState<RoadSummary | null>(null);
  const [floodOverview, setFloodOverview] = useState<FloodForecastOverview | null>(null);
  const [drainageSummary, setDrainageSummary] = useState<DrainageSummary | null>(null);
  const [isDrainagePanelOpen, setIsDrainagePanelOpen] = useState<boolean>(false);
  const [isUpdatingBlockage, setIsUpdatingBlockage] = useState<boolean>(false);
  const [surchargingCount, setSurchargingCount] = useState<number>(0);
  const [wsStatus, setWsStatus] = useState<'connected' | 'connecting' | 'disconnected'>('connecting');
  const [drainageRefreshKey, setDrainageRefreshKey] = useState<number>(0);
  const [simulationKey, setSimulationKey] = useState<number>(0);

  const [landmarks, setLandmarks] = useState<Landmark[]>([]);
  const [selectedOriginId, setSelectedOriginId] = useState<string>('bkc-hub');
  const [selectedDestinationId, setSelectedDestinationId] = useState<string>('kurla-station');
  const [isRoutePanelOpen, setIsRoutePanelOpen] = useState<boolean>(false);
  const [isCalculatingRoute, setIsCalculatingRoute] = useState<boolean>(false);
  const [routeResult, setRouteResult] = useState<RouteResult | null>(null);
  const [routeAlternatives, setRouteAlternatives] = useState<RouteResult[]>([]);
  const [activeRouteIndex, setActiveRouteIndex] = useState<number>(0);

  // ── Turn-by-Turn Navigation HUD & Simulator State ──────────────────────────
  const [isNavigating, setIsNavigating] = useState<boolean>(false);
  const [navSteps, setNavSteps] = useState<NavigationStep[]>([]);
  const [navActiveStepIndex, setNavActiveStepIndex] = useState<number>(0);
  const [navLocation, setNavLocation] = useState<[number, number] | null>(null);
  const [navBearing, setNavBearing] = useState<number>(0);
  const [navTraversedCoords, setNavTraversedCoords] = useState<[number, number][]>([]);
  const [navRemainingCoords, setNavRemainingCoords] = useState<[number, number][]>([]);
  const [isFollowMode, setIsFollowMode] = useState<boolean>(true);
  const [isLiveGps, setIsLiveGps] = useState<boolean>(false);
  const [hasGpsLock, setHasGpsLock] = useState<boolean>(false);
  const [isVoiceMuted, setIsVoiceMuted] = useState<boolean>(false);
  const [isSimPlaying, setIsSimPlaying] = useState<boolean>(false);
  const [simProgressPct, setSimProgressPct] = useState<number>(0);
  const [simSpeedMultiplier, setSimSpeedMultiplier] = useState<number>(1);
  const [distanceToNextTurn, setDistanceToNextTurn] = useState<number>(0);
  const [totalRemainingDistance, setTotalRemainingDistance] = useState<number>(0);
  const [totalRemainingDuration, setTotalRemainingDuration] = useState<number>(0);

  const lastAnnouncedStepRef = useRef<number>(-1);
  const navWatchIdRef = useRef<number | null>(null);

  // ── Live GPS Location ─────────────────────────────────────────────────────
  const [userLocation, setUserLocation] = useState<[number, number] | null>(null);
  const [geoError, setGeoError] = useState<string | null>(null);
  const geoWatchRef = useRef<number | null>(null);
  // ─────────────────────────────────────────────────────────────────────────
  
  const playIntervalRef = useRef<any>(null);


  // ── Live GPS Geolocation ─────────────────────────────────────────────────
  useEffect(() => {
    if (!navigator.geolocation) {
      setGeoError('Geolocation is not supported by this browser.');
      return;
    }
    geoWatchRef.current = navigator.geolocation.watchPosition(
      (pos) => {
        setUserLocation([pos.coords.latitude, pos.coords.longitude]);
        setGeoError(null);
      },
      (err) => {
        console.warn('Geolocation error:', err.message);
        setGeoError(err.message);
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 5000 }
    );
    return () => {
      if (geoWatchRef.current !== null) {
        navigator.geolocation.clearWatch(geoWatchRef.current);
      }
    };
  }, []);
  // ─────────────────────────────────────────────────────────────────────────


  const forecastHorizons = [0, 30, 60, 90, 120, 180];

  // Fetch scenarios metadata on initial mount
  useEffect(() => {
    fetchSupportedScenarios().then(data => {
      if (data) {
        setScenariosMeta(data);
      }
    });
    fetchTrafficConfig().then(cfg => {
      if (cfg) setTrafficConfig(cfg);
    });
  }, []);

  // Handle initial scenario trigger from landing / bento grid
  useEffect(() => {
    if (initialScenario) {
      setHasCalculatedRoute(true);
      if (initialScenario === 'mumbai_severe') {
        handleRunSimulation('demo', 'cloudburst');
      } else if (initialScenario === 'mumbai_river_spill') {
        handleRunSimulation('demo', 'extreme');
      } else if (initialScenario === 'kolkata_drainage_choke') {
        handleRunSimulation('demo', 'extreme_blocked');
      } else {
        handleRunSimulation('demo', initialScenario);
      }
    }
  }, [initialScenario]);

  // Update default historical dates and presets when city changes
  useEffect(() => {
    const isKolkata = currentCity.toLowerCase() === 'kolkata';
    if (isKolkata) {
      setSelectedHistoricalPreset('kolkata_2021_cloudburst');
      setCustomDate('2021-09-20');
      setCustomStartHour(1);
    } else {
      setSelectedHistoricalPreset('mumbai_2023_deluge');
      setCustomDate('2023-07-26');
      setCustomStartHour(11);
    }
  }, [currentCity]);

  const handleRunSimulation = async (modeOverride?: 'live' | 'historical' | 'demo', scenarioOverride?: string) => {
    const activeMode = modeOverride || simMode;
    const isKolkata = currentCity.toLowerCase() === 'kolkata';
    setIsSimulating(true);
    setSimStatusMsg(
      `Coupling 2D shallow-water model with ${isKolkata ? 'Kolkata (35m DEM, 10,305 conduits)' : 'Mumbai (10m DEM, Mithi basin)'}...`
    );

    try {
      let scenario = scenarioOverride || selectedScenario;
      let date_str: string | undefined = undefined;
      let start_hour: number | undefined = undefined;
      let preset: string | undefined = undefined;

      const allPresets = [
        'kolkata_2021_cloudburst',
        'kolkata_2020_amphan',
        'kolkata_2021_depression',
        'mumbai_2023_deluge',
        'mumbai_2005_cloudburst',
        'mumbai_2019_monsoon',
      ];
      if (allPresets.includes(scenario)) {
        preset = scenario;
      }

      if (activeMode === 'live') {
        scenario = 'live';
      } else if (activeMode === 'historical') {
        scenario = 'historical';
        const presets = scenariosMeta?.historical_presets?.[isKolkata ? 'kolkata' : 'mumbai'] || [];
        const foundPreset = presets.find(p => p.id === (preset || selectedHistoricalPreset));
        if (foundPreset) {
          preset = foundPreset.id;
          date_str = foundPreset.date_str;
          start_hour = foundPreset.start_hour;
        } else if (preset) {
          if (preset === 'kolkata_2021_cloudburst') { date_str = '2021-09-20'; start_hour = 1; }
          else if (preset === 'kolkata_2020_amphan') { date_str = '2020-05-20'; start_hour = 8; }
          else if (preset === 'kolkata_2021_depression') { date_str = '2021-06-17'; start_hour = 4; }
          else if (preset === 'mumbai_2023_deluge') { date_str = '2023-07-26'; start_hour = 11; }
          else if (preset === 'mumbai_2005_cloudburst') { date_str = '2005-07-26'; start_hour = 9; }
          else if (preset === 'mumbai_2019_monsoon') { date_str = '2019-07-02'; start_hour = 3; }
        } else {
          date_str = customDate || (isKolkata ? '2021-09-20' : '2023-07-26');
          start_hour = customStartHour;
          preset = selectedHistoricalPreset || undefined;
        }
      }

      const res = await runSimulation({
        city: currentCity,
        scenario,
        preset,
        horizon_minutes: 180,
        date_str,
        start_hour,
      });

      if (res) {
        setFloodOverview(res);
        clearFloodGridCache();
        setSimulationKey((prev) => prev + 1);
        const dSummary = await fetchDrainageSummary(currentCity);
        if (dSummary) setDrainageSummary(dSummary);
        setDrainageRefreshKey((prev) => prev + 1);
        // Automatically advance timeline from 0m to 60m so flood inundation is immediately visible
        setCurrentTimeStep((prev) => (prev === 0 ? 60 : prev));
      }
      setIsSimModalOpen(false);
    } catch (err: any) {
      console.error('Simulation execution failed:', err);
      alert(`Simulation failed: ${err.message || err}`);
    } finally {
      setIsSimulating(false);
      setSimStatusMsg('');
    }
  };

  // Fetch initial summary metrics, drainage summary, and landmark catalog for the active city
  useEffect(() => {
    // Clear routes from previous city
    setRouteResult(null);
    setRouteAlternatives([]);
    setActiveRouteIndex(0);
    setHasCalculatedRoute(false);

    fetchRoadsSummary(currentCity).then(data => {
      if (data) setRoadSummary(data);
    });

    fetchFloodOverview(currentCity).then(data => {
      if (data) setFloodOverview(data);
    });

    fetchDrainageSummary(currentCity).then(data => {
      if (data) setDrainageSummary(data);
    });

    fetchDestinationsCatalog(currentCity).then(catalog => {
      if (catalog && catalog.destinations && catalog.destinations.length > 0) {
        setLandmarks(catalog.destinations);
        const isKolkata = currentCity.toLowerCase() === 'kolkata';
        if (isKolkata) {
          const hasRuby = catalog.destinations.some(d => d.id === 'ruby-hospital');
          const hasKestopur = catalog.destinations.some(d => d.id === 'kestopur-canal');
          setSelectedOriginId(hasRuby ? 'ruby-hospital' : catalog.destinations[0].id);
          setSelectedDestinationId(hasKestopur ? 'kestopur-canal' : catalog.destinations[Math.min(1, catalog.destinations.length - 1)].id);
        } else {
          const hasBkc = catalog.destinations.some(d => d.id === 'bkc-hub');
          const hasKurla = catalog.destinations.some(d => d.id === 'kurla-station');
          const origId = hasBkc ? 'bkc-hub' : catalog.destinations[0].id;
          const destId = hasKurla ? 'kurla-station' : catalog.destinations[Math.min(1, catalog.destinations.length - 1)].id;
          setSelectedOriginId(origId);
          setSelectedDestinationId(destId);
        }
      }
    });
  }, [currentCity]);

  // Live WebSocket Streaming from /ws/flood-updates
  useEffect(() => {
    const unsubscribe = createFloodWebSocket(
      (data) => {
        if (data.type === 'horizon_update') {
          if (data.drainage_telemetry) {
            setDrainageSummary(data.drainage_telemetry);
          }
        }
      },
      (status) => setWsStatus(status),
      currentCity
    );
    return () => unsubscribe();
  }, [currentCity]);

  // Keyboard Navigation Shortcuts (Space = Play/Pause, Arrows = Scrub, Esc = Minimize HUD)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return;
      if (e.code === 'Space') {
        e.preventDefault();
        setIsPlaying((prev) => !prev);
      } else if (e.code === 'ArrowRight') {
        e.preventDefault();
        setIsPlaying(false);
        setCurrentTimeStep((prev) => {
          const idx = forecastHorizons.indexOf(prev);
          return forecastHorizons[(idx + 1) % forecastHorizons.length];
        });
      } else if (e.code === 'ArrowLeft') {
        e.preventDefault();
        setIsPlaying(false);
        setCurrentTimeStep((prev) => {
          const idx = forecastHorizons.indexOf(prev);
          return forecastHorizons[(idx - 1 + forecastHorizons.length) % forecastHorizons.length];
        });
      } else if (e.code === 'Escape') {
        setIsRoutePanelOpen(false);
        setIsDrainagePanelOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleUpdateBlockage = async (pct: number) => {
    setIsUpdatingBlockage(true);
    try {
      await updatePipeBlockage(pct, undefined, currentCity);
      const data = await fetchDrainageSummary(currentCity);
      if (data) setDrainageSummary(data);
      setShowDrainagePipes(true);
      setDrainageRefreshKey((k) => k + 1);
      // Automatically re-run simulation so flood depths reflect reduced drainage conveyance
      await handleRunSimulation();
      const postSimData = await fetchDrainageSummary(currentCity);
      if (postSimData) setDrainageSummary(postSimData);
      setDrainageRefreshKey((k) => k + 1);
    } finally {
      setIsUpdatingBlockage(false);
    }
  };

  const handleResetDrainage = async () => {
    await resetDrainageNetwork(currentCity);
    const data = await fetchDrainageSummary(currentCity);
    if (data) setDrainageSummary(data);
    setDrainageRefreshKey((k) => k + 1);
    await handleRunSimulation();
    const postSimData = await fetchDrainageSummary(currentCity);
    if (postSimData) setDrainageSummary(postSimData);
    setDrainageRefreshKey((k) => k + 1);
  };

  const handleMapClick = (_lat: number, _lng: number) => {
    // Interactive map click for depth inspection
  };

  // Route calculation routine
  const triggerRouteCalculation = async (
    origId: string = selectedOriginId,
    destId: string = selectedDestinationId,
    veh: TransportMode = selectedVehicle,
    horizon: number = currentTimeStep,
    trafficM: 'peak_monsoon' | 'live' = trafficMode,
  ) => {
    // Standard landmark & live GPS mode
    const allLandmarks: Landmark[] = userLocation
      ? [
          {
            id: 'my-location',
            name: '📍 My Current Location (GPS)',
            category: 'live',
            lat: userLocation[0],
            lon: userLocation[1],
            elevation_m: 0,
            description: 'Your live GPS position',
          },
          ...landmarks,
        ]
      : landmarks;

    if (allLandmarks.length === 0) return;
    const orig = allLandmarks.find(l => l.id === origId);
    const dest = allLandmarks.find(l => l.id === destId);
    if (!orig || !dest) return;

    setIsCalculatingRoute(true);
    try {
      const res = await calculateFloodRoute({
        src_lat: orig.lat,
        src_lon: orig.lon,
        dst_lat: dest.lat,
        dst_lon: dest.lon,
        vehicle_type: veh,
        time_horizon_min: horizon,
        include_alternatives: true,
        traffic_mode: trafficM,
      });
      if (res) {
        if (res.primary_route) {
          setRouteResult(res.primary_route);
        }
        setRouteAlternatives(res.alternatives || []);
        setActiveRouteIndex(0);
      }
    } finally {
      setIsCalculatingRoute(false);
    }
  };

  // Trigger route recalculation when waypoints, vehicle, or forecast horizon change
  useEffect(() => {
    if (hasCalculatedRoute && landmarks.length > 0 && selectedOriginId && selectedDestinationId) {
      triggerRouteCalculation(selectedOriginId, selectedDestinationId, selectedVehicle, currentTimeStep);
    }
  }, [
    hasCalculatedRoute,
    landmarks,
    userLocation,
    selectedOriginId,
    selectedDestinationId,
    selectedVehicle,
    currentTimeStep,
    selectedScenario,
  ]);

  // Handle Play/Pause Auto-Advance Scrubber Loop
  useEffect(() => {
    if (isPlaying) {
      playIntervalRef.current = setInterval(() => {
        setCurrentTimeStep((prev) => {
          const currentIndex = forecastHorizons.indexOf(prev);
          const nextIndex = (currentIndex + 1) % forecastHorizons.length;
          return forecastHorizons[nextIndex];
        });
      }, 2000);
    } else {
      if (playIntervalRef.current) {
        clearInterval(playIntervalRef.current);
      }
    }
    return () => {
      if (playIntervalRef.current) clearInterval(playIntervalRef.current);
    };
  }, [isPlaying]);

  // Active Navigation Route Coordinates & Calculations
  const activeNavRoute: RouteResult | null =
    activeRouteIndex === 0 ? routeResult : routeAlternatives[activeRouteIndex - 1] || routeResult;

  const activeRouteCoords: [number, number][] =
    (activeNavRoute?.geojson?.geometry?.coordinates as [number, number][]) || [];

  const updateNavTelemetryFromProgress = (
    pct: number,
    coords: [number, number][],
    steps: NavigationStep[],
    speedMultiplier: number = simSpeedMultiplier
  ) => {
    if (coords.length < 2) return;

    const segDistances: number[] = [];
    let totalD = 0;
    for (let i = 0; i < coords.length - 1; i++) {
      const d = calculateDistanceMeters(coords[i], coords[i + 1]);
      segDistances.push(d);
      totalD += d;
    }

    const targetDistance = (pct / 100) * totalD;
    let accumulated = 0;
    let currentSegmentIndex = 0;
    let segFraction = 0;

    for (let i = 0; i < segDistances.length; i++) {
      if (accumulated + segDistances[i] >= targetDistance) {
        currentSegmentIndex = i;
        segFraction = segDistances[i] > 0 ? (targetDistance - accumulated) / segDistances[i] : 0;
        break;
      }
      accumulated += segDistances[i];
      if (i === segDistances.length - 1) {
        currentSegmentIndex = i;
        segFraction = 1;
      }
    }

    const pA = coords[currentSegmentIndex];
    const pB = coords[Math.min(currentSegmentIndex + 1, coords.length - 1)];

    const currLng = pA[0] + segFraction * (pB[0] - pA[0]);
    const currLat = pA[1] + segFraction * (pB[1] - pA[1]);
    const currPos: [number, number] = [currLng, currLat];
    const heading = calculateBearing(pA, pB);

    setNavLocation(currPos);
    setNavBearing(heading);

    const traversed: [number, number][] = coords.slice(0, currentSegmentIndex + 1);
    traversed.push(currPos);
    const remaining: [number, number][] = [currPos, ...coords.slice(currentSegmentIndex + 1)];

    setNavTraversedCoords(traversed);
    setNavRemainingCoords(remaining);

    const remDist = Math.max(0, totalD - targetDistance);
    setTotalRemainingDistance(remDist);
    const totalDuration = activeNavRoute?.travel_time_s || (totalD / 8.33);
    setTotalRemainingDuration(Math.max(0, (remDist / totalD) * totalDuration));

    if (steps.length > 0) {
      let activeIdx = 0;
      for (let s = 0; s < steps.length; s++) {
        const stepDistFromStart = calculateDistanceMeters(coords[0], steps[s].startCoord);
        if (targetDistance >= stepDistFromStart) {
          activeIdx = s;
        } else {
          break;
        }
      }
      setNavActiveStepIndex(activeIdx);

      const nextTurnCoord = steps[activeIdx + 1]?.startCoord || steps[steps.length - 1].startCoord;
      const distToTurn = calculateDistanceMeters(currPos, nextTurnCoord);
      setDistanceToNextTurn(distToTurn);

      if (activeIdx !== lastAnnouncedStepRef.current && activeIdx < steps.length) {
        lastAnnouncedStepRef.current = activeIdx;
        const prompt = steps[activeIdx].instruction;
        if (prompt) {
          navigationVoice.speak(prompt, false, speedMultiplier);
        }
      }
    }
  };

  const handleStartNavigation = () => {
    if (!activeNavRoute || activeRouteCoords.length < 2) return;

    const steps = generateTurnByTurnSteps(activeNavRoute);
    setNavSteps(steps);
    setNavActiveStepIndex(0);
    setNavLocation(activeRouteCoords[0]);
    setNavBearing(steps[0]?.bearing || 0);
    setNavTraversedCoords([activeRouteCoords[0]]);
    setNavRemainingCoords(activeRouteCoords);
    setSimProgressPct(0);
    setTotalRemainingDistance(activeNavRoute.distance_m);
    setTotalRemainingDuration(activeNavRoute.travel_time_s);
    setIsNavigating(true);
    setIsSimPlaying(true);
    setIsRoutePanelOpen(false);
    setIsDrainagePanelOpen(false);
    setIsFollowMode(true);
    lastAnnouncedStepRef.current = -1;

    const vehicleName = selectedVehicle.toUpperCase();
    navigationVoice.speak(
      `Starting flood-resilient navigation for ${vehicleName}. Clearance calibrated. ${steps[0]?.instruction || 'Proceed on route.'}`,
      true
    );
  };

  const handleExitNavigation = () => {
    setIsNavigating(false);
    setIsSimPlaying(false);
    navigationVoice.stop();
    setIsRoutePanelOpen(true);
    if (navWatchIdRef.current !== null && 'geolocation' in navigator) {
      navigator.geolocation.clearWatch(navWatchIdRef.current);
      navWatchIdRef.current = null;
    }
  };

  const handleToggleVoice = () => {
    const nextMuted = !isVoiceMuted;
    setIsVoiceMuted(nextMuted);
    navigationVoice.setMuted(nextMuted);
  };

  const handleSeekProgress = (pct: number) => {
    setSimProgressPct(pct);
    updateNavTelemetryFromProgress(pct, activeRouteCoords, navSteps);
  };

  const handleToggleLiveGps = () => {
    const nextGps = !isLiveGps;
    setIsLiveGps(nextGps);
    if (nextGps) {
      setIsSimPlaying(false);
      if ('geolocation' in navigator) {
        navigationVoice.speak('Switching to live device GPS tracking.');
        const wid = navigator.geolocation.watchPosition(
          (pos) => {
            setHasGpsLock(true);
            const userPt: [number, number] = [pos.coords.longitude, pos.coords.latitude];
            setNavLocation(userPt);
            if (pos.coords.heading !== null && !isNaN(pos.coords.heading)) {
              setNavBearing(pos.coords.heading);
            }
            if (activeRouteCoords.length >= 2) {
              const { minDistance_m } = getMinDistanceToRouteMeters(userPt, activeRouteCoords);
              if (minDistance_m > 40) {
                navigationVoice.speak('Off route detected. Recalculating route around submerged roads.', true);
              }
            }
          },
          (err) => {
            console.warn('GPS watch error:', err);
            setHasGpsLock(false);
          },
          { enableHighAccuracy: true, maximumAge: 1000 }
        );
        navWatchIdRef.current = wid;
      } else {
        alert('Geolocation is not supported by your browser.');
        setIsLiveGps(false);
      }
    } else {
      if (navWatchIdRef.current !== null && 'geolocation' in navigator) {
        navigator.geolocation.clearWatch(navWatchIdRef.current);
        navWatchIdRef.current = null;
      }
      setIsSimPlaying(true);
      navigationVoice.speak('Resuming route navigation playback.');
    }
  };

  const handleTriggerOffRouteSim = () => {
    if (!navLocation) return;
    const [lng, lat] = navLocation;
    const deviated: [number, number] = [lng + 0.003, lat + 0.003];
    setNavLocation(deviated);
    navigationVoice.speak('Off-route deviation simulated! Dynamic A* recalculation initiated.', true);
  };

  // Turn-by-Turn Simulated Vehicle Movement Clock
  useEffect(() => {
    if (!isNavigating || !isSimPlaying || isLiveGps || activeRouteCoords.length < 2) return;

    const intervalMs = 100;
    const totalD = activeNavRoute?.distance_m || 1000;
    const speedMs = 12 * simSpeedMultiplier; // ~43 km/h base speed
    const distPerTick = speedMs * (intervalMs / 1000);
    const pctIncrement = (distPerTick / totalD) * 100;

    const simTimer = setInterval(() => {
      setSimProgressPct((prevPct) => {
        const nextPct = prevPct + pctIncrement;
        if (nextPct >= 100) {
          clearInterval(simTimer);
          setIsSimPlaying(false);
          updateNavTelemetryFromProgress(100, activeRouteCoords, navSteps, simSpeedMultiplier);
          navigationVoice.speak('You have safely arrived at your destination.', true, simSpeedMultiplier);
          return 100;
        }
        updateNavTelemetryFromProgress(nextPct, activeRouteCoords, navSteps, simSpeedMultiplier);
        return nextPct;
      });
    }, intervalMs);

    return () => clearInterval(simTimer);
  }, [isNavigating, isSimPlaying, isLiveGps, simSpeedMultiplier, activeRouteCoords, navSteps, activeNavRoute]);

  const handleUseLiveLocationAsOrigin = () => {
    if (!userLocation) {
      alert('Live GPS location not acquired yet. Please allow browser location access.');
      return;
    }
    setSelectedOriginId('my-location');
    triggerRouteCalculation('my-location', selectedDestinationId, selectedVehicle, currentTimeStep, trafficMode);
  };

  const handleTestCorridorPipeline = async (src?: string, dst?: string) => {
    try {
      const sourcePoint = src || selectedOriginId || 'bkc-hub';
      const destPoint = dst || selectedDestinationId || 'kurla-station';
      const resp = await computeCorridorRoute({
        src: sourcePoint,
        dst: destPoint,
        vehicle_type: selectedVehicle,
        horizon_minutes: currentTimeStep,
      });
      if (resp && resp.status === 'ok') {
        alert(`Corridor Pipeline Computed from ${sourcePoint} to ${destPoint}:\nTotal Distance: ${resp.distance_m ? (resp.distance_m / 1000).toFixed(2) + ' km' : 'N/A'}\nFlood Status: ${resp.flooded ? 'Submerged' : 'Clear'}`);
      } else {
        alert('Corridor calculation response: ' + (resp?.message || JSON.stringify(resp)));
      }
    } catch (e: any) {
      console.error('Corridor error:', e);
      alert('Error calculating corridor route: ' + (e.message || 'Check network'));
    }
  };

  // Current Horizon Summary
  const currentSummary: HorizonSummary | undefined = 
    floodOverview?.summaries ? floodOverview.summaries[String(currentTimeStep)] : undefined;

  // Selected Origin and Destination Waypoint Lookups
  // Inject "My Location" as a virtual landmark when GPS is active
  const landmarksWithMyLocation: Landmark[] = userLocation
    ? [
        {
          id: 'my-location',
          name: '📍 My Current Location (GPS)',
          category: 'live',
          lat: userLocation[0],
          lon: userLocation[1],
          elevation_m: 0,
          description: 'Your live GPS position',
        },
        ...landmarks,
      ]
    : landmarks;

  const currentOrigin = landmarksWithMyLocation.find(l => l.id === selectedOriginId);
  const currentDestination = landmarksWithMyLocation.find(l => l.id === selectedDestinationId);
  const originCoords = useMemo<[number, number] | null>(() => {
    return currentOrigin ? [currentOrigin.lat, currentOrigin.lon] : null;
  }, [currentOrigin?.lat, currentOrigin?.lon]);
  const destinationCoords = useMemo<[number, number] | null>(() => {
    return currentDestination ? [currentDestination.lat, currentDestination.lon] : null;
  }, [currentDestination?.lat, currentDestination?.lon]);
  const displayedOriginName = currentOrigin?.name;
  const displayedDestinationName = currentDestination?.name;

  return (
    <div className="relative flex flex-col h-[calc(100vh-4rem)] bg-slate-950 text-slate-100 overflow-hidden">
      
      {/* Top HUD Mission Bar */}
      <div className="h-11 shrink-0 border-b border-slate-800/80 bg-slate-950/90 backdrop-blur-md px-4 flex items-center justify-between z-20">
        <div className="flex items-center space-x-3">
          {/* City Context Switcher */}
          {onCityChange && (
            <div className="flex items-center bg-slate-900/90 p-0.5 rounded-lg border border-slate-800">
              <button
                onClick={() => onCityChange('mumbai')}
                className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                  currentCity.toLowerCase() === 'mumbai'
                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Mumbai (BKC)
              </button>
              <button
                onClick={() => onCityChange('kolkata')}
                className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                  currentCity.toLowerCase() === 'kolkata'
                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Kolkata (Bypass)
              </button>
            </div>
          )}

          {/* Simulation / Live Mode Button */}
          <button
            onClick={() => setIsSimModalOpen(true)}
            className="flex items-center space-x-1.5 px-2.5 py-1 rounded-lg border border-slate-800 bg-slate-900/80 hover:bg-slate-800 text-slate-300 text-xs font-mono transition-all cursor-pointer"
          >
            <Radio className="h-3 w-3 text-cyan-400" />
            <span className="capitalize">{floodOverview?.scenario || 'Simulation'}</span>
            <Sliders className="h-3 w-3 text-slate-500" />
          </button>

          {/* Forecast Horizon Badge & Toggle */}
          <button
            onClick={() => setShowTimelineBar(!showTimelineBar)}
            className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-lg border text-xs font-mono transition-all cursor-pointer ${
              showTimelineBar
                ? 'bg-slate-900/80 hover:bg-slate-800 border-slate-800 text-cyan-400'
                : 'bg-cyan-500/20 hover:bg-cyan-500/30 border-cyan-500/40 text-cyan-300'
            }`}
            title={showTimelineBar ? "Hide timeline bar" : "Show timeline bar"}
          >
            <Clock className="h-3 w-3" />
            <span>T+{currentTimeStep}m</span>
          </button>

          {/* Traffic Layer Quick Toggle */}
          <button
            onClick={() => setShowTrafficLayer(!showTrafficLayer)}
            className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-lg border text-xs font-mono transition-all cursor-pointer ${
              showTrafficLayer
                ? 'bg-amber-950/40 hover:bg-amber-900/50 border-amber-500/40 text-amber-300 shadow-sm'
                : 'bg-slate-900/80 hover:bg-slate-800 border-slate-800 text-slate-500'
            }`}
            title={showTrafficLayer ? `Traffic Layer Active (${trafficMode === 'peak_monsoon' ? 'Peak Monsoon Rush Hour' : 'TomTom Live'})` : 'Show Traffic Flow Layer'}
          >
            <span className={`h-2 w-2 rounded-full ${showTrafficLayer ? 'bg-amber-400 animate-pulse' : 'bg-slate-600'}`} />
            <span className="font-semibold">Traffic: {trafficMode === 'peak_monsoon' ? 'Peak' : 'Live'}</span>
          </button>

          {/* Drainage HUD Quick Button */}
          <button
            onClick={() => setIsDrainagePanelOpen(!isDrainagePanelOpen)}
            className={`hidden md:flex items-center space-x-1.5 px-2.5 py-1 rounded-lg border text-xs font-mono transition-all cursor-pointer ${
              isDrainagePanelOpen
                ? 'bg-emerald-950/40 hover:bg-emerald-900/50 border-emerald-500/40 text-emerald-300 shadow-sm'
                : 'bg-slate-900/80 hover:bg-slate-800 border-slate-800 text-slate-400'
            }`}
            title="Toggle Drainage Network HUD"
          >
            <GitFork className="h-3 w-3 text-emerald-400" />
            <span>Drainage HUD</span>
            {surchargingCount > 0 && (
              <span className="px-1.5 py-0.2 rounded-full bg-red-500/30 text-red-400 text-[9px] font-bold border border-red-500/40">
                {surchargingCount}
              </span>
            )}
          </button>

          {/* Evacuation Router HUD Quick Button */}
          <button
            onClick={() => setIsRoutePanelOpen(!isRoutePanelOpen)}
            className={`hidden md:flex items-center space-x-1.5 px-2.5 py-1 rounded-lg border text-xs font-mono transition-all cursor-pointer ${
              isRoutePanelOpen
                ? 'bg-cyan-950/40 hover:bg-cyan-900/50 border-cyan-500/40 text-cyan-300 shadow-sm'
                : 'bg-slate-900/80 hover:bg-slate-800 border-slate-800 text-slate-400'
            }`}
            title="Toggle Evacuation Router HUD"
          >
            <Navigation className="h-3 w-3 text-cyan-400" />
            <span>Router HUD</span>
          </button>
        </div>

        {/* Right: Consolidated System Status Indicator with Popover */}
        <div className="relative">
          <button
            onClick={() => setIsTelemetryOpen(!isTelemetryOpen)}
            className="flex items-center space-x-2 px-3 py-1 rounded-full border border-slate-800 bg-slate-900/80 hover:bg-slate-800 text-xs transition-all cursor-pointer"
          >
            <span className={`h-2 w-2 rounded-full ${
              (currentSummary?.flooded_cells_30cm || 0) > 0
                ? 'bg-rose-500 animate-pulse'
                : (currentSummary?.flooded_cells_15cm || 0) > 0
                ? 'bg-amber-400'
                : 'bg-emerald-400'
            }`} />
            <span className="font-mono text-slate-300">
              {(currentSummary?.flooded_cells_30cm || 0) > 0
                ? `${currentSummary?.flooded_cells_30cm} Severe Cells`
                : (currentSummary?.flooded_cells_15cm || 0) > 0
                ? `${currentSummary?.flooded_cells_15cm} Caution Cells`
                : 'System Normal'}
            </span>
            <ChevronDown className="h-3 w-3 text-slate-500" />
          </button>

          {/* Popover for Full System Telemetry */}
          {isTelemetryOpen && (
            <div className="absolute right-0 top-9 w-72 rounded-2xl bg-slate-950/95 border border-slate-800 shadow-2xl p-4 text-xs font-mono z-50 space-y-2.5 backdrop-blur-xl animate-in fade-in duration-150">
              <div className="flex items-center justify-between pb-2 border-b border-slate-800 text-slate-300 font-bold">
                <span>SYSTEM STATUS</span>
                <span className={`text-[10px] px-2 py-0.5 rounded-full ${wsStatus === 'connected' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'}`}>
                  {wsStatus === 'connected' ? 'WS STREAMING' : 'CONNECTING'}
                </span>
              </div>
              <div className="space-y-1.5 text-slate-400 text-[11px]">
                <div className="flex justify-between">
                  <span>Peak Inundation:</span>
                  <span className="font-bold text-slate-200">{currentSummary ? `${currentSummary.max_depth_m.toFixed(2)}m` : '0.23m'}</span>
                </div>
                <div className="flex justify-between">
                  <span>Surface Volume:</span>
                  <span className="font-bold text-slate-200">{currentSummary ? `${Math.round(currentSummary.surface_water_volume_m3).toLocaleString()} m³` : '12,055 m³'}</span>
                </div>
                <div className="flex justify-between">
                  <span>Caution Cells (&gt;0.15m):</span>
                  <span className="font-bold text-amber-400">{currentSummary?.flooded_cells_15cm || 30}</span>
                </div>
                <div className="flex justify-between">
                  <span>Severe Cells (&gt;0.30m):</span>
                  <span className="font-bold text-rose-400">{currentSummary?.flooded_cells_30cm || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span>Total Rain Volume:</span>
                  <span className="font-bold text-slate-200">{floodOverview ? `${Math.round(floodOverview.total_rain_volume_m3).toLocaleString()} m³` : '—'}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Main Workspace Grid */}
      <div className="relative flex-1 flex overflow-hidden">
        
        {/* Left Floating Tool Palette (Collapsible & Narrow) */}
        <aside
          className={`relative shrink-0 border-r border-slate-800/80 bg-slate-950/90 backdrop-blur-xl flex flex-col justify-between overflow-y-auto z-10 transition-all duration-200 ${
            isSidebarCollapsed ? 'w-12 p-2 items-center' : 'w-64 p-3.5'
          }`}
        >
          {isSidebarCollapsed ? (
            /* Collapsed Sidebar Rail */
            <div className="flex flex-col items-center space-y-4 pt-2">
              <button
                onClick={() => setIsSidebarCollapsed(false)}
                title="Expand Controls"
                className="p-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-300 hover:text-cyan-400 hover:bg-slate-800 transition-colors cursor-pointer"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
              <button
                onClick={() => setShowFloodHeatmap(!showFloodHeatmap)}
                title="Toggle Flood Depth"
                className={`p-2 rounded-xl border transition-colors cursor-pointer ${
                  showFloodHeatmap ? 'bg-cyan-500/20 border-cyan-500/40 text-cyan-300' : 'bg-slate-900 border-slate-800 text-slate-500'
                }`}
              >
                <Waves className="h-4 w-4" />
              </button>
              <button
                onClick={() => setShowRoadGrid(!showRoadGrid)}
                title="Toggle Road Grid"
                className={`p-2 rounded-xl border transition-colors cursor-pointer ${
                  showRoadGrid ? 'bg-cyan-500/20 border-cyan-500/40 text-cyan-300' : 'bg-slate-900 border-slate-800 text-slate-500'
                }`}
              >
                <Layers className="h-4 w-4" />
              </button>
              <button
                onClick={() => setIsSimModalOpen(true)}
                title="Configure Simulation"
                className="p-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-400 hover:text-cyan-300 transition-colors cursor-pointer"
              >
                <Sliders className="h-4 w-4" />
              </button>
            </div>
          ) : (
            /* Expanded Sidebar Content */
            <div className="space-y-4">
              
              {/* Header with collapse button */}
              <div className="flex items-center justify-between pb-1 border-b border-slate-800/80">
                <span className="text-xs font-mono font-bold text-slate-400 tracking-wider">CONTROLS</span>
                <button
                  onClick={() => setIsSidebarCollapsed(true)}
                  title="Collapse sidebar"
                  className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-900 transition-colors cursor-pointer"
                >
                  <ChevronLeft className="h-3.5 w-3.5" />
                </button>
              </div>

              {/* Active Sector */}
              {onCityChange && (
                <div className="space-y-1.5">
                  <span className="text-[11px] font-mono font-bold text-slate-400 block">ACTIVE SECTOR</span>
                  <div className="grid grid-cols-2 gap-1.5">
                    <button
                      onClick={() => onCityChange('mumbai')}
                      className={`py-1.5 px-2 rounded-xl border text-xs font-semibold transition-all text-center cursor-pointer ${
                        currentCity.toLowerCase() === 'mumbai'
                          ? 'bg-cyan-500/20 border-cyan-400/60 text-cyan-300 ring-1 ring-cyan-500/30'
                          : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      Mumbai (BKC)
                    </button>
                    <button
                      onClick={() => onCityChange('kolkata')}
                      className={`py-1.5 px-2 rounded-xl border text-xs font-semibold transition-all text-center cursor-pointer ${
                        currentCity.toLowerCase() === 'kolkata'
                          ? 'bg-cyan-500/20 border-cyan-400/60 text-cyan-300 ring-1 ring-cyan-500/30'
                          : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      Kolkata (Bypass)
                    </button>
                  </div>
                </div>
              )}

              {/* Rainfall Source */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-[11px] font-mono font-bold text-slate-400">
                  <span className="flex items-center">
                    <CloudRain className="h-3.5 w-3.5 mr-1 text-cyan-400" />
                    RAINFALL
                  </span>
                  <span 
                    className="text-[10px] text-cyan-400 uppercase font-mono truncate max-w-[130px]"
                    title={floodOverview?.scenario_title || floodOverview?.scenario || 'HEAVY'}
                  >
                    {floodOverview?.scenario_title || floodOverview?.scenario || 'HEAVY'}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-1.5">
                  <button
                    disabled={isSimulating}
                    onClick={() => handleRunSimulation('live')}
                    className="py-1.5 px-2 rounded-xl border border-emerald-500/30 bg-emerald-950/30 hover:bg-emerald-900/40 text-emerald-300 text-xs font-medium flex items-center justify-center space-x-1 cursor-pointer transition-all active:scale-95 disabled:opacity-50"
                  >
                    <Radio className="h-3 w-3 text-emerald-400" />
                    <span>Live Doppler</span>
                  </button>
                  <button
                    disabled={isSimulating}
                    onClick={() => handleRunSimulation('historical')}
                    className="py-1.5 px-2 rounded-xl border border-blue-500/30 bg-blue-950/30 hover:bg-blue-900/40 text-blue-300 text-xs font-medium flex items-center justify-center space-x-1 cursor-pointer transition-all active:scale-95 disabled:opacity-50"
                  >
                    <Calendar className="h-3 w-3 text-blue-400" />
                    <span>Historical</span>
                  </button>
                </div>

                {/* Quick Historic Presets Selector */}
                <div className="pt-0.5">
                  <select
                    value={selectedHistoricalPreset}
                    onChange={(e) => {
                      const presetId = e.target.value;
                      setSelectedHistoricalPreset(presetId);
                      setSimMode('historical');
                      handleRunSimulation('historical', presetId);
                    }}
                    className="w-full bg-slate-900/90 border border-cyan-500/30 hover:border-cyan-400/50 rounded-xl px-2 py-1.5 text-[11px] font-mono text-cyan-300 focus:outline-none focus:border-cyan-400 cursor-pointer shadow-inner transition-colors"
                  >
                    {currentCity.toLowerCase() === 'kolkata' ? (
                      <>
                        <option value="kolkata_2021_cloudburst">Sep 2021 Cloudburst (142mm)</option>
                        <option value="kolkata_2020_amphan">May 2020 Cyclone Amphan (236mm)</option>
                        <option value="kolkata_2021_depression">Jun 2021 Depression (178mm)</option>
                      </>
                    ) : (
                      <>
                        <option value="mumbai_2023_deluge">Jul 2023 Deluge (204mm)</option>
                        <option value="mumbai_2005_cloudburst">Jul 2005 Cloudburst (944mm)</option>
                        <option value="mumbai_2019_monsoon">Jul 2019 Monsoon Deluge (375mm)</option>
                      </>
                    )}
                  </select>
                </div>

                <button
                  onClick={() => setIsSimModalOpen(true)}
                  className="w-full py-1.5 px-2.5 rounded-xl border border-slate-800 bg-slate-900/50 hover:bg-slate-800/80 text-slate-300 text-[11px] font-mono flex items-center justify-between cursor-pointer transition-all group"
                >
                  <span className="flex items-center space-x-1.5">
                    <Sliders className="h-3 w-3 text-cyan-400 group-hover:rotate-45 transition-transform" />
                    <span>Configure Scenario...</span>
                  </span>
                  <ChevronRight className="h-3 w-3 text-slate-500 group-hover:translate-x-0.5 transition-transform" />
                </button>
              </div>

              {/* Map Layers */}
              <div className="space-y-1.5">
                <span className="text-[11px] font-mono font-bold text-slate-400 tracking-wider block">
                  MAP LAYERS
                </span>

                <div className="space-y-1">
                  <button
                    onClick={() => setShowFloodHeatmap(!showFloodHeatmap)}
                    className={`w-full flex items-center justify-between p-2 rounded-xl border text-xs font-medium transition-all cursor-pointer ${
                      showFloodHeatmap
                        ? 'bg-cyan-950/40 border-cyan-500/40 text-cyan-300 shadow-sm'
                        : 'bg-slate-900/40 border-slate-800/80 text-slate-500'
                    }`}
                  >
                    <span className="flex items-center space-x-2">
                      <span className={`h-1.5 w-1.5 rounded-full ${showFloodHeatmap ? 'bg-cyan-400' : 'bg-slate-600'}`} />
                      <span>Flood Depth</span>
                    </span>
                    {showFloodHeatmap ? <Eye className="h-3.5 w-3.5 text-cyan-400" /> : <EyeOff className="h-3.5 w-3.5" />}
                  </button>

                  <button
                    onClick={() => setShowRoadGrid(!showRoadGrid)}
                    className={`w-full flex items-center justify-between p-2 rounded-xl border text-xs font-medium transition-all cursor-pointer ${
                      showRoadGrid
                        ? 'bg-cyan-950/40 border-cyan-500/40 text-cyan-300 shadow-sm'
                        : 'bg-slate-900/40 border-slate-800/80 text-slate-500'
                    }`}
                  >
                    <span className="flex items-center space-x-2">
                      <span className={`h-1.5 w-1.5 rounded-full ${showRoadGrid ? 'bg-cyan-400' : 'bg-slate-600'}`} />
                      <span>Roads ({roadSummary ? `${roadSummary.total_length_km.toFixed(0)}km` : '102km'})</span>
                    </span>
                    {showRoadGrid ? <Eye className="h-3.5 w-3.5 text-cyan-400" /> : <EyeOff className="h-3.5 w-3.5" />}
                  </button>

                  <button
                    onClick={() => setShowHotspots(!showHotspots)}
                    className={`w-full flex items-center justify-between p-2 rounded-xl border text-xs font-medium transition-all cursor-pointer ${
                      showHotspots
                        ? 'bg-amber-950/40 border-amber-500/40 text-amber-300 shadow-sm'
                        : 'bg-slate-900/40 border-slate-800/80 text-slate-500'
                    }`}
                  >
                    <span className="flex items-center space-x-2">
                      <span className={`h-1.5 w-1.5 rounded-full ${showHotspots ? 'bg-amber-400 animate-pulse' : 'bg-slate-600'}`} />
                      <span>Hotspots (Clustered)</span>
                    </span>
                    {showHotspots ? <Eye className="h-3.5 w-3.5 text-amber-400" /> : <EyeOff className="h-3.5 w-3.5" />}
                  </button>

                  <button
                    onClick={() => setShowDrainagePipes(!showDrainagePipes)}
                    className={`w-full flex items-center justify-between p-2 rounded-xl border text-xs font-medium transition-all cursor-pointer ${
                      showDrainagePipes
                        ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300'
                        : 'bg-slate-900/40 border-slate-800/80 text-slate-500'
                    }`}
                  >
                    <span className="flex items-center space-x-2">
                      <span className={`h-1.5 w-1.5 rounded-full ${showDrainagePipes ? 'bg-emerald-400' : 'bg-slate-600'}`} />
                      <span>Drainage Network</span>
                    </span>
                    {showDrainagePipes ? <Eye className="h-3.5 w-3.5 text-emerald-400" /> : <EyeOff className="h-3.5 w-3.5" />}
                  </button>

                  <button
                    onClick={() => setShowTrafficLayer(!showTrafficLayer)}
                    className={`w-full flex items-center justify-between p-2 rounded-xl border text-xs font-medium transition-all cursor-pointer ${
                      showTrafficLayer
                        ? 'bg-amber-950/40 border-amber-500/40 text-amber-300 shadow-sm'
                        : 'bg-slate-900/40 border-slate-800/80 text-slate-500'
                    }`}
                  >
                    <span className="flex items-center space-x-2">
                      <span className={`h-1.5 w-1.5 rounded-full ${showTrafficLayer ? 'bg-amber-400 animate-pulse' : 'bg-slate-600'}`} />
                      <span>Traffic Flow ({trafficMode === 'peak_monsoon' ? 'Peak Rush' : 'TomTom'})</span>
                    </span>
                    {showTrafficLayer ? <Eye className="h-3.5 w-3.5 text-amber-400" /> : <EyeOff className="h-3.5 w-3.5" />}
                  </button>

                  <button
                    onClick={() => setShowDemTerrain(!showDemTerrain)}
                    className={`w-full flex items-center justify-between p-2 rounded-xl border text-xs font-medium transition-all cursor-pointer ${
                      showDemTerrain
                        ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300 shadow-sm'
                        : 'bg-slate-900/40 border-slate-800/80 text-slate-500'
                    }`}
                  >
                    <span className="flex items-center space-x-2">
                      <Mountain className={`h-3 w-3 ${showDemTerrain ? 'text-emerald-400' : 'text-slate-600'}`} />
                      <span>3D DEM Relief</span>
                    </span>
                    {showDemTerrain ? <Eye className="h-3.5 w-3.5 text-emerald-400" /> : <EyeOff className="h-3.5 w-3.5" />}
                  </button>
                </div>
              </div>

              {/* Advanced Configuration Accordion */}
              <div className="pt-2 border-t border-slate-800/80">
                <button
                  onClick={() => setIsAdvancedConfigOpen(!isAdvancedConfigOpen)}
                  className="w-full flex items-center justify-between text-[11px] font-mono text-slate-400 hover:text-slate-200 py-1 transition-colors cursor-pointer"
                >
                  <span className="font-bold">ADVANCED SETTINGS</span>
                  {isAdvancedConfigOpen ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                </button>

                {isAdvancedConfigOpen && (
                  <div className="mt-2 space-y-3 animate-in fade-in duration-150">
                    <div>
                      <span className="text-[10px] font-mono text-slate-400 block mb-1">
                        VEHICLE WADING PROFILE
                      </span>
                      <div className="grid grid-cols-3 gap-1 p-1 rounded-xl bg-slate-900/80 border border-slate-800">
                        <button
                          onClick={() => setSelectedVehicle('pedestrian')}
                          className={`py-1 text-center text-[9px] font-medium rounded-lg transition-all cursor-pointer ${
                            selectedVehicle === 'pedestrian'
                              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold'
                              : 'text-slate-400 hover:text-slate-200'
                          }`}
                        >
                          Foot
                        </button>
                        <button
                          onClick={() => setSelectedVehicle('bike')}
                          className={`py-1 text-center text-[9px] font-medium rounded-lg transition-all cursor-pointer ${
                            selectedVehicle === 'bike'
                              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold'
                              : 'text-slate-400 hover:text-slate-200'
                          }`}
                        >
                          Bike
                        </button>
                        <button
                          onClick={() => setSelectedVehicle('car')}
                          className={`py-1 text-center text-[9px] font-medium rounded-lg transition-all cursor-pointer ${
                            selectedVehicle === 'car'
                              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold'
                              : 'text-slate-400 hover:text-slate-200'
                          }`}
                        >
                          Car
                        </button>
                        <button
                          onClick={() => setSelectedVehicle('suv')}
                          className={`py-1 text-center text-[9px] font-medium rounded-lg transition-all cursor-pointer ${
                            selectedVehicle === 'suv'
                              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold'
                              : 'text-slate-400 hover:text-slate-200'
                          }`}
                        >
                          SUV
                        </button>
                        <button
                          onClick={() => setSelectedVehicle('ambulance')}
                          className={`py-1 text-center text-[9px] font-medium rounded-lg transition-all cursor-pointer ${
                            selectedVehicle === 'ambulance'
                              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold'
                              : 'text-slate-400 hover:text-slate-200'
                          }`}
                        >
                          Amb
                        </button>
                        <button
                          onClick={() => setSelectedVehicle('rescue')}
                          className={`py-1 text-center text-[9px] font-medium rounded-lg transition-all cursor-pointer ${
                            selectedVehicle === 'rescue'
                              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold'
                              : 'text-slate-400 hover:text-slate-200'
                          }`}
                        >
                          Truck
                        </button>
                      </div>
                    </div>

                    {showDemTerrain && (
                      <div className="p-2 rounded-xl bg-slate-900/50 border border-slate-800/80 space-y-1">
                        <span className="text-[10px] font-mono text-emerald-400 flex items-center space-x-1">
                          <Mountain className="h-3 w-3" />
                          <span>HYPSOMETRIC RELIEF</span>
                        </span>
                        <div className="h-1.5 w-full rounded-full bg-gradient-to-r from-emerald-600 via-lime-500 via-amber-500 to-slate-100" />
                        <div className="flex justify-between text-[9px] font-mono text-slate-400">
                          <span>Low (&lt;3m)</span>
                          <span>High (&gt;15m)</span>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

            </div>
          )}
        </aside>

        {/* Center GIS Viewport: Leaflet Native Map with Flood Raster & Subterranean Network */}
        <main className="relative flex-1 bg-slate-950 overflow-hidden">
          <GisMap
            currentCity={currentCity}
            currentTimeStep={currentTimeStep}
            showRoads={showRoadGrid}
            showHotspots={showHotspots}
            showFloodHeatmap={showFloodHeatmap}
            showDrainagePipes={showDrainagePipes}
            showDemTerrain={showDemTerrain}
            routeResult={routeResult}
            alternatives={routeAlternatives}
            activeRouteIndex={activeRouteIndex}
            onSelectRouteIndex={(idx) => setActiveRouteIndex(idx)}
            originCoords={originCoords}
            destinationCoords={destinationCoords}
            originName={displayedOriginName}
            destinationName={displayedDestinationName}
            onDrainageSummaryLoaded={(surcharges) => setSurchargingCount(surcharges)}
            drainageRefreshKey={drainageRefreshKey}
            simulationKey={simulationKey}
            userLocation={userLocation}
            onMapClick={handleMapClick}
            isNavigating={isNavigating}
            navLocation={navLocation}
            navBearing={navBearing}
            navTraversedCoords={navTraversedCoords}
            navRemainingCoords={navRemainingCoords}
            isFollowMode={isFollowMode}
            onMapUserDrag={() => setIsFollowMode(false)}
            showTrafficLayer={showTrafficLayer}
            trafficTileUrl={trafficConfig?.traffic_tile_url}
            trafficMode={trafficMode}
            selectedVehicle={selectedVehicle}
            navViewMode={navViewMode}
          />

          {/* Active Turn-by-Turn Navigation HUD Overlay */}
          {isNavigating && (
            <NavigationHud
              currentStep={navSteps[navActiveStepIndex] || null}
              nextStep={navSteps[navActiveStepIndex + 1] || null}
              distanceToNextTurn_m={distanceToNextTurn}
              totalRemainingDistance_m={totalRemainingDistance}
              totalRemainingDuration_s={totalRemainingDuration}
              isSimulating={isSimPlaying}
              simProgressPct={simProgressPct}
              simSpeedMultiplier={simSpeedMultiplier}
              isVoiceMuted={isVoiceMuted}
              vehicleType={selectedVehicle}
              isLiveGps={isLiveGps}
              hasGpsLock={hasGpsLock}
              isFollowMode={isFollowMode}
              navViewMode={navViewMode}
              onToggleViewMode={() => setNavViewMode((prev) => (prev === '3d' ? '2d' : '3d'))}
              onTogglePlayPause={() => setIsSimPlaying(!isSimPlaying)}
              onChangeSpeed={(mult) => setSimSpeedMultiplier(mult)}
              onSeekProgress={(pct) => handleSeekProgress(pct)}
              onToggleVoice={handleToggleVoice}
              onRecenterCamera={() => setIsFollowMode(true)}
              onToggleLiveGps={handleToggleLiveGps}
              onTriggerOffRouteSim={handleTriggerOffRouteSim}
              onExitNavigation={handleExitNavigation}
            />
          )}

          {/* Floating Subterranean Drainage Diagnostics HUD Panel (Hidden during navigation) */}
          {!isNavigating && (
            <DrainagePanel
              city={currentCity}
              summary={drainageSummary}
              onUpdateBlockage={handleUpdateBlockage}
              onResetDrainage={handleResetDrainage}
              isUpdating={isUpdatingBlockage}
              isOpen={isDrainagePanelOpen}
              onToggleOpen={() => setIsDrainagePanelOpen(!isDrainagePanelOpen)}
              surchargingCount={surchargingCount}
            />
          )}

          {/* Floating Resilient Evacuation Route HUD Panel (Hidden during navigation) */}
          {!isNavigating && (
            <RoutePanel
              landmarks={landmarksWithMyLocation}
              selectedOriginId={selectedOriginId}
              selectedDestinationId={selectedDestinationId}
              onSelectOriginId={(id) => { setSelectedOriginId(id); setRouteResult(null); setRouteAlternatives([]); }}
              onSelectDestinationId={(id) => { setSelectedDestinationId(id); setRouteResult(null); setRouteAlternatives([]); }}
              selectedVehicle={selectedVehicle}
              onSelectVehicle={(v) => { setSelectedVehicle(v); setRouteResult(null); setRouteAlternatives([]); }}
              onCalculateRoute={() => { setHasCalculatedRoute(true); triggerRouteCalculation(); }}
              isCalculating={isCalculatingRoute}
              routeResult={routeResult}
              alternatives={routeAlternatives}
              activeRouteIndex={activeRouteIndex}
              onSelectRouteIndex={(idx) => setActiveRouteIndex(idx)}
              isOpen={isRoutePanelOpen}
              onToggleOpen={() => setIsRoutePanelOpen(!isRoutePanelOpen)}
              timeHorizon={currentTimeStep}
              onStartNavigation={handleStartNavigation}
              trafficMode={trafficMode}
              onSelectTrafficMode={(mode) => {
                setTrafficMode(mode);
                if (routeResult) {
                  triggerRouteCalculation(selectedOriginId, selectedDestinationId, selectedVehicle, currentTimeStep, mode);
                }
              }}
              userLocation={userLocation}
              onUseLiveLocation={handleUseLiveLocationAsOrigin}
              onTestCorridorPipeline={handleTestCorridorPipeline}
            />
          )}
          {/* GPS Error / Permission nudge */}
          {geoError && !userLocation && !isNavigating && (
            <div className="absolute bottom-24 left-1/2 -translate-x-1/2 z-30 flex items-center space-x-2 px-4 py-2 rounded-xl bg-amber-950/90 border border-amber-500/40 text-amber-300 text-xs font-mono-num shadow-xl backdrop-blur-md">
              <span>⚠️</span>
              <span>GPS: {geoError} — allow location access for live tracking</span>
            </div>
          )}
        </main>

      </div>

      {/* Bottom Temporal Timeline Bar */}
      {showTimelineBar ? (
        <footer
        className="relative h-[54px] shrink-0 border-t border-slate-800/80 bg-slate-950/95 backdrop-blur-xl px-4 flex items-center justify-between z-20 overflow-hidden"
      >
        <div className="flex items-center space-x-2.5">
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className={`flex h-8 w-8 items-center justify-center rounded-lg font-bold shadow-md active:scale-95 transition-all cursor-pointer ${
              isPlaying 
                ? 'bg-amber-400 text-slate-950 shadow-amber-400/25 hover:bg-amber-300' 
                : 'bg-cyan-500 text-slate-950 shadow-cyan-500/25 hover:bg-cyan-400'
            }`}
          >
            {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4 ml-0.5" />}
          </button>

          <button
            onClick={() => {
              setIsPlaying(false);
              setCurrentTimeStep(0);
            }}
            title="Reset to T+0"
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-800 bg-slate-900 text-slate-400 hover:text-slate-200 hover:bg-slate-800 active:scale-95 transition-all cursor-pointer"
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>

          <div className="flex items-center space-x-1.5 pl-1 text-xs font-mono">
            <span className="text-slate-400">Horizon:</span>
            <span className="font-bold text-cyan-400">T+{currentTimeStep}m</span>
          </div>
        </div>

        {/* Horizon Step Slider & Buttons */}
        <div className="flex-1 max-w-xl mx-4 sm:mx-8 flex items-center space-x-4">
          <div className="flex-1 flex flex-col justify-center">
            <div className="flex justify-between text-[11px] font-mono text-slate-400 mb-1">
              {forecastHorizons.map(h => (
                <button
                  key={h}
                  onClick={() => {
                    setIsPlaying(false);
                    setCurrentTimeStep(h);
                  }}
                  className={`transition-colors cursor-pointer px-1 ${
                    currentTimeStep === h ? 'text-cyan-400 font-bold' : 'hover:text-slate-200'
                  }`}
                >
                  T+{h}
                </button>
              ))}
            </div>

            <input
              type="range"
              min={0}
              max={180}
              step={30}
              value={currentTimeStep}
              onChange={(e) => {
                setIsPlaying(false);
                setCurrentTimeStep(Number(e.target.value));
              }}
              className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400"
            />
          </div>
        </div>

        {/* Compact Critical Alerts Area & Hide Button */}
        <div className="flex items-center space-x-3 text-xs font-mono">
          <div className="flex items-center space-x-2">
            <span className="flex items-center space-x-1 text-amber-400">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
              <span>{currentSummary?.flooded_cells_15cm || 30} caution</span>
            </span>
            <span className="text-slate-600">·</span>
            <span className="flex items-center space-x-1 text-rose-400">
              <span className="h-1.5 w-1.5 rounded-full bg-rose-400" />
              <span>{currentSummary?.flooded_cells_30cm || 0} severe</span>
            </span>
          </div>

          <button
            onClick={() => setShowTimelineBar(false)}
            className="flex items-center space-x-1.5 px-2.5 py-1 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 hover:border-cyan-500/50 text-xs text-cyan-300 hover:text-white transition-all cursor-pointer shadow-sm"
            title="Hide horizon timeline bar"
          >
            <EyeOff className="h-3.5 w-3.5 text-cyan-400" />
            <span className="font-semibold">Hide Bar</span>
          </button>
        </div>
      </footer>
    ) : (
      /* Floating restore button when timeline bar is hidden */
      <div className="fixed bottom-3 right-4 z-30 pointer-events-none">
        <button
          onClick={() => setShowTimelineBar(true)}
          className="pointer-events-auto flex items-center space-x-2 px-3.5 py-2 rounded-xl bg-slate-900/95 hover:bg-slate-800 border border-cyan-500/50 text-xs font-mono text-cyan-300 hover:text-white shadow-2xl backdrop-blur-md transition-all cursor-pointer group"
          title="Show horizon timeline bar"
        >
          <Eye className="h-4 w-4 text-cyan-400 group-hover:scale-110 transition-transform" />
          <span className="font-semibold">Show Horizon Bar (T+{currentTimeStep}m)</span>
        </button>
      </div>
    )}

      {/* Simulation & Live / Historic Rainfall Intelligence Modal */}
      {isSimModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-in fade-in duration-200">
          <div 
            className="relative w-full max-w-2xl bg-slate-900/95 border border-slate-700/80 rounded-3xl shadow-2xl shadow-cyan-950/60 p-6 space-y-5 text-slate-100 overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Ambient decorative glow */}
            <div className="absolute -top-24 -left-24 w-64 h-64 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
            <div className="absolute -bottom-24 -right-24 w-64 h-64 bg-blue-500/10 rounded-full blur-3xl pointer-events-none" />

            {/* Modal Header */}
            <div className="flex items-start justify-between border-b border-slate-800 pb-4 relative z-10">
              <div>
                <div className="flex items-center space-x-2">
                  <div className="h-7 w-7 rounded-xl bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center text-cyan-400">
                    <Radio className="h-4 w-4 animate-pulse" />
                  </div>
                  <h3 className="text-base font-bold text-white tracking-wide">
                    FLOWS SIMULATION & RAINFALL INTELLIGENCE
                  </h3>
                </div>
                <p className="text-xs text-slate-400 mt-1">
                  Run coupled 2D shallow-water hydrodynamic simulations on <span className="text-cyan-300 font-semibold capitalize">{currentCity}</span> ({currentCity.toLowerCase() === 'kolkata' ? '10.5 km EM Bypass Corridor, 35m DEM' : 'BKC / Kurla Basin, 10m DEM'}).
                </p>
              </div>
              <button
                onClick={() => !isSimulating && setIsSimModalOpen(false)}
                className="p-1.5 rounded-xl border border-slate-800 bg-slate-800/50 hover:bg-slate-800 text-slate-400 hover:text-slate-100 transition-colors cursor-pointer"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Mode Tabs */}
            <div className="grid grid-cols-3 gap-2 p-1.5 rounded-2xl bg-slate-950/70 border border-slate-800 relative z-10">
              <button
                onClick={() => setSimMode('live')}
                className={`py-2 px-3 rounded-xl text-xs font-semibold flex items-center justify-center space-x-2 transition-all cursor-pointer ${
                  simMode === 'live'
                    ? 'bg-emerald-500/20 border border-emerald-500/50 text-emerald-300 shadow-sm shadow-emerald-950'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Radio className="h-3.5 w-3.5 text-emerald-400" />
                <span>⚡ Live Radar</span>
              </button>

              <button
                onClick={() => setSimMode('historical')}
                className={`py-2 px-3 rounded-xl text-xs font-semibold flex items-center justify-center space-x-2 transition-all cursor-pointer ${
                  simMode === 'historical'
                    ? 'bg-blue-500/20 border border-blue-500/50 text-blue-300 shadow-sm shadow-blue-950'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Calendar className="h-3.5 w-3.5 text-blue-400" />
                <span>📅 Historic Storm</span>
              </button>

              <button
                onClick={() => setSimMode('demo')}
                className={`py-2 px-3 rounded-xl text-xs font-semibold flex items-center justify-center space-x-2 transition-all cursor-pointer ${
                  simMode === 'demo'
                    ? 'bg-purple-500/20 border border-purple-500/50 text-purple-300 shadow-sm shadow-purple-950'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Zap className="h-3.5 w-3.5 text-purple-400" />
                <span>🌊 Stress Tests</span>
              </button>
            </div>

            {/* Tab 1: Live Radar Nowcast */}
            {simMode === 'live' && (
              <div className="space-y-4 relative z-10">
                <div className="p-4 rounded-2xl bg-emerald-950/20 border border-emerald-500/30 text-xs space-y-2.5">
                  <div className="flex items-center justify-between font-mono-num">
                    <span className="font-bold text-emerald-300 flex items-center space-x-1.5">
                      <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                      <span>LIVE RADAR SYNCHRONIZATION</span>
                    </span>
                    <span className="text-[10px] bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded-full border border-emerald-500/30">
                      RAINVIEWER + OPEN-METEO API
                    </span>
                  </div>
                  <p className="text-slate-300 leading-relaxed">
                    Fetches real-time minute-by-minute Doppler radar reflectivity tiles and high-resolution precipitation nowcasts for <b className="text-white capitalize">{currentCity}</b>. Converts Doppler radar reflectivity (dBZ) to continuous rain rate via Marshall-Palmer equations (<code className="text-emerald-300">Z = 200 · R^1.6</code>).
                  </p>
                  <div className="grid grid-cols-2 gap-2 text-[11px] font-mono-num text-slate-300 pt-1 border-t border-emerald-500/20">
                    <div>Station Coordinates: <span className="text-white font-bold">{currentCity.toLowerCase() === 'kolkata' ? '22.55°N, 88.41°E' : '19.07°N, 72.85°E'}</span></div>
                    <div>Domain Resolution: <span className="text-white font-bold">{currentCity.toLowerCase() === 'kolkata' ? '35m (300×160 cells)' : '10m (200×200 cells)'}</span></div>
                  </div>
                </div>

                <button
                  disabled={isSimulating}
                  onClick={() => handleRunSimulation('live')}
                  className="w-full py-3 rounded-2xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-slate-950 font-bold text-sm shadow-lg shadow-emerald-500/25 active:scale-98 transition-all flex items-center justify-center space-x-2 cursor-pointer disabled:opacity-50"
                >
                  {isSimulating ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>Processing Live Radar Nowcast...</span>
                    </>
                  ) : (
                    <>
                      <Radio className="h-4 w-4" />
                      <span>Fetch Live Doppler Nowcast & Run Model</span>
                    </>
                  )}
                </button>
              </div>
            )}

            {/* Tab 2: Historical Storm Replay */}
            {simMode === 'historical' && (
              <div className="space-y-4 relative z-10">
                <div className="p-4 rounded-2xl bg-blue-950/20 border border-blue-500/30 text-xs space-y-2">
                  <div className="flex items-center justify-between font-mono-num">
                    <span className="font-bold text-blue-300 flex items-center space-x-1.5">
                      <Calendar className="h-3.5 w-3.5 text-blue-400" />
                      <span>REAL STORM REANALYSIS (ERA5 / OPEN-METEO ARCHIVE)</span>
                    </span>
                  </div>
                  <p className="text-slate-300 leading-relaxed">
                    Replays verified catastrophic rainfall events over <b className="text-white capitalize">{currentCity}</b>. Hourly historical precipitation records are disaggregated using a calibrated convective hyetograph to model realistic 15–25 minute cloudburst peaks.
                  </p>
                </div>

                {/* Event Selector */}
                <div className="space-y-2">
                  <label className="text-xs font-mono-num font-bold text-slate-300 block">
                    SELECT HISTORICAL DELUGE PRESET:
                  </label>
                  <div className="grid grid-cols-1 gap-2">
                    {((scenariosMeta?.historical_presets?.[currentCity.toLowerCase() === 'kolkata' ? 'kolkata' : 'mumbai']) || []).map((preset) => {
                      const isSelected = selectedHistoricalPreset === preset.id;
                      return (
                        <div
                          key={preset.id}
                          onClick={() => {
                            setSelectedHistoricalPreset(preset.id);
                            setCustomDate(preset.date_str);
                            setCustomStartHour(preset.start_hour);
                          }}
                          className={`p-3 rounded-2xl border text-xs cursor-pointer transition-all ${
                            isSelected
                              ? 'bg-blue-950/40 border-blue-400 text-blue-200 ring-1 ring-blue-400/50 shadow-sm shadow-blue-950'
                              : 'bg-slate-950/60 border-slate-800 text-slate-300 hover:border-slate-700'
                          }`}
                        >
                          <div className="flex justify-between items-center mb-1">
                            <span className="font-bold text-white flex items-center space-x-1.5">
                              {isSelected ? <CheckCircle2 className="h-3.5 w-3.5 text-blue-400" /> : <span className="h-3.5 w-3.5 rounded-full border border-slate-600 inline-block" />}
                              <span>{preset.title}</span>
                            </span>
                            <span className="font-mono-num text-[11px] text-cyan-400 font-bold">
                              {preset.date_str} @ {String(preset.start_hour).padStart(2, '0')}:00 UTC
                            </span>
                          </div>
                          <p className="text-[11px] text-slate-400 pl-5">{preset.description}</p>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Custom Date / Time Overrides */}
                <div className="grid grid-cols-2 gap-3 p-3 rounded-2xl bg-slate-950/60 border border-slate-800 text-xs">
                  <div>
                    <label className="text-[10px] font-mono-num text-slate-400 block mb-1">CUSTOM DATE (YYYY-MM-DD):</label>
                    <input
                      type="date"
                      value={customDate}
                      onChange={(e) => {
                        setCustomDate(e.target.value);
                        setSelectedHistoricalPreset('');
                      }}
                      className="w-full bg-slate-900 border border-slate-700 rounded-xl px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-cyan-400"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] font-mono-num text-slate-400 block mb-1">START HOUR (0-23 UTC):</label>
                    <input
                      type="number"
                      min={0}
                      max={23}
                      value={customStartHour}
                      onChange={(e) => {
                        setCustomStartHour(Number(e.target.value));
                        setSelectedHistoricalPreset('');
                      }}
                      className="w-full bg-slate-900 border border-slate-700 rounded-xl px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-cyan-400"
                    />
                  </div>
                </div>

                <button
                  disabled={isSimulating}
                  onClick={() => handleRunSimulation('historical')}
                  className="w-full py-3 rounded-2xl bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-400 hover:to-indigo-500 text-white font-bold text-sm shadow-lg shadow-blue-500/25 active:scale-98 transition-all flex items-center justify-center space-x-2 cursor-pointer disabled:opacity-50"
                >
                  {isSimulating ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>Replaying Historic Deluge...</span>
                    </>
                  ) : (
                    <>
                      <Calendar className="h-4 w-4" />
                      <span>Run Historical Reanalysis Simulation</span>
                    </>
                  )}
                </button>
              </div>
            )}

            {/* Tab 3: Synthetic Stress Tests */}
            {simMode === 'demo' && (
              <div className="space-y-4 relative z-10">
                <div className="p-3 rounded-2xl bg-purple-950/20 border border-purple-500/30 text-xs text-slate-300">
                  Select a calibrated synthetic storm intensity to stress-test surface runoff, roadside drainage capacity, and evacuation routes.
                </div>

                <div className="grid grid-cols-1 gap-2 max-h-56 overflow-y-auto pr-1">
                  {[
                    { key: 'cloudburst', title: 'Severe Cloudburst (120 mm/hr)', desc: '120 mm/hr localized 500m-radius cloudburst lasting 30 minutes.' },
                    { key: 'extreme', title: 'Extreme Moving Storm Cell (60 mm/hr)', desc: '60 mm/hr storm cell moving across the domain at 20 km/h.' },
                    { key: 'extreme_blocked', title: 'Extreme Storm + 40% Blocked Drains', desc: '60 mm/hr moving storm cell combined with severe pipe clogging.' },
                    { key: 'heavy', title: 'Heavy Convective Storm (30 mm/hr)', desc: '30 mm/hr Gaussian storm focused over low-elevation terrain depressions.' },
                    { key: 'moderate', title: 'Moderate Steady Rain (10 mm/hr)', desc: '10 mm/hr uniform baseline precipitation over 2 hours.' },
                  ].map((sc) => {
                    const isSel = selectedScenario === sc.key;
                    return (
                      <div
                        key={sc.key}
                        onClick={() => setSelectedScenario(sc.key)}
                        className={`p-3 rounded-2xl border text-xs cursor-pointer transition-all ${
                          isSel
                            ? 'bg-purple-950/40 border-purple-400 text-purple-200 ring-1 ring-purple-400/50 shadow-sm shadow-purple-950'
                            : 'bg-slate-950/60 border-slate-800 text-slate-300 hover:border-slate-700'
                        }`}
                      >
                        <div className="font-bold text-white flex items-center space-x-1.5 mb-1">
                          {isSel ? <CheckCircle2 className="h-3.5 w-3.5 text-purple-400" /> : <span className="h-3.5 w-3.5 rounded-full border border-slate-600 inline-block" />}
                          <span>{sc.title}</span>
                        </div>
                        <p className="text-[11px] text-slate-400 pl-5">{sc.desc}</p>
                      </div>
                    );
                  })}
                </div>

                <button
                  disabled={isSimulating}
                  onClick={() => handleRunSimulation('demo')}
                  className="w-full py-3 rounded-2xl bg-gradient-to-r from-purple-500 to-indigo-600 hover:from-purple-400 hover:to-indigo-500 text-white font-bold text-sm shadow-lg shadow-purple-500/25 active:scale-98 transition-all flex items-center justify-center space-x-2 cursor-pointer disabled:opacity-50"
                >
                  {isSimulating ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>Executing Stress Simulation...</span>
                    </>
                  ) : (
                    <>
                      <Zap className="h-4 w-4" />
                      <span>Execute Stress Simulation</span>
                    </>
                  )}
                </button>
              </div>
            )}

            {/* In-Flight Simulation Progress Banner */}
            {isSimulating && (
              <div className="p-3 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-xs text-cyan-300 flex items-center space-x-2.5 font-mono-num animate-pulse">
                <Loader2 className="h-4 w-4 animate-spin text-cyan-400 flex-shrink-0" />
                <span>{simStatusMsg || 'Running 2D shallow-water hydrodynamic model...'}</span>
              </div>
            )}

          </div>
        </div>
      )}

    </div>
  );
};
