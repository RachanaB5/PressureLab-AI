import type { PitchFrame, PitchPlayer } from '../components/workspace/MomentPitch';

export type PitchCamera = { cx: number; cy: number; zoom: number };

export const DEFAULT_CAMERA: PitchCamera = { cx: 60, cy: 40, zoom: 1 };

/** Event transition duration (ms) — timeline click animates over this window. */
export const TRANSITION_MS = 800;
export const WITHIN_MOMENT_MS = 1800;

export function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

export function easeInOutCubic(t: number) {
  const c = Math.max(0, Math.min(1, t));
  return c < 0.5 ? 4 * c * c * c : 1 - Math.pow(-2 * c + 2, 3) / 2;
}

/** Ball uses a slightly snappier ease so it leads player movement. */
export function easeOutQuad(t: number) {
  const c = Math.max(0, Math.min(1, t));
  return 1 - (1 - c) * (1 - c);
}

export function bezierPoint(
  from: [number, number],
  to: [number, number],
  t: number,
  arc = 8,
): [number, number] {
  const mx = (from[0] + to[0]) / 2;
  const my = (from[1] + to[1]) / 2 - arc;
  const u = 1 - t;
  return [
    u * u * from[0] + 2 * u * t * mx + t * t * to[0],
    u * u * from[1] + 2 * u * t * my + t * t * to[1],
  ];
}

export function bezierPathD(
  from: [number, number],
  to: [number, number],
  sx: (x: number) => number,
  sy: (y: number) => number,
  arc = 8,
) {
  const mx = (from[0] + to[0]) / 2;
  const my = (from[1] + to[1]) / 2 - arc;
  return `M ${sx(from[0])} ${sy(from[1])} Q ${sx(mx)} ${sy(my)} ${sx(to[0])} ${sy(to[1])}`;
}

export function getConvexHull(points: {x: number; y: number}[]): {x: number; y: number}[] {
  if (points.length <= 3) return points;
  const pts = [...points].sort((a, b) => a.x === b.x ? a.y - b.y : a.x - b.x);
  const cross = (o: any, a: any, b: any) => (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x);
  const lower = [];
  for (let i = 0; i < pts.length; i++) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], pts[i]) <= 0) lower.pop();
    lower.push(pts[i]);
  }
  const upper = [];
  for (let i = pts.length - 1; i >= 0; i--) {
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], pts[i]) <= 0) upper.pop();
    upper.push(pts[i]);
  }
  upper.pop();
  lower.pop();
  return lower.concat(upper);
}

function clampCoord(x: number, y: number): [number, number] {
  return [Math.max(8, Math.min(112, x)), Math.max(6, Math.min(74, y))];
}

function roleWeight(p: PitchPlayer): { wx: number; wy: number } {
  const role = p.role ?? '';
  if (role.includes('Defender') || (p.team === 'home' && p.x < 35) || (p.team === 'away' && p.x > 85)) {
    return { wx: 0.68, wy: 0.32 };
  }
  if (role.includes('Midfielder')) return { wx: 0.48, wy: 0.28 };
  return { wx: 0.82, wy: 0.45 };
}

/** Ensure pitch has replay tracks even when API omits them (stale cache / old backend). */
export function enrichPitchForReplay(pitch: PitchFrame): PitchFrame {
  const ball = pitch.ball;
  const ballStart = pitch.ball_start ?? {
    x: Math.max(10, ball.x - 14),
    y: ball.y,
  };
  const ballDx = ball.x - ballStart.x;
  const ballDy = ball.y - ballStart.y;
  const pressAvg =
    pitch.players.reduce((s, p) => s + (p.pressure ?? 50), 0) / Math.max(pitch.players.length, 1);
  const compress = (pressAvg - 50) / 100;

  const players: PitchPlayer[] = pitch.players.map(p => {
    const toX = p.to_x ?? p.x;
    const toY = p.to_y ?? p.y;
    let fromX = p.from_x;
    let fromY = p.from_y;
    if (fromX == null || fromY == null) {
      const { wx, wy } = roleWeight(p);
      const sign = p.team === 'home' ? 1 : -1;
      fromX = p.x - sign * ballDx * wx - sign * 5;
      fromY = p.y - ballDy * wy;
      if ((p.role ?? '').includes('Midfielder')) {
        fromY += compress * 4 * (p.y > 40 ? 1 : -1);
      }
      [fromX, fromY] = clampCoord(fromX, fromY);
    }
    if (Math.hypot(toX - fromX, toY - fromY) < 5.0) {
      const { wx } = roleWeight(p);
      const sign = p.team === 'home' ? 1 : -1;
      fromX = toX - sign * Math.max(6, Math.abs(ballDx) * wx + 4);
      fromY = toY - Math.max(3, Math.abs(ballDy) * 0.4 + 2);
      [fromX, fromY] = clampCoord(fromX, fromY);
    }
    const fromPressure =
      p.from_pressure ??
      Math.max(20, Math.min(95, (p.pressure ?? 50) - Math.abs(ballDx) * 0.12 - compress * 8));
    return {
      ...p,
      from_x: fromX,
      from_y: fromY,
      to_x: toX,
      to_y: toY,
      from_pressure: fromPressure,
    };
  });

  const homeLine = pitch.defensive_lines?.home ?? 22;
  const awayLine = pitch.defensive_lines?.away ?? 98;
  const homeStart = pitch.defensive_lines?.home_start ?? homeLine - ballDx * 0.55 - compress * 2;
  const awayStart = pitch.defensive_lines?.away_start ?? awayLine - ballDx * 0.45 + compress * 2;

  const danger = pitch.danger_zone ?? {
    x: ball.x + (ball.x > 60 ? 4 : -4),
    y: ball.y,
    radius: 12,
    intensity: 0.5,
  };
  const dangerStart = pitch.danger_zone_start ?? {
    x: ballStart.x + (ballStart.x > 60 ? 3 : -3),
    y: ballStart.y,
    radius: danger.radius * 0.85,
    intensity: (danger.intensity ?? 0.5) * 0.8,
  };

  const replay_start = pitch.replay_start?.players?.length
    ? pitch.replay_start
    : {
        ball: ballStart,
        players: players.map(p => ({
          id: p.id,
          x: p.from_x!,
          y: p.from_y!,
          name: p.name,
          team: p.team,
          pressure: p.from_pressure ?? p.pressure,
          is_active: p.is_active,
          xthreat: (p.xthreat ?? 0.1) * 0.7,
        })),
        home_team: pitch.home_team,
        away_team: pitch.away_team,
        passing_lanes: pitch.passing_lanes_start ?? [],
        pressure_zones: pitch.pressure_zones_start ?? [],
        defensive_lines: { home: homeStart, away: awayStart },
        danger_zone: dangerStart,
      };

  return {
    ...pitch,
    ball_start: ballStart,
    players,
    replay_start,
    passing_lanes_start: pitch.passing_lanes_start ?? pitch.replay_start?.passing_lanes ?? [],
    pressure_zones_start: pitch.pressure_zones_start ?? pitch.replay_start?.pressure_zones ?? [],
    defensive_lines: {
      home: homeLine,
      away: awayLine,
      home_start: homeStart,
      away_start: awayStart,
    },
    danger_zone: danger,
    danger_zone_start: dangerStart,
    transition_ms: pitch.transition_ms ?? TRANSITION_MS,
  };
}

export function buildStartFrameFromPitch(pitch: PitchFrame): PitchFrame {
  const enriched = enrichPitchForReplay(pitch);
  const rs = enriched.replay_start;
  return {
    ...enriched,
    ball: rs?.ball ?? enriched.ball_start ?? enriched.ball,
    players: (rs?.players ?? enriched.players).map(p => ({
      ...p,
      x: 'from_x' in p && p.from_x != null ? (p as PitchPlayer).from_x! : p.x,
      y: 'from_y' in p && p.from_y != null ? (p as PitchPlayer).from_y! : p.y,
    })),
    passing_lanes: rs?.passing_lanes ?? enriched.passing_lanes_start ?? [],
    pressure_zones: rs?.pressure_zones ?? enriched.pressure_zones_start ?? [],
    defensive_lines: {
      home: rs?.defensive_lines?.home ?? enriched.defensive_lines?.home_start ?? 22,
      away: rs?.defensive_lines?.away ?? enriched.defensive_lines?.away_start ?? 98,
    },
    danger_zone: rs?.danger_zone ?? enriched.danger_zone_start,
  };
}

function rebuildPressureZones(players: PitchPlayer[], t: number): PitchFrame['pressure_zones'] {
  return players
    .filter(p => (p.pressure ?? 0) > 40)
    .map(p => ({
      x: p.x,
      y: p.y,
      radius: (6 + (p.pressure ?? 50) / 18) * (0.55 + t * 0.45),
      intensity: ((p.pressure ?? 50) / 100) * (0.4 + t * 0.6),
    }));
}

function morphLanes(
  from: PitchFrame['passing_lanes'],
  to: PitchFrame['passing_lanes'],
  t: number,
): PitchFrame['passing_lanes'] {
  const eased = easeInOutCubic(t);
  const dest = to ?? [];
  if (!dest.length) return from?.length ? morphLanes(from, [], 1 - eased) ?? [] : [];
  const src = from ?? [];
  return dest.map((lane, i) => {
    const prev = src[i];
    if (!prev) {
      return {
        ...lane,
        from: [lerp(lane.from[0] - 12, lane.from[0], eased), lerp(lane.from[1], lane.from[1], eased)],
        to: [lerp(lane.to[0] - 14, lane.to[0], eased), lerp(lane.to[1], lane.to[1], eased)],
        success: lane.success,
      };
    }
    return {
      ...lane,
      from: [lerp(prev.from[0], lane.from[0], eased), lerp(prev.from[1], lane.from[1], eased)],
      to: [lerp(prev.to[0], lane.to[0], eased), lerp(prev.to[1], lane.to[1], eased)],
      success: lane.success,
    };
  });
}

function morphDangerZone(
  from: PitchFrame['danger_zone'],
  to: PitchFrame['danger_zone'],
  t: number,
): PitchFrame['danger_zone'] {
  const eased = easeInOutCubic(t);
  const a = from ?? to ?? { x: 60, y: 40, radius: 10, intensity: 0.4 };
  const b = to ?? from ?? a;
  return {
    x: lerp(a.x, b.x, eased),
    y: lerp(a.y, b.y, eased),
    radius: lerp(a.radius ?? 10, b.radius ?? 10, eased),
    intensity: lerp(a.intensity ?? 0.4, b.intensity ?? 0.4, eased),
  };
}

function morphDefensiveLines(
  from: PitchFrame['defensive_lines'],
  to: PitchFrame['defensive_lines'],
  t: number,
): PitchFrame['defensive_lines'] {
  const eased = easeInOutCubic(t);
  const a = from ?? { home: 22, away: 98 };
  const b = to ?? a;
  return {
    home: lerp(a.home ?? 22, b.home ?? 22, eased),
    away: lerp(a.away ?? 98, b.away ?? 98, eased),
    home_start: a.home_start,
    away_start: a.away_start,
  };
}

/**
 * Interpolate full pitch state — all 22 players, ball, lanes, pressure, danger zone.
 */
export function interpolatePitchFrame(
  from: PitchFrame | null,
  to: PitchFrame,
  replayT: number,
): PitchFrame {
  const enrichedTo = enrichPitchForReplay(to);
  const start = from ? enrichPitchForReplay(from) : buildStartFrameFromPitch(enrichedTo);
  const enrichedStart = from ? start : enrichPitchForReplay(start);
  const t = easeInOutCubic(Math.max(0, Math.min(1, replayT)));
  const ballT = easeOutQuad(Math.max(0, Math.min(1, replayT)));

  const fromMap = new Map(enrichedStart.players.map(p => [p.id, p]));
  const ballFrom = enrichedStart.ball ?? enrichedTo.ball_start ?? enrichedTo.ball;
  const ballTo = enrichedTo.ball;

  let ball = { x: lerp(ballFrom.x, ballTo.x, ballT), y: lerp(ballFrom.y, ballTo.y, ballT) };

  const lanesFrom = enrichedStart.passing_lanes ?? enrichedTo.passing_lanes_start ?? [];
  const lanesInterp = morphLanes(lanesFrom, enrichedTo.passing_lanes, t) ?? [];

  if (lanesInterp.length > 0 && ballT < 0.85) {
    const lane = lanesInterp[0];
    const pt = bezierPoint(
      [lane.from[0], lane.from[1]],
      [lane.to[0], lane.to[1]],
      ballT / 0.85,
      Math.abs(ballTo.x - ballFrom.x) * 0.1 + 7,
    );
    ball = { x: pt[0], y: pt[1] };
  }

  const players: PitchPlayer[] = enrichedTo.players.map(p => {
    const fp = fromMap.get(p.id);
    const fx = fp?.x ?? p.from_x ?? p.x;
    const fy = fp?.y ?? p.from_y ?? p.y;
    const tx = p.to_x ?? p.x;
    const ty = p.to_y ?? p.y;
    const pressFrom = fp?.pressure ?? p.from_pressure ?? p.pressure ?? 50;
    const pressTo = p.pressure ?? 50;
    return {
      ...p,
      x: lerp(fx, tx, t),
      y: lerp(fy, ty, t),
      pressure: lerp(pressFrom, pressTo, t),
      pressure_index: Math.round(lerp(pressFrom, pressTo, t)),
      xthreat: lerp((fp?.xthreat ?? p.xthreat ?? 0.1) * 0.85, p.xthreat ?? 0.1, t),
    };
  });

  const zonesFrom = enrichedStart.pressure_zones ?? enrichedTo.pressure_zones_start ?? [];
  const zonesTo = rebuildPressureZones(
    enrichedTo.players.map(p => ({
      ...p,
      x: p.to_x ?? p.x,
      y: p.to_y ?? p.y,
      pressure: p.pressure,
    })),
    1,
  ) ?? [];
  const pressure_zones = zonesFrom.length
    ? zonesFrom.map((z, i) => {
        const end = zonesTo[i] ?? zonesTo[0] ?? z;
        return {
          x: lerp(z.x, end.x, t),
          y: lerp(z.y, end.y, t),
          radius: lerp(z.radius * 0.5, end.radius, t),
          intensity: lerp((z.intensity ?? 0.3) * 0.4, end.intensity ?? 0.5, t),
        };
      })
    : rebuildPressureZones(players, t);

  return {
    ...enrichedTo,
    ball,
    players,
    passing_lanes: lanesInterp,
    pressure_zones,
    defensive_lines: morphDefensiveLines(enrichedStart.defensive_lines, enrichedTo.defensive_lines, t),
    danger_zone: morphDangerZone(enrichedStart.danger_zone, enrichedTo.danger_zone, t),
    pitch_adjustment: enrichedTo.pitch_adjustment,
  };
}

export function buildPitchEndState(pitch: PitchFrame): PitchFrame {
  const enriched = enrichPitchForReplay(pitch);
  return {
    ...enriched,
    ball: { ...enriched.ball },
    players: enriched.players.map(p => ({
      ...p,
      x: p.to_x ?? p.x,
      y: p.to_y ?? p.y,
      pressure: p.pressure ?? 50,
    })),
    passing_lanes: enriched.passing_lanes ?? [],
    pressure_zones: enriched.pressure_zones ?? [],
    defensive_lines: enriched.defensive_lines,
    danger_zone: enriched.danger_zone,
  };
}

export type HeatCell = { x: number; y: number; value: number };

export function buildXThreatHeatmap(players: PitchPlayer[], cols = 14, rows = 9): HeatCell[] {
  const cells: HeatCell[] = [];
  const cellW = 120 / cols;
  const cellH = 80 / rows;
  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      const cx = col * cellW + cellW / 2;
      const cy = row * cellH + cellH / 2;
      let value = 0;
      for (const p of players) {
        const xt = p.xthreat ?? 0;
        const d = Math.hypot(p.x - cx, p.y - cy);
        value += xt * Math.max(0, 1 - d / 25);
      }
      if (value > 0.05) cells.push({ x: cx, y: cy, value: Math.min(1, value) });
    }
  }
  return cells;
}

export function computeCamera(
  ball: { x: number; y: number },
  players: PitchPlayer[],
  zoom = 1.65,
): PitchCamera {
  const active = players.find(p => p.is_active);
  const cx = active ? lerp(active.x, ball.x, 0.4) : ball.x;
  const cy = active ? lerp(active.y, ball.y, 0.4) : ball.y;
  return {
    cx: Math.max(25, Math.min(95, cx)),
    cy: Math.max(15, Math.min(65, cy)),
    zoom: ball.x > 85 ? zoom + 0.25 : zoom,
  };
}

export function crowdIntensityFromPressure(pressure?: number, eventType?: string): number {
  let base = (pressure ?? 50) / 100;
  if (eventType === 'Goal' || eventType === 'Shot') base += 0.25;
  return Math.min(1, base);
}
