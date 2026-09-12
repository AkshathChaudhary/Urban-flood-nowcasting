import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { 
  ArrowRight, 
  Radio, 
  ShieldCheck, 
  Compass, 
  MapPin, 
  Maximize2,
  Play
} from 'lucide-react';

interface LandingHeroProps {
  onLaunchCommandCenter: () => void;
  onSelectScenario: (scenario: string) => void;
}

export const LandingHero: React.FC<LandingHeroProps> = ({
  onLaunchCommandCenter,
  onSelectScenario,
}) => {
  const [activeTab, setActiveTab] = useState<'depth' | 'routing' | 'drainage'>('depth');
  const [activeHorizon, setActiveHorizon] = useState<string>('T+60m');

  const scrollToExplore = () => {
    const el = document.getElementById('product-preview');
    el?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <div className="relative isolate overflow-hidden min-h-screen flex flex-col justify-start px-4 sm:px-6 lg:px-8 pt-12 pb-24">
      
      {/* Luminous Ambient Lights & High-Tech Cyber Grid */}
      <div className="absolute inset-0 -z-10 overflow-hidden pointer-events-none">
        {/* Rich High-Luminance Atmospheric Glows */}
        <div className="absolute -top-24 left-1/2 -translate-x-1/2 w-[1000px] h-[650px] bg-gradient-to-b from-cyan-400/35 via-blue-600/25 to-indigo-700/18 blur-[130px] rounded-full pointer-events-none animate-pulse [animation-duration:8s]" />
        <div className="absolute top-1/4 -right-24 w-[700px] h-[600px] bg-cyan-400/28 blur-[140px] rounded-full pointer-events-none" />
        <div className="absolute top-1/3 -left-28 w-[650px] h-[550px] bg-blue-500/25 blur-[130px] rounded-full pointer-events-none" />
        <div className="absolute bottom-10 left-1/2 -translate-x-1/2 w-[900px] h-[400px] bg-teal-400/22 blur-[140px] rounded-full pointer-events-none" />

        {/* High-Tech Grid Overlay Pattern */}
        <div 
          className="absolute inset-0 opacity-[0.10] pointer-events-none"
          style={{
            backgroundImage: `radial-gradient(circle at 1px 1px, #38bdf8 1.4px, transparent 0)`,
            backgroundSize: '32px 32px'
          }}
        />
      </div>

      {/* Main Hero Header */}
      <div className="mx-auto max-w-5xl w-full flex flex-col items-center text-center pt-8 sm:pt-14 pb-12">

        {/* Huge Brand Typography */}
        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="text-6xl sm:text-7xl lg:text-8xl font-black tracking-tight text-white mb-2 drop-shadow-[0_0_40px_rgba(6,182,212,0.4)]"
        >
          FLOW<span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-sky-300">S</span>
        </motion.h1>

        {/* Subtitle Name */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.15 }}
          className="text-base sm:text-xl font-medium text-slate-200 tracking-wide mb-3"
        >
          Flood Level Optimised Warning & Safety
        </motion.div>

        {/* Tagline */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="text-lg sm:text-2xl font-serif italic text-transparent bg-clip-text bg-gradient-to-r from-cyan-200 via-sky-100 to-blue-200 mb-6 tracking-wide drop-shadow-[0_0_20px_rgba(56,189,248,0.3)]"
        >
          &ldquo;Predict. Visualize. Respond.&rdquo;
        </motion.div>

        {/* Short Description */}
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.25 }}
          className="text-base sm:text-lg text-slate-300 max-w-2xl leading-relaxed mb-8"
        >
          FLOWS provides real-time flood monitoring, coupled 2D hydrodynamic prediction, 
          risk visualization, and safer evacuation decisions before streets inundate.
        </motion.p>

        {/* Hero CTA Button Group */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="flex flex-wrap items-center justify-center gap-4 w-full sm:w-auto"
        >
          <button
            onClick={scrollToExplore}
            className="inline-flex items-center justify-center rounded-xl border border-slate-700/90 bg-slate-900/80 hover:bg-slate-800/90 px-6 py-3.5 text-sm font-semibold text-slate-100 hover:text-white transition-all duration-200 cursor-pointer backdrop-blur-md hover:border-cyan-500/40 hover:shadow-lg hover:shadow-cyan-500/10"
          >
            <span>Explore FLOWS</span>
          </button>

          <button
            onClick={onLaunchCommandCenter}
            className="group relative inline-flex items-center justify-center rounded-xl bg-gradient-to-r from-cyan-400 via-teal-400 to-blue-500 px-7 py-3.5 text-sm font-semibold text-slate-950 shadow-xl shadow-cyan-400/30 hover:shadow-cyan-400/50 hover:brightness-110 active:scale-95 transition-all duration-200 cursor-pointer ring-2 ring-cyan-300/30 font-sans"
          >
            <span className="font-bold tracking-tight">View Live Dashboard</span>
            <ArrowRight className="ml-2 h-4 w-4 text-slate-950 transition-transform group-hover:translate-x-1 stroke-[2.5]" />
          </button>
        </motion.div>

      </div>

      {/* Product Visual: Futuristic Preview of the FLOWS Flood Monitoring Dashboard */}
      <motion.div
        id="product-preview"
        initial={{ opacity: 0, y: 35 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, delay: 0.35 }}
        className="mx-auto max-w-6xl w-full"
      >
        <div className="relative rounded-2xl sm:rounded-3xl border border-cyan-500/30 bg-slate-950/75 p-2 sm:p-3.5 shadow-2xl shadow-cyan-500/15 backdrop-blur-xl group">
          
          {/* Subtle Outer Neon Accent Lines */}
          <div className="absolute -inset-px rounded-2xl sm:rounded-3xl bg-gradient-to-b from-cyan-400/45 via-blue-500/20 to-transparent -z-10 opacity-80 group-hover:opacity-100 transition-opacity" />

          {/* Window Chrome Header */}
          <div className="flex items-center justify-between px-3 sm:px-4 py-2.5 rounded-t-xl bg-slate-900/70 border-b border-slate-800/80 text-xs font-mono text-slate-400">
            <div className="flex items-center space-x-2">
              <div className="flex space-x-1.5">
                <div className="h-2.5 w-2.5 rounded-full bg-slate-700" />
                <div className="h-2.5 w-2.5 rounded-full bg-slate-700" />
                <div className="h-2.5 w-2.5 rounded-full bg-slate-700" />
              </div>
              <span className="text-[11px] text-slate-300 font-semibold pl-2 hidden sm:inline">
                FLOWS COMMAND CENTER · MUMBAI SECTOR
              </span>
            </div>

            {/* Quick Layer Switcher */}
            <div className="flex items-center space-x-1 sm:space-x-1.5 bg-slate-950/60 p-1 rounded-lg border border-slate-800 text-[11px]">
              <button
                onClick={() => setActiveTab('depth')}
                className={`px-2 py-0.5 rounded cursor-pointer transition-colors ${
                  activeTab === 'depth' ? 'bg-cyan-500/20 text-cyan-300 font-medium' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Flood Raster
              </button>
              <button
                onClick={() => setActiveTab('routing')}
                className={`px-2 py-0.5 rounded cursor-pointer transition-colors ${
                  activeTab === 'routing' ? 'bg-cyan-500/20 text-cyan-300 font-medium' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                A* Routes
              </button>
              <button
                onClick={() => setActiveTab('drainage')}
                className={`px-2 py-0.5 rounded cursor-pointer transition-colors ${
                  activeTab === 'drainage' ? 'bg-cyan-500/20 text-cyan-300 font-medium' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Hydraulics
              </button>
            </div>

            <div className="flex items-center space-x-2">
              <span className="hidden md:inline-block text-[10px] text-emerald-400 font-mono bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-800/40">
                10m GRID ONLINE
              </span>
              <button
                onClick={onLaunchCommandCenter}
                className="flex items-center space-x-1 text-cyan-400 hover:text-cyan-300 cursor-pointer p-1 rounded hover:bg-slate-800/60"
                title="Launch full screen dashboard"
              >
                <Maximize2 className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>

          {/* Interactive Simulated Preview Canvas Area */}
          <div className="relative w-full h-[320px] sm:h-[440px] lg:h-[500px] rounded-b-xl bg-slate-950 overflow-hidden border border-slate-900 flex flex-col justify-between">
            
            {/* GIS Simulated Grid Topography Background */}
            <div 
              className="absolute inset-0 opacity-20"
              style={{
                backgroundImage: `
                  linear-gradient(to right, rgba(6, 182, 212, 0.15) 1px, transparent 1px),
                  linear-gradient(to bottom, rgba(6, 182, 212, 0.15) 1px, transparent 1px)
                `,
                backgroundSize: '40px 40px'
              }}
            />

            {/* Simulated River Vector (Mithi River channel in BKC) */}
            <svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 800 500" preserveAspectRatio="none">
              <path 
                d="M 50,450 C 200,420 320,310 420,240 C 520,170 650,160 780,80" 
                fill="none" 
                stroke="#0891b2" 
                strokeWidth="12" 
                strokeOpacity="0.4" 
              />
              <path 
                d="M 50,450 C 200,420 320,310 420,240 C 520,170 650,160 780,80" 
                fill="none" 
                stroke="#22d3ee" 
                strokeWidth="4" 
                strokeDasharray="6 4"
                strokeOpacity="0.8" 
              />

              {/* Road Network Grid Lines */}
              <path d="M 120,50 L 120,450" stroke="#334155" strokeWidth="1.5" strokeOpacity="0.6" />
              <path d="M 280,30 L 280,480" stroke="#334155" strokeWidth="2" strokeOpacity="0.7" />
              <path d="M 450,20 L 450,470" stroke="#334155" strokeWidth="1.5" strokeOpacity="0.6" />
              <path d="M 620,40 L 620,480" stroke="#334155" strokeWidth="2" strokeOpacity="0.7" />
              <path d="M 40,140 L 760,140" stroke="#334155" strokeWidth="2" strokeOpacity="0.7" />
              <path d="M 50,290 L 750,290" stroke="#334155" strokeWidth="2" strokeOpacity="0.7" />
              <path d="M 80,400 L 740,400" stroke="#334155" strokeWidth="1.5" strokeOpacity="0.6" />

              {/* Simulated Safe A* Evacuation Route (Emerald Green) */}
              <path 
                d="M 120,400 L 280,400 L 280,290 L 450,290 L 450,140 L 620,140" 
                fill="none" 
                stroke="#10b981" 
                strokeWidth="4" 
                strokeLinecap="round"
                strokeLinejoin="round"
                filter="drop-shadow(0 0 8px rgba(16, 185, 129, 0.8))"
              />

              {/* Severed Flooded Route (Dashed Red with Warning X) */}
              <path 
                d="M 280,400 L 420,240" 
                fill="none" 
                stroke="#ef4444" 
                strokeWidth="2.5" 
                strokeDasharray="5 5"
                strokeOpacity="0.8" 
              />
            </svg>

            {/* Depth Heatmap Inundation Blobs */}
            <div className="absolute top-[38%] left-[45%] w-40 h-32 rounded-full bg-cyan-500/25 blur-xl pointer-events-none" />
            <div className="absolute top-[42%] left-[48%] w-24 h-20 rounded-full bg-blue-600/35 blur-lg pointer-events-none" />
            <div className="absolute top-[45%] left-[50%] w-12 h-10 rounded-full bg-indigo-700/40 blur-sm pointer-events-none" />

            {/* Hotspot Markers on Map */}
            <div className="absolute top-[46%] left-[52%] -translate-x-1/2 -translate-y-1/2 flex flex-col items-center">
              <span className="relative flex h-4 w-4">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-4 w-4 bg-rose-500 items-center justify-center text-[8px] font-bold text-white font-mono">
                  !
                </span>
              </span>
              <span className="mt-1 px-1.5 py-0.5 rounded bg-slate-900/90 text-[9px] font-mono text-rose-300 border border-rose-800">
                BKC Junction · 0.34m
              </span>
            </div>

            <div className="absolute top-[28%] left-[25%] -translate-x-1/2 -translate-y-1/2 flex flex-col items-center">
              <span className="relative flex h-3.5 w-3.5">
                <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-amber-500 items-center justify-center text-[8px] font-bold text-white font-mono" />
              </span>
              <span className="mt-1 px-1.5 py-0.5 rounded bg-slate-900/90 text-[9px] font-mono text-amber-300 border border-amber-800">
                Kurla West · 0.18m
              </span>
            </div>

            {/* Top Overlay Card: Telemetry Overview */}
            <div className="relative z-10 p-3 sm:p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pointer-events-none">
              
              <div className="flex flex-col p-2.5 sm:p-3 rounded-xl bg-slate-900/85 border border-slate-800/90 backdrop-blur-md shadow-lg pointer-events-auto">
                <div className="flex items-center space-x-2 text-xs font-mono text-cyan-400 mb-1">
                  <Radio className="h-3.5 w-3.5 animate-pulse" />
                  <span>DOPPLER RADAR DWR</span>
                  <span className="text-slate-500">·</span>
                  <span className="text-slate-300">{activeHorizon} Horizon</span>
                </div>
                <div className="flex items-baseline space-x-3">
                  <span className="text-xl sm:text-2xl font-bold font-mono text-white">
                    124 <span className="text-xs font-normal text-slate-400 font-mono">mm/h</span>
                  </span>
                  <span className="text-xs text-rose-400 font-mono font-medium">
                    Heavy Cloudburst Cell
                  </span>
                </div>
              </div>

              <div className="flex items-center space-x-2 pointer-events-auto">
                <div className="p-2.5 rounded-xl bg-slate-900/85 border border-slate-800/90 backdrop-blur-md text-right font-mono">
                  <div className="text-[10px] text-slate-400">A* SAFE PATH</div>
                  <div className="text-xs font-bold text-emerald-400 flex items-center justify-end space-x-1">
                    <ShieldCheck className="h-3 w-3" />
                    <span>Dry Corridor Active</span>
                  </div>
                </div>

                <button
                  onClick={() => onSelectScenario('mumbai_severe')}
                  className="hidden md:inline-flex items-center space-x-1.5 px-3 py-2.5 rounded-xl bg-slate-900/90 hover:bg-slate-800 border border-slate-700/80 text-xs font-semibold text-slate-200 hover:text-white transition-colors cursor-pointer shadow-md"
                >
                  <Play className="h-3.5 w-3.5 text-cyan-400 fill-cyan-400/20" />
                  <span>Test 150mm Event</span>
                </button>

                <button
                  onClick={onLaunchCommandCenter}
                  className="hidden sm:inline-flex items-center space-x-1.5 px-3 py-2.5 rounded-xl bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/40 text-xs font-semibold text-cyan-200 hover:text-white transition-colors cursor-pointer shadow-md"
                >
                  <Compass className="h-4 w-4 text-cyan-400 animate-spin [animation-duration:10s]" />
                  <span>Launch Live</span>
                </button>
              </div>

            </div>

            {/* Bottom Overlay: Forecast Timeline Bar */}
            <div className="relative z-10 p-3 sm:p-4 border-t border-slate-800/80 bg-slate-950/90 backdrop-blur-md flex flex-col sm:flex-row items-center justify-between gap-2.5">
              <div className="flex items-center space-x-2 text-xs font-mono text-slate-400">
                <MapPin className="h-3.5 w-3.5 text-cyan-400" />
                <span className="hidden sm:inline">FORECAST HORIZON:</span>
              </div>

              {/* Scrubber Buttons */}
              <div className="grid grid-cols-6 gap-1.5 w-full sm:w-auto">
                {['T+0m', 'T+30m', 'T+60m', 'T+90m', 'T+120m', 'T+180m'].map((step) => (
                  <button
                    key={step}
                    onClick={() => setActiveHorizon(step)}
                    className={`py-1 px-2.5 rounded-lg text-xs font-mono font-semibold transition-all cursor-pointer ${
                      activeHorizon === step 
                        ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/30' 
                        : 'bg-slate-900 text-slate-400 hover:bg-slate-800 hover:text-white border border-slate-800'
                    }`}
                  >
                    {step}
                  </button>
                ))}
              </div>

              <div className="hidden lg:flex items-center space-x-2 text-[11px] font-mono text-slate-400">
                <span>Saint-Venant 2D</span>
                <span>·</span>
                <span className="text-cyan-400">40,000 Cells</span>
              </div>
            </div>

          </div>

        </div>
      </motion.div>

    </div>
  );
};

