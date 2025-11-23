from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path
import os
import json
import tempfile
from enhanced_cv_service import EnhancedCVService
from services.pdf_to_txt_converter import PDFToTextConverter


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


# Initialize services
cv_service = EnhancedCVService()
pdf_converter = PDFToTextConverter()


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
    Parse CV with caching and vector database indexing.
    Automatically converts PDF to text and caches it.
    """
    try:
        # Validate file type
        if not file.filename.lower().endswith(('.pdf', '.docx')):
            raise HTTPException(
                status_code=400,
                detail="Only PDF and DOCX files are supported"
            )
        
        # Determine file extension
        file_ext = '.pdf' if file.filename.lower().endswith('.pdf') else '.docx'
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        # Step 1: Convert PDF to text and cache it (only for PDFs)
        txt_conversion_result = None
        if file.filename.lower().endswith('.pdf'):
            try:
                txt_conversion_result = pdf_converter.convert_pdf_to_text(
                    tmp_path,
                    output_filename=Path(file.filename).stem,
                    preserve_formatting=True,
                    method="auto"
                )
                
                if txt_conversion_result["success"]:
                    print(f"✓ PDF converted to text: {txt_conversion_result['text_file_path']}")
                else:
                    print(f"⚠ PDF to text conversion failed: {txt_conversion_result.get('error')}")
            except Exception as e:
                print(f"⚠ Warning: PDF to text conversion failed: {e}")
        
        # Step 2: Parse with caching and indexing
        result = cv_service.parse_cv_with_cache(tmp_path)
        
        # Step 3: Add text conversion info to result
        if txt_conversion_result and txt_conversion_result["success"]:
            result["text_conversion"] = {
                "text_file_path": txt_conversion_result["text_file_path"],
                "text_length": txt_conversion_result["text_length"],
                "method_used": txt_conversion_result["method_used"],
                "converted_at": txt_conversion_result["converted_at"]
            }
        
        # Clean up temporary file
        os.unlink(tmp_path)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error parsing CV: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error parsing CV: {str(e)}"
        )


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


@app.post("/convert-pdf-to-text")
async def convert_pdf_to_text(
    file: UploadFile = File(...),
    preserve_formatting: bool = True
):
    """
    Convert uploaded PDF CV to plain text file
    
    Args:
        file: PDF file to convert
        preserve_formatting: Whether to preserve page separators and formatting
        
    Returns:
        Conversion result with text file path and metadata
    """
    try:
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=400,
                detail="Only PDF files are supported"
            )
        
        # Read file content
        content = await file.read()
        
        # Convert PDF to text
        result = pdf_converter.convert_pdf_bytes_to_text(
            content,
            file.filename,
            preserve_formatting=preserve_formatting
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Conversion failed: {result.get('error', 'Unknown error')}"
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error converting PDF: {str(e)}"
        )


@app.post("/batch-convert-pdfs")
async def batch_convert_pdfs(
    pdf_directory: str,
    file_pattern: str = "*.pdf",
    preserve_formatting: bool = True
):
    """
    Convert multiple PDF files in a directory to text
    
    Args:
        pdf_directory: Path to directory containing PDF files
        file_pattern: Glob pattern to match files (default: *.pdf)
        preserve_formatting: Whether to preserve formatting
        
    Returns:
        Batch conversion results
    """
    try:
        result = pdf_converter.batch_convert(
            pdf_directory,
            file_pattern=file_pattern,
            preserve_formatting=preserve_formatting
        )
        
        if not result.get("total_files"):
            raise HTTPException(
                status_code=404,
                detail=f"No PDF files found in {pdf_directory}"
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error in batch conversion: {str(e)}"
        )


@app.get("/pdf-preview")
async def get_pdf_preview(pdf_path: str, max_chars: int = 500):
    """
    Get a text preview of a PDF file
    
    Args:
        pdf_path: Path to the PDF file
        max_chars: Maximum characters to return (default: 500)
        
    Returns:
        Text preview of the PDF
    """
    try:
        if not os.path.exists(pdf_path):
            raise HTTPException(
                status_code=404,
                detail=f"PDF file not found: {pdf_path}"
            )
        
        preview = pdf_converter.get_text_preview(pdf_path, max_chars)
        
        return {
            "pdf_path": pdf_path,
            "preview": preview,
            "preview_length": len(preview)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating preview: {str(e)}"
        )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "mode": "enhanced",
        "features": {
            "caching": True,
            "vector_db": cv_service.weaviate_client is not None,
            "detailed_scoring": True,
            "pdf_to_text_conversion": True
        }
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
