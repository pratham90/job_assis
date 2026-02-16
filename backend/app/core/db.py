from typing import List, Optional
from bson import ObjectId
import os
import json
import redis.asyncio as redis
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import logging
from datetime import datetime, timedelta
import re
import asyncio
import concurrent.futures
import threading
import time
from functools import lru_cache
import weakref

logger = logging.getLogger(__name__)

load_dotenv()
redis_uri = os.getenv(
    "REDIS_URI", "redis://default:liiSkjZQkhWPULcAcQ2dV0MZzy82wj2B@redis-13364.c56.east-us.azure.redns.redis-cloud.com:13364/0")
mongo_uri = os.getenv("MONGO_URI", os.getenv(
    "MONGODB_URI", "mongodb+srv://Jobs:Jobs-provider@jobs.2m8l8hb.mongodb.net"))


class Database:
    def __init__(self):
        # Vercel-optimized connection settings for serverless
        self.redis_client = redis.from_url(
            redis_uri,
            decode_responses=True,
            max_connections=10,  # Reduced for serverless
            retry_on_timeout=True,
            socket_keepalive=False,  # Disabled for serverless
            socket_keepalive_options={},
            health_check_interval=0  # Disabled for serverless
        )

        # Serverless-optimized MongoDB connection
        self.mongo_client = AsyncIOMotorClient(
            mongo_uri,
            maxPoolSize=10,  # Reduced for serverless
            minPoolSize=1,  # Minimum for serverless
            maxIdleTimeMS=10000,  # 10 seconds (shorter for serverless)
            serverSelectionTimeoutMS=3000,  # 3 seconds
            connectTimeoutMS=5000,  # 5 seconds
            socketTimeoutMS=10000,  # 10 seconds
            retryWrites=True,
            retryReads=True
        )

        # Use the Jobs database for jobs
        self.mongo_db = self.mongo_client.Jobs
        # Connect to users database for user profiles and skills
        self.users_db = self.mongo_client.users
        self.scraper = None

        # Serverless-optimized performance settings
        self._cache = {}  # Simple in-memory cache
        self._cache_lock = threading.RLock()
        self._cache_ttl = 300  # 5 minutes TTL

        # Reduced thread pool for serverless environment
        self._thread_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=2)

        logger.info("🔗 Vercel-optimized database connections initialized:")
        logger.info(
            f"   📦 Redis: {redis_uri.split('@')[1] if '@' in redis_uri else 'localhost'}")
        logger.info(f"   🍃 MongoDB: Serverless-optimized connection pooling")
        logger.info(f"   🧵 Thread pool: 2 workers (serverless)")
        logger.info(f"   💾 Cache: In-memory with 5min TTL")
        logger.info(f"   🚀 Environment: Vercel serverless")

    # ===== NEW: SWIPE LIMIT TRACKING METHODS =====

    async def check_and_increment_swipe_limit(self, user_id: str) -> dict:
        """
        Check if user has reached daily swipe limit (20 swipes per 24 hours).
        If not, increment the swipe count.
        Returns: {
            "allowed": bool,
            "remaining": int,
            "reset_at": datetime,
            "total_today": int
        }
        """
        try:
            collection = self.users_db.user_swipe_limits
            now = datetime.utcnow()
            today_start = datetime(now.year, now.month,
                                   now.day)  # Midnight UTC
            tomorrow_start = today_start + timedelta(days=1)

            # Find or create today's swipe limit document
            swipe_doc = await collection.find_one({
                "user_id": user_id,
                "date": today_start
            })

            if not swipe_doc:
                # Create new document for today
                swipe_doc = {
                    "user_id": user_id,
                    "date": today_start,
                    "swipe_count": 0,
                    "reset_at": tomorrow_start,
                    "created_at": now,
                    "updated_at": now
                }
                await collection.insert_one(swipe_doc)
                logger.info(
                    f"📊 Created new swipe limit document for user: {user_id[:8]}...")

            current_count = swipe_doc.get("swipe_count", 0)
            limit = 20

            # Check if limit reached
            if current_count >= limit:
                logger.warning(
                    f"🚫 User {user_id[:8]}... reached daily swipe limit ({current_count}/{limit})")
                return {
                    "allowed": False,
                    "remaining": 0,
                    "reset_at": tomorrow_start,
                    "total_today": current_count,
                    "limit": limit
                }

            # Increment swipe count
            result = await collection.update_one(
                {"user_id": user_id, "date": today_start},
                {
                    "$inc": {"swipe_count": 1},
                    "$set": {"updated_at": now}
                }
            )

            new_count = current_count + 1
            remaining = limit - new_count

            logger.info(
                f"✅ Swipe counted: user={user_id[:8]}..., count={new_count}/{limit}, remaining={remaining}")

            return {
                "allowed": True,
                "remaining": remaining,
                "reset_at": tomorrow_start,
                "total_today": new_count,
                "limit": limit
            }

        except Exception as e:
            logger.error(f"❌ Failed to check/increment swipe limit: {e}")
            # On error, allow the swipe (fail-open approach)
            return {
                "allowed": True,
                "remaining": 20,
                "reset_at": datetime.utcnow() + timedelta(days=1),
                "total_today": 0,
                "limit": 20,
                "error": str(e)
            }

    async def get_swipe_limit_status(self, user_id: str) -> dict:
        """
        Get current swipe limit status for a user without incrementing.
        Returns: {
            "remaining": int,
            "total_today": int,
            "limit": int,
            "reset_at": datetime
        }
        """
        try:
            collection = self.users_db.user_swipe_limits
            now = datetime.utcnow()
            today_start = datetime(now.year, now.month, now.day)
            tomorrow_start = today_start + timedelta(days=1)

            swipe_doc = await collection.find_one({
                "user_id": user_id,
                "date": today_start
            })

            limit = 20
            total_today = swipe_doc.get("swipe_count", 0) if swipe_doc else 0
            remaining = max(0, limit - total_today)

            return {
                "remaining": remaining,
                "total_today": total_today,
                "limit": limit,
                "reset_at": tomorrow_start
            }

        except Exception as e:
            logger.error(f"❌ Failed to get swipe limit status: {e}")
            return {
                "remaining": 20,
                "total_today": 0,
                "limit": 20,
                "reset_at": datetime.utcnow() + timedelta(days=1),
                "error": str(e)
            }

    async def reset_old_swipe_limits(self):
        """
        Cleanup old swipe limit documents (older than 7 days).
        This can be called periodically or on server startup.
        """
        try:
            collection = self.users_db.user_swipe_limits
            cutoff_date = datetime.utcnow() - timedelta(days=7)

            result = await collection.delete_many({
                "date": {"$lt": cutoff_date}
            })

            if result.deleted_count > 0:
                logger.info(
                    f"🧹 Cleaned up {result.deleted_count} old swipe limit documents")

            return result.deleted_count

        except Exception as e:
            logger.error(f"❌ Failed to reset old swipe limits: {e}")
            return 0

    async def ensure_swipe_limit_indexes(self):
        """Create indexes for swipe limit collection"""
        try:
            collection = self.users_db.user_swipe_limits

            # Compound index on user_id and date for fast lookups
            await collection.create_index(
                [("user_id", 1), ("date", 1)],
                unique=True,
                name="user_date_unique"
            )
            logger.info(
                "   ✅ Unique compound index: (user_id, date) for swipe limits")

            # TTL index to auto-delete old documents after 7 days
            await collection.create_index(
                [("date", 1)],
                expireAfterSeconds=7*24*3600,  # 7 days in seconds
                name="date_ttl"
            )
            logger.info("   ✅ TTL index: date (7 days) for auto-cleanup")

        except Exception as e:
            logger.warning(f"⚠️  Swipe limit index creation warning: {e}")

    # ===== END OF NEW SWIPE LIMIT METHODS =====

    def _get_cache_key(self, prefix: str, *args) -> str:
        """Generate cache key from prefix and arguments"""
        return f"{prefix}:{':'.join(str(arg) for arg in args)}"

    def _get_from_cache(self, key: str):
        """Get value from cache with TTL check"""
        with self._cache_lock:
            if key in self._cache:
                value, timestamp = self._cache[key]
                if time.time() - timestamp < self._cache_ttl:
                    return value
                else:
                    del self._cache[key]
            return None

    def _set_cache(self, key: str, value):
        """Set value in cache with timestamp"""
        with self._cache_lock:
            self._cache[key] = (value, time.time())

    def _clear_cache(self):
        """Clear all cached data"""
        with self._cache_lock:
            self._cache.clear()

    async def get_user_by_clerk_id_cached(self, clerk_id: str) -> Optional[dict]:
        """Get user by clerk ID with caching"""
        cache_key = self._get_cache_key("user", clerk_id)
        cached_user = self._get_from_cache(cache_key)

        if cached_user is not None:
            logger.debug(f"📋 Cache hit for user: {clerk_id[:8]}...")
            return cached_user

        # Cache miss - fetch from database
        user = await self.get_user_by_clerk_id(clerk_id)
        if user:
            self._set_cache(cache_key, user)
            logger.debug(f"📋 Cache miss - stored user: {clerk_id[:8]}...")

        return user

    async def ensure_indexes(self):
        """Create unique indexes to prevent duplicate job actions and setup swipe limits"""
        try:
            # Create unique compound index on user_job_actions collection
            # This ensures no duplicate (user_id, job_id, action) combinations
            await self.users_db.user_job_actions.create_index(
                [("user_id", 1), ("job_id", 1), ("action", 1)],
                unique=True,
                name="unique_user_job_action"
            )
            logger.info(
                "   ✅ Unique compound index: (user_id, job_id, action)")

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

            # NEW: Ensure swipe limit indexes
            await self.ensure_swipe_limit_indexes()

        except Exception as e:
            logger.warning(
                f"⚠️  Index creation warning (indexes may already exist): {e}")

    def _initialize_scraper(self):
        """Initialize the web scraper only when needed"""
        if self.scraper is None:
            try:
                from app.job_scraper import RedisCachedJobScraper

                redis_parts = redis_uri.split('@')
                if len(redis_parts) == 2:
                    auth_part = redis_parts[0].split('//')[1]
                    host_part = redis_parts[1]
                    password = auth_part.split(
                        ':')[1] if ':' in auth_part else None
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
            logger.debug(f"Searching for user with clerk_id: {clerk_id}")

            # Get user profile with skills from users/Profile collection
            profile_data = await self.users_db.Profile.find_one({"clerk_id": clerk_id})
            if profile_data:
                logger.info(
                    f"Profile found with skills: {profile_data.get('skills', [])}")
                profile_data["_id"] = str(profile_data["_id"])
                return profile_data
            else:
                logger.warning(f"User with clerk_id '{clerk_id}' not found")
                return None

        except Exception as e:
            logger.error(f"Error fetching user from MongoDB: {e}")
            return None

    async def create_user(self, user_data: dict) -> Optional[str]:
        """Create a new user in users/Profile collection"""
        try:
            logger.info("Creating user in users/Profile collection")
            logger.debug(f"User data: {user_data}")

            # Store user in users/Profile collection
            result = await self.users_db.Profile.insert_one(user_data)
            user_id = str(result.inserted_id)
            logger.info(f"User created with ID: {user_id}")

            # Verify the user was created
            verify_user = await self.users_db.Profile.find_one({"_id": result.inserted_id})
            if verify_user:
                logger.info(
                    f"User verification successful: {verify_user.get('first_name')} {verify_user.get('last_name')}")
            else:
                logger.error("User verification failed!")

            return user_id
        except Exception as e:
            logger.error(f"Error creating user: {e}")
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
        """Get all active job postings with optimized All Locations support"""
        start_time = time.time()
        all_jobs = []

        # Normalize location input
        is_all_locations = (
            not location or
            location.strip() == "" or
            location.lower() in ["all locations", "all", "global"]
        )

        print(f"🎯 Starting job search (limit: {limit})")
        print(
            f"   Keywords: {keywords}, Location: {'All Locations' if is_all_locations else location}")
        print(
            f"   Filters: job_type={job_type_filter}, category={category_filter}, trusted={trusted_only}")

        # ============= STEP 1: MONGODB JOBS (Jobs/jobs-lists) =============
        try:
            print(f"\n📋 STEP 1: Fetching from MongoDB Jobs/jobs-lists...")
            posted_jobs = await self.mongo_db["jobs-lists"].find(
                {"is_active": {"$ne": False}},
                {
                    "_id": 1, "employer_id": 1, "title": 1, "description": 1,
                    "employment_type": 1, "location": 1, "skills_required": 1,
                    "requirements": 1, "category": 1, "source": 1, "created_at": 1,
                    "posted_at": 1, "salary": 1, "company": 1, "url": 1, "experience_level": 1
                }
            ).to_list(200)  # Increased limit for all locations

            print(f"✅ Found {len(posted_jobs)} jobs in MongoDB")

            # Parallel processing
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                job_futures = [executor.submit(self._convert_jobs_lists_job, job_data)
                               for job_data in posted_jobs]

                for future in concurrent.futures.as_completed(job_futures):
                    converted_job = future.result()
                    if converted_job:
                        # Apply location filter if NOT "All Locations"
                        if not is_all_locations:
                            if not self._matches_location_filter(converted_job, location):
                                continue

                        converted_job["source"] = "jobs_lists"
                        converted_job["priority"] = 1.0
                        all_jobs.append(converted_job)

            print(f"✅ Processed {len(all_jobs)} MongoDB jobs")

        except Exception as e:
            print(f"❌ Error fetching MongoDB jobs: {e}")

        # ============= STEP 2: REDIS CACHED JOBS =============
        remaining_needed = limit - len(all_jobs)

        if remaining_needed > 0:
            try:
                print(
                    f"\n🔄 STEP 2: Fetching from Redis (need {remaining_needed} more)...")

                job_ids = []

                if is_all_locations:
                    # **KEY FIX**: Fetch from ALL clusters for "All Locations"
                    print(f"📍 All Locations mode - fetching from ALL clusters")

                    clusters_to_fetch = ["usa", "india", "global"]

                    # Fetch job IDs from all clusters concurrently
                    async def fetch_cluster_jobs(cluster_name):
                        cluster_key = f"cluster:{cluster_name}:jobs"
                        try:
                            cluster_job_ids = await self.redis_client.smembers(cluster_key)
                            ids = [job_id.decode('utf-8') if isinstance(job_id, bytes) else job_id
                                   for job_id in cluster_job_ids]
                            print(f"   📊 {cluster_name}: {len(ids)} jobs")
                            return ids
                        except Exception as e:
                            print(
                                f"   ⚠️  Error fetching {cluster_name} cluster: {e}")
                            return []

                    # Fetch all clusters in parallel
                    cluster_results = await asyncio.gather(
                        *[fetch_cluster_jobs(cluster) for cluster in clusters_to_fetch]
                    )

                    # Combine and deduplicate job IDs
                    for cluster_ids in cluster_results:
                        job_ids.extend(cluster_ids)

                    job_ids = list(set(job_ids))  # Remove duplicates
                    print(
                        f"✅ Total unique jobs across all clusters: {len(job_ids)}")

                else:
                    # Location-specific cluster fetch
                    location_lower = location.lower()

                    if any(kw in location_lower for kw in ['usa', 'united states', 'us']):
                        cluster_name = "usa"
                    elif any(kw in location_lower for kw in ['india', 'mumbai', 'delhi', 'bangalore']):
                        cluster_name = "india"
                    else:
                        cluster_name = "global"

                    cluster_key = f"cluster:{cluster_name}:jobs"
                    print(f"📍 Fetching from cluster: {cluster_name}")

                    cluster_job_ids = await self.redis_client.smembers(cluster_key)
                    job_ids = [job_id.decode('utf-8') if isinstance(job_id, bytes) else job_id
                               for job_id in cluster_job_ids]

                    print(
                        f"📊 Found {len(job_ids)} jobs in {cluster_name} cluster")

                # Process jobs in chunks
                # Fetch extra for filtering
                max_jobs_to_process = min(len(job_ids), remaining_needed * 2)
                chunk_size = 25
                job_chunks = [job_ids[i:i + chunk_size]
                              for i in range(0, max_jobs_to_process, chunk_size)]

                # Concurrent Redis fetch
                async def fetch_job_chunk(chunk):
                    pipeline = self.redis_client.pipeline()
                    for job_id in chunk:
                        pipeline.hgetall(f"job:{job_id}")
                    return await pipeline.execute()

                chunk_results = await asyncio.gather(*[fetch_job_chunk(chunk) for chunk in job_chunks])

                # Flatten results
                job_data_list = [
                    job_data for chunk_result in chunk_results for job_data in chunk_result]

                print(f"📊 Processing {len(job_data_list)} Redis jobs")

                # Parallel processing with deduplication
                seen_job_ids = set()
                seen_job_ids_lock = threading.Lock()

                def process_job_batch(job_batch):
                    batch_results = []
                    for job_data in job_batch:
                        if not job_data:
                            continue

                        job_id = job_data.get('job_id', '')

                        with seen_job_ids_lock:
                            if job_id in seen_job_ids:
                                continue
                            seen_job_ids.add(job_id)

                        converted_job = self._convert_scraped_job(job_data)
                        if converted_job:
                            # Apply location filter if NOT "All Locations"
                            if not is_all_locations:
                                if not self._matches_location_filter(converted_job, location):
                                    continue

                            converted_job["source"] = "scraped"
                            converted_job["priority"] = 0.7
                            batch_results.append(converted_job)

                    return batch_results

                # Process in parallel
                batch_size = 20
                job_batches = [job_data_list[i:i + batch_size]
                               for i in range(0, len(job_data_list), batch_size)]

                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                    batch_futures = [executor.submit(process_job_batch, batch)
                                     for batch in job_batches]

                    for future in concurrent.futures.as_completed(batch_futures):
                        all_jobs.extend(future.result())

                print(
                    f"✅ Processed {len(all_jobs) - len([j for j in all_jobs if j.get('source') == 'jobs_lists'])} Redis jobs")

            except Exception as e:
                print(f"❌ Error fetching Redis jobs: {e}")

        # ============= STEP 3: WEB SCRAPING (MINIMAL) =============
        remaining_needed = limit - len(all_jobs)

        # Scraping threshold - much higher for "All Locations"
        min_threshold = 50 if is_all_locations else 20
        should_scrape = remaining_needed > 0 and len(
            all_jobs) < min_threshold and not is_all_locations

        if should_scrape or force_scrape:
            try:
                print(f"\n🕷️  STEP 3: Web scraping...")
                self._initialize_scraper()

                if self.scraper:
                    scrape_location = "United States" if location.lower() == "usa" else location
                    max_scrape = min(remaining_needed, 50)

                    scraped_jobs = self.scraper.get_jobs(
                        keywords=keywords,
                        location=scrape_location,
                        max_jobs=max_scrape,
                        job_type_filter=job_type_filter,
                        category_filter=category_filter,
                        trusted_only=trusted_only,
                        force_refresh=force_scrape
                    )

                    for job in scraped_jobs:
                        converted_job = self._convert_scraped_job_format(job)
                        if converted_job:
                            converted_job["source"] = "fresh_scraped"
                            converted_job["priority"] = 0.5
                            all_jobs.append(converted_job)

                    print(f"✅ Added {len(scraped_jobs)} fresh jobs")
            except Exception as e:
                print(f"❌ Scraping error: {e}")
        else:
            print(
                f"\n⏸️  STEP 3: Skipping scraping (have {len(all_jobs)} jobs)")

        # ============= FINAL RESULTS =============
        print(f"\n📊 === SUMMARY ===")
        print(f"Total jobs: {len(all_jobs)}")
        print(
            f"  MongoDB: {len([j for j in all_jobs if j.get('source') == 'jobs_lists'])}")
        print(
            f"  Redis: {len([j for j in all_jobs if j.get('source') == 'scraped'])}")
        print(
            f"  Fresh: {len([j for j in all_jobs if j.get('source') == 'fresh_scraped'])}")
        print(f"⚡ Execution: {time.time() - start_time:.2f}s")

        # Sort and limit
        all_jobs.sort(key=lambda x: x.get('priority', 0), reverse=True)
        return all_jobs[:limit]

    def _matches_location_filter(self, job_data: dict, location: str) -> bool:
        """Check if a job matches the location filter"""
        try:
            if not location or not location.strip() or location.lower() in ["all locations", "all"]:
                return True  # No location filter applied

            location_lower = location.lower()

            # Handle different location data formats
            if isinstance(job_data.get('location'), dict):
                # Structured location format
                job_location_dict = job_data['location']
                job_location_str = f"{job_location_dict.get('city', '')} {job_location_dict.get('state', '')} {job_location_dict.get('country', '')}".strip(
                ).lower()
                is_remote = job_location_dict.get('remote', False)
            else:
                # String location format
                job_location_str = str(job_data.get('location', '')).lower()
                is_remote = "remote" in job_location_str or "hybrid" in job_location_str

            # Enhanced location matching for USA and India
            if location_lower == "usa":
                usa_keywords = ['united states', 'usa', 'us', 'california', 'new york',
                                'texas', 'washington', 'massachusetts', 'illinois', 'colorado',
                                ', ca', ', ny', ', tx', 'san francisco', 'los angeles', 'seattle']
                if not any(keyword in job_location_str for keyword in usa_keywords) and not is_remote:
                    return False
                # Exclude jobs that also contain India keywords
                india_keywords = ['india', 'mumbai', 'delhi', 'bangalore', 'bengaluru',
                                  'hyderabad', 'chennai', 'pune', 'kolkata', 'ahmedabad']
                if any(india_keyword in job_location_str for india_keyword in india_keywords):
                    return False
            elif location_lower == "india":
                india_keywords = ['india', 'mumbai', 'delhi', 'bangalore', 'bengaluru',
                                  'hyderabad', 'chennai', 'pune', 'kolkata', 'ahmedabad']
                if not any(keyword in job_location_str for keyword in india_keywords) and not is_remote:
                    return False
                # Exclude jobs that also contain USA keywords
                usa_keywords = ['united states', 'usa', 'us', 'california', 'new york',
                                'texas', 'washington', 'massachusetts', 'illinois', 'colorado']
                if any(usa_keyword in job_location_str for usa_keyword in usa_keywords):
                    return False
            else:
                # Generic location matching
                if location_lower not in job_location_str and not is_remote:
                    return False

            return True

        except Exception as e:
            logger.error(f"Error matching location filter: {e}")
            return False

    def _matches_search_criteria(self, job_data: dict, keywords: str, location: str,
                                 job_type_filter: str, category_filter: str, trusted_only: bool) -> bool:
        """Check if a Redis job matches the search criteria"""
        try:
            # Apply location filtering for Redis jobs
            if not self._matches_location_filter(job_data, location):
                return False

            if job_type_filter:
                job_type = job_data.get(
                    'employment_type', job_data.get('job_type', '')).lower()
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
            raw_employment_type = job_data.get(
                'employment_type', job_data.get('job_type', 'Full-time'))
            normalized_employment_type = self._normalize_employment_type(
                raw_employment_type)

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

    def _convert_job_data(self, job_data: dict) -> dict:
        """Convert job data to standardized format for frontend consumption."""
        try:
            if not job_data:
                return None

            # Handle different job data sources
            if 'title' in job_data and 'company' in job_data:
                # This looks like a jobs-lists or Redis job
                return self._convert_jobs_lists_job(job_data)
            elif '_id' in job_data or 'employer_id' in job_data:
                # This looks like a MongoDB job
                return self._convert_mongo_job(job_data)
            else:
                # This might be frontend job data, return as-is with minimal processing
                return {
                    "id": str(job_data.get("id", job_data.get("_id", ""))),
                    "title": job_data.get("title", ""),
                    "description": job_data.get("description", ""),
                    "company": job_data.get("company", ""),
                    "location": job_data.get("location", ""),
                    "salary": job_data.get("salary", ""),
                    "matchPercentage": job_data.get("matchPercentage", 0),
                    "type": job_data.get("type", job_data.get("employment_type", "")),
                    "requirements": job_data.get("requirements", []),
                    "benefits": job_data.get("benefits", []),
                    "tags": job_data.get("tags", job_data.get("skills_required", [])),
                    "postedTime": job_data.get("postedTime", job_data.get("posted_at", "")),
                    "companySize": job_data.get("companySize", ""),
                    "experience": job_data.get("experience", job_data.get("experience_level", "")),
                    "companyDescription": job_data.get("companyDescription", ""),
                    "hrContact": job_data.get("hrContact", None),
                    "employment_type": job_data.get("employment_type", ""),
                    "skills_required": job_data.get("skills_required", []),
                    "is_active": job_data.get("is_active", True),
                    "employer_id": job_data.get("employer_id", ""),
                    "posted_at": job_data.get("posted_at", ""),
                    "expires_at": job_data.get("expires_at", ""),
                    "responsibilities": job_data.get("responsibilities", [])
                }
        except Exception as e:
            logger.error(f"Error converting job data: {e}")
            return None

    def _convert_jobs_lists_job(self, job_data: dict) -> dict:
        """Convert jobs-lists collection job data to our expected format"""
        try:
            skills = []
            if job_data.get('skills_required'):
                if isinstance(job_data['skills_required'], list):
                    skills = job_data['skills_required']
                else:
                    skills = [skill.strip() for skill in job_data['skills_required'].split(
                        ',') if skill.strip()]

            location_data = job_data.get('location', {})
            if isinstance(location_data, str):
                location = self._parse_location(location_data)
            else:
                location = location_data

            raw_job_type = job_data.get('employment_type', 'Full-time')
            normalized_employment_type = self._normalize_employment_type(
                raw_job_type)

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
                "expires_at": None,
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
                skills = [skill.strip() for skill in job_data['skills'].split(
                    ',') if skill.strip()]

            location_str = job_data.get('location_1', '')
            location = self._parse_location(location_str)

            raw_job_type = job_data.get('job_type', 'Full-time')
            normalized_employment_type = self._normalize_employment_type(
                raw_job_type)

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
                "expires_at": None,
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
                    skills = json.loads(job_data['skills']) if isinstance(
                        job_data['skills'], str) else job_data['skills']
                except:
                    skills = job_data['skills'].split(',') if isinstance(
                        job_data['skills'], str) else []

            requirements = []
            if job_data.get('requirements'):
                try:
                    requirements = json.loads(job_data['requirements']) if isinstance(
                        job_data['requirements'], str) else job_data['requirements']
                except:
                    requirements = [job_data['requirements']
                                    ] if job_data['requirements'] else []

            responsibilities = []
            if job_data.get('responsibilities'):
                try:
                    responsibilities = json.loads(job_data['responsibilities']) if isinstance(
                        job_data['responsibilities'], str) else job_data['responsibilities']
                except:
                    responsibilities = [
                        job_data['responsibilities']] if job_data['responsibilities'] else []

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
            normalized_employment_type = self._normalize_employment_type(
                raw_employment_type)

            # Generate a unique ID if not present - handle Redis data structure
            job_id = job_data.get('job_id') or job_data.get(
                '_id') or str(hash(job_data.get('title', '')))

            # Handle posted_at and expires_at dates using helper method
            posted_at = self._parse_datetime(job_data.get(
                'posted_date', job_data.get('posted_at', '2024-01-01')))
            expires_at = self._parse_datetime(
                job_data.get('expires_at', '2024-12-31'))

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
                "posted_at": posted_at,
                "expires_at": expires_at,
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
                cleared_count = self.scraper.clear_cache(
                    expired_only=expired_only)
                return {
                    "success": True,
                    "cleared_count": cleared_count,
                    "expired_only": expired_only
                }
            else:
                return {"success": False, "error": "Scraper not available"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ===== Separate Collections for Job Actions =====

    async def save_job_saved(self, user_id: str, job_id: str, job_details: dict) -> bool:
        """Save job bookmark with full job details to users_job_saved collection."""
        try:
            collection = self.users_db.users_job_saved
            now = datetime.utcnow()

            logger.info(
                f"🔖 Saving job bookmark: user={user_id[:8]}..., job={job_id[:8]}...")

            # Prepare document with full job details
            saved_doc = {
                "user_id": user_id,
                "job_id": job_id,
                "job_details": job_details,
                "saved_at": now,
                "created_at": now,
                "updated_at": now
            }

            result = await collection.update_one(
                {"user_id": user_id, "job_id": job_id},
                {"$set": saved_doc},
                upsert=True,
            )

            if result.upserted_id:
                logger.info(
                    f"✅ New job bookmark saved (ID: {str(result.upserted_id)[:8]}...)")
            elif result.modified_count > 0:
                logger.info(f"✅ Job bookmark updated")
            else:
                logger.debug(f"ℹ️  Job bookmark already exists (no changes)")

            return True
        except Exception as e:
            logger.error(f"❌ Failed to save job bookmark: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def save_job_like(self, user_id: str, job_id: str, job_details: dict) -> bool:
        """Save job like with full job details to users_job_like collection."""
        try:
            collection = self.users_db.users_job_like
            now = datetime.utcnow()

            logger.info(
                f"💚 Saving job like: user={user_id[:8]}..., job={job_id[:8]}...")

            # Prepare document with full job details
            like_doc = {
                "user_id": user_id,
                "job_id": job_id,
                "job_details": job_details,
                "liked_at": now,
                "created_at": now,
                "updated_at": now
            }

            result = await collection.update_one(
                {"user_id": user_id, "job_id": job_id},
                {"$set": like_doc},
                upsert=True,
            )

            if result.upserted_id:
                logger.info(
                    f"✅ New job like saved (ID: {str(result.upserted_id)[:8]}...)")
            elif result.modified_count > 0:
                logger.info(f"✅ Job like updated")
            else:
                logger.debug(f"ℹ️  Job like already exists (no changes)")

            return True
        except Exception as e:
            logger.error(f"❌ Failed to save job like: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def save_job_dislike(self, user_id: str, job_id: str) -> bool:
        """Save job dislike with minimal data to users_job_dislike collection."""
        try:
            collection = self.users_db.users_job_dislike
            now = datetime.utcnow()

            logger.info(
                f"👎 Saving job dislike: user={user_id[:8]}..., job={job_id[:8]}...")

            # Minimal document - only user_id and job_id
            dislike_doc = {
                "user_id": user_id,
                "job_id": job_id,
                "disliked_at": now,
                "created_at": now
            }

            result = await collection.update_one(
                {"user_id": user_id, "job_id": job_id},
                {"$set": dislike_doc},
                upsert=True,
            )

            if result.upserted_id:
                logger.info(
                    f"✅ New job dislike saved (ID: {str(result.upserted_id)[:8]}...)")
            elif result.modified_count > 0:
                logger.info(f"✅ Job dislike updated")
            else:
                logger.debug(f"ℹ️  Job dislike already exists (no changes)")

            return True
        except Exception as e:
            logger.error(f"❌ Failed to save job dislike: {e}")
            import traceback
            traceback.print_exc()
            return False

    # Legacy method for backward compatibility - handles 3 actions only
    async def save_user_job_action(self, user_id: str, job_id: str, action: str, job_snapshot: Optional[dict] = None) -> bool:
        """Legacy method - redirects to new separate collection methods.

        Actions handled:
        1. 'like' (apply) -> users_job_like (with full job details)
        2. 'dislike' (pass) -> users_job_dislike (minimal data)
        3. 'save' -> users_job_saved (with full job details)
        """
        try:
            if action == "like":
                return await self.save_job_like(user_id, job_id, job_snapshot or {})
            elif action == "save":
                return await self.save_job_saved(user_id, job_id, job_snapshot or {})
            elif action == "dislike":
                return await self.save_job_dislike(user_id, job_id)
            else:
                logger.warning(
                    f"⚠️  Unknown action '{action}', saving as dislike")
                return await self.save_job_dislike(user_id, job_id)
        except Exception as e:
            logger.error(f"❌ Failed to save user job action: {e}")
            return False

    async def remove_saved_job(self, user_id: str, job_id: str) -> bool:
        """Remove a saved job document for a user from users_job_saved collection."""
        try:
            logger.info(
                f"🗑️  Removing saved job: user={user_id[:8]}..., job={job_id[:8]}...")

            result = await self.users_db.users_job_saved.delete_one(
                {"user_id": user_id, "job_id": job_id}
            )

            if result.deleted_count > 0:
                logger.info(f"✅ Saved job removed successfully")
                return True
            else:
                logger.warning(
                    f"⚠️  Saved job not found (may already be removed)")
                return False
        except Exception as e:
            logger.error(f"❌ Failed to remove saved job: {e}")
            return False

    async def remove_job_like(self, user_id: str, job_id: str) -> bool:
        """Remove a job like for a user from users_job_like collection."""
        try:
            logger.info(
                f"🗑️  Removing job like: user={user_id[:8]}..., job={job_id[:8]}...")

            result = await self.users_db.users_job_like.delete_one(
                {"user_id": user_id, "job_id": job_id}
            )

            if result.deleted_count > 0:
                logger.info(f"✅ Job like removed successfully")
                return True
            else:
                logger.warning(
                    f"⚠️  Job like not found (may already be removed)")
                return False
        except Exception as e:
            logger.error(f"❌ Failed to remove job like: {e}")
            return False

    async def remove_job_dislike(self, user_id: str, job_id: str) -> bool:
        """Remove a job dislike for a user from users_job_dislike collection."""
        try:
            logger.info(
                f"🗑️  Removing job dislike: user={user_id[:8]}..., job={job_id[:8]}...")

            result = await self.users_db.users_job_dislike.delete_one(
                {"user_id": user_id, "job_id": job_id}
            )

            if result.deleted_count > 0:
                logger.info(f"✅ Job dislike removed successfully")
                return True
            else:
                logger.warning(
                    f"⚠️  Job dislike not found (may already be removed)")
                return False
        except Exception as e:
            logger.error(f"❌ Failed to remove job dislike: {e}")
            return False

    async def get_user_saved_jobs_optimized(self, user_id: str) -> List[dict]:
        """Optimized version of get_user_saved_jobs with concurrent operations"""
        try:
            # Use cache first
            cache_key = self._get_cache_key("saved_jobs", user_id)
            cached_jobs = self._get_from_cache(cache_key)
            if cached_jobs is not None:
                logger.debug(f"📋 Cache hit for saved jobs: {user_id[:8]}...")
                return cached_jobs

            # Fetch from database with concurrent operations
            cursor = self.users_db.users_job_saved.find({"user_id": user_id})
            items = [doc async for doc in cursor]

            if not items:
                self._set_cache(cache_key, [])
                return []

            # Process jobs concurrently
            async def process_job_doc(doc):
                job_details = doc.get("job_details", {})
                if job_details:
                    return {
                        "id": doc.get("job_id"),
                        "saved_at": doc.get("saved_at"),
                        **job_details
                    }
                else:
                    # Fallback: try to get job from main collection
                    job_id = doc.get("job_id")
                    job_data = await self.get_job_by_id(job_id)
                    if job_data:
                        job_obj = self._convert_job_data(job_data)
                        if job_obj:
                            return {
                                "id": job_id,
                                "saved_at": doc.get("saved_at"),
                                **job_obj
                            }
                return None

            # Process all jobs concurrently
            results = await asyncio.gather(*[process_job_doc(doc) for doc in items])
            final_results = [
                result for result in results if result is not None]

            # Cache the results
            self._set_cache(cache_key, final_results)
            logger.debug(
                f"📋 Processed {len(final_results)} saved jobs for user: {user_id[:8]}...")

            return final_results
        except Exception as e:
            logger.error(f"Failed to fetch saved jobs: {e}")
            return []

    async def get_user_saved_jobs(self, user_id: str) -> List[dict]:
        """Return saved jobs from users_job_saved collection with full job details."""
        try:
            cursor = self.users_db.users_job_saved.find({"user_id": user_id})
            items = [doc async for doc in cursor]
            results: List[dict] = []

            for doc in items:
                job_details = doc.get("job_details", {})
                if job_details:
                    # Use the stored job details directly
                    results.append({
                        "id": doc.get("job_id"),
                        "saved_at": doc.get("saved_at"),
                        **job_details
                    })
                else:
                    # Fallback: try to get job from main collection
                    job_id = doc.get("job_id")
                    job_data = await self.get_job_by_id(job_id)
                    if job_data:
                        job_obj = self._convert_job_data(job_data)
                        if job_obj:
                            results.append({
                                "id": job_id,
                                "saved_at": doc.get("saved_at"),
                                **job_obj
                            })

            return results
        except Exception as e:
            logger.error(f"Failed to fetch saved jobs: {e}")
            return []

    async def get_user_disliked_jobs(self, user_id: str) -> List[dict]:
        """Return disliked job IDs from users_job_dislike collection (minimal data)."""
        try:
            cursor = self.users_db.users_job_dislike.find({"user_id": user_id})
            items = [doc async for doc in cursor]
            results: List[dict] = []

            for doc in items:
                # Only return basic info for disliked jobs
                results.append({
                    "job_id": doc.get("job_id"),
                    "disliked_at": doc.get("disliked_at"),
                    "user_id": doc.get("user_id")
                })

            return results
        except Exception as e:
            logger.error(f"Failed to fetch disliked jobs: {e}")
            return []

    async def is_job_disliked(self, user_id: str, job_id: str) -> bool:
        """Check if a job is disliked by the user."""
        try:
            result = await self.users_db.users_job_dislike.find_one({
                "user_id": user_id,
                "job_id": job_id
            })
            return result is not None
        except Exception as e:
            logger.error(f"Failed to check if job is disliked: {e}")
            return False

    async def get_user_liked_jobs(self, user_id: str) -> List[dict]:
        """Return liked jobs from users_job_like collection with full job details."""
        try:
            cursor = self.users_db.users_job_like.find({"user_id": user_id})
            items = [doc async for doc in cursor]
            results: List[dict] = []

            for doc in items:
                job_details = doc.get("job_details", {})
                if job_details:
                    # Use the stored job details directly
                    results.append({
                        "id": doc.get("job_id"),
                        "liked_at": doc.get("liked_at"),
                        **job_details
                    })
                else:
                    # Fallback: try to get job from main collection
                    job_id = doc.get("job_id")
                    job_data = await self.get_job_by_id(job_id)
                    if job_data:
                        job_obj = self._convert_job_data(job_data)
                        if job_obj:
                            results.append({
                                "id": job_id,
                                "liked_at": doc.get("liked_at"),
                                **job_obj
                            })

            return results
        except Exception as e:
            logger.error(f"Failed to fetch liked jobs: {e}")
            return []

    async def get_user_action_job_ids(self, user_id: str, actions: List[str]) -> List[str]:
        """Fetch job ids from MongoDB where user performed any of the given actions."""
        try:
            cursor = self.users_db.user_job_actions.find(
                {"user_id": user_id, "action": {"$in": actions}})
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
        partial_score = (partial_matches - len(exact_matches)
                         ) / total_job_skills * 0.5

        final_score = min(exact_score + partial_score, 1.0)
        return round(final_score, 3)


# Singleton instance
db = Database()
