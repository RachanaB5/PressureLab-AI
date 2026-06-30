export default function SettingsPage() {
  return (
    <div className="p-8 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Settings</h1>
      <div className="glass rounded-xl p-6 space-y-4 text-sm text-text-secondary">
        <p><strong className="text-text-primary">IBM Stack</strong> — Granite, LangFlow, Docling, Context Forge, IBM Bob</p>
        <p><strong className="text-text-primary">Data source</strong> — StatsBomb Open Data + custom JSON uploads</p>
        <p><strong className="text-text-primary">Performance</strong> — Demo cache, moment cache, async Granite enrichment</p>
      </div>
    </div>
  );
}
