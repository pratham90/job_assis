from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Annotated
from pydantic import AfterValidator, BaseModel, Field, ConfigDict
from bson import ObjectId
from .user import PyObjectId


def validate_object_id(value: str) -> str:
    if not ObjectId.is_valid(value):
        raise ValueError("Invalid ObjectId")
    return str(value)


PyObjectId = Annotated[str, AfterValidator(validate_object_id)]


class EmploymentType(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"


class SalaryRange(BaseModel):
    min: int
    max: int
    currency: str = "USD"
    is_public: bool = True


class Location(BaseModel):
    city: str
    state: Optional[str] = None
    country: str
    remote: bool = False
    coordinates: Optional[tuple[float, float]] = None


class JobPosting(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: PyObjectId = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    employer_id: str
    title: str
    description: str
    requirements: List[str] = Field(default_factory=list)
    responsibilities: List[str] = Field(default_factory=list)
    employment_type: EmploymentType  # Your existing enum
    salary: SalaryRange
    location: Location
    skills_required: List[str] = Field(default_factory=list)
    benefits: List[str] = Field(default_factory=list)
    is_active: bool = True
    posted_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(
        default_factory=lambda: datetime.utcnow() + timedelta(days=30)
    )


class JobRecommendation(BaseModel):
    job: JobPosting
    match_score: float

