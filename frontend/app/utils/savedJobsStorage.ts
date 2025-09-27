const SAVED_JOBS_KEY = 'saved_jobs';

function isWebPlatform() {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';
}

export async function saveJob(job: any) {
  try {
    const jobs = await getSavedJobs();
    // Avoid duplicates for this user
    const exists = jobs.some((j: any) => j.id === job.id && j.userKey === job.userKey);
    if (!exists) {
      const updatedJobs = [...jobs, job];
      if (isWebPlatform()) {
        window.localStorage.setItem(SAVED_JOBS_KEY, JSON.stringify(updatedJobs));
      } else {
        const AsyncStorage = (await import('@react-native-async-storage/async-storage')).default;
        await AsyncStorage.setItem(SAVED_JOBS_KEY, JSON.stringify(updatedJobs));
      }
    }
  } catch (error) {
    console.error('Error saving job:', error);
  }
}

export async function getSavedJobs(): Promise<any[]> {
  try {
    if (isWebPlatform()) {
      const jobsString = window.localStorage.getItem(SAVED_JOBS_KEY);
      return jobsString ? JSON.parse(jobsString) : [];
    } else {
      const AsyncStorage = (await import('@react-native-async-storage/async-storage')).default;
      const jobsString = await AsyncStorage.getItem(SAVED_JOBS_KEY);
      return jobsString ? JSON.parse(jobsString) : [];
    }
  } catch (error) {
    console.error('Error getting saved jobs:', error);
    return [];
  }
}

export async function removeSavedJob(jobId: string, userKey?: string) {
  try {
    const jobs = await getSavedJobs();
    // Remove only jobs for this user if userKey is provided
    const updatedJobs = userKey
      ? jobs.filter((j: any) => !(j.id === jobId && j.userKey === userKey))
      : jobs.filter((j: any) => j.id !== jobId);
    if (isWebPlatform()) {
      window.localStorage.setItem(SAVED_JOBS_KEY, JSON.stringify(updatedJobs));
    } else {
      const AsyncStorage = (await import('@react-native-async-storage/async-storage')).default;
      await AsyncStorage.setItem(SAVED_JOBS_KEY, JSON.stringify(updatedJobs));
    }
  } catch (error) {
    console.error('Error removing saved job:', error);
  }
}
