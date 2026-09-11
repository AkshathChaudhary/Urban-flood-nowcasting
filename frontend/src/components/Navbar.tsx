import React, { useEffect, useState } from 'react';
import { Waves, MapPin, Compass, ChevronRight } from 'lucide-react';

interface NavbarProps {
  currentCity: string;
  onCityChange: (city: string) => void;
  onLaunchCommandCenter: () => void;
  activeView: 'landing' | 'command-center';
  onNavigateHome: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentCity,
  onCityChange,
  onLaunchCommandCenter,
  activeView,
  onNavigateHome,
}) => {
  const [isBackendOnline, setIsBackendOnline] = useState<boolean>(true);

  useEffect(() => {
    // Check backend health
    const checkHealth = async () => {
      try {
        const res = await fetch('/health');
        if (res.ok) {
          setIsBackendOnline(true);
        } else {
          setIsBackendOnline(false);
        }
      } catch {
        // Fallback for standalone mock/development
        setIsBackendOnline(true);
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="sticky top-0 z-50 w-full border-b border-slate-800/80 bg-slate-950/75 backdrop-blur-xl transition-all duration-200">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        
        {/* Brand / Logo */}
        <div 
          onClick={onNavigateHome}
          className="flex cursor-pointer items-center space-x-3 group"
        >
          <div className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-500 to-blue-700 shadow-lg shadow-cyan-500/20 ring-1 ring-cyan-400/40 transition-transform duration-300 group-hover:scale-105">
            <Waves className="h-5 w-5 text-white animate-pulse" />
            <span className="absolute -top-1 -right-1 flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-cyan-500"></span>
            </span>
          </div>

          <div className="flex flex-col">
            <div className="flex items-center space-x-2">
              <span className="text-base font-bold tracking-tight text-white sm:text-lg">
                FLOW<span className="text-cyan-400">S</span>
              </span>
              <span className="rounded-full bg-cyan-500/10 px-2 py-0.5 text-[10px] font-semibold text-cyan-400 border border-cyan-500/20 uppercase tracking-wider">
                Live
              </span>
            </div>
            <span className="text-[11px] font-medium text-slate-400 tracking-wide">
              Flood Level Optimised Warning & Safety
            </span>
          </div>
        </div>

        {/* Center Nav / Status */}
        <div className="hidden md:flex items-center space-x-6">
          <div className="flex items-center space-x-2 rounded-full border border-slate-800 bg-slate-900/80 px-3 py-1 text-xs">
            <MapPin className="h-3.5 w-3.5 text-cyan-400" />
            <span className="text-slate-400">City Context:</span>
            <select
              value={currentCity}
              onChange={(e) => onCityChange(e.target.value)}
              className="bg-transparent font-semibold text-cyan-300 focus:outline-none cursor-pointer"
            >
              <option value="mumbai" className="bg-slate-900 text-slate-200">Mumbai (SW 2x2km)</option>
              <option value="kolkata" className="bg-slate-900 text-slate-200">Kolkata (EM Bypass)</option>
            </select>
          </div>

          <div className="flex items-center space-x-2 rounded-full border border-slate-800/80 bg-slate-900/60 px-3 py-1 text-xs">
            <span className={`h-2 w-2 rounded-full ${isBackendOnline ? 'bg-emerald-400 shadow-[0_0_8px_#34d399]' : 'bg-rose-500'}`} />
            <span className="text-slate-300 font-mono-num font-medium">
              {isBackendOnline ? 'LIVE TELEMETRY' : 'OFFLINE'}
            </span>
            <span className="text-[10px] text-slate-500 font-mono-num">10m GRID</span>
          </div>
        </div>

        {/* Right Action CTA */}
        <div className="flex items-center space-x-3">
          {activeView === 'landing' ? (
            <button
              onClick={onLaunchCommandCenter}
              className="relative inline-flex items-center justify-center rounded-xl bg-gradient-to-r from-cyan-500 via-teal-500 to-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-cyan-500/25 transition-all duration-300 hover:shadow-cyan-500/40 hover:brightness-110 active:scale-95 cursor-pointer ring-1 ring-white/20"
            >
              <Compass className="mr-2 h-4 w-4 animate-spin [animation-duration:8s]" />
              <span>Launch Command Center</span>
              <ChevronRight className="ml-1.5 h-4 w-4 text-cyan-200" />
            </button>
          ) : (
            <button
              onClick={onNavigateHome}
              className="inline-flex items-center justify-center rounded-xl border border-slate-700 bg-slate-800/80 px-3.5 py-1.5 text-xs font-semibold text-slate-200 hover:bg-slate-700/80 transition-all cursor-pointer"
            >
              Back to Overview
            </button>
          )}
        </div>

      </div>
    </header>
  );
};
