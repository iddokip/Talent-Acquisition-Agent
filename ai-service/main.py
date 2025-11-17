from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
from dotenv import load_dotenv

from services.cv_parser import CVParser
from services.candidate_ranker import CandidateRanker

load_dotenv()

app = FastAPI(
    title="AI Recruitment Service",
    description="CV Parsing and Candidate Ranking API",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
cv_parser = CVParser()
candidate_ranker = CandidateRanker()


# Pydantic models
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


@app.get("/")
async def root():
    return {
        "message": "AI Recruitment Service",
        "version": "1.0.0",
        "endpoints": {
            "parse_cv": "/parse-cv",
            "rank_candidates": "/rank-candidates",
            "extract_skills": "/extract-skills",
            "docs": "/docs"
        }
    }


@app.post("/parse-cv")
async def parse_cv(file: UploadFile = File(...)):
    """
    Parse a CV file (PDF or DOCX) and extract structured information
    """
    try:
        # Validate file type
        if not file.filename.lower().endswith(('.pdf', '.docx')):
            raise HTTPException(
                status_code=400,
                detail="Only PDF and DOCX files are supported"
            )
        
        # Read file content
        content = await file.read()
        
        # Parse CV
        parsed_data = await cv_parser.parse_cv(content, file.filename)
        
        return parsed_data
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error parsing CV: {str(e)}"
        )


@app.post("/rank-candidates")
async def rank_candidates(request: RankRequest):
    """
    Rank candidates based on job requirements
    """
    try:
        ranked_candidates = await candidate_ranker.rank_candidates(
            request.job_requirements,
            request.candidates
        )
        
        return {"ranked_candidates": ranked_candidates}
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error ranking candidates: {str(e)}"
        )


@app.post("/extract-skills")
async def extract_skills(text: str):
    """
    Extract skills from text using AI
    """
    try:
        skills = await cv_parser.extract_skills(text)
        return {"skills": skills}
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error extracting skills: {str(e)}"
        )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "ollama_url": os.getenv("OLLAMA_BASE_URL"),
        "model": os.getenv("MODEL_NAME")
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
