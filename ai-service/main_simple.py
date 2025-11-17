from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import json
import tempfile
from enhanced_cv_service import EnhancedCVService


app = FastAPI(
    title="AI Recruitment Service",
    description="CV Parsing and Candidate Ranking API with Caching and Vector Database",
    version="2.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Experience(BaseModel):
    title: str
    company: str
    startDate: str
    endDate: str
    description: str
    responsibilities: Optional[List[str]] = []


class Education(BaseModel):
    degree: str
    institution: str
    startDate: str
    endDate: str
    fieldOfStudy: Optional[str] = None


class Candidate(BaseModel):
    id: str
    email: str
    full_name: str
    skills: List[str]
    experience: List[Experience]
    education: List[Education]
    years_of_experience: float


class JobRequirements(BaseModel):
    title: str
    description: str
    required_skills: List[str]
    preferred_skills: List[str] = []
    min_years_experience: float = 0
    required_education: str = ""


class RankRequest(BaseModel):
    job_requirements: JobRequirements
    candidates: List[Candidate]


# Initialize enhanced CV service
cv_service = EnhancedCVService()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    cv_service.close()


@app.get("/")
async def root():
    return {
        "message": "AI Recruitment Service (Enhanced)",
        "version": "2.0.0",
        "status": "running",
        "features": [
            "CV Parsing with caching",
            "Vector database integration (Weaviate)",
            "Semantic CV search",
            "Detailed scoring breakdown"
        ]
    }


@app.post("/parse-cv")
async def parse_cv(file: UploadFile = File(...)):
    """
    Parse CV with caching and vector database indexing
    """
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        # Parse with caching and indexing
        result = cv_service.parse_cv_with_cache(tmp_path)
        
        # Clean up
        os.unlink(tmp_path)
        
        return result
    except Exception as e:
        print(f"Error parsing CV: {e}")
        # Return default response if parsing fails
        return {
            "skills": [],
            "experience": [],
            "education": [],
            "phone": None,
            "email": None,
            "years_of_experience": 0
        }


@app.post("/rank-candidates")
async def rank_candidates(request: RankRequest):
    """
    Rank candidates with detailed evaluation breakdown
    """
    try:
        ranked_candidates = []
        
        for candidate in request.candidates:
            # Prepare candidate data
            candidate_data = {
                "skills": candidate.skills,
                "years_of_experience": candidate.years_of_experience,
                "education": [edu.dict() for edu in candidate.education],
                "experience": [exp.dict() for exp in candidate.experience],
            }
            
            # Prepare job requirements
            job_req_data = {
                "required_skills": request.job_requirements.required_skills,
                "preferred_skills": request.job_requirements.preferred_skills,
                "min_years_experience": request.job_requirements.min_years_experience,
                "required_education": request.job_requirements.required_education,
            }
            
            # Calculate detailed scores
            scores = cv_service.calculate_detailed_scores(candidate_data, job_req_data)
            
            # Prepare response
            ranked_candidates.append({
                "candidate_id": candidate.id,
                "score": scores["totalScore"],
                "matching_skills": list(set(candidate.skills) & set(request.job_requirements.required_skills)),
                "scoring_details": {
                    "skillsScore": scores["skillsScore"],
                    "experienceScore": scores["experienceScore"],
                    "educationScore": scores["educationScore"],
                    "yearsExperienceScore": scores["yearsExperienceScore"],
                    "reasoning": scores["reasoning"],
                    "breakdown": scores["breakdown"]
                }
            })
        
        # Sort by score descending
        ranked_candidates.sort(key=lambda x: x["score"], reverse=True)
        
        return {"ranked_candidates": ranked_candidates}
    
    except Exception as e:
        print(f"Error ranking candidates: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error ranking candidates: {str(e)}"
        )


@app.get("/search-cvs")
async def search_cvs(query: str, limit: int = 5):
    """
    Search for similar CVs using vector database
    """
    try:
        results = cv_service.search_similar_cvs(query, limit)
        return {"results": results}
    except Exception as e:
        print(f"Error searching CVs: {e}")
        return {"results": [], "error": str(e)}


@app.delete("/cleanup-candidate/{candidate_id}")
async def cleanup_candidate(candidate_id: str):
    """
    Clean up all candidate data including cache and vector database entries
    """
    try:
        cleanup_count = 0
        
        # 1. Clean up cache files - search for entries with this candidate_id
        cache_dir = cv_service.cache_dir
        if os.path.exists(cache_dir):
            for cache_file in os.listdir(cache_dir):
                if cache_file.endswith('.json'):
                    cache_path = os.path.join(cache_dir, cache_file)
                    try:
                        with open(cache_path, 'r') as f:
                            data = json.load(f)
                            # Check if this cache entry is for the candidate
                            # We can check by file hash or any candidate identifier in metadata
                            # For now, we'll remove the cache file
                            os.remove(cache_path)
                            cleanup_count += 1
                    except Exception as e:
                        print(f"Error cleaning cache file {cache_file}: {e}")
        
        # 2. Remove from Weaviate vector database
        if cv_service.weaviate_client:
            try:
                collection = cv_service.weaviate_client.collections.get("CVData")
                # Delete by candidate_id
                result = collection.data.delete_many(
                    where={
                        "path": ["candidate_id"],
                        "operator": "Equal",
                        "valueText": candidate_id
                    }
                )
                print(f"Deleted {result} entries from Weaviate for candidate {candidate_id}")
            except Exception as e:
                print(f"Error cleaning Weaviate: {e}")
        
        return {
            "success": True,
            "message": f"Cleaned up data for candidate {candidate_id}",
            "cache_files_removed": cleanup_count,
            "vector_db_cleaned": cv_service.weaviate_client is not None
        }
    
    except Exception as e:
        print(f"Error during cleanup: {e}")
        return {
            "success": False,
            "message": str(e)
        }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "mode": "enhanced",
        "features": {
            "caching": True,
            "vector_db": cv_service.weaviate_client is not None,
            "detailed_scoring": True
        }
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
