import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { 
  Waves, 
  GitFork, 
  Navigation, 
  CloudRain, 
  Cpu, 
  ArrowRight,
  Truck,
  Car,
  Shield,
  Play,
  Layers,
  Server,
  Globe2
} from 'lucide-react';

interface BentoShowcaseProps {
  onExploreFeature: (featureId: string) => void;
  onSelectScenario?: (scenario: string) => void;
}

export const BentoShowcase: React.FC<BentoShowcaseProps> = ({ 
  onExploreFeature,
  onSelectScenario,
}) => {
  const [selectedHorizon, setSelectedHorizon] = useState<string>('T+60m');

  const horizons = [
    { label: 'T+0m', desc: 'Current State' },
    { label: 'T+30m', desc: 'Cell Inundation' },
    { label: 'T+60m', desc: 'Peak Surcharge' },
    { label: 'T+90m', desc: 'Overland Flux' },
    { label: 'T+120m', desc: 'Drainage Peak' },
    { label: 'T+180m', desc: 'Recession Phase' },
  ];

  const scenarios = [
    {
      id: 'mumbai_severe',
      title: 'Mumbai 150mm Cloudburst',
      city: 'Mumbai (BKC Sector)',
      desc: 'Simulate an extreme localized downpour exceeding drainage capacity with instantaneous manhole surcharge.',
      severity: 'Critical Alert',
      badgeColor: 'text-rose-400 bg-rose-950/40 border-rose-800/40',
    },
    {
      id: 'mumbai_river_spill',
      title: 'Mithi River Bank Spillover',
      city: 'Mumbai (BKC / Kurla)',
      desc: 'High-tide coupled river breach sending overland flood vectors across major transit arteries.',
      severity: 'High Surcharge',
      badgeColor: 'text-amber-400 bg-amber-950/40 border-amber-800/40',
    },
    {
      id: 'kolkata_drainage_choke',
      title: 'EM Bypass Drainage Failure',
      city: 'Kolkata (Science City)',
      desc: '40% stormwater canal blockage testing hospital evacuation corridors and arterial detours.',
      severity: 'Corridor Hazard',
      badgeColor: 'text-cyan-400 bg-cyan-950/40 border-cyan-800/40',
    },
  ];

  return (
    <div className="relative bg-transparent text-slate-100">
      
      {/* SECTION 1: Core Physical Intelligence Grid (Monitoring & Prediction) */}
      <section id="features" className="relative px-4 sm:px-6 lg:px-8 py-24 sm:py-32 border-t border-slate-900/80">
        <div className="mx-auto max-w-7xl">
          
          <div className="flex flex-col items-center text-center mb-16 sm:mb-20">
            <span className="text-xs font-mono font-semibold tracking-widest text-cyan-400 uppercase mb-3">
              INTELLIGENCE & PREDICTION
            </span>
            <h2 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight max-w-3xl">
              High-Precision Physics for <span className="bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">Urban Flood Dynamics</span>
            </h2>
            <p className="mt-4 text-base sm:text-lg text-slate-400 max-w-2xl font-normal leading-relaxed">
              FLOWS bridges atmospheric nowcasting with 2D overland hydrodynamics and subterranean hydraulic conduit networks.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-12 gap-6 lg:gap-8">
            
            {/* 1. Real-Time Doppler Monitoring (7 cols) */}
            <motion.div
              whileHover={{ y: -3 }}
              transition={{ duration: 0.2 }}
              className="md:col-span-7 rounded-2xl sm:rounded-3xl p-7 sm:p-9 border border-slate-800/80 bg-slate-900/30 backdrop-blur-sm flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-6">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
                    <CloudRain className="h-5 w-5" />
                  </div>
                  <span className="text-[11px] font-mono font-medium text-cyan-400 px-3 py-1 rounded-full bg-cyan-950/40 border border-cyan-800/30">
                    REAL-TIME MONITORING
                  </span>
                </div>

                <h3 className="text-2xl font-bold text-white mb-3">
                  0–180 Minute Doppler Radar Nowcast
                </h3>

                <p className="text-sm text-slate-300 leading-relaxed mb-6 font-normal">
                  Ingests live Doppler radar reflectivity (dBZ) and executes optical flow extrapolation to predict storm cell trajectories. 
                  Generates continuous discrete precipitation snapshots feeding the coupled hydrodynamic surface model.
                </p>

                {/* Horizon Stepper */}
                <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800/70">
                  <div className="flex items-center justify-between text-xs text-slate-400 mb-2 font-mono">
                    <span>NOWCAST HORIZONS</span>
                    <span className="text-cyan-400">SELECT TIMESTEP</span>
                  </div>
                  <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 text-center">
                    {horizons.map((h) => (
                      <button
                        key={h.label}
                        onClick={() => setSelectedHorizon(h.label)}
                        className={`py-2 px-1 rounded-lg font-mono text-xs font-semibold transition-all cursor-pointer ${
                          selectedHorizon === h.label 
                            ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/50 shadow-sm' 
                            : 'bg-slate-900/60 text-slate-400 border border-slate-800/40 hover:text-slate-200'
                        }`}
                      >
                        <div>{h.label}</div>
                        <div className="text-[8px] font-normal opacity-70 mt-0.5 truncate">{h.desc}</div>
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <div className="mt-8 flex items-center justify-between pt-4 border-t border-slate-800/50">
                <span className="text-xs text-slate-400 font-mono">Continuous 5-Min Time-Step</span>
                <button 
                  onClick={() => onExploreFeature('radar')}
                  className="inline-flex items-center text-xs font-semibold text-cyan-400 hover:text-cyan-300 transition-colors cursor-pointer"
                >
                  <span>Explore Radar</span>
                  <ArrowRight className="ml-1 h-3.5 w-3.5" />
                </button>
              </div>
            </motion.div>

            {/* 2. Hydrodynamic Flood Prediction (5 cols) */}
            <motion.div
              whileHover={{ y: -3 }}
              transition={{ duration: 0.2 }}
              className="md:col-span-5 rounded-2xl sm:rounded-3xl p-7 sm:p-9 border border-slate-800/80 bg-slate-900/30 backdrop-blur-sm flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-6">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500/10 border border-blue-500/30 text-blue-400">
                    <Waves className="h-5 w-5" />
                  </div>
                  <span className="text-[11px] font-mono font-medium text-blue-400 px-3 py-1 rounded-full bg-blue-950/40 border border-blue-800/30">
                    HYDRODYNAMICS
                  </span>
                </div>

                <h3 className="text-2xl font-bold text-white mb-3">
                  2D Shallow-Water Simulation
                </h3>

                <p className="text-sm text-slate-300 leading-relaxed mb-6 font-normal">
                  Finite-difference numerical solver across a 200×200 grid (10m cells). Computes elevation flux transfer, 
                  depression ponding, and slope runoffs with strict mass conservation (&gt;99.8%).
                </p>

                <div className="grid grid-cols-2 gap-3 pt-2">
                  <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/60 font-mono">
                    <div className="text-[10px] text-slate-400">CELL RESOLUTION</div>
                    <div className="text-lg font-bold text-cyan-300 mt-0.5">10 × 10 m</div>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/60 font-mono">
                    <div className="text-[10px] text-slate-400">TIME STEP Δt</div>
                    <div className="text-lg font-bold text-white mt-0.5">300 sec</div>
                  </div>
                </div>
              </div>

              <div className="mt-8 flex items-center justify-between pt-4 border-t border-slate-800/50">
                <span className="text-xs text-slate-400 font-mono">Saint-Venant 2D</span>
                <button 
                  onClick={() => onExploreFeature('hydrodynamics')}
                  className="inline-flex items-center text-xs font-semibold text-blue-400 hover:text-blue-300 transition-colors cursor-pointer"
                >
                  <span>View Solver</span>
                  <ArrowRight className="ml-1 h-3.5 w-3.5" />
                </button>
              </div>
            </motion.div>

            {/* 3. Subterranean Pipe Hydraulics (5 cols) */}
            <motion.div
              whileHover={{ y: -3 }}
              transition={{ duration: 0.2 }}
              className="md:col-span-5 rounded-2xl sm:rounded-3xl p-7 sm:p-9 border border-slate-800/80 bg-slate-900/30 backdrop-blur-sm flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-6">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400">
                    <GitFork className="h-5 w-5" />
                  </div>
                  <span className="text-[11px] font-mono font-medium text-amber-400 px-3 py-1 rounded-full bg-amber-950/40 border border-amber-800/30">
                    DRAINAGE HYDRAULICS
                  </span>
                </div>

                <h3 className="text-2xl font-bold text-white mb-3">
                  Subsurface Pipe Surcharge
                </h3>

                <p className="text-sm text-slate-300 leading-relaxed mb-4 font-normal">
                  Directed hydraulic network modeling stormwater pipes via Manning&apos;s formula. When runoff exceeds pipe intake capacity, 
                  manholes calculate back-surcharge, expelling trapped water onto surface streets.
                </p>

                <div className="space-y-2 mt-4 text-xs font-mono">
                  <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/60">
                    <span className="text-slate-400">Pipe Head Loss:</span>
                    <span className="text-amber-400 font-semibold">Manning Eq. (n=0.013)</span>
                  </div>
                  <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/60">
                    <span className="text-slate-400">Manhole Overflow:</span>
                    <span className="text-rose-400 font-semibold">Q_surcharge &gt; 0</span>
                  </div>
                </div>
              </div>

              <div className="mt-8 flex items-center justify-between pt-4 border-t border-slate-800/50">
                <span className="text-xs text-slate-400 font-mono">NetworkX Topology</span>
                <button 
                  onClick={() => onExploreFeature('drainage')}
                  className="inline-flex items-center text-xs font-semibold text-amber-400 hover:text-amber-300 transition-colors cursor-pointer"
                >
                  <span>Examine Network</span>
                  <ArrowRight className="ml-1 h-3.5 w-3.5" />
                </button>
              </div>
            </motion.div>

            {/* 4. A* Evacuation Routing (7 cols) */}
            <motion.div
              whileHover={{ y: -3 }}
              transition={{ duration: 0.2 }}
              className="md:col-span-7 rounded-2xl sm:rounded-3xl p-7 sm:p-9 border border-slate-800/80 bg-slate-900/30 backdrop-blur-sm flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-6">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
                    <Navigation className="h-5 w-5" />
                  </div>
                  <span className="text-[11px] font-mono font-medium text-emerald-400 px-3 py-1 rounded-full bg-emerald-950/40 border border-emerald-800/30">
                    EVACUATION ROUTING
                  </span>
                </div>

                <h3 className="text-2xl font-bold text-white mb-3">
                  Flood-Penalized A* Emergency Corridors
                </h3>

                <p className="text-sm text-slate-300 leading-relaxed mb-6 font-normal">
                  OpenStreetMap road graph continuously re-weighted by forecasted water depths. 
                  Streets with deep inundation are severed in milliseconds, steering rescue responders and evacuees along safe dry corridors.
                </p>

                {/* Vehicle Threshold Matrix */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                  <div className="flex items-center justify-between sm:flex-col sm:items-start p-3 rounded-xl bg-slate-950/60 border border-slate-800/70">
                    <div className="flex items-center space-x-1.5 text-xs text-slate-300">
                      <Car className="h-3.5 w-3.5 text-slate-400" />
                      <span>Standard Car</span>
                    </div>
                    <span className="text-sm font-bold font-mono text-amber-400 sm:mt-1">0.15m Limit</span>
                  </div>

                  <div className="flex items-center justify-between sm:flex-col sm:items-start p-3 rounded-xl bg-slate-950/60 border border-slate-800/70">
                    <div className="flex items-center space-x-1.5 text-xs text-slate-300">
                      <Shield className="h-3.5 w-3.5 text-emerald-400" />
                      <span>Ambulance</span>
                    </div>
                    <span className="text-sm font-bold font-mono text-emerald-400 sm:mt-1">0.30m Limit</span>
                  </div>

                  <div className="flex items-center justify-between sm:flex-col sm:items-start p-3 rounded-xl bg-slate-950/60 border border-slate-800/70">
                    <div className="flex items-center space-x-1.5 text-xs text-slate-300">
                      <Truck className="h-3.5 w-3.5 text-cyan-400" />
                      <span>Heavy 4x4</span>
                    </div>
                    <span className="text-sm font-bold font-mono text-cyan-400 sm:mt-1">0.50m Limit</span>
                  </div>
                </div>
              </div>

              <div className="mt-8 flex items-center justify-between pt-4 border-t border-slate-800/50">
                <span className="text-xs text-slate-400 font-mono">&lt;0.4s A* Recalculation</span>
                <button 
                  onClick={() => onExploreFeature('routing')}
                  className="inline-flex items-center text-xs font-semibold text-emerald-400 hover:text-emerald-300 transition-colors cursor-pointer"
                >
                  <span>Test Routes</span>
                  <ArrowRight className="ml-1 h-3.5 w-3.5" />
                </button>
              </div>
            </motion.div>

          </div>

        </div>
      </section>

      {/* SECTION 2: How FLOWS Works (The 3-Tier Pipeline) */}
      <section id="pipeline" className="relative px-4 sm:px-6 lg:px-8 py-24 sm:py-32 border-t border-slate-900 bg-slate-950/50">
        <div className="mx-auto max-w-7xl">
          
          <div className="flex flex-col items-center text-center mb-16 sm:mb-20">
            <span className="text-xs font-mono font-semibold tracking-widest text-cyan-400 uppercase mb-3">
              SYSTEM WORKFLOW
            </span>
            <h2 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight">
              How FLOWS Works
            </h2>
            <p className="mt-4 text-base sm:text-lg text-slate-400 max-w-2xl font-normal leading-relaxed">
              From Doppler radar ingestion to sub-second responder dispatch in three synchronized stages.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 relative">
            
            {/* Step 1 */}
            <div className="relative rounded-2xl p-7 border border-slate-800/80 bg-slate-900/20 backdrop-blur-sm flex flex-col justify-between">
              <div>
                <div className="text-3xl font-black font-mono text-cyan-500/30 mb-4">01</div>
                <h3 className="text-xl font-bold text-white mb-2">Ingest & Nowcast</h3>
                <p className="text-sm text-slate-400 leading-relaxed font-normal">
                  Continuous ingestion of IMD Doppler radar reflectivity (dBZ). Optical flow algorithms compute storm displacement vectors to produce rolling 0–180m discrete precipitation timesteps.
                </p>
              </div>
              <div className="mt-6 pt-4 border-t border-slate-800/60 text-xs font-mono text-cyan-400">
                Precipitation Extrapolation
              </div>
            </div>

            {/* Step 2 */}
            <div className="relative rounded-2xl p-7 border border-slate-800/80 bg-slate-900/20 backdrop-blur-sm flex flex-col justify-between">
              <div>
                <div className="text-3xl font-black font-mono text-blue-500/30 mb-4">02</div>
                <h3 className="text-xl font-bold text-white mb-2">Couple Hydro & Pipes</h3>
                <p className="text-sm text-slate-400 leading-relaxed font-normal">
                  Surface rainfall is routed through digital elevation terrain while drainage conduits simulate intake. Surcharging pipes spit water back into overland depressions, modeling actual flood depths.
                </p>
              </div>
              <div className="mt-6 pt-4 border-t border-slate-800/60 text-xs font-mono text-blue-400">
                Saint-Venant + Manning Solver
              </div>
            </div>

            {/* Step 3 */}
            <div className="relative rounded-2xl p-7 border border-slate-800/80 bg-slate-900/20 backdrop-blur-sm flex flex-col justify-between">
              <div>
                <div className="text-3xl font-black font-mono text-emerald-500/30 mb-4">03</div>
                <h3 className="text-xl font-bold text-white mb-2">Reroute Responders</h3>
                <p className="text-sm text-slate-400 leading-relaxed font-normal">
                  Predicted water depths dynamically penalize road edge weights. Deeply flooded intersections are severed, steering ambulances and rescue teams along verified dry corridors.
                </p>
              </div>
              <div className="mt-6 pt-4 border-t border-slate-800/60 text-xs font-mono text-emerald-400">
                A* Flood-Penalized Graph
              </div>
            </div>

          </div>

        </div>
      </section>

      {/* SECTION 3: Technology Architecture */}
      <section id="technology" className="relative px-4 sm:px-6 lg:px-8 py-24 sm:py-32 border-t border-slate-900">
        <div className="mx-auto max-w-7xl">
          
          <div className="flex flex-col items-center text-center mb-16 sm:mb-20">
            <span className="text-xs font-mono font-semibold tracking-widest text-cyan-400 uppercase mb-3">
              SPECIFICATIONS
            </span>
            <h2 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight">
              Technology Stack
            </h2>
            <p className="mt-4 text-base sm:text-lg text-slate-400 max-w-2xl font-normal leading-relaxed">
              Engineered with industrial computational libraries and high-throughput asynchronous services.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            
            <div className="p-6 rounded-2xl border border-slate-800/70 bg-slate-900/20">
              <div className="flex items-center space-x-2 text-cyan-400 mb-3">
                <Cpu className="h-4 w-4" />
                <span className="text-xs font-mono uppercase tracking-wider font-semibold">Physics Engine</span>
              </div>
              <h4 className="text-base font-bold text-white mb-1">NumPy & SciPy</h4>
              <p className="text-xs text-slate-400 leading-relaxed">
                Vectorized finite-difference matrix math computing elevation runoff flux across 40,000 grid cells.
              </p>
            </div>

            <div className="p-6 rounded-2xl border border-slate-800/70 bg-slate-900/20">
              <div className="flex items-center space-x-2 text-teal-400 mb-3">
                <Layers className="h-4 w-4" />
                <span className="text-xs font-mono uppercase tracking-wider font-semibold">Drainage Graph</span>
              </div>
              <h4 className="text-base font-bold text-white mb-1">NetworkX</h4>
              <p className="text-xs text-slate-400 leading-relaxed">
                Directed graph solver resolving subterranean stormwater capacity, junctions, and manhole surcharge.
              </p>
            </div>

            <div className="p-6 rounded-2xl border border-slate-800/70 bg-slate-900/20">
              <div className="flex items-center space-x-2 text-emerald-400 mb-3">
                <Globe2 className="h-4 w-4" />
                <span className="text-xs font-mono uppercase tracking-wider font-semibold">GIS Map Layers</span>
              </div>
              <h4 className="text-base font-bold text-white mb-1">Leaflet & OSM</h4>
              <p className="text-xs text-slate-400 leading-relaxed">
                Hardware-accelerated GIS raster overlays, elevation contours, and OpenStreetMap graph traversals.
              </p>
            </div>

            <div className="p-6 rounded-2xl border border-slate-800/70 bg-slate-900/20">
              <div className="flex items-center space-x-2 text-blue-400 mb-3">
                <Server className="h-4 w-4" />
                <span className="text-xs font-mono uppercase tracking-wider font-semibold">Backend Core</span>
              </div>
              <h4 className="text-base font-bold text-white mb-1">FastAPI & Python</h4>
              <p className="text-xs text-slate-400 leading-relaxed">
                Sub-50ms REST endpoints pre-warming coupled simulation models for instantaneous scenario analysis.
              </p>
            </div>

          </div>

        </div>
      </section>

      {/* SECTION 4: Pre-Configured Emergency Scenarios */}
      <section className="relative px-4 sm:px-6 lg:px-8 py-24 sm:py-32 border-t border-slate-900 bg-slate-950/60">
        <div className="mx-auto max-w-7xl">
          
          <div className="flex flex-col sm:flex-row sm:items-end justify-between mb-12 gap-4">
            <div>
              <span className="text-xs font-mono font-semibold tracking-widest text-cyan-400 uppercase mb-2 block">
                SCENARIO BENCHMARKS
              </span>
              <h3 className="text-3xl font-extrabold text-white tracking-tight">
                Simulate Critical Flood Events
              </h3>
            </div>
            <p className="text-xs sm:text-sm text-slate-400 max-w-md font-normal">
              Execute real-world stress tests with one click to observe hydrodynamic propagation and automated responder rerouting.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {scenarios.map((sc) => (
              <div
                key={sc.id}
                className="rounded-2xl p-6 sm:p-7 flex flex-col justify-between border border-slate-800/90 bg-slate-900/30 hover:border-cyan-500/40 transition-all group"
              >
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className={`text-[10px] font-mono font-semibold px-2.5 py-0.5 rounded-full border ${sc.badgeColor}`}>
                      {sc.severity}
                    </span>
                    <span className="text-xs text-slate-400 font-mono">{sc.city}</span>
                  </div>
                  <h4 className="text-lg font-bold text-white mb-2 group-hover:text-cyan-300 transition-colors">
                    {sc.title}
                  </h4>
                  <p className="text-xs text-slate-400 leading-relaxed font-normal">
                    {sc.desc}
                  </p>
                </div>

                <div className="mt-8 pt-4 border-t border-slate-800/70">
                  <button
                    onClick={() => {
                      if (onSelectScenario) {
                        onSelectScenario(sc.id);
                      } else {
                        onExploreFeature(sc.id);
                      }
                    }}
                    className="w-full inline-flex items-center justify-center space-x-2 py-2.5 px-4 rounded-xl bg-slate-900 hover:bg-cyan-500/20 border border-slate-700/80 hover:border-cyan-500/50 text-xs font-semibold text-white transition-all cursor-pointer group-hover:shadow-md"
                  >
                    <Play className="h-3.5 w-3.5 text-cyan-400 fill-cyan-400/20" />
                    <span>Run Simulation</span>
                  </button>
                </div>
              </div>
            ))}
          </div>

        </div>
      </section>

      {/* SECTION 5: High-Impact Mission CTA */}
      <section className="relative px-4 sm:px-6 lg:px-8 py-24 sm:py-32 border-t border-slate-900 overflow-hidden">
        <div className="absolute inset-0 pointer-events-none -z-10">
          <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[600px] h-[300px] bg-gradient-to-t from-cyan-600/10 via-blue-600/5 to-transparent blur-[140px] rounded-full" />
        </div>

        <div className="mx-auto max-w-4xl text-center flex flex-col items-center">
          <span className="text-xs font-mono font-semibold tracking-widest text-cyan-400 uppercase mb-3">
            MISSION READINESS
          </span>
          <h2 className="text-3xl sm:text-5xl font-black text-white tracking-tight mb-4">
            Protect Urban Infrastructure Before Streets Submerge
          </h2>
          <p className="text-base sm:text-lg text-slate-400 max-w-2xl font-normal leading-relaxed mb-8">
            Experience the real-time GIS command center, inspect subterranean pipe surcharges, and calculate live flood-penalized evacuation routes.
          </p>

          <div className="flex flex-wrap items-center justify-center gap-4">
            <button
              onClick={() => onExploreFeature('command-center')}
              className="group relative inline-flex items-center justify-center rounded-xl bg-gradient-to-r from-cyan-500 via-teal-500 to-blue-600 px-7 py-3.5 text-sm font-semibold text-white shadow-lg shadow-cyan-500/25 hover:shadow-cyan-500/40 hover:brightness-110 active:scale-95 transition-all duration-200 cursor-pointer ring-1 ring-white/20"
            >
              <span>Launch Command Center</span>
              <ArrowRight className="ml-2 h-4 w-4 text-cyan-200 transition-transform group-hover:translate-x-1" />
            </button>

            <button
              onClick={() => onSelectScenario ? onSelectScenario('mumbai_severe') : onExploreFeature('mumbai_severe')}
              className="inline-flex items-center justify-center rounded-xl border border-slate-700/80 bg-slate-900/80 hover:bg-slate-800 px-6 py-3.5 text-sm font-semibold text-slate-200 hover:text-white transition-all duration-200 cursor-pointer"
            >
              <Play className="mr-2 h-4 w-4 text-cyan-400 fill-cyan-400/20" />
              <span>Simulate Cloudburst</span>
            </button>
          </div>
        </div>
      </section>

    </div>
  );
};

