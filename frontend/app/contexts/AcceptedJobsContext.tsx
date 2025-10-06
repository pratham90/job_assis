import React, { createContext, useContext, useEffect, useState } from 'react';
import { api } from '../utils/api';
import { useUser } from '@clerk/clerk-expo';

type Job = {
  id: string;
  [key: string]: any;
};

type AcceptedJobsContextType = {
  acceptedJobs: Job[];
  addAcceptedJob: (job: Job) => Promise<void>;
  removeAcceptedJob: (jobId: string) => Promise<void>;
  refreshAcceptedJobs: () => Promise<void>;
};

const AcceptedJobsContext = createContext<AcceptedJobsContextType | undefined>(undefined);

export const AcceptedJobsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [acceptedJobs, setAcceptedJobs] = useState<Job[]>([]);
  const { user } = useUser();

  const refreshAcceptedJobs = async () => {
    if (!user?.id) {
      console.log('No user authenticated, clearing jobs');
      setAcceptedJobs([]);
      return;
    }
    
    try {
      console.log('Fetching liked jobs (applied jobs) from backend for user:', user.id);
      // Liked jobs represent applied jobs in our 3-action system
      const jobs = await api.getLikedJobs(user.id);
      console.log('Retrieved liked jobs (applied) count:', jobs?.length || 0);
      setAcceptedJobs(jobs);
      return jobs;
    } catch (error) {
      console.error('Failed to fetch liked jobs (applied):', error);
      setAcceptedJobs([]);
      return [];
    }
  };

  useEffect(() => {
    console.log('AcceptedJobsProvider: User changed, refreshing jobs');
    if (user) {
      console.log('User is authenticated, fetching liked jobs (applied) from backend');
      refreshAcceptedJobs();
    } else {
      console.log('No user authenticated, clearing jobs');
      setAcceptedJobs([]);
    }
  }, [user]);

  const addAcceptedJob = async (job: Job) => {
    if (!user?.id) {
      console.log('No user authenticated, cannot add job');
      return;
    }
    
    console.log('Adding liked job (applied) to backend:', job.id, 'for user:', user.id);
    
    // The job is already sent to backend via handleSwipeAction in index.tsx
    // Just update local state optimistically and refresh
    const exists = acceptedJobs.some(j => j.id === job.id);
    if (!exists) {
      setAcceptedJobs(prev => [...prev, job]);
    }
    
    // Refresh from backend to ensure consistency
    setTimeout(() => refreshAcceptedJobs(), 500);
  };

  const removeAcceptedJobFn = async (jobId: string) => {
    if (!user?.id) {
      console.log('No user authenticated, cannot remove job');
      return;
    }
    
    console.log('Removing liked job (applied) from backend:', jobId, 'for user:', user.id);
    
    // Update local state immediately for better UX
    setAcceptedJobs(prev => prev.filter(job => job.id !== jobId));
    
    // Call backend to remove liked job
    try {
      await api.removeLikedJob(user.id, jobId);
    } catch (error) {
      console.error('Failed to remove liked job (applied) from backend:', error);
    }
    
    // Refresh to sync with backend
    setTimeout(() => refreshAcceptedJobs(), 500);
  };

  return (
    <AcceptedJobsContext.Provider value={{ acceptedJobs, addAcceptedJob, removeAcceptedJob: removeAcceptedJobFn, refreshAcceptedJobs }}>
      {children}
    </AcceptedJobsContext.Provider>
  );
};

export const useAcceptedJobs = () => {
  const context = useContext(AcceptedJobsContext);
  if (!context) {
    throw new Error('useAcceptedJobs must be used within an AcceptedJobsProvider');
  }
  return context;
};