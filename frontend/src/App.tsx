import { useState } from 'react';
import { Navbar } from './components/Navbar';
import { LandingHero } from './components/LandingHero';
import { BentoShowcase } from './components/BentoShowcase';
import { CommandCenterView } from './components/CommandCenterView';
import { Waves, ShieldCheck } from 'lucide-react';
import { AetherBackground } from './components/ui/aether-background';

export function App() {
  const [activeView, setActiveView] = useState<'landing' | 'command-center'>('landing');
  const [currentCity, setCurrentCity] = useState<string>('mumbai');

  const handleLaunchCommandCenter = () => {
    setActiveView('command-center');
  };

  const handleNavigateHome = () => {
    setActiveView('landing');
  };

  const handleSelectScenario = (scenario: string) => {
    console.log('Selected scenario:', scenario);
    // If scenario specifies city
    if (scenario.includes('kolkata')) {
      setCurrentCity('kolkata');
    } else {
      setCurrentCity('mumbai');
    }
    setActiveView('command-center');
  };

  const handleExploreFeature = (featureId: string) => {
    console.log('Explore feature:', featureId);
    setActiveView('command-center');
  };

  return (
    <div className="min-h-screen bg-[#030712] text-slate-100 flex flex-col selection:bg-cyan-500/30 selection:text-cyan-200 relative">
      
      {/* Universal Glass Navbar */}
      <Navbar
        currentCity={currentCity}
        onCityChange={setCurrentCity}
        onLaunchCommandCenter={handleLaunchCommandCenter}
        activeView={activeView}
        onNavigateHome={handleNavigateHome}
      />

      {/* Main Content Area */}
      {activeView === 'landing' ? (
        <main className="flex-1 flex flex-col relative">
          {/* Fixed Full-Page Interactive Luminous Aether Background */}
          <AetherBackground isFixed={true} />

          {/* Mission Control Hero */}
          <LandingHero
            onLaunchCommandCenter={handleLaunchCommandCenter}
            onSelectScenario={handleSelectScenario}
          />

          {/* Architecture & Multi-Physics Bento Grid */}
          <BentoShowcase 
            onExploreFeature={handleExploreFeature}
            onSelectScenario={handleSelectScenario}
          />

          {/* Refined High-Tech Footer */}
          <footer className="border-t border-slate-900 bg-slate-950/90 py-10 px-4 sm:px-6 lg:px-8 text-slate-500 text-xs font-mono">
            <div className="mx-auto max-w-7xl flex flex-col sm:flex-row items-center justify-between gap-4">
              <div className="flex items-center space-x-2.5">
                <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-cyan-500/10 border border-cyan-500/30">
                  <Waves className="h-3.5 w-3.5 text-cyan-400" />
                </div>
                <span className="text-slate-300 font-bold tracking-tight">FLOWS</span>
                <span className="text-slate-500">— Flood Level Optimised Warning & Safety</span>
              </div>

              <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-slate-400">
                <span className="inline-flex items-center space-x-1">
                  <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
                  <span>Saint-Venant 2D Solver</span>
                </span>
                <span>OSM A* Graph Routing</span>
                <span>Doppler Optical Flow</span>
              </div>
            </div>
          </footer>
        </main>
      ) : (
        <main className="flex-1 flex flex-col">
          {/* Interactive Command Center Workspace */}
          <CommandCenterView currentCity={currentCity} onCityChange={setCurrentCity} />
        </main>
      )}

    </div>
  );
}

export default App;
