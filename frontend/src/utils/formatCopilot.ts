export type CopilotStructured = {
  answer?: string;
  response?: string;
  reasoning?: string;
  explanation?: string;
  summary?: string;
  bullets?: Array<{ label?: string; text?: string; key?: string }>;
  why_now?: string;
  evidence?: string[] | string;
  what_if?: string;
  what_next?: string;
  alternatives?: string[] | Array<{ action?: string; success_probability?: number }>;
  confidence?: number;
};

function bulletsFromRes(res: CopilotStructured): string[] {
  if (res.bullets?.length) {
    return res.bullets.map(b => `• ${b.label ? `${b.label}: ` : ''}${b.text}`).filter(Boolean);
  }
  const main = res.answer || res.response || res.explanation || res.summary || res.reasoning || '';
  if (!main) return [];
  return main
    .split('\n')
    .map(l => l.trim())
    .filter(Boolean)
    .map(l => (l.startsWith('•') || l.startsWith('- ') ? l : `• ${l.replace(/^[-*]\s*/, '')}`))
    .slice(0, 6);
}

/** Event-grounded answer — bullets only, never raw JSON or generic prose. */
export function formatCopilotAnswer(res: CopilotStructured): string {
  const bullets = bulletsFromRes(res);
  if (bullets.length) return bullets.join('\n');

  const evidence = Array.isArray(res.evidence) ? res.evidence : res.evidence ? [String(res.evidence)] : [];
  if (evidence.length) {
    return evidence.slice(0, 4).map(e => `• ${e}`).join('\n');
  }

  return '';
}

export function groundedLocalAnswer(momentData: any, question: string): string {
  const brief = momentData?.tactical_brief ?? momentData?.why_brief?.bullets ?? [];
  if (brief.length) {
    return brief.map((b: { label?: string; text?: string }) =>
      `• ${b.label ? `${b.label}: ` : ''}${b.text}`,
    ).join('\n');
  }
  const ev = momentData?.event;
  const ms = momentData?.match_state;
  const minute = momentData?.minute ?? ms?.minute ?? '?';
  const player = ev?.player ?? 'Player';
  const et = ev?.type ?? 'event';
  const score = ms?.score ?? '?';
  const ball = momentData?.pitch?.ball;
  const pos = ball ? ` at ball (${Math.round(ball.x)}, ${Math.round(ball.y)})` : '';
  return `• At ${minute}' (${score}), ${player}'s ${et}${pos} — ${question}`;
}
