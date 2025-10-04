"""
Script to remove duplicate job actions from MongoDB
Run this once to clean up existing duplicates before creating unique index
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

load_dotenv()
mongo_uri = os.getenv("MONGO_URI", "mongodb+srv://Jobs:Jobs-provider@jobs.2m8l8hb.mongodb.net")

async def cleanup_duplicates():
    """Remove duplicate user_job_actions keeping only the most recent one"""
    
    client = AsyncIOMotorClient(mongo_uri)
    db = client.users
    collection = db.user_job_actions
    
    print("🔍 Finding duplicate entries...")
    
    # Aggregate to find duplicates
    pipeline = [
        {
            "$group": {
                "_id": {
                    "user_id": "$user_id",
                    "job_id": "$job_id",
                    "action": "$action"
                },
                "count": {"$sum": 1},
                "docs": {"$push": {"_id": "$_id", "created_at": "$created_at"}}
            }
        },
        {
            "$match": {
                "count": {"$gt": 1}
            }
        }
    ]
    
    duplicates = await collection.aggregate(pipeline).to_list(None)
    
    print(f"📊 Found {len(duplicates)} duplicate groups")
    
    if len(duplicates) == 0:
        print("✅ No duplicates found! Database is clean.")
        return
    
    total_removed = 0
    
    for dup in duplicates:
        user_id = dup["_id"]["user_id"]
        job_id = dup["_id"]["job_id"]
        action = dup["_id"]["action"]
        docs = dup["docs"]
        
        print(f"\n🔄 Processing: user={user_id[:8]}..., job={job_id[:8]}..., action={action}")
        print(f"   Found {len(docs)} duplicates")
        
        # Sort by created_at to keep the most recent
        docs_sorted = sorted(docs, key=lambda x: x.get("created_at", ""), reverse=True)
        
        # Keep the first (most recent), delete the rest
        keep_id = docs_sorted[0]["_id"]
        delete_ids = [doc["_id"] for doc in docs_sorted[1:]]
        
        print(f"   Keeping: {keep_id}")
        print(f"   Deleting: {len(delete_ids)} old entries")
        
        # Delete duplicates
        result = await collection.delete_many({"_id": {"$in": delete_ids}})
        total_removed += result.deleted_count
        print(f"   ✅ Deleted {result.deleted_count} duplicates")
    
    print(f"\n✨ Cleanup complete!")
    print(f"📊 Total duplicates removed: {total_removed}")
    print(f"✅ Database is now ready for unique index")
    
    client.close()

if __name__ == "__main__":
    print("🧹 MongoDB Duplicate Cleanup Script")
    print("=" * 50)
    asyncio.run(cleanup_duplicates())
