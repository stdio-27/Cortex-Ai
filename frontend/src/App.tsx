import { useState } from 'react';
import './App.css';
import { useJobStore } from './store/useJobStore';
import ReportViewer from './components/ReportViewer';

const STEPS = ['Planner', 'Search', 'Synthesizing', 'Critiquing'];

function App() {
  const [query, setQuery] = useState('');
  
  const { status, currentStep, error, reportContent, startJob } = useJobStore();

  return (
    <div className="min-h-screen bg-gray-900 text-white font-sans selection:bg-indigo-500/30 flex flex-col items-center py-20 px-4 relative overflow-hidden">
      {/* Background Orbs */}
      <div className="absolute top-[-10%] left-[-10%] w-[40vw] h-[40vw] rounded-full bg-indigo-600/20 blur-[120px] pointer-events-none"></div>
      <div className="absolute bottom-[-10%] right-[-10%] w-[40vw] h-[40vw] rounded-full bg-purple-600/20 blur-[120px] pointer-events-none"></div>

      <div className="z-10 w-full max-w-4xl flex flex-col items-center gap-12">
        <div className="text-center space-y-4">
          <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400 drop-shadow-sm">
            Cortex AI
          </h1>
          <p className="text-gray-400 text-lg md:text-xl max-w-2xl mx-auto font-medium">
            Autonomous Research Copilot. Enter your query and watch the agent graph work in real-time.
          </p>
        </div>

        <div className="w-full max-w-2xl relative group">
          <div className="absolute -inset-1 bg-gradient-to-r from-indigo-500 to-purple-500 rounded-2xl blur opacity-25 group-hover:opacity-40 transition duration-500"></div>
          <div className="relative flex items-center bg-gray-800/80 backdrop-blur-xl rounded-2xl p-2 border border-gray-700/50 shadow-2xl">
            <input
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="What would you like to research today?"
              className="flex-1 bg-transparent border-none outline-none text-white px-6 py-4 text-lg placeholder-gray-500"
              onKeyDown={e => e.key === 'Enter' && startJob(query)}
            />
            <button
              onClick={() => startJob(query)}
              disabled={status === 'PENDING' || status === 'PROCESSING'}
              className="bg-indigo-500 hover:bg-indigo-600 text-white px-8 py-4 rounded-xl font-semibold transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed transform active:scale-95 shadow-[0_0_20px_rgba(99,102,241,0.4)]"
            >
              {status === 'PENDING' ? 'Starting...' : 'Research'}
            </button>
          </div>
        </div>

        {/* Agent Graph Visualization */}
        <div className="w-full mt-12 bg-gray-800/40 backdrop-blur-md rounded-3xl p-10 border border-gray-700/50 shadow-2xl transition-all duration-500">
          <h2 className="text-2xl font-bold mb-12 text-center text-gray-200">Agent Workflow</h2>
          
          <div className="flex flex-col md:flex-row justify-between items-center relative gap-8 md:gap-0">
            {/* Connecting Line */}
            <div className="hidden md:block absolute top-1/2 left-[10%] right-[10%] h-1 bg-gray-700 -translate-y-1/2 z-0"></div>
            
            {STEPS.map((step, index) => {
              const isPast = 
                (status === 'COMPLETED') ||
                (currentStep && STEPS.indexOf(currentStep as string) > index);
              const isCurrent = currentStep === step;

              return (
                <div key={step} className="relative z-10 flex flex-col items-center gap-4 w-32">
                  <div className={`
                    w-20 h-20 rounded-2xl flex items-center justify-center text-2xl shadow-xl transition-all duration-500
                    ${isPast ? 'bg-indigo-500 shadow-[0_0_30px_rgba(99,102,241,0.6)] scale-100 border-2 border-indigo-400' : 
                      isCurrent ? 'bg-purple-600 shadow-[0_0_40px_rgba(147,51,234,0.8)] scale-110 border-2 border-purple-400 animate-pulse' : 
                      'bg-gray-800/80 border-2 border-gray-700 text-gray-500 scale-90'}
                  `}>
                    {index === 0 && '📝'}
                    {index === 1 && '🔍'}
                    {index === 2 && '🧠'}
                    {index === 3 && '⚖️'}
                  </div>
                  <span className={`font-semibold tracking-wide transition-colors duration-300
                    ${isPast || isCurrent ? 'text-gray-100' : 'text-gray-500'}
                  `}>
                    {step}
                  </span>
                  {isCurrent && (
                    <span className="absolute -bottom-8 text-sm text-purple-400 font-medium animate-bounce">
                      Processing...
                    </span>
                  )}
                </div>
              );
            })}
          </div>
          
          {status === 'COMPLETED' && (
            <div className="mt-16 text-center animate-fade-in-up">
              <div className="inline-flex items-center gap-3 bg-emerald-500/20 text-emerald-400 px-6 py-3 rounded-full border border-emerald-500/30">
                <span className="text-xl">✨</span>
                <span className="font-semibold text-lg">Research Completed Successfully!</span>
              </div>
            </div>
          )}
          
          {status === 'FAILED' && (
            <div className="mt-16 text-center animate-fade-in-up">
              <div className="inline-flex items-center gap-3 bg-red-500/20 text-red-400 px-6 py-3 rounded-full border border-red-500/30">
                <span className="text-xl">⚠️</span>
                <span className="font-semibold text-lg">Error: {error || 'Job failed during execution'}</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {status === 'COMPLETED' && reportContent && (
        <ReportViewer markdown={reportContent} />
      )}
    </div>
  );
}

export default App;
