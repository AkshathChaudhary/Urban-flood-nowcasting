/**
 * Resilient Turn-by-Turn Navigation & Vector Math Engine
 * =======================================================
 * Pure client-side calculations:
 * 1. Forward azimuth / bearing between coordinates (atan2)
 * 2. Relative turn deflection (straight, slight, regular, sharp, u-turn)
 * 3. Segment clustering into readable turn-by-turn instructions with street names
 * 4. Cross-track perpendicular distance for off-route detection (>35m)
 * 5. Web Speech API synthesis wrapper with audio queueing and mute support
 */

import type { RouteResult, RouteSegment } from './api';

export type ManeuverType =
  | 'depart'
  | 'straight'
  | 'slight-left'
  | 'turn-left'
  | 'sharp-left'
  | 'slight-right'
  | 'turn-right'
  | 'sharp-right'
  | 'u-turn'
  | 'arrive';

export interface NavigationStep {
  stepIndex: number;
  instruction: string;
  roadName: string;
  distance_m: number;
  duration_s: number;
  maneuver: ManeuverType;
  bearing: number;
  startCoord: [number, number]; // [lng, lat]
  endCoord: [number, number];   // [lng, lat]
  maxFloodDepth_m: number;
  floodRisk: 'SAFE' | 'MODERATE' | 'ELEVATED' | 'CRITICAL';
}

/**
 * Calculates forward compass azimuth bearing from p1 to p2 in degrees [0, 360)
 * Note: Coordinates are [lon, lat]
 */
export function calculateBearing(p1: [number, number], p2: [number, number]): number {
  const [lon1, lat1] = [(p1[0] * Math.PI) / 180, (p1[1] * Math.PI) / 180];
  const [lon2, lat2] = [(p2[0] * Math.PI) / 180, (p2[1] * Math.PI) / 180];

  const y = Math.sin(lon2 - lon1) * Math.cos(lat2);
  const x =
    Math.cos(lat1) * Math.sin(lat2) -
    Math.sin(lat1) * Math.cos(lat2) * Math.cos(lon2 - lon1);

  const initialBearing = (Math.atan2(y, x) * 180) / Math.PI;
  return (initialBearing + 360) % 360;
}

/**
 * Great-circle distance between two [lon, lat] points in meters using Haversine formula
 */
export function calculateDistanceMeters(p1: [number, number], p2: [number, number]): number {
  const R = 6371000; // Earth radius in meters
  const lat1 = (p1[1] * Math.PI) / 180;
  const lat2 = (p2[1] * Math.PI) / 180;
  const deltaLat = ((p2[1] - p1[1]) * Math.PI) / 180;
  const deltaLon = ((p2[0] - p1[0]) * Math.PI) / 180;

  const a =
    Math.sin(deltaLat / 2) * Math.sin(deltaLat / 2) +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(deltaLon / 2) * Math.sin(deltaLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

  return R * c;
}

/**
 * Classifies angular deflection into standard navigation maneuvers
 * delta = (b2 - b1 + 540) % 360 - 180
 * Positive = Right, Negative = Left
 */
export function classifyManeuver(b1: number, b2: number): ManeuverType {
  const delta = ((b2 - b1 + 540) % 360) - 180;

  if (Math.abs(delta) <= 22) return 'straight';
  if (delta > 22 && delta <= 60) return 'slight-right';
  if (delta > 60 && delta <= 125) return 'turn-right';
  if (delta > 125 && delta <= 165) return 'sharp-right';
  if (delta < -22 && delta >= -60) return 'slight-left';
  if (delta < -60 && delta >= -125) return 'turn-left';
  if (delta < -125 && delta >= -165) return 'sharp-left';
  return 'u-turn';
}

/**
 * Generates human-friendly instruction text from maneuver and road name
 */
export function formatInstructionText(
  maneuver: ManeuverType,
  roadName: string,
  distance_m: number,
  isFirst: boolean = false,
  isLast: boolean = false
): string {
  const cleanRoad = roadName && roadName !== 'Unnamed Road' ? roadName : 'the road';
  const distStr = distance_m >= 1000 ? `${(distance_m / 1000).toFixed(1)} km` : `${Math.round(distance_m)} m`;

  if (isFirst) {
    return `Head on ${cleanRoad}`;
  }
  if (isLast) {
    return `Arrive at destination on ${cleanRoad}`;
  }

  const forDist = distance_m > 0 ? ` (${distStr})` : '';

  switch (maneuver) {
    case 'straight':
      return `Continue straight on ${cleanRoad}${forDist}`;
    case 'slight-right':
      return `Keep right onto ${cleanRoad}${forDist}`;
    case 'turn-right':
      return `Turn right onto ${cleanRoad}${forDist}`;
    case 'sharp-right':
      return `Make a sharp right onto ${cleanRoad}${forDist}`;
    case 'slight-left':
      return `Keep left onto ${cleanRoad}${forDist}`;
    case 'turn-left':
      return `Turn left onto ${cleanRoad}${forDist}`;
    case 'sharp-left':
      return `Make a sharp left onto ${cleanRoad}${forDist}`;
    case 'u-turn':
      return `Make a U-turn onto ${cleanRoad}${forDist}`;
    default:
      return `Proceed onto ${cleanRoad}${forDist}`;
  }
}

/**
 * Converts a RouteResult into a sequential list of high-level turn-by-turn NavigationSteps
 */
export function generateTurnByTurnSteps(route: RouteResult): NavigationStep[] {
  const steps: NavigationStep[] = [];
  const coords: [number, number][] = (route.geojson?.geometry?.coordinates as [number, number][]) || [];
  const roads: RouteSegment[] = route.roads_traversed || [];

  if (coords.length < 2) {
    return steps;
  }

  // If we have detailed traversed edges, we group sequential edges with the same road name
  if (roads.length > 0) {
    let currentRoadName = roads[0].name || 'Unnamed Road';
    let currentDist = 0;
    let maxDepth = roads[0].flood_depth_m || 0;
    let segmentStartIndex = 0;
    let prevBearing = calculateBearing(coords[0], coords[1]);

    // Depart step
    steps.push({
      stepIndex: 0,
      instruction: formatInstructionText('depart', currentRoadName, 0, true, false),
      roadName: currentRoadName,
      distance_m: 0,
      duration_s: 0,
      maneuver: 'depart',
      bearing: prevBearing,
      startCoord: coords[0],
      endCoord: coords[1] || coords[0],
      maxFloodDepth_m: maxDepth,
      floodRisk: maxDepth > 0.3 ? 'CRITICAL' : maxDepth > 0.15 ? 'ELEVATED' : 'SAFE',
    });

    for (let i = 0; i < roads.length; i++) {
      const road = roads[i];
      const rName = road.name || 'Unnamed Road';
      currentDist += road.length_m || 0;
      if ((road.flood_depth_m || 0) > maxDepth) {
        maxDepth = road.flood_depth_m;
      }

      const isLastRoad = i === roads.length - 1;
      const isRoadNameChange = rName !== currentRoadName;

      // When street name changes or at the end of the route, compile a step
      if (isRoadNameChange || isLastRoad) {
        const approxCoordIdx = Math.min(
          coords.length - 1,
          Math.max(1, Math.round((i / roads.length) * coords.length))
        );
        const nextCoord = coords[approxCoordIdx] || coords[coords.length - 1];
        const nextBearing = approxCoordIdx < coords.length - 1
          ? calculateBearing(coords[approxCoordIdx], coords[approxCoordIdx + 1])
          : prevBearing;

        const maneuver = classifyManeuver(prevBearing, nextBearing);
        const instr = formatInstructionText(maneuver, currentRoadName, currentDist, false, false);

        steps.push({
          stepIndex: steps.length,
          instruction: instr,
          roadName: currentRoadName,
          distance_m: Math.round(currentDist),
          duration_s: Math.round(currentDist / 8.33), // ~30 km/h average
          maneuver: maneuver,
          bearing: nextBearing,
          startCoord: coords[segmentStartIndex] || coords[0],
          endCoord: nextCoord,
          maxFloodDepth_m: maxDepth,
          floodRisk: maxDepth > 0.3 ? 'CRITICAL' : maxDepth > 0.15 ? 'ELEVATED' : 'SAFE',
        });

        // Reset for next cluster
        currentRoadName = rName;
        currentDist = 0;
        maxDepth = road.flood_depth_m || 0;
        segmentStartIndex = approxCoordIdx;
        prevBearing = nextBearing;
      }
    }

    // Add Final Arrival Step
    const lastCoord = coords[coords.length - 1];
    steps.push({
      stepIndex: steps.length,
      instruction: formatInstructionText('arrive', currentRoadName, 0, false, true),
      roadName: currentRoadName,
      distance_m: 0,
      duration_s: 0,
      maneuver: 'arrive',
      bearing: prevBearing,
      startCoord: lastCoord,
      endCoord: lastCoord,
      maxFloodDepth_m: 0,
      floodRisk: 'SAFE',
    });

    return steps;
  }

  // Fallback: If no road attributes available, calculate solely from geometry vertices
  let accumulatedDist = 0;
  let prevB = calculateBearing(coords[0], coords[1]);

  steps.push({
    stepIndex: 0,
    instruction: 'Head towards destination',
    roadName: 'Main Route',
    distance_m: 0,
    duration_s: 0,
    maneuver: 'depart',
    bearing: prevB,
    startCoord: coords[0],
    endCoord: coords[1],
    maxFloodDepth_m: 0,
    floodRisk: 'SAFE',
  });

  for (let i = 1; i < coords.length - 1; i++) {
    accumulatedDist += calculateDistanceMeters(coords[i - 1], coords[i]);
    const nextB = calculateBearing(coords[i], coords[i + 1]);
    const maneuver = classifyManeuver(prevB, nextB);

    if (maneuver !== 'straight' || accumulatedDist > 500) {
      steps.push({
        stepIndex: steps.length,
        instruction: formatInstructionText(maneuver, 'Corridor', accumulatedDist),
        roadName: 'Corridor',
        distance_m: Math.round(accumulatedDist),
        duration_s: Math.round(accumulatedDist / 8.33),
        maneuver,
        bearing: nextB,
        startCoord: coords[i],
        endCoord: coords[i + 1],
        maxFloodDepth_m: 0,
        floodRisk: 'SAFE',
      });
      accumulatedDist = 0;
      prevB = nextB;
    }
  }

  const finalPt = coords[coords.length - 1];
  steps.push({
    stepIndex: steps.length,
    instruction: 'Arrive at destination',
    roadName: 'Destination',
    distance_m: 0,
    duration_s: 0,
    maneuver: 'arrive',
    bearing: prevB,
    startCoord: finalPt,
    endCoord: finalPt,
    maxFloodDepth_m: 0,
    floodRisk: 'SAFE',
  });

  return steps;
}

/**
 * Calculates perpendicular cross-track distance (in meters) from point P to line segment AB.
 * Used for instant off-route detection (>35m threshold).
 */
export function getDistanceToSegmentMeters(
  point: [number, number],
  segA: [number, number],
  segB: [number, number]
): number {
  const deg2rad = Math.PI / 180;
  const cosLat = Math.cos(segA[1] * deg2rad);

  const x = (point[0] - segA[0]) * 111320 * cosLat;
  const y = (point[1] - segA[1]) * 110540;

  const x2 = (segB[0] - segA[0]) * 111320 * cosLat;
  const y2 = (segB[1] - segA[1]) * 110540;

  const lineLenSq = x2 * x2 + y2 * y2;
  if (lineLenSq === 0) {
    return Math.sqrt(x * x + y * y);
  }

  const t = Math.max(0, Math.min(1, (x * x2 + y * y2) / lineLenSq));
  const projX = t * x2;
  const projY = t * y2;

  const dx = x - projX;
  const dy = y - projY;

  return Math.sqrt(dx * dx + dy * dy);
}

/**
 * Finds the minimum distance from current position to ANY segment on the route polyline.
 */
export function getMinDistanceToRouteMeters(
  currentPos: [number, number],
  routeCoords: [number, number][]
): { minDistance_m: number; nearestSegmentIndex: number } {
  if (routeCoords.length < 2) {
    return { minDistance_m: 0, nearestSegmentIndex: 0 };
  }

  let minDistance = Infinity;
  let nearestIdx = 0;

  for (let i = 0; i < routeCoords.length - 1; i++) {
    const dist = getDistanceToSegmentMeters(currentPos, routeCoords[i], routeCoords[i + 1]);
    if (dist < minDistance) {
      minDistance = dist;
      nearestIdx = i;
    }
  }

  return { minDistance_m: minDistance, nearestSegmentIndex: nearestIdx };
}

/**
 * Speech Guidance System using native Web Speech API (zero cost, zero cloud latency)
 */
class NavigationVoiceService {
  private isMuted: boolean = false;
  private lastSpokenText: string = '';
  private lastSpokenTime: number = 0;

  constructor() {
    this.isMuted = false;
  }

  public setMuted(muted: boolean) {
    this.isMuted = muted;
    if (muted && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
  }

  public getIsMuted(): boolean {
    return this.isMuted;
  }

  public speak(text: string, force: boolean = false, speedMultiplier: number = 1.0) {
    if (this.isMuted) return;
    if (!('speechSynthesis' in window)) {
      console.warn('Web Speech API is not supported in this browser.');
      return;
    }

    const now = Date.now();
    // In accelerated simulation, lower repeat suppression window so rapid turns can be announced
    const minInterval = speedMultiplier > 2 ? 1500 : speedMultiplier > 1 ? 3000 : 6000;
    if (!force && text === this.lastSpokenText && now - this.lastSpokenTime < minInterval) {
      return;
    }

    this.lastSpokenText = text;
    this.lastSpokenTime = now;

    // Immediately cancel any previous or lagging speech queue so turns never overlap
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    // Rate scales proportionally with simulation speed (Web Speech API supports 0.1 to 10.0, standard 1-2.5)
    const scaledRate = Math.min(2.5, Math.max(1.0, 1.05 * (1 + (speedMultiplier - 1) * 0.35)));
    utterance.rate = scaledRate;
    utterance.pitch = 1.0;
    utterance.volume = 1.0;

    const voices = window.speechSynthesis.getVoices();
    const naturalVoice = voices.find(
      (v) => (v.name.includes('Natural') || v.name.includes('Google') || v.lang.startsWith('en')) && !v.name.includes('Whisper')
    );
    if (naturalVoice) {
      utterance.voice = naturalVoice;
    }

    window.speechSynthesis.speak(utterance);
  }

  public stop() {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
  }
}

export const navigationVoice = new NavigationVoiceService();
