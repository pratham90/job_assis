import { useAuth } from "@clerk/clerk-expo";
import { Ionicons } from "@expo/vector-icons";
import React from "react";
import { useSavedJobs } from '../contexts/SavedJobsContext';
import {
  Alert,
  Dimensions,
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
  RefreshControl,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

export interface SalaryRange {
  min: number;
  max: number;
  currency: string;
  is_public: boolean;
}

export interface Location {
  city: string;
  state?: string;
  country: string;
  remote: boolean;
}

export interface Job {
  _id: string;
  title: string;
  description: string;
  requirements: string[];
  responsibilities: string[];
  employment_type: "full_time" | "part_time" | "contract" | "internship";
  salary: SalaryRange;
  location: Location;
  skills_required: string[];
  benefits: string[];
  is_active: boolean;
  employer_id: string;
  posted_at: string;
  expires_at: string;
  // Additional properties for display
  company?: string;
  matchPercentage?: number;
  tags?: string[];
  companyDescription?: string;
  type?: string;
  postedTime?: string;
  hrContact?: {
    name: string;
    position: string;
    email: string;
    phone: string;
  };
}

const { width } = Dimensions.get("window");


const SavedJobs = () => {
  const { savedJobs, removeJob, refreshSavedJobs } = useSavedJobs();
  const [selectedJob, setSelectedJob] = React.useState<Job | null>(null);
  const [showJobModal, setShowJobModal] = React.useState(false);
  const loading = false;

  const handleJobPress = (job: Job) => {
    setSelectedJob(job);
    setShowJobModal(true);
  };

  const [refreshing, setRefreshing] = React.useState(false);
  const onRefresh = async () => {
    setRefreshing(true);
    await refreshSavedJobs();
    setRefreshing(false);
  };

  const handleUnsaveJob = (jobId: string) => {
    Alert.alert(
      "Remove Job",
      "Are you sure you want to remove this job from your saved list?",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Remove",
          style: "destructive",
          onPress: () => {
            removeJob(jobId);
          },
        },
      ]
    );
  };

  const handleApply = (job: Job) => {
    Alert.alert("Apply for Job", `Ready to apply for ${job.title}?`, [
      { text: "Cancel", style: "cancel" },
      {
        text: "Apply",
        onPress: () => {
          Alert.alert("Success!", "Your application has been submitted!");
          setShowJobModal(false);
        },
      },
    ]);
  };

  const handleContactHR = (hrContact: Job['hrContact']) => {
    if (!hrContact) return;
    Alert.alert(
      "Contact HR",
      `Contact ${hrContact.name}?`,
      [
        { text: "Cancel", style: "cancel" },
        { text: "Call", onPress: () => Alert.alert("Calling...", `${hrContact.phone}`) },
        { text: "Email", onPress: () => Alert.alert("Opening email...", `${hrContact.email}`) },
      ]
    );
  };

  const formatSalary = (salary: SalaryRange) => {
    return `$${salary.min/1000}k - $${salary.max/1000}k`;
  };

  const formatLocation = (location: Location) => {
    if (location.remote) return "Remote";
    return location.state ? `${location.city}, ${location.state}` : location.city;
  };

  const renderJobCard = (job: Job) => (
    <TouchableOpacity
      key={job._id}
      style={styles.jobCard}
      onPress={() => handleJobPress(job)}
      activeOpacity={0.7}
    >
      <View style={styles.cardHeader}>
        <View style={styles.logo}>
          <Text style={styles.logoText}>{job.company?.charAt(0) || 'J'}</Text>
        </View>
        <View style={styles.jobInfo}>
          <Text style={styles.jobTitle}>{job.title}</Text>
          <Text style={styles.company}>{job.company || 'Company'}</Text>
          <View style={styles.jobMeta}>
            <View style={styles.metaItem}>
              <Ionicons name="location-outline" size={14} color="#6b7280" />
              <Text style={styles.metaText}>{formatLocation(job.location)}</Text>
            </View>
            <View style={styles.metaItem}>
              <Ionicons name="cash-outline" size={14} color="#6b7280" />
              <Text style={styles.metaText}>{formatSalary(job.salary)}</Text>
            </View>
          </View>
        </View>
        <View style={styles.cardActions}>
          <View style={styles.matchBadge}>
            <Text style={styles.matchText}>{job.matchPercentage || 0}%</Text>
          </View>
          <TouchableOpacity
            style={styles.unsaveButton}
            onPress={() => handleUnsaveJob(job._id)}
          >
            <Ionicons name="bookmark" size={20} color="#ef4444" />
          </TouchableOpacity>
        </View>
      </View>
      
      <Text style={styles.jobDescription} numberOfLines={2}>
        {job.description}
      </Text>
      
      <View style={styles.tags}>
        {(job.tags || job.skills_required).slice(0, 3).map((tag, index) => (
          <View key={index} style={styles.tag}>
            <Text style={styles.tagText}>{tag}</Text>
          </View>
        ))}
        {(job.tags || job.skills_required).length > 3 && (
          <Text style={styles.moreTagsText}>+{(job.tags || job.skills_required).length - 3} more</Text>
        )}
      </View>
    </TouchableOpacity>
  );

  const renderJobModal = () => (
    <Modal
      visible={showJobModal}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={() => setShowJobModal(false)}
    >
      <SafeAreaView style={styles.modalContainer}>
        <View style={styles.modalHeader}>
          <TouchableOpacity
            style={styles.closeButton}
            onPress={() => setShowJobModal(false)}
          >
            <Ionicons name="close" size={24} color="#374151" />
          </TouchableOpacity>
          <Text style={styles.modalTitle}>Job Details</Text>
          <View style={styles.placeholder} />
        </View>

        {selectedJob && (
          <ScrollView style={styles.modalContent} showsVerticalScrollIndicator={false}>
            {/* Job Header */}
            <View style={styles.jobHeader}>
              <View style={styles.jobHeaderInfo}>
                <Text style={styles.modalJobTitle}>{selectedJob.title}</Text>
                <Text style={styles.modalCompany}>{selectedJob.company}</Text>
                <View style={styles.jobDetails}>
                  <View style={styles.detailItem}>
                    <Ionicons name="location-outline" size={16} color="#6b7280" />
                    <Text style={styles.detailText}>{formatLocation(selectedJob.location)}</Text>
                  </View>
                  <View style={styles.detailItem}>
                    <Ionicons name="cash-outline" size={16} color="#6b7280" />
                    <Text style={styles.detailText}>{formatSalary(selectedJob.salary)}</Text>
                  </View>
                  <View style={styles.detailItem}>
                    <Ionicons name="time-outline" size={16} color="#6b7280" />
                    <Text style={styles.detailText}>{selectedJob.postedTime || 'Recently'}</Text>
                  </View>
                  <View style={styles.detailItem}>
                    <Ionicons name="briefcase-outline" size={16} color="#6b7280" />
                    <Text style={styles.detailText}>{selectedJob.type || selectedJob.employment_type}</Text>
                  </View>
                </View>
              </View>
              <View style={styles.matchBadgeLarge}>
                <Text style={styles.matchTextLarge}>{selectedJob.matchPercentage || 0}% match</Text>
              </View>
            </View>

            {/* Company Description */}
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>About Company</Text>
              <Text style={styles.sectionContent}>{selectedJob.companyDescription || 'No company description available.'}</Text>
            </View>

            {/* Job Description */}
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Job Description</Text>
              <Text style={styles.sectionContent}>{selectedJob.description}</Text>
            </View>

            {/* Requirements */}
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Requirements</Text>
              {selectedJob.requirements.map((req, index) => (
                <View key={index} style={styles.listItem}>
                  <Text style={styles.bulletPoint}>•</Text>
                  <Text style={styles.listText}>{req}</Text>
                </View>
              ))}
            </View>

            {/* Benefits */}
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Benefits</Text>
              {selectedJob.benefits.map((benefit, index) => (
                <View key={index} style={styles.listItem}>
                  <Text style={styles.bulletPoint}>•</Text>
                  <Text style={styles.listText}>{benefit}</Text>
                </View>
              ))}
            </View>

            {/* Skills */}
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Required Skills</Text>
              <View style={styles.skillTags}>
                {(selectedJob.tags || selectedJob.skills_required).map((tag, index) => (
                  <View key={index} style={styles.skillTag}>
                    <Text style={styles.skillTagText}>{tag}</Text>
                  </View>
                ))}
              </View>
            </View>

            {/* HR Contact */}
            {selectedJob.hrContact && (
              <View style={styles.section}>
                <Text style={styles.sectionTitle}>HR Contact</Text>
                <TouchableOpacity
                  style={styles.hrCard}
                  onPress={() => handleContactHR(selectedJob.hrContact)}
                >
                  <View style={styles.hrAvatar}>
                    <Text style={styles.hrAvatarText}>
                      {selectedJob.hrContact.name.split(' ').map(n => n[0]).join('')}
                    </Text>
                  </View>
                  <View style={styles.hrInfo}>
                    <Text style={styles.hrName}>{selectedJob.hrContact.name}</Text>
                    <Text style={styles.hrPosition}>{selectedJob.hrContact.position}</Text>
                    <Text style={styles.hrEmail}>{selectedJob.hrContact.email}</Text>
                    <Text style={styles.hrPhone}>{selectedJob.hrContact.phone}</Text>
                  </View>
                  <Ionicons name="chevron-forward" size={20} color="#9ca3af" />
                </TouchableOpacity>
              </View>
            )}

            <View style={styles.modalFooterSpacer} />
          </ScrollView>
        )}

        {/* Fixed Apply Button */}
        {selectedJob && (
          <View style={styles.modalFooter}>
            <TouchableOpacity
              style={styles.applyButton}
              onPress={() => handleApply(selectedJob)}
            >
              <Text style={styles.applyButtonText}>Apply Now</Text>
            </TouchableOpacity>
          </View>
        )}
      </SafeAreaView>
    </Modal>
  );

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <View style={styles.headerBadge}>
          <Text style={styles.headerBadgeText}>{savedJobs.length}</Text>
        </View>
      </View>

      {loading ? (
        <View style={styles.emptyState}>
          <View style={styles.loadingSpinner}>
            <Text style={styles.loadingEmoji}>🔄</Text>
          </View>
          <Text style={styles.emptyTitle}>Loading your saved jobs...</Text>
        </View>
      ) : savedJobs.length === 0 ? (
        <View style={styles.emptyState}>
          <View style={styles.emptyIcon}>
            <Text style={styles.emptyEmoji}>🔖</Text>
          </View>
          <Text style={styles.emptyTitle}>No Saved Jobs Yet</Text>
          <Text style={styles.emptyDescription}>
            Jobs you bookmark will appear here for easy access. Start exploring and save jobs that interest you!
          </Text>
        </View>
      ) : (
        <ScrollView
          style={styles.jobsList}
          showsVerticalScrollIndicator={false}
          contentContainerStyle={styles.jobsListContent}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
            />
          }
        >
          {savedJobs.map(job => (
            <React.Fragment key={job.id}>
              {renderJobCard(job)}
            </React.Fragment>
          ))}
        </ScrollView>
      )}

      {renderJobModal()}
    </SafeAreaView>
  );
};

export default SavedJobs;

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0f172a",
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "flex-end",
    paddingHorizontal: 20,
    paddingTop: 10,
    paddingBottom: 10,
  },

  headerBadge: {
    backgroundColor: "#3b82f6",
    borderRadius: 12,
    paddingHorizontal: 8,
    paddingVertical: 4,
    minWidth: 24,
    alignItems: "center",
  },
  headerBadgeText: {
    color: "#fff",
    fontSize: 11,
    fontWeight: "600",
  },
  emptyState: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 40,
  },
  emptyIcon: {
    marginBottom: 16,
  },
  emptyEmoji: {
    fontSize: 64,
    opacity: 0.7,
  },
  loadingSpinner: {
    marginBottom: 16,
    transform: [{ rotate: '0deg' }], // Will be animated in real app
  },
  loadingEmoji: {
    fontSize: 32,
    opacity: 0.8,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: "700",
    color: "#ffffff",
    marginBottom: 8,
    textAlign: "center",
    textShadowColor: 'rgba(0, 0, 0, 0.2)',
    textShadowOffset: { width: 1, height: 1 },
    textShadowRadius: 2,
  },
  emptyDescription: {
    fontSize: 14,
    color: "#cbd5e1", // Light slate for better readability
    textAlign: "center",
    lineHeight: 22,
    opacity: 0.9,
  },
  jobsList: {
    flex: 1,
  },
  jobsListContent: {
    padding: 16,
    paddingTop: 8,
  },
  jobCard: {
    backgroundColor: "#ffffff",
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    marginHorizontal: 2,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  cardHeader: {
    flexDirection: "row",
    alignItems: "flex-start",
    marginBottom: 14,
  },
  logo: {
    width: 50,
    height: 50,
    borderRadius: 14,
    backgroundColor: "#dbeafe",
    alignItems: "center",
    justifyContent: "center",
    marginRight: 14,
    shadowColor: "#3b82f6",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  logoText: {
    fontWeight: "800",
    fontSize: 18,
    color: "#1e3a8a",
  },
  jobInfo: {
    flex: 1,
  },
  jobTitle: {
    fontSize: 17,
    fontWeight: "700",
    color: "#1f2937",
    marginBottom: 4,
    lineHeight: 22,
  },
  company: {
    fontSize: 14,
    color: "#6b7280",
    fontWeight: "500",
    marginBottom: 10,
  },
  jobMeta: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 4,
  },
  metaItem: {
    flexDirection: "row",
    alignItems: "center",
    marginRight: 16,
    marginBottom: 4,
  },
  metaText: {
    fontSize: 12,
    color: "#6b7280",
    fontWeight: "500",
    marginLeft: 4,
  },
  cardActions: {
    alignItems: "flex-end",
    gap: 8,
  },
  matchBadge: {
    backgroundColor: "#ecfdf5",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#22c55e",
  },
  matchText: {
    fontSize: 11,
    fontWeight: "700",
    color: "#22c55e",
  },
  unsaveButton: {
    padding: 6,
    borderRadius: 8,
    backgroundColor: "#fef2f2",
  },
  jobDescription: {
    fontSize: 14,
    color: "#4b5563",
    lineHeight: 20,
    marginBottom: 14,
  },
  tags: {
    flexDirection: "row",
    flexWrap: "wrap",
    alignItems: "center",
  },
  tag: {
    backgroundColor: "#e0e7ff",
    paddingVertical: 4,
    paddingHorizontal: 10,
    borderRadius: 12,
    marginRight: 6,
    marginBottom: 4,
    borderWidth: 1,
    borderColor: "#c7d2fe",
  },
  tagText: {
    fontSize: 11,
    color: "#3730a3",
    fontWeight: "600",
  },
  moreTagsText: {
    fontSize: 11,
    color: "#6b7280",
    fontStyle: "italic",
    fontWeight: "500",
  },
  
  // Modal Styles (keeping white for readability)
  modalContainer: {
    flex: 1,
    backgroundColor: "#fff",
  },
  modalHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: "#e5e7eb",
    backgroundColor: "#fff",
  },
  closeButton: {
    padding: 4,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: "600",
    color: "#1f2937",
  },
  placeholder: {
    width: 32,
  },
  modalContent: {
    flex: 1,
    paddingHorizontal: 20,
  },
  jobHeader: {
    paddingVertical: 20,
    borderBottomWidth: 1,
    borderBottomColor: "#e5e7eb",
    marginBottom: 20,
  },
  jobHeaderInfo: {
    marginBottom: 16,
  },
  modalJobTitle: {
    fontSize: 24,
    fontWeight: "700",
    color: "#1f2937",
    marginBottom: 4,
  },
  modalCompany: {
    fontSize: 16,
    color: "#6b7280",
    marginBottom: 16,
  },
  jobDetails: {
    flexDirection: "row",
    flexWrap: "wrap",
  },
  detailItem: {
    flexDirection: "row",
    alignItems: "center",
    marginRight: 20,
    marginBottom: 8,
  },
  detailText: {
    fontSize: 14,
    color: "#4b5563",
    marginLeft: 6,
  },
  matchBadgeLarge: {
    backgroundColor: "#ecfdf5",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#22c55e",
    alignSelf: "flex-start",
  },
  matchTextLarge: {
    fontSize: 14,
    fontWeight: "600",
    color: "#22c55e",
  },
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: "600",
    color: "#1f2937",
    marginBottom: 12,
  },
  sectionContent: {
    fontSize: 14,
    color: "#4b5563",
    lineHeight: 22,
  },
  listItem: {
    flexDirection: "row",
    alignItems: "flex-start",
    marginBottom: 8,
  },
  bulletPoint: {
    fontSize: 14,
    color: "#3b82f6",
    marginRight: 8,
    marginTop: 2,
  },
  listText: {
    fontSize: 14,
    color: "#4b5563",
    flex: 1,
    lineHeight: 20,
  },
  skillTags: {
    flexDirection: "row",
    flexWrap: "wrap",
  },
  skillTag: {
    backgroundColor: "#dbeafe",
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 16,
    marginRight: 8,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: "#3b82f6",
  },
  skillTagText: {
    fontSize: 12,
    color: "#1e40af",
    fontWeight: "500",
  },
  hrCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#f8fafc",
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#e5e7eb",
  },
  hrAvatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: "#3b82f6",
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12,
  },
  hrAvatarText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "600",
  },
  hrInfo: {
    flex: 1,
  },
  hrName: {
    fontSize: 16,
    fontWeight: "600",
    color: "#1f2937",
    marginBottom: 2,
  },
  hrPosition: {
    fontSize: 14,
    color: "#6b7280",
    marginBottom: 4,
  },
  hrEmail: {
    fontSize: 12,
    color: "#3b82f6",
    marginBottom: 2,
  },
  hrPhone: {
    fontSize: 12,
    color: "#6b7280",
  },
  modalFooterSpacer: {
    height: 80,
  },
  modalFooter: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: "#fff",
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 16,
    borderTopWidth: 1,
    borderTopColor: "#e5e7eb",
  },
  applyButton: {
    backgroundColor: "#3b82f6",
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: "center",
    shadowColor: "#3b82f6",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 4,
  },
  applyButtonText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "600",
  },
});