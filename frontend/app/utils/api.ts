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


