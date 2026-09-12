import React, { useState } from 'react';
import {
  ArrowUp,
  CornerUpLeft,
  CornerUpRight,
  RotateCcw,
  Flag,
  Volume2,
  VolumeX,
  Crosshair,
  X,
  Play,
  Pause,
  ShieldCheck,
  AlertTriangle,
  Waves,
  Clock,
  Gauge,
  Radio
} from 'lucide-react';
import type { NavigationStep, ManeuverType } from '../services/navigation';

interface NavigationHudProps {
  currentStep: NavigationStep | null;
  nextStep: NavigationStep | null;
  distanceToNextTurn_m: number;
  totalRemainingDistance_m: number;
  totalRemainingDuration_s: number;
  isSimulating: boolean;
  simProgressPct: number; // 0 to 100
  simSpeedMultiplier: number;
  isVoiceMuted: boolean;
  vehicleType: string;
  isLiveGps: boolean;
  hasGpsLock: boolean;
  onTogglePlayPause: () => void;
  onChangeSpeed: (multiplier: number) => void;
  onSeekProgress: (pct: number) => void;
  onToggleVoice: () => void;
  onRecenterCamera: () => void;
  onToggleLiveGps: () => void;
  onTriggerOffRouteSim?: () => void;
  onExitNavigation: () => void;
}

export const NavigationHud: React.FC<NavigationHudProps> = ({
  currentStep,
  nextStep,
  distanceToNextTurn_m,
  totalRemainingDistance_m,
  totalRemainingDuration_s,
  isSimulating,
  simProgressPct,
  simSpeedMultiplier,
  isVoiceMuted,
  vehicleType,
  isLiveGps,
  hasGpsLock,
  onTogglePlayPause,
  onChangeSpeed,
  onSeekProgress,
  onToggleVoice,
  onRecenterCamera,
  onToggleLiveGps,
  onTriggerOffRouteSim,
  onExitNavigation,
}) => {
  const [showSimControls] = useState<boolean>(true);

  // Helper to render maneuver icon
  const renderManeuverIcon = (maneuver: ManeuverType | undefined, size: string = 'h-7 w-7') => {
    switch (maneuver) {
      case 'turn-left':
      case 'slight-left':
        return <CornerUpLeft className={`${size} text-cyan-400`} />;
      case 'sharp-left':
        return <CornerUpLeft className={`${size} text-amber-400 rotate-[-15deg]`} />;
      case 'turn-right':
      case 'slight-right':
        return <CornerUpRight className={`${size} text-cyan-400`} />;
      case 'sharp-right':
        return <CornerUpRight className={`${size} text-amber-400 rotate-[15deg]`} />;
      case 'u-turn':
        return <RotateCcw className={`${size} text-amber-400`} />;
      case 'arrive':
        return <Flag className={`${size} text-emerald-400`} />;
      case 'straight':
      case 'depart':
      default:
        return <ArrowUp className={`${size} text-emerald-400`} />;
    }
  };

  const formatDistance = (meters: number): string => {
    if (meters >= 1000) {
      return `${(meters / 1000).toFixed(1)} km`;
    }
    return `${Math.round(meters)} m`;
  };

  const formatDuration = (seconds: number): string => {
    const mins = Math.max(1, Math.round(seconds / 60));
    if (mins >= 60) {
      const hrs = Math.floor(mins / 60);
      const remMins = mins % 60;
      return `${hrs} hr ${remMins} min`;
    }
    return `${mins} min`;
  };

  // Compute calculated arrival time
  const etaDate = new Date(Date.now() + totalRemainingDuration_s * 1000);
  const etaString = etaDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  const aheadWaterDepth_cm = Math.round((currentStep?.maxFloodDepth_m || 0) * 100);
  const isWaterElevated = aheadWaterDepth_cm > 15;

  return (
    <div className="absolute inset-0 pointer-events-none z-30 flex flex-col justify-between p-3 sm:p-5">
      
      {/* ── TOP HEADS-UP TURN BANNER ────────────────────────────────────────── */}
      <div className="pointer-events-auto max-w-xl w-full mx-auto flex flex-col space-y-2">
        <div className="glass-panel bg-slate-950/92 border border-cyan-500/30 rounded-2xl shadow-2xl p-4 backdrop-blur-2xl transition-all">
          <div className="flex items-center space-x-4">
            
            {/* Primary Maneuver Icon */}
            <div className="flex-shrink-0 flex items-center justify-center h-14 w-14 rounded-2xl bg-cyan-950/70 border border-cyan-500/40 shadow-inner">
              {renderManeuverIcon(currentStep?.maneuver, 'h-8 w-8')}
            </div>

            {/* Instruction & Distance */}
            <div className="flex-1 min-w-0">
              <div className="flex items-baseline space-x-2">
                <span className="text-2xl sm:text-3xl font-black font-mono-num text-white tracking-tight">
                  {formatDistance(distanceToNextTurn_m)}
                </span>
                <span className="text-xs uppercase tracking-wider font-semibold text-cyan-400">
                  {currentStep?.maneuver === 'arrive' ? 'To Destination' : 'Then Turn'}
                </span>
              </div>

              <h2 className="text-sm sm:text-base font-bold text-slate-100 truncate mt-0.5">
                {currentStep?.instruction || 'Follow highlighted safe route'}
              </h2>

              {nextStep && nextStep.maneuver !== 'arrive' && (
                <div className="flex items-center space-x-1.5 mt-1 text-[11px] text-slate-400 truncate">
                  <span className="text-slate-500">Then:</span>
                  <div className="h-3 w-3 inline-flex items-center justify-center">
                    {renderManeuverIcon(nextStep.maneuver, 'h-3 w-3')}
                  </div>
                  <span className="truncate">{nextStep.roadName}</span>
                </div>
              )}
            </div>

            {/* Voice Guidance Toggle */}
            <button
              onClick={onToggleVoice}
              title={isVoiceMuted ? 'Voice Guidance: MUTED (Click to Turn ON)' : 'Voice Guidance: ACTIVE (Click to Mute)'}
              className={`flex-shrink-0 flex items-center space-x-1.5 px-3 py-2 rounded-xl border transition-all cursor-pointer font-mono-num text-xs font-bold ${
                isVoiceMuted
                  ? 'bg-rose-500/15 border-rose-500/30 text-rose-400 hover:bg-rose-500/25'
                  : 'bg-cyan-500/15 border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/25 shadow-[0_0_12px_rgba(6,182,212,0.25)]'
              }`}
            >
              {isVoiceMuted ? <VolumeX className="h-4 w-4 text-rose-400" /> : <Volume2 className="h-4 w-4 text-cyan-300 animate-pulse" />}
              <span className="hidden sm:inline">{isVoiceMuted ? 'Voice: OFF' : 'Voice: ON'}</span>
            </button>

            {/* Exit Button */}
            <button
              onClick={onExitNavigation}
              title="Exit Navigation"
              className="flex-shrink-0 p-2.5 rounded-xl bg-slate-800/80 hover:bg-red-500/20 text-slate-400 hover:text-red-400 border border-slate-700 hover:border-red-500/40 transition-colors cursor-pointer"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Real-time Flood Hazard Strip for Upcoming Segment */}
          <div className={`mt-3 pt-2.5 border-t border-slate-800/80 flex items-center justify-between text-xs ${
            isWaterElevated ? 'text-amber-300' : 'text-emerald-300'
          }`}>
            <div className="flex items-center space-x-1.5">
              {isWaterElevated ? (
                <AlertTriangle className="h-3.5 w-3.5 text-amber-400 flex-shrink-0" />
              ) : (
                <ShieldCheck className="h-3.5 w-3.5 text-emerald-400 flex-shrink-0" />
              )}
              <span className="font-medium text-[11px] sm:text-xs">
                {aheadWaterDepth_cm > 0
                  ? `Road Water Ponding Ahead: ${aheadWaterDepth_cm} cm (Clearance safe for ${vehicleType})`
                  : 'Road surface completely dry & clear'}
              </span>
            </div>

            <div className="flex items-center space-x-1 font-mono-num text-[10px] uppercase font-bold px-2 py-0.5 rounded-md bg-slate-900 border border-slate-800">
              <Waves className="h-3 w-3 text-cyan-400" />
              <span>A* Flood-Free</span>
            </div>
          </div>
        </div>
      </div>

      {/* ── BOTTOM HUD CONTROLS & TELEMETRY ─────────────────────────────────── */}
      <div className="pointer-events-auto max-w-xl w-full mx-auto space-y-2.5">
        
        {/* Simulation / Indoor Demo Controller Box */}
        {showSimControls && (
          <div className="glass-panel bg-slate-950/90 border border-slate-800/90 rounded-2xl shadow-xl p-3 backdrop-blur-xl">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center space-x-2">
                <span className="flex h-2 w-2 rounded-full bg-cyan-400 animate-ping" />
                <span className="text-[11px] font-mono-num font-bold text-slate-300 uppercase tracking-wider">
                  {isLiveGps ? (hasGpsLock ? 'Live Device GPS Active' : 'Waiting for GPS Lock...') : 'Demo Drive Simulator'}
                </span>
              </div>

              {/* Mode Toggle & Fake Off-Route Button */}
              <div className="flex items-center space-x-1.5">
                {onTriggerOffRouteSim && !isLiveGps && (
                  <button
                    onClick={onTriggerOffRouteSim}
                    title="Simulate driver missing a turn to test automatic flood-safe re-routing"
                    className="text-[10px] font-mono-num font-bold px-2 py-1 rounded-lg bg-amber-500/15 hover:bg-amber-500/30 text-amber-300 border border-amber-500/30 transition-all cursor-pointer"
                  >
                    Simulate Missed Turn
                  </button>
                )}

                <button
                  onClick={onToggleLiveGps}
                  className={`text-[10px] font-mono-num font-bold px-2.5 py-1 rounded-lg border transition-all cursor-pointer flex items-center space-x-1 ${
                    isLiveGps
                      ? 'bg-cyan-500/20 border-cyan-500/40 text-cyan-300'
                      : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-white'
                  }`}
                >
                  <Radio className="h-3 w-3 mr-0.5" />
                  <span>{isLiveGps ? 'GPS' : 'Sim'}</span>
                </button>
              </div>
            </div>

            {/* Simulation Playback Bar (When in Demo Mode) */}
            {!isLiveGps && (
              <div className="flex items-center space-x-3">
                {/* Play / Pause */}
                <button
                  onClick={onTogglePlayPause}
                  className="p-2 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-md shadow-cyan-500/20 hover:brightness-110 active:scale-95 transition-all cursor-pointer"
                >
                  {isSimulating ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                </button>

                {/* Progress Scrubber Slider */}
                <div className="flex-1 flex flex-col justify-center">
                  <input
                    type="range"
                    min={0}
                    max={100}
                    step={0.5}
                    value={simProgressPct}
                    onChange={(e) => onSeekProgress(parseFloat(e.target.value))}
                    className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400"
                  />
                  <div className="flex justify-between text-[9px] font-mono-num text-slate-500 mt-1">
                    <span>Point A (Origin)</span>
                    <span>{simProgressPct.toFixed(0)}%</span>
                    <span>Point B (Target)</span>
                  </div>
                </div>

                {/* Speed Multiplier Options */}
                <div className="flex items-center space-x-1 bg-slate-900/80 p-0.5 rounded-lg border border-slate-800">
                  {[1, 2, 5, 10].map((mult) => (
                    <button
                      key={mult}
                      onClick={() => onChangeSpeed(mult)}
                      className={`text-[10px] font-mono-num font-bold px-1.5 py-0.5 rounded transition-colors cursor-pointer ${
                        simSpeedMultiplier === mult
                          ? 'bg-cyan-500 text-slate-950'
                          : 'text-slate-400 hover:text-white'
                      }`}
                    >
                      {mult}x
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Primary Navigation Telemetry Footer */}
        <div className="glass-panel bg-slate-950/95 border border-slate-800/90 rounded-2xl shadow-2xl p-3.5 backdrop-blur-2xl flex items-center justify-between">
          
          {/* Trip Metrics */}
          <div className="flex items-center space-x-5">
            <div>
              <div className="text-[10px] font-mono-num text-slate-400 flex items-center">
                <Clock className="h-3 w-3 mr-1 text-cyan-400" />
                EST. TIME
              </div>
              <div className="text-lg font-black font-mono-num text-emerald-400">
                {formatDuration(totalRemainingDuration_s)}
              </div>
            </div>

            <div className="h-7 w-[1px] bg-slate-800" />

            <div>
              <div className="text-[10px] font-mono-num text-slate-400 flex items-center">
                <Gauge className="h-3 w-3 mr-1 text-cyan-400" />
                REMAINING
              </div>
              <div className="text-lg font-black font-mono-num text-white">
                {formatDistance(totalRemainingDistance_m)}
              </div>
            </div>

            <div className="h-7 w-[1px] bg-slate-800" />

            <div>
              <div className="text-[10px] font-mono-num text-slate-400">ETA</div>
              <div className="text-lg font-black font-mono-num text-slate-300">
                {etaString}
              </div>
            </div>
          </div>

          {/* Quick HUD Action Buttons */}
          <div className="flex items-center space-x-2">
            {/* Recenter Camera */}
            <button
              onClick={onRecenterCamera}
              title="Recenter Map on Vehicle"
              className="p-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-800 transition-colors cursor-pointer"
            >
              <Crosshair className="h-4 w-4" />
            </button>

            {/* Voice Mute / Unmute */}
            <button
              onClick={onToggleVoice}
              title={isVoiceMuted ? 'Turn Voice Guidance ON' : 'Mute Voice Guidance'}
              className={`flex items-center space-x-1.5 px-3 py-2 rounded-xl border transition-colors cursor-pointer text-xs font-mono-num font-bold ${
                isVoiceMuted
                  ? 'bg-red-500/15 border-red-500/30 text-red-400 hover:bg-red-500/25'
                  : 'bg-cyan-500/15 border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/25'
              }`}
            >
              {isVoiceMuted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
              <span>{isVoiceMuted ? 'Voice Muted' : 'Voice Active'}</span>
            </button>
          </div>

        </div>
      </div>

    </div>
  );
};
