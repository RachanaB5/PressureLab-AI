import { useEffect, useMemo, type ReactNode } from 'react';
import { matchApi } from '../services/api';
import { useMatchState } from '../context/MatchStateContext';
import { useMomentEngine } from '../hooks/useMomentEngine';
import { deriveLiveOverview } from '../utils/matchOverview';
import { LoadingStages } from '../components/workspace/LoadingStages';
import { ReplayTransport } from '../components/workspace/ReplayTransport';
import { InteractiveTimeline } from '../components/workspace/InteractiveTimeline';
import { MatchHeader } from '../components/workspace/MatchHeader';
import { WorkflowStrip } from '../components/workspace/WorkflowStrip';
import { DigitalMatchTwin } from '../components/workspace/DigitalMatchTwin';
import { TacticalDetective } from '../components/workspace/TacticalDetective';
import { AICopilot } from '../components/copilot/AICopilot';
import { Play } from 'lucide-react';

export default function WorkspacePage() {
  const {
    matchId, matchInfo, selectedEventId, momentData, selectedPlayerId,
    loadingStage, whyHighlight, replayProgress, replayPlaying,
    copilotHighlights, pitchCamera, crowdIntensity, highlightedPlayerIds,
    loadingMoment, narrationText, selectedMinute, replaySpeed, pitchFrom,
    coachComparison, keyEvents, setKeyEvents, goalTimeline, setGoalTimeline, copilotSessionKey,
    setReplaySpeed,
  } = useMatchState();

  const { syncMoment, previewMoment, selectPlayer, triggerSlowMotion, replayControls } = useMomentEngine();

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    matchApi.getKeyEvents(matchId)
      .then(r => {
        if (!cancelled) {
          setKeyEvents(r.events);
          setGoalTimeline(r.goals ?? []);
        }
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [matchId, setKeyEvents, setGoalTimeline]);

  useEffect(() => {
    if (keyEvents.length && !selectedEventId && matchId) {
      const pick = [...keyEvents].reverse().find(e => e.type === 'Goal') || keyEvents[Math.floor(keyEvents.length / 2)];
      if (pick) syncMoment(pick.id, pick.minute);
    }
  }, [keyEvents, selectedEventId, syncMoment, matchId]);

  const liveOverview = useMemo(
    () => deriveLiveOverview({
      matchInfo,
      momentData,
      matchId,
      selectedEventId,
      selectedMinute,
      goalTimeline,
      keyEvents,
      replayProgress,
    }),
    [matchInfo, momentData, matchId, selectedEventId, selectedMinute, goalTimeline, keyEvents, replayProgress],
  );

  const pitchFrame = useMemo(() => {
    if (!momentData?.pitch) return null;
    if (momentData.match_id !== matchId) return null;
    if (selectedEventId != null && momentData.event_id !== selectedEventId) return null;
    return momentData.pitch;
  }, [momentData, matchId, selectedEventId]);

  const showDetective = !loadingMoment
    && momentData?.match_id === matchId
    && momentData?.event_id === selectedEventId;

  const highlights = [...copilotHighlights, whyHighlight].filter(Boolean) as string[];
  const workflowStep = coachComparison ? 4 : selectedEventId && momentData ? 3 : selectedEventId ? 2 : 1;

  return (
    <div className="max-w-6xl mx-auto p-6 pb-24 space-y-8">
      <WorkflowStrip active={workflowStep} />
      <MatchHeader overview={liveOverview} loading={loadingMoment} />

      <section>
        <SectionTitle icon={<Play size={18} />} title="Tactical Replay Timeline" />
        <InteractiveTimeline
          events={keyEvents}
          selectedId={selectedEventId}
          onSelect={ev => syncMoment(ev.id, ev.minute)}
          onHover={ev => ev && previewMoment(ev.id)}
          onSlowMotion={ev => triggerSlowMotion(ev)}
        />
        <div className="mt-3">
          <ReplayTransport
            replayProgress={replayProgress}
            replayPlaying={replayPlaying}
            slowMotion={replaySpeed < 0.5}
            controls={replayControls}
            onResetSlowMo={() => setReplaySpeed(1)}
          />
        </div>
      </section>

      <section className="relative">
        <DigitalMatchTwin
          pitchFrame={pitchFrame}
          pitchFrom={pitchFrom}
          selectedPlayerId={selectedPlayerId}
          onSelectPlayer={selectPlayer}
          animateKey={selectedEventId ?? 0}
          replayProgress={replayProgress}
          camera={pitchCamera}
          crowdIntensity={crowdIntensity}
          highlightedPlayerIds={highlightedPlayerIds}
          highlights={highlights}
          whyHighlight={whyHighlight}
          narrationText={narrationText}
          replayPlaying={replayPlaying}
          loading={loadingMoment}
        />
        {loadingMoment && (
          <div className="absolute inset-0 z-30 flex items-center justify-center bg-bg-primary/70 backdrop-blur-sm rounded-xl">
            <LoadingStages stage={loadingStage} />
          </div>
        )}
      </section>

      <section>
        {showDetective ? (
          <TacticalDetective onSeekReplay={replayControls.seekReplay} />
        ) : loadingMoment ? <LoadingStages stage={loadingStage} /> : null}
      </section>

      <div className="xl:hidden fixed bottom-0 left-56 right-0 h-56 border-t border-border-glass glass z-30">
        <AICopilot key={`mobile-${matchId}-${selectedEventId ?? 0}-${copilotSessionKey}`} />
      </div>
    </div>
  );
}

function SectionTitle({ title, icon }: { title: string; icon?: ReactNode }) {
  return (
    <div className="flex items-center gap-2 mb-4">
      <h2 className="text-lg font-bold flex items-center gap-2">{icon}{title}</h2>
    </div>
  );
}
