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

// API utility functions
export const api = {
  // Get job recommendations for a user
  async getRecommendations(clerkId: string, limit: number = 10) {
    const url = `${API_BASE_URL}/api/recommend/${clerkId}?limit=${limit}`;
    console.log('📡 Fetching recommendations from:', url);
    
    const response = await fetch(url);
    console.log('📊 Response status:', response.status, response.statusText);
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error('❌ API Error:', errorText);
      throw new Error(`Failed to fetch recommendations: ${response.statusText}`);
    }
    
    const data = await response.json();
    console.log('✅ Recommendations received:', data?.length || 0, 'jobs');
    return data;
  },

  // Handle swipe actions (like, dislike, save)
  async handleSwipeAction(userId: string, jobId: string, action: 'like' | 'dislike' | 'save' | 'apply' | 'super_like') {
    const response = await fetch(`${API_BASE_URL}/api/recommend/swipe`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id: userId,
        job_id: jobId,
        action: action,
      }),
    });
    
    if (!response.ok) {
      throw new Error(`Failed to handle swipe action: ${response.statusText}`);
    }
    return response.json();
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


