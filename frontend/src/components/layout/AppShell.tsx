import { Home, Library, Settings, ChevronLeft } from 'lucide-react';
import { useMatchState, type AppView } from '../../context/MatchStateContext';
import { AICopilot } from '../copilot/AICopilot';

const NAV: { id: AppView; label: string; icon: typeof Home }[] = [
  { id: 'home', label: 'Home', icon: Home },
  { id: 'library', label: 'Match Library', icon: Library },
  { id: 'settings', label: 'Settings', icon: Settings },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { appView, setAppView, matchId, selectedEventId, copilotSessionKey } = useMatchState();
  const showCopilot = appView === 'workspace' && matchId > 0;
  const copilotKey = `${matchId}-${selectedEventId ?? 0}-${copilotSessionKey}`;

  return (
    <div className="flex h-screen bg-bg-primary overflow-hidden">
      <aside className="w-56 flex-shrink-0 border-r border-border-glass glass flex flex-col">
        <div className="p-5 border-b border-border-glass">
          <h1 className="text-lg font-bold gradient-text">PressureLab AI</h1>
          <p className="text-[10px] text-text-muted mt-1 uppercase tracking-widest">Digital Match Twin</p>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {NAV.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setAppView(id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                appView === id
                  ? 'bg-accent-blue/20 text-accent-cyan border border-accent-blue/30'
                  : 'text-text-secondary hover:bg-bg-glass-hover'
              }`}
            >
              <Icon size={18} />
              {label}
            </button>
          ))}
          {appView === 'workspace' && (
            <button
              onClick={() => setAppView('home')}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-text-muted hover:text-text-primary mt-4"
            >
              <ChevronLeft size={18} />
              Exit workspace
            </button>
          )}
        </nav>
      </aside>

      <main className="flex-1 overflow-y-auto min-w-0">{children}</main>

      {showCopilot && (
        <aside className="w-80 flex-shrink-0 border-l border-border-glass glass hidden xl:block">
          <AICopilot key={copilotKey} />
        </aside>
      )}
    </div>
  );
}
