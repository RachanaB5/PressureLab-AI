export type InvestigationKey =
  | 'why'
  | 'best_passing_option'
  | 'missed_opportunity'
  | 'defensive_mistake'
  | 'tactical_pattern';

export type VisualInvestigation = {
  why?: string;
  best_passing_option?: string;
  missed_opportunity?: string;
  defensive_mistake?: string;
  tactical_pattern?: string;
  confidence?: number;
  highlights?: Partial<Record<InvestigationKey, string>>;
  granite_line?: string;
};

export const INVESTIGATION_LABELS: Record<InvestigationKey, string> = {
  why: 'Why it happened',
  best_passing_option: 'Best pass',
  missed_opportunity: 'Missed chance',
  defensive_mistake: 'Defensive gap',
  tactical_pattern: 'Pattern',
};

export function resolveInvestigation(momentData: any): VisualInvestigation {
  const inv = momentData?.investigation ?? momentData?.detective;
  const why = momentData?.why;
  const brief = momentData?.why_brief ?? why?.brief;
  const bullets = momentData?.tactical_brief ?? brief?.bullets ?? [];
  const bulletText = (key: string, fallback: string) =>
    bullets.find((b: { key?: string }) => b.key === key)?.text ?? fallback;
  if (inv?.why && inv?.tactical_pattern) return inv;
  return {
    why: bulletText('why', brief?.summary ?? why?.headline ?? `Moment at ${momentData?.minute ?? '?'}.`),
    best_passing_option: bulletText('pass', why?.attacker_choice ?? 'See passing lanes on pitch.'),
    missed_opportunity: why?.alternatives?.[0] ?? 'Earlier switch before this action.',
    defensive_mistake: bulletText('mistake', why?.defender_reaction ?? 'Defensive line timing.'),
    tactical_pattern: bulletText('takeaway', why?.tactical_pattern ?? ''),
    highlights: {
      why: 'attacker movement',
      best_passing_option: 'passing lane',
      missed_opportunity: 'half-space',
      defensive_mistake: 'defensive mistake',
      tactical_pattern: 'pressing trigger',
    },
    granite_line: brief?.summary ?? why?.headline,
  };
}
