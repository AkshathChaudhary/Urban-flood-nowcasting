import React, { useState } from 'react';
import {
  X,
  Sparkles,
  MapPin,
  Radio,
  CloudRain,
  Compass,
  CheckCircle2,
  Loader2,
  AlertCircle,
  ArrowRight,
  Layers,
  Zap,
} from 'lucide-react';
import { buildDynamicCorridor, type BuildCorridorResult } from '../services/api';

interface CorridorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCorridorCreated: (corridorId: string, result?: BuildCorridorResult) => void;
}

const PRESET_CORRIDORS = [
  {
    name: 'Chennai: T. Nagar → Nungambakkam',
    src: 'T. Nagar, Chennai',
    dst: 'Nungambakkam, Chennai',
    tag: 'Pre-Compiled Demo',
  },
  {
    name: 'Bengaluru: Silk Board → Bellandur',
    src: 'Silk Board, Bengaluru',
    dst: 'Bellandur Lake, Bengaluru',
    tag: 'Lake Overflow Basin',
  },
  {
    name: 'Delhi: Connaught Place → ITO Underpass',
    src: 'Connaught Place, New Delhi',
    dst: 'ITO Underpass, New Delhi',
    tag: 'Yamuna Floodplain',
  },
  {
    name: 'Hyderabad: Hitec City → Gachibowli',
    src: 'Hitec City, Hyderabad',
    dst: 'Gachibowli, Hyderabad',
    tag: 'IT Corridor Depression',
  },
];

const PIPELINE_STEPS = [
  'Resolving geocoded coordinates & bounding buffer...',
  'Extracting multi-tier Copernicus DEM & hydro-conditioning...',
  'Building OpenStreetMap topological highway network...',
  'Synthesizing CPHEEO subterranean drainage conduits & outfalls...',
  'Ingesting Open-Meteo & Doppler radar rainfall profiles...',
  'Coupling 2D hydrodynamic simulation & route graph...',
];

export const CorridorModal: React.FC<CorridorModalProps> = ({
  isOpen,
  onClose,
  onCorridorCreated,
}) => {
  const [src, setSrc] = useState('T. Nagar, Chennai');
  const [dst, setDst] = useState('Nungambakkam, Chennai');
  const [scenario, setScenario] = useState('heavy');
  const [useLiveRadar, setUseLiveRadar] = useState(false);
  const [isBuilding, setIsBuilding] = useState(false);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successResult, setSuccessResult] = useState<BuildCorridorResult | null>(null);

  if (!isOpen) return null;

  const handleApplyPreset = (presetSrc: string, presetDst: string) => {
    setSrc(presetSrc);
    setDst(presetDst);
    setErrorMsg(null);
  };

  const handleBuild = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!src.trim() || !dst.trim()) {
      setErrorMsg('Please specify both origin and destination.');
      return;
    }

    setIsBuilding(true);
    setErrorMsg(null);
    setSuccessResult(null);
    setCurrentStepIndex(0);

    // Simulate animated step progression while backend builds
    const stepInterval = setInterval(() => {
      setCurrentStepIndex((prev) => (prev < PIPELINE_STEPS.length - 1 ? prev + 1 : prev));
    }, 2800);

    try {
      const result = await buildDynamicCorridor({
        src: src.trim(),
        dst: dst.trim(),
        scenario: useLiveRadar ? 'live' : scenario,
        use_live_radar: useLiveRadar,
      });

      clearInterval(stepInterval);
      setCurrentStepIndex(PIPELINE_STEPS.length - 1);
      setSuccessResult(result);

      // Brief delay to allow user to see success state before transitioning
      setTimeout(() => {
        setIsBuilding(false);
        onCorridorCreated(result.corridor_id, result);
        onClose();
      }, 1200);
    } catch (err: any) {
      clearInterval(stepInterval);
      setIsBuilding(false);
      setErrorMsg(err.message || 'Failed to build corridor. Please verify your locations.');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="relative w-full max-w-2xl overflow-hidden rounded-2xl border border-cyan-500/30 bg-slate-900/95 p-6 shadow-2xl shadow-cyan-950/50 text-slate-100 max-h-[90vh] flex flex-col">
        
        {/* Header Glow */}
        <div className="absolute -top-24 -left-24 h-48 w-48 rounded-full bg-cyan-500/15 blur-3xl pointer-events-none" />
        <div className="absolute -top-24 -right-24 h-48 w-48 rounded-full bg-blue-500/15 blur-3xl pointer-events-none" />

        {/* Modal Header */}
        <div className="flex items-start justify-between pb-4 border-b border-slate-800">
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-cyan-500/20 text-cyan-400 border border-cyan-500/40">
                <Sparkles className="h-4 w-4" />
              </span>
              <h2 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
                Universal Corridor Engine
                <span className="text-[10px] font-mono uppercase bg-cyan-950 text-cyan-400 px-2 py-0.5 rounded-full border border-cyan-800">
                  Any 2 Points in India
                </span>
              </h2>
            </div>
            <p className="text-xs text-slate-400">
              Generate coupled DEM, OSM road topology, subterranean drainage networks, and hydrodynamic nowcasting for any custom geography.
            </p>
          </div>
          <button
            onClick={onClose}
            disabled={isBuilding}
            className="rounded-lg p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 transition-colors disabled:opacity-40"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="overflow-y-auto space-y-5 py-4 pr-1 flex-1">
          
          {/* Presets Bar */}
          <div>
            <label className="text-[11px] font-mono text-slate-400 uppercase tracking-wider block mb-2">
              Quick Test Corridors Across India:
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {PRESET_CORRIDORS.map((p, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleApplyPreset(p.src, p.dst)}
                  disabled={isBuilding}
                  className="flex items-center justify-between p-2 rounded-lg border border-slate-800 hover:border-cyan-500/40 bg-slate-950/50 hover:bg-cyan-950/20 text-left transition-all group"
                >
                  <div className="truncate mr-2">
                    <div className="text-xs font-medium text-slate-200 group-hover:text-cyan-300 truncate">
                      {p.name}
                    </div>
                    <div className="text-[10px] text-slate-400">{p.tag}</div>
                  </div>
                  <ArrowRight className="h-3 w-3 text-slate-600 group-hover:text-cyan-400 shrink-0 transition-transform group-hover:translate-x-0.5" />
                </button>
              ))}
            </div>
          </div>

          {/* Form */}
          <form onSubmit={handleBuild} className="space-y-4">
            
            {/* Origin & Destination Inputs */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                  <MapPin className="h-3.5 w-3.5 text-cyan-400" />
                  Origin (Landmark or Lat, Lon)
                </label>
                <input
                  type="text"
                  value={src}
                  onChange={(e) => setSrc(e.target.value)}
                  disabled={isBuilding}
                  placeholder="e.g. T. Nagar, Chennai or 13.0418, 80.2341"
                  className="w-full rounded-xl border border-slate-700 bg-slate-950/80 px-3 py-2 text-xs text-white placeholder-slate-500 focus:border-cyan-400 focus:outline-none focus:ring-1 focus:ring-cyan-400"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                  <Compass className="h-3.5 w-3.5 text-blue-400" />
                  Destination (Landmark or Lat, Lon)
                </label>
                <input
                  type="text"
                  value={dst}
                  onChange={(e) => setDst(e.target.value)}
                  disabled={isBuilding}
                  placeholder="e.g. Nungambakkam, Chennai or 13.0600, 80.2400"
                  className="w-full rounded-xl border border-slate-700 bg-slate-950/80 px-3 py-2 text-xs text-white placeholder-slate-500 focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400"
                />
              </div>
            </div>

            {/* Precipitation Mode */}
            <div className="space-y-2 pt-1">
              <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                <CloudRain className="h-3.5 w-3.5 text-cyan-400" />
                Rainfall Nowcasting Source & Scenario
              </label>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {[
                  { id: 'heavy', label: 'Heavy Storm', desc: '30 mm/hr' },
                  { id: 'extreme', label: 'Extreme Downpour', desc: '55 mm/hr' },
                  { id: 'cloudburst', label: 'Cloudburst Deluge', desc: '100 mm/hr' },
                  { id: 'live', label: 'Doppler Radar', desc: 'Live Open-Meteo' },
                ].map((s) => {
                  const isLive = s.id === 'live';
                  const isSelected = isLive ? useLiveRadar : (!useLiveRadar && scenario === s.id);

                  return (
                    <button
                      key={s.id}
                      type="button"
                      disabled={isBuilding}
                      onClick={() => {
                        if (isLive) {
                          setUseLiveRadar(true);
                        } else {
                          setUseLiveRadar(false);
                          setScenario(s.id);
                        }
                      }}
                      className={`p-2 rounded-xl border text-left transition-all ${
                        isSelected
                          ? 'border-cyan-400 bg-cyan-950/40 shadow-sm shadow-cyan-950'
                          : 'border-slate-800 bg-slate-950/40 hover:border-slate-700 text-slate-400'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className={`text-xs font-semibold ${isSelected ? 'text-cyan-300' : 'text-slate-300'}`}>
                          {s.label}
                        </span>
                        {isLive && (
                          <Radio className={`h-3 w-3 ${isSelected ? 'text-cyan-400 animate-pulse' : 'text-slate-500'}`} />
                        )}
                      </div>
                      <span className="text-[10px] text-slate-400 block mt-0.5">{s.desc}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Active Building Animation & Progress Tracker */}
            {isBuilding && (
              <div className="rounded-xl border border-cyan-500/30 bg-cyan-950/20 p-4 space-y-3">
                <div className="flex items-center justify-between text-xs font-semibold text-cyan-300">
                  <span className="flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin text-cyan-400" />
                    Synthesizing Domain Assets...
                  </span>
                  <span className="font-mono text-cyan-400">
                    Step {currentStepIndex + 1} of {PIPELINE_STEPS.length}
                  </span>
                </div>

                {/* Progress bar */}
                <div className="h-1.5 w-full rounded-full bg-slate-800 overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 transition-all duration-500 rounded-full"
                    style={{
                      width: `${((currentStepIndex + 1) / PIPELINE_STEPS.length) * 100}%`,
                    }}
                  />
                </div>

                <div className="text-[11px] font-mono text-slate-300 flex items-center gap-2">
                  <Zap className="h-3.5 w-3.5 text-amber-400 shrink-0" />
                  <span>{PIPELINE_STEPS[currentStepIndex]}</span>
                </div>
              </div>
            )}

            {/* Success State */}
            {successResult && (
              <div className="rounded-xl border border-emerald-500/40 bg-emerald-950/20 p-3.5 flex items-center gap-3 text-emerald-300 text-xs">
                <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0" />
                <div>
                  <div className="font-semibold">Corridor Assets Compiled Successfully!</div>
                  <div className="text-[11px] text-emerald-400/80">
                    {successResult.road_edges} road segments • {successResult.drainage_nodes} drainage nodes • Transitioning map view...
                  </div>
                </div>
              </div>
            )}

            {/* Error Message */}
            {errorMsg && (
              <div className="rounded-xl border border-rose-500/40 bg-rose-950/20 p-3 flex items-center gap-2 text-rose-300 text-xs">
                <AlertCircle className="h-4 w-4 text-rose-400 shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}

            {/* Submit Action */}
            <div className="flex items-center justify-end space-x-3 pt-2">
              <button
                type="button"
                onClick={onClose}
                disabled={isBuilding}
                className="px-4 py-2 rounded-xl border border-slate-800 text-xs text-slate-300 hover:bg-slate-800 transition-colors disabled:opacity-40"
              >
                Cancel
              </button>

              <button
                type="submit"
                disabled={isBuilding}
                className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-5 py-2 text-xs font-semibold text-white shadow-lg shadow-cyan-950 hover:from-cyan-400 hover:to-blue-500 transition-all disabled:opacity-50 cursor-pointer"
              >
                {isBuilding ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    <span>Compiling Physics Assets...</span>
                  </>
                ) : (
                  <>
                    <Layers className="h-3.5 w-3.5" />
                    <span>Build & Nowcast Corridor</span>
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};
