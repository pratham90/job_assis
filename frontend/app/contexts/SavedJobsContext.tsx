import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";
// Moving away from local storage to backend persistence
import { api } from "../utils/api";
import { useUser } from "@clerk/clerk-expo";

// Job type for context (should match your Job type in index.tsx)
export interface Job {
  id: string;
  title: string;
  company: string;
  location: string;
  salary: string;
  matchPercentage: number;
  type: string;
  description: string;
  requirements: string[];
  benefits: string[];
  tags: string[];
  postedTime: string;
  companySize: string;
  experience: string;
}

interface SavedJobsContextType {
  savedJobs: Job[];
  addJob: (job: Job) => void;
  removeJob: (jobId: string) => void;
  isJobSaved: (jobId: string) => boolean;
  refreshSavedJobs: () => void;
}

const SavedJobsContext = createContext<SavedJobsContextType | undefined>(undefined);

export const SavedJobsProvider = ({ children }: { children: ReactNode }) => {
  const [savedJobs, setSavedJobs] = useState<Job[]>([]);
  const { user } = useUser();

  // Get user key (clerkId or email)
  const getUserKey = () => {
    if (!user) return "default";
    return user.id || user.primaryEmailAddress?.emailAddress || user.emailAddresses?.[0]?.emailAddress || "default";
  };

  // Load saved jobs for current user from backend on mount and when user changes
  useEffect(() => {
    (async () => {
      const userKey = getUserKey();
      if (userKey && userKey !== "default") {
        try {
          const jobs = await api.getSavedJobs(userKey);
          setSavedJobs(jobs || []);
        } catch (e) {
          console.warn("Failed to load saved jobs:", e);
          setSavedJobs([]);
        }
      } else {
        setSavedJobs([]);
      }
    })();
  }, [user]);

  const addJob = async (job: Job) => {
    const userKey = getUserKey();
    try {
      await api.handleSwipeAction(userKey, job.id, 'save');
      const jobs = await api.getSavedJobs(userKey);
      setSavedJobs(jobs || []);
    } catch (e) {
      console.warn('Failed to save job:', e);
    }
  };

  const removeJob = async (jobId: string) => {
    const userKey = getUserKey();
    console.log('🔄 SavedJobsContext: removeJob called');
    console.log('   User Key:', userKey);
    console.log('   Job ID:', jobId);
    try {
      console.log('📡 Calling API to remove saved job...');
      await api.removeSavedJob(userKey, jobId);
      console.log('✅ API call successful, refreshing saved jobs list...');
      const jobs = await api.getSavedJobs(userKey);
      console.log('✅ Refreshed saved jobs, count:', jobs?.length || 0);
      setSavedJobs(jobs || []);
    } catch (e) {
      console.error('❌ Failed to remove saved job:', e);
      console.warn('Failed to remove saved job:', e);
    }
  };

  const isJobSaved = (jobId: string) => {
    return savedJobs.some((job) => job.id === jobId);
  };

  const refreshSavedJobs = async () => {
    const userKey = getUserKey();
    if (!userKey || userKey === 'default') {
      setSavedJobs([]);
      return;
    }
    try {
      const jobs = await api.getSavedJobs(userKey);
      setSavedJobs(jobs || []);
    } catch (e) {
      console.warn('Failed to refresh saved jobs:', e);
    }
  };

  return (
    <SavedJobsContext.Provider value={{ savedJobs, addJob, removeJob, isJobSaved, refreshSavedJobs }}>
      {children}
    </SavedJobsContext.Provider>
  );
};

export const useSavedJobs = () => {
  const context = useContext(SavedJobsContext);
  if (!context) {
    throw new Error("useSavedJobs must be used within a SavedJobsProvider");
  }
  return context;
};
