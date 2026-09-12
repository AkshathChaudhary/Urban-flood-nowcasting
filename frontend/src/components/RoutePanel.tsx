import React from 'react';
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
  GitFork
} from 'lucide-react';
import type { Landmark, RouteResult } from '../services/api';

interface RoutePanelProps {
  landmarks: Landmark[];
  selectedOriginId: string;
  selectedDestinationId: string;
  onSelectOriginId: (id: string) => void;
  onSelectDestinationId: (id: string) => void;
  selectedVehicle: 'car' | 'ambulance' | 'rescue';
  onSelectVehicle: (v: 'car' | 'ambulance' | 'rescue') => void;
  onCalculateRoute: () => void;
  isCalculating: boolean;
  routeResult: RouteResult | null;
  alternatives?: RouteResult[];
  activeRouteIndex?: number;
  onSelectRouteIndex?: (idx: number) => void;
  isOpen: boolean;
  onToggleOpen: () => void;
  timeHorizon: number;
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
}) => {
  if (!isOpen) {
    return (
      <button
        onClick={onToggleOpen}
        className="absolute top-4 right-4 z-20 flex items-center space-x-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-semibold text-xs shadow-xl shadow-cyan-500/25 hover:brightness-110 active:scale-95 transition-all cursor-pointer ring-1 ring-white/20"
      >
        <Navigation className="h-4 w-4" />
        <span>Resilient Evacuation Router</span>
      </button>
    );
  }

  // Active route being inspected (0 is primary safest, 1+ is alternative)
  const currentDisplayedRoute: RouteResult | null = 
    activeRouteIndex === 0 
      ? routeResult 
      : alternatives[activeRouteIndex - 1] || routeResult;

  return (
    <div className="absolute top-4 right-4 z-20 w-84 sm:w-96 glass-panel rounded-3xl border border-slate-800/90 shadow-2xl p-5 flex flex-col max-h-[calc(100vh-8rem)] overflow-y-auto backdrop-blur-2xl">
      
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
          <label className="text-[11px] font-mono-num font-bold text-slate-400 block mb-1 flex items-center justify-between">
            <span className="flex items-center">
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 mr-1.5 shadow-[0_0_8px_#34d399]" />
              ORIGIN WAYPOINT (POINT A)
            </span>
            <span className="text-[10px] text-emerald-400 font-normal">Marked on map</span>
          </label>
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

      {/* Vehicle Profile Selection */}
      <div className="mb-4">
        <span className="text-[11px] font-mono-num font-bold text-slate-400 block mb-1.5">
          VEHICLE WADING CLEARANCE TOLERANCE
        </span>
        <div className="grid grid-cols-3 gap-1.5 p-1 rounded-xl bg-slate-900/80 border border-slate-800">
          <button
            onClick={() => onSelectVehicle('car')}
            className={`py-1.5 text-center text-xs rounded-lg transition-all cursor-pointer ${
              selectedVehicle === 'car'
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Car className="h-3.5 w-3.5 mx-auto mb-0.5" />
            <span>Car (30cm)</span>
          </button>

          <button
            onClick={() => onSelectVehicle('ambulance')}
            className={`py-1.5 text-center text-xs rounded-lg transition-all cursor-pointer ${
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
            className={`py-1.5 text-center text-xs rounded-lg transition-all cursor-pointer ${
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

          <div className="grid grid-cols-2 gap-2 text-xs font-mono-num">
            <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-850">
              <div className="text-[10px] text-slate-400 flex items-center">
                <Clock className="h-3 w-3 mr-1 text-cyan-400" />
                EST. DURATION
              </div>
              <div className="text-base font-bold text-white mt-0.5">
                {currentDisplayedRoute.travel_time_min.toFixed(1)} <span className="text-xs font-normal text-slate-400">min</span>
              </div>
            </div>

            <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-850">
              <div className="text-[10px] text-slate-400 flex items-center">
                <Gauge className="h-3 w-3 mr-1 text-teal-400" />
                TOTAL DISTANCE
              </div>
              <div className="text-base font-bold text-white mt-0.5">
                {(currentDisplayedRoute.distance_m / 1000).toFixed(2)} <span className="text-xs font-normal text-slate-400">km</span>
              </div>
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
        </div>
      )}

    </div>
  );
};
