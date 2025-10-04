import { useAuth, useUser } from "@clerk/clerk-expo";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import { API_BASE_URL, api } from "../utils/api";
import * as Location from "expo-location";
import React, { useEffect, useState } from "react";
import { useSavedJobs } from "../contexts/SavedJobsContext";
import { useAcceptedJobs } from "../contexts/AcceptedJobsContext";
import {
  Alert,
  Dimensions,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import {
  GestureHandlerRootView,
  PanGestureHandler,
} from "react-native-gesture-handler";
import Animated, {
  Extrapolate,
  interpolate,
  runOnJS,
  useAnimatedGestureHandler,
  useAnimatedStyle,
  useSharedValue,
  withSequence,
  withSpring,
  withTiming,
} from "react-native-reanimated";

// Types
interface Job {
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

// Export interfaces and types
export interface JobSwipeCardProps {
  job: Job;
  onSwipeLeft: () => void;
  onSwipeRight: () => void;
  onBookmark: () => void;
  isTop: boolean;
  isSaved: boolean;
}

const { width, height } = Dimensions.get("window");
const SWIPE_THRESHOLD = 100;

export default function SeekerJobs() {
  // Swipe limit states
  const [swipeLimit, setSwipeLimit] = useState<number>(20);
  const [swipeResetTime, setSwipeResetTime] = useState<Date | null>(null);
  const [userKey, setUserKey] = useState<string>("");
  const isWeb = typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';
  // Accepted jobs context
  const { addAcceptedJob } = useAcceptedJobs();

  // Clerk user info
   // Clerk user info
  const { isSignedIn } = useAuth();
  const { user } = useUser();

  // Swipe limit logic (per user, cross-platform)
  useEffect(() => {
    if (!user) return;
    const key = user.id || user.primaryEmailAddress?.emailAddress || user.emailAddresses?.[0]?.emailAddress || "default";
    setUserKey(key);
    const now = new Date();
    if (isWeb) {
      const swipeData = window.localStorage.getItem(`swipeLimitData_${key}`);
      if (swipeData) {
        const parsed = JSON.parse(swipeData);
        const resetTime = new Date(parsed.resetTime);
        if (now > resetTime) {
          setSwipeLimit(20);
          setSwipeResetTime(new Date(now.getTime() + 24 * 60 * 60 * 1000));
          window.localStorage.setItem(`swipeLimitData_${key}`, JSON.stringify({ count: 0, resetTime: new Date(now.getTime() + 24 * 60 * 60 * 1000) }));
        } else {
          setSwipeLimit(20 - parsed.count);
          setSwipeResetTime(resetTime);
        }
      } else {
        setSwipeLimit(20);
        setSwipeResetTime(new Date(now.getTime() + 24 * 60 * 60 * 1000));
        window.localStorage.setItem(`swipeLimitData_${key}`, JSON.stringify({ count: 0, resetTime: new Date(now.getTime() + 24 * 60 * 60 * 1000) }));
      }
    } else {
      // Mobile: use AsyncStorage
      const AsyncStorage = require('@react-native-async-storage/async-storage').default;
      (async () => {
        const swipeData = await AsyncStorage.getItem(`swipeLimitData_${key}`);
        if (swipeData) {
          const parsed = JSON.parse(swipeData);
          const resetTime = new Date(parsed.resetTime);
          if (now > resetTime) {
            setSwipeLimit(20);
            setSwipeResetTime(new Date(now.getTime() + 24 * 60 * 60 * 1000));
            await AsyncStorage.setItem(`swipeLimitData_${key}`, JSON.stringify({ count: 0, resetTime: new Date(now.getTime() + 24 * 60 * 60 * 1000) }));
          } else {
            setSwipeLimit(20 - parsed.count);
            setSwipeResetTime(resetTime);
          }
        } else {
          setSwipeLimit(20);
          setSwipeResetTime(new Date(now.getTime() + 24 * 60 * 60 * 1000));
          await AsyncStorage.setItem(`swipeLimitData_${key}`, JSON.stringify({ count: 0, resetTime: new Date(now.getTime() + 24 * 60 * 60 * 1000) }));
        }
      })();
    }
  }, [user]);

  // Update swipe limit for both web and mobile
  const updateSwipeLimit = () => {
    setSwipeLimit((prev) => prev - 1);
    if (!userKey) return;
    if (isWeb) {
      const swipeData = window.localStorage.getItem(`swipeLimitData_${userKey}`);
      let count = 1;
      let resetTime = swipeResetTime;
      if (swipeData) {
        const parsed = JSON.parse(swipeData);
        count = parsed.count + 1;
        resetTime = new Date(parsed.resetTime);
      }
      window.localStorage.setItem(`swipeLimitData_${userKey}`, JSON.stringify({ count, resetTime }));
    } else {
      const AsyncStorage = require('@react-native-async-storage/async-storage').default;
      (async () => {
        const swipeData = await AsyncStorage.getItem(`swipeLimitData_${userKey}`);
        let count = 1;
        let resetTime = swipeResetTime;
        if (swipeData) {
          const parsed = JSON.parse(swipeData);
          count = parsed.count + 1;
          resetTime = new Date(parsed.resetTime);
        }
        await AsyncStorage.setItem(`swipeLimitData_${userKey}`, JSON.stringify({ count, resetTime }));
      })();
    }
  };


  useEffect(() => {
    // API_BASE_URL imported at top
    if (!isSignedIn || !user) {
      console.log('🔍 User not authenticated, trying sample user...');
      // Try with sample user for development
      fetchJobs('sample_user_123');
      return;
    }
    
    const clerkId = user.id;
    const email =
      user.primaryEmailAddress?.emailAddress ||
      user.emailAddresses?.[0]?.emailAddress ||
      "";

    console.log('🔍 User authentication check:');
    console.log('  isSignedIn:', isSignedIn);
    console.log('  user:', user?.id);
    console.log('  clerkId:', clerkId);
    console.log('  email:', email);

    const checkAndCreateUserAndFetchJobs = async () => {
      try {
        // Try to GET recommendations (also validates user existence in backend flow)
        try {
          await api.getRecommendations(clerkId, 1);
          // User exists, fetch jobs
          await fetchJobs(clerkId);
          return;
        } catch (error: any) {
          console.log('🔍 Error details:', error.message);
          if (error.message.includes('404') || error.message.includes('not found')) {
            console.log('👤 User not found, creating new user...');
            // User not found, create them
            const payload = {
              clerk_id: clerkId,
              email,
              first_name: user.firstName || "",
              last_name: user.lastName || "",
              role: "job_seeker",
              skills: [],
              location: "",
              company_name: "",
            };
            
            console.log('📝 Creating user with payload:', payload);
            try {
              const createResult = await api.createUser(payload);
              console.log('✅ User creation result:', createResult);
              // User created, fetch jobs
              await fetchJobs(clerkId);
            } catch (createError: any) {
              console.error('❌ User creation failed:', createError);
              setError(`Failed to create user: ${createError.message}`);
            }
          } else {
            console.error('❌ Unexpected error:', error);
            setError("Error fetching user. Please try again.");
          }
        }
      } catch (err) {
        // Fallback for dev when Clerk is not signed in: try sample user
        try {
          await api.createSampleUser();
          await fetchJobs('sample_user_123');
          return;
        } catch {}
        setError("Could not reach backend. Ensure API URL is reachable.");
      }
    };
    checkAndCreateUserAndFetchJobs();
  }, [isSignedIn, user]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [applications, setApplications] = useState<any[]>([]);
  const [showOverlay, setShowOverlay] = useState(true);

  const [selectedLocation, setSelectedLocation] =
    useState<string>("All Locations"); // Default to All Locations
  const [showLocationModal, setShowLocationModal] = useState(false);
  const [allJobs, setAllJobs] = useState<Job[]>([]);
  const [userLocation, setUserLocation] = useState<string>("");
  const [isLocationLoading, setIsLocationLoading] = useState(false);
  const [isFetching, setIsFetching] = useState(false);

  // Periodically refresh recommendations so new backend results appear automatically
  // Only refresh if user is actively using the app and not currently fetching
  useEffect(() => {
    if (!user?.id || isFetching) return;
    
    // Only refresh every 5 minutes instead of 30 seconds to prevent constant refreshes
    const interval = setInterval(() => {
      if (!isFetching && jobs.length > 0) {
        console.log('🔄 Periodic refresh triggered with location:', selectedLocation);
        fetchJobs(user.id);
      }
    }, 300000); // every 5 minutes

    return () => clearInterval(interval);
  }, [user?.id, isFetching]);

  // Debounced effect for location changes - provides instant feedback
  useEffect(() => {
    if (!user?.id) return;
    
    const timeoutId = setTimeout(() => {
      if (!isFetching) {
        console.log('🔄 Location changed, fetching new jobs...');
        fetchJobs(user.id);
      }
    }, 500); // 500ms debounce

    return () => clearTimeout(timeoutId);
  }, [selectedLocation]);

  const locations = [
    "All Locations",
    "India",
    "USA",
  ];

  const overlayOpacity = useSharedValue(1);
  const leftArrowTranslateX = useSharedValue(0);
  const rightArrowTranslateX = useSharedValue(0);
  const leftArrowOpacity = useSharedValue(1);
  const rightArrowOpacity = useSharedValue(1);
  const textOpacity = useSharedValue(1);

  const leftTutorialOpacity = useSharedValue(0);
  const rightTutorialOpacity = useSharedValue(0);

  const leftScreenOpacity = useSharedValue(0);
  const rightScreenOpacity = useSharedValue(0);
  const leftScreenScale = useSharedValue(0.8);
  const rightScreenScale = useSharedValue(0.8);

  // Removed fallbackJobsData: only real jobs will be shown

  const [jobs, setJobs] = useState<Job[]>([]);
  const [swipedJobs, setSwipedJobs] = useState<{ job: Job; action: string }[]>(
    []
  );
  const [isAnimating, setIsAnimating] = useState(false);
  const { savedJobs, addJob, removeJob, isJobSaved } = useSavedJobs();

  // Location filtering is now done on the backend for better performance

  useEffect(() => {
    if (showOverlay) {
      overlayOpacity.value = 1;
      leftArrowTranslateX.value = 0;
      rightArrowTranslateX.value = 0;

      startOverlayAnimation();

      const timer = setTimeout(() => {
        hideOverlay();
      }, 3000);

      return () => clearTimeout(timer);
    }
  }, [showOverlay]);

  const startOverlayAnimation = () => {
    leftTutorialOpacity.value = withTiming(0.4, { duration: 300 });
    rightTutorialOpacity.value = withTiming(0.4, { duration: 300 });

    const animateArrows = () => {
      leftArrowTranslateX.value = withSequence(
        withTiming(-40, { duration: 600 }),
        withTiming(0, { duration: 600 })
      );
      rightArrowTranslateX.value = withSequence(
        withTiming(40, { duration: 600 }),
        withTiming(0, { duration: 600 })
      );
    };

    animateArrows();

    const intervalId = setInterval(animateArrows, 1200);

    setTimeout(() => {
      clearInterval(intervalId);
    }, 2500);
  };

  const hideOverlay = () => {
    leftTutorialOpacity.value = withTiming(0, { duration: 400 });
    rightTutorialOpacity.value = withTiming(0, { duration: 400 });
    overlayOpacity.value = withTiming(0, { duration: 400 }, () => {
      runOnJS(setShowOverlay)(false);
    });
  };

  const triggerHalfScreenAnimation = (direction: "left" | "right") => {
    if (direction === "left") {
      leftScreenOpacity.value = withSequence(
        withTiming(0.8, { duration: 200 }),
        withTiming(0, { duration: 300 })
      );
      leftScreenScale.value = withSequence(
        withTiming(1, { duration: 200 }),
        withTiming(0.8, { duration: 300 })
      );
    } else {
      rightScreenOpacity.value = withSequence(
        withTiming(0.8, { duration: 200 }),
        withTiming(0, { duration: 300 })
      );
      rightScreenScale.value = withSequence(
        withTiming(1, { duration: 200 }),
        withTiming(0.8, { duration: 300 })
      );
    }
  };


  // Fetch jobs from backend and map to UI format
  const fetchJobs = async (clerkId: string) => {
    try {
      if (isFetching) {
        console.log('⏳ Already fetching jobs, skipping...');
        return; // prevent overlapping requests
      }
      setIsFetching(true);
      if (jobs.length === 0) setIsLoading(true);
      setError(null);
      
      console.log('🔄 Fetching jobs for user:', clerkId);
      console.log('📍 Selected location:', selectedLocation);
      
      // Use the new API utility function
      const effectiveLocation = selectedLocation === 'All Locations' 
        ? 'All Locations' 
        : selectedLocation;
      
      const jobsData = await api.getRecommendations(clerkId, 20, effectiveLocation);
      // jobsData: [{ job: {...}, match_score: ... }, ...]
      const mappedJobs: Job[] = jobsData.map((item: any) => {
        const job = item.job ? item.job : item;
        // id
        const id = job.id || job._id || '';
        // title
        const title = job.title || 'Job Title Not Available';
        // company
        const company = job.company || job.company_name || job.employer_id || 'Unknown Company';
        // companySize
        const companySize = job.companySize || job.company_size || job.company_size_text || 'Company size not specified';
        // type
        const type = job.type || job.employment_type || 'Full-time';
        // experience
        const experience = job.experience || job.experience_required || job.experience_text || 'Experience not specified';
        // location
        let location = 'Location not specified';
        if (typeof job.location === 'string') {
          location = job.location;
        } else if (job.location && typeof job.location === 'object') {
          const { city, state, country, remote } = job.location;
          let locArr = [];
          if (city) locArr.push(city);
          if (state) locArr.push(state);
          if (country) locArr.push(country);
          location = locArr.join(' / ');
          if (remote) location += ' / Remote';
        }
        // salary
        let salary = 'Salary not specified';
        if (job.salary && typeof job.salary === 'object') {
          const sMin = typeof job.salary.min === 'number' ? job.salary.min : Number(job.salary.min);
          const sMax = typeof job.salary.max === 'number' ? job.salary.max : Number(job.salary.max);
          const sCur = job.salary.currency || '';
          if (!isNaN(sMin) && !isNaN(sMax) && sCur) {
            salary = `${sCur}${sMin} - ${sCur}${sMax}`;
          } else if (!isNaN(sMin) && sCur) {
            salary = `${sCur}${sMin}`;
          } else if (sCur) {
            salary = `${sCur}`;
          }
        } else if (typeof job.salary === 'string') {
          salary = job.salary;
        }
        // matchPercentage
        let matchPercentage = item.match_score || job.match_score || job.matchPercentage || 0;
        if (typeof matchPercentage === 'string') {
          matchPercentage = parseFloat(matchPercentage);
        }
        if (matchPercentage > 1 && matchPercentage <= 100) {
          // already percent
        } else if (matchPercentage > 0 && matchPercentage <= 1) {
          matchPercentage = Math.round(matchPercentage * 100);
        }
        // description
        const description = job.description || '';
        // requirements: combine requirements and responsibilities arrays, fallback to []
        let requirements: string[] = [];
        if (Array.isArray(job.requirements)) {
          requirements = requirements.concat(job.requirements);
        }
        if (Array.isArray(job.responsibilities)) {
          requirements = requirements.concat(job.responsibilities);
        }
        // benefits
        let benefits: string[] = [];
        if (Array.isArray(job.benefits)) {
          benefits = job.benefits;
        }
        // tags
        let tags: string[] = [];
        if (Array.isArray(job.tags)) {
          tags = job.tags;
        } else if (Array.isArray(job.skills_required)) {
          tags = job.skills_required;
        }
        // postedTime
        let postedTime = 'Recently posted';
        if (job.posted_at) {
          // Format as 'X days ago' if possible
          const postedDate = new Date(job.posted_at);
          const now = new Date();
          const diffMs = now.getTime() - postedDate.getTime();
          const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
          if (diffDays === 0) {
            postedTime = 'Today';
          } else if (diffDays === 1) {
            postedTime = '1 day ago';
          } else {
            postedTime = `${diffDays} days ago`;
          }
        } else if (job.postedTime) {
          postedTime = job.postedTime;
        }
        return {
          id,
          title,
          company,
          location,
          salary,
          matchPercentage,
          type,
          experience,
          companySize,
          description,
          requirements,
          benefits,
          tags,
          postedTime,
        };
      });
      try {
        console.log("Fetched jobs count:", mappedJobs.length);
        console.log("Fetched job titles:", mappedJobs.map(j => j.title));
      } catch {}
      setJobs(mappedJobs);
      setAllJobs(mappedJobs);
      // Backend already filtered jobs by location
    } catch (err) {
      setError("Failed to load job applications. Please check your internet connection or try again later.");
      setJobs([]);
      setAllJobs([]);
    } finally {
      setIsLoading(false);
      setIsFetching(false);
    }
  };

  const fetchLiveLocation = async () => {
    try {
      setIsLocationLoading(true);

      let { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== "granted") {
        Alert.alert(
          "Permission Denied",
          "Location permission is required to find jobs near you"
        );
        setIsLocationLoading(false);
        return;
      }

      const location = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });

      const { latitude, longitude } = location.coords;

      try {
        const reverseGeocodeResult = await Location.reverseGeocodeAsync({
          latitude,
          longitude,
        });

        if (reverseGeocodeResult && reverseGeocodeResult.length > 0) {
          const result = reverseGeocodeResult[0];
          const city = result.city || result.subregion || "Unknown City";
          const region = result.region || result.country || "";
          const locationString = region ? `${city}, ${region}` : city;

          setUserLocation(locationString);
          setSelectedLocation("Live Location");
          setShowLocationModal(false);
          // Show loading state - debounced effect will handle fetch
          setIsLoading(true);

          Alert.alert(
            "Location Found! 📍",
            `Jobs filtered for: ${locationString}`,
            [{ text: "Great!", style: "default" }]
          );
        } else {
          throw new Error("No location data returned");
        }
      } catch (geocodingError) {
        console.error("Geocoding error:", geocodingError);
        const locationString = `${latitude.toFixed(2)}, ${longitude.toFixed(
          2
        )}`;
        setUserLocation(locationString);
        setSelectedLocation("Live Location");
        setShowLocationModal(false);
        // Show loading state - debounced effect will handle fetch
        setIsLoading(true);

        Alert.alert("Location Found! 📍", `Jobs filtered for your location`, [
          { text: "Great!", style: "default" },
        ]);
      }
    } catch (error: any) {
      console.error("Location error:", error);
      let errorMessage = "Unable to get your location. ";

      if (error.code) {
        switch (error.code) {
          case "E_LOCATION_PERMISSION_DENIED":
            errorMessage += "Please enable location permissions in settings.";
            break;
          case "E_LOCATION_UNAVAILABLE":
            errorMessage += "Location services are unavailable.";
            break;
          case "E_LOCATION_TIMEOUT":
            errorMessage += "Location request timed out. Please try again.";
            break;
          default:
            errorMessage += "Please try again or select a location manually.";
            break;
        }
      }

      Alert.alert(
        "Location Error",
        "Unable to get your location. Please check your permissions and try again."
      );
    } finally {
      setIsLocationLoading(false);
    }
  };

  const handleLocationSelect = (location: string) => {
    setSelectedLocation(location);
    setShowLocationModal(false);
    
    // Show loading state for instant feedback
    setIsLoading(true);
    
    // The debounced useEffect will handle the actual fetch
  };

  // No need to fetchApplications on mount; jobs are fetched after user check/create

  const retryFetch = () => {
    if (user) {
      fetchJobs(user.id);
    }
  };

  const handleSwipeLeft = async (job: Job) => {
    if (isAnimating || swipeLimit <= 0) return;
    setIsAnimating(true);
    updateSwipeLimit();
    triggerHalfScreenAnimation("left");
    
    // Send swipe action to backend
    try {
      if (user?.id) {
        await api.handleSwipeAction(user.id, job.id, 'dislike', job);
      }
    } catch (error) {
      console.error('Failed to send swipe action to backend:', error);
    }
    
    setTimeout(() => {
      setJobs((prev) => prev.slice(1));
      setSwipedJobs((prev) => [...prev, { job, action: "rejected" }]);
      Alert.alert("Job Rejected", `You rejected ${job.title} at ${job.company}`, [
        { text: "OK", style: "default" },
      ]);
      setIsAnimating(false);
    }, 300);
  };
  const handleSwipeRight = async (job: Job) => {
    if (isAnimating || swipeLimit <= 0) return;
    setIsAnimating(true);
    updateSwipeLimit();
    triggerHalfScreenAnimation("right");
    
    // Send swipe action to backend
    try {
      if (user?.id) {
        await api.handleSwipeAction(user.id, job.id, 'like', job);
      }
    } catch (error) {
      console.error('Failed to send swipe action to backend:', error);
    }
    
    setTimeout(() => {
      setJobs((prev) => prev.slice(1));
      setSwipedJobs((prev) => [...prev, { job, action: "liked" }]);
      
      // Add job to accepted jobs when user swipes right
      console.log('Adding job to accepted jobs:', job.id, job.title);
      // Ensure job has all necessary properties before saving
      const jobToSave = {
        ...job,
        // Add any missing properties that might be needed
        id: job.id || `job-${Date.now()}`,
        title: job.title || 'Unknown Position',
        company: job.company || 'Unknown Company',
        // Add timestamp to help with sorting
        postedTime: job.postedTime || new Date().toISOString(),
        // Add a unique identifier to prevent duplicates
        uniqueId: `${job.id}-${Date.now()}`
      };
      addAcceptedJob(jobToSave);
      
      Alert.alert("Job Liked! 💚", `You liked ${job.title} at ${job.company}`, [
        { text: "Great!", style: "default" },
      ]);
      setIsAnimating(false);
    }, 300);
  };

  const handleBookmark = async (job: Job) => {
    if (isJobSaved(job.id)) {
      removeJob(job.id);
      Alert.alert(
        "Removed 📝",
        `${job.title} has been removed from your bookmarks.`
      );
    } else {
      addJob(job);
      
      // Send save action to backend
      try {
        if (user?.id) {
          await api.handleSwipeAction(user.id, job.id, 'save', job);
        }
      } catch (error) {
        console.error('Failed to send save action to backend:', error);
      }
      
      // Immediately remove from current recommendation queue
      setJobs((prev) => prev.filter((j) => j.id !== job.id));

      Alert.alert(
        "Bookmarked! 🔖",
        `${job.title} has been saved to your bookmarks.`
      );
    }
  };


  const overlayAnimatedStyle = useAnimatedStyle(() => ({
    opacity: overlayOpacity.value,
  }));

  const leftArrowAnimatedStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: leftArrowTranslateX.value }],
    opacity: leftArrowOpacity.value,
  }));

  const rightArrowAnimatedStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: rightArrowTranslateX.value }],
    opacity: rightArrowOpacity.value,
  }));

  const textAnimatedStyle = useAnimatedStyle(() => ({
    opacity: textOpacity.value,
  }));

  const leftTutorialAnimatedStyle = useAnimatedStyle(() => ({
    opacity: leftTutorialOpacity.value,
  }));

  const rightTutorialAnimatedStyle = useAnimatedStyle(() => ({
    opacity: rightTutorialOpacity.value,
  }));

  const leftScreenAnimatedStyle = useAnimatedStyle(() => ({
    opacity: leftScreenOpacity.value,
    transform: [{ scale: leftScreenScale.value }],
  }));

  const rightScreenAnimatedStyle = useAnimatedStyle(() => ({
    opacity: rightScreenOpacity.value,
    transform: [{ scale: rightScreenScale.value }],
  }));

  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <Text style={styles.loadingText}>Loading job opportunities...</Text>
        <View style={styles.loadingSpinner}>
          <Text style={styles.loadingEmoji}>🔄</Text>
        </View>
      </View>
    );
  }
  if (swipeLimit <= 0) {
    return (
      <View style={styles.loadingContainer}>
        <Text style={styles.loadingText}>Swipe limit reached!</Text>
        <Text style={styles.loadingText}>You can swipe again in 24 hours.</Text>
      </View>
    );
  }

  return (
    <GestureHandlerRootView style={styles.container}>
      <LinearGradient
        colors={["#0f172a", "#1e293b", "#334155"]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={{ flex: 1 }}
      >
        {/* Location Selector - Moved and positioned better */}
        <View style={styles.locationContainer}>
          <TouchableOpacity
            style={styles.locationSelector}
            onPress={() => setShowLocationModal(true)}
          >
            <Ionicons name="location-outline" size={14} color="#6b7280" />
            <Text style={styles.locationText} numberOfLines={1}>
              {selectedLocation}
            </Text>
            <Ionicons name="chevron-down" size={14} color="#6b7280" />
          </TouchableOpacity>
        </View>

        {/* REMOVED: Header with "Industrial Jobs" text - completely removed this section */}

        {/* MODIFIED: Card container with adjusted positioning - moved higher */}
        <View style={styles.cardContainer}>
          {jobs && jobs.length > 0 ? (
            <>
              {jobs.length > 1 && (
                <View style={[styles.card, styles.backgroundCard]}>
                  <JobCardContent job={jobs[1]} />
                </View>
              )}
              <JobSwipeCard
                key={jobs[0]?.id || "fallback-0"}
                job={jobs[0]}
                isTop={true}
                isSaved={isJobSaved(jobs[0]?.id || "")}
                onSwipeLeft={() => handleSwipeLeft(jobs[0])}
                onSwipeRight={() => handleSwipeRight(jobs[0])}
                onBookmark={() => handleBookmark(jobs[0])}
                onSwipeAnimation={triggerHalfScreenAnimation}
              />
            </>
          ) : (
            <View style={styles.noJobsContainer}>
              <Text style={styles.noJobsEmoji}>
                {selectedLocation === "All Locations" ? "🎉" : "📍"}
              </Text>
              <Text style={styles.noJobsTitle}>
                {selectedLocation === "All Locations"
                  ? "All done!"
                  : "No jobs found"}
              </Text>
              <Text style={styles.noJobsSubtitle}>
                {selectedLocation === "All Locations"
                  ? "You've reviewed all available positions. Check back later for new opportunities!"
                  : `No jobs available in ${selectedLocation} right now. Try selecting a different location.`}
              </Text>
            </View>
          )}
        </View>

        {/* Show info messages and reset button at bottom */}
        {(selectedLocation !== "All Locations" ||
          error ||
          swipedJobs.length > 0) && (
          <View style={styles.bottomInfo}>
            {selectedLocation !== "All Locations" && (
              <Text style={styles.jobCount}>
                {jobs.length} job{jobs.length !== 1 ? "s" : ""} in{" "}
                {selectedLocation}
              </Text>
            )}

            {error && (
              <View style={styles.errorContainer}>
                <Text style={styles.errorText}>{error}</Text>
                <TouchableOpacity
                  style={styles.retryButton}
                  onPress={retryFetch}
                >
                  <Ionicons name="refresh-outline" size={14} color="#3b82f6" />
                  <Text style={styles.retryButtonText}>Retry</Text>
                </TouchableOpacity>
              </View>
            )}

            {/* Reset button and debug list removed for production */}
          </View>
        )}

        {/* Location Modal */}
        {showLocationModal && (
          <View style={styles.modalOverlay}>
            <View style={styles.locationModal}>
              <View style={styles.modalHeader}>
                <Text style={styles.modalTitle}>Select Location</Text>
                <TouchableOpacity
                  style={styles.closeButton}
                  onPress={() => setShowLocationModal(false)}
                >
                  <Ionicons name="close" size={20} color="#6b7280" />
                </TouchableOpacity>
              </View>
              <ScrollView
                style={styles.locationList}
                showsVerticalScrollIndicator={false}
              >
                {locations.map((location, index) => (
                  <TouchableOpacity
                    key={index}
                    style={[
                      styles.locationItem,
                      selectedLocation === location &&
                        styles.selectedLocationItem,
                      location === "Live Location" &&
                        isLocationLoading &&
                        styles.loadingLocationItem,
                    ]}
                    onPress={() => handleLocationSelect(location)}
                    disabled={location === "Live Location" && isLocationLoading}
                  >
                    {location === "Live Location" && isLocationLoading ? (
                      <Text style={styles.loadingText}>📍</Text>
                    ) : (
                      <Ionicons
                        name={
                          location === "Live Location"
                            ? "locate-outline"
                            : location === "Remote"
                            ? "laptop-outline"
                            : "location-outline"
                        }
                        size={18}
                        color={
                          selectedLocation === location ? "#3b82f6" : "#6b7280"
                        }
                      />
                    )}
                    <Text
                      style={[
                        styles.locationItemText,
                        selectedLocation === location &&
                          styles.selectedLocationText,
                        location === "Live Location" &&
                          isLocationLoading &&
                          styles.loadingLocationText,
                      ]}
                    >
                      {location === "Live Location" &&
                      userLocation &&
                      selectedLocation === "Live Location"
                        ? `Live Location (${userLocation})`
                        : location === "Live Location" && isLocationLoading
                        ? "Getting your location..."
                        : location}
                    </Text>
                    {selectedLocation === location && (
                      <Ionicons name="checkmark" size={18} color="#3b82f6" />
                    )}
                  </TouchableOpacity>
                ))}
              </ScrollView>
            </View>
          </View>
        )}

        {/* Half-screen animation overlays */}
        <Animated.View
          style={[
            styles.halfScreenOverlay,
            styles.leftHalfScreen,
            leftScreenAnimatedStyle,
          ]}
        >
          <View style={styles.halfScreenContent}>
            <Ionicons name="close-circle" size={80} color="#fff" />
            <Text style={styles.halfScreenText}>REJECT</Text>
          </View>
        </Animated.View>

        <Animated.View
          style={[
            styles.halfScreenOverlay,
            styles.rightHalfScreen,
            rightScreenAnimatedStyle,
          ]}
        >
          <View style={styles.halfScreenContent}>
            <Ionicons name="checkmark-circle" size={80} color="#fff" />
            <Text style={styles.halfScreenText}>ACCEPT</Text>
          </View>
        </Animated.View>

        {/* Tutorial Overlay */}
        {showOverlay && (
          <TouchableOpacity
            activeOpacity={1}
            onPress={hideOverlay}
            style={[styles.tutorialOverlay, overlayAnimatedStyle]}
          >
            <Animated.View
              style={[
                styles.tutorialHalfScreen,
                styles.leftTutorialHalf,
                leftTutorialAnimatedStyle,
              ]}
            />
            <Animated.View
              style={[
                styles.tutorialHalfScreen,
                styles.rightTutorialHalf,
                rightTutorialAnimatedStyle,
              ]}
            />

            <View style={styles.tutorialContent}>
              <Animated.View
                style={[
                  styles.arrowContainer,
                  styles.leftArrow,
                  leftArrowAnimatedStyle,
                ]}
              >
                <Ionicons name="close-circle" size={60} color="#fff" />
                <Text style={styles.arrowLabel}>REJECT</Text>
              </Animated.View>

              <Animated.View
                style={[
                  styles.arrowContainer,
                  styles.rightArrow,
                  rightArrowAnimatedStyle,
                ]}
              >
                <Ionicons name="checkmark-circle" size={60} color="#fff" />
                <Text style={styles.arrowLabel}>ACCEPT</Text>
              </Animated.View>

              <Animated.View
                style={[styles.instructionContainer, textAnimatedStyle]}
              >
                <Text style={styles.instructionText}>
                  Swipe right to accept • Swipe left to reject
                </Text>
                <Text style={styles.instructionSubtext}>
                  Tap to dismiss tutorial
                </Text>
              </Animated.View>
            </View>
          </TouchableOpacity>
        )}
      </LinearGradient>
    </GestureHandlerRootView>
  );
}

export const JobSwipeCard: React.FC<JobSwipeCardAllProps> = ({
  job,
  onSwipeLeft,
  onSwipeRight,
  onBookmark,
  isTop,
  isSaved,
  onSwipeAnimation,
}) => {
  const translateX = useSharedValue(0);
  const rotate = useSharedValue(0);
  const scale = useSharedValue(1);

  const gestureHandler = useAnimatedGestureHandler({
    onStart: () => {
      scale.value = withSpring(0.98);
    },
    onActive: (event) => {
      translateX.value = event.translationX;
      rotate.value = interpolate(
        event.translationX,
        [-width, 0, width],
        [-8, 0, 8],
        Extrapolate.CLAMP
      );

      if (Math.abs(event.translationX) > SWIPE_THRESHOLD * 0.6) {
        if (event.translationX > 0) {
          runOnJS(onSwipeAnimation)("right");
        } else {
          runOnJS(onSwipeAnimation)("left");
        }
      }
    },
    onEnd: (event) => {
      scale.value = withSpring(1);

      if (event.translationX > SWIPE_THRESHOLD) {
        translateX.value = withTiming(
          width * 1.5,
          { duration: 300 },
          (finished) => {
            if (finished) {
              runOnJS(onSwipeRight)();
              translateX.value = 0;
              rotate.value = 0;
            }
          }
        );
        rotate.value = withTiming(8, { duration: 300 });
      } else if (event.translationX < -SWIPE_THRESHOLD) {
        translateX.value = withTiming(
          -width * 1.5,
          { duration: 300 },
          (finished) => {
            if (finished) {
              runOnJS(onSwipeLeft)();
              translateX.value = 0;
              rotate.value = 0;
            }
          }
        );
        rotate.value = withTiming(-8, { duration: 300 });
      } else {
        translateX.value = withSpring(0);
        rotate.value = withSpring(0);
      }
    },
  });

  const animatedStyle = useAnimatedStyle(() => {
    const opacity = interpolate(
      Math.abs(translateX.value),
      [0, SWIPE_THRESHOLD, width],
      [1, 0.9, 0],
      Extrapolate.CLAMP
    );

    return {
      transform: [
        { translateX: translateX.value },
        { rotate: `${rotate.value}deg` },
        { scale: scale.value },
      ],
      opacity,
    };
  });

  const likeOverlayStyle = useAnimatedStyle(() => {
    const opacity = interpolate(
      translateX.value,
      [0, SWIPE_THRESHOLD],
      [0, 1],
      Extrapolate.CLAMP
    );

    return { opacity };
  });

  const rejectOverlayStyle = useAnimatedStyle(() => {
    const opacity = interpolate(
      translateX.value,
      [-SWIPE_THRESHOLD, 0],
      [1, 0],
      Extrapolate.CLAMP
    );

    return { opacity };
  });

  return (
    <PanGestureHandler onGestureEvent={gestureHandler}>
      <Animated.View style={[styles.card, animatedStyle]}>
        <JobCardContent job={job} />

        <Animated.View style={[styles.likeOverlay, likeOverlayStyle]}>
          <View style={[styles.overlayContent, styles.likeOverlayContent]}>
            <Ionicons name="heart" size={24} color="#22c55e" />
            <Text style={[styles.overlayText, styles.likeOverlayText]}>
              LIKE
            </Text>
          </View>
        </Animated.View>

        <Animated.View style={[styles.rejectOverlay, rejectOverlayStyle]}>
          <View style={[styles.overlayContent, styles.rejectOverlayContent]}>
            <Ionicons name="close" size={24} color="#ef4444" />
            <Text style={[styles.overlayText, styles.rejectOverlayText]}>
              PASS
            </Text>
          </View>
        </Animated.View>

        <View style={styles.actions}>
          <TouchableOpacity
            style={[styles.actionButton, styles.rejectButton]}
            onPress={onSwipeLeft}
          >
            <Ionicons name="close" size={20} color="#ef4444" />
          </TouchableOpacity>

          <TouchableOpacity
            style={[
              styles.actionButton,
              styles.bookmarkButton,
              isSaved && styles.bookmarkButtonActive,
            ]}
            onPress={onBookmark}
          >
            <Ionicons
              name={isSaved ? "bookmark" : "bookmark-outline"}
              size={16}
              color={isSaved ? "#3b82f6" : "#6b7280"}
            />
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.actionButton, styles.likeButton]}
            onPress={onSwipeRight}
          >
            <Ionicons name="heart" size={20} color="#22c55e" />
          </TouchableOpacity>
        </View>
      </Animated.View>
    </PanGestureHandler>
  );
}

function JobCardContent({ job }: { job: Job }) {
  if (!job) {
    return (
      <View style={styles.cardContent}>
        <Text style={styles.errorText}>Job data unavailable</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.cardContent} showsVerticalScrollIndicator={false}>
      <View style={styles.cardHeader}>
        <View style={styles.logo}>
          <Text style={styles.logoText}>{job.company?.charAt(0) || "N"}</Text>
        </View>
        <View style={styles.companyInfo}>
          <Text style={styles.company}>{job.company || "Unknown Company"}</Text>
          <Text style={styles.companySizeText}>
            {job.companySize || "Company size not specified"}
          </Text>
          <Text style={styles.experienceText}>
            {job.type || "Full-time"} •{" "}
            {job.experience || "Experience not specified"}
          </Text>
        </View>
        <View style={styles.matchBadge}>
          <Text style={styles.matchText}>{job.matchPercentage || 0}%</Text>
        </View>
      </View>

      <Text style={styles.title}>{job.title || "Job Title Not Available"}</Text>

      {/* Job Details Row */}
      <View style={styles.jobDetails}>
        <View style={styles.jobDetailItem}>
          <Ionicons name="location-outline" size={14} color="#6b7280" />
          <Text style={styles.jobDetailText}>
            {job.location || "Location not specified"}
          </Text>
        </View>
        <View style={styles.jobDetailItem}>
          <Ionicons name="cash-outline" size={14} color="#6b7280" />
          <Text style={styles.jobDetailText}>
            {job.salary || "Salary not specified"}
          </Text>
        </View>
        <View style={styles.jobDetailItem}>
          <Ionicons name="time-outline" size={14} color="#6b7280" />
          <Text style={styles.jobDetailText}>
            {job.postedTime || "Recently posted"}
          </Text>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>About the Role</Text>
        <Text style={styles.description}>
          {job.description || "Job description not available at this time."}
        </Text>
      </View>

      {job.requirements && job.requirements.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Requirements</Text>
          {job.requirements.map((req, index) => (
            <View key={index} style={styles.requirementItem}>
              <Text style={styles.requirementBullet}>•</Text>
              <Text style={styles.requirementText}>{req}</Text>
            </View>
          ))}
        </View>
      )}

      {job.tags && job.tags.length > 0 && (
        <View style={styles.tags}>
          {job.tags.map((tag, index) => (
            <View key={index} style={styles.tag}>
              <Text style={styles.tagText}>{tag}</Text>
            </View>
          ))}
        </View>
      )}

      <View style={{ height: 70 }} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  // Location selector positioned at top
  locationContainer: {
    position: "absolute",
    top: 45,
    left: 20,
    zIndex: 100,
  },
  locationSelector: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#fff",
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "#e5e7eb",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius: 3,
    elevation: 2,
    maxWidth: 140,
  },
  locationText: {
    fontSize: 11,
    color: "#4b5563",
    fontWeight: "500",
    marginHorizontal: 4,
    flex: 1,
  },
  // Moved info to bottom, more space for cards
  bottomInfo: {
    position: "absolute",
    bottom: 20,
    left: 20,
    right: 20,
    alignItems: "center",
    zIndex: 50,
  },
  jobCount: {
    fontSize: 11,
    color: "#cbd5e1",
    fontWeight: "500",
    marginBottom: 4,
  },
  resetButton: {
    backgroundColor: "#3b82f6",
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginTop: 4,
  },
  resetButtonText: {
    color: "#fff",
    fontWeight: "600",
    fontSize: 12,
  },
  // MODIFIED: Card container moved higher with adjusted top padding
  cardContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 16,
    paddingTop: 30, // Reduced from original padding since header is removed
    paddingBottom: 90, // Space for bottom info
  },
  noJobsContainer: {
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 32,
  },
  noJobsEmoji: {
    fontSize: 48,
    marginBottom: 12,
  },
  noJobsTitle: {
    fontSize: 20,
    fontWeight: "700",
    color: "#1f2937",
    marginBottom: 6,
  },
  noJobsSubtitle: {
    fontSize: 14,
    color: "#6b7280",
    textAlign: "center",
    marginBottom: 24,
  },
  primaryButton: {
    backgroundColor: "#3b82f6",
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 20,
  },
  primaryButtonText: {
    color: "#fff",
    fontWeight: "600",
    fontSize: 14,
  },
  // Card size optimized for better content display
  card: {
    width: width * 0.88,
    height: height * 0.75,
    maxWidth: 380,
    backgroundColor: "#ffffff",
    borderRadius: 24,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.25,
    shadowRadius: 25,
    elevation: 15,
    position: "absolute",
    overflow: "hidden",
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.1)",
  },
  backgroundCard: {
    transform: [{ scale: 0.94 }],
    opacity: 0.3,
    zIndex: 0,
  },
  // Optimized content padding
  cardContent: {
    flex: 1,
    padding: 18,
  },
  likeOverlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 20,
  },
  rejectOverlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 20,
  },
  overlayContent: {
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 16,
    borderWidth: 2,
    alignItems: "center",
    gap: 6,
  },
  likeOverlayContent: {
    backgroundColor: "rgba(34, 197, 94, 0.1)",
    borderColor: "#22c55e",
  },
  rejectOverlayContent: {
    backgroundColor: "rgba(239, 68, 68, 0.1)",
    borderColor: "#ef4444",
  },
  overlayText: {
    fontSize: 16,
    fontWeight: "800",
    letterSpacing: 1.5,
  },
  likeOverlayText: {
    color: "#22c55e",
  },
  rejectOverlayText: {
    color: "#ef4444",
  },
  // Reduced font sizes and spacing
  cardHeader: {
    flexDirection: "row",
    alignItems: "flex-start",
    marginBottom: 14,
  },
  logo: {
    width: 48,
    height: 48,
    borderRadius: 12,
    backgroundColor: "#dbeafe",
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12,
  },
  logoText: {
    fontWeight: "800",
    fontSize: 18,
    color: "#1e3a8a",
  },
  companyInfo: {
    flex: 1,
  },
  company: {
    fontWeight: "600",
    fontSize: 14,
    color: "#1f2937",
    marginBottom: 2,
  },
  companySizeText: {
    fontSize: 11,
    color: "#6b7280",
    fontWeight: "500",
    marginBottom: 2,
  },
  experienceText: {
    fontSize: 11,
    color: "#6b7280",
    fontWeight: "500",
  },
  matchBadge: {
    backgroundColor: "#ecfdf5",
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#22c55e",
  },
  matchText: {
    fontSize: 12,
    fontWeight: "700",
    color: "#22c55e",
  },
  title: {
    fontSize: 20,
    fontWeight: "800",
    marginBottom: 12,
    color: "#1f2937",
    lineHeight: 26,
  },
  // Job details row styles
  jobDetails: {
    marginBottom: 16,
    gap: 8,
  },
  jobDetailItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  jobDetailText: {
    fontSize: 13,
    color: "#6b7280",
    fontWeight: "500",
  },
  section: {
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: "700",
    color: "#1f2937",
    marginBottom: 8,
  },
  description: {
    fontSize: 13,
    color: "#4b5563",
    lineHeight: 19,
  },
  requirementItem: {
    flexDirection: "row",
    alignItems: "flex-start",
    marginBottom: 6,
  },
  requirementBullet: {
    fontSize: 14,
    color: "#3b82f6",
    marginRight: 8,
    marginTop: 1,
  },
  requirementText: {
    fontSize: 12,
    color: "#4b5563",
    lineHeight: 18,
    flex: 1,
  },
  tags: {
    flexDirection: "row",
    flexWrap: "wrap",
    marginBottom: 12,
  },
  tag: {
    backgroundColor: "#e0e7ff",
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 12,
    marginRight: 6,
    marginBottom: 6,
    borderWidth: 1,
    borderColor: "#c7d2fe",
  },
  tagText: {
    fontSize: 10,
    color: "#3730a3",
    fontWeight: "600",
  },
  // Reduced action button sizes
  actions: {
    flexDirection: "row",
    justifyContent: "space-around",
    alignItems: "center",
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: "rgba(255, 255, 255, 0.95)",
    paddingVertical: 14,
    paddingHorizontal: 20,
    borderTopWidth: 1,
    borderTopColor: "#f3f4f6",
  },
  actionButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.12,
    shadowRadius: 6,
    elevation: 4,
  },
  rejectButton: {
    backgroundColor: "#fee2e2",
    borderWidth: 1.5,
    borderColor: "#fecaca",
  },
  bookmarkButton: {
    backgroundColor: "#f3f4f6",
    borderWidth: 1.5,
    borderColor: "#e5e7eb",
  },
  bookmarkButtonActive: {
    backgroundColor: "#dbeafe",
    borderColor: "#93c5fd",
  },
  likeButton: {
    backgroundColor: "#dcfce7",
    borderWidth: 1.5,
    borderColor: "#bbf7d0",
  },
  // Loading and error states
  loadingContainer: {
    flex: 1,
    backgroundColor: "#0f172a",
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 32,
  },
  loadingText: {
    fontSize: 16,
    color: "#cbd5e1",
    marginBottom: 12,
    textAlign: "center",
  },
  loadingSpinner: {
    padding: 12,
  },
  loadingEmoji: {
    fontSize: 28,
  },
  errorContainer: {
    backgroundColor: "#fef2f2",
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 10,
    marginVertical: 4,
    borderWidth: 1,
    borderColor: "#fecaca",
    alignItems: "center",
  },
  errorText: {
    fontSize: 11,
    color: "#dc2626",
    textAlign: "center",
    marginBottom: 6,
  },
  retryButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 4,
    backgroundColor: "#fff",
    borderRadius: 6,
    borderWidth: 1,
    borderColor: "#3b82f6",
  },
  retryButtonText: {
    color: "#3b82f6",
    fontSize: 10,
    fontWeight: "600",
  },
  // Modal styles
  modalOverlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(0, 0, 0, 0.5)",
    justifyContent: "center",
    alignItems: "center",
    zIndex: 2000,
  },
  locationModal: {
    backgroundColor: "#fff",
    borderRadius: 16,
    width: width * 0.85,
    maxHeight: height * 0.6,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.25,
    shadowRadius: 20,
    elevation: 15,
  },
  modalHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 18,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: "#f3f4f6",
  },
  modalTitle: {
    fontSize: 16,
    fontWeight: "600",
    color: "#1f2937",
  },
  closeButton: {
    padding: 4,
  },
  locationList: {
    maxHeight: height * 0.4,
  },
  locationItem: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 18,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: "#f9fafb",
  },
  selectedLocationItem: {
    backgroundColor: "#f0f9ff",
  },
  locationItemText: {
    fontSize: 14,
    color: "#4b5563",
    marginLeft: 10,
    flex: 1,
    fontWeight: "500",
  },
  selectedLocationText: {
    color: "#3b82f6",
    fontWeight: "600",
  },
  loadingLocationItem: {
    opacity: 0.6,
  },
  loadingLocationText: {
    fontStyle: "italic",
    color: "#9ca3af",
  },
  // Half-screen animation styles
  halfScreenOverlay: {
    position: "absolute",
    top: 0,
    bottom: 0,
    justifyContent: "center",
    alignItems: "center",
    zIndex: 999,
    pointerEvents: "none",
  },
  leftHalfScreen: {
    left: 0,
    width: width / 2,
    backgroundColor: "#ef4444",
  },
  rightHalfScreen: {
    right: 0,
    width: width / 2,
    backgroundColor: "#22c55e",
  },
  halfScreenContent: {
    alignItems: "center",
    justifyContent: "center",
  },
  halfScreenText: {
    color: "#fff",
    fontSize: 22,
    fontWeight: "900",
    marginTop: 12,
    letterSpacing: 2,
    textShadowColor: "rgba(0, 0, 0, 0.3)",
    textShadowOffset: { width: 2, height: 2 },
    textShadowRadius: 4,
  },
  // Tutorial Overlay Styles
  tutorialOverlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(0, 0, 0, 0.75)",
    justifyContent: "center",
    alignItems: "center",
    zIndex: 1000,
  },
  tutorialContent: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 30,
    width: "100%",
    height: "100%",
  },
  tutorialHalfScreen: {
    position: "absolute",
    top: 0,
    bottom: 0,
    width: width / 2,
    zIndex: 1,
  },
  leftTutorialHalf: {
    left: 0,
    backgroundColor: "#ef4444",
  },
  rightTutorialHalf: {
    right: 0,
    backgroundColor: "#22c55e",
  },
  arrowContainer: {
    position: "absolute",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 2,
  },
  leftArrow: {
    left: width * 0.15,
    top: "42%",
  },
  rightArrow: {
    right: width * 0.15,
    top: "42%",
  },
  arrowLabel: {
    color: "#fff",
    fontSize: 14,
    fontWeight: "900",
    marginTop: 8,
    letterSpacing: 2,
    textShadowColor: "rgba(0, 0, 0, 0.5)",
    textShadowOffset: { width: 2, height: 2 },
    textShadowRadius: 4,
  },
  instructionContainer: {
    position: "absolute",
    bottom: height * 0.25,
    alignItems: "center",
    width: "100%",
    paddingHorizontal: 20,
    zIndex: 2,
  },
  instructionText: {
    color: "#fff",
    fontSize: 15,
    fontWeight: "700",
    textAlign: "center",
    letterSpacing: 0.6,
    textShadowColor: "rgba(0, 0, 0, 0.5)",
    textShadowOffset: { width: 1, height: 1 },
    textShadowRadius: 3,
  },
  instructionSubtext: {
    color: "rgba(255, 255, 255, 0.8)",
    fontSize: 12,
    fontWeight: "500",
    textAlign: "center",
    marginTop: 6,
    letterSpacing: 0.4,
    textShadowColor: "rgba(0, 0, 0, 0.5)",
    textShadowOffset: { width: 1, height: 1 },
    textShadowRadius: 3,
  },
});
