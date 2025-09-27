import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { saveJob, getSavedJobs, removeSavedJob } from "../utils/savedJobsStorage";
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

  // Load saved jobs for current user on mount and when user changes
  useEffect(() => {
    (async () => {
      const allJobs = await getSavedJobs();
      const userKey = getUserKey();
      // Only show jobs for current user
      const jobs = allJobs.filter((j: any) => j.userKey === userKey);
      setSavedJobs(jobs);
    })();
  }, [user]);

  const addJob = async (job: Job) => {
    const userKey = getUserKey();
    // Avoid duplicates for this user
    const allJobs = await getSavedJobs();
    const exists = allJobs.some((j: any) => j.id === job.id && j.userKey === userKey);
    if (!exists) {
      await saveJob({ ...job, userKey });
    }
    // Refresh jobs for this user
    const jobs = (await getSavedJobs()).filter((j: any) => j.userKey === userKey);
    setSavedJobs(jobs);
  };

  const removeJob = async (jobId: string) => {
    const userKey = getUserKey();
    // Remove only for this user
    const allJobs = await getSavedJobs();
    const updatedJobs = allJobs.filter((j: any) => !(j.id === jobId && j.userKey === userKey));
    // Save updated jobs
    if (typeof window !== 'undefined' && window.localStorage) {
      window.localStorage.setItem('saved_jobs', JSON.stringify(updatedJobs));
    } else {
      const AsyncStorage = (await import('@react-native-async-storage/async-storage')).default;
      await AsyncStorage.setItem('saved_jobs', JSON.stringify(updatedJobs));
    }
    setSavedJobs(updatedJobs.filter((j: any) => j.userKey === userKey));
  };

  const isJobSaved = (jobId: string) => {
    const userKey = getUserKey();
    return savedJobs.some((job) => job.id === jobId && job.userKey === userKey);
  };

  const refreshSavedJobs = async () => {
    const userKey = getUserKey();
    const jobs = (await getSavedJobs()).filter((j: any) => j.userKey === userKey);
    setSavedJobs(jobs);
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
