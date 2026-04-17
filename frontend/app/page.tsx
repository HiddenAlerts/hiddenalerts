export default function Home() {
  return (
    <div className="min-h-screen bg-black text-white">

      {/* NAV */}
      <nav className="flex justify-between items-center px-8 py-4 border-b border-zinc-800">
        <h1 className="text-xl font-bold">HiddenAlerts</h1>
        <button className="bg-red-600 px-4 py-2 rounded-md text-sm font-semibold hover:bg-red-700">
          Get Access
        </button>
      </nav>

      {/* HERO */}
      <section className="px-8 py-20 max-w-5xl mx-auto">
        <h1 className="text-5xl font-bold mb-6 leading-tight">
          Real-Time Fraud Intelligence — Not Just News
        </h1>
        <p className="text-lg text-zinc-400 mb-8 max-w-2xl">
          AI-filtered, risk-scored alerts from FBI, SEC, DOJ and more — so you
          can identify threats before they escalate.
        </p>
        <button className="bg-red-600 px-6 py-3 rounded-lg font-semibold hover:bg-red-700">
          Get Early Access
        </button>
      </section>

      {/* ALERT PREVIEW */}
      <section className="px-8 py-12 max-w-5xl mx-auto">
        <h2 className="text-2xl font-semibold mb-6">Live Intelligence Feed</h2>

        <div className="space-y-6">

          <div className="bg-zinc-900 p-6 rounded-lg border border-zinc-800">
            <div className="flex justify-between mb-2">
              <span className="text-sm text-zinc-400">DOJ</span>
              <span className="text-red-500 text-sm font-semibold">HIGH RISK</span>
            </div>
            <h3 className="text-lg font-semibold mb-2">
              $19M WIC Fraud Scheme — Multi-State Operation
            </h3>
            <p className="text-zinc-400 text-sm">
              Why it matters: Organized fraud network exploiting federal assistance programs.
            </p>
          </div>

          <div className="bg-zinc-900 p-6 rounded-lg border border-zinc-800">
            <div className="flex justify-between mb-2">
              <span className="text-sm text-zinc-400">SEC</span>
              <span className="text-yellow-500 text-sm font-semibold">MEDIUM RISK</span>
            </div>
            <h3 className="text-lg font-semibold mb-2">
              Investment Scam Targeting Retirees
            </h3>
            <p className="text-zinc-400 text-sm">
              Why it matters: Increasing pattern of targeted financial exploitation.
            </p>
          </div>

        </div>
      </section>

      {/* DIFFERENTIATION */}
      <section className="px-8 py-16 bg-zinc-950">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-3xl font-bold mb-6">Not News. Intelligence.</h2>

          <div className="grid md:grid-cols-3 gap-8 text-zinc-400">

            <div>
              <h3 className="text-white font-semibold mb-2">Filtered Signals</h3>
              <p>No noise. Only high-relevance fraud events.</p>
            </div>

            <div>
              <h3 className="text-white font-semibold mb-2">Risk Scoring</h3>
              <p>Every alert prioritized by severity and impact.</p>
            </div>

            <div>
              <h3 className="text-white font-semibold mb-2">Pattern Detection</h3>
              <p>Identify trends across agencies before they surface publicly.</p>
            </div>

          </div>
        </div>
      </section>

      {/* PATTERN EXAMPLE */}
      <section className="px-8 py-16 max-w-5xl mx-auto">
        <h2 className="text-2xl font-semibold mb-6">Emerging Threat Patterns</h2>

        <div className="bg-zinc-900 p-6 rounded-lg border border-zinc-800">
          <p className="text-zinc-300">
            3 federal agencies reported similar crypto laundering activity within the past 72 hours.
          </p>
          <p className="text-sm text-zinc-500 mt-2">
            Cross-source intelligence signal detected
          </p>
        </div>
      </section>

      {/* CTA */}
      <section className="px-8 py-20 text-center">
        <h2 className="text-3xl font-bold mb-4">
          Stay Ahead of Financial Threats
        </h2>
        <p className="text-zinc-400 mb-6">
          Join early users getting access to real-time fraud intelligence.
        </p>

        <button className="bg-red-600 px-8 py-3 rounded-lg font-semibold hover:bg-red-700">
          Subscribe for Full Access
        </button>
      </section>

    </div>
  );
}
