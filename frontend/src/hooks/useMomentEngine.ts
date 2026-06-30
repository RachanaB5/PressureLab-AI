import { useCallback, useEffect, useRef } from 'react';
import { matchApi } from '../services/api';
import { useMatchState } from '../context/MatchStateContext';
import {
  computeCamera,
  crowdIntensityFromPressure,
  buildPitchEndState,
  interpolatePitchFrame,
  enrichPitchForReplay,
  TRANSITION_MS,
  WITHIN_MOMENT_MS,
} from '../utils/replayPhysics';

const FRAME_STEP = 0.06;
const SLOW_MO_SPEED = 0.35;

export type ReplayControls = {
  togglePlay: () => void;
  pauseReplay: () => void;
  playReplay: (opts?: { fromStart?: boolean; fromProgress?: number }) => void;
  seekReplay: (progress: number, autoPlay?: boolean) => void;
  stepFrame: (delta: number) => void;
};

export function useMomentEngine(): {
  syncMoment: (eventId: number, minute: number, opts?: { slowMo?: boolean }) => Promise<void>;
  previewMoment: (eventId: number) => void;
  selectPlayer: (playerId: string | null) => void;
  triggerSlowMotion: (ev: { id: number; minute: number }) => void;
  replayControls: ReplayControls;
} {
  const state = useMatchState();
  const {
    matchId, selectedEventId, keyEvents,
    setSelectedEventId, setSelectedMinute, setMomentData,
    setSelectedPlayerId, setLoadingStage, setWhyHighlight,
    setReplayProgress, setReplayPlaying,
    setPitchFrom,
    setCoachComparison, setLoadingMoment,
    momentData, replayPlaying, replayProgress,
    pitchFrom,
    setPitchCamera, setCrowdIntensity, setHighlightedPlayerIds, setNarrationText,
    setCopilotHighlights, bumpCopilotSession,
    replaySpeed, setReplaySpeed,
  } = state;

  const stageTimer = useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  const rafRef = useRef<number | undefined>(undefined);
  const animStartRef = useRef(0);
  const animModeRef = useRef<'transition' | 'within'>('within');
  const isPlayingRef = useRef(false);
  const replayProgressRef = useRef(0);
  const replaySpeedRef = useRef(1);
  const momentDataRef = useRef(momentData);
  const matchIdRef = useRef(matchId);
  const requestSeqRef = useRef(0);

  momentDataRef.current = momentData;
  matchIdRef.current = matchId;
  replayProgressRef.current = replayProgress;
  replaySpeedRef.current = replaySpeed;

  const syncNarration = useCallback((data: any, progress: number) => {
    const bullets = data?.tactical_brief ?? data?.why_brief?.bullets ?? [];
    const steps = data?.why_brief?.sync_steps ?? [];
    if (bullets.length) {
      const idx = Math.min(bullets.length - 1, Math.floor(progress * bullets.length));
      setNarrationText(bullets[idx]?.text ?? '');
      if (steps[idx]?.highlight) setWhyHighlight(steps[idx].highlight);
      return;
    }
    if (steps.length) {
      const idx = Math.min(steps.length - 1, Math.floor(progress * steps.length));
      setNarrationText(steps[idx]?.text ?? '');
      if (steps[idx]?.highlight) setWhyHighlight(steps[idx].highlight);
      return;
    }
    const inv = data?.investigation;
    setNarrationText(inv?.granite_line ?? data?.why_brief?.summary ?? data?.why?.headline ?? '');
  }, [setNarrationText, setWhyHighlight]);

  const stopReplayLoop = useCallback(() => {
    if (rafRef.current != null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = undefined;
    }
    isPlayingRef.current = false;
    setReplayPlaying(false);
  }, [setReplayPlaying]);

  const startReplayLoop = useCallback((
    mode: 'transition' | 'within',
    speed: number,
    fromProgress: number,
    data?: any,
  ) => {
    if (rafRef.current != null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = undefined;
    }

    const narrateData = data ?? momentDataRef.current;
    if (!narrateData?.pitch) {
      isPlayingRef.current = false;
      setReplayPlaying(false);
      return;
    }

    const duration = Math.max(1, (mode === 'transition' ? TRANSITION_MS : WITHIN_MOMENT_MS) / speed);
    let startAt = Math.max(0, Math.min(1, fromProgress));
    if (startAt >= 1) startAt = 0;

    animModeRef.current = mode;
    animStartRef.current = performance.now() - startAt * duration;
    isPlayingRef.current = true;
    setReplayPlaying(true);
    replayProgressRef.current = startAt;
    setReplayProgress(startAt);

    const tick = (now: number) => {
      if (!isPlayingRef.current) return;
      const elapsed = now - animStartRef.current;
      const progress = Math.min(1, elapsed / duration);
      replayProgressRef.current = progress;
      setReplayProgress(progress);
      syncNarration(narrateData, progress);
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        isPlayingRef.current = false;
        setReplayPlaying(false);
        rafRef.current = undefined;
      }
    };
    rafRef.current = requestAnimationFrame(tick);
  }, [setReplayPlaying, setReplayProgress, syncNarration]);

  const pauseReplay = useCallback(() => {
    stopReplayLoop();
  }, [stopReplayLoop]);

  const playReplay = useCallback((opts?: { fromStart?: boolean; fromProgress?: number }) => {
    const speed = replaySpeedRef.current;
    const mode = animModeRef.current;
    let from = opts?.fromProgress ?? replayProgressRef.current;
    if (opts?.fromStart || from >= 1) from = 0;
    startReplayLoop(mode, speed, from);
  }, [startReplayLoop]);

  const seekReplay = useCallback((progress: number, autoPlay = false) => {
    stopReplayLoop();
    const p = Math.max(0, Math.min(1, progress));
    replayProgressRef.current = p;
    setReplayProgress(p);
    const md = momentDataRef.current;
    if (md) syncNarration(md, p);
    if (autoPlay && p < 1) {
      startReplayLoop(animModeRef.current, replaySpeedRef.current, p);
    }
  }, [stopReplayLoop, setReplayProgress, syncNarration, startReplayLoop]);

  const togglePlay = useCallback(() => {
    if (isPlayingRef.current) {
      pauseReplay();
    } else {
      playReplay();
    }
  }, [pauseReplay, playReplay]);

  const stepFrame = useCallback((delta: number) => {
    pauseReplay();
    const next = Math.max(0, Math.min(1, replayProgressRef.current + delta));
    seekReplay(next, false);
  }, [pauseReplay, seekReplay]);

  const syncMoment = useCallback(async (
    eventId: number,
    minute: number,
    opts?: { slowMo?: boolean },
  ) => {
    if (!matchIdRef.current) return;

    const seq = ++requestSeqRef.current;
    const activeMatchId = matchIdRef.current;

    stopReplayLoop();

    const prevEnd = momentDataRef.current?.pitch
      && momentDataRef.current.match_id === activeMatchId
      && momentDataRef.current.event_id === selectedEventId
      ? buildPitchEndState(momentDataRef.current.pitch)
      : null;
    setPitchFrom(prevEnd);

    setLoadingMoment(true);
    setCoachComparison(null);
    setSelectedPlayerId(null);
    setHighlightedPlayerIds([]);
    setCopilotHighlights([]);
    setNarrationText('');
    setMomentData(null);
    setSelectedEventId(eventId);
    setSelectedMinute(minute);
    replayProgressRef.current = 0;
    setReplayProgress(0);
    bumpCopilotSession();

    const speed = opts?.slowMo ? SLOW_MO_SPEED : 1;
    setReplaySpeed(speed);
    replaySpeedRef.current = speed;
    setLoadingStage(0);

    clearInterval(stageTimer.current);
    stageTimer.current = setInterval(() => {
      setLoadingStage(s => Math.min(s + 1, 5));
    }, 400);

    const ev = keyEvents.find(e => e.id === eventId);
    setCrowdIntensity(crowdIntensityFromPressure(ev?.pressure, ev?.type));

    try {
      const data = await matchApi.getMoment(activeMatchId, eventId);
      if (seq !== requestSeqRef.current || matchIdRef.current !== activeMatchId) return;

      const enrichedPitch = enrichPitchForReplay(data.pitch);
      const payload = { ...data, pitch: enrichedPitch, match_id: activeMatchId };
      setWhyHighlight(data.why_brief?.highlight ?? data.investigation?.highlights?.why ?? 'half-space');
      syncNarration(payload, 0);

      const activeId = enrichedPitch.players?.find((p: any) => p.is_active)?.id;
      if (activeId) setHighlightedPlayerIds([activeId]);

      setMomentData(payload);

      requestAnimationFrame(() => {
        if (seq !== requestSeqRef.current) return;
        startReplayLoop(prevEnd ? 'transition' : 'within', speed, 0, payload);
      });
    } catch {
      setMomentData(null);
    } finally {
      if (seq === requestSeqRef.current) {
        clearInterval(stageTimer.current);
        setLoadingMoment(false);
        setLoadingStage(5);
      }
    }
  }, [keyEvents, setPitchFrom, setSelectedEventId, setSelectedMinute, setMomentData,
    setSelectedPlayerId, setLoadingStage, setWhyHighlight,
    setCoachComparison, setCopilotHighlights, bumpCopilotSession,
    setLoadingMoment, setCrowdIntensity, setHighlightedPlayerIds,
    syncNarration, setReplaySpeed, selectedEventId, setNarrationText,
    stopReplayLoop, startReplayLoop, setReplayProgress]);

  const triggerSlowMotion = useCallback((ev: { id: number; minute: number }) => {
    syncMoment(ev.id, ev.minute, { slowMo: true });
  }, [syncMoment]);

  const previewMoment = useCallback((eventId: number) => {
    if (!matchIdRef.current || !momentDataRef.current?.pitch) return;
    if (momentDataRef.current.event_id !== selectedEventId) return;
    stopReplayLoop();
    seekReplay(0.35, false);
    const ev = keyEvents.find(e => e.id === eventId);
    if (ev) setCrowdIntensity(crowdIntensityFromPressure(ev.pressure, ev.type) * 0.6);
  }, [keyEvents, selectedEventId, stopReplayLoop, seekReplay, setCrowdIntensity]);

  const selectPlayer = useCallback((playerId: string | null) => {
    setSelectedPlayerId(playerId);
    const md = momentDataRef.current;
    if (playerId && md?.pitch && md.event_id === selectedEventId) {
      setHighlightedPlayerIds([playerId]);
      const frame = interpolatePitchFrame(pitchFrom, md.pitch, replayProgressRef.current);
      const player = frame.players.find((p: any) => p.id === playerId);
      if (player) {
        setPitchCamera(computeCamera({ x: player.x, y: player.y }, frame.players, 2.2));
      }
    }
  }, [setSelectedPlayerId, setHighlightedPlayerIds, setPitchCamera, pitchFrom, selectedEventId]);

  useEffect(() => {
    const md = momentData;
    if (!md?.pitch || md.match_id !== matchId || md.event_id !== selectedEventId) return;
    const frame = interpolatePitchFrame(pitchFrom, md.pitch, replayProgress);
    setPitchCamera(computeCamera(frame.ball, frame.players, 1.7));
  }, [momentData, matchId, selectedEventId, pitchFrom, replayProgress, setPitchCamera]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.code === 'Space') {
        e.preventDefault();
        togglePlay();
        return;
      }
      if (!keyEvents.length) return;
      const idx = selectedEventId != null ? keyEvents.findIndex(ev => ev.id === selectedEventId) : -1;
      if (e.key === 'ArrowRight') {
        e.preventDefault();
        if (e.shiftKey && idx < keyEvents.length - 1) {
          syncMoment(keyEvents[idx + 1].id, keyEvents[idx + 1].minute);
        } else {
          stepFrame(FRAME_STEP);
        }
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        if (e.shiftKey && idx > 0) {
          syncMoment(keyEvents[idx - 1].id, keyEvents[idx - 1].minute);
        } else {
          stepFrame(-FRAME_STEP);
        }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [keyEvents, selectedEventId, syncMoment, togglePlay, stepFrame]);

  useEffect(() => () => {
    stopReplayLoop();
    clearInterval(stageTimer.current);
  }, [stopReplayLoop]);

  const replayControls: ReplayControls = {
    togglePlay,
    pauseReplay,
    playReplay,
    seekReplay,
    stepFrame,
  };

  return { syncMoment, previewMoment, selectPlayer, triggerSlowMotion, replayControls };
}
