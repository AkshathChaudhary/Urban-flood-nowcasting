import React, { useState } from 'react';
import { 
  GitBranch, 
  Droplets, 
  AlertOctagon, 
  Sliders, 
  RotateCcw, 
  X,
  Waves,
  ArrowDownCircle
} from 'lucide-react';
import type { DrainageSummary } from '../services/api';

interface DrainagePanelProps {
  summary: DrainageSummary | null;
  onUpdateBlockage: (pct: number) => void;
  onResetDrainage: () => void;
  isUpdating: boolean;
  isOpen: boolean;
  onToggleOpen: () => void;
  surchargingCount: number;
}

export const DrainagePanel: React.FC<DrainagePanelProps> = ({
  summary,
  onUpdateBlockage,
  onResetDrainage,
  isUpdating,
  isOpen,
  onToggleOpen,
  surchargingCount,
}) => {
  const [blockagePct, setBlockagePct] = useState<number>(0);

  const handleApplyBlockage = () => {
    onUpdateBlockage(blockagePct / 100.0);
  };

  const handlePreset = (pct: number) => {
    setBlockagePct(pct);
    onUpdateBlockage(pct / 100.0);
  };

  if (!isOpen) {
    return (
      <button
        onClick={onToggleOpen}
        className="absolute top-16 right-4 z-20 flex items-center space-x-2 px-3.5 py-2 rounded-xl bg-slate-900/90 border border-emerald-500/40 text-emerald-300 font-semibold text-xs shadow-xl hover:brightness-110 active:scale-95 transition-all cursor-pointer backdrop-blur-md"
      >
        <GitBranch className="h-3.5 w-3.5" />
        <span>Drainage Diagnostics</span>
        {surchargingCount > 0 && (
          <span className="px-1.5 py-0.2 rounded-full bg-red-500/20 text-red-300 border border-red-500/40 text-[10px]">
            {surchargingCount} Surcharge
          </span>
        )}
      </button>
    );
  }

  return (
    <div className="absolute top-16 right-4 z-20 w-84 sm:w-96 glass-panel rounded-3xl border border-slate-800/90 shadow-2xl p-5 flex flex-col max-h-[calc(100vh-10rem)] overflow-y-auto backdrop-blur-2xl">
      
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-800/80 mb-4">
        <div className="flex items-center space-x-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
            <GitBranch className="h-4 w-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white tracking-tight">
              SUBTERRANEAN DRAINAGE
            </h3>
            <span className="text-[10px] font-mono-num text-emerald-400 font-medium">
              1,316 Conduits • 1,479 Manholes
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

      {/* Hydraulic State Grid */}
      <div className="grid grid-cols-2 gap-2 text-xs font-mono-num mb-4">
        <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-850">
          <div className="text-[10px] text-slate-400 flex items-center">
            <Droplets className="h-3 w-3 mr-1 text-emerald-400" />
            STORED IN PIPES
          </div>
          <div className="text-base font-bold text-white mt-0.5">
            {summary ? summary.current_water_stored_m3.toFixed(1) : '24.2'} <span className="text-xs font-normal text-slate-400">m³</span>
          </div>
        </div>

        <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-850">
          <div className="text-[10px] text-slate-400 flex items-center">
            <ArrowDownCircle className="h-3 w-3 mr-1 text-cyan-400" />
            OUTFALL DISCHARGE
          </div>
          <div className="text-base font-bold text-white mt-0.5">
            {summary ? Math.round(summary.total_discharged_m3).toLocaleString() : '2,345'} <span className="text-xs font-normal text-slate-400">m³</span>
          </div>
        </div>

        <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-850">
          <div className="text-[10px] text-slate-400">INLETS & JUNCTIONS</div>
          <div className="text-base font-bold text-slate-200 mt-0.5">
            {summary ? `${summary.inlet_nodes} / ${summary.junction_nodes}` : '1005 / 466'}
          </div>
        </div>

        <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-850">
          <div className="text-[10px] text-slate-400 flex items-center">
            <Waves className="h-3 w-3 mr-1 text-blue-400" />
            MITHI OUTFALLS
          </div>
          <div className="text-base font-bold text-cyan-400 mt-0.5">
            {summary ? `${summary.outfall_nodes} Points` : '8 Points'}
          </div>
        </div>
      </div>

      {/* Surcharge Status Badge */}
      <div className={`p-2.5 rounded-xl border text-xs font-mono-num flex items-center justify-between mb-4 ${
        surchargingCount > 0 
          ? 'bg-red-950/40 border-red-500/40 text-red-300' 
          : 'bg-emerald-950/30 border-emerald-500/30 text-emerald-300'
      }`}>
        <span className="flex items-center space-x-1.5">
          <AlertOctagon className={`h-4 w-4 ${surchargingCount > 0 ? 'text-red-400 animate-pulse' : 'text-emerald-400'}`} />
          <span>PIPE SURCHARGE STATUS:</span>
        </span>
        <span className="font-bold">
          {surchargingCount > 0 ? `${surchargingCount} MANHOLES BOILING UP` : 'CLEAR HEADROOM'}
        </span>
      </div>

      {/* Debris Blockage Simulator */}
      <div className="p-3.5 rounded-2xl bg-slate-900/70 border border-slate-800/80 mb-3 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-mono-num font-bold text-slate-300 flex items-center">
            <Sliders className="h-3.5 w-3.5 mr-1.5 text-amber-400" />
            DEBRIS BLOCKAGE SIMULATOR
          </span>
          <span className="text-xs font-mono-num font-bold text-amber-400">
            {blockagePct}%
          </span>
        </div>

        <input
          type="range"
          min={0}
          max={100}
          step={5}
          value={blockagePct}
          onChange={(e) => setBlockagePct(Number(e.target.value))}
          className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-amber-400"
        />

        {/* Quick Presets */}
        <div className="grid grid-cols-3 gap-1.5 text-[10px] font-mono-num">
          <button
            onClick={() => handlePreset(0)}
            className={`py-1 rounded-lg border text-center transition-all cursor-pointer ${
              blockagePct === 0 
                ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300 font-bold' 
                : 'bg-slate-950/50 border-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            Clear (0%)
          </button>
          <button
            onClick={() => handlePreset(40)}
            className={`py-1 rounded-lg border text-center transition-all cursor-pointer ${
              blockagePct === 40 
                ? 'bg-amber-500/20 border-amber-500/40 text-amber-300 font-bold' 
                : 'bg-slate-950/50 border-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            Monsoon (40%)
          </button>
          <button
            onClick={() => handlePreset(75)}
            className={`py-1 rounded-lg border text-center transition-all cursor-pointer ${
              blockagePct === 75 
                ? 'bg-red-500/20 border-red-500/40 text-red-300 font-bold' 
                : 'bg-slate-950/50 border-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            Clogged (75%)
          </button>
        </div>

        {/* Apply & Reset Buttons */}
        <div className="flex space-x-2 pt-1">
          <button
            onClick={handleApplyBlockage}
            disabled={isUpdating}
            className="flex-1 py-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 text-white text-xs font-bold shadow-lg shadow-amber-500/20 hover:brightness-110 active:scale-95 transition-all cursor-pointer disabled:opacity-50 text-center"
          >
            {isUpdating ? 'APPLYING BLOCKAGE...' : 'SIMULATE CLOG'}
          </button>

          <button
            onClick={onResetDrainage}
            title="Reset Drainage Network"
            className="p-2 rounded-xl bg-slate-800 text-slate-300 hover:bg-slate-700 active:scale-95 transition-all cursor-pointer"
          >
            <RotateCcw className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="text-[10px] text-slate-500 font-mono-num text-center">
        Coupled Manning equation subterranean pipe network with hydraulic head surcharge
      </div>

    </div>
  );
};
