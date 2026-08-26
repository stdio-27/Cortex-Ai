import { create } from 'zustand';

type JobStep = 'Planner' | 'Search' | 'Synthesizing' | 'Critiquing' | 'DONE' | 'ERROR';

interface JobState {
  jobId: string | null;
  status: 'IDLE' | 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  currentStep: JobStep | null;
  error?: string;
  reportContent: string | null;
  startJob: (query: string) => Promise<void>;
  listenToJob: (jobId: string) => void;
  fetchReport: (jobId: string) => Promise<void>;
  reset: () => void;
}

let eventSource: EventSource | null = null;

export const useJobStore = create<JobState>((set, get) => ({
  jobId: null,
  status: 'IDLE',
  currentStep: null,
  reportContent: null,

  reset: () => {
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
    set({
      jobId: null,
      status: 'IDLE',
      currentStep: null,
      error: undefined,
      reportContent: null,
    });
  },

  startJob: async (query: string) => {
    if (!query.trim()) return;

    get().reset();
    set({ status: 'PENDING' });

    try {
      const res = await fetch('/api/jobs', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ query })
      });

      if (!res.ok) throw new Error('Failed to start job');

      const data = await res.json();
      set({ jobId: data.job_id, status: 'PROCESSING' });
      get().listenToJob(data.job_id);
    } catch (error: any) {
      set({ status: 'FAILED', currentStep: 'ERROR', error: error.message });
    }
  },

  listenToJob: (jobId: string) => {
    if (eventSource) {
      eventSource.close();
    }

    eventSource = new EventSource(`/api/jobs/${jobId}/stream`);

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log("SSE Event:", data);
      
      if (data.step === 'DONE') {
        set({ status: 'COMPLETED', currentStep: 'DONE' });
        eventSource?.close();
        get().fetchReport(jobId);
      } else if (data.step === 'ERROR') {
        set({ status: 'FAILED', currentStep: 'ERROR' });
        eventSource?.close();
      } else {
        set({ currentStep: data.step });
      }
    };

    eventSource.onerror = () => {
      console.error("SSE Error");
      eventSource?.close();
    };
  },

  fetchReport: async (jobId: string) => {
    try {
      const res = await fetch(`/api/jobs/${jobId}`);
      if (!res.ok) throw new Error('Failed to fetch report');
      const data = await res.json();
      set({ reportContent: data.report || null });
    } catch (error: any) {
      console.error("Error fetching report:", error);
    }
  }
}));
