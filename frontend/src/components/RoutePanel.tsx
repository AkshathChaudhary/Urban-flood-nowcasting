import React, { useState } from 'react';
import { 
  Navigation, 
  Car, 
  Truck, 
  Activity, 
  AlertTriangle, 
  Clock, 
  Gauge, 
  ChevronDown, 
  X, 
  ShieldCheck, 
  GitFork,
  User,
  Bike,
  MapPin,
  Info,
  Compass,
  Zap
} from 'lucide-react';
import type { Landmark, RouteResult } from '../services/api';

export type TransportMode = 'pedestrian' | 'bike' | 'car' | 'suv' | 'ambulance' | 'rescue';

interface RoutePanelProps {
  landmarks: Landmark[];
  selectedOriginId: string;
  selectedDestinationId: string;
  onSelectOriginId: (id: string) => void;
  onSelectDestinationId: (id: string) => void;
  selectedVehicle: TransportMode;
  onSelectVehicle: (v: TransportMode) => void;
  onCalculateRoute: () => void;
  isCalculating: boolean;
  routeResult: RouteResult | null;
  alternatives?: RouteResult[];
  activeRouteIndex?: number;
  onSelectRouteIndex?: (idx: number) => void;
  isOpen: boolean;
  onToggleOpen: () => void;
  timeHorizon: number;
  onStartNavigation?: () => void;
  trafficMode?: 'peak_monsoon' | 'live';
  onSelectTrafficMode?: (mode: 'peak_monsoon' | 'live') => void;
  userLocation?: [number, number] | null;
  onUseLiveLocation?: () => void;
  onTestCorridorPipeline?: (src: string, dst: string) => void;
}

export const RoutePanel: React.FC<RoutePanelProps> = ({
  landmarks,
  selectedOriginId,
  selectedDestinationId,
  onSelectOriginId,
  onSelectDestinationId,
  selectedVehicle,
  onSelectVehicle,
  onCalculateRoute,
  isCalculating,
  routeResult,
  alternatives = [],
  activeRouteIndex = 0,
  onSelectRouteIndex,
  isOpen,
  onToggleOpen,
  timeHorizon,
  onStartNavigation,
  trafficMode = 'peak_monsoon',
  onSelectTrafficMode,
  userLocation,
  onUseLiveLocation,
  onTestCorridorPipeline,
}) => {
  const [showCorridorTool, setShowCorridorTool] = useState<boolean>(false);
  const [corridorSrc, setCorridorSrc] = useState<string>('Kestopur');
  const [corridorDst, setCorridorDst] = useState<string>('Ruby Hospital');

  if (!isOpen) {
    return (
      <button
        onClick={onToggleOpen}
        className="absolute top-4 right-4 z-20 flex items-center space-x-2 px-3.5 py-2 rounded-xl bg-slate-950/85 border border-cyan-500/40 text-cyan-300 font-mono text-xs font-semibold shadow-xl backdrop-blur-md hover:bg-slate-900/90 active:scale-95 transition-all cursor-pointer ring-1 ring-cyan-500/20"
      >
        <Navigation className="h-3.5 w-3.5 text-cyan-400" />
        <span>Evacuation Router</span>
        {routeResult && (
          <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 text-[10px] font-bold border border-emerald-500/30">
            {(routeResult.distance_m / 1000).toFixed(1)} km
          </span>
        )}
      </button>
    );
  }

  // Active route being inspected (0 is primary safest, 1+ is alternative)
  const currentDisplayedRoute: RouteResult | null = 
    activeRouteIndex === 0 
      ? routeResult 
      : alternatives[activeRouteIndex - 1] || routeResult;

  return (
    <div className="absolute top-4 right-4 z-20 w-80 sm:w-96 rounded-2xl bg-slate-950/95 border border-slate-800/90 shadow-2xl p-4 flex flex-col max-h-[calc(100vh-6rem)] overflow-y-auto backdrop-blur-2xl animate-in slide-in-from-right-4 duration-200">
      
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-800/80 mb-3">
        <div className="flex items-center space-x-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
            <Navigation className="h-4 w-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white tracking-tight">
              EVACUATION ROUTER
            </h3>
            <span className="text-[10px] font-mono-num text-cyan-400 font-medium">
              Multi-Route Hydrodynamic Risk Solver
            </span>
          </div>
        </div>

        <button
          onClick={onToggleOpen}
          className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Origin & Destination Selectors */}
      <div className="space-y-3 mb-4">
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-[11px] font-mono-num font-bold text-slate-400 flex items-center">
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 mr-1.5 shadow-[0_0_8px_#34d399]" />
              ORIGIN WAYPOINT (POINT A)
            </label>
            {onUseLiveLocation && (
              <button
                type="button"
                onClick={onUseLiveLocation}
                className="flex items-center space-x-1 text-[10px] font-mono text-cyan-400 hover:text-cyan-300 transition-colors cursor-pointer px-1.5 py-0.5 rounded bg-cyan-950/60 border border-cyan-800/50 hover:bg-cyan-900/60"
                title={userLocation ? `Current GPS: ${userLocation[0].toFixed(4)}, ${userLocation[1].toFixed(4)}` : "Use current GPS position as origin"}
              >
                <MapPin className="h-3 w-3 text-cyan-400 animate-pulse" />
                <span>{userLocation ? 'Snap to GPS' : 'Use My GPS'}</span>
              </button>
            )}
          </div>
          <div className="relative">
            <select
              value={selectedOriginId}
              onChange={(e) => onSelectOriginId(e.target.value)}
              className="w-full bg-slate-900/90 border border-slate-700/80 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-400 appearance-none cursor-pointer"
            >
              {landmarks.map((lm) => (
                <option key={`orig-${lm.id}`} value={lm.id} className="bg-slate-900 text-slate-200">
                  {lm.name} ({lm.elevation_m}m)
                </option>
              ))}
            </select>
            <ChevronDown className="absolute right-3 top-2.5 h-3.5 w-3.5 text-slate-400 pointer-events-none" />
          </div>
        </div>

        <div>
          <label className="text-[11px] font-mono-num font-bold text-slate-400 block mb-1 flex items-center justify-between">
            <span className="flex items-center">
              <span className="h-2.5 w-2.5 rounded-full bg-red-400 mr-1.5 shadow-[0_0_8px_#f87171]" />
              DESTINATION WAYPOINT (POINT B)
            </span>
            <span className="text-[10px] text-red-400 font-normal">Highlighted on map</span>
          </label>
          <div className="relative">
            <select
              value={selectedDestinationId}
              onChange={(e) => onSelectDestinationId(e.target.value)}
              className="w-full bg-slate-900/90 border border-slate-700/80 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-400 appearance-none cursor-pointer"
            >
              {landmarks.map((lm) => (
                <option key={`dest-${lm.id}`} value={lm.id} className="bg-slate-900 text-slate-200">
                  {lm.name} ({lm.elevation_m}m)
                </option>
              ))}
            </select>
            <ChevronDown className="absolute right-3 top-2.5 h-3.5 w-3.5 text-slate-400 pointer-events-none" />
          </div>
        </div>
      </div>

      {/* Vehicle Profile Selection (All 6 Classes with Real Clearance Specs) */}
      <div className="mb-4">
        <span className="text-[11px] font-mono-num font-bold text-slate-400 block mb-1.5 flex items-center justify-between">
          <span>VEHICLE WADING CLEARANCE TOLERANCE</span>
          <span className="text-[10px] text-cyan-400 font-mono">6 Modes</span>
        </span>
        <div className="grid grid-cols-3 gap-1.5 p-1 rounded-xl bg-slate-900/80 border border-slate-800">
          <button
            onClick={() => onSelectVehicle('pedestrian')}
            className={`py-1.5 text-center text-[10px] rounded-lg transition-all cursor-pointer ${
              selectedVehicle === 'pedestrian'
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <User className="h-3.5 w-3.5 mx-auto mb-0.5" />
            <span>Foot (12cm)</span>
          </button>

          <button
            onClick={() => onSelectVehicle('bike')}
            className={`py-1.5 text-center text-[10px] rounded-lg transition-all cursor-pointer ${
              selectedVehicle === 'bike'
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Bike className="h-3.5 w-3.5 mx-auto mb-0.5" />
            <span>Bike (18cm)</span>
          </button>

          <button
            onClick={() => onSelectVehicle('car')}
            className={`py-1.5 text-center text-[10px] rounded-lg transition-all cursor-pointer ${
              selectedVehicle === 'car'
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Car className="h-3.5 w-3.5 mx-auto mb-0.5" />
            <span>Car (30cm)</span>
          </button>

          <button
            onClick={() => onSelectVehicle('suv')}
            className={`py-1.5 text-center text-[10px] rounded-lg transition-all cursor-pointer ${
              selectedVehicle === 'suv'
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Car className="h-3.5 w-3.5 mx-auto mb-0.5 text-teal-400" />
            <span>SUV (45cm)</span>
          </button>

          <button
            onClick={() => onSelectVehicle('ambulance')}
            className={`py-1.5 text-center text-[10px] rounded-lg transition-all cursor-pointer ${
              selectedVehicle === 'ambulance'
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Activity className="h-3.5 w-3.5 mx-auto mb-0.5 text-cyan-400" />
            <span>Ambulance</span>
          </button>

          <button
            onClick={() => onSelectVehicle('rescue')}
            className={`py-1.5 text-center text-[10px] rounded-lg transition-all cursor-pointer ${
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

      {/* Traffic Congestion Profile Selector */}
      <div className="mb-4 p-3 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-2">
        <div className="flex items-center justify-between text-[11px] font-mono-num font-bold text-slate-300">
          <span className="flex items-center space-x-1.5">
            <span className={`h-2 w-2 rounded-full ${trafficMode === 'peak_monsoon' ? 'bg-amber-400 animate-pulse' : 'bg-cyan-400'}`} />
            <span>TRAFFIC CONGESTION PROFILE</span>
          </span>
          <span className="text-[10px] text-amber-400 font-normal">Multi-Modal</span>
        </div>

        <div className="grid grid-cols-2 gap-1.5 p-1 bg-slate-950/80 rounded-xl border border-slate-800/80 text-xs">
          <button
            type="button"
            onClick={() => onSelectTrafficMode && onSelectTrafficMode('peak_monsoon')}
            className={`py-2 px-2 rounded-lg flex flex-col items-center justify-center text-center transition-all cursor-pointer ${
              trafficMode === 'peak_monsoon'
                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/50 font-bold shadow-md shadow-amber-950/50'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <div className="flex items-center space-x-1 mb-0.5">
              <span className="h-1.5 w-1.5 rounded-full bg-red-400" />
              <span className="text-[11px]">Busy Day Peak</span>
            </div>
            <span className="text-[9px] text-amber-400/90 font-mono">Monsoon Bottlenecks</span>
          </button>

          <button
            type="button"
            onClick={() => onSelectTrafficMode && onSelectTrafficMode('live')}
            className={`py-2 px-2 rounded-lg flex flex-col items-center justify-center text-center transition-all cursor-pointer ${
              trafficMode === 'live'
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/50 font-bold shadow-md shadow-cyan-950/50'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <div className="flex items-center space-x-1 mb-0.5">
              <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" />
              <span className="text-[11px]">Live Real-Time</span>
            </div>
            <span className="text-[9px] text-cyan-400/90 font-mono">TomTom Live API</span>
          </button>
        </div>

        <div className="text-[10px] text-slate-400 flex items-start space-x-1.5 pt-0.5">
          <Info className="h-3 w-3 text-amber-400 shrink-0 mt-0.5" />
          <span>
            {trafficMode === 'peak_monsoon'
              ? 'Simulating monsoon gridlock bottlenecks on transit arteries to showcase dynamic flood + traffic evasion.'
              : 'Directly querying minute-by-minute live satellite traffic flow speeds via TomTom API.'}
          </span>
        </div>
      </div>

      {/* Calculate Button */}
      <button
        onClick={onCalculateRoute}
        disabled={isCalculating}
        className="w-full flex items-center justify-center space-x-2 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 via-cyan-500 to-blue-600 text-white text-xs font-bold shadow-lg shadow-cyan-500/20 hover:brightness-110 active:scale-95 transition-all cursor-pointer disabled:opacity-50 mb-4"
      >
        <Navigation className={`h-3.5 w-3.5 ${isCalculating ? 'animate-spin' : ''}`} />
        <span>{isCalculating ? 'SOLVING MULTI-ROUTE GRAPH...' : `CALCULATE SAFE ROUTES (T+${timeHorizon}m)`}</span>
      </button>

      {/* MULTI-ROUTE COMPARISON SELECTOR */}
      {routeResult && (
        <div className="mb-4 space-y-2">
          <div className="flex items-center justify-between text-[11px] font-mono-num text-slate-400">
            <span className="flex items-center space-x-1.5">
              <GitFork className="h-3.5 w-3.5 text-cyan-400" />
              <span>COMPARE ROUTES ({1 + alternatives.length} OPTIONS)</span>
            </span>
            <span className="text-cyan-400">Click to inspect</span>
          </div>

          {/* Primary Recommended Route Card */}
          <div
            onClick={() => onSelectRouteIndex && onSelectRouteIndex(0)}
            className={`p-3 rounded-xl border transition-all cursor-pointer ${
              activeRouteIndex === 0
                ? 'bg-emerald-950/40 border-emerald-500 shadow-[0_0_12px_rgba(16,185,129,0.3)] ring-1 ring-emerald-500/50'
                : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
            }`}
          >
            <div className="flex items-center justify-between mb-1.5">
              <span className="flex items-center space-x-1.5 text-xs font-bold text-emerald-400">
                <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
                <span>★ RECOMMENDED SAFEST ROUTE</span>
              </span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-bold border border-emerald-500/30">
                SAFEST
              </span>
            </div>
            <div className="flex items-center justify-between text-xs font-mono-num text-slate-300">
              <span>{(routeResult.distance_m / 1000).toFixed(2)} km</span>
              <span>{routeResult.travel_time_min.toFixed(1)} min</span>
              <span className="text-emerald-400">Max: {(routeResult.max_flood_depth_m * 100).toFixed(0)}cm</span>
            </div>
          </div>

          {/* Alternative Detours */}
          {alternatives.map((alt, idx) => {
            const isSelected = activeRouteIndex === idx + 1;
            const borderColor = idx === 0 ? 'border-amber-500/70' : 'border-sky-500/70';
            const textColor = idx === 0 ? 'text-amber-400' : 'text-sky-400';
            const badgeBg = idx === 0 ? 'bg-amber-500/20 text-amber-300' : 'bg-sky-500/20 text-sky-300';

            return (
              <div
                key={`alt-${idx}`}
                onClick={() => onSelectRouteIndex && onSelectRouteIndex(idx + 1)}
                className={`p-3 rounded-xl border transition-all cursor-pointer ${
                  isSelected
                    ? `bg-slate-900/90 ${borderColor} shadow-lg ring-1 ring-white/20`
                    : 'bg-slate-900/60 border-slate-800/80 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className={`text-xs font-bold ${textColor}`}>
                    ALTERNATIVE DETOUR {idx + 1}
                  </span>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold border border-white/10 ${badgeBg}`}>
                    DETOUR
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs font-mono-num text-slate-300">
                  <span>{(alt.distance_m / 1000).toFixed(2)} km</span>
                  <span>{alt.travel_time_min.toFixed(1)} min</span>
                  <span className={alt.max_flood_depth_m > 0.15 ? 'text-amber-400' : 'text-emerald-400'}>
                    Max: {(alt.max_flood_depth_m * 100).toFixed(0)}cm
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Detailed Telemetry for Selected Route */}
      {currentDisplayedRoute && (
        <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-4 space-y-3">
          <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
            <span className="text-[11px] font-mono-num font-bold text-slate-400">
              {activeRouteIndex === 0 ? 'RECOMMENDED ROUTE SPECS' : `DETOUR ${activeRouteIndex} SPECS`}
            </span>
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
              currentDisplayedRoute.flood_risk === 'SAFE'
                ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 shadow-[0_0_8px_rgba(52,211,153,0.3)]'
                : 'bg-amber-500/20 text-amber-300 border-amber-500/40'
            }`}>
              {currentDisplayedRoute.flood_risk} PASSAGE
            </span>
          </div>

          {currentDisplayedRoute.advisory && (
            <div className="p-2.5 rounded-xl bg-amber-500/15 border border-amber-500/40 text-[11px] text-amber-200 font-sans flex items-start space-x-2">
              <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
              <div>
                <span className="font-bold text-amber-300">Flood Advisory:</span> {currentDisplayedRoute.advisory}
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-2 text-xs font-mono-num">
            <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-850">
              <div className="text-[10px] text-slate-400 flex items-center">
                <Clock className="h-3 w-3 mr-1 text-cyan-400" />
                EST. DURATION
              </div>
              <div className="text-base font-bold text-white mt-0.5">
                {currentDisplayedRoute.travel_time_min.toFixed(1)} <span className="text-xs font-normal text-slate-400">min</span>
              </div>
              {currentDisplayedRoute.traffic_delay_min !== undefined && currentDisplayedRoute.traffic_delay_min > 0.1 && (
                <div className="text-[10px] text-amber-400 font-semibold mt-0.5">
                  +{currentDisplayedRoute.traffic_delay_min.toFixed(1)}m delay
                </div>
              )}
            </div>

            <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-850">
              <div className="text-[10px] text-slate-400 flex items-center">
                <Gauge className="h-3 w-3 mr-1 text-teal-400" />
                TOTAL DISTANCE
              </div>
              <div className="text-base font-bold text-white mt-0.5">
                {(currentDisplayedRoute.distance_m / 1000).toFixed(2)} <span className="text-xs font-normal text-slate-400">km</span>
              </div>
              {currentDisplayedRoute.traffic_status && (
                <div className={`text-[10px] font-semibold mt-0.5 ${
                  currentDisplayedRoute.traffic_status === 'FREE_FLOW' || currentDisplayedRoute.traffic_status === 'OPTIMAL'
                    ? 'text-emerald-400' 
                    : currentDisplayedRoute.traffic_status === 'MODERATE_DELAY' 
                    ? 'text-amber-400' 
                    : 'text-rose-400'
                }`}>
                  {currentDisplayedRoute.traffic_status.replace('_', ' ')}
                </div>
              )}
            </div>

            <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-850">
              <div className="text-[10px] text-slate-400">PEAK PONDING</div>
              <div className={`text-base font-bold mt-0.5 ${
                currentDisplayedRoute.max_flood_depth_m > 0.15 ? 'text-amber-400' : 'text-emerald-400'
              }`}>
                {(currentDisplayedRoute.max_flood_depth_m * 100).toFixed(1)} <span className="text-xs font-normal text-slate-400">cm</span>
              </div>
            </div>

            <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-850">
              <div className="text-[10px] text-slate-400">ROAD SEGMENTS</div>
              <div className="text-base font-bold text-white mt-0.5">
                {currentDisplayedRoute.segment_count} <span className="text-xs font-normal text-slate-400">links</span>
              </div>
            </div>
          </div>

          {currentDisplayedRoute.roads_avoided && currentDisplayedRoute.roads_avoided.length > 0 && (
            <div className="p-2.5 rounded-xl bg-red-950/30 border border-red-500/30 text-[11px] text-red-300 font-mono-num flex items-center justify-between">
              <span className="flex items-center space-x-1.5">
                <AlertTriangle className="h-3.5 w-3.5 text-red-400" />
                <span>Avoided Inundated Road Segments:</span>
              </span>
              <span className="font-bold">{currentDisplayedRoute.roads_avoided.length} SECTIONS</span>
            </div>
          )}

          <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-[10px] text-emerald-300 font-mono-num leading-tight">
            💡 <b>Guidance:</b> {activeRouteIndex === 0 
              ? 'This route is strongly suggested as it has the lowest cumulative flood depth risk across all known road links.' 
              : 'This is a secondary detour corridor. Use caution in low-elevation depressions.'}
          </div>

          {/* 🚀 START TURN-BY-TURN HUD NAVIGATION BUTTON */}
          {onStartNavigation && (
            <div className="pt-2">
              <button
                type="button"
                onClick={onStartNavigation}
                className="w-full flex items-center justify-center space-x-2 py-3 rounded-xl bg-gradient-to-r from-emerald-500 via-cyan-500 to-blue-600 text-white font-black text-xs tracking-wider uppercase shadow-xl shadow-cyan-500/30 hover:brightness-110 active:scale-95 transition-all cursor-pointer ring-1 ring-white/30"
              >
                <Navigation className="h-4 w-4 fill-white" />
                <span>START LIVE TURN-BY-TURN HUD</span>
              </button>
            </div>
          )}
        </div>
      )}

      {/* Cross-Basin Corridor Pipeline Tool Drawer */}
      <div className="mt-4 pt-3 border-t border-slate-800/80">
        <button
          type="button"
          onClick={() => setShowCorridorTool(!showCorridorTool)}
          className="w-full flex items-center justify-between text-[11px] font-mono text-cyan-400 hover:text-cyan-300 transition-colors p-2 rounded-xl bg-slate-900/60 border border-slate-800"
        >
          <span className="flex items-center space-x-1.5">
            <Zap className="h-3.5 w-3.5 text-cyan-400" />
            <span className="font-semibold">Cross-Basin Corridor Pipeline</span>
          </span>
          <span className="text-[10px] text-slate-400">{showCorridorTool ? 'Close ▲' : 'Open ▼'}</span>
        </button>

        {showCorridorTool && (
          <div className="mt-2 p-3 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2.5 animate-in fade-in duration-150">
            <div className="text-[10px] text-slate-400">
              Directly executes the coupled 3-model hydrodynamic simulation + graph routing between any two custom corridor points.
            </div>
            <div className="space-y-1.5">
              <input
                type="text"
                value={corridorSrc}
                onChange={(e) => setCorridorSrc(e.target.value)}
                placeholder="Origin (e.g. Kestopur or BKC)"
                className="w-full px-2.5 py-1.5 text-xs rounded-lg bg-slate-950 border border-slate-800 text-slate-200 focus:outline-none focus:border-cyan-400 font-mono"
              />
              <input
                type="text"
                value={corridorDst}
                onChange={(e) => setCorridorDst(e.target.value)}
                placeholder="Destination (e.g. Ruby Hospital or Kurla)"
                className="w-full px-2.5 py-1.5 text-xs rounded-lg bg-slate-950 border border-slate-800 text-slate-200 focus:outline-none focus:border-cyan-400 font-mono"
              />
            </div>
            <button
              type="button"
              onClick={() => onTestCorridorPipeline && onTestCorridorPipeline(corridorSrc, corridorDst)}
              className="w-full flex items-center justify-center space-x-1.5 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-[11px] font-bold transition-all cursor-pointer shadow-md"
            >
              <Compass className="h-3.5 w-3.5" />
              <span>RUN 3-MODEL PIPELINE</span>
            </button>
          </div>
        )}
      </div>

    </div>
  );
};
