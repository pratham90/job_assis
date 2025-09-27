import { AcceptedJobsProvider } from '../contexts/AcceptedJobsContext';
import { AntDesign, Feather, Ionicons } from '@expo/vector-icons';
import { Tabs, useRouter } from 'expo-router';
import React from 'react';
import { Platform, TouchableOpacity } from 'react-native';
import { useAuth } from '@clerk/clerk-expo';


import { HapticTab } from '../../components/HapticTab';
import TabBarBackground from '../../components/ui/TabBarBackground';
import { useColorScheme } from '../../hooks/useColorScheme';
import { SavedJobsProvider } from '../contexts/SavedJobsContext';

export default function TabLayout() {
  const colorScheme = useColorScheme();
  const { signOut } = useAuth();
  const router = useRouter();

  // Logout handler for header
  const handleLogout = async () => {
    try {
      await signOut();
      router.replace('/(auth)/sign-in');
    } catch (error) {
      // Optionally handle error
      console.error('Logout error:', error);
    }
  };

  // Reusable logout button
  const LogoutButton = () => (
    <TouchableOpacity onPress={handleLogout} style={{ marginRight: 16 }}>
      <Feather name="log-out" size={26} color="#FFFFFF" />
    </TouchableOpacity>
  );

  return (
    <SavedJobsProvider>
       <AcceptedJobsProvider>
      <Tabs
        screenOptions={{
        tabBarActiveTintColor: "#4A90E2",
        tabBarInactiveTintColor: "#6B7280",
        headerShown: true,
        tabBarButton: HapticTab,
        tabBarBackground: TabBarBackground,
        tabBarStyle: Platform.select({
          ios: {
            position: "absolute",
            bottom: 0,
            left: 16,
            right: 16,
            borderRadius: 16,
            height: 70,
            backgroundColor: "#1A1A1A",
            shadowColor: "#000",
            shadowOpacity: 0.5,
            shadowOffset: { width: 0, height: 5 },
            shadowRadius: 10,
            borderWidth: 0,
          },
          android: {
            position: "absolute",
            bottom: 0,
            left: 16,
            right: 16,
            borderRadius: 16,
            height: 70,
            backgroundColor: "#1A1A1A",
            elevation: 5,
            borderWidth: 0,
          },
          default: {
            position: "absolute",
            bottom: 0,
            left: 16,
            right: 16,
            borderRadius: 16,
            height: 70,
            backgroundColor: "#1A1A1A",
            borderWidth: 0,
          },
        }),
        tabBarLabelStyle: {
          fontSize: 12,
          fontWeight: "500",
          marginBottom: 8,
        },
        tabBarItemStyle: {
          paddingVertical: 8,
        },
        headerStyle: {
          backgroundColor: "#2C3E50",
          elevation: 0,
          shadowOpacity: 0,
          borderBottomWidth: 0,
        },
        headerTintColor: "#FFFFFF",
        headerTitleStyle: {
          fontSize: 18,
          fontWeight: "600",
          color: "#FFFFFF",
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          headerTitle: "Job-Seeker",
          title: "Home",
          tabBarIcon: ({ focused }) => (
            <AntDesign
              name="home"
              size={24}
              color={focused ? "#4A90E2" : "#6B7280"}
            />
          ),
          headerRight: () => <LogoutButton />,
        }}
      />
      <Tabs.Screen
        name="SeekerJobs"
        options={{
          headerTitle: "Industrial Jobs",
          title: "Jobs",
          tabBarIcon: ({ focused }) => (
            <Ionicons
              name="briefcase-outline"
              size={24}
              color={focused ? "#4A90E2" : "#6B7280"}
            />
          ),
          headerRight: () => <LogoutButton />,
        }}
      />
      <Tabs.Screen
        name="SavedJobs"
        options={{
          headerTitle: "Saved Jobs",
          title: "Saved",
          tabBarIcon: ({ focused }) => (
            <Ionicons
              name="bookmark-outline"
              size={24}
              color={focused ? "#4A90E2" : "#6B7280"}
            />
          ),
          headerRight: () => <LogoutButton />,
        }}
      />
      <Tabs.Screen
        name="SeekerProfile"
        options={{
          headerTitle: "Profile",
          title: "Profile",
          tabBarIcon: ({ focused }) => (
            <Ionicons
              name="person-outline"
              size={24}
              color={focused ? "#4A90E2" : "#6B7280"}
            />
          ),
          headerRight: () => <LogoutButton />,
        }}
      />
      </Tabs>
       </AcceptedJobsProvider>
    </SavedJobsProvider>
  );
}