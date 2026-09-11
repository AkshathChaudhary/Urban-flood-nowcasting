import React from 'react';
import { motion } from 'framer-motion';
import { 
  Waves, 
  GitFork, 
  Navigation, 
  CloudRain, 
  Cpu, 
  ShieldCheck, 
  ArrowRight 
} from 'lucide-react';

interface BentoShowcaseProps {
  onExploreFeature: (featureId: string) => void;
}

export const BentoShowcase: React.FC<BentoShowcaseProps> = ({ onExploreFeature }) => {
  return (
    <section className="relative px-4 sm:px-6 lg:px-8 py-20 bg-slate-950/60 border-t border-slate-900">
      
      <div className="mx-auto max-w-7xl">
        
        {/* Section Header */}
        <div className="flex flex-col items-center text-center mb-16">
          <div className="inline-flex items-center space-x-2 rounded-full border border-slate-800 bg-slate-900/80 px-3 py-1 text-xs text-cyan-400 font-mono-num mb-4">
            <Cpu className="h-3.5 w-3.5" />
            <span>COUPLING 3 SUBSYSTEMS INTO A UNIFIED PIPELINE</span>
          </div>

          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold text-white tracking-tight">
            Engineered for <span className="bg-gradient-to-r from-cyan-400 to-teal-300 bg-clip-text text-transparent">Extreme Urban Weather</span>
          </h2>
          
          <p className="mt-4 text-base sm:text-lg text-slate-400 max-w-2xl">
            Our unified solver seamlessly links underground hydraulic pipes with surface terrain runoffs and road routing graphs.
          </p>
        </div>

        {/* 21st.dev Inspired Bento Grid */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
          
          {/* Card 1: 2D Hydrodynamic Surface Model (Large Feature Card, 7 cols) */}
          <motion.div
            whileHover={{ y: -4 }}
            transition={{ duration: 0.2 }}
            className="md:col-span-7 glass-card rounded-3xl p-8 flex flex-col justify-between relative overflow-hidden group"
          >
            {/* Ambient Background Gradient */}
            <div className="absolute top-0 right-0 w-64 h-64 bg-cyan-500/10 blur-3xl rounded-full pointer-events-none transition-opacity group-hover:opacity-100 opacity-60" />

            <div>
              <div className="flex items-center justify-between mb-6">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
                  <Waves className="h-6 w-6" />
                </div>
                <span className="text-xs font-mono-num font-semibold text-cyan-400/90 px-3 py-1 rounded-full bg-cyan-950/60 border border-cyan-800/50">
                  PAIR B: HYDRODYNAMICS
                </span>
              </div>

              <h3 className="text-2xl font-bold text-white mb-3">
                2D Shallow-Water Surface Inundation
              </h3>

              <p className="text-sm text-slate-300 leading-relaxed mb-6">
                High-resolution finite-difference numerical solver simulating 2D water depth progression across 
                a 200×200 grid (10m cells). Computes elevation flux transfer, depression ponding, and depression storage.
              </p>

              {/* Technical Spec Tags */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-4 border-t border-slate-800/80">
                <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800">
                  <div className="text-[11px] text-slate-400">Time Step (Δt)</div>
                  <div className="text-sm font-bold text-white font-mono-num mt-0.5">300 Seconds</div>
                </div>
                <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800">
                  <div className="text-[11px] text-slate-400">Domain Bounds</div>
                  <div className="text-sm font-bold text-cyan-300 font-mono-num mt-0.5">2.0 × 2.0 km</div>
                </div>
                <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 col-span-2 sm:col-span-1">
                  <div className="text-[11px] text-slate-400">Mass Conservation</div>
                  <div className="text-sm font-bold text-emerald-400 font-mono-num mt-0.5">&gt; 99.8%</div>
                </div>
              </div>
            </div>

            <div className="mt-8 flex items-center justify-between">
              <span className="text-xs text-slate-400 font-mono-num">
                Coupled with SRTM / TanDEM-X Topography
              </span>
              <button 
                onClick={() => onExploreFeature('hydrodynamics')}
                className="inline-flex items-center text-xs font-semibold text-cyan-400 group-hover:text-cyan-300 cursor-pointer"
              >
                <span>Inspect Solver</span>
                <ArrowRight className="ml-1 h-3.5 w-3.5 transition-transform group-hover:translate-x-1" />
              </button>
            </div>
          </motion.div>

          {/* Card 2: Subterranean Drainage Network (5 cols) */}
          <motion.div
            whileHover={{ y: -4 }}
            transition={{ duration: 0.2 }}
            className="md:col-span-5 glass-card rounded-3xl p-8 flex flex-col justify-between relative overflow-hidden group"
          >
            <div className="absolute -bottom-10 -right-10 w-48 h-48 bg-amber-500/10 blur-3xl rounded-full pointer-events-none" />

            <div>
              <div className="flex items-center justify-between mb-6">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-400">
                  <GitFork className="h-6 w-6" />
                </div>
                <span className="text-xs font-mono-num font-semibold text-amber-400/90 px-3 py-1 rounded-full bg-amber-950/60 border border-amber-800/50">
                  PAIR A: DRAINAGE
                </span>
              </div>

              <h3 className="text-2xl font-bold text-white mb-3">
                Manning Pipe Hydraulics & Surcharge
              </h3>

              <p className="text-sm text-slate-300 leading-relaxed mb-4">
                Models underground stormwater conduits via NetworkX directed graphs. When rainfall exceeds pipe capacity, 
                manhole nodes calculate reverse surcharge, spitting excess water back onto the surface.
              </p>

              <div className="space-y-2 mt-4">
                <div className="flex items-center justify-between text-xs p-2.5 rounded-lg bg-slate-900/70 border border-slate-800/80 font-mono-num">
                  <span className="text-slate-400">Absorption Rate:</span>
                  <span className="text-emerald-400 font-bold">Dynamic (f(h))</span>
                </div>
                <div className="flex items-center justify-between text-xs p-2.5 rounded-lg bg-slate-900/70 border border-slate-800/80 font-mono-num">
                  <span className="text-slate-400">Overflow Threshold:</span>
                  <span className="text-amber-400 font-bold">Q_in &gt; Q_pipe_cap</span>
                </div>
              </div>
            </div>

            <div className="mt-8 flex items-center justify-between pt-4 border-t border-slate-800/80">
              <span className="text-xs text-slate-400 font-mono-num">Pumps & Outfall Tracking</span>
              <button 
                onClick={() => onExploreFeature('drainage')}
                className="inline-flex items-center text-xs font-semibold text-amber-400 group-hover:text-amber-300 cursor-pointer"
              >
                <span>View Graph</span>
                <ArrowRight className="ml-1 h-3.5 w-3.5 transition-transform group-hover:translate-x-1" />
              </button>
            </div>
          </motion.div>

          {/* Card 3: Resilient Emergency Routing (5 cols) */}
          <motion.div
            whileHover={{ y: -4 }}
            transition={{ duration: 0.2 }}
            className="md:col-span-5 glass-card rounded-3xl p-8 flex flex-col justify-between relative overflow-hidden group"
          >
            <div>
              <div className="flex items-center justify-between mb-6">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
                  <Navigation className="h-6 w-6" />
                </div>
                <span className="text-xs font-mono-num font-semibold text-emerald-400/90 px-3 py-1 rounded-full bg-emerald-950/60 border border-emerald-800/50">
                  PAIR C: ROUTING
                </span>
              </div>

              <h3 className="text-2xl font-bold text-white mb-3">
                Flood-Aware Evacuation Routing
              </h3>

              <p className="text-sm text-slate-300 leading-relaxed mb-4">
                OpenStreetMap road networks continuously penalized by forecasted water depth. Roads with &gt;0.15m water 
                slow traffic; roads with &gt;0.30m are severed, instantly forcing A* to find alternative dry corridors.
              </p>

              <div className="flex items-center space-x-2 text-xs text-slate-300 bg-slate-900/80 border border-slate-800 p-3 rounded-xl font-mono-num">
                <ShieldCheck className="h-4 w-4 text-emerald-400 shrink-0" />
                <span>Zero trapped vehicle guarantee via live depth penalties.</span>
              </div>
            </div>

            <div className="mt-8 flex items-center justify-between pt-4 border-t border-slate-800/80">
              <span className="text-xs text-slate-400 font-mono-num">Sub-second Dijkstra solver</span>
              <button 
                onClick={() => onExploreFeature('routing')}
                className="inline-flex items-center text-xs font-semibold text-emerald-400 group-hover:text-emerald-300 cursor-pointer"
              >
                <span>Test Route</span>
                <ArrowRight className="ml-1 h-3.5 w-3.5 transition-transform group-hover:translate-x-1" />
              </button>
            </div>
          </motion.div>

          {/* Card 4: Doppler Radar Nowcasting & Timeline (7 cols) */}
          <motion.div
            whileHover={{ y: -4 }}
            transition={{ duration: 0.2 }}
            className="md:col-span-7 glass-card rounded-3xl p-8 flex flex-col justify-between relative overflow-hidden group"
          >
            <div className="absolute top-0 left-1/3 w-64 h-64 bg-blue-500/10 blur-3xl rounded-full pointer-events-none" />

            <div>
              <div className="flex items-center justify-between mb-6">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-500/10 border border-blue-500/30 text-blue-400">
                  <CloudRain className="h-6 w-6" />
                </div>
                <span className="text-xs font-mono-num font-semibold text-blue-400/90 px-3 py-1 rounded-full bg-blue-950/60 border border-blue-800/50">
                  METEOROLOGY
                </span>
              </div>

              <h3 className="text-2xl font-bold text-white mb-3">
                0–180 Minute Doppler Radar Nowcast
              </h3>

              <p className="text-sm text-slate-300 leading-relaxed mb-6">
                Ingests radar reflectivity (dBZ) and uses optical flow extrapolation to predict storm cell displacement. 
                Generates continuous 5-minute precipitation snapshots feeding the hydrodynamic overland model.
              </p>

              {/* Timeline Step Visual Indicator */}
              <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800/90">
                <div className="flex items-center justify-between text-xs text-slate-400 mb-2 font-mono-num">
                  <span>FORECAST HORIZONS</span>
                  <span className="text-cyan-400">5-MINUTE DISCRETE TIMESTEPS</span>
                </div>
                <div className="grid grid-cols-6 gap-2 text-center">
                  {['T+0m', 'T+30m', 'T+60m', 'T+90m', 'T+120m', 'T+180m'].map((time, idx) => (
                    <div 
                      key={time} 
                      className={`py-2 rounded-lg font-mono-num text-xs font-bold ${
                        idx === 0 
                          ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40' 
                          : 'bg-slate-800/50 text-slate-400 border border-slate-700/40'
                      }`}
                    >
                      {time}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="mt-8 flex items-center justify-between pt-4 border-t border-slate-800/80">
              <span className="text-xs text-slate-400 font-mono-num">Optical Flow Tracking</span>
              <button 
                onClick={() => onExploreFeature('radar')}
                className="inline-flex items-center text-xs font-semibold text-blue-400 group-hover:text-blue-300 cursor-pointer"
              >
                <span>View Timeline</span>
                <ArrowRight className="ml-1 h-3.5 w-3.5 transition-transform group-hover:translate-x-1" />
              </button>
            </div>
          </motion.div>

        </div>

      </div>

    </section>
  );
};
