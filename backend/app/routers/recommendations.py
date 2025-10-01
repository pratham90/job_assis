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

from app.utils.converter import convert_mongo_doc

router = APIRouter()

class SwipeRequest(BaseModel):
    user_id: str
    job_id: str
    action: str  # 'like', 'dislike', 'save', 'apply', 'super_like'

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
        users = await db.mongo_db.users.find({}, {
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
    recommender: HybridRecommender = Depends(get_recommender),
):
    try:
        print(f"\n🚀 === RECOMMENDATION REQUEST ===")
        print(f"User ID: {clerk_id}")
        print(f"Requested limit: {limit}")
        
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

        # 2. Convert user document
        user_converted = convert_mongo_doc(user)
        user_model = UserProfile(**user_converted)

        # 3. Build search params from user resume/skills and fetch up to 100 jobs
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
        derived_location = user.get("location") or "India"

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

        # 4. Convert job documents
        job_models = []
        for job in jobs:
            try:
                converted = convert_mongo_doc(job)
                job_models.append(JobPosting(**converted))
            except Exception as e:
                print(f"Skipping invalid job {job.get('_id')}: {str(e)}")
                continue

        # 5. Fetch user swipes
        swipes = await db.get_user_swipes(clerk_id)
        swipe_models = [UserSwipe(**convert_mongo_doc(swipe)) for swipe in swipes]

        # 6. Generate recommendations
        print(f"🤖 Generating recommendations using AI...")
        recommendations = await recommender.recommend(
            user_model, job_models, swipe_models
        )
        
        print(f"\n🎯 === TOP RECOMMENDATIONS ===")
        for i, (job, score) in enumerate(recommendations[:limit]):
            print(f"\n--- Recommendation {i+1} ---")
            print(f"Job Title: {job.title}")
            print(f"Company: {getattr(job, 'employer_id', 'N/A')}")
            print(f"Location: {job.location.city if job.location else 'N/A'}")
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
