import React, { useState, useEffect, useRef } from 'react';
import { 
  Play, 
  Pause, 
  RotateCcw, 
  Layers, 
  Eye, 
  EyeOff, 
  AlertTriangle, 
  Activity, 
  Car, 
  Truck,
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
  User,
  Bike
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
} from '../services/api';
import type { 
  RoadSummary, 
  FloodForecastOverview, 
  HorizonSummary, 
  Landmark, 
  RouteResult,
  DrainageSummary,
  ScenariosResponse,
  TrafficConfig,
} from '../services/api';

interface CommandCenterViewProps {
  currentCity: string;
  onCityChange?: (city: string) => void;
}

export const CommandCenterView: React.FC<CommandCenterViewProps> = ({ currentCity, onCityChange }) => {
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [currentTimeStep, setCurrentTimeStep] = useState<number>(60); // default to T+60m
  const [showFloodHeatmap, setShowFloodHeatmap] = useState<boolean>(true);
  const [showDrainagePipes, setShowDrainagePipes] = useState<boolean>(false); // default OFF to avoid cluttered green lines
  const [showRoadGrid, setShowRoadGrid] = useState<boolean>(true);
  const [showHotspots, setShowHotspots] = useState<boolean>(true);
  const [showDemTerrain, setShowDemTerrain] = useState<boolean>(false);
  const [showTrafficLayer, setShowTrafficLayer] = useState<boolean>(true);
  const [trafficConfig, setTrafficConfig] = useState<TrafficConfig | null>(null);
  const [trafficMode, setTrafficMode] = useState<'peak_monsoon' | 'live'>('peak_monsoon');
  const [selectedVehicle, setSelectedVehicle] = useState<TransportMode>('ambulance');
  
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
  const [isRoutePanelOpen, setIsRoutePanelOpen] = useState<boolean>(true);
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
  const [isSimPlaying, setIsSimPlaying] = useState<boolean>(false);
  const [simProgressPct, setSimProgressPct] = useState<number>(0);
  const [simSpeedMultiplier, setSimSpeedMultiplier] = useState<number>(2);
  const [isVoiceMuted, setIsVoiceMuted] = useState<boolean>(false);
  const [distanceToNextTurn, setDistanceToNextTurn] = useState<number>(0);
  const [totalRemainingDistance, setTotalRemainingDistance] = useState<number>(0);
  const [totalRemainingDuration, setTotalRemainingDuration] = useState<number>(0);
  const lastAnnouncedStepRef = useRef<number>(-1);
  const navWatchIdRef = useRef<number | null>(null);
  
  const playIntervalRef = useRef<any>(null);

  // ── Resizable footer ──────────────────────────────────────────────────────
  const [footerHeight, setFooterHeight] = useState<number>(80);
  const footerDragRef = useRef<{ startY: number; startH: number } | null>(null);

  const onFooterDragStart = (e: React.MouseEvent) => {
    e.preventDefault();
    footerDragRef.current = { startY: e.clientY, startH: footerHeight };
    const onMove = (mv: MouseEvent) => {
      if (!footerDragRef.current) return;
      const delta = footerDragRef.current.startY - mv.clientY;
      setFooterHeight(Math.min(260, Math.max(56, footerDragRef.current.startH + delta)));
    };
    const onUp = () => {
      footerDragRef.current = null;
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  };

  // ── Resizable left tool panel ─────────────────────────────────────────────
  const [leftPanelWidth, setLeftPanelWidth] = useState<number>(320);
  const leftDragRef = useRef<{ startX: number; startW: number } | null>(null);

  const onLeftDragStart = (e: React.MouseEvent) => {
    e.preventDefault();
    leftDragRef.current = { startX: e.clientX, startW: leftPanelWidth };
    const onMove = (mv: MouseEvent) => {
      if (!leftDragRef.current) return;
      const delta = mv.clientX - leftDragRef.current.startX;
      setLeftPanelWidth(Math.min(540, Math.max(260, leftDragRef.current.startW + delta)));
    };
    const onUp = () => {
      leftDragRef.current = null;
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  };
  // ─────────────────────────────────────────────────────────────────────────

  const forecastHorizons = [0, 30, 60, 90, 120, 180];

  // Fetch scenarios metadata and traffic configuration on initial mount
  useEffect(() => {
    fetchSupportedScenarios().then(data => {
      if (data) {
        setScenariosMeta(data);
      }
    });

    fetchTrafficConfig().then(cfg => {
      if (cfg) {
        setTrafficConfig(cfg);
      }
    });
  }, []);

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
      let date_str = undefined;
      let start_hour = undefined;

      if (activeMode === 'live') {
        scenario = 'live';
      } else if (activeMode === 'historical') {
        scenario = 'historical';
        const presets = scenariosMeta?.historical_presets?.[isKolkata ? 'kolkata' : 'mumbai'] || [];
        const preset = presets.find(p => p.id === selectedHistoricalPreset);
        if (preset) {
          date_str = preset.date_str;
          start_hour = preset.start_hour;
        } else {
          date_str = customDate || (isKolkata ? '2021-09-20' : '2023-07-26');
          start_hour = customStartHour;
        }
      }

      const res = await runSimulation({
        city: currentCity,
        scenario,
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

  // Route calculation routine
  const triggerRouteCalculation = async (
    origId = selectedOriginId,
    destId = selectedDestinationId,
    veh = selectedVehicle,
    horizon = currentTimeStep,
    tMode = trafficMode
  ) => {
    if (landmarks.length === 0) return;
    const orig = landmarks.find(l => l.id === origId);
    const dest = landmarks.find(l => l.id === destId);
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
        traffic_mode: tMode,
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

  // Reset route whenever city changes so route only appears on explicit calculation
  useEffect(() => {
    setRouteResult(null);
    setRouteAlternatives([]);
    setActiveRouteIndex(0);
    setIsNavigating(false);
  }, [currentCity]);

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

  // Current Horizon Summary
  const currentSummary: HorizonSummary | undefined = 
    floodOverview?.summaries ? floodOverview.summaries[String(currentTimeStep)] : undefined;

  // ── NAVIGATION ENGINE LOGIC & TELEMETRY ─────────────────────────────────────
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
      setHasGpsLock(false);
      navigationVoice.speak('Switching to demo route simulation.');
    }
  };

  const handleTriggerOffRouteSim = () => {
    if (!navLocation || !currentDestination) return;
    const offLat = navLocation[1] + 0.0035;
    const offLon = navLocation[0] + 0.0035;
    setNavLocation([offLon, offLat]);
    navigationVoice.speak('Off route detected. Recalculating path around flooded corridors.', true);

    calculateFloodRoute({
      src_lat: offLat,
      src_lon: offLon,
      dst_lat: currentDestination.lat,
      dst_lon: currentDestination.lon,
      vehicle_type: selectedVehicle,
      time_horizon_min: currentTimeStep,
      include_alternatives: true,
    }).then((res) => {
      if (res && res.primary_route) {
        setRouteResult(res.primary_route);
        const newSteps = generateTurnByTurnSteps(res.primary_route);
        setNavSteps(newSteps);
        setNavActiveStepIndex(0);
        const newCoords = (res.primary_route.geojson?.geometry?.coordinates as [number, number][]) || [];
        setNavRemainingCoords(newCoords);
        setNavTraversedCoords([[offLon, offLat]]);
        setSimProgressPct(0);
        setTotalRemainingDistance(res.primary_route.distance_m);
        setTotalRemainingDuration(res.primary_route.travel_time_s);
        navigationVoice.speak(`New route calculated. In 100 meters, ${newSteps[0]?.instruction || 'proceed'}`);
      }
    });
  };

  useEffect(() => {
    if (!isNavigating || !isSimPlaying || isLiveGps) return;

    const intervalMs = 60;
    const stepDuration = Math.max(20, (activeNavRoute?.travel_time_s || 120) / 10);
    const pctIncrement = (100 / (stepDuration * (1000 / intervalMs))) * simSpeedMultiplier;

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

  // Selected Origin and Destination Waypoint Lookups
  const currentOrigin = landmarks.find(l => l.id === selectedOriginId);
  const currentDestination = landmarks.find(l => l.id === selectedDestinationId);
  const originCoords: [number, number] | null = currentOrigin ? [currentOrigin.lat, currentOrigin.lon] : null;
  const destinationCoords: [number, number] | null = currentDestination ? [currentDestination.lat, currentDestination.lon] : null;

  return (
    <div className="relative flex flex-col h-[calc(100vh-4rem)] bg-slate-950 text-slate-100 overflow-hidden">
      
      {/* Top HUD Telemetry Bar (21st.dev style) */}
      <div className="h-12 border-b border-slate-800/80 bg-slate-900/70 backdrop-blur-md px-4 flex items-center justify-between z-20">
        <div className="flex items-center space-x-6">
          <div className="flex items-center space-x-2">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_#34d399]" />
            <span className="text-xs font-mono-num font-bold text-slate-200">
              HYDRODYNAMIC ENGINE: T+{currentTimeStep}m
            </span>
          </div>

          <div className="hidden sm:flex items-center space-x-2 text-xs font-mono-num text-slate-400">
            <span>PEAK INUNDATION:</span>
            <span className={`font-bold ${
              (currentSummary?.max_depth_m || 0) > 0.3 ? 'text-red-400' : 'text-cyan-400'
            }`}>
              {currentSummary ? `${currentSummary.max_depth_m.toFixed(2)}m` : '0.23m'}
            </span>
          </div>

          <div className="hidden md:flex items-center space-x-2 text-xs font-mono-num text-slate-400">
            <span>SURFACE WATER VOLUME:</span>
            <span className="text-slate-200">
              {currentSummary ? `${Math.round(currentSummary.surface_water_volume_m3).toLocaleString()} m³` : '12,055 m³'}
            </span>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          {/* Simulation & Live Radar Trigger Button */}
          <button
            onClick={() => setIsSimModalOpen(true)}
            className="flex items-center space-x-2 px-3 py-1.5 rounded-xl border border-cyan-500/40 bg-gradient-to-r from-cyan-950/90 to-blue-950/90 hover:from-cyan-900/90 hover:to-blue-900/90 text-cyan-300 text-xs font-semibold shadow-sm shadow-cyan-950/60 cursor-pointer transition-all active:scale-95 group"
          >
            <Radio className="h-3.5 w-3.5 text-cyan-400 group-hover:animate-pulse" />
            <span className="font-mono-num font-bold">SIMULATION / LIVE</span>
            <span className="px-1.5 py-0.5 rounded bg-cyan-500/20 text-[10px] text-cyan-300 border border-cyan-500/30 uppercase">
              {floodOverview?.scenario || 'HEAVY'}
            </span>
            <Sliders className="h-3 w-3 text-slate-400 group-hover:text-cyan-300 ml-0.5" />
          </button>

          {/* Traffic Mode Quick Toggle in HUD */}
          <button
            onClick={() => {
              const nextMode = trafficMode === 'peak_monsoon' ? 'live' : 'peak_monsoon';
              setTrafficMode(nextMode);
              if (routeResult) {
                triggerRouteCalculation(selectedOriginId, selectedDestinationId, selectedVehicle, currentTimeStep, nextMode);
              }
            }}
            className={`hidden lg:flex items-center space-x-2 px-3 py-1.5 rounded-xl border text-xs font-semibold cursor-pointer transition-all active:scale-95 ${
              trafficMode === 'peak_monsoon'
                ? 'border-amber-500/50 bg-gradient-to-r from-amber-950/80 to-slate-900/90 text-amber-300 shadow-sm shadow-amber-950/50'
                : 'border-cyan-500/40 bg-gradient-to-r from-cyan-950/80 to-slate-900/90 text-cyan-300 shadow-sm shadow-cyan-950/50'
            }`}
            title="Toggle between Busy Day (Monsoon Rush Hour) bottlenecks and Real-Time TomTom satellite traffic"
          >
            <span className={`h-2 w-2 rounded-full ${trafficMode === 'peak_monsoon' ? 'bg-amber-400 animate-pulse' : 'bg-cyan-400'}`} />
            <span className="font-mono-num font-bold">
              {trafficMode === 'peak_monsoon' ? 'BUSY DAY TRAFFIC' : 'TOMTOM LIVE'}
            </span>
            <span className={`px-1.5 py-0.5 rounded text-[9px] font-mono uppercase ${
              trafficMode === 'peak_monsoon' ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' : 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
            }`}>
              {trafficMode === 'peak_monsoon' ? 'MONSOON PEAK' : 'LIVE FEED'}
            </span>
          </button>

          {/* Direct City Context Switcher in HUD */}
          {onCityChange && (
            <div className="flex items-center bg-slate-950/80 p-0.5 rounded-lg border border-slate-800 shadow-inner">
              <button
                onClick={() => onCityChange('mumbai')}
                className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-all cursor-pointer flex items-center space-x-1.5 ${
                  currentCity.toLowerCase() === 'mumbai'
                    ? 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-sm shadow-cyan-500/30'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <span className={`h-1.5 w-1.5 rounded-full ${currentCity.toLowerCase() === 'mumbai' ? 'bg-white' : 'bg-slate-500'}`} />
                <span>Mumbai (BKC)</span>
              </button>
              <button
                onClick={() => onCityChange('kolkata')}
                className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-all cursor-pointer flex items-center space-x-1.5 ${
                  currentCity.toLowerCase() === 'kolkata'
                    ? 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-sm shadow-cyan-500/30'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <span className={`h-1.5 w-1.5 rounded-full ${currentCity.toLowerCase() === 'kolkata' ? 'bg-white' : 'bg-slate-500'}`} />
                <span>Kolkata (Bypass)</span>
              </button>
            </div>
          )}

          <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full border text-xs font-mono-num bg-slate-900/80 border-slate-700">
            <span className={`h-2 w-2 rounded-full ${
              wsStatus === 'connected' 
                ? 'bg-emerald-400 animate-pulse shadow-[0_0_8px_#34d399]' 
                : wsStatus === 'connecting' 
                ? 'bg-amber-400 animate-ping' 
                : 'bg-slate-500'
            }`} />
            <span className="text-slate-200 font-semibold">
              {wsStatus === 'connected' ? 'LIVE WS: STREAMING' : wsStatus === 'connecting' ? 'WS: CONNECTING...' : 'OFFLINE'}
            </span>
          </div>

          <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-red-500/10 border border-red-500/30 text-red-400 text-xs font-mono-num">
            <AlertTriangle className="h-3.5 w-3.5" />
            <span>
              {currentSummary ? `${currentSummary.flooded_cells_30cm} SEVERE CELLS (>0.3m)` : '0 SEVERE'}
            </span>
          </div>

          <div className="hidden lg:flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 text-xs font-mono-num">
            <Activity className="h-3.5 w-3.5" />
            <span>CAUTION CELLS (&gt;0.15m): {currentSummary?.flooded_cells_15cm || 30}</span>
          </div>
        </div>
      </div>

      {/* Main Workspace Grid */}
      <div className="relative flex-1 flex overflow-hidden">
        
        {/* Left Floating Tool Palette (Resizable) */}
        <aside
          style={{ width: `${leftPanelWidth}px` }}
          className="relative shrink-0 border-r border-slate-800/80 bg-slate-950/85 backdrop-blur-xl p-4 flex flex-col justify-between overflow-y-auto z-10"
        >
          <div className="space-y-5">
            
            {/* City Selector Box */}
            {onCityChange && (
              <div className="p-3 rounded-2xl bg-slate-900/70 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between text-xs font-mono-num font-bold text-slate-400">
                  <span className="text-cyan-400 font-bold tracking-wider">ACTIVE CITY SECTOR</span>
                  <span className="text-[10px] text-emerald-400 uppercase font-bold">READY</span>
                </div>
                <div className="grid grid-cols-2 gap-1.5">
                  <button
                    onClick={() => onCityChange('mumbai')}
                    className={`p-2 rounded-xl border text-xs font-semibold transition-all text-center cursor-pointer ${
                      currentCity.toLowerCase() === 'mumbai'
                        ? 'bg-cyan-500/20 border-cyan-400/60 text-cyan-300 ring-1 ring-cyan-500/40 shadow-sm shadow-cyan-950'
                        : 'bg-slate-900/50 border-slate-800 text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    Mumbai (BKC)
                  </button>
                  <button
                    onClick={() => onCityChange('kolkata')}
                    className={`p-2 rounded-xl border text-xs font-semibold transition-all text-center cursor-pointer ${
                      currentCity.toLowerCase() === 'kolkata'
                        ? 'bg-cyan-500/20 border-cyan-400/60 text-cyan-300 ring-1 ring-cyan-500/40 shadow-sm shadow-cyan-950'
                        : 'bg-slate-900/50 border-slate-800 text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    Kolkata (Bypass)
                  </button>
                </div>
              </div>
            )}

            {/* Rainfall & Simulation Engine Card */}
            <div className="p-3.5 rounded-2xl bg-gradient-to-b from-slate-900/90 to-slate-950/90 border border-slate-800 space-y-3 shadow-sm">
              <div className="flex items-center justify-between text-xs font-mono-num font-bold">
                <span className="flex items-center text-cyan-400">
                  <CloudRain className="h-3.5 w-3.5 mr-1.5" />
                  RAINFALL SOURCE
                </span>
                <span className={`text-[10px] px-2 py-0.5 rounded-full border font-bold uppercase ${
                  floodOverview?.scenario === 'live'
                    ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300 animate-pulse'
                    : floodOverview?.scenario === 'historical'
                    ? 'bg-blue-500/20 border-blue-500/40 text-blue-300'
                    : 'bg-purple-500/20 border-purple-500/40 text-purple-300'
                }`}>
                  {floodOverview?.scenario === 'live' ? '⚡ LIVE NOWCAST' : floodOverview?.scenario === 'historical' ? '📅 HISTORICAL' : '🌊 STRESS TEST'}
                </span>
              </div>

              <div className="text-[11px] text-slate-300 bg-slate-950/60 p-2.5 rounded-xl border border-slate-800/80 font-mono-num space-y-1">
                <div className="flex justify-between">
                  <span className="text-slate-400">Sector:</span>
                  <span className="font-bold text-slate-200 capitalize">{currentCity}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Active Scenario:</span>
                  <span className="font-bold text-cyan-300 uppercase">{floodOverview?.scenario || 'HEAVY'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Total Rain Vol:</span>
                  <span className="font-bold text-slate-200">
                    {floodOverview ? `${Math.round(floodOverview.total_rain_volume_m3).toLocaleString()} m³` : '—'}
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-1.5">
                <button
                  disabled={isSimulating}
                  onClick={() => handleRunSimulation('live')}
                  className="p-2 rounded-xl border border-emerald-500/40 bg-emerald-950/30 hover:bg-emerald-900/40 text-emerald-300 text-xs font-semibold flex items-center justify-center space-x-1.5 cursor-pointer transition-all active:scale-95 disabled:opacity-50 shadow-sm"
                >
                  <Radio className="h-3 w-3 text-emerald-400" />
                  <span>Live Doppler</span>
                </button>
                <button
                  disabled={isSimulating}
                  onClick={() => handleRunSimulation('historical')}
                  className="p-2 rounded-xl border border-blue-500/40 bg-blue-950/30 hover:bg-blue-900/40 text-blue-300 text-xs font-semibold flex items-center justify-center space-x-1.5 cursor-pointer transition-all active:scale-95 disabled:opacity-50 shadow-sm"
                >
                  <Calendar className="h-3 w-3 text-blue-400" />
                  <span>Historic Storm</span>
                </button>
              </div>

              <button
                onClick={() => setIsSimModalOpen(true)}
                className="w-full py-2 px-3 rounded-xl border border-slate-700/80 bg-slate-800/50 hover:bg-slate-800 text-slate-200 text-xs font-medium flex items-center justify-between cursor-pointer transition-all group"
              >
                <span className="flex items-center space-x-1.5">
                  <Sliders className="h-3.5 w-3.5 text-cyan-400 group-hover:rotate-45 transition-transform" />
                  <span>Configure Simulation...</span>
                </span>
                <ChevronRight className="h-3.5 w-3.5 text-slate-400 group-hover:translate-x-0.5 transition-transform" />
              </button>
            </div>

            {/* GIS Layers Switcher */}
            <div>
              <div className="flex items-center justify-between mb-2.5 text-xs font-mono-num font-bold text-slate-400 tracking-wider">
                <span className="flex items-center">
                  <Layers className="h-3.5 w-3.5 mr-1.5 text-cyan-400" />
                  GIS SPATIAL LAYERS
                </span>
              </div>

              <div className="space-y-2">
                <button
                  onClick={() => setShowFloodHeatmap(!showFloodHeatmap)}
                  className={`w-full flex items-center justify-between p-2.5 rounded-xl border text-xs font-medium transition-all cursor-pointer ${
                    showFloodHeatmap
                      ? 'bg-cyan-950/40 border-cyan-500/40 text-cyan-300 shadow-sm shadow-cyan-950'
                      : 'bg-slate-900/40 border-slate-800 text-slate-500'
                  }`}
                >
                  <span className="flex items-center space-x-2">
                    <span className="h-2 w-2 rounded-full bg-cyan-400" />
                    <span>2D Flood Depth Raster</span>
                  </span>
                  {showFloodHeatmap ? <Eye className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />}
                </button>

                <button
                  onClick={() => setShowRoadGrid(!showRoadGrid)}
                  className={`w-full flex items-center justify-between p-2.5 rounded-xl border text-xs font-medium transition-all cursor-pointer ${
                    showRoadGrid
                      ? 'bg-cyan-950/40 border-cyan-500/40 text-cyan-300 shadow-sm shadow-cyan-950'
                      : 'bg-slate-900/40 border-slate-800 text-slate-500'
                  }`}
                >
                  <span className="flex items-center space-x-2">
                    <span className="h-2 w-2 rounded-full bg-cyan-400" />
                    <span>OSM Roads ({roadSummary ? `${roadSummary.total_length_km.toFixed(0)}km` : '102km'})</span>
                  </span>
                  {showRoadGrid ? <Eye className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />}
                </button>

                <button
                  onClick={() => setShowHotspots(!showHotspots)}
                  className={`w-full flex items-center justify-between p-2.5 rounded-xl border text-xs font-medium transition-all cursor-pointer ${
                    showHotspots
                      ? 'bg-amber-950/40 border-amber-500/40 text-amber-300 shadow-sm shadow-amber-950'
                      : 'bg-slate-900/40 border-slate-800 text-slate-500'
                  }`}
                >
                  <span className="flex items-center space-x-2">
                    <span className="h-2 w-2 rounded-full bg-amber-400 animate-pulse" />
                    <span>Flood Elevation Hotspots</span>
                  </span>
                  {showHotspots ? <Eye className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />}
                </button>

                <button
                  onClick={() => setShowDrainagePipes(!showDrainagePipes)}
                  className={`w-full flex items-center justify-between p-2.5 rounded-xl border text-xs font-medium transition-all cursor-pointer ${
                    showDrainagePipes
                      ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300'
                      : 'bg-slate-900/40 border-slate-800 text-slate-500'
                  }`}
                >
                  <span className="flex items-center space-x-2">
                    <span className="h-2 w-2 rounded-full bg-emerald-400" />
                    <span>Subterranean Drainage Pipes</span>
                  </span>
                  {showDrainagePipes ? <Eye className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />}
                </button>

                <button
                  onClick={() => setShowDemTerrain(!showDemTerrain)}
                  className={`w-full flex items-center justify-between p-2.5 rounded-xl border text-xs font-medium transition-all cursor-pointer ${
                    showDemTerrain
                      ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300 shadow-sm shadow-emerald-950'
                      : 'bg-slate-900/40 border-slate-800 text-slate-500'
                  }`}
                >
                  <span className="flex items-center space-x-2">
                    <Mountain className="h-3.5 w-3.5 text-emerald-400" />
                    <span>DEM Terrain Elevation (3D Relief)</span>
                  </span>
                  {showDemTerrain ? <Eye className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />}
                </button>

                <div className="space-y-1.5">
                  <button
                    onClick={() => setShowTrafficLayer(!showTrafficLayer)}
                    className={`w-full flex items-center justify-between p-2.5 rounded-xl border text-xs font-medium transition-all cursor-pointer ${
                      showTrafficLayer
                        ? 'bg-amber-950/40 border-amber-500/40 text-amber-300 shadow-sm shadow-amber-950'
                        : 'bg-slate-900/40 border-slate-800 text-slate-500'
                    }`}
                  >
                    <span className="flex items-center space-x-2">
                      <span className={`h-2 w-2 rounded-full ${showTrafficLayer ? 'bg-amber-400 animate-pulse' : 'bg-slate-500'}`} />
                      <span>Traffic Flow ({trafficMode === 'peak_monsoon' ? 'Busy Day Simulation' : 'TomTom Live'})</span>
                    </span>
                    {showTrafficLayer ? <Eye className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />}
                  </button>

                  {showTrafficLayer && (
                    <div className="grid grid-cols-2 gap-1 p-1 bg-slate-950/90 rounded-xl border border-slate-800 text-[10px] font-mono-num">
                      <button
                        onClick={() => {
                          setTrafficMode('peak_monsoon');
                          if (routeResult) triggerRouteCalculation(selectedOriginId, selectedDestinationId, selectedVehicle, currentTimeStep, 'peak_monsoon');
                        }}
                        className={`py-1 px-1.5 rounded-lg text-center transition-all cursor-pointer ${
                          trafficMode === 'peak_monsoon'
                            ? 'bg-amber-500/20 text-amber-300 font-bold border border-amber-500/40 shadow-sm'
                            : 'text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        🚗 Busy Monsoon
                      </button>
                      <button
                        onClick={() => {
                          setTrafficMode('live');
                          if (routeResult) triggerRouteCalculation(selectedOriginId, selectedDestinationId, selectedVehicle, currentTimeStep, 'live');
                        }}
                        className={`py-1 px-1.5 rounded-lg text-center transition-all cursor-pointer ${
                          trafficMode === 'live'
                            ? 'bg-cyan-500/20 text-cyan-300 font-bold border border-cyan-500/40 shadow-sm'
                            : 'text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        📡 TomTom Live
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Depth & DEM Legend */}
            <div className="p-3.5 rounded-2xl bg-slate-900/60 border border-slate-800/80 space-y-3">
              <div>
                <span className="text-[11px] font-mono-num font-bold text-slate-400 block mb-1.5">
                  HYDRODYNAMIC DEPTH ({currentCity.toLowerCase() === 'kolkata' ? '0–9cm Delta Scale' : '0–70cm Urban Scale'})
                </span>
                <div className="h-2.5 w-full rounded-full bg-gradient-to-r from-cyan-400 via-sky-500 via-indigo-500 via-amber-400 to-rose-600 mb-1.5 shadow-inner" />
                <div className="flex justify-between text-[10px] font-mono-num text-slate-400">
                  {currentCity.toLowerCase() === 'kolkata' ? (
                    <>
                      <span>0cm (Dry)</span>
                      <span className="text-cyan-300">1.5cm</span>
                      <span className="text-indigo-400">3.5cm</span>
                      <span className="text-amber-400">6cm</span>
                      <span className="text-rose-400">&gt;8cm</span>
                    </>
                  ) : (
                    <>
                      <span>0.00m</span>
                      <span className="text-cyan-300">0.08m</span>
                      <span className="text-indigo-400">0.20m</span>
                      <span className="text-amber-400">0.35m</span>
                      <span className="text-rose-400">&gt;0.50m</span>
                    </>
                  )}
                </div>
              </div>

              {showDemTerrain && (
                <div className="pt-2 border-t border-slate-800/60">
                  <span className="text-[11px] font-mono-num font-bold text-emerald-400 flex items-center space-x-1 mb-1.5">
                    <Mountain className="h-3 w-3" />
                    <span>DEM HYPSOMETRIC TOPOGRAPHY</span>
                  </span>
                  <div className="h-2.5 w-full rounded-full bg-gradient-to-r from-emerald-600 via-lime-500 via-amber-500 via-orange-800 to-slate-100 mb-1.5 shadow-inner" />
                  <div className="flex justify-between text-[10px] font-mono-num text-slate-400">
                    <span className="text-emerald-400">Low Basin (&lt;3m)</span>
                    <span className="text-amber-400">Terrace (5-10m)</span>
                    <span className="text-slate-200">Ridge (&gt;15m)</span>
                  </div>
                </div>
              )}
            </div>

            {/* Transit / Evacuation Profile Selector */}
            <div>
              <span className="text-xs font-mono-num font-bold text-slate-400 tracking-wider block mb-2 flex items-center justify-between">
                <span>TRANSIT CLEARANCE</span>
                <span className="text-cyan-400 font-normal">Calibrated</span>
              </span>
              <div className="grid grid-cols-5 gap-1 p-1 rounded-xl bg-slate-900/80 border border-slate-800">
                <button
                  onClick={() => setSelectedVehicle('pedestrian')}
                  className={`py-1.5 text-center text-[10px] font-medium rounded-lg transition-all cursor-pointer ${
                    selectedVehicle === 'pedestrian'
                      ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <User className="h-3.5 w-3.5 mx-auto mb-0.5" />
                  <span>Foot (12cm)</span>
                </button>
                <button
                  onClick={() => setSelectedVehicle('bike')}
                  className={`py-1.5 text-center text-[10px] font-medium rounded-lg transition-all cursor-pointer ${
                    selectedVehicle === 'bike'
                      ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Bike className="h-3.5 w-3.5 mx-auto mb-0.5" />
                  <span>Bike (18cm)</span>
                </button>
                <button
                  onClick={() => setSelectedVehicle('car')}
                  className={`py-1.5 text-center text-[10px] font-medium rounded-lg transition-all cursor-pointer ${
                    selectedVehicle === 'car'
                      ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Car className="h-3.5 w-3.5 mx-auto mb-0.5" />
                  <span>Car (30cm)</span>
                </button>
                <button
                  onClick={() => setSelectedVehicle('ambulance')}
                  className={`py-1.5 text-center text-[10px] font-medium rounded-lg transition-all cursor-pointer ${
                    selectedVehicle === 'ambulance'
                      ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Activity className="h-3.5 w-3.5 mx-auto mb-0.5" />
                  <span>Ambulance</span>
                </button>
                <button
                  onClick={() => setSelectedVehicle('rescue')}
                  className={`py-1.5 text-center text-[10px] font-medium rounded-lg transition-all cursor-pointer ${
                    selectedVehicle === 'rescue'
                      ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Truck className="h-3.5 w-3.5 mx-auto mb-0.5" />
                  <span>Truck (60cm)</span>
                </button>
              </div>
            </div>

          </div>

          <div className="pt-4 border-t border-slate-800 text-[11px] font-mono-num text-slate-500">
            Phase 5: Subterranean Drainage Diagnostics & Live WebSockets
          </div>

          {/* Vertical Resize Drag Handle */}
          <div
            onMouseDown={onLeftDragStart}
            title="Drag to resize panel width"
            className="absolute top-0 right-0 w-2.5 h-full cursor-col-resize hover:bg-cyan-500/40 active:bg-cyan-400 transition-colors z-20 group flex items-center justify-center select-none"
          >
            <div className="w-0.5 h-10 rounded-full bg-slate-700/80 group-hover:bg-cyan-400 group-active:bg-cyan-300 transition-colors" />
          </div>
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
            originName={currentOrigin?.name}
            destinationName={currentDestination?.name}
            onDrainageSummaryLoaded={(surcharges) => setSurchargingCount(surcharges)}
            drainageRefreshKey={drainageRefreshKey}
            simulationKey={simulationKey}
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
              landmarks={landmarks}
              selectedOriginId={selectedOriginId}
              selectedDestinationId={selectedDestinationId}
              onSelectOriginId={(id) => { setSelectedOriginId(id); setRouteResult(null); setRouteAlternatives([]); }}
              onSelectDestinationId={(id) => { setSelectedDestinationId(id); setRouteResult(null); setRouteAlternatives([]); }}
              selectedVehicle={selectedVehicle}
              onSelectVehicle={(v) => { setSelectedVehicle(v); setRouteResult(null); setRouteAlternatives([]); }}
              onCalculateRoute={() => triggerRouteCalculation()}
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
            />
          )}
        </main>

      </div>

      {/* Bottom Temporal Timeline Scrubber Bar — resizable by dragging the top handle */}
      <footer
        style={{ height: footerHeight }}
        className="relative border-t border-slate-800/80 bg-slate-950/90 backdrop-blur-xl px-4 sm:px-6 flex flex-col justify-center z-20 overflow-hidden transition-none"
      >
        {/* ▲ Drag handle — grab and drag up/down to resize */}
        <div
          onMouseDown={onFooterDragStart}
          className="absolute left-0 right-0 top-0 h-1.5 cursor-ns-resize group flex items-center justify-center"
          title="Drag to resize"
        >
          <div className="w-10 h-0.5 rounded-full bg-slate-700 group-hover:bg-cyan-500 transition-colors" />
        </div>

        {/* Inner row — same layout as before */}
        <div className="flex flex-wrap items-center justify-between gap-y-2">
        <div className="flex items-center space-x-3">
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className={`flex h-10 w-10 items-center justify-center rounded-xl font-bold shadow-lg active:scale-95 transition-all cursor-pointer ${
              isPlaying 
                ? 'bg-amber-400 text-slate-950 shadow-amber-400/25 hover:bg-amber-300' 
                : 'bg-cyan-500 text-slate-950 shadow-cyan-500/25 hover:bg-cyan-400'
            }`}
          >
            {isPlaying ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5 ml-0.5" />}
          </button>

          <button
            onClick={() => {
              setIsPlaying(false);
              setCurrentTimeStep(0);
            }}
            className="flex h-10 w-10 items-center justify-center rounded-xl border border-slate-800 bg-slate-900 text-slate-300 hover:bg-slate-800 active:scale-95 transition-all cursor-pointer"
          >
            <RotateCcw className="h-4 w-4" />
          </button>

          <div className="flex flex-col ml-2">
            <span className="text-[10px] font-mono-num text-slate-400 uppercase tracking-wider">
              FORECAST HORIZON
            </span>
            <span className="text-sm font-bold font-mono-num text-white">
              T+{currentTimeStep}m <span className="text-xs font-normal text-cyan-400">({currentTimeStep * 60}s)</span>
            </span>
          </div>
        </div>

        {/* Discrete Horizon Step Buttons & Range Slider — scrollable when narrow */}
        <div className="flex-1 min-w-0 mx-4 sm:mx-8 overflow-x-auto scrollbar-thin scrollbar-track-slate-900 scrollbar-thumb-slate-700">
          <div className="min-w-[320px] flex flex-col justify-center">
            <div className="flex justify-between text-[11px] font-mono-num text-slate-400 mb-1.5">
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
                  T+{h}m
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
              className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400"
            />
          </div>
        </div>

          {/* Action Info & dBZ Status */}
          <div className="hidden lg:flex items-center space-x-3 text-xs font-mono-num text-slate-400">
            <span className="flex h-2 w-2 rounded-full bg-cyan-400 animate-ping" />
            <span>RADAR dBZ: OPTICAL FLOW SYNC</span>
          </div>

        </div>{/* end inner flex-wrap row */}
      </footer>

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
