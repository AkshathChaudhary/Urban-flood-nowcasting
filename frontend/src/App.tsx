import { useState } from 'react';
import { Navbar } from './components/Navbar';
import { LandingHero } from './components/LandingHero';
import { BentoShowcase } from './components/BentoShowcase';
import { CommandCenterView } from './components/CommandCenterView';
import { Waves } from 'lucide-react';

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
    setActiveView('command-center');
  };

  const handleExploreFeature = (featureId: string) => {
    console.log('Explore feature:', featureId);
    setActiveView('command-center');
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-cyan-500/30 selection:text-cyan-200">
      
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
        <main className="flex-1 flex flex-col">
          {/* motionsites.ai inspired Hero */}
          <LandingHero
            onLaunchCommandCenter={handleLaunchCommandCenter}
            onSelectScenario={handleSelectScenario}
          />

          {/* 21st.dev inspired Bento Grid */}
          <BentoShowcase onExploreFeature={handleExploreFeature} />

          {/* Simple Cinematic Footer */}
          <footer className="border-t border-slate-900 bg-slate-950 py-12 px-4 sm:px-6 lg:px-8 text-slate-500 text-xs font-mono-num">
            <div className="mx-auto max-w-7xl flex flex-col sm:flex-row items-center justify-between gap-4">
              <div className="flex items-center space-x-2">
                <Waves className="h-4 w-4 text-cyan-400" />
                <span className="text-slate-300 font-bold">FLOWS</span>
                <span>— Flood Level Optimised Warning & Safety</span>
              </div>

              <div className="flex items-center space-x-6 text-slate-400">
                <span>FastAPI + NumPy Hydrodynamics</span>
                <span>OpenStreetMap A* Routing</span>
                <span>Doppler Radar Ingestion</span>
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
