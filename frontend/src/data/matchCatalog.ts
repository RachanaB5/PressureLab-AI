/** Mirrors backend CATALOG_MATCHES — only verified StatsBomb open-data IDs */
export const MATCH_CATALOG = [
  { statsbomb_id: 8658, home_team: 'France', away_team: 'Croatia', competition: '2018 FIFA World Cup Final', season: '2018', match_date: '2018-07-15' },
  { statsbomb_id: 7581, home_team: 'France', away_team: 'Belgium', competition: '2018 FIFA World Cup Semi-Final', season: '2018', match_date: '2018-07-10' },
  { statsbomb_id: 8656, home_team: 'Croatia', away_team: 'England', competition: '2018 FIFA World Cup Semi-Final', season: '2018', match_date: '2018-07-11' },
  { statsbomb_id: 7580, home_team: 'Belgium', away_team: 'Japan', competition: '2018 FIFA World Cup', season: '2018', match_date: '2018-07-02' },
  { statsbomb_id: 22912, home_team: 'Argentina', away_team: 'France', competition: '2022 FIFA World Cup Final', season: '2022', match_date: '2022-12-18' },
  { statsbomb_id: 3942819, home_team: 'Spain', away_team: 'England', competition: 'Euro 2024 Final', season: '2024', match_date: '2024-07-14' },
  { statsbomb_id: 18245, home_team: 'Liverpool', away_team: 'Real Madrid', competition: 'UEFA Champions League Final', season: '2017/18', match_date: '2018-05-26' },
  { statsbomb_id: 3773585, home_team: 'Barcelona', away_team: 'Real Madrid', competition: 'La Liga', season: '2020/21', match_date: '2020-10-24' },
  { statsbomb_id: 3754174, home_team: 'Borussia Dortmund', away_team: 'Real Madrid', competition: 'UEFA Champions League Final', season: '2023/24', match_date: '2024-06-01' },
];

export type MatchSuggestion = {
  id?: number | null;
  statsbomb_id?: number;
  label: string;
  home_team: string;
  away_team: string;
  competition: string;
  match_date: string;
  loaded?: boolean;
};

export function suggestLocalMatches(query: string, limit = 8): MatchSuggestion[] {
  const q = query.trim().toLowerCase();
  if (q.length < 2) return [];

  const scored: Array<{ rank: number; item: MatchSuggestion }> = [];

  for (const m of MATCH_CATALOG) {
    const label = `${m.home_team} vs ${m.away_team}`;
    const hay = `${label} ${m.competition} ${m.season}`.toLowerCase();
    if (!hay.includes(q) && !q.split(/\s+/).some(w => w.length > 2 && hay.includes(w))) continue;

    let rank = 20;
    if (label.toLowerCase().startsWith(q)) rank = 100;
    else if (m.home_team.toLowerCase().startsWith(q) || m.away_team.toLowerCase().startsWith(q)) rank = 80;
    else if (label.toLowerCase().includes(q)) rank = 50;

    scored.push({
      rank,
      item: {
        statsbomb_id: m.statsbomb_id,
        label,
        home_team: m.home_team,
        away_team: m.away_team,
        competition: m.competition,
        match_date: m.match_date,
        loaded: false,
      },
    });
  }

  return scored
    .sort((a, b) => b.rank - a.rank)
    .slice(0, limit)
    .map(s => s.item);
}
