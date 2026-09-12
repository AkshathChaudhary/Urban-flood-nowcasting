import React, { useEffect, useRef } from 'react';

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  baseVx: number;
  baseVy: number;
  radius: number;
  color: string;
  alpha: number;
  baseAlpha: number;
  pulseSpeed: number;
  pulseOffset: number;
}

interface Spark {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  alpha: number;
  color: string;
  decay: number;
}

interface Ripple {
  x: number;
  y: number;
  radius: number;
  maxRadius: number;
  alpha: number;
  lineWidth: number;
  color: string;
}

interface TrailDot {
  x: number;
  y: number;
  radius: number;
  alpha: number;
  color: string;
}

interface AetherBackgroundProps {
  className?: string;
  isFixed?: boolean;
}

export const AetherBackground: React.FC<AetherBackgroundProps> = ({ 
  className = '', 
  isFixed = false 
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d', { alpha: true });
    if (!ctx) return;

    let animationFrameId: number;
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // High-luminance neon palette: Hyper-Cyan, Electric Sky, Brilliant Blue, Radiant Violet
    const vibrantColors = [
      'rgba(6, 245, 255, ',   // Hyper Cyan (very bright)
      'rgba(56, 189, 248, ',  // Electric Sky
      'rgba(96, 165, 250, ',  // Brilliant Azure
      'rgba(168, 85, 247, ',  // Radiant Violet
      'rgba(52, 211, 153, ',  // Emerald Surge
    ];

    // Responsive particle counts
    const isMobile = width < 768;
    const particleCount = isMobile ? 55 : width < 1440 ? 95 : 130;
    const maxConnectionDistance = isMobile ? 120 : 160;

    // Interactive mouse state with smooth easing
    const mouse = {
      x: -1000,
      y: -1000,
      targetX: -1000,
      targetY: -1000,
      radius: isMobile ? 180 : 260,
      active: false,
      speed: 0,
      lastX: -1000,
      lastY: -1000,
    };

    const particles: Particle[] = [];
    const sparks: Spark[] = [];
    const ripples: Ripple[] = [];
    const trailDots: TrailDot[] = [];

    // Initialize glowing particles
    for (let i = 0; i < particleCount; i++) {
      const color = vibrantColors[Math.floor(Math.random() * vibrantColors.length)];
      const baseAlpha = Math.random() * 0.4 + 0.6; // High base brightness: 0.60 to 1.00
      const vx = prefersReducedMotion ? 0 : (Math.random() - 0.5) * 0.9;
      const vy = prefersReducedMotion ? 0 : (Math.random() - 0.5) * 0.9;

      particles.push({
        x: Math.random() * width,
        y: Math.random() * height,
        vx,
        vy,
        baseVx: vx,
        baseVy: vy,
        radius: Math.random() * 2.6 + 1.4,
        color,
        baseAlpha,
        alpha: baseAlpha,
        pulseSpeed: Math.random() * 0.03 + 0.015,
        pulseOffset: Math.random() * Math.PI * 2,
      });
    }

    // Window resize handler
    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };

    // Smooth mouse movement tracking across whole window
    const handleMouseMove = (e: MouseEvent) => {
      mouse.targetX = e.clientX;
      mouse.targetY = e.clientY;
      mouse.active = true;

      // Calculate cursor speed
      const dx = e.clientX - mouse.lastX;
      const dy = e.clientY - mouse.lastY;
      mouse.speed = Math.min(Math.sqrt(dx * dx + dy * dy), 40);
      mouse.lastX = e.clientX;
      mouse.lastY = e.clientY;

      // Spawn subtle stardust trail while moving
      if (!prefersReducedMotion && Math.random() > 0.35 && trailDots.length < 50) {
        trailDots.push({
          x: e.clientX + (Math.random() - 0.5) * 20,
          y: e.clientY + (Math.random() - 0.5) * 20,
          radius: Math.random() * 2.2 + 1.0,
          alpha: 0.85,
          color: vibrantColors[Math.floor(Math.random() * vibrantColors.length)],
        });
      }
    };

    const handleMouseLeave = () => {
      mouse.active = false;
      mouse.targetX = -1000;
      mouse.targetY = -1000;
    };

    // Dynamic interactive click: Shockwave ripple + explosive firework spark burst
    const handleClick = (e: MouseEvent) => {
      const clickX = e.clientX;
      const clickY = e.clientY;

      // 1. Expanding shockwave ring
      ripples.push({
        x: clickX,
        y: clickY,
        radius: 10,
        maxRadius: isMobile ? 160 : 240,
        alpha: 0.9,
        lineWidth: 3,
        color: 'rgba(6, 245, 255, ',
      });

      ripples.push({
        x: clickX,
        y: clickY,
        radius: 5,
        maxRadius: isMobile ? 120 : 180,
        alpha: 0.7,
        lineWidth: 2,
        color: 'rgba(168, 85, 247, ',
      });

      // 2. High-energy spark burst
      const sparkCount = isMobile ? 16 : 26;
      for (let i = 0; i < sparkCount; i++) {
        const angle = (Math.PI * 2 * i) / sparkCount + (Math.random() - 0.5) * 0.4;
        const speed = Math.random() * 4.5 + 2.0;
        sparks.push({
          x: clickX,
          y: clickY,
          vx: Math.cos(angle) * speed,
          vy: Math.sin(angle) * speed,
          radius: Math.random() * 3.0 + 1.5,
          alpha: 1.0,
          color: vibrantColors[Math.floor(Math.random() * vibrantColors.length)],
          decay: Math.random() * 0.02 + 0.015,
        });
      }

      // 3. Impart direct impulse on surrounding particles
      particles.forEach((p) => {
        const pdx = p.x - clickX;
        const pdy = p.y - clickY;
        const dist = Math.sqrt(pdx * pdx + pdy * pdy);
        if (dist < 280 && dist > 1) {
          const force = (1 - dist / 280) * 12;
          p.vx += (pdx / dist) * force;
          p.vy += (pdy / dist) * force;
        }
      });
    };

    window.addEventListener('resize', handleResize, { passive: true });
    window.addEventListener('mousemove', handleMouseMove, { passive: true });
    window.addEventListener('mouseleave', handleMouseLeave, { passive: true });
    window.addEventListener('click', handleClick);

    let tick = 0;

    const render = () => {
      tick++;
      ctx.clearRect(0, 0, width, height);

      // Smooth lerp mouse position
      if (mouse.active) {
        mouse.x += (mouse.targetX - mouse.x) * 0.2;
        mouse.y += (mouse.targetY - mouse.y) * 0.2;
      } else {
        mouse.x += (-1000 - mouse.x) * 0.1;
        mouse.y += (-1000 - mouse.y) * 0.1;
      }

      // 1. Draw Vibrant Ambient Floating Energy Orbs (deep luminous backdrop)
      const orbTime = tick * 0.006;
      const orb1X = width * 0.25 + Math.sin(orbTime) * 80;
      const orb1Y = height * 0.2 + Math.cos(orbTime * 0.8) * 60;
      const orb1 = ctx.createRadialGradient(orb1X, orb1Y, 0, orb1X, orb1Y, 400);
      orb1.addColorStop(0, 'rgba(6, 182, 212, 0.16)');
      orb1.addColorStop(0.5, 'rgba(14, 116, 144, 0.08)');
      orb1.addColorStop(1, 'transparent');
      ctx.fillStyle = orb1;
      ctx.beginPath();
      ctx.arc(orb1X, orb1Y, 400, 0, Math.PI * 2);
      ctx.fill();

      const orb2X = width * 0.75 + Math.cos(orbTime * 0.7) * 90;
      const orb2Y = height * 0.45 + Math.sin(orbTime * 0.9) * 70;
      const orb2 = ctx.createRadialGradient(orb2X, orb2Y, 0, orb2X, orb2Y, 450);
      orb2.addColorStop(0, 'rgba(59, 130, 246, 0.15)');
      orb2.addColorStop(0.5, 'rgba(99, 102, 241, 0.07)');
      orb2.addColorStop(1, 'transparent');
      ctx.fillStyle = orb2;
      ctx.beginPath();
      ctx.arc(orb2X, orb2Y, 450, 0, Math.PI * 2);
      ctx.fill();

      // 2. Draw Interactive Radiant Cursor Spotlight (Bright Flashlight Aura)
      if (mouse.x > -500 && mouse.y > -500) {
        const aura = ctx.createRadialGradient(
          mouse.x,
          mouse.y,
          0,
          mouse.x,
          mouse.y,
          mouse.radius
        );
        aura.addColorStop(0, 'rgba(6, 245, 255, 0.35)');      // Bright neon core
        aura.addColorStop(0.3, 'rgba(56, 189, 248, 0.22)');   // Vibrant cyan bloom
        aura.addColorStop(0.65, 'rgba(129, 140, 248, 0.12)'); // Electric indigo rim
        aura.addColorStop(1, 'transparent');

        ctx.fillStyle = aura;
        ctx.beginPath();
        ctx.arc(mouse.x, mouse.y, mouse.radius, 0, Math.PI * 2);
        ctx.fill();

        // Inner bright halo ring
        ctx.beginPath();
        ctx.arc(mouse.x, mouse.y, 45, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(6, 245, 255, 0.08)';
        ctx.fill();
      }

      // 3. Render Click Shockwaves
      for (let i = ripples.length - 1; i >= 0; i--) {
        const r = ripples[i];
        r.radius += 5.5;
        r.alpha -= 0.022;

        if (r.alpha <= 0 || r.radius >= r.maxRadius) {
          ripples.splice(i, 1);
          continue;
        }

        ctx.beginPath();
        ctx.arc(r.x, r.y, r.radius, 0, Math.PI * 2);
        ctx.strokeStyle = `${r.color}${r.alpha})`;
        ctx.lineWidth = r.lineWidth;
        ctx.stroke();
      }

      // 4. Render Mouse Stardust Trail
      for (let i = trailDots.length - 1; i >= 0; i--) {
        const t = trailDots[i];
        t.alpha -= 0.03;
        t.radius *= 0.96;

        if (t.alpha <= 0 || t.radius < 0.4) {
          trailDots.splice(i, 1);
          continue;
        }

        ctx.beginPath();
        ctx.arc(t.x, t.y, t.radius * 2, 0, Math.PI * 2);
        ctx.fillStyle = `${t.color}${t.alpha * 0.35})`;
        ctx.fill();

        ctx.beginPath();
        ctx.arc(t.x, t.y, t.radius, 0, Math.PI * 2);
        ctx.fillStyle = `${t.color}${t.alpha})`;
        ctx.fill();
      }

      // 5. Connect particles to each other with bright electric lines
      for (let i = 0; i < particles.length; i++) {
        const p1 = particles[i];

        for (let j = i + 1; j < particles.length; j++) {
          const p2 = particles[j];
          const dx = p1.x - p2.x;
          const dy = p1.y - p2.y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < maxConnectionDistance) {
            const lineAlpha = (1 - dist / maxConnectionDistance) * 0.48; // Upgraded brightness
            ctx.beginPath();
            ctx.strokeStyle = `rgba(56, 189, 248, ${lineAlpha})`;
            ctx.lineWidth = dist < maxConnectionDistance * 0.4 ? 1.5 : 0.9;
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.stroke();
          }
        }

        // 6. Connect particles directly to Mouse Cursor with high-energy laser beams
        if (mouse.x > -500 && mouse.y > -500) {
          const mdx = p1.x - mouse.x;
          const mdy = p1.y - mouse.y;
          const mdist = Math.sqrt(mdx * mdx + mdy * mdy);

          if (mdist < mouse.radius) {
            const mLineAlpha = Math.pow(1 - mdist / mouse.radius, 1.2) * 0.85; // Very bright near cursor
            ctx.beginPath();
            ctx.strokeStyle = `rgba(6, 245, 255, ${mLineAlpha})`;
            ctx.lineWidth = 1.6;
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(mouse.x, mouse.y);
            ctx.stroke();

            // Living fluid repulsion + speed-driven vortex
            if (!prefersReducedMotion) {
              const repulseForce = (1 - mdist / mouse.radius) * 1.5;
              p1.vx += (mdx / mdist) * repulseForce * 0.6;
              p1.vy += (mdy / mdist) * repulseForce * 0.6;

              // Angular swirl around cursor
              const angle = Math.atan2(mdy, mdx) + Math.PI / 2;
              const swirlStrength = (mouse.speed * 0.015) * (1 - mdist / mouse.radius);
              p1.vx += Math.cos(angle) * swirlStrength;
              p1.vy += Math.sin(angle) * swirlStrength;
            }
          }
        }
      }

      // 7. Update and render particles
      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];

        if (!prefersReducedMotion) {
          // Dynamic damping returning to organic drift
          p.vx = p.vx * 0.95 + p.baseVx * 0.05;
          p.vy = p.vy * 0.95 + p.baseVy * 0.05;

          p.x += p.vx;
          p.y += p.vy;

          // Seamless edge wrapping
          if (p.x < 0) p.x = width;
          if (p.x > width) p.x = 0;
          if (p.y < 0) p.y = height;
          if (p.y > height) p.y = 0;
        }

        // Twinkle / pulse calculation
        const pulse = Math.sin(tick * p.pulseSpeed + p.pulseOffset);
        const dynamicAlpha = Math.min(1, Math.max(0.3, p.baseAlpha + pulse * 0.25));

        // Radiant outer neon halo (3x radius)
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius * 3.5, 0, Math.PI * 2);
        ctx.fillStyle = `${p.color}${dynamicAlpha * 0.35})`;
        ctx.fill();

        // Brilliant glowing particle body
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fillStyle = `${p.color}${dynamicAlpha})`;
        ctx.fill();

        // Hot white stellar specular point in center
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius * 0.45, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255, 255, 255, ${dynamicAlpha * 0.95})`;
        ctx.fill();
      }

      // 8. Render Click Spark Particles
      for (let i = sparks.length - 1; i >= 0; i--) {
        const s = sparks[i];
        s.x += s.vx;
        s.y += s.vy;
        s.vx *= 0.94;
        s.vy *= 0.94;
        s.alpha -= s.decay;

        if (s.alpha <= 0) {
          sparks.splice(i, 1);
          continue;
        }

        // Spark outer bloom
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.radius * 2.5, 0, Math.PI * 2);
        ctx.fillStyle = `${s.color}${s.alpha * 0.4})`;
        ctx.fill();

        // Spark core
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.radius, 0, Math.PI * 2);
        ctx.fillStyle = `${s.color}${s.alpha})`;
        ctx.fill();

        // Spark hot center
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.radius * 0.4, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255, 255, 255, ${s.alpha})`;
        ctx.fill();
      }

      if (!prefersReducedMotion) {
        animationFrameId = requestAnimationFrame(render);
      }
    };

    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseleave', handleMouseLeave);
      window.removeEventListener('click', handleClick);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className={`${isFixed ? 'fixed' : 'absolute'} inset-0 h-full w-full pointer-events-none ${className}`}
      style={{
        background: 'transparent',
      }}
    />
  );
};


