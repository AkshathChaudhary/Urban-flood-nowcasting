import React from 'react';
import { motion } from 'framer-motion';
import { 
  Play, 
  Compass, 
  CloudRain, 
  ArrowUpRight 
} from 'lucide-react';

interface LandingHeroProps {
  onLaunchCommandCenter: () => void;
  onSelectScenario: (scenario: string) => void;
}

export const LandingHero: React.FC<LandingHeroProps> = ({
  onLaunchCommandCenter,
  onSelectScenario,
}) => {
  return (
    <div className="relative isolate overflow-hidden min-h-[calc(100vh-4rem)] flex flex-col justify-center px-4 sm:px-6 lg:px-8 py-12 md:py-20">
      
      {/* Background Animated Ambient Lights */}
      <div className="absolute inset-0 -z-10 overflow-hidden pointer-events-none">
        {/* Deep radial glows */}
        <div className="absolute -top-40 left-1/2 -translate-x-1/2 w-[800px] h-[500px] bg-gradient-to-tr from-cyan-600/20 via-blue-700/15 to-purple-800/10 blur-[130px] rounded-full" />
        <div className="absolute top-1/3 -right-40 w-[600px] h-[450px] bg-cyan-500/10 blur-[140px] rounded-full" />
        <div className="absolute -bottom-20 -left-40 w-[550px] h-[400px] bg-emerald-500/10 blur-[120px] rounded-full" />

        {/* Subtle grid pattern overlay */}
        <div 
          className="absolute inset-0 opacity-[0.035]"
          style={{
            backgroundImage: `radial-gradient(circle at 1px 1px, #38bdf8 1px, transparent 0)`,
            backgroundSize: '32px 32px'
          }}
        />
      </div>

      <div className="mx-auto max-w-7xl w-full grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-8 items-center">
        
        {/* Left Column: Mission, Headlines & CTAs */}
        <div className="lg:col-span-7 flex flex-col items-start text-left">
          
          {/* Status Badge */}
          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="inline-flex items-center space-x-2.5 rounded-full border border-cyan-500/30 bg-cyan-950/40 px-3.5 py-1.5 backdrop-blur-md mb-6 shadow-sm shadow-cyan-950"
          >
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-cyan-500"></span>
            </span>
            <span className="text-xs font-semibold tracking-wide text-cyan-300 uppercase font-mono-num">
              FLOWS — Real-Time Flood Intelligence Platform
            </span>
          </motion.div>

          {/* Main Headline */}
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-white leading-[1.12]"
          >
            Predict Flood Depths.{' '}
            <span className="block bg-gradient-to-r from-cyan-400 via-teal-300 to-emerald-400 bg-clip-text text-transparent">
              Reroute Responders.
            </span>
            Before Streets Inundate.
          </motion.h1>

          {/* Subtitle */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="mt-6 text-base sm:text-lg text-slate-300 max-w-2xl leading-relaxed"
          >
            A high-resolution <span className="text-cyan-300 font-semibold">10-meter urban physics model</span> coupling 
            Doppler radar precipitation nowcasting, 2D shallow water surface runoff, and subterranean pipe network hydraulics 
            to calculate safe, flood-penalized evacuation routes in real time.
          </motion.p>

          {/* Action Button Group */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
            className="mt-8 flex flex-wrap items-center gap-4 w-full sm:w-auto"
          >
            <button
              onClick={onLaunchCommandCenter}
              className="group relative inline-flex items-center justify-center rounded-xl bg-gradient-to-r from-cyan-500 via-teal-500 to-blue-600 px-6 py-3.5 text-base font-semibold text-white shadow-xl shadow-cyan-500/20 hover:shadow-cyan-500/35 hover:brightness-110 active:scale-95 transition-all duration-300 cursor-pointer ring-1 ring-white/20"
            >
              <Compass className="mr-2.5 h-5 w-5 text-cyan-200 transition-transform group-hover:rotate-45" />
              <span>Enter Command Center</span>
              <ArrowUpRight className="ml-2 h-4 w-4 text-cyan-200 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
            </button>

            <button
              onClick={() => onSelectScenario('mumbai_severe')}
              className="inline-flex items-center justify-center rounded-xl border border-slate-700/80 bg-slate-900/70 px-5 py-3.5 text-base font-medium text-slate-200 hover:bg-slate-800/80 hover:border-slate-600 hover:text-white transition-all duration-200 cursor-pointer backdrop-blur-sm"
            >
              <Play className="mr-2 h-4 w-4 text-cyan-400 fill-cyan-400/20" />
              <span>Simulate Cloudburst Scenario</span>
            </button>
          </motion.div>

          {/* Telemetry Metrics Bar */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.4 }}
            className="mt-12 grid grid-cols-2 sm:grid-cols-4 gap-4 w-full pt-8 border-t border-slate-800/60"
          >
            <div className="flex flex-col">
              <span className="text-2xl sm:text-3xl font-bold text-white font-mono-num">
                10<span className="text-cyan-400 text-lg font-normal">m</span>
              </span>
              <span className="text-xs text-slate-400 mt-0.5">Cell Resolution</span>
            </div>

            <div className="flex flex-col">
              <span className="text-2xl sm:text-3xl font-bold text-white font-mono-num">
                0–180<span className="text-teal-400 text-lg font-normal">m</span>
              </span>
              <span className="text-xs text-slate-400 mt-0.5">Nowcast Horizon</span>
            </div>

            <div className="flex flex-col">
              <span className="text-2xl sm:text-3xl font-bold text-white font-mono-num">
                &lt;0.4<span className="text-emerald-400 text-lg font-normal">s</span>
              </span>
              <span className="text-xs text-slate-400 mt-0.5">A* Rerouting Speed</span>
            </div>

            <div className="flex flex-col">
              <span className="text-2xl sm:text-3xl font-bold text-white font-mono-num">
                40,000
              </span>
              <span className="text-xs text-slate-400 mt-0.5">Grid Mesh Cells</span>
            </div>
          </motion.div>

        </div>

        {/* Right Column: Live Simulated Radar Sweep Screen (21st.dev / motionsites.ai aesthetic) */}
        <motion.div
          initial={{ opacity: 0, scale: 0.94 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.8, delay: 0.2 }}
          className="lg:col-span-5 flex justify-center"
        >
          <div className="relative w-full max-w-[420px] aspect-square rounded-3xl p-4 glass-panel border border-slate-700/60 shadow-2xl shadow-cyan-950/50 flex items-center justify-center overflow-hidden">
            
            {/* Outer Radial Ring Guides */}
            <div className="absolute inset-4 rounded-full border border-cyan-500/20" />
            <div className="absolute inset-16 rounded-full border border-cyan-500/15" />
            <div className="absolute inset-28 rounded-full border border-cyan-500/10" />
            
            {/* Center Crosshairs */}
            <div className="absolute inset-x-4 top-1/2 h-[1px] bg-cyan-500/20" />
            <div className="absolute inset-y-4 left-1/2 w-[1px] bg-cyan-500/20" />

            {/* Rotating Radar Sweep Beam */}
            <div className="absolute inset-4 rounded-full overflow-hidden pointer-events-none">
              <div 
                className="w-full h-full animate-radar-sweep origin-center"
                style={{
                  background: 'conic-gradient(from 0deg, transparent 0deg, transparent 270deg, rgba(6, 182, 212, 0.45) 360deg)'
                }}
              />
            </div>

            {/* Simulated Storm Cell Blips / Flood Inundation Zones */}
            <div className="absolute top-[28%] left-[34%] w-8 h-8 rounded-full bg-red-500/40 blur-sm animate-pulse" />
            <div className="absolute top-[28%] left-[34%] w-3 h-3 rounded-full bg-red-400 ring-4 ring-red-500/30" />
            
            <div className="absolute bottom-[35%] right-[28%] w-10 h-10 rounded-full bg-amber-500/35 blur-sm" />
            <div className="absolute bottom-[35%] right-[28%] w-3.5 h-3.5 rounded-full bg-amber-400" />
            
            <div className="absolute top-[60%] left-[25%] w-6 h-6 rounded-full bg-cyan-500/40 blur-xs" />
            <div className="absolute top-[60%] left-[25%] w-2 h-2 rounded-full bg-cyan-300" />

            {/* Center Landmark / Origin Indicator */}
            <div className="relative z-10 flex flex-col items-center justify-center p-3 rounded-2xl bg-slate-950/80 border border-cyan-500/40 shadow-xl backdrop-blur-md">
              <CloudRain className="h-6 w-6 text-cyan-400 animate-bounce [animation-duration:2.5s]" />
              <span className="text-[10px] font-mono-num text-cyan-300 font-bold uppercase mt-1 tracking-wider">
                MUMBAI RADAR
              </span>
              <span className="text-[9px] font-mono-num text-slate-400">
                19.06°N 72.85°E
              </span>
            </div>

            {/* HUD Corner Badges */}
            <div className="absolute top-4 left-4 flex items-center space-x-1.5 px-2.5 py-1 rounded-lg bg-slate-900/80 border border-slate-800 text-[10px] text-cyan-400 font-mono-num">
              <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-ping" />
              <span>DWR REFLECTIVITY: 48 dBZ</span>
            </div>

            <div className="absolute bottom-4 right-4 px-2.5 py-1 rounded-lg bg-slate-900/80 border border-slate-800 text-[10px] text-emerald-400 font-mono-num">
              SURCHARGE OVERFLOW: 0.14 m³/s
            </div>

            <div className="absolute bottom-4 left-4 px-2.5 py-1 rounded-lg bg-slate-900/80 border border-slate-800 text-[10px] text-slate-400 font-mono-num">
              T+45m PROJECTION
            </div>

          </div>
        </motion.div>

      </div>

    </div>
  );
};
