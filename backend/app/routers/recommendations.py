from fastapi import APIRouter, Depends, HTTPException
from app.core.db import db
from app.services.recommender import HybridRecommender
from app.services.embeddings import EmbeddingService
from app.models.user import UserProfile, JobSeekerCreate, EmployerCreate
from app.models.job import JobPosting, JobRecommendation
from app.models.swipe import UserSwipe, SwipeType
from typing import List
from pydantic import BaseModel
from datetime import datetime
import json

from app.utils.converter import convert_mongo_doc

router = APIRouter()

class SwipeRequest(BaseModel):
    user_id: str
    job_id: str
    action: str  # 'like', 'dislike', 'save', 'apply', 'super_like'
    job_payload: dict | None = None  # optional snapshot to persist

class CreateUserRequest(BaseModel):
    clerk_id: str
    email: str
    first_name: str
    last_name: str
    role: str = "job_seeker"  # "job_seeker" or "employer"
    skills: List[str] = []
    location: str = None
    company_name: str = None  # For employers


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
        
        # Check if user already exists
        existing_user = await db.get_user_by_clerk_id(request.clerk_id)
        if existing_user:
            print(f"⚠️  User already exists")
            return {"message": "User already exists", "user_id": existing_user["_id"]}
        
        # Create user data
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

        # Only add company_name for employers
        if request.role == "employer" and request.company_name:
            user_data["company_name"] = request.company_name

        print(f"[DEBUG] user_data to insert: {user_data}")

        # Create user in MongoDB
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
        
        # Check if sample user already exists
        existing_user = await db.get_user_by_clerk_id("sample_user_123")
        if existing_user:
            print(f"⚠️  Sample user already exists")
            return {"message": "Sample user already exists", "user_id": existing_user["_id"]}
        
        # Create sample user
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
    location: str = "All Locations",  # Default to "All Locations"
    recommender: HybridRecommender = Depends(get_recommender),
):
    try:
        print(f"\n🚀 === RECOMMENDATION REQUEST ===")
        print(f"User ID: {clerk_id}")
        print(f"Requested limit: {limit}")
        print(f"Timestamp: {datetime.utcnow().isoformat()}")
        
        # 1. Fetch user data
        print(f"📋 Fetching user profile from MongoDB...")
        user = await db.get_user_by_clerk_id(clerk_id)
        if not user:
            print(f"❌ User not found in MongoDB")
            raise HTTPException(status_code=404, detail="User not found")
        
        print(f"✅ User found: {user.get('first_name', 'N/A')} {user.get('last_name', 'N/A')}")
        print(f"   Email: {user.get('email', 'N/A')}")
        print(f"   Skills: {user.get('skills', [])}")
        print(f"   Location: {user.get('location', 'N/A')}")

        # 2. Use raw user data instead of strict Pydantic validation
        # This allows us to work with the actual MongoDB document structure
        print(f"📊 Using raw user data for recommendations...")
        print(f"📊 User data keys: {list(user.keys())}")
        
        # Create a simple user object with the data we need
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

        # 3. Build search params from user skills and fetch up to 100 jobs
        keywords_parts = []
        if user.get("skills"):
            keywords_parts.extend(user.get("skills")[:5])
        
        # Pull common resume keywords if available
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
        
        # Use frontend location filter, don't filter by location if "All Locations"
        if location and location.lower() not in ["all locations", "all", ""]:
            derived_location = location
        else:
            derived_location = ""  # Empty means no location filtering
        
        print(f"🔍 Searching with keywords: {derived_keywords}")
        print(f"📍 Location filter: {location}")
        print(f"📍 Final location: {derived_location}")

        jobs = await db.get_active_jobs(limit=100, keywords=derived_keywords, location=derived_location)
        if not jobs:
            # Relax filters and retry instead of hard 404
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
            # Return empty list so UI can handle gracefully
            return []

        # 4. Convert job documents (jobs from get_active_jobs are already converted) and apply location filter
        job_models = []
        for job in jobs:
            try:
                # If job is already a dict (from get_active_jobs), use it directly
                if isinstance(job, dict):
                    job_data = job
                else:
                    # If it's a MongoDB document, convert it
                    job_data = convert_mongo_doc(job)
                # Apply location filter if provided and not 'All Locations'
                if location and location != "All Locations":
                    loc_ok = False
                    if isinstance(job_data.get('location'), str):
                        loc_ok = location.lower() in job_data['location'].lower()
                    elif isinstance(job_data.get('location'), dict):
                        parts = [str(job_data['location'].get('city','')), str(job_data['location'].get('state','')), str(job_data['location'].get('country',''))]
                        loc_ok = location.lower() in (' '.join(parts)).lower()
                    if not loc_ok:
                        continue

                job_model = JobPosting(**job_data)
                job_models.append(job_model)
            except Exception as e:
                print(f"❌ Skipping invalid job: {str(e)}")
                continue

        # 5. Fetch user swipes from Redis and persisted actions from MongoDB
        swipes = await db.get_user_swipes(clerk_id)
        mongo_action_ids = await db.get_user_action_job_ids(clerk_id, ['save', 'like', 'super_like', 'dislike'])

        # 6. Filter out jobs that user has already liked/saved/disliked
        liked_job_ids = set()
        disliked_job_ids = set()
        
        for swipe in swipes:
            job_id = swipe.get('job_id')
            action = swipe.get('action')
            if job_id:
                if action in ['like', 'super_like', 'save']:
                    liked_job_ids.add(job_id)
                elif action == 'dislike':
                    disliked_job_ids.add(job_id)

        # Also include MongoDB persisted actions to ensure no duplicates show up
        for jid in mongo_action_ids:
            liked_job_ids.add(jid)
        
        print(f"🚫 Filtering out {len(liked_job_ids)} liked jobs and {len(disliked_job_ids)} disliked jobs")
        
        # Filter job models to exclude liked/saved/disliked jobs
        filtered_job_models = []
        for job_model in job_models:
            if job_model.id not in liked_job_ids and job_model.id not in disliked_job_ids:
                filtered_job_models.append(job_model)
        
        print(f"📊 After filtering: {len(filtered_job_models)} jobs available for recommendations")
        
        # 7. If we don't have enough jobs, try to get more from Redis/LinkedIn
        if len(filtered_job_models) < limit:
            print(f"⚠️  Only {len(filtered_job_models)} jobs available, need {limit}")
            print(f"🔄 Attempting to fetch more jobs from Redis/LinkedIn...")
            
            # Try to get more jobs with relaxed criteria
            try:
                additional_jobs = await db.get_active_jobs(
                    limit=limit * 2,  # Get more jobs
                    keywords="",  # No keyword filtering
                    location="",  # No location filtering
                    job_type_filter=None,
                    category_filter=None,
                    trusted_only=False,  # Include all companies
                    force_scrape=True  # Force LinkedIn scraping
                )
                
                print(f"📊 Additional jobs fetched: {len(additional_jobs)}")
                
                # Process additional jobs (already converted by get_active_jobs)
                for job in additional_jobs:
                    try:
                        # Jobs from get_active_jobs are already converted
                        if isinstance(job, dict):
                            job_data = job
                        else:
                            job_data = convert_mongo_doc(job)
                        
                        job_model = JobPosting(**job_data)
                        
                        # Only add if not already liked/disliked AND not already in filtered_job_models
                        if (job_model.id not in liked_job_ids and 
                            job_model.id not in disliked_job_ids and
                            job_model.id not in [j.id for j in filtered_job_models]):
                            filtered_job_models.append(job_model)
                            
                            if len(filtered_job_models) >= limit:
                                break
                    except Exception as e:
                        continue
                        
            except Exception as e:
                print(f"❌ Error fetching additional jobs: {e}")
        
        print(f"📊 Final job count: {len(filtered_job_models)} jobs")

        # 7. Generate recommendations
        print(f"🤖 Generating recommendations using AI...")
        recommendations = await recommender.recommend(
            user_model, filtered_job_models, swipes
        )
        
        print(f"\n🎯 === TOP RECOMMENDATIONS ===")
        for i, (job, score) in enumerate(recommendations[:limit]):
            print(f"\n--- Recommendation {i+1} ---")
            print(f"Job Title: {job.title}")
            print(f"Company: {getattr(job, 'company', getattr(job, 'employer_id', 'N/A'))}")
            print(f"Location: {job.location.city if job.location else 'N/A'}")
            print(f"Skills Required: {getattr(job, 'skills_required', [])}")
            print(f"Match Score: {score:.3f}")
            print(f"Source: {getattr(job, 'source', 'unknown')}")
            print(f"Priority: {getattr(job, 'priority', 'N/A')}")
        
        print(f"\n✅ Returning {min(len(recommendations), limit)} recommendations")
        print(f"=====================================")
        
        # 7. Enqueue remaining related jobs (beyond the first page)
        try:
            # Map id->original dict for queuing
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
                # Prefer the dict if available; otherwise dump from model
                payload = id_to_dict.get(str(jid)) or job.model_dump(by_alias=True)
                queue_payload.append(payload)

            if queue_payload:
                await db.enqueue_user_jobs(clerk_id, queue_payload)
        except Exception as e:
            print(f"Queueing related jobs failed: {e}")

        # 8. Return top N recommendations
        return [
            JobRecommendation(job=job, match_score=score)
            for job, score in recommendations[:limit]
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendation failed: {str(e)}")

@router.post("/swipe")
async def handle_swipe_action(request: SwipeRequest):
    """Handle user swipe actions (like, dislike, save)"""
    try:
        print(f"\n👆 === SWIPE ACTION ===")
        print(f"User ID: {request.user_id}")
        print(f"Job ID: {request.job_id}")
        print(f"Action: {request.action}")
        
        # Validate action
        valid_actions = ['like', 'dislike', 'save', 'apply', 'super_like']
        if request.action not in valid_actions:
            raise HTTPException(status_code=400, detail=f"Invalid action. Must be one of: {valid_actions}")
        
        # Store swipe action in Redis
        swipe_data = {
            "user_id": request.user_id,
            "job_id": request.job_id,
            "action": request.action,
            "timestamp": datetime.utcnow().isoformat(),
            "undone": False
        }
        
        # Store in Redis with expiration (30 days)
        swipe_key = f"swipe:{request.user_id}:{request.job_id}:{request.action}"
        await db.redis_client.setex(swipe_key, 30 * 24 * 60 * 60, json.dumps(swipe_data))
        
        print(f"✅ Swipe action stored successfully")

        # Also persist 'save' and 'like' to MongoDB for long-term storage
        if request.action in ["save", "like", "super_like"]:
            # Try to attach job snapshot for rich Saved view
            job_snapshot = None
            try:
                if request.job_payload:
                    job_snapshot = request.job_payload
                else:
                    job_snapshot = await db.get_job_by_id(request.job_id)
            except Exception:
                job_snapshot = None
            await db.save_user_job_action(request.user_id, request.job_id, request.action, job_snapshot)

        return {
            "success": True,
            "message": f"Job {request.action} successfully",
            "action": request.action,
            "job_id": request.job_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"💥 Error handling swipe action: {e}")
        raise HTTPException(status_code=500, detail=f"Swipe action failed: {str(e)}")

@router.get("/saved/{clerk_id}")
async def get_saved_jobs(clerk_id: str):
    """Return the user's saved jobs from MongoDB."""
    try:
        jobs = await db.get_user_saved_jobs(clerk_id)
        return jobs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch saved jobs: {str(e)}")

class RemoveSavedRequest(BaseModel):
    user_id: str
    job_id: str

@router.post("/saved/remove")
async def remove_saved_job(req: RemoveSavedRequest):
    try:
        ok = await db.remove_saved_job(req.user_id, req.job_id)
        return {"success": ok}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove saved job: {str(e)}")
