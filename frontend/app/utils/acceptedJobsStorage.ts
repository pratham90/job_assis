import AsyncStorage from '@react-native-async-storage/async-storage';

const ACCEPTED_JOBS_KEY = 'accepted_jobs';

export async function saveAcceptedJob(job: any) {
  try {
    const jobs = await getAcceptedJobs();
    // Avoid duplicates by job id
    const exists = jobs.some((j: any) => j.id === job.id);
    if (!exists) {
      const updatedJobs = [...jobs, job];
      await AsyncStorage.setItem(ACCEPTED_JOBS_KEY, JSON.stringify(updatedJobs));
    }
  } catch (error) {
    console.error('Error saving accepted job:', error);
  }
}

export async function getAcceptedJobs(): Promise<any[]> {
  try {
    const jobsString = await AsyncStorage.getItem(ACCEPTED_JOBS_KEY);
    return jobsString ? JSON.parse(jobsString) : [];
  } catch (error) {
    console.error('Error getting accepted jobs:', error);
    return [];
  }
}

export async function removeAcceptedJob(jobId: string) {
  try {
    const jobs = await getAcceptedJobs();
    const updatedJobs = jobs.filter((j: any) => j.id !== jobId);
    await AsyncStorage.setItem(ACCEPTED_JOBS_KEY, JSON.stringify(updatedJobs));
  } catch (error) {
    console.error('Error removing accepted job:', error);
  }
}