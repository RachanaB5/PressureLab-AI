export type GoalEntry = {
  minute: number;
  second?: number;
  team?: string;
  id?: number;
};

export type MatchOverviewState = {
  home_team: string;
  away_team: string;
  competition?: string;
  score: string;
  home_score: number;
  away_score: number;
  minute: number;
  clock: string;
  momentum?: { home: number; away: number };
  possession?: { home: number; away: number };
  pressure_index?: number;
};

export function formatScore(home: number, away: number): string {
  return `${home} – ${away}`;
}

export function parseScore(score: string | undefined): { home: number; away: number } | null {
  if (!score) return null;
  const parts = score.split(/[-–]/).map(s => parseInt(s.trim(), 10));
  if (parts.length !== 2 || parts.some(n => Number.isNaN(n))) return null;
  return { home: parts[0], away: parts[1] };
}

function isGoalEvent(ev: { type?: string; event_type?: string; outcome?: string }): boolean {
  const type = ev.type ?? ev.event_type ?? '';
  if (type === 'Goal') return true;
  if (type === 'Shot') return String(ev.outcome ?? '').toLowerCase().includes('goal');
  return false;
}

/** Merge API goal timeline with goal markers from the key-events strip. */
export function collectGoals(
  goalTimeline: GoalEntry[],
  keyEvents: Array<{ id?: number; minute?: number; second?: number; team?: string; type?: string; event_type?: string; outcome?: string }>,
): GoalEntry[] {
  const seen = new Set<string>();
  const goals: GoalEntry[] = [];

  const add = (g: GoalEntry) => {
    const key = `${g.minute}:${g.second ?? 0}:${g.team ?? ''}:${g.id ?? ''}`;
    if (seen.has(key)) return;
    seen.add(key);
    goals.push(g);
  };

  for (const g of goalTimeline) add(g);
  for (const e of keyEvents) {
    if (!isGoalEvent(e)) continue;
    add({
      minute: e.minute ?? 0,
      second: e.second ?? 0,
      team: e.team,
      id: e.id,
    });
  }

  goals.sort((a, b) => (a.minute - b.minute) || ((a.second ?? 0) - (b.second ?? 0)));
  return goals;
}

/** Score at a given match clock, with optional second precision and replay exclusion. */
export function scoreAtMinute(
  goals: GoalEntry[],
  minute: number,
  homeTeam: string,
  awayTeam: string,
  opts?: { second?: number; excludeGoalId?: number },
): { home: number; away: number } {
  const second = opts?.second ?? 59;
  const excludeGoalId = opts?.excludeGoalId;
  let home = 0;
  let away = 0;

  for (const g of goals) {
    if (excludeGoalId != null && g.id === excludeGoalId) continue;
    const gSecond = g.second ?? 0;
    if (g.minute > minute || (g.minute === minute && gSecond > second)) break;
    if (g.team === homeTeam) home += 1;
    else if (g.team === awayTeam) away += 1;
  }

  return { home, away };
}

function resolveScoreFromState(ms: any): { home: number; away: number } | null {
  const parsed = parseScore(ms?.score);
  const homeNum = ms?.home_score;
  const awayNum = ms?.away_score;
  if (typeof homeNum === 'number' && typeof awayNum === 'number') {
    if (homeNum > 0 || awayNum > 0) return { home: homeNum, away: awayNum };
    if (parsed) return parsed;
    return { home: homeNum, away: awayNum };
  }
  return parsed;
}

export function deriveLiveOverview(params: {
  matchInfo: any;
  momentData: any;
  matchId: number;
  selectedEventId: number | null;
  selectedMinute: number;
  goalTimeline: GoalEntry[];
  keyEvents?: Array<{ id: number; minute?: number; second?: number; team?: string; type?: string; event_type?: string; outcome?: string; pressure?: number; momentum?: number }>;
  replayProgress?: number;
}): MatchOverviewState | null {
  const {
    matchInfo, momentData, matchId, selectedEventId, selectedMinute,
    goalTimeline, keyEvents = [], replayProgress = 0,
  } = params;
  if (!matchId || !matchInfo) return null;

  const homeTeam = matchInfo.home_team ?? 'Home';
  const awayTeam = matchInfo.away_team ?? 'Away';
  const competition = matchInfo.competition ?? '';

  const momentMatches =
    momentData?.match_id === matchId
    && momentData?.event_id === selectedEventId
    && momentData?.match_state;

  const ms = momentMatches ? momentData.match_state : null;
  const minute = ms?.minute ?? (selectedEventId != null ? selectedMinute : 0);
  const selectedEv = selectedEventId != null ? keyEvents.find(e => e.id === selectedEventId) : undefined;

  const allGoals = collectGoals(goalTimeline, keyEvents);
  const isGoalMoment = selectedEv != null && isGoalEvent(selectedEv);
  const goalSecond = selectedEv?.second ?? momentData?.pitch?.second ?? 0;

  // During goal-moment replay, show pre-goal score until the ball is in the net.
  const excludeGoalId = isGoalMoment && replayProgress < 0.88 ? selectedEventId ?? undefined : undefined;
  const scoreSecond = excludeGoalId != null ? Math.max(0, goalSecond - 1) : goalSecond;

  let { home, away } = allGoals.length > 0
    ? scoreAtMinute(allGoals, minute, homeTeam, awayTeam, {
      second: scoreSecond,
      excludeGoalId,
    })
    : { home: 0, away: 0 };

  if (allGoals.length === 0) {
    const fromState = ms ? resolveScoreFromState(ms) : null;
    if (fromState) {
      home = fromState.home;
      away = fromState.away;
    } else if (
      typeof matchInfo.home_score === 'number'
      && typeof matchInfo.away_score === 'number'
      && minute >= (keyEvents.at(-1)?.minute ?? 90)
    ) {
      home = matchInfo.home_score;
      away = matchInfo.away_score;
    }
  }

  const clockSecond = excludeGoalId != null
    ? goalSecond
    : (momentData?.pitch?.second ?? goalSecond);
  const clock = clockSecond > 0 ? `${minute}:${String(clockSecond).padStart(2, '0')}` : `${minute}'`;

  let momentum = ms?.momentum ?? { home: 50, away: 50 };
  if (!ms && selectedEv?.momentum != null) {
    const teamMom = selectedEv.momentum;
    if (selectedEv.team === homeTeam) {
      momentum = { home: teamMom, away: Math.max(0, 100 - teamMom) };
    } else if (selectedEv.team === awayTeam) {
      momentum = { away: teamMom, home: Math.max(0, 100 - teamMom) };
    }
  }

  return {
    home_team: ms?.home_team ?? homeTeam,
    away_team: ms?.away_team ?? awayTeam,
    competition: ms?.competition ?? competition,
    score: formatScore(home, away),
    home_score: home,
    away_score: away,
    minute,
    clock: ms?.clock && !excludeGoalId ? ms.clock : clock,
    momentum,
    possession: ms?.possession,
    pressure_index: ms?.pressure_index ?? selectedEv?.pressure,
  };
}
