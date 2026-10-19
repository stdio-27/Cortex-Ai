import { create } from 'zustand';

type JobStep = 'Planner' | 'AWAITING_HUMAN_FEEDBACK' | 'Search' | 'Synthesizing' | 'Verification' | 'Critiquing' | 'DONE' | 'ERROR';

interface JobState {
  jobId: string | null;
  status: 'IDLE' | 'PENDING' | 'PROCESSING' | 'AWAITING_INPUT' | 'COMPLETED' | 'FAILED';
  currentStep: JobStep | null;
  error?: string;
  reportContent: string | null;
  subTopics: string[];
  verificationMetadata: any | null;
  startJob: (query: string) => Promise<void>;
  resumeJob: (jobId: string, approvedQueries: string[]) => Promise<void>;
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
  subTopics: [],
  verificationMetadata: null,

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
      subTopics: [],
      verificationMetadata: null,
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

  resumeJob: async (jobId: string, approvedQueries: string[]) => {
    set({ status: 'PROCESSING', currentStep: 'Search' });
    try {
      const res = await fetch(`/api/jobs/${jobId}/resume`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ approved_queries: approvedQueries })
      });

      if (!res.ok) throw new Error('Failed to resume job');
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
      const parsedEvent = JSON.parse(event.data);
      console.log("SSE Event:", parsedEvent);
      
      const payload = parsedEvent.data || {};
      const step = payload.step;
      
      if (parsedEvent.event_type === 'COMPLETED' || step === 'DONE') {
        set({ status: 'COMPLETED', currentStep: 'DONE' });
        eventSource?.close();
        get().fetchReport(jobId);
      } else if (parsedEvent.event_type === 'ERROR' || step === 'ERROR') {
        set({ status: 'FAILED', currentStep: 'ERROR', error: payload.error });
        eventSource?.close();
      } else if (parsedEvent.event_type === 'AWAITING_INPUT' || step === 'AWAITING_HUMAN_FEEDBACK') {
        set({ status: 'AWAITING_INPUT', currentStep: 'AWAITING_HUMAN_FEEDBACK', subTopics: payload.sub_topics || [] });
      } else if (step === 'VERIFICATION_COMPLETE') {
        set({ verificationMetadata: payload.verification_metadata });
      } else if (step) {
        set({ currentStep: step });
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
      set({ 
          reportContent: data.report || null,
          verificationMetadata: data.verification_metadata || get().verificationMetadata
      });
    } catch (error: any) {
      console.error("Error fetching report:", error);
    }
  }
}));
