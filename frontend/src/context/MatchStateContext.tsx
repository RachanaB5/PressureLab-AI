import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';

export type AppView = 'home' | 'library' | 'workspace' | 'settings';

interface MatchState {
  matchId: number;
  setMatchId: (id: number) => void;
  matchInfo: any;
  setMatchInfo: (info: any) => void;
  keyEvents: any[];
  setKeyEvents: (events: any[]) => void;
  goalTimeline: Array<{ minute: number; team?: string }>;
  setGoalTimeline: (goals: Array<{ minute: number; team?: string }>) => void;
  selectedEventId: number | null;
  setSelectedEventId: (id: number | null) => void;
  selectedMinute: number;
  setSelectedMinute: (m: number) => void;
  momentData: any;
  setMomentData: (d: any | ((prev: any) => any)) => void;
  selectedPlayerId: string | null;
  setSelectedPlayerId: (id: string | null) => void;
  loadingStage: number;
  setLoadingStage: (n: number | ((prev: number) => number)) => void;
  whyHighlight: string | null;
  setWhyHighlight: (h: string | null) => void;
  replayProgress: number;
  setReplayProgress: (n: number | ((prev: number) => number)) => void;
  replayPlaying: boolean;
  setReplayPlaying: (b: boolean) => void;
  replaySpeed: number;
  setReplaySpeed: (n: number) => void;
  pitchFrom: any;
  setPitchFrom: (p: any) => void;
  coachComparison: any | null;
  setCoachComparison: (r: any | null) => void;
  copilotHighlights: string[];
  setCopilotHighlights: (h: string[]) => void;
  copilotSessionKey: number;
  bumpCopilotSession: () => void;
  loadingMoment: boolean;
  setLoadingMoment: (b: boolean) => void;
  pitchCamera: { cx: number; cy: number; zoom: number };
  setPitchCamera: (c: { cx: number; cy: number; zoom: number }) => void;
  crowdIntensity: number;
  setCrowdIntensity: (n: number) => void;
  highlightedPlayerIds: string[];
  setHighlightedPlayerIds: (ids: string[]) => void;
  narrationText: string;
  setNarrationText: (t: string) => void;
  appView: AppView;
  setAppView: (v: AppView) => void;
  resetWorkspaceState: () => void;
}

const MatchStateContext = createContext<MatchState | undefined>(undefined);

export function MatchStateProvider({ children }: { children: ReactNode }) {
  const [matchId, setMatchId] = useState(0);
  const [matchInfo, setMatchInfo] = useState<any>(null);
  const [keyEvents, setKeyEvents] = useState<any[]>([]);
  const [goalTimeline, setGoalTimeline] = useState<Array<{ minute: number; team?: string }>>([]);
  const [selectedEventId, setSelectedEventId] = useState<number | null>(null);
  const [selectedMinute, setSelectedMinute] = useState(0);
  const [momentData, setMomentData] = useState<any>(null);
  const [selectedPlayerId, setSelectedPlayerId] = useState<string | null>(null);
  const [loadingStage, setLoadingStage] = useState(0);
  const [whyHighlight, setWhyHighlight] = useState<string | null>(null);
  const [replayProgress, setReplayProgress] = useState(0);
  const [replayPlaying, setReplayPlaying] = useState(false);
  const [replaySpeed, setReplaySpeed] = useState(1);
  const [pitchFrom, setPitchFrom] = useState<any>(null);
  const [coachComparison, setCoachComparison] = useState<any | null>(null);
  const [copilotHighlights, setCopilotHighlights] = useState<string[]>([]);
  const [copilotSessionKey, setCopilotSessionKey] = useState(0);
  const [loadingMoment, setLoadingMoment] = useState(false);
  const [pitchCamera, setPitchCamera] = useState({ cx: 60, cy: 40, zoom: 1 });
  const [crowdIntensity, setCrowdIntensity] = useState(0.4);
  const [highlightedPlayerIds, setHighlightedPlayerIds] = useState<string[]>([]);
  const [narrationText, setNarrationText] = useState('');
  const [appView, setAppView] = useState<AppView>('home');

  const bumpCopilotSession = useCallback(() => {
    setCopilotSessionKey(k => k + 1);
  }, []);

  const resetWorkspaceState = useCallback(() => {
    setKeyEvents([]);
    setGoalTimeline([]);
    setSelectedEventId(null);
    setSelectedMinute(0);
    setMomentData(null);
    setSelectedPlayerId(null);
    setLoadingStage(0);
    setWhyHighlight(null);
    setReplayProgress(0);
    setReplayPlaying(false);
    setReplaySpeed(1);
    setPitchFrom(null);
    setCoachComparison(null);
    setCopilotHighlights([]);
    setLoadingMoment(false);
    setPitchCamera({ cx: 60, cy: 40, zoom: 1 });
    setCrowdIntensity(0.4);
    setHighlightedPlayerIds([]);
    setNarrationText('');
    bumpCopilotSession();
  }, [bumpCopilotSession]);

  return (
    <MatchStateContext.Provider
      value={{
        matchId, setMatchId, matchInfo, setMatchInfo,
        keyEvents, setKeyEvents,
        goalTimeline, setGoalTimeline,
        selectedEventId, setSelectedEventId,
        selectedMinute, setSelectedMinute,
        momentData, setMomentData,
        selectedPlayerId, setSelectedPlayerId,
        loadingStage, setLoadingStage,
        whyHighlight, setWhyHighlight,
        replayProgress, setReplayProgress,
        replayPlaying, setReplayPlaying,
        replaySpeed, setReplaySpeed,
        pitchFrom, setPitchFrom,
        coachComparison, setCoachComparison,
        copilotHighlights, setCopilotHighlights,
        copilotSessionKey, bumpCopilotSession,
        loadingMoment, setLoadingMoment,
        pitchCamera, setPitchCamera,
        crowdIntensity, setCrowdIntensity,
        highlightedPlayerIds, setHighlightedPlayerIds,
        narrationText, setNarrationText,
        appView, setAppView,
        resetWorkspaceState,
      }}
    >
      {children}
    </MatchStateContext.Provider>
  );
}

export function useMatchState() {
  const ctx = useContext(MatchStateContext);
  if (!ctx) throw new Error('useMatchState must be used within MatchStateProvider');
  return ctx;
}
