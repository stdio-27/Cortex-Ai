import React from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Download } from 'lucide-react';

interface ReportViewerProps {
  markdown: string;
}

const ReportViewer: React.FC<ReportViewerProps> = ({ markdown }) => {
  const handleDownload = () => {
    const blob = new Blob([markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'research_report.md';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="w-full max-w-4xl mx-auto mt-12 bg-gray-800/60 backdrop-blur-xl rounded-3xl border border-gray-700/50 shadow-2xl overflow-hidden animate-fade-in-up">
      <div className="flex items-center justify-between px-8 py-6 border-b border-gray-700/50 bg-gray-900/40">
        <h3 className="text-xl font-bold text-gray-200">Research Report</h3>
        <button
          onClick={handleDownload}
          className="flex items-center gap-2 bg-indigo-500/20 hover:bg-indigo-500/30 text-indigo-400 px-4 py-2 rounded-xl transition-colors duration-300 border border-indigo-500/30 font-medium"
        >
          <Download size={18} />
          <span>Download Markdown</span>
        </button>
      </div>
      <div className="p-8 md:p-12 overflow-x-auto">
        <div className="prose prose-invert prose-indigo max-w-none prose-pre:bg-gray-900 prose-pre:border prose-pre:border-gray-700">
          <Markdown remarkPlugins={[remarkGfm]}>
            {markdown}
          </Markdown>
        </div>
      </div>
    </div>
  );
};

export default ReportViewer;
