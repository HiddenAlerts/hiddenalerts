"use client";
import { useState } from "react";

export default function Home() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = () => {
    if (!email) return;
    console.log("Captured email:", email); // temporary
    setSubmitted(true);
  };

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

        <p className="text-lg text-zinc-400 mb-4 max-w-2xl">
          AI-filtered, risk-scored alerts from FBI, SEC, DOJ and more — so you
          can identify threats before they escalate.
        </p>

        <p className="text-sm text-red-500 mb-8">
          Most fraud signals are missed in the first 24 hours.
        </p>

        {/* EMAIL CAPTURE */}
        {!submitted ? (
          <div className="flex flex-col sm:flex-row gap-3 max-w-md">
            <input
              type="email"
              placeholder="Enter your email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="flex-1 px-4 py-3 rounded-md bg-zinc-900 border border-zinc-700 text-white focus:outline-none"
            />
            <button
              onClick={handleSubmit}
              className="bg-red-600 px-6 py-3 rounded-md font-semibold hover:bg-red-700"
            >
              Get Early Access
            </button>
          </div>
        ) : (
          <p className="text-green-500 font-semibold">
            You’re on the list. Early access coming soon.
          </p>
        )}
      </section>

      {/* ALERT PREVIEW */}
      <section className="px-8 py-12 max-w-5xl mx-auto">
        <h2 className="text-2xl font-semibold mb-6">Live Intelligence Feed</h2>

        <div className="space-y-6">

          <div className="bg-zinc-900 p-6 rounded-lg border border-zinc-800">
            <div className="flex justify-between mb-2">
              <span className="text-sm text-zinc-400">DOJ • 2 hours ago</span>
              <span className="text-red-500 text-sm font-semibold">HIGH RISK</span>
            </div>
            <h3 className="text-lg font-semibold mb-2">
              $19M WIC Fraud Scheme — Multi-State Operation
            </h3>
            <p className="text-zinc-400 text-sm">
              Why it matters: Indicates coordinated fraud ring likely expanding across states.
            </p>
          </div>

          <div className="bg-zinc-900 p-6 rounded-lg border border-zinc-800">
            <div className="flex justify-between mb-2">
              <span className="text-sm text-zinc-400">SEC • 5 hours ago</span>
              <span className="text-yellow-500 text-sm font-semibold">MEDIUM RISK</span>
            </div>
            <h3 className="text-lg font-semibold mb-2">
              Investment Scam Targeting Retirees
            </h3>
            <p className="text-zinc-400 text-sm">
              Why it matters: Pattern of targeted financial exploitation increasing.
            </p>
          </div>

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
      </section>

    </div>
  );
}
