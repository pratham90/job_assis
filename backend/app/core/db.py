# app/core/db.py - COMPLETE FIXED VERSION

from typing import List, Optional
from bson import ObjectId
import os
import json
import redis.asyncio as redis
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import logging
from datetime import datetime
import re

logger = logging.getLogger(__name__)

load_dotenv()
redis_uri = os.getenv("REDIS_URI", "redis://default:liiSkjZQkhWPULcAcQ2dV0MZzy82wj2B@redis-13364.c56.east-us.azure.redns.redis-cloud.com:13364/0")
mongo_uri = os.getenv("MONGO_URI", "mongodb+srv://Jobs:Jobs-provider@jobs.2m8l8hb.mongodb.net")

class Database:
    def __init__(self):
        self.redis_client = redis.from_url(redis_uri, decode_responses=True)
        self.mongo_client = AsyncIOMotorClient(mongo_uri)
        # Use the Jobs database for jobs
        self.mongo_db = self.mongo_client.Jobs
        # Connect to users database for user profiles and skills
        self.users_db = self.mongo_client.users
        self.scraper = None
        
        logger.info("🔗 Database connections initialized:")
        logger.info(f"   📦 Redis: {redis_uri.split('@')[1] if '@' in redis_uri else 'localhost'}")
        logger.info(f"   🍃 MongoDB: {mongo_uri.split('@')[1].split('/')[0] if '@' in mongo_uri else 'localhost'}")
    
    async def ensure_indexes(self):
        """Create unique indexes to prevent duplicate job actions"""
        try:
            # Create unique compound index on user_job_actions collection
            # This ensures no duplicate (user_id, job_id, action) combinations
            await self.users_db.user_job_actions.create_index(
                [("user_id", 1), ("job_id", 1), ("action", 1)],
                unique=True,
                name="unique_user_job_action"
            )
            logger.info("   ✅ Unique compound index: (user_id, job_id, action)")
            
            # Create index on user_id for faster queries
            await self.users_db.user_job_actions.create_index(
                [("user_id", 1)],
                name="user_id_index"
            )
            logger.info("   ✅ Index: user_id")
            
            # Create index on action for faster filtering
            await self.users_db.user_job_actions.create_index(
                [("action", 1)],
                name="action_index"
            )
            logger.info("   ✅ Index: action")
            
        except Exception as e:
            logger.warning(f"⚠️  Index creation warning (indexes may already exist): {e}")
    
    def _initialize_scraper(self):
        """Initialize the web scraper only when needed"""
        if self.scraper is None:
            try:
                from app.job_scraper import RedisCachedJobScraper
                
                redis_parts = redis_uri.split('@')
                if len(redis_parts) == 2:
                    auth_part = redis_parts[0].split('//')[1]
                    host_part = redis_parts[1]
                    password = auth_part.split(':')[1] if ':' in auth_part else None
                    host = host_part.split(':')[0]
                    port = int(host_part.split(':')[1].split('/')[0])
                else:
                    host = 'localhost'
                    port = 6379
                    password = None
                
                self.scraper = RedisCachedJobScraper(
                    redis_host=host,
                    redis_port=port, 
                    redis_password=password,
                    cache_duration_hours=72
                )
                logger.info("Web scraper initialized successfully")
                
            except Exception as e:
                logger.error(f"Failed to initialize web scraper: {e}")
                self.scraper = None

    def _normalize_employment_type(self, employment_type: str) -> str:
        """Convert employment type to expected enum values"""
        if not employment_type:
            return 'full_time'
        
        employment_type = employment_type.lower().strip()
        
        type_mapping = {
            'full-time': 'full_time',
            'full time': 'full_time', 
            'fulltime': 'full_time',
            'permanent': 'full_time',
            'part-time': 'part_time',
            'part time': 'part_time',
            'parttime': 'part_time',
            'contract': 'contract',
            'contractor': 'contract',
            'freelance': 'contract',
            'temporary': 'contract',
            'temp': 'contract',
            'intern': 'internship',
            'internship': 'internship',
            'graduate': 'internship'
        }
        
        return type_mapping.get(employment_type, 'full_time')

    def _parse_salary_string(self, salary_str: str) -> dict:
        """Parse salary string into SalaryRange format"""
        if not salary_str or salary_str.strip() == '':
            return {
                "min": 0,
                "max": 0,
                "currency": "USD",
                "is_public": False
            }
        
        # Extract numbers from salary string
        numbers = re.findall(r'[\d,]+', salary_str.replace(',', ''))
        
        # Determine currency
        currency = "USD"
        if any(indicator in salary_str.lower() for indicator in ['lakh', 'lpa', '₹', 'inr']):
            currency = "INR"
        elif '€' in salary_str or 'eur' in salary_str.lower():
            currency = "EUR"
        elif '£' in salary_str or 'gbp' in salary_str.lower():
            currency = "GBP"
        
        # Parse salary range
        if len(numbers) >= 2:
            try:
                min_salary = int(numbers[0])
                max_salary = int(numbers[1])
                
                # Handle cases where salaries are in thousands
                if 'k' in salary_str.lower():
                    min_salary *= 1000
                    max_salary *= 1000
                    
                return {
                    "min": min_salary,
                    "max": max_salary,
                    "currency": currency,
                    "is_public": True
                }
            except ValueError:
                pass
        elif len(numbers) == 1:
            try:
                salary = int(numbers[0])
                if 'k' in salary_str.lower():
                    salary *= 1000
                return {
                    "min": salary,
                    "max": salary,
                    "currency": currency,
                    "is_public": True
                }
            except ValueError:
                pass
        
        return {
            "min": 0,
            "max": 0,
            "currency": currency,
            "is_public": False
        }
    
    async def get_user_by_clerk_id(self, clerk_id: str) -> Optional[dict]:
        """Get user by Clerk ID from users/Profile collection"""
        try:
            print(f"🔍 Searching for user with clerk_id: {clerk_id}")
            print(f"🔍 Database: {self.users_db.name}")
            print(f"🔍 Collection: Profile")
            
            # Get user profile with skills from users/Profile collection
            profile_data = await self.users_db.Profile.find_one({"clerk_id": clerk_id})
            if profile_data:
                print(f"✅ Profile found with skills: {profile_data.get('skills', [])}")
                profile_data["_id"] = str(profile_data["_id"])
                return profile_data
            else:
                print(f"❌ User with clerk_id '{clerk_id}' not found in users/Profile collection")
                
                # Debug: Check if there are any users in the Profile collection
                total_profiles = await self.users_db.Profile.count_documents({})
                print(f"📊 Total profiles in users/Profile: {total_profiles}")
                
                # Debug: List all clerk_ids in Profile collection
                all_profiles = await self.users_db.Profile.find({}, {"clerk_id": 1}).to_list(10)
                print(f"📋 Sample clerk_ids in Profile: {[p.get('clerk_id') for p in all_profiles]}")
                
                return None
                
        except Exception as e:
            print(f"💥 Error fetching user from MongoDB: {e}")
            return None
    
    async def create_user(self, user_data: dict) -> Optional[str]:
        """Create a new user in users/Profile collection"""
        try:
            print(f"📝 Creating user in users/Profile collection...")
            print(f"📝 User data: {user_data}")
            
            # Store user in users/Profile collection
            result = await self.users_db.Profile.insert_one(user_data)
            user_id = str(result.inserted_id)
            print(f"✅ User created in users/Profile with ID: {user_id}")
            
            # Verify the user was created
            verify_user = await self.users_db.Profile.find_one({"_id": result.inserted_id})
            if verify_user:
                print(f"✅ User verification successful: {verify_user.get('first_name')} {verify_user.get('last_name')}")
            else:
                print(f"❌ User verification failed!")
            
            return user_id
        except Exception as e:
            print(f"Error creating user in MongoDB: {e}")
            return None
    
    async def update_user(self, clerk_id: str, update_data: dict) -> bool:
        """Update user data in users/Profile collection"""
        try:
            result = await self.users_db.Profile.update_one(
                {"clerk_id": clerk_id},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            print(f"Error updating user in MongoDB: {e}")
            return False
    
    async def get_active_jobs(self, limit: int = 100, 
                            keywords: str = "software engineer", 
                            location: str = "India",
                            job_type_filter: str = None, 
                            category_filter: str = None,
                            trusted_only: bool = True,
                            force_scrape: bool = False) -> List[dict]:
        """Get all active job postings with 3-step priority and loop prevention"""
        all_jobs = []
        
        print(f"🎯 Starting 3-step job search (limit: {limit})")
        print(f"   Keywords: {keywords}, Location: {location}")
        print(f"   Filters: job_type={job_type_filter}, category={category_filter}, trusted={trusted_only}")
        
        # ============= STEP 1: GET JOBS FROM JOBS/JOBS-LISTS COLLECTION =============
        try:
            print(f"\n📋 STEP 1: Fetching jobs from Jobs/jobs-lists collection...")
            posted_jobs = await self.mongo_db["jobs-lists"].find(
                {"is_active": {"$ne": False}},  # Get active jobs
                {
                    "_id": 1, "employer_id": 1, "title": 1, "description": 1,
                    "employment_type": 1, "location": 1, "skills_required": 1, "requirements": 1,
                    "category": 1, "source": 1, "created_at": 1, "posted_at": 1,
                    "salary": 1, "company": 1, "url": 1, "experience_level": 1
                }
            ).to_list(100)
            
            print(f"✅ Found {len(posted_jobs)} jobs in Jobs/jobs-lists collection")
            
            for job in posted_jobs:
                converted_job = self._convert_jobs_lists_job(job)
                if converted_job:
                    converted_job["source"] = "jobs_lists"
                    converted_job["priority"] = 1.0
                    all_jobs.append(converted_job)
                    
            print(f"✅ Successfully processed {len([j for j in all_jobs if j.get('source') == 'jobs_lists'])} jobs from jobs-lists")
            
        except Exception as e:
            print(f"❌ Error fetching jobs from Jobs/jobs-lists: {e}")
        
        # ============= STEP 2: GET CACHED JOBS FROM REDIS =============
        remaining_needed = limit - len(all_jobs)
        if remaining_needed > 0:
            try:
                print(f"\n🔄 STEP 2: Fetching cached jobs from Redis (need {remaining_needed} more)...")
                
                # Use simple cluster-based job retrieval
                # Default behavior: Show jobs from both clusters (All Locations)
                if location and location.lower() == "usa":
                    # Get job IDs from USA cluster only
                    usa_job_ids = await self.redis_client.smembers("cluster:usa:jobs")
                    job_ids = [job_id.decode('utf-8') if isinstance(job_id, bytes) else job_id for job_id in usa_job_ids]
                    cluster_info = "USA cluster"
                elif location and location.lower() == "india":
                    # Get job IDs from India cluster only
                    india_job_ids = await self.redis_client.smembers("cluster:india:jobs")
                    job_ids = [job_id.decode('utf-8') if isinstance(job_id, bytes) else job_id for job_id in india_job_ids]
                    cluster_info = "India cluster"
                else:
                    # DEFAULT: Get job IDs from BOTH clusters (All Locations/No filter)
                    usa_job_ids = await self.redis_client.smembers("cluster:usa:jobs")
                    india_job_ids = await self.redis_client.smembers("cluster:india:jobs")
                    
                    # Combine both clusters
                    all_job_ids = list(usa_job_ids) + list(india_job_ids)
                    job_ids = [job_id.decode('utf-8') if isinstance(job_id, bytes) else job_id for job_id in all_job_ids]
                    cluster_info = f"All Locations - Combined clusters (USA: {len(usa_job_ids)}, India: {len(india_job_ids)})"
                scraped_count = 0
                
                print(f"📊 Found {len(job_ids)} cached job IDs from {cluster_info}")
                
                # LOOP PREVENTION: Limit the jobs we process
                max_jobs_to_process = min(len(job_ids), remaining_needed * 3, 200)  # Cap at 200
                
                for job_id in job_ids[:max_jobs_to_process]:
                    job_data = await self.redis_client.hgetall(f"job:{job_id}")
                    if job_data:
                        # Convert Redis job first
                        converted_job = self._convert_scraped_job(job_data)
                        
                        if converted_job:
                            # Apply location filtering to Redis jobs
                            if location and location.strip() and location.lower() not in ["all locations", "all"]:
                                location_lower = location.lower()
                                
                                # Handle location data format (could be dict or string)
                                job_location_raw = converted_job.get('location', '')
                                if isinstance(job_location_raw, dict):
                                    # Extract location string from dict
                                    parts = [
                                        str(job_location_raw.get('city', '')),
                                        str(job_location_raw.get('state', '')),
                                        str(job_location_raw.get('country', ''))
                                    ]
                                    job_location = ' '.join(parts).lower()
                                else:
                                    job_location = str(job_location_raw).lower()
                                
                                # Enhanced location matching for USA and India
                                if location_lower == "usa":
                                    usa_keywords = ['united states', 'usa', 'us', 'california', 'new york', 
                                                  'texas', 'washington', 'massachusetts', 'illinois', 'colorado',
                                                  ', ca', ', ny', ', tx', 'san francisco', 'los angeles', 'seattle']
                                    if not any(keyword in job_location for keyword in usa_keywords):
                                        continue  # Skip this job
                                    # Exclude jobs that also contain India keywords
                                    india_keywords = ['india', 'mumbai', 'delhi', 'bangalore', 'bengaluru', 
                                                    'hyderabad', 'chennai', 'pune', 'kolkata', 'ahmedabad']
                                    if any(india_keyword in job_location for india_keyword in india_keywords):
                                        continue  # Skip this job
                                elif location_lower == "india":
                                    india_keywords = ['india', 'mumbai', 'delhi', 'bangalore', 'bengaluru', 
                                                    'hyderabad', 'chennai', 'pune', 'kolkata', 'ahmedabad']
                                    if not any(keyword in job_location for keyword in india_keywords):
                                        continue  # Skip this job
                                    # Exclude jobs that also contain USA keywords
                                    usa_keywords = ['united states', 'usa', 'us', 'california', 'new york', 
                                                  'texas', 'washington', 'massachusetts', 'illinois', 'colorado']
                                    if any(usa_keyword in job_location for usa_keyword in usa_keywords):
                                        continue  # Skip this job
                                else:
                                    # Generic location matching
                                    if location_lower not in job_location and "remote" not in job_location:
                                        continue  # Skip this job
                            
                            # Job passed location filter, add it
                            converted_job["source"] = "scraped"
                            converted_job["priority"] = 0.7
                            all_jobs.append(converted_job)
                            scraped_count += 1
                            
                            if scraped_count >= remaining_needed:
                                break
                
                print(f"✅ Successfully processed {scraped_count} cached Redis jobs")
                
            except Exception as e:
                print(f"❌ Error fetching cached jobs from Redis: {e}")
        
        # ============= STEP 3: WEB SCRAPING IF NEEDED =============
        remaining_needed = limit - len(all_jobs)
        
        # LOOP PREVENTION: Only scrape if we have very few jobs and haven't scraped recently
        # OR if force_scrape is explicitly requested
        # For "All Locations" (default), be more conservative about scraping
        is_default_or_all_locations = (not location or location.strip() == "" or 
                                      (location and location.lower() == "all locations"))
        min_jobs_threshold = 20 if is_default_or_all_locations else max(50, limit * 0.1)
        should_scrape = (
            remaining_needed > 0 and 
            (len(all_jobs) < min_jobs_threshold or force_scrape)  # Scrape if few jobs OR force_scrape=True
        )
        
        if should_scrape:
            try:
                print(f"\n🕷️  STEP 3: Web scraping needed (need {remaining_needed} more jobs)...")
                
                self._initialize_scraper()
                
                if self.scraper:
                    print(f"🔍 Starting fresh web scraping...")
                    print(f"   Search params: keywords='{keywords}', location='{location}'")
                    
                    # LIMIT SCRAPING: Cap the number of jobs to scrape
                    max_scrape_jobs = min(remaining_needed, 100)  # Max 100 fresh jobs
                    
                    # Use broader search terms for LinkedIn scraping
                    broad_keywords = "software engineer developer python javascript"
                    
                    # Map location filter to LinkedIn-compatible location
                    if location and location.lower() == "usa":
                        broad_location = "United States"
                    elif location and location.lower() == "india":
                        broad_location = "India"
                    elif location and location.lower() == "all locations":
                        # For "All Locations", don't scrape if we have enough cached jobs
                        if len(all_jobs) >= 20:  # If we have 20+ jobs, don't scrape
                            print(f"   Skipping scraping for 'All Locations' - have {len(all_jobs)} cached jobs")
                            return all_jobs  # Return early without scraping
                        broad_location = "United States"  # Default to USA for scraping
                    elif not location or location.strip() == "":
                        # DEFAULT: No location specified - treat as "All Locations"
                        if len(all_jobs) >= 20:  # If we have 20+ jobs, don't scrape
                            print(f"   Skipping scraping for default (All Locations) - have {len(all_jobs)} cached jobs")
                            return all_jobs  # Return early without scraping
                        broad_location = "United States"  # Default to USA for scraping
                    elif location and location.strip():
                        broad_location = location  # Use the original location
                    else:
                        broad_location = "United States"  # Default to USA for empty location
                    
                    print(f"   Using broader terms: keywords='{broad_keywords}', location='{broad_location}'")
                    
                    scraped_jobs = self.scraper.get_jobs(
                        keywords=broad_keywords,
                        location=broad_location,
                        max_jobs=max_scrape_jobs,
                        job_type_filter=job_type_filter,
                        category_filter=category_filter,
                        trusted_only=trusted_only,
                        force_refresh=force_scrape
                    )
                    
                    print(f"✅ Web scraping returned {len(scraped_jobs)} fresh jobs")
                    
                    fresh_jobs_added = 0
                    for job in scraped_jobs:
                        converted_job = self._convert_scraped_job_format(job)
                        if converted_job:
                            converted_job["source"] = "fresh_scraped"
                            converted_job["priority"] = 0.5
                            all_jobs.append(converted_job)
                            fresh_jobs_added += 1
                    
                    print(f"✅ Added {fresh_jobs_added} freshly scraped jobs")
                    
                else:
                    print("❌ Web scraper not available")
                    
            except Exception as e:
                print(f"❌ Error during web scraping: {e}")
        else:
            print(f"\n⏸️  STEP 3: Skipping web scraping (have {len(all_jobs)} jobs, sufficient for now)")
        
        # ============= FINAL RESULTS =============
        print(f"\n📊 === FINAL JOB SUMMARY ===")
        jobs_lists_count = len([j for j in all_jobs if j.get('source') == 'jobs_lists'])
        cached_count = len([j for j in all_jobs if j.get('source') == 'scraped'])
        fresh_count = len([j for j in all_jobs if j.get('source') == 'fresh_scraped'])
        
        print(f"Total jobs found: {len(all_jobs)}")
        print(f"  🏢 Jobs from jobs-lists (MongoDB): {jobs_lists_count}")
        print(f"  💾 Cached jobs (Redis): {cached_count}")
        print(f"  🌐 Fresh scraped jobs: {fresh_count}")
        print(f"=============================")
        
        # Sort by priority and return limited results
        all_jobs.sort(key=lambda x: x.get('priority', 0), reverse=True)
        final_jobs = all_jobs[:limit]
        
        print(f"🎯 Returning {len(final_jobs)} jobs to recommendation system")
        return final_jobs
    
    def _matches_search_criteria(self, job_data: dict, keywords: str, location: str, 
                               job_type_filter: str, category_filter: str, trusted_only: bool) -> bool:
        """Check if a Redis job matches the search criteria"""
        try:
            # Apply location filtering for Redis jobs
            if location and location.strip() and location.lower() not in ["all locations", "all"]:
                location_lower = location.lower()
                job_location = job_data.get('location', '').lower()
                
                # Enhanced location matching for USA and India
                if location_lower == "usa":
                    usa_keywords = ['united states', 'usa', 'us', 'california', 'new york', 
                                  'texas', 'washington', 'massachusetts', 'illinois', 'colorado',
                                  ', ca', ', ny', ', tx', 'san francisco', 'los angeles', 'seattle']
                    if not any(keyword in job_location for keyword in usa_keywords):
                        return False
                    # Exclude jobs that also contain India keywords
                    india_keywords = ['india', 'mumbai', 'delhi', 'bangalore', 'bengaluru', 
                                    'hyderabad', 'chennai', 'pune', 'kolkata', 'ahmedabad']
                    if any(india_keyword in job_location for india_keyword in india_keywords):
                        return False
                elif location_lower == "india":
                    india_keywords = ['india', 'mumbai', 'delhi', 'bangalore', 'bengaluru', 
                                    'hyderabad', 'chennai', 'pune', 'kolkata', 'ahmedabad']
                    if not any(keyword in job_location for keyword in india_keywords):
                        return False
                    # Exclude jobs that also contain USA keywords
                    usa_keywords = ['united states', 'usa', 'us', 'california', 'new york', 
                                  'texas', 'washington', 'massachusetts', 'illinois', 'colorado']
                    if any(usa_keyword in job_location for usa_keyword in usa_keywords):
                        return False
                else:
                    # Generic location matching
                    if location_lower not in job_location and "remote" not in job_location:
                        return False
            
            if job_type_filter:
                job_type = job_data.get('employment_type', job_data.get('job_type', '')).lower()
                if job_type_filter.lower() not in job_type:
                    return False
            
            if category_filter and category_filter != 'All':
                job_category = job_data.get('category', '')
                if category_filter not in job_category:
                    return False
            
            if trusted_only:
                is_trusted = job_data.get('is_trusted_company', False)
                if not is_trusted:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error matching search criteria: {e}")
            return False
    
    def _convert_scraped_job_format(self, job_data: dict) -> dict:
        """Convert job data from scraper format to our expected format"""
        try:
            raw_employment_type = job_data.get('employment_type', job_data.get('job_type', 'Full-time'))
            normalized_employment_type = self._normalize_employment_type(raw_employment_type)
            
            raw_salary = job_data.get('salary', '')
            parsed_salary = self._parse_salary_string(raw_salary)
            
            return {
                "id": job_data.get('job_id', job_data.get('id', '')),
                "employer_id": job_data.get('company', job_data.get('employer_id', '')),
                "title": job_data.get('title', ''),
                "description": job_data.get('description', job_data.get('responsibilities', '')),
                "requirements": job_data.get('requirements', []) if isinstance(job_data.get('requirements'), list) else [job_data.get('requirements', '')],
                "responsibilities": job_data.get('responsibilities', []) if isinstance(job_data.get('responsibilities'), list) else [job_data.get('responsibilities', '')],
                "employment_type": normalized_employment_type,
                "salary": parsed_salary,
                "location": self._parse_location(job_data.get('location', '')),
                "skills_required": job_data.get('skills', job_data.get('skills_required', [])),
                "benefits": job_data.get('benefits', []),
                "is_active": True,
                "posted_at": self._parse_datetime(job_data.get('posted_date', job_data.get('posted_at', datetime.now().strftime('%Y-%m-%d')))),
                "expires_at": self._parse_datetime(job_data.get('expires_at', '2024-12-31')),
                "company": job_data.get('company', ''),
                "url": job_data.get('url', job_data.get('job_link', '')),
                "experience_level": job_data.get('experience_level', ''),
                "category": job_data.get('category', ''),
                "is_trusted_company": job_data.get('is_trusted_company', False),
                "remote_work": job_data.get('remote_work', job_data.get('remote', 'No'))
            }
        except Exception as e:
            logger.error(f"Error converting scraped job format: {e}")
            return None
    
    def _parse_location(self, location_str: str) -> dict:
        """Parse location string into structured format"""
        location_parts = location_str.split(',') if location_str else []
        return {
            "city": location_parts[0].strip() if location_parts else "",
            "state": location_parts[1].strip() if len(location_parts) > 1 else None,
            "country": location_parts[2].strip() if len(location_parts) > 2 else "USA",
            "remote": "remote" in location_str.lower() or "hybrid" in location_str.lower(),
            "coordinates": None
        }
    
    def _convert_jobs_lists_job(self, job_data: dict) -> dict:
        """Convert jobs-lists collection job data to our expected format"""
        try:
            skills = []
            if job_data.get('skills_required'):
                if isinstance(job_data['skills_required'], list):
                    skills = job_data['skills_required']
                else:
                    skills = [skill.strip() for skill in job_data['skills_required'].split(',') if skill.strip()]
            
            location_data = job_data.get('location', {})
            if isinstance(location_data, str):
                location = self._parse_location(location_data)
            else:
                location = location_data
            
            raw_job_type = job_data.get('employment_type', 'Full-time')
            normalized_employment_type = self._normalize_employment_type(raw_job_type)
            
            salary_data = job_data.get('salary', {})
            if isinstance(salary_data, str):
                salary_data = self._parse_salary_string(salary_data)
            
            return {
                "id": str(job_data.get("_id", "")),
                "employer_id": job_data.get("employer_id", ""),
                "title": job_data.get("title", ""),
                "description": job_data.get("description", ""),
                "requirements": job_data.get("requirements", []),
                "responsibilities": [],
                "employment_type": normalized_employment_type,
                "salary": salary_data,
                "location": location,
                "skills_required": skills,
                "benefits": [],
                "is_active": True,
                "posted_at": job_data.get("posted_at", job_data.get("created_at", "2024-01-01")),
                "expires_at": None,  # Make it optional to avoid validation errors
                "category": job_data.get("category", ""),
                "source": job_data.get("source", "jobs_lists"),
                "company": job_data.get("company", ""),
                "url": job_data.get("url", ""),
                "experience_level": job_data.get("experience_level", "")
            }
        except Exception as e:
            print(f"Error converting jobs-lists job: {e}")
            return None

    def _convert_mongo_job(self, job_data: dict) -> dict:
        """Convert MongoDB job data to our expected format"""
        try:
            skills = []
            if job_data.get('skills'):
                skills = [skill.strip() for skill in job_data['skills'].split(',') if skill.strip()]
            
            location_str = job_data.get('location_1', '')
            location = self._parse_location(location_str)
            
            raw_job_type = job_data.get('job_type', 'Full-time')
            normalized_employment_type = self._normalize_employment_type(raw_job_type)
            
            return {
                "id": str(job_data.get("_id", "")),
                "employer_id": job_data.get("employer_id_1", ""),
                "title": job_data.get("title", ""),
                "description": job_data.get("description_text", ""),
                "requirements": [job_data.get("requirements", "")] if job_data.get("requirements") else [],
                "responsibilities": [],
                "employment_type": normalized_employment_type,
                "salary": {"min": 0, "max": 0, "currency": "USD", "is_public": False},
                "location": location,
                "skills_required": skills,
                "benefits": [],
                "is_active": True,
                "posted_at": job_data.get("created_at", "2024-01-01"),
                "expires_at": None,  # Make it optional to avoid validation errors
                "category": job_data.get("category", ""),
                "source": job_data.get("source", "Manual"),
                "job_link": job_data.get("job_link", ""),
                "posted_time": job_data.get("posted_time", "")
            }
        except Exception as e:
            print(f"Error converting MongoDB job: {e}")
            return None
    
    def _parse_datetime(self, date_input) -> datetime:
        """Parse various date formats into datetime objects"""
        from datetime import datetime
        
        if isinstance(date_input, datetime):
            return date_input
        
        if isinstance(date_input, str):
            try:
                # Handle YYYY-MM-DD format
                if len(date_input) == 10 and date_input.count('-') == 2:
                    return datetime.strptime(date_input, '%Y-%m-%d')
                # Handle ISO format
                elif 'T' in date_input or 'Z' in date_input:
                    return datetime.fromisoformat(date_input.replace('Z', '+00:00'))
                else:
                    # Try parsing as ISO format
                    return datetime.fromisoformat(date_input)
            except:
                # Default fallback
                return datetime(2024, 1, 1)
        
        # Default fallback for any other type
        return datetime(2024, 1, 1)

    def _convert_scraped_job(self, job_data: dict) -> dict:
        """Convert scraped job data to our expected format"""
        try:
            skills = []
            if job_data.get('skills'):
                try:
                    skills = json.loads(job_data['skills']) if isinstance(job_data['skills'], str) else job_data['skills']
                except:
                    skills = job_data['skills'].split(',') if isinstance(job_data['skills'], str) else []
            
            requirements = []
            if job_data.get('requirements'):
                try:
                    requirements = json.loads(job_data['requirements']) if isinstance(job_data['requirements'], str) else job_data['requirements']
                except:
                    requirements = [job_data['requirements']] if job_data['requirements'] else []
            
            responsibilities = []
            if job_data.get('responsibilities'):
                try:
                    responsibilities = json.loads(job_data['responsibilities']) if isinstance(job_data['responsibilities'], str) else job_data['responsibilities']
                except:
                    responsibilities = [job_data['responsibilities']] if job_data['responsibilities'] else []
            
            # Handle salary - be more flexible and handle empty values
            raw_salary = job_data.get('salary', '')
            if raw_salary and raw_salary.strip():
                parsed_salary = self._parse_salary_string(raw_salary)
            else:
                # Default salary structure for empty salary
                parsed_salary = {
                    "min": 0,
                    "max": 0,
                    "currency": "USD",
                    "is_public": False
                }
            
            location = self._parse_location(job_data.get('location', ''))
            if not location["country"]:
                location["country"] = "India"
            
            raw_employment_type = job_data.get('employment_type', 'full_time')
            normalized_employment_type = self._normalize_employment_type(raw_employment_type)
            
            # Generate a unique ID if not present - handle Redis data structure
            job_id = job_data.get('job_id') or job_data.get('_id') or str(hash(job_data.get('title', '')))
            
            # Handle posted_at and expires_at dates using helper method
            posted_at = self._parse_datetime(job_data.get('posted_date', job_data.get('posted_at', '2024-01-01')))
            expires_at = self._parse_datetime(job_data.get('expires_at', '2024-12-31'))
            
            # Create a robust job object with all required fields
            job_obj = {
                "id": str(job_id),
                "employer_id": job_data.get('company', 'unknown'),
                "title": job_data.get('title', 'Untitled Job'),
                "description": job_data.get('description', job_data.get('responsibilities', 'No description available')),
                "requirements": requirements if requirements else ['No specific requirements listed'],
                "responsibilities": responsibilities if responsibilities else ['No specific responsibilities listed'],
                "employment_type": normalized_employment_type,
                "salary": parsed_salary,
                "location": location,
                "skills_required": skills if skills else [],
                "benefits": [],
                "is_active": True,
                "posted_at": posted_at,  # Use the parsed datetime
                "expires_at": expires_at,  # Use the parsed datetime
                "company": job_data.get('company', 'Unknown Company'),
                "url": job_data.get('url', ''),
                "experience_level": job_data.get('experience_level', 'Not specified'),
                "category": job_data.get('category', 'General'),
                "is_trusted_company": job_data.get('is_trusted_company', False)
            }
            
            return job_obj
        except Exception as e:
            print(f"Error converting job data: {e}")
            return None
    
    async def get_user_swipes(self, clerk_id: str) -> List[dict]:
        """Get all swipes for a user from Redis"""
        swipe_keys = await self.redis_client.keys(f"swipe:{clerk_id}:*")
        swipes = []
        
        for key in swipe_keys:
            swipe_data = await self.redis_client.get(key)
            if swipe_data:
                swipe = json.loads(swipe_data)
                if not swipe.get("undone", False):
                    swipes.append(swipe)
        
        return swipes
    
    async def get_job_by_id(self, job_id: str) -> Optional[dict]:
        """Get job details by ID from Redis"""
        job_data = await self.redis_client.get(f"job:{job_id}")
        if job_data:
            return json.loads(job_data)
        return None
    
    async def enqueue_user_jobs(self, clerk_id: str, jobs: List[dict]) -> int:
        """Enqueue related jobs into a per-user Redis list queue.
        Stores as JSON strings; returns number enqueued.
        Key format: queue:recommendations:{clerk_id}
        """
        try:
            if not jobs:
                return 0
            key = f"queue:recommendations:{clerk_id}"
            # Avoid duplicates by using a set of job ids currently in queue
            existing = await self.redis_client.lrange(key, 0, -1)
            existing_ids = set()
            for item in existing:
                try:
                    doc = json.loads(item)
                    jid = str(doc.get("_id") or doc.get("id") or "")
                    if jid:
                        existing_ids.add(jid)
                except Exception:
                    continue
            to_push = []
            def _to_json_safe(d: dict) -> dict:
                def convert(obj):
                    if isinstance(obj, datetime):
                        return obj.isoformat()
                    return obj
                return {k: convert(v) for k, v in d.items()}

            for job in jobs:
                jid = str(job.get("_id") or job.get("id") or "")
                if not jid or jid in existing_ids:
                    continue
                to_push.append(json.dumps(_to_json_safe(job)))
            enqueued = 0
            if to_push:
                # Push to the right to preserve order
                enqueued = await self.redis_client.rpush(key, *to_push)
                # Set a TTL of 48 hours
                await self.redis_client.expire(key, 48 * 3600)
            return int(enqueued if enqueued is not None else 0)
        except Exception as e:
            logger.error(f"Failed to enqueue jobs for {clerk_id}: {e}")
            return 0
    
    async def get_scraper_stats(self) -> dict:
        """Get web scraper statistics"""
        try:
            self._initialize_scraper()
            if self.scraper:
                return {
                    "cache_status": self.scraper.get_cache_status(),
                    "job_statistics": self.scraper.get_job_statistics(),
                    "redis_health": self.scraper.get_redis_health(),
                    "available_categories": self.scraper.get_job_categories(),
                    "trusted_companies_count": len(self.scraper.get_trusted_companies())
                }
            else:
                return {"error": "Scraper not available"}
        except Exception as e:
            return {"error": str(e)}
    
    async def clear_job_cache(self, expired_only: bool = True) -> dict:
        """Clear job cache"""
        try:
            self._initialize_scraper()
            if self.scraper:
                cleared_count = self.scraper.clear_cache(expired_only=expired_only)
                return {
                    "success": True,
                    "cleared_count": cleared_count,
                    "expired_only": expired_only
                }
            else:
                return {"success": False, "error": "Scraper not available"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ===== Saved/Liked jobs persistence in MongoDB =====
    async def save_user_job_action(self, user_id: str, job_id: str, action: str, job_snapshot: Optional[dict] = None) -> bool:
        """Persist a user's job action (e.g., save/like/dislike) to MongoDB.

        Collection: users.user_job_actions
        Unique per (user_id, job_id, action)
        """
        try:
            collection = self.users_db.user_job_actions
            now = datetime.utcnow()
            
            logger.info(f"💾 Saving {action} action: user={user_id[:8]}..., job={job_id[:8]}...")
            
            update_doc = {"$set": {"user_id": user_id, "job_id": job_id, "action": action, "updated_at": now},
                          "$setOnInsert": {"created_at": now}}
            if job_snapshot:
                update_doc["$set"]["job_snapshot"] = job_snapshot
            
            result = await collection.update_one(
                {"user_id": user_id, "job_id": job_id, "action": action},
                update_doc,
                upsert=True,
            )
            
            if result.upserted_id:
                logger.info(f"✅ New {action} saved (ID: {str(result.upserted_id)[:8]}...)")
            elif result.modified_count > 0:
                logger.info(f"✅ {action.capitalize()} updated")
            else:
                logger.debug(f"ℹ️  {action.capitalize()} already exists (no changes)")
            
            return True
        except Exception as e:
            logger.error(f"❌ Failed to save user job action: {e}")
            print(f"❌ Error details: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    async def remove_saved_job(self, user_id: str, job_id: str) -> bool:
        """Remove a saved job document for a user."""
        try:
            logger.info(f"🗑️  Removing saved job: user={user_id[:8]}..., job={job_id[:8]}...")
            
            result = await self.users_db.user_job_actions.delete_one(
                {"user_id": user_id, "job_id": job_id, "action": "save"}
            )
            
            if result.deleted_count > 0:
                logger.info(f"✅ Saved job removed successfully")
                return True
            else:
                logger.warning(f"⚠️  Saved job not found (may already be removed)")
                return False
        except Exception as e:
            logger.error(f"❌ Failed to remove saved job: {e}")
            return False

    async def get_user_saved_jobs(self, user_id: str) -> List[dict]:
        """Return saved jobs with enriched job data when available."""
        try:
            cursor = self.users_db.user_job_actions.find({"user_id": user_id, "action": "save"})
            items = [doc async for doc in cursor]
            results: List[dict] = []
            for doc in items:
                jid = str(doc.get("job_id"))
                job_data = await self.get_job_by_id(jid)
                if job_data:
                    # Normalize to JobPosting fields expected by frontend
                    job_obj = self._convert_job_data(job_data)
                    if job_obj:
                        results.append(job_obj)
                else:
                    # Fallback to stored snapshot
                    snapshot = doc.get("job_snapshot") or {}
                    snapshot_id = snapshot.get("id") or snapshot.get("_id") or jid
                    results.append({"id": str(snapshot_id), **snapshot})
            return results
        except Exception as e:
            logger.error(f"Failed to fetch saved jobs: {e}")
            return []

    async def get_user_liked_jobs(self, user_id: str) -> List[dict]:
        """Return liked jobs with enriched job data when available."""
        try:
            cursor = self.users_db.user_job_actions.find({"user_id": user_id, "action": {"$in": ["like", "super_like"]}})
            items = [doc async for doc in cursor]
            results: List[dict] = []
            for doc in items:
                jid = str(doc.get("job_id"))
                job_data = await self.get_job_by_id(jid)
                if job_data:
                    # Normalize to JobPosting fields expected by frontend
                    job_obj = self._convert_job_data(job_data)
                    if job_obj:
                        results.append(job_obj)
                else:
                    # Fallback to stored snapshot
                    snapshot = doc.get("job_snapshot") or {}
                    snapshot_id = snapshot.get("id") or snapshot.get("_id") or jid
                    results.append({"id": str(snapshot_id), **snapshot})
            return results
        except Exception as e:
            logger.error(f"Failed to fetch liked jobs: {e}")
            return []

    async def get_user_disliked_jobs(self, user_id: str) -> List[dict]:
        """Return disliked jobs with enriched job data when available."""
        try:
            cursor = self.users_db.user_job_actions.find({"user_id": user_id, "action": "dislike"})
            items = [doc async for doc in cursor]
            results: List[dict] = []
            for doc in items:
                jid = str(doc.get("job_id"))
                job_data = await self.get_job_by_id(jid)
                if job_data:
                    # Normalize to JobPosting fields expected by frontend
                    job_obj = self._convert_job_data(job_data)
                    if job_obj:
                        results.append(job_obj)
                else:
                    # Fallback to stored snapshot
                    snapshot = doc.get("job_snapshot") or {}
                    snapshot_id = snapshot.get("id") or snapshot.get("_id") or jid
                    results.append({"id": str(snapshot_id), **snapshot})
            return results
        except Exception as e:
            logger.error(f"Failed to fetch disliked jobs: {e}")
            return []

    async def get_user_action_job_ids(self, user_id: str, actions: List[str]) -> List[str]:
        """Fetch job ids from MongoDB where user performed any of the given actions."""
        try:
            cursor = self.users_db.user_job_actions.find({"user_id": user_id, "action": {"$in": actions}})
            ids: List[str] = []
            async for doc in cursor:
                jid = str(doc.get("job_id"))
                if jid:
                    ids.append(jid)
            return ids
        except Exception as e:
            logger.error(f"Failed to fetch user action job ids: {e}")
            return []
    
    def calculate_skill_match_score(self, user_skills: list, job_skills: list) -> float:
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

# Singleton instance
db = Database()