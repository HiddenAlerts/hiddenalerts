export default function Home() {
  return (
    <div className="min-h-screen bg-black text-white p-10">
      <h1 className="text-4xl font-bold mb-4">HiddenAlerts</h1>
      <p className="text-lg mb-8">
        Real-time fraud intelligence from trusted sources — filtered, scored,
        and prioritized so you don’t miss what matters.
      </p>

      <div className="bg-zinc-900 p-6 rounded-lg mb-6">
        <h2 className="text-2xl font-semibold mb-2">🚨 High-Risk Alert</h2>
        <p>
          Chicago convenience store owner sentenced in $19M WIC fraud scheme.
        </p>
        <p className="text-sm text-zinc-400 mt-2">
          Why it matters: Organized fraud ring exploiting federal assistance
          programs.
        </p>
      </div>

      <div className="bg-zinc-900 p-6 rounded-lg mb-6">
        <h2 className="text-2xl font-semibold mb-2">⚠️ Emerging Pattern</h2>
        <p>
          Multiple agencies reporting increase in crypto-related laundering
          cases.
        </p>
        <p className="text-sm text-zinc-400 mt-2">
          Pattern detected across DOJ, SEC, and FBI sources.
        </p>
      </div>

      <button className="mt-6 px-6 py-3 bg-red-600 rounded-lg font-semibold hover:bg-red-700">
        Subscribe for Full Intelligence Access
      </button>
    </div>
  );
}
