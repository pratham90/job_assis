from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from app.core.db import db
from app.services.recommender import HybridRecommender
from app.services.embeddings import EmbeddingService
from app.services.email_service import email_service  # Import email service
from app.models.user import UserProfile, JobSeekerCreate, EmployerCreate
from app.models.job import JobPosting, JobRecommendation
from app.models.swipe import UserSwipe, SwipeType
from typing import List
from pydantic import BaseModel
from datetime import datetime
import json
import logging

from app.utils.converter import convert_mongo_doc

router = APIRouter()
logger = logging.getLogger(__name__)

class SwipeRequest(BaseModel):
    user_id: str
    job_id: str
    action: str  # 'like', 'dislike', 'save', 'apply', 'super_like'
    job_payload: dict | None = None

class CreateUserRequest(BaseModel):
    clerk_id: str
    email: str
    first_name: str = ""
    last_name: str = ""
    role: str = "job_seeker"
    skills: List[str] | None = None
    location: str | None = None
    company_name: str | None = None

class RemoveSavedRequest(BaseModel):
    user_id: str
    job_id: str


def get_recommender():
    return HybridRecommender(EmbeddingService())

@router.post("/create-user")
async def create_user(request: CreateUserRequest):
    """Create a new user in MongoDB"""
    try:
        print(f"\n👤 === CREATING USER ===")
        print(f"Clerk ID: {request.clerk_id}")
        print(f"Name: {request.first_name} {request.last_name}")
        print(f"Email: {request.email}")
        print(f"Role: {request.role}")
        
        existing_user = await db.get_user_by_clerk_id(request.clerk_id)
        if existing_user:
            print(f"⚠️  User already exists")
            return {"message": "User already exists", "user_id": existing_user["_id"]}
        
        user_data = {
            "clerk_id": request.clerk_id,
            "email": request.email,
            "first_name": request.first_name,
            "last_name": request.last_name,
            "role": request.role,
            "skills": request.skills if request.skills is not None else [],
            "location": request.location if request.location is not None else "",
            "profile_complete": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        if request.role == "employer" and request.company_name:
            user_data["company_name"] = request.company_name

        print(f"[DEBUG] user_data to insert: {user_data}")

        user_id = await db.create_user(user_data)
        if user_id:
            print(f"✅ User created successfully with ID: {user_id}")
            return {"message": "User created successfully", "user_id": user_id}
        else:
            print(f"❌ Failed to create user")
            raise HTTPException(status_code=500, detail="Failed to create user")
            
    except Exception as e:
        print(f"💥 Error creating user: {e}")
        raise HTTPException(status_code=500, detail=f"User creation failed: {str(e)}")

@router.get("/users")
async def list_users():
    """List all users in the system (for debugging)"""
    try:
        print(f"\n📋 === LISTING ALL USERS ===")
        users = await db.users_db.Profile.find({}, {
            "clerk_id": 1, 
            "email": 1, 
            "first_name": 1, 
            "last_name": 1, 
            "role": 1,
            "skills": 1,
            "location": 1
        }).to_list(100)
        
        user_list = []
        for user in users:
            user["_id"] = str(user["_id"])
            user_list.append(user)
        
        print(f"Found {len(user_list)} users")
        return {"users": user_list, "count": len(user_list)}
        
    except Exception as e:
        print(f"💥 Error listing users: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list users: {str(e)}")

@router.post("/create-sample-user")
async def create_sample_user():
    """Create a sample user for testing purposes"""
    try:
        print(f"\n🧪 === CREATING SAMPLE USER ===")
        
        sample_user_data = {
            "clerk_id": "sample_user_123",
            "email": "john.doe@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "role": "job_seeker",
            "skills": ["Python", "FastAPI", "MongoDB", "React", "JavaScript"],
            "location": "New York, NY",
            "profile_complete": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        existing_user = await db.get_user_by_clerk_id("sample_user_123")
        if existing_user:
            print(f"⚠️  Sample user already exists")
            return {"message": "Sample user already exists", "user_id": existing_user["_id"]}
        
        user_id = await db.create_user(sample_user_data)
        if user_id:
            print(f"✅ Sample user created successfully with ID: {user_id}")
            return {
                "message": "Sample user created successfully", 
                "user_id": user_id,
                "clerk_id": "sample_user_123",
                "note": "You can now test recommendations with clerk_id: sample_user_123"
            }
        else:
            print(f"❌ Failed to create sample user")
            raise HTTPException(status_code=500, detail="Failed to create sample user")
            
    except Exception as e:
        print(f"💥 Error creating sample user: {e}")
        raise HTTPException(status_code=500, detail=f"Sample user creation failed: {str(e)}")


@router.get("/{clerk_id}")
async def get_recommendations(
    clerk_id: str,
    limit: int = 10,
    location: str = "All Locations",
    recommender: HybridRecommender = Depends(get_recommender),
):
    """Get personalized job recommendations for a user"""
    try:
        print(f"\n🚀 === RECOMMENDATION REQUEST ===")
        print(f"User ID: {clerk_id}")
        print(f"Requested limit: {limit}")
        print(f"Location filter: {location}")
        print(f"Timestamp: {datetime.utcnow().isoformat()}")
        
        # Fetch user data with caching
        print(f"📋 Fetching user profile from MongoDB (with cache)...")
        user = await db.get_user_by_clerk_id_cached(clerk_id)
        if not user:
            print(f"❌ User not found in MongoDB")
            raise HTTPException(status_code=404, detail="User not found")
        
        print(f"✅ User found: {user.get('first_name', 'N/A')} {user.get('last_name', 'N/A')}")
        print(f"   Email: {user.get('email', 'N/A')}")
        print(f"   Skills: {user.get('skills', [])}")
        print(f"   Location: {user.get('location', 'N/A')}")

        # Use raw user data for recommendations
        print(f"📊 Using raw user data for recommendations...")
        print(f"📊 User data keys: {list(user.keys())}")
        
        class SimpleUser:
            def __init__(self, data):
                self.clerk_id = data.get('clerk_id', '')
                self.email = data.get('email', '')
                self.first_name = data.get('first_name', '')
                self.last_name = data.get('last_name', '')
                self.location = data.get('location', '')
                self.skills = data.get('skills', [])
                self.technical_skills = data.get('technical_skills', [])
                self.soft_skills = data.get('soft_skills', [])
                self.certifications = data.get('certifications', [])
                self.experience = data.get('experience', [])
                self.education = data.get('education', [])
                self.projects = data.get('projects', [])
                self.resume = data.get('resume', {})
        
        try:
            user_model = SimpleUser(user)
            print(f"✅ SimpleUser created successfully")
        except Exception as e:
            print(f"💥 Error creating SimpleUser: {e}")
            raise HTTPException(status_code=500, detail=f"User processing failed: {str(e)}")

        # Build search params from user skills
        keywords_parts = []
        if user.get("skills"):
            keywords_parts.extend(user.get("skills")[:5])
        
        # Pull resume keywords if available
        try:
            if user.get("resume") and isinstance(user["resume"].get("parsed_data"), dict):
                parsed = user["resume"]["parsed_data"]
                resume_keywords = []
                for k in ["skills", "technologies", "experience", "projects"]:
                    v = parsed.get(k)
                    if isinstance(v, list):
                        resume_keywords.extend([str(s) for s in v[:5]])
                    elif isinstance(v, str):
                        resume_keywords.extend(v.split()[:5])
                keywords_parts.extend(resume_keywords[:10])
        except Exception:
            pass

        derived_keywords = " ".join(dict.fromkeys([kp for kp in keywords_parts if isinstance(kp, str)])) or "software engineer"
        
        # Handle location filter
        if location and location.lower() not in ["all locations", "all", ""]:
            derived_location = location
        else:
            derived_location = ""
        
        print(f"🔍 Searching with keywords: {derived_keywords}")
        print(f"📍 Location filter: {location}")
        print(f"📍 Final location: {derived_location}")

        jobs = await db.get_active_jobs(limit=100, keywords=derived_keywords, location=derived_location)
        if not jobs:
            try:
                jobs = await db.get_active_jobs(
                    limit=100,
                    keywords=derived_keywords or "software engineer",
                    location=derived_location or "India",
                    trusted_only=False,
                    force_scrape=False
                )
            except Exception:
                jobs = []
        if not jobs:
            return []

        # Convert and filter jobs
        job_models = []
        for job in jobs:
            try:
                if isinstance(job, dict):
                    job_data = job
                else:
                    job_data = convert_mongo_doc(job)
                
                # Apply location filtering (your existing logic)
                if location and location != "All Locations":
                    # Your location filtering logic here...
                    pass

                job_model = JobPosting(**job_data)
                job_models.append(job_model)
            except Exception as e:
                print(f"❌ Skipping invalid job: {str(e)}")
                continue

        # Filter out already interacted jobs
        liked_action_ids = await db.get_user_action_job_ids(clerk_id, ['save', 'like', 'super_like'])
        disliked_action_ids = await db.get_user_action_job_ids(clerk_id, ['dislike'])

        liked_job_ids = set(liked_action_ids)
        disliked_job_ids = set(disliked_action_ids)
        
        print(f"🚫 Filtering out {len(liked_job_ids)} liked jobs and {len(disliked_job_ids)} disliked jobs")
        
        filtered_job_models = []
        for job_model in job_models:
            if job_model.id not in liked_job_ids and job_model.id not in disliked_job_ids:
                filtered_job_models.append(job_model)
        
        print(f"📊 After filtering: {len(filtered_job_models)} jobs available")

        # Generate recommendations
        print(f"🤖 Generating recommendations using AI...")
        recommendations = await recommender.recommend(
            user_model, filtered_job_models, []
        )
        
        print(f"\n🎯 === TOP RECOMMENDATIONS ===")
        for i, (job, score) in enumerate(recommendations[:limit]):
            print(f"\n--- Recommendation {i+1} ---")
            print(f"Job Title: {job.title}")
            print(f"Company: {getattr(job, 'company', getattr(job, 'employer_id', 'N/A'))}")
            print(f"Match Score: {score:.3f}")
        
        print(f"\n✅ Returning {min(len(recommendations), limit)} recommendations")
        
        # Enqueue remaining jobs
        try:
            id_to_dict = {}
            for job in jobs:
                try:
                    converted = convert_mongo_doc(job)
                    id_to_dict[str(converted.get("_id", converted.get("id", "")))] = converted
                except Exception:
                    continue

            remaining = [job for job, _ in recommendations[limit:100]]
            queue_payload = []
            for job in remaining:
                jid = getattr(job, "id", None)
                if not jid:
                    continue
                payload = id_to_dict.get(str(jid)) or job.model_dump(by_alias=True)
                queue_payload.append(payload)

            if queue_payload:
                await db.enqueue_user_jobs(clerk_id, queue_payload)
        except Exception as e:
            print(f"Queueing related jobs failed: {e}")

        return [
            JobRecommendation(job=job, match_score=score)
            for job, score in recommendations[:limit]
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendation failed: {str(e)}")

@router.post("/swipe")
async def handle_swipe_action(request: SwipeRequest, background_tasks: BackgroundTasks):
    """Handle user swipe actions (like, dislike, save) with email notifications"""
    try:
        import time
        start_time = time.time()
        
        logger.info(f"\n👆 === SWIPE ACTION ===")
        logger.info(f"User: {request.user_id[:12]}...")
        logger.info(f"Job: {request.job_id[:12]}...")
        logger.info(f"Action: {request.action}")
        logger.info(f"Timestamp: {datetime.utcnow().isoformat()}")
        
        valid_actions = ['like', 'dislike', 'save', 'apply', 'super_like']
        if request.action not in valid_actions:
            raise HTTPException(status_code=400, detail=f"Invalid action. Must be one of: {valid_actions}")
        
        limit_check = await db.check_and_increment_swipe_limit(request.user_id)
        
        if not limit_check.get("allowed", False):
            logger.warning(f"🚫 User exceeded daily swipe limit")
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Daily swipe limit reached",
                    "message": f"You've reached your daily limit of {limit_check.get('limit', 20)} swipes",
                    "remaining": limit_check.get("remaining", 0),
                    "reset_at": limit_check.get("reset_at").isoformat() if limit_check.get("reset_at") else None,
                    "total_today": limit_check.get("total_today", 0)
                }
            )
        
        logger.info(f"✅ Swipe allowed. Remaining: {limit_check.get('remaining', 0)}")
        
        # Get user details for email
        user = await db.get_user_by_clerk_id(request.user_id)
        if not user:
            logger.warning(f"⚠️  User not found: {request.user_id}")
        
        if request.action in ["save", "like", "super_like", "dislike"]:
            action_start = time.time()
            
            job_snapshot = None
            try:
                if request.job_payload:
                    job_snapshot = request.job_payload
                else:
                    job_snapshot = await db.get_job_by_id(request.job_id)
            except Exception as e:
                logger.debug(f"⚠️  Could not get job snapshot: {e}")
                job_snapshot = None
            
            result = await db.save_user_job_action(request.user_id, request.job_id, request.action, job_snapshot)
            action_elapsed = time.time() - action_start
            
            if not result:
                logger.error(f"❌ Failed to persist action '{request.action}' to MongoDB")
            else:
                logger.info(f"✅ Action saved in {action_elapsed:.3f} seconds")
            
            # Send email notification for right swipes (like, super_like, apply)
            if request.action in ['like', 'super_like', 'apply'] and user and job_snapshot:
                logger.info(f"📧 Triggering email notification for {request.action} action")
                
                # Extract user details
                user_email = user.get('email', '')
                user_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or "User"
                
                # Extract job details
                job_title = job_snapshot.get('title', 'Job Position')
                company_name = job_snapshot.get('company', job_snapshot.get('employer_id', 'Company'))
                job_location = job_snapshot.get('location', 'Location not specified')
                
                if user_email:
                    # Send email in background to not block the response
                    background_tasks.add_task(
                        email_service.send_application_confirmation,
                        recipient_email=user_email,
                        user_name=user_name,
                        job_title=job_title,
                        company_name=company_name,
                        location=job_location
                    )
                    logger.info(f"✅ Email queued for {user_email}")
                else:
                    logger.warning(f"⚠️  No email found for user {request.user_id}")
            
            # Send email notification for saved jobs
            elif request.action == 'save' and user and job_snapshot:
                logger.info(f"📧 Triggering saved job notification")
                
                user_email = user.get('email', '')
                user_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or "User"
                job_title = job_snapshot.get('title', 'Job Position')
                company_name = job_snapshot.get('company', job_snapshot.get('employer_id', 'Company'))
                
                if user_email:
                    background_tasks.add_task(
                        email_service.send_saved_job_notification,
                        recipient_email=user_email,
                        user_name=user_name,
                        job_title=job_title,
                        company_name=company_name
                    )
                    logger.info(f"✅ Saved job notification queued for {user_email}")

        elapsed = time.time() - start_time
        logger.info(f"⏱️  Total swipe handling: {elapsed:.3f} seconds")
        logger.info(f"=====================================")

        return {
            "success": True,
            "message": f"Job {request.action} successfully",
            "action": request.action,
            "job_id": request.job_id,
            "email_sent": request.action in ['like', 'super_like', 'apply', 'save'],
            "swipe_limit": {
                "remaining": limit_check.get("remaining", 0),
                "total_today": limit_check.get("total_today", 0),
                "limit": limit_check.get("limit", 20),
                "reset_at": limit_check.get("reset_at").isoformat() if limit_check.get("reset_at") else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"💥 Error handling swipe action: {e}")
        raise HTTPException(status_code=500, detail=f"Swipe action failed: {str(e)}")

@router.get("/saved/{clerk_id}")
async def get_saved_jobs(clerk_id: str):
    """Return the user's saved jobs from MongoDB WITHOUT caching for real-time updates"""
    try:
        import time
        start_time = time.time()
        
        logger.info(f"\n💾 === FETCHING SAVED JOBS ===")
        logger.info(f"User ID: {clerk_id}")
        logger.info(f"Timestamp: {datetime.utcnow().isoformat()}")
        
        # Use NON-CACHED version for real-time updates
        jobs = await db.get_user_saved_jobs(clerk_id)
        
        elapsed = time.time() - start_time
        logger.info(f"✅ Found {len(jobs)} saved jobs in {elapsed:.3f} seconds")
        logger.info(f"=====================================")
        
        return jobs
    except Exception as e:
        logger.error(f"💥 Error fetching saved jobs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch saved jobs: {str(e)}")

@router.post("/saved/remove")
async def remove_saved_job(req: RemoveSavedRequest):
    """Remove a saved job from MongoDB"""
    try:
        import time
        start_time = time.time()
        
        logger.info(f"\n🗑️  === REMOVING SAVED JOB ===")
        logger.info(f"User: {req.user_id[:12]}...")
        logger.info(f"Job: {req.job_id[:12]}...")
        
        ok = await db.remove_saved_job(req.user_id, req.job_id)
        
        elapsed = time.time() - start_time
        logger.info(f"{'✅ Removed' if ok else '❌ Failed'} in {elapsed:.3f} seconds")
        logger.info(f"=====================================")
        
        return {"success": ok}
    except Exception as e:
        logger.error(f"❌ Error removing saved job: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remove saved job: {str(e)}")

@router.get("/liked/{clerk_id}")
async def get_liked_jobs(clerk_id: str):
    """Return the user's liked jobs from users_job_like collection"""
    try:
        print(f"\n💚 === FETCHING LIKED JOBS ===")
        print(f"User ID: {clerk_id}")
        jobs = await db.get_user_liked_jobs(clerk_id)
        print(f"✅ Found {len(jobs)} liked jobs")
        return jobs
    except Exception as e:
        print(f"💥 Error fetching liked jobs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch liked jobs: {str(e)}")

@router.post("/liked/remove")
async def remove_liked_job(req: RemoveSavedRequest):
    """Remove a liked job from users_job_like collection"""
    try:
        ok = await db.remove_job_like(req.user_id, req.job_id)
        return {"success": ok}
    except Exception as e:
        logger.error(f"❌ Error removing liked job: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remove liked job: {str(e)}")

@router.get("/disliked/{clerk_id}")
async def get_disliked_jobs(clerk_id: str):
    """Return the user's disliked job IDs from users_job_dislike collection"""
    try:
        jobs = await db.get_user_disliked_jobs(clerk_id)
        return jobs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch disliked jobs: {str(e)}")

@router.post("/disliked/remove")
async def remove_disliked_job(req: RemoveSavedRequest):
    """Remove a disliked job from users_job_dislike collection"""
    try:
        ok = await db.remove_job_dislike(req.user_id, req.job_id)
        return {"success": ok}
    except Exception as e:
        logger.error(f"❌ Error removing disliked job: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remove disliked job: {str(e)}")

@router.get("/disliked/check/{clerk_id}/{job_id}")
async def check_job_disliked(clerk_id: str, job_id: str):
    """Check if a specific job is disliked by the user"""
    try:
        is_disliked = await db.is_job_disliked(clerk_id, job_id)
        return {"is_disliked": is_disliked}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check job dislike status: {str(e)}")