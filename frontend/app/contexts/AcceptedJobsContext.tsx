import React, { createContext, useContext, useEffect, useState } from 'react';
import { getAcceptedJobs, saveAcceptedJob, removeAcceptedJob } from '../utils/acceptedJobsStorage';
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

  // Get user key (clerkId or email)
  const getUserKey = () => {
    if (!user) return "default";
    return user.id || user.primaryEmailAddress?.emailAddress || user.emailAddresses?.[0]?.emailAddress || "default";
  };

  const refreshAcceptedJobs = async () => {
    const userKey = getUserKey();
    console.log('Refreshing accepted jobs for user key:', userKey);
    const jobs = await getAcceptedJobs(userKey);
    console.log('Retrieved accepted jobs count:', jobs?.length || 0);
    setAcceptedJobs(jobs);
    return jobs; // Return jobs for immediate use
  };

  useEffect(() => {
    console.log('AcceptedJobsProvider: User changed, refreshing jobs');
    if (user) {
      console.log('User is authenticated, refreshing jobs');
      refreshAcceptedJobs();
    } else {
      console.log('No user authenticated, clearing jobs');
      setAcceptedJobs([]);
    }
  }, [user]);

  const addAcceptedJob = async (job: Job) => {
    const userKey = getUserKey();
    console.log('Adding job to context:', job.id, 'for user:', userKey);
    
    // Add userKey to the job object
    const jobWithUserKey = { ...job, userKey };
    
    // Save to storage
    const saveResult = await saveAcceptedJob(jobWithUserKey);
    
    if (saveResult) {
      console.log('Job saved successfully, updating state');
      // Update local state immediately for better UX
      // Check if job already exists for this user
      const exists = acceptedJobs.some(j => j.id === job.id && j.userKey === userKey);
      if (!exists) {
        setAcceptedJobs(prev => [...prev, jobWithUserKey]);
      }
    } else {
      console.log('Job not saved (likely duplicate)');
    }
    
    // Also refresh from storage to ensure consistency
    await refreshAcceptedJobs();
  };

  const removeAcceptedJobFn = async (jobId: string) => {
    const userKey = getUserKey();
    console.log('Removing job from context:', jobId, 'for user:', userKey);
    
    // Remove from storage
    await removeAcceptedJob(jobId, userKey);
    
    // Update local state immediately for better UX
    setAcceptedJobs(prev => prev.filter(job => job.id !== jobId));
    
    // Also refresh from storage to ensure consistency
    await refreshAcceptedJobs();
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