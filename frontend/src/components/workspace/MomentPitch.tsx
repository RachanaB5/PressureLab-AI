import { useState, useMemo, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  interpolatePitchFrame,
  buildXThreatHeatmap,
  bezierPathD,
  bezierPoint,
  lerp,
  getConvexHull,
  type PitchCamera,
  DEFAULT_CAMERA,
} from '../../utils/replayPhysics';

export interface PitchPlayer {
  id: string;
  x: number;
  y: number;
  name: string;
  team: 'home' | 'away';
  pressure?: number;
  is_active?: boolean;
  role?: string;
  speed_kmh?: number;
  decision_score?: number;
  xthreat?: number;
  pressure_index?: number;
  expected_action?: string;
  pass_options?: Array<{ type: string; success_prob?: number; xG?: number }>;
  space_control_pct?: number;
  from_x?: number;
  from_y?: number;
  to_x?: number;
  to_y?: number;
  from_pressure?: number;
}

export interface PitchFrame {
  ball: { x: number; y: number };
  ball_start?: { x: number; y: number };
  replay_start?: PitchFrame;
  players: PitchPlayer[];
  passing_lanes?: Array<{ from: number[]; to: number[]; success?: boolean }>;
  passing_lanes_start?: Array<{ from: number[]; to: number[]; success?: boolean }>;
  movements?: Array<{ from: number[]; to: number[]; player?: string }>;
  pressure_zones?: Array<{ x: number; y: number; radius: number; intensity: number }>;
  pressure_zones_start?: Array<{ x: number; y: number; radius: number; intensity: number }>;
  defensive_lines?: { home?: number; away?: number; home_start?: number; away_start?: number };
  team_shape?: { home?: { width: number; depth: number; compactness: number; offside_line: number; }; away?: { width: number; depth: number; compactness: number; offside_line: number; } };
  danger_zone?: { x: number; y: number; radius: number; intensity?: number };
  danger_zone_start?: { x: number; y: number; radius: number; intensity?: number };
  transition_ms?: number;
  home_team?: string;
  away_team?: string;
  pitch_adjustment?: { defensive_line?: number; press_radius?: number; passing_speed?: number };
}

const PW = 120;
const PH = 80;

type Props = {
  frame: PitchFrame | null;
  selectedPlayerId?: string | null;
  onSelectPlayer?: (id: string | null) => void;
  highlight?: string | null;
  animateKey?: string | number;
  compact?: boolean;
  replayProgress?: number;
  extraHighlights?: string[];
  frozen?: boolean;
  camera?: PitchCamera;
  crowdIntensity?: number;
  highlightedPlayerIds?: string[];
  showHeatmap?: boolean;
  enhancedPlayerFocus?: boolean;
  showPlayerMetrics?: boolean;
  loading?: boolean;
  pitchFrom?: PitchFrame | null;
};

export function MomentPitch({
  frame,
  selectedPlayerId,
  onSelectPlayer,
  highlight,
  animateKey = 0,
  compact = false,
  replayProgress = 1,
  extraHighlights = [],
  frozen = false,
  camera = DEFAULT_CAMERA,
  crowdIntensity = 0,
  highlightedPlayerIds = [],
  showHeatmap = true,
  enhancedPlayerFocus = false,
  showPlayerMetrics = true,
  loading = false,
  pitchFrom = null,
}: Props) {
  const [hoverId, setHoverId] = useState<string | null>(null);
  const [animPhase, setAnimPhase] = useState(0);

  const width = compact ? 420 : 900;
  const height = compact ? 280 : 560;
  const sx = (x: number) => (x / PW) * width;
  const sy = (y: number) => (y / PH) * height;

  const z = camera.zoom;
  const vbW = width / z;
  const vbH = height / z;
  const vbX = sx(camera.cx) - vbW / 2;
  const vbY = sy(camera.cy) - vbH / 2;
  const viewBox = `${vbX} ${vbY} ${vbW} ${vbH}`;

  useEffect(() => {
    setAnimPhase(0);
    const t = setInterval(() => setAnimPhase(p => (p + 1) % 60), 50);
    return () => clearInterval(t);
  }, [animateKey, frame?.ball?.x, frame?.ball?.y]);

  const replayT = Math.max(0, Math.min(1, replayProgress));
  const moves = useMemo(() => frame?.movements ?? [], [frame]);

  const liveFrame = useMemo(
    () => (frame ? interpolatePitchFrame(pitchFrom, frame, replayT) : null),
    [frame, pitchFrom, replayT],
  );

  const focusEnhanced = enhancedPlayerFocus && !!selectedPlayerId;

  const memoizedDrawData = useMemo(() => {
    if (!liveFrame) return { livePlayers: [], lanes: [], movements: [], zones: [], defLines: undefined, dangerZone: undefined, pressRadius: 12, homeHull: '', awayHull: '', offsideHome: undefined, offsideAway: undefined };
    
    const offsideHome = liveFrame.team_shape?.home?.offside_line;
    const offsideAway = liveFrame.team_shape?.away?.offside_line;
    
    let homeHull: string = '';
    let awayHull: string = '';
    if (liveFrame.players && liveFrame.players.length > 0) {
      const homePl = liveFrame.players.filter(p => p.team === 'home');
      const awayPl = liveFrame.players.filter(p => p.team === 'away');
      if (homePl.length >= 3) {
        const hull = getConvexHull(homePl.map(p => ({ x: sx(p.x), y: sy(p.y) })));
        homeHull = hull.map(p => `${p.x},${p.y}`).join(' ');
      }
      if (awayPl.length >= 3) {
        const hull = getConvexHull(awayPl.map(p => ({ x: sx(p.x), y: sy(p.y) })));
        awayHull = hull.map(p => `${p.x},${p.y}`).join(' ');
      }
    }

    return {
      livePlayers: liveFrame.players,
      lanes: liveFrame.passing_lanes ?? [],
      movements: liveFrame.movements ?? [],
      zones: liveFrame.pressure_zones ?? [],
      defLines: liveFrame.defensive_lines,
      dangerZone: liveFrame.danger_zone,
      pressRadius: liveFrame.pitch_adjustment?.press_radius ?? 12,
      homeHull,
      awayHull,
      offsideHome,
      offsideAway,
    };
  }, [liveFrame, sx, sy, focusEnhanced, selectedPlayerId]);

  const { livePlayers, lanes, movements, zones, defLines, dangerZone, pressRadius } = memoizedDrawData;
  const ballReplay = liveFrame?.ball ?? { x: 60, y: 40 };

  const heatCells = useMemo(() => (showHeatmap ? buildXThreatHeatmap(livePlayers) : []), [livePlayers, showHeatmap]);

  const selected = livePlayers.find(p => p.id === selectedPlayerId);
  const hovered = livePlayers.find(p => p.id === hoverId);
  const focus = selected ?? hovered;

  if (!frame) {
    return (
      <div className="w-full aspect-[120/80] rounded-xl bg-bg-secondary border border-border-glass flex items-center justify-center text-text-muted text-sm">
        {loading ? 'Reconstructing digital twin…' : 'Select a moment on the timeline'}
      </div>
    );
  }



  const ballAnim = {
    x: sx(ballReplay.x + (frozen ? 0 : Math.sin(animPhase / 10) * 0.2)),
    y: sy(ballReplay.y + (frozen ? 0 : Math.cos(animPhase / 10) * 0.15)),
  };

  return (
    <div
      className="relative w-full rounded-xl overflow-hidden border border-border-glass shadow-2xl group"
    >
      {crowdIntensity > 0.3 && (
        <motion.div
          className="absolute inset-0 pointer-events-none z-10"
          style={{
            background: `radial-gradient(ellipse at center, transparent 40%, rgba(0,0,0,${crowdIntensity * 0.35}) 100%)`,
            boxShadow: `inset 0 0 ${40 + crowdIntensity * 60}px rgba(239,68,68,${crowdIntensity * 0.15})`,
          }}
          animate={{ opacity: [0.7, 1, 0.7] }}
          transition={{ repeat: Infinity, duration: 2.5 }}
        />
      )}

      <svg viewBox={viewBox} className="w-full h-auto bg-[#1a3d2a]">
        {[0, 1, 2, 3, 4, 5].map(i => (
          <rect key={i} x={sx(i * 20)} y={0} width={sx(20)} height={height}
            fill={i % 2 === 0 ? '#1e4d32' : '#1a3d2a'} />
        ))}
        <g stroke="rgba(255,255,255,0.45)" strokeWidth={1.5 / z} fill="none">
          <rect x={2} y={2} width={width - 4} height={height - 4} />
          <line x1={sx(60)} y1={0} x2={sx(60)} y2={height} />
          <circle cx={sx(60)} cy={sy(40)} r={sx(9.15)} />
          <rect x={0} y={sy(18)} width={sx(18)} height={sy(44)} />
          <rect x={sx(102)} y={sy(18)} width={sx(18)} height={sy(44)} />
        </g>

        {/* xThreat heatmap */}
        {heatCells.map((c, i) => (
          <rect
            key={`h${i}`}
            x={sx(c.x - 4.3)} y={sy(c.y - 2.9)}
            width={sx(8.6)} height={sy(5.8)}
            fill={`rgba(250,204,21,${c.value * 0.35})`}
            rx={2}
          />
        ))}



        {/* Team Shape Polygons */}
        {memoizedDrawData.homeHull && (
          <polygon 
            points={memoizedDrawData.homeHull} 
            fill="rgba(96, 165, 250, 0.05)" 
            stroke="rgba(96, 165, 250, 0.2)" 
            strokeWidth={1 / z} 
            strokeDasharray={`${4/z} ${4/z}`}
          />
        )}
        {memoizedDrawData.awayHull && (
          <polygon 
            points={memoizedDrawData.awayHull} 
            fill="rgba(248, 113, 113, 0.05)" 
            stroke="rgba(248, 113, 113, 0.2)" 
            strokeWidth={1 / z} 
            strokeDasharray={`${4/z} ${4/z}`}
          />
        )}

        {/* Dynamic Offside Lines (based on live team shape) */}
        {memoizedDrawData.offsideHome !== undefined && (
          <line
            x1={sx(memoizedDrawData.offsideHome)} y1={sy(2)}
            x2={sx(memoizedDrawData.offsideHome)} y2={sy(78)}
            stroke="rgba(96, 165, 250, 0.6)" strokeWidth={1.5 / z} strokeDasharray={`${8 / z} ${4 / z}`}
          />
        )}
        {memoizedDrawData.offsideAway !== undefined && (
          <line
            x1={sx(memoizedDrawData.offsideAway)} y1={sy(2)}
            x2={sx(memoizedDrawData.offsideAway)} y2={sy(78)}
            stroke="rgba(248, 113, 113, 0.6)" strokeWidth={1.5 / z} strokeDasharray={`${8 / z} ${4 / z}`}
          />
        )}

        {/* Defensive lines — static overlay if needed (fading out for dynamic offside) */}
        {defLines && !memoizedDrawData.offsideHome && (
          <g opacity={0.35 + replayT * 0.35}>
            <line
              x1={sx(defLines.home ?? 22)} y1={sy(8)}
              x2={sx(defLines.home ?? 22)} y2={sy(72)}
              stroke="#60a5fa" strokeWidth={2 / z} strokeDasharray={`${6 / z} ${4 / z}`}
            />
            <line
              x1={sx(defLines.away ?? 98)} y1={sy(8)}
              x2={sx(defLines.away ?? 98)} y2={sy(72)}
              stroke="#f87171" strokeWidth={2 / z} strokeDasharray={`${6 / z} ${4 / z}`}
            />
          </g>
        )}

        {/* Danger zone — follows ball / possession */}
        {dangerZone && (
          <ellipse
            cx={sx(dangerZone.x)} cy={sy(dangerZone.y)}
            rx={sx(dangerZone.radius)} ry={sy(dangerZone.radius * 0.65)}
            fill={`rgba(250,204,21,${(dangerZone.intensity ?? 0.4) * (0.25 + replayT * 0.5)})`}
            stroke="rgba(250,204,21,0.55)" strokeWidth={1.2 / z}
          />
        )}

        {zones.map((zone, i) => {
          const pulse = 1 + Math.sin(animPhase / 8 + i) * 0.08;
          const growT = Math.max(0.15, replayT);
          return (
            <circle key={i}
              cx={sx(zone.x)} cy={sy(zone.y)}
              r={sx((zone.radius + pressRadius * 0.03) * pulse * growT)}
              fill={`rgba(255,80,80,${(zone.intensity ?? 0.4) * growT * 0.35})`}
              stroke={`rgba(255,80,80,${0.25 + growT * 0.5})`} strokeWidth={1.2 / z}
            />
          );
        })}

        {/* Curved passing lanes */}
        {lanes.map((lane, i) => {
          if (focusEnhanced && selectedPlayerId) {
            const sp = livePlayers.find(p => p.id === selectedPlayerId);
            if (sp && Math.hypot(lane.from[0] - sp.x, lane.from[1] - sp.y) > 18) return null;
          }
          const pathD = bezierPathD(
            [lane.from[0], lane.from[1]],
            [lane.to[0], lane.to[1]],
            sx, sy,
          );
          const passT = Math.min(1, replayT * 1.4);
          const ballOnPass = bezierPoint(
            [lane.from[0], lane.from[1]],
            [lane.to[0], lane.to[1]],
            passT,
          );
          return (
            <g key={`lane${i}`}>
              <path d={pathD} fill="none"
                stroke={lane.success ? '#4ade80' : '#f87171'}
                strokeWidth={(selectedPlayerId ? 3 : 2) / z}
                strokeDasharray={`${8 / z} ${6 / z}`}
                opacity={0.55 + replayT * 0.4}
              />
              {i === 0 && replayT > 0.05 && replayT < 0.7 && (
                <circle cx={sx(ballOnPass[0])} cy={sy(ballOnPass[1])} r={3 / z}
                  fill="rgba(255,255,255,0.7)" />
              )}
            </g>
          );
        })}

        {moves.map((m, i) => (
          <motion.line key={`m${i}`}
            x1={sx(m.from[0])} y1={sy(m.from[1])}
            x2={sx(lerp(m.from[0], m.to[0], replayT))} y2={sy(lerp(m.from[1], m.to[1], replayT))}
            stroke="#fbbf24" strokeWidth={2 / z}
            strokeDasharray={`${6 / z} ${4 / z}`}
            opacity={0.4 + replayT * 0.5}
            markerEnd="url(#arrow)"
          />
        ))}
        <defs>
          <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
            <path d="M0,0 L6,3 L0,6 Z" fill="#fbbf24" />
          </marker>
        </defs>

        <motion.circle cx={ballAnim.x} cy={ballAnim.y} r={sx(10 + replayT * 4)}
          fill="rgba(250,204,21,0.08)" stroke="rgba(250,204,21,0.45)" strokeWidth={1.2 / z}
        />

        {focusEnhanced && selected && (
          <g>
            <line x1={sx(selected.x)} y1={sy(selected.y)} x2={sx(ballReplay.x)} y2={sy(ballReplay.y)}
              stroke="#4ade80" strokeWidth={2 / z} strokeDasharray={`${6 / z} ${4 / z}`}
              opacity={0.5 + replayT * 0.4}
            />
          </g>
        )}

        {livePlayers.map(p => {
          const isSel = p.id === selectedPlayerId;
          const isHov = p.id === hoverId;
          const isHl = highlightedPlayerIds.includes(p.id);
          const pressure = p.pressure ?? 50;
          const coneR = (6 + (pressure / 100) * 12) * (0.4 + replayT * 0.6);

          return (
            <g key={p.id}
              onMouseEnter={() => setHoverId(p.id)}
              onMouseLeave={() => setHoverId(null)}
              onClick={() => onSelectPlayer?.(isSel ? null : p.id)}
              className="cursor-pointer"
            >
              {pressure > 38 && (
                <circle cx={sx(p.x)} cy={sy(p.y)} r={coneR}
                  fill="none" stroke="rgba(255,100,100,0.4)" strokeWidth={1 / z}
                  opacity={0.3 + replayT * 0.5}
                />
              )}
              {isSel && (
                <motion.circle cx={sx(p.x)} cy={sy(p.y)} r={18 / z}
                  fill="none" stroke="#fbbf24" strokeWidth={1.5 / z}
                  animate={{ opacity: [0.35, 0.7, 0.35], r: [16 / z, 20 / z, 16 / z] }}
                  transition={{ repeat: Infinity, duration: 1.8 }}
                />
              )}
              {(p.is_active || isHl) && !isSel && (
                <circle cx={sx(p.x)} cy={sy(p.y)} r={14 / z}
                  fill="none" stroke={isHl ? '#a78bfa' : 'white'}
                  strokeWidth={1.5 / z} strokeDasharray={`${3 / z} ${2 / z}`}
                  opacity={0.5 + replayT * 0.4}
                />
              )}
              <circle cx={sx(p.x)} cy={sy(p.y)} r={(isSel ? 11 : 9) / z}
                fill={p.team === 'home' ? '#3b82f6' : '#ef4444'}
                stroke={isSel ? '#fbbf24' : 'white'}
                strokeWidth={(isSel ? 2.5 : 1) / z}
              />
              <text x={sx(p.x)} y={sy(p.y) - 14 / z} textAnchor="middle"
                fill="white" fontSize={(compact ? 6 : 8) / z} fontWeight="600"
                opacity={isSel || isHov ? 1 : 0.85}
                style={{ textShadow: '0 1px 3px rgba(0,0,0,0.7)' }}>
                {p.name.split(' ').pop()}
              </text>
            </g>
          );
        })}

        <circle cx={ballAnim.x} cy={ballAnim.y} r={5 / z}
          fill="white" stroke="#111" strokeWidth={1 / z}
        />
      </svg>

      <AnimatePresence>
        {focus && showPlayerMetrics && (
          <motion.div
            initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }}
            className="absolute bottom-3 left-3 right-3 glass rounded-xl p-3 text-xs grid grid-cols-2 md:grid-cols-4 gap-2 border border-accent-cyan/30 shadow-lg z-20"
          >
            <Metric label="Player" value={focus.name} />
            <Metric label="Role" value={focus.role ?? '—'} />
            <Metric label="Pressure" value={`${focus.pressure_index ?? focus.pressure ?? 50}`} />
            <Metric label="xThreat" value={focus.xthreat != null ? String(focus.xthreat) : '—'} />
            <Metric label="Speed" value={focus.speed_kmh ? `${focus.speed_kmh} km/h` : '—'} />
            <Metric label="Decision" value={`${focus.decision_score ?? '—'}/100`} />
            <Metric label="Expected" value={focus.expected_action ?? '—'} />
            <Metric label="Pass opts" value={String(focus.pass_options?.length ?? 0)} />
          </motion.div>
        )}
      </AnimatePresence>

      {!compact && (
        <div className="absolute top-3 left-3 flex gap-2 text-xs font-medium z-20">
          <span className="px-2 py-1 rounded bg-blue-600/80 text-white">{frame.home_team}</span>
          <span className="px-2 py-1 rounded bg-red-600/80 text-white">{frame.away_team}</span>
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-text-muted uppercase tracking-wide text-[10px]">{label}</div>
      <div className="font-semibold text-text-primary truncate">{value}</div>
    </div>
  );
}
