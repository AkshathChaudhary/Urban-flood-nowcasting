import React, { useEffect, useState } from 'react';
import { Waves, MapPin, ArrowRight, ArrowLeft } from 'lucide-react';

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
  const [isScrolled, setIsScrolled] = useState<boolean>(false);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 20);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const scrollToSection = (id: string) => {
    if (activeView !== 'landing') {
      onNavigateHome();
      setTimeout(() => {
        const element = document.getElementById(id);
        element?.scrollIntoView({ behavior: 'smooth' });
      }, 100);
    } else {
      const element = document.getElementById(id);
      element?.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <header 
      className={`sticky top-0 z-50 w-full transition-all duration-300 ${
        isScrolled 
          ? 'border-b border-slate-800/60 bg-slate-950/80 backdrop-blur-xl shadow-lg shadow-black/40 py-3' 
          : 'border-b border-slate-800/30 bg-slate-950/50 backdrop-blur-md py-4'
      }`}
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        
        {/* Brand / Logo */}
        <div 
          onClick={onNavigateHome}
          className="flex cursor-pointer items-center space-x-2.5 group select-none"
        >
          <div className="relative flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-tr from-cyan-500/20 to-blue-600/20 border border-cyan-500/40 transition-transform duration-300 group-hover:scale-105">
            <Waves className="h-4 w-4 text-cyan-400" />
            <span className="absolute -top-0.5 -right-0.5 flex h-1.5 w-1.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-cyan-400" />
            </span>
          </div>

          <div className="flex items-center space-x-1.5">
            <span className="text-base font-bold tracking-wider text-white">
              FLOW<span className="text-cyan-400">S</span>
            </span>
            <span className="hidden sm:inline-block text-[10px] font-mono text-slate-400 uppercase tracking-widest pl-1">
              Flood Intelligence
            </span>
          </div>
        </div>

        {/* Center Nav Links */}
        {activeView === 'landing' ? (
          <nav className="hidden md:flex items-center space-x-6 text-xs font-medium text-slate-400">
            <button
              onClick={() => scrollToSection('product-preview')}
              className="hover:text-white transition-colors cursor-pointer"
            >
              Product
            </button>
            <button
              onClick={() => scrollToSection('technology')}
              className="hover:text-white transition-colors cursor-pointer"
            >
              Technology
            </button>
            <button
              onClick={() => scrollToSection('pipeline')}
              className="hover:text-white transition-colors cursor-pointer"
            >
              How it Works
            </button>
            <button
              onClick={onLaunchCommandCenter}
              className="hover:text-cyan-300 transition-colors cursor-pointer font-semibold text-slate-300"
            >
              Dashboard
            </button>
          </nav>
        ) : (
          <div className="hidden md:flex items-center space-x-2 text-xs font-mono text-cyan-400 bg-cyan-950/40 px-3 py-1 rounded-full border border-cyan-800/40">
            <span className="h-2 w-2 rounded-full bg-cyan-400 animate-pulse" />
            <span>COMMAND CENTER ACTIVE</span>
          </div>
        )}

        {/* Right Section: City Selector + Get Started CTA */}
        <div className="flex items-center space-x-3">
          
          {/* City Context Selector */}
          <div className="hidden sm:flex items-center space-x-1.5 rounded-lg border border-slate-800/80 bg-slate-900/60 px-2.5 py-1 text-xs">
            <MapPin className="h-3 w-3 text-cyan-400 shrink-0" />
            <select
              value={currentCity}
              onChange={(e) => onCityChange(e.target.value)}
              className="bg-transparent font-medium text-slate-300 focus:outline-none cursor-pointer text-xs"
              aria-label="Select City Context"
            >
              <option value="mumbai" className="bg-slate-950 text-slate-200">Mumbai (SW 2x2km)</option>
              <option value="kolkata" className="bg-slate-950 text-slate-200">Kolkata (EM Bypass)</option>
            </select>
          </div>

          {/* Primary Action Button */}
          {activeView === 'landing' ? (
            <button
              onClick={onLaunchCommandCenter}
              className="group relative inline-flex items-center justify-center rounded-lg bg-cyan-500/15 hover:bg-cyan-500/25 border border-cyan-500/40 hover:border-cyan-400 px-4 py-1.5 text-xs font-semibold text-cyan-300 hover:text-white transition-all duration-200 cursor-pointer shadow-sm shadow-cyan-950"
            >
              <span>Get Started</span>
              <ArrowRight className="ml-1.5 h-3.5 w-3.5 text-cyan-300 transition-transform group-hover:translate-x-0.5" />
            </button>
          ) : (
            <button
              onClick={onNavigateHome}
              className="inline-flex items-center justify-center rounded-lg border border-slate-700 bg-slate-800/80 px-3 py-1.5 text-xs font-semibold text-slate-200 hover:bg-slate-700/80 hover:text-white transition-all cursor-pointer"
            >
              <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
              <span>Landing Page</span>
            </button>
          )}
        </div>

      </div>
    </header>
  );
};

