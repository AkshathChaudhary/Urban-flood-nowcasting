import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { 
  ArrowRight, 
  Radio, 
  ShieldCheck, 
  Compass, 
  MapPin, 
  Maximize2,
  Play,
  CloudRain,
  Droplets,
  Navigation,
  Activity,
  Eye,
  EyeOff
} from 'lucide-react';

interface LandingHeroProps {
  onLaunchCommandCenter: () => void;
  onSelectScenario: (scenario: string) => void;
}

export const LandingHero: React.FC<LandingHeroProps> = ({
  onLaunchCommandCenter,
  onSelectScenario,
}) => {
  const [activeTab, setActiveTab] = useState<'radar' | 'depth' | 'routing' | 'drainage'>('radar');
  const [activeHorizon, setActiveHorizon] = useState<string>('T+60m');
  const [showTimeline, setShowTimeline] = useState<boolean>(true);

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
        
        {/* Category Pill Badge */}
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="inline-flex items-center space-x-2 rounded-full border border-cyan-400/30 bg-cyan-950/40 px-4 py-1.5 backdrop-blur-md mb-6 shadow-md shadow-cyan-500/15"
        >
          <span className="h-2 w-2 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_10px_#22d3ee]" />
          <span className="text-[11px] font-mono tracking-widest text-cyan-300 uppercase font-semibold">
            REAL-TIME FLOOD INTELLIGENCE
          </span>
        </motion.div>

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
                FLOWS COMMAND CENTER · REAL-TIME SIMULATION
              </span>
            </div>
            {/* Quick Layer Switcher */}
            <div className="flex items-center space-x-1 sm:space-x-1.5 bg-slate-950/60 p-1 rounded-lg border border-slate-800 text-[11px]">
              <button
                onClick={() => setActiveTab('radar')}
                className={`px-2.5 py-1 rounded cursor-pointer transition-colors ${
                  activeTab === 'radar' ? 'bg-cyan-500/25 text-cyan-300 font-semibold border border-cyan-500/40 shadow-sm' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Doppler Radar
              </button>
              <button
                onClick={() => setActiveTab('depth')}
                className={`px-2.5 py-1 rounded cursor-pointer transition-colors ${
                  activeTab === 'depth' ? 'bg-cyan-500/25 text-cyan-300 font-semibold border border-cyan-500/40 shadow-sm' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Flood Raster
              </button>
              <button
                onClick={() => setActiveTab('routing')}
                className={`px-2.5 py-1 rounded cursor-pointer transition-colors ${
                  activeTab === 'routing' ? 'bg-cyan-500/25 text-cyan-300 font-semibold border border-cyan-500/40 shadow-sm' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                A* Routes
              </button>
              <button
                onClick={() => setActiveTab('drainage')}
                className={`px-2.5 py-1 rounded cursor-pointer transition-colors ${
                  activeTab === 'drainage' ? 'bg-cyan-500/25 text-cyan-300 font-semibold border border-cyan-500/40 shadow-sm' : 'text-slate-400 hover:text-slate-200'
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
                onClick={() => setShowTimeline(!showTimeline)}
                className={`flex items-center space-x-1.5 px-2.5 py-1 rounded text-xs font-mono border cursor-pointer transition-colors ${
                  showTimeline 
                    ? 'bg-slate-800/90 text-slate-300 hover:text-white border-slate-700' 
                    : 'bg-cyan-500/20 text-cyan-300 hover:bg-cyan-500/30 border-cyan-500/40'
                }`}
                title={showTimeline ? "Hide forecast horizon timeline" : "Show forecast horizon timeline"}
              >
                {showTimeline ? <EyeOff className="h-3.5 w-3.5 text-cyan-400" /> : <Eye className="h-3.5 w-3.5 text-cyan-400" />}
                <span>{showTimeline ? 'Hide Timestamp' : 'Show Timestamp'}</span>
              </button>
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
          <div className="relative w-full h-[360px] sm:h-[460px] lg:h-[520px] rounded-b-xl bg-slate-950 overflow-hidden border border-slate-900 flex flex-col justify-between">
            
            {/* GIS Simulated Grid Topography Background */}
            <div 
              className="absolute inset-0 opacity-20 pointer-events-none"
              style={{
                backgroundImage: `
                  linear-gradient(to right, rgba(6, 182, 212, 0.15) 1px, transparent 1px),
                  linear-gradient(to bottom, rgba(6, 182, 212, 0.15) 1px, transparent 1px)
                `,
                backgroundSize: '40px 40px'
              }}
            />

            {/* LIVE SIMULATED RADAR SWEEP — Abstract, no city-specific data */}
            {activeTab === 'radar' && (
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div className="relative w-[300px] sm:w-[380px] lg:w-[440px] aspect-square rounded-full border border-cyan-500/30 flex items-center justify-center overflow-hidden">
                  
                  {/* Concentric Range Rings */}
                  <div className="absolute inset-4 rounded-full border border-cyan-500/25" />
                  <div className="absolute inset-16 sm:inset-20 rounded-full border border-cyan-500/20" />
                  <div className="absolute inset-28 sm:inset-36 rounded-full border border-cyan-500/15" />
                  <div className="absolute inset-40 sm:inset-52 rounded-full border border-cyan-500/10" />

                  {/* Center Crosshairs */}
                  <div className="absolute inset-x-0 top-1/2 h-[1px] bg-cyan-500/25" />
                  <div className="absolute inset-y-0 left-1/2 w-[1px] bg-cyan-500/25" />

                  {/* Rotating Radar Sweep Beam */}
                  <div className="absolute inset-0 rounded-full overflow-hidden pointer-events-none">
                    <div 
                      className="w-full h-full animate-radar-sweep origin-center"
                      style={{
                        background: 'conic-gradient(from 0deg, transparent 0deg, transparent 270deg, rgba(6, 182, 212, 0.45) 360deg)'
                      }}
                    />
                  </div>

                  {/* Abstract Storm Cell Blips */}
                  <div className="absolute top-[28%] left-[34%] w-9 h-9 rounded-full bg-red-500/40 blur-sm animate-pulse" />
                  <div className="absolute top-[28%] left-[34%] w-3.5 h-3.5 rounded-full bg-red-400 ring-4 ring-red-500/30" />
                  
                  <div className="absolute bottom-[35%] right-[28%] w-10 h-10 rounded-full bg-amber-500/35 blur-sm" />
                  <div className="absolute bottom-[35%] right-[28%] w-3.5 h-3.5 rounded-full bg-amber-400 ring-2 ring-amber-500/20" />
                  
                  <div className="absolute top-[58%] left-[24%] w-7 h-7 rounded-full bg-cyan-500/40 blur-xs" />
                  <div className="absolute top-[58%] left-[24%] w-2.5 h-2.5 rounded-full bg-cyan-300" />

                  <div className="absolute top-[36%] right-[22%] w-12 h-12 rounded-full bg-rose-600/30 blur-md animate-pulse" />
                  <div className="absolute top-[38%] right-[25%] w-3 h-3 rounded-full bg-rose-500 ring-4 ring-rose-600/20" />

                  {/* Center Origin Indicator */}
                  <div className="relative z-10 flex flex-col items-center justify-center p-2.5 sm:p-3 rounded-2xl bg-slate-950/85 border border-cyan-500/40 shadow-xl backdrop-blur-md">
                    <CloudRain className="h-5 w-5 sm:h-6 sm:w-6 text-cyan-400 animate-bounce [animation-duration:2.5s]" />
                    <span className="text-[9px] sm:text-[10px] font-mono-num text-cyan-300 font-bold uppercase mt-1 tracking-wider">
                      DOPPLER RADAR
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* FLOOD RASTER TAB — Depth heatmap visualization */}
            {activeTab === 'depth' && (
              <>
                <svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 800 500" preserveAspectRatio="none">
                  {/* River channel */}
                  <path d="M 50,450 C 200,420 320,310 420,240 C 520,170 650,160 780,80" fill="none" stroke="#0891b2" strokeWidth="12" strokeOpacity="0.3" />
                  <path d="M 50,450 C 200,420 320,310 420,240 C 520,170 650,160 780,80" fill="none" stroke="#22d3ee" strokeWidth="3" strokeDasharray="6 4" strokeOpacity="0.5" />
                  {/* Road grid (faint) */}
                  <path d="M 120,50 L 120,450" stroke="#334155" strokeWidth="1" strokeOpacity="0.3" />
                  <path d="M 280,30 L 280,480" stroke="#334155" strokeWidth="1" strokeOpacity="0.3" />
                  <path d="M 450,20 L 450,470" stroke="#334155" strokeWidth="1" strokeOpacity="0.3" />
                  <path d="M 620,40 L 620,480" stroke="#334155" strokeWidth="1" strokeOpacity="0.3" />
                  <path d="M 40,140 L 760,140" stroke="#334155" strokeWidth="1" strokeOpacity="0.3" />
                  <path d="M 50,290 L 750,290" stroke="#334155" strokeWidth="1" strokeOpacity="0.3" />
                  <path d="M 80,400 L 740,400" stroke="#334155" strokeWidth="1" strokeOpacity="0.3" />
                </svg>

                {/* Flood depth inundation zones — multi-layered heatmap blobs */}
                <div className="absolute top-[30%] left-[38%] w-56 h-44 rounded-full bg-cyan-500/20 blur-2xl pointer-events-none animate-pulse [animation-duration:4s]" />
                <div className="absolute top-[35%] left-[42%] w-40 h-32 rounded-full bg-blue-500/30 blur-xl pointer-events-none" />
                <div className="absolute top-[40%] left-[46%] w-28 h-24 rounded-full bg-blue-600/40 blur-lg pointer-events-none" />
                <div className="absolute top-[44%] left-[49%] w-16 h-14 rounded-full bg-indigo-600/50 blur-md pointer-events-none" />
                <div className="absolute top-[47%] left-[51%] w-8 h-8 rounded-full bg-violet-700/60 blur-sm pointer-events-none" />

                {/* Secondary flood zone */}
                <div className="absolute top-[55%] left-[20%] w-36 h-28 rounded-full bg-cyan-400/18 blur-2xl pointer-events-none" />
                <div className="absolute top-[58%] left-[23%] w-20 h-16 rounded-full bg-blue-500/30 blur-lg pointer-events-none" />

                {/* Tertiary flood zone */}
                <div className="absolute top-[22%] left-[60%] w-32 h-24 rounded-full bg-sky-500/15 blur-xl pointer-events-none" />
                <div className="absolute top-[25%] left-[63%] w-14 h-12 rounded-full bg-blue-400/25 blur-md pointer-events-none" />

                {/* Hotspot depth pins */}
                <div className="absolute top-[44%] left-[49%] -translate-x-1/2 flex flex-col items-center pointer-events-none z-10">
                  <span className="px-2 py-0.5 rounded-full bg-slate-950/90 border border-violet-500/80 text-[10px] font-mono text-violet-300 font-bold shadow-lg shadow-violet-900/40 animate-pulse">
                    0.58m Peak
                  </span>
                </div>
                <div className="absolute top-[58%] left-[23%] -translate-x-1/2 flex flex-col items-center pointer-events-none z-10">
                  <span className="px-1.5 py-0.5 rounded-full bg-slate-950/85 border border-blue-500/70 text-[9px] font-mono text-blue-300 shadow-md">
                    0.32m
                  </span>
                </div>
                <div className="absolute top-[25%] left-[63%] -translate-x-1/2 flex flex-col items-center pointer-events-none z-10">
                  <span className="px-1.5 py-0.5 rounded-full bg-slate-950/85 border border-sky-500/60 text-[9px] font-mono text-sky-300 shadow-md">
                    0.14m
                  </span>
                </div>

                {/* Depth legend */}
                <div className="absolute right-4 top-1/2 -translate-y-1/2 flex flex-col items-center bg-slate-900/85 border border-slate-800/90 rounded-lg p-2.5 font-mono text-[9px] text-slate-400 z-10 space-y-1">
                  <span className="font-semibold text-cyan-300 text-[10px]">DEPTH</span>
                  <div className="w-3 h-24 rounded-full bg-gradient-to-t from-violet-600 via-blue-500 via-cyan-400 to-sky-200" />
                  <span className="text-violet-400 font-bold">&gt;0.5m</span>
                  <span className="text-blue-400">0.3m</span>
                  <span className="text-cyan-400">0.1m</span>
                  <span className="text-sky-300">0.0m</span>
                </div>
              </>
            )}

            {/* A* ROUTES TAB — Evacuation routing visualization */}
            {activeTab === 'routing' && (
              <>
                <svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 800 500" preserveAspectRatio="none">
                  {/* Road network — prominent */}
                  <path d="M 120,50 L 120,450" stroke="#475569" strokeWidth="2.5" strokeOpacity="0.8" />
                  <path d="M 280,30 L 280,480" stroke="#475569" strokeWidth="3" strokeOpacity="0.8" />
                  <path d="M 450,20 L 450,470" stroke="#475569" strokeWidth="2.5" strokeOpacity="0.8" />
                  <path d="M 620,40 L 620,480" stroke="#475569" strokeWidth="3" strokeOpacity="0.8" />
                  <path d="M 40,140 L 760,140" stroke="#475569" strokeWidth="3" strokeOpacity="0.8" />
                  <path d="M 50,290 L 750,290" stroke="#475569" strokeWidth="3" strokeOpacity="0.8" />
                  <path d="M 80,400 L 740,400" stroke="#475569" strokeWidth="2.5" strokeOpacity="0.8" />

                  {/* Safe A* Route 1 (Emerald Green — primary) */}
                  <path 
                    d="M 120,400 L 280,400 L 280,290 L 450,290 L 450,140 L 620,140" 
                    fill="none" stroke="#10b981" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round"
                    filter="drop-shadow(0 0 10px rgba(16, 185, 129, 0.9))"
                  />
                  {/* Route 1 directional arrows */}
                  <polygon points="610,133 625,140 610,147" fill="#10b981" />
                  <polygon points="443,283 450,298 457,283" fill="#10b981" opacity="0.7" />

                  {/* Safe A* Route 2 (Teal — alternate) */}
                  <path 
                    d="M 120,400 L 120,290 L 280,290 L 280,140 L 450,140" 
                    fill="none" stroke="#14b8a6" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="8 4"
                    filter="drop-shadow(0 0 6px rgba(20, 184, 166, 0.6))"
                  />

                  {/* Blocked / Flooded Route (Red dashed) */}
                  <path d="M 280,400 L 420,240" fill="none" stroke="#ef4444" strokeWidth="3" strokeDasharray="6 6" strokeOpacity="0.9" />
                  <path d="M 450,400 L 550,290" fill="none" stroke="#ef4444" strokeWidth="3" strokeDasharray="6 6" strokeOpacity="0.7" />
                  {/* X marks on blocked routes */}
                  <text x="340" y="330" fill="#ef4444" fontSize="18" fontWeight="bold" textAnchor="middle" opacity="0.8">✕</text>
                  <text x="495" y="355" fill="#ef4444" fontSize="15" fontWeight="bold" textAnchor="middle" opacity="0.6">✕</text>

                  {/* Waypoint nodes */}
                  <circle cx="120" cy="400" r="6" fill="#10b981" stroke="#064e3b" strokeWidth="2" />
                  <circle cx="280" cy="400" r="5" fill="#10b981" stroke="#064e3b" strokeWidth="1.5" />
                  <circle cx="280" cy="290" r="5" fill="#10b981" stroke="#064e3b" strokeWidth="1.5" />
                  <circle cx="450" cy="290" r="5" fill="#10b981" stroke="#064e3b" strokeWidth="1.5" />
                  <circle cx="450" cy="140" r="5" fill="#10b981" stroke="#064e3b" strokeWidth="1.5" />
                  <circle cx="620" cy="140" r="7" fill="#10b981" stroke="#064e3b" strokeWidth="2" filter="drop-shadow(0 0 6px rgba(16,185,129,0.8))" />
                </svg>

                {/* Start marker */}
                <div className="absolute bottom-[18%] left-[14%] flex flex-col items-center z-10">
                  <span className="px-2 py-0.5 rounded bg-emerald-900/90 text-[9px] font-mono text-emerald-300 border border-emerald-700 font-bold">START</span>
                </div>

                {/* End marker */}
                <div className="absolute top-[23%] right-[20%] flex flex-col items-center z-10">
                  <span className="px-2 py-0.5 rounded bg-emerald-900/90 text-[9px] font-mono text-emerald-300 border border-emerald-700 font-bold">SAFE ZONE</span>
                </div>

                {/* Route legend */}
                <div className="absolute right-4 top-1/2 -translate-y-1/2 flex flex-col bg-slate-900/85 border border-slate-800/90 rounded-lg p-2.5 font-mono text-[9px] text-slate-400 z-10 space-y-2">
                  <span className="font-semibold text-cyan-300 text-[10px]">ROUTES</span>
                  <div className="flex items-center space-x-2">
                    <div className="w-4 h-0.5 bg-emerald-500 rounded" />
                    <span className="text-emerald-400">Safe Path</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <div className="w-4 h-0.5 bg-teal-500 rounded border-dashed" style={{borderTop: '2px dashed #14b8a6', height: 0}} />
                    <span className="text-teal-400">Alternate</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <div className="w-4 h-0.5 bg-red-500 rounded" />
                    <span className="text-red-400">Blocked</span>
                  </div>
                </div>
              </>
            )}

            {/* HYDRAULICS TAB — Underground drainage pipe network */}
            {activeTab === 'drainage' && (
              <>
                <svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 800 500" preserveAspectRatio="none">
                  {/* Underground pipe network — main trunk lines */}
                  <path d="M 60,250 L 200,250 L 200,150 L 400,150 L 400,350 L 600,350 L 600,200 L 750,200" 
                    fill="none" stroke="#6366f1" strokeWidth="6" strokeOpacity="0.7" strokeLinecap="round" strokeLinejoin="round" />
                  <path d="M 60,250 L 200,250 L 200,150 L 400,150 L 400,350 L 600,350 L 600,200 L 750,200" 
                    fill="none" stroke="#818cf8" strokeWidth="2" strokeDasharray="8 4" strokeOpacity="0.9" />
                  
                  {/* Branch pipe 1 */}
                  <path d="M 200,250 L 200,400 L 350,400" fill="none" stroke="#6366f1" strokeWidth="4" strokeOpacity="0.5" strokeLinecap="round" strokeLinejoin="round" />
                  <path d="M 200,250 L 200,400 L 350,400" fill="none" stroke="#818cf8" strokeWidth="1.5" strokeDasharray="6 4" strokeOpacity="0.7" />
                  
                  {/* Branch pipe 2 */}
                  <path d="M 400,150 L 400,80 L 550,80" fill="none" stroke="#6366f1" strokeWidth="4" strokeOpacity="0.5" strokeLinecap="round" strokeLinejoin="round" />
                  <path d="M 400,150 L 400,80 L 550,80" fill="none" stroke="#818cf8" strokeWidth="1.5" strokeDasharray="6 4" strokeOpacity="0.7" />
                  
                  {/* Branch pipe 3 */}
                  <path d="M 600,350 L 600,440 L 720,440" fill="none" stroke="#6366f1" strokeWidth="4" strokeOpacity="0.5" strokeLinecap="round" strokeLinejoin="round" />

                  {/* Flow direction arrows on main trunk */}
                  <polygon points="295,143 310,150 295,157" fill="#818cf8" opacity="0.8" />
                  <polygon points="500,343 515,350 500,357" fill="#818cf8" opacity="0.8" />
                  <polygon points="680,193 695,200 680,207" fill="#818cf8" opacity="0.8" />

                  {/* Manhole / junction nodes */}
                  <circle cx="200" cy="250" r="8" fill="#1e1b4b" stroke="#818cf8" strokeWidth="2" />
                  <circle cx="200" cy="250" r="3" fill="#818cf8" />
                  
                  <circle cx="400" cy="150" r="8" fill="#1e1b4b" stroke="#818cf8" strokeWidth="2" />
                  <circle cx="400" cy="150" r="3" fill="#818cf8" />
                  
                  <circle cx="400" cy="350" r="8" fill="#1e1b4b" stroke="#818cf8" strokeWidth="2" />
                  <circle cx="400" cy="350" r="3" fill="#818cf8" />
                  
                  <circle cx="600" cy="350" r="8" fill="#1e1b4b" stroke="#818cf8" strokeWidth="2" />
                  <circle cx="600" cy="350" r="3" fill="#818cf8" />
                  
                  <circle cx="600" cy="200" r="8" fill="#1e1b4b" stroke="#818cf8" strokeWidth="2" />
                  <circle cx="600" cy="200" r="3" fill="#818cf8" />

                  {/* Surcharge overflow indicator at junction */}
                  <circle cx="400" cy="350" r="14" fill="none" stroke="#f59e0b" strokeWidth="2" strokeDasharray="3 2" opacity="0.8">
                    <animate attributeName="r" values="14;20;14" dur="2s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.8;0.3;0.8" dur="2s" repeatCount="indefinite" />
                  </circle>

                  {/* Blockage indicator */}
                  <line x1="190" y1="390" x2="210" y2="410" stroke="#ef4444" strokeWidth="3" strokeLinecap="round" />
                  <line x1="210" y1="390" x2="190" y2="410" stroke="#ef4444" strokeWidth="3" strokeLinecap="round" />
                </svg>

                {/* Surcharge warning badge */}
                <div className="absolute top-[65%] left-[49%] -translate-x-1/2 flex flex-col items-center z-10">
                  <span className="relative flex h-3 w-3">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
                    <span className="relative inline-flex rounded-full h-3 w-3 bg-amber-500" />
                  </span>
                  <span className="mt-1 px-1.5 py-0.5 rounded bg-slate-900/90 text-[9px] font-mono text-amber-300 border border-amber-800">
                    Surcharge
                  </span>
                </div>

                {/* Blockage badge */}
                <div className="absolute top-[76%] left-[24%] flex flex-col items-center z-10">
                  <span className="px-1.5 py-0.5 rounded bg-slate-900/90 text-[9px] font-mono text-red-400 border border-red-800">
                    Blockage
                  </span>
                </div>

                {/* Pipe legend */}
                <div className="absolute right-4 top-1/2 -translate-y-1/2 flex flex-col bg-slate-900/85 border border-slate-800/90 rounded-lg p-2.5 font-mono text-[9px] text-slate-400 z-10 space-y-2">
                  <span className="font-semibold text-indigo-300 text-[10px]">PIPES</span>
                  <div className="flex items-center space-x-2">
                    <div className="w-4 h-1 bg-indigo-500 rounded" />
                    <span className="text-indigo-400">Trunk</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <div className="w-4 h-0.5 bg-indigo-400 rounded" />
                    <span className="text-indigo-300">Branch</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <div className="w-2 h-2 rounded-full bg-indigo-500 border border-indigo-300" />
                    <span className="text-slate-300">Manhole</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <div className="w-2 h-2 rounded-full bg-amber-500" />
                    <span className="text-amber-400">Surcharge</span>
                  </div>
                </div>
              </>
            )}

            {/* Top Overlay Card: Telemetry Overview (Dynamically adapts to activeTab) */}
            <div className="relative z-10 p-3 sm:p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pointer-events-none">
              
              <div className="flex flex-col p-2.5 sm:p-3 rounded-xl bg-slate-900/85 border border-slate-800/90 backdrop-blur-md shadow-lg pointer-events-auto min-w-[220px]">
                {activeTab === 'radar' && (
                  <>
                    <div className="flex items-center space-x-2 text-xs font-mono text-cyan-400 mb-1">
                      <Radio className="h-3.5 w-3.5 animate-pulse" />
                      <span>DOPPLER RADAR</span>
                      <span className="text-slate-500">·</span>
                      <span className="text-slate-300">{activeHorizon} Horizon</span>
                    </div>
                    <div className="flex items-baseline space-x-3">
                      <span className="text-xs text-slate-300 font-mono font-medium">
                        Precipitation Nowcast Active
                      </span>
                    </div>
                  </>
                )}

                {activeTab === 'depth' && (
                  <>
                    <div className="flex items-center space-x-2 text-xs font-mono text-cyan-400 mb-1">
                      <Droplets className="h-3.5 w-3.5 text-cyan-400" />
                      <span>FLOOD RASTER GRID</span>
                      <span className="text-slate-500">·</span>
                      <span className="text-slate-300">{activeHorizon} Horizon</span>
                    </div>
                    <div className="flex items-baseline space-x-3">
                      <span className="text-xs text-slate-300 font-mono font-medium">
                        2D Shallow-Water Inundation
                      </span>
                    </div>
                  </>
                )}

                {activeTab === 'routing' && (
                  <>
                    <div className="flex items-center space-x-2 text-xs font-mono text-emerald-400 mb-1">
                      <Navigation className="h-3.5 w-3.5 text-emerald-400" />
                      <span>A* DYNAMIC ROUTING</span>
                      <span className="text-slate-500">·</span>
                      <span className="text-slate-300">{activeHorizon} Horizon</span>
                    </div>
                    <div className="flex items-baseline space-x-3">
                      <span className="text-xs text-slate-300 font-mono font-medium">
                        Flood-Aware Safe Evacuation
                      </span>
                    </div>
                  </>
                )}

                {activeTab === 'drainage' && (
                  <>
                    <div className="flex items-center space-x-2 text-xs font-mono text-indigo-400 mb-1">
                      <Activity className="h-3.5 w-3.5 text-indigo-400" />
                      <span>1D SWMM HYDRAULICS</span>
                      <span className="text-slate-500">·</span>
                      <span className="text-slate-300">{activeHorizon} Horizon</span>
                    </div>
                    <div className="flex items-baseline space-x-3">
                      <span className="text-xs text-slate-300 font-mono font-medium">
                        Storm Drain Network & Manholes
                      </span>
                    </div>
                  </>
                )}
              </div>

              <div className="flex items-center space-x-2 pointer-events-auto">
                <div className="p-2.5 rounded-xl bg-slate-900/85 border border-slate-800/90 backdrop-blur-md text-right font-mono min-w-[130px]">
                  {activeTab === 'radar' && (
                    <>
                      <div className="text-[10px] text-slate-400">SCAN SWEEP</div>
                      <div className="text-xs font-bold text-cyan-400 flex items-center justify-end space-x-1">
                        <Radio className="h-3 w-3 animate-pulse" />
                        <span>360° Continuous</span>
                      </div>
                    </>
                  )}
                  {activeTab === 'depth' && (
                    <>
                      <div className="text-[10px] text-slate-400">MAX INUNDATION</div>
                      <div className="text-xs font-bold text-cyan-300 flex items-center justify-end space-x-1">
                        <Droplets className="h-3 w-3" />
                        <span>0.58m Peak</span>
                      </div>
                    </>
                  )}
                  {activeTab === 'routing' && (
                    <>
                      <div className="text-[10px] text-slate-400">A* SAFE PATH</div>
                      <div className="text-xs font-bold text-emerald-400 flex items-center justify-end space-x-1">
                        <ShieldCheck className="h-3 w-3" />
                        <span>Dry Corridor Active</span>
                      </div>
                    </>
                  )}
                  {activeTab === 'drainage' && (
                    <>
                      <div className="text-[10px] text-slate-400">SURCHARGE RISK</div>
                      <div className="text-xs font-bold text-amber-400 flex items-center justify-end space-x-1">
                        <Activity className="h-3 w-3" />
                        <span>Conduit Alert</span>
                      </div>
                    </>
                  )}
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

            {/* Bottom Overlay: Forecast Timeline Bar (with Hide option) */}
            {showTimeline ? (
              <div className="relative z-10 p-2.5 sm:p-3 border-t border-slate-800/80 bg-slate-950/90 backdrop-blur-md flex flex-col sm:flex-row items-center justify-between gap-2.5">
                <div className="flex items-center space-x-2 text-xs font-mono text-slate-400">
                  <MapPin className="h-3.5 w-3.5 text-cyan-400" />
                  <span>FORECAST HORIZON:</span>
                  <button
                    onClick={() => setShowTimeline(false)}
                    className="flex items-center space-x-1 px-2 py-0.5 rounded-md bg-slate-800 hover:bg-slate-700 text-cyan-300 hover:text-white border border-slate-700 text-[11px] font-mono transition-colors cursor-pointer"
                    title="Hide timestamp bar"
                  >
                    <EyeOff className="h-3 w-3 text-cyan-400" />
                    <span>Hide</span>
                  </button>
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

                <div className="flex items-center space-x-3">
                  <div className="hidden lg:flex items-center space-x-2 text-[11px] font-mono text-slate-400">
                    {activeTab === 'radar' && (
                      <>
                        <span>Doppler Reflectivity</span>
                        <span>·</span>
                        <span className="text-cyan-400">Optical Flow</span>
                      </>
                    )}
                    {activeTab === 'depth' && (
                      <>
                        <span>Saint-Venant 2D</span>
                        <span>·</span>
                        <span className="text-cyan-400">40,000 Inundation Cells</span>
                      </>
                    )}
                    {activeTab === 'routing' && (
                      <>
                        <span>A* Shortest Path</span>
                        <span>·</span>
                        <span className="text-emerald-400">Dry Heuristic Graph</span>
                      </>
                    )}
                    {activeTab === 'drainage' && (
                      <>
                        <span>SWMM Dynamic Wave</span>
                        <span>·</span>
                        <span className="text-indigo-400">Conduit Surcharge</span>
                      </>
                    )}
                  </div>

                  {/* Hide option button */}
                  <button
                    onClick={() => setShowTimeline(false)}
                    className="flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 hover:border-cyan-500/50 text-xs font-mono text-cyan-300 hover:text-white transition-all cursor-pointer shadow-md"
                    title="Hide timestamp bar"
                  >
                    <EyeOff className="h-3.5 w-3.5 text-cyan-400" />
                    <span className="font-semibold">Hide Bar</span>
                  </button>
                </div>
              </div>
            ) : (
              /* Floating mini-restore pill when timeline bar is hidden */
              <div className="relative z-10 p-2.5 sm:p-3 flex justify-end pointer-events-none">
                <button
                  onClick={() => setShowTimeline(true)}
                  className="pointer-events-auto flex items-center space-x-2 px-3.5 py-2 rounded-xl bg-slate-900/95 hover:bg-slate-800 border border-cyan-500/50 text-xs font-mono text-cyan-300 hover:text-white shadow-2xl backdrop-blur-md transition-all cursor-pointer group"
                  title="Show timestamp bar"
                >
                  <Eye className="h-4 w-4 text-cyan-400 group-hover:scale-110 transition-transform" />
                  <span className="font-semibold">Show Timestamp ({activeHorizon})</span>
                </button>
              </div>
            )}

          </div>

        </div>
      </motion.div>

    </div>
  );
};

