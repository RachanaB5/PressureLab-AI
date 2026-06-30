import { AppShell } from './components/layout/AppShell';
import { MatchStateProvider, useMatchState } from './context/MatchStateContext';
import HomePage from './pages/HomePage';
import MatchLibrary from './pages/MatchLibrary';
import WorkspacePage from './pages/WorkspacePage';
import SettingsPage from './pages/SettingsPage';

function AppRouter() {
  const { appView } = useMatchState();

  return (
    <AppShell>
      {appView === 'home' && <HomePage />}
      {appView === 'library' && <MatchLibrary />}
      {appView === 'workspace' && <WorkspacePage />}
      {appView === 'settings' && <SettingsPage />}
    </AppShell>
  );
}

export default function App() {
  return (
    <MatchStateProvider>
      <AppRouter />
    </MatchStateProvider>
  );
}
