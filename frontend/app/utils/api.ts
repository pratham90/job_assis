import { Platform } from 'react-native';

const RAW_API_BASE = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:3000';

function normalizeBaseUrl(raw: string): string {
  try {
    // Ensure protocol
    const withProtocol = /^https?:\/\//i.test(raw) ? raw : `http://${raw}`;
    const u = new URL(withProtocol);
    // Replace 0.0.0.0 with a reachable host for clients
    if (u.hostname === '0.0.0.0') {
      // Android emulator special host, otherwise localhost
      u.hostname = Platform.OS === 'android' ? '10.0.2.2' : 'localhost';
    }
    // Trim trailing slash
    const normalized = u.toString().replace(/\/$/, '');
    return normalized;
  } catch {
    // Fallback: naive replacement and default
    const replaced = raw.replace('0.0.0.0', Platform.OS === 'android' ? '10.0.2.2' : 'localhost');
    return replaced || 'http://localhost:3000';
  }
}

export const API_BASE_URL = normalizeBaseUrl(RAW_API_BASE);

// Debug logging
console.log('🔗 API Configuration:');
console.log('  RAW_API_BASE:', RAW_API_BASE);
console.log('  API_BASE_URL:', API_BASE_URL);

// API utility functions with performance optimizations
export const api = {
  // Cache for API responses
  _cache: new Map<string, { data: any; timestamp: number }>(),
  _cacheTimeout: 5 * 60 * 1000, // 5 minutes

  // Cache helper methods
  _getCacheKey: (url: string, params?: any) => {
    return `${url}:${JSON.stringify(params || {})}`;
  },

  _getFromCache: (key: string) => {
    const cached = api._cache.get(key);
    if (cached && Date.now() - cached.timestamp < api._cacheTimeout) {
      console.log('📋 Cache hit for:', key);
      return cached.data;
    }
    if (cached) {
      api._cache.delete(key);
    }
    return null;
  },

  _setCache: (key: string, data: any) => {
    api._cache.set(key, { data, timestamp: Date.now() });
  },
  // Get job recommendations for a user with caching
  async getRecommendations(clerkId: string, limit: number = 10, location: string = 'All Locations') {
    const cacheKey = api._getCacheKey('/api/recommend', { clerkId, limit, location });
    const cached = api._getFromCache(cacheKey);
    if (cached) return cached;

    const locParam = `&location=${encodeURIComponent(location)}`;
    const url = `${API_BASE_URL}/api/recommend/${clerkId}?limit=${limit}${locParam}`;
    console.log('📡 Fetching recommendations from:', url);
    console.log('📍 Location parameter:', location);
    
    const response = await fetch(url);
    console.log('📊 Response status:', response.status, response.statusText);
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error('❌ API Error:', errorText);
      throw new Error(`Failed to fetch recommendations: ${response.statusText}`);
    }
    
    const data = await response.json();
    console.log('✅ Recommendations received:', data?.length || 0, 'jobs');
    
    // Cache the results
    api._setCache(cacheKey, data);
    return data;
  },

  // Handle swipe actions (like, dislike, save)
  async handleSwipeAction(userId: string, jobId: string, action: 'like' | 'dislike' | 'save' | 'apply' | 'super_like', jobPayload?: any) {
    const response = await fetch(`${API_BASE_URL}/api/recommend/swipe`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id: userId,
        job_id: jobId,
        action: action,
        job_payload: jobPayload,
      }),
    });
    
    if (!response.ok) {
      throw new Error(`Failed to handle swipe action: ${response.statusText}`);
    }
    return response.json();
  },

  // Saved jobs APIs with caching
  async getSavedJobs(clerkId: string) {
    const cacheKey = api._getCacheKey('/api/recommend/saved', { clerkId });
    const cached = api._getFromCache(cacheKey);
    if (cached) return cached;

    const url = `${API_BASE_URL}/api/recommend/saved/${clerkId}`;
    console.log('📡 Fetching saved jobs from:', url);
    const response = await fetch(url);
    if (!response.ok) throw new Error(`Failed to fetch saved jobs: ${response.statusText}`);
    const data = await response.json();
    console.log('✅ Saved jobs received:', data?.length || 0);
    
    // Cache the results
    api._setCache(cacheKey, data);
    return data;
  },

  async removeSavedJob(userId: string, jobId: string) {
    const url = `${API_BASE_URL}/api/recommend/saved/remove`;
    console.log('🗑️  Removing saved job from:', url);
    console.log('   User ID:', userId);
    console.log('   Job ID:', jobId);
    
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, job_id: jobId }),
    });
    
    console.log('📊 Remove response status:', response.status, response.statusText);
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error('❌ Remove saved job error:', errorText);
      throw new Error(`Failed to remove saved job: ${response.statusText}`);
    }
    
    const data = await response.json();
    console.log('✅ Remove saved job response:', data);
    return data;
  },

  // Liked jobs APIs
  async getLikedJobs(clerkId: string) {
    const url = `${API_BASE_URL}/api/recommend/liked/${clerkId}`;
    console.log('💚 Fetching liked jobs from:', url);
    const response = await fetch(url);
    if (!response.ok) throw new Error(`Failed to fetch liked jobs: ${response.statusText}`);
    const data = await response.json();
    console.log('✅ Liked jobs received:', data?.length || 0);
    return data;
  },

  async removeLikedJob(userId: string, jobId: string) {
    const url = `${API_BASE_URL}/api/recommend/liked/remove`;
    console.log('🗑️  Removing liked job from:', url);
    console.log('   User ID:', userId);
    console.log('   Job ID:', jobId);
    
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, job_id: jobId }),
    });
    
    console.log('📊 Remove liked job response status:', response.status, response.statusText);
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error('❌ Remove liked job error:', errorText);
      throw new Error(`Failed to remove liked job: ${response.statusText}`);
    }
    
    const data = await response.json();
    console.log('✅ Remove liked job response:', data);
    return data;
  },


  // Disliked jobs APIs
  async getDislikedJobs(clerkId: string) {
    const url = `${API_BASE_URL}/api/recommend/disliked/${clerkId}`;
    console.log('👎 Fetching disliked jobs from:', url);
    const response = await fetch(url);
    if (!response.ok) throw new Error(`Failed to fetch disliked jobs: ${response.statusText}`);
    const data = await response.json();
    console.log('✅ Disliked jobs received:', data?.length || 0);
    return data;
  },

  async removeDislikedJob(userId: string, jobId: string) {
    const url = `${API_BASE_URL}/api/recommend/disliked/remove`;
    console.log('🗑️  Removing disliked job from:', url);
    console.log('   User ID:', userId);
    console.log('   Job ID:', jobId);
    
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, job_id: jobId }),
    });
    
    console.log('📊 Remove disliked job response status:', response.status, response.statusText);
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error('❌ Remove disliked job error:', errorText);
      throw new Error(`Failed to remove disliked job: ${response.statusText}`);
    }
    
    const data = await response.json();
    console.log('✅ Remove disliked job response:', data);
    return data;
  },

  async checkJobDisliked(clerkId: string, jobId: string) {
    const url = `${API_BASE_URL}/api/recommend/disliked/check/${clerkId}/${jobId}`;
    console.log('🔍 Checking if job is disliked:', url);
    const response = await fetch(url);
    if (!response.ok) throw new Error(`Failed to check job dislike status: ${response.statusText}`);
    const data = await response.json();
    console.log('✅ Job dislike check result:', data);
    return data;
  },

  // Create a new user
  async createUser(userData: {
    clerk_id: string;
    email: string;
    first_name: string;
    last_name: string;
    role?: string;
    skills?: string[];
    location?: string;
    company_name?: string;
  }) {
    const url = `${API_BASE_URL}/api/recommend/create-user`;
    console.log('📝 Creating user at:', url);
    console.log('📝 User data:', userData);
    
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(userData),
    });
    
    console.log('📊 Create user response status:', response.status, response.statusText);
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error('❌ Create user API Error:', errorText);
      throw new Error(`Failed to create user: ${response.statusText}`);
    }
    
    const data = await response.json();
    console.log('✅ User created successfully:', data);
    return data;
  },

  // Create sample user for testing
  async createSampleUser() {
    const response = await fetch(`${API_BASE_URL}/api/recommend/create-sample-user`, {
      method: 'POST',
    });
    
    if (!response.ok) {
      throw new Error(`Failed to create sample user: ${response.statusText}`);
    }
    return response.json();
  },
};


