from typing import List, Tuple
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from app.models.job import JobPosting
from app.models.user import UserProfile
from app.models.swipe import UserSwipe

class HybridRecommender:
    def __init__(self, embedder):
        self.embedder = embedder
    
    async def recommend(self, user: UserProfile, jobs: List[JobPosting], swipes: List[UserSwipe]) -> List[Tuple[JobPosting, float]]:
        """Enhanced recommendation with skill-based matching"""
        # 1. Content-based filtering
        user_embed = await self._embed_user(user)
        job_embeds = await self._embed_jobs(jobs)
        content_scores = cosine_similarity([user_embed], job_embeds)[0]
        
        # 2. Collaborative filtering
        swipe_scores = self._calculate_swipe_scores(user.clerk_id, swipes, jobs)
        
        # 3. Skill-based matching
        skill_scores = self._calculate_skill_scores(user, jobs)
        
        # 4. Hybrid scoring with skill matching and priority boost
        results = []
        for idx, job in enumerate(jobs):
            # Base content and collaborative scores
            content_score = content_scores[idx]
            swipe_score = swipe_scores.get(job.id, 0)
            skill_score = skill_scores.get(job.id, 0)
            
            # Priority boost for jobs-lists (source priority)
            priority_boost = getattr(job, 'priority', 0.5)  # Default to 0.5 for scraped jobs
            
            # Calculate final score with skill matching emphasis
            base_score = (0.4 * content_score) + (0.3 * skill_score) + (0.3 * swipe_score)
            final_score = base_score + (priority_boost * 0.2)  # Add up to 20% boost for jobs-lists
            
            results.append((job, final_score))
        
        # Sort by score descending (highest scores first)
        rr = sorted(results, key=lambda x: -x[1])
        return rr
    
    async def _embed_user(self, user: UserProfile) -> np.ndarray:
        """Async user embedding with resume-derived context if available"""
        resume_text = ""
        try:
            if getattr(user, "resume", None) and isinstance(user.resume.parsed_data, dict):
                parsed = user.resume.parsed_data or {}
                sections = []
                for key in [
                    "summary", "objective", "skills", "experience", "projects",
                    "education", "certifications", "technologies"
                ]:
                    value = parsed.get(key)
                    if isinstance(value, list):
                        sections.append(" ".join([str(v) for v in value]))
                    elif isinstance(value, dict):
                        sections.append(" ".join([str(v) for v in value.values()]))
                    elif isinstance(value, str):
                        sections.append(value)
                resume_text = " ".join([s for s in sections if s])
        except Exception:
            resume_text = ""

        # Handle experience - check if it's a list of dicts or objects
        experience_titles = []
        for exp in (getattr(user, "experience", []) or []):
            if isinstance(exp, dict):
                if exp.get('title') or exp.get('position'):
                    experience_titles.append(exp.get('title') or exp.get('position'))
            else:
                if hasattr(exp, 'title') and exp.title:
                    experience_titles.append(exp.title)
        
        text = " ".join([
            " ".join(getattr(user, "skills", []) or []),
            " ".join(experience_titles),
            getattr(user, "location", "") or "",
            resume_text
        ])
        return await self.embedder.embed(text)
    
    async def _embed_jobs(self, jobs: List[JobPosting]) -> List[np.ndarray]:
        """Async batch job embeddings"""
        texts = [
            f"{job.title} {' '.join(job.skills_required)} {job.location.city}"
            for job in jobs
        ]
        return await self.embedder.embed(texts)  # Assumes your embedder supports batch
    
    def _calculate_swipe_scores(self, clerk_id: str, swipes, jobs: List[JobPosting]) -> dict:
        """Sync calculation (no I/O needed) - works with raw swipe data"""
        weights = {
            "like": 1.0,
            "super_like": 1.5,
            "dislike": -1.0,
            "save": 0.8
        }
        return {job.id: sum(
            weights.get(s.get('action', ''), 0)
            for s in swipes
            if s.get('user_id') == clerk_id and s.get('job_id') == job.id
        ) for job in jobs}
    
    def _calculate_skill_scores(self, user, jobs: List[JobPosting]) -> dict:
        """Calculate skill-based matching scores"""
        user_skills = getattr(user, 'skills', []) or []
        skill_scores = {}
        
        for job in jobs:
            job_skills = getattr(job, 'skills_required', []) or []
            score = self._calculate_skill_match_score(user_skills, job_skills)
            skill_scores[job.id] = score
        
        return skill_scores
    
    def _calculate_skill_match_score(self, user_skills: list, job_skills: list) -> float:
        """Calculate skill matching score between user and job"""
        if not user_skills or not job_skills:
            return 0.0
        
        # Convert to lowercase for case-insensitive matching
        user_skills_lower = [skill.lower().strip() for skill in user_skills]
        job_skills_lower = [skill.lower().strip() for skill in job_skills]
        
        # Calculate exact matches
        exact_matches = set(user_skills_lower) & set(job_skills_lower)
        
        # Calculate partial matches (skills that contain each other)
        partial_matches = 0
        for user_skill in user_skills_lower:
            for job_skill in job_skills_lower:
                if user_skill in job_skill or job_skill in user_skill:
                    partial_matches += 1
                    break
        
        # Calculate score
        total_job_skills = len(job_skills_lower)
        if total_job_skills == 0:
            return 0.0
        
        exact_score = len(exact_matches) / total_job_skills
        partial_score = (partial_matches - len(exact_matches)) / total_job_skills * 0.5
        
        final_score = min(exact_score + partial_score, 1.0)
        return round(final_score, 3)