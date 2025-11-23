import os
import json
import hashlib
import pickle
from typing import Dict, List, Any, Optional
from datetime import datetime
import weaviate
from weaviate.classes.init import Auth
from weaviate.classes.config import Configure, Property, DataType
from services.cv_parser import CVParser


class EnhancedCVService:
    """Enhanced CV service with caching, embeddings, and vector database integration"""
    
    def __init__(self):
        self.parser = CVParser()
        self.cache_dir = "cv_cache"
        self.weaviate_url = os.getenv("WEAVIATE_URL", "http://localhost:8080")
        
        # Create cache directory
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Initialize Weaviate client
        try:
            self.weaviate_client = weaviate.connect_to_local(
                host=self.weaviate_url.replace("http://", "").replace("https://", "")
            )
            self._setup_weaviate_schema()
        except Exception as e:
            print(f"Warning: Could not connect to Weaviate: {e}")
            self.weaviate_client = None
    
    def _setup_weaviate_schema(self):
        """Setup Weaviate schema for CV data"""
        if not self.weaviate_client:
            return
        
        try:
            # Check if collection exists
            collections = self.weaviate_client.collections.list_all()
            if "CVData" not in [c.name for c in collections]:
                # Create collection
                self.weaviate_client.collections.create(
                    name="CVData",
                    properties=[
                        Property(name="candidate_id", data_type=DataType.TEXT),
                        Property(name="email", data_type=DataType.TEXT),
                        Property(name="full_text", data_type=DataType.TEXT),
                        Property(name="skills", data_type=DataType.TEXT_ARRAY),
                        Property(name="years_of_experience", data_type=DataType.NUMBER),
                        Property(name="phone", data_type=DataType.TEXT),
                        Property(name="parsed_data", data_type=DataType.TEXT),
                        Property(name="file_hash", data_type=DataType.TEXT),
                        Property(name="timestamp", data_type=DataType.DATE),
                    ],
                    vectorizer_config=Configure.Vectorizer.text2vec_transformers(),
                )
                print("Created CVData collection in Weaviate")
        except Exception as e:
            print(f"Error setting up Weaviate schema: {e}")
    
    def _get_file_hash(self, file_path: str) -> str:
        """Calculate hash of file for caching"""
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            hasher.update(f.read())
        return hasher.hexdigest()
    
    def _get_cache_path(self, file_hash: str) -> str:
        """Get cache file path for a given file hash"""
        return os.path.join(self.cache_dir, f"{file_hash}.json")
    
    def _load_from_cache(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """Load parsed CV data from cache"""
        cache_path = self._get_cache_path(file_hash)
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r') as f:
                    cached_data = json.load(f)
                    print(f"Loaded CV data from cache: {file_hash}")
                    return cached_data
            except Exception as e:
                print(f"Error loading cache: {e}")
        return None
    
    def _save_to_cache(self, file_hash: str, data: Dict[str, Any]):
        """Save parsed CV data to cache"""
        cache_path = self._get_cache_path(file_hash)
        try:
            with open(cache_path, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"Saved CV data to cache: {file_hash}")
        except Exception as e:
            print(f"Error saving to cache: {e}")
    
    def _index_to_weaviate(self, file_hash: str, full_text: str, parsed_data: Dict[str, Any], candidate_id: Optional[str] = None):
        """Index CV data to Weaviate vector database"""
        if not self.weaviate_client:
            print("Weaviate client not available, skipping indexing")
            return
        
        try:
            collection = self.weaviate_client.collections.get("CVData")
            
            # Prepare data for Weaviate
            properties = {
                "candidate_id": candidate_id or file_hash,
                "email": parsed_data.get("email") or "",
                "full_text": full_text[:10000],  # Limit text length
                "skills": parsed_data.get("skills", []),
                "years_of_experience": float(parsed_data.get("years_of_experience", 0)),
                "phone": parsed_data.get("phone") or "",
                "parsed_data": json.dumps(parsed_data),
                "file_hash": file_hash,
                "timestamp": datetime.now().isoformat(),
            }
            
            # Add to Weaviate
            collection.data.insert(properties)
            print(f"Indexed CV data to Weaviate: {file_hash}")
            
        except Exception as e:
            print(f"Error indexing to Weaviate: {e}")
    
    def parse_cv_with_cache(self, file_path: str, candidate_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Parse CV with caching and vector database indexing
        
        Args:
            file_path: Path to CV file
            candidate_id: Optional candidate ID for tracking
            
        Returns:
            Parsed CV data
        """
        # Calculate file hash
        file_hash = self._get_file_hash(file_path)
        
        # Try to load from cache
        cached_data = self._load_from_cache(file_hash)
        if cached_data:
            return cached_data
        
        # Parse the CV
        print(f"Parsing CV: {file_path}")
        
        # Extract full text first
        full_text = ""
        try:
            import PyPDF2
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    full_text += page.extract_text()
        except Exception as e:
            print(f"Error extracting text: {e}")
        
        # Parse structured data
        parsed_data = self.parser.parse_pdf(file_path)
        
        # Add metadata
        parsed_data["file_hash"] = file_hash
        parsed_data["parsed_at"] = datetime.now().isoformat()
        parsed_data["full_text_length"] = len(full_text)
        
        # Save to cache
        self._save_to_cache(file_hash, parsed_data)
        
        # Index to Weaviate
        self._index_to_weaviate(file_hash, full_text, parsed_data, candidate_id)
        
        return parsed_data
    
    def search_similar_cvs(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for similar CVs in vector database"""
        if not self.weaviate_client:
            return []
        
        try:
            collection = self.weaviate_client.collections.get("CVData")
            response = collection.query.near_text(
                query=query,
                limit=limit
            )
            
            results = []
            for item in response.objects:
                results.append({
                    "candidate_id": item.properties.get("candidate_id"),
                    "email": item.properties.get("email"),
                    "skills": item.properties.get("skills"),
                    "years_of_experience": item.properties.get("years_of_experience"),
                    "score": item.metadata.distance if hasattr(item.metadata, 'distance') else None
                })
            
            return results
        except Exception as e:
            print(f"Error searching Weaviate: {e}")
            return []
    
    def calculate_detailed_scores(self, candidate: Dict[str, Any], job_requirements: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate detailed evaluation scores with semantic similarity search for each field
        
        Args:
            candidate: Candidate data with skills, experience, education
            job_requirements: Job requirements
            
        Returns:
            Detailed scoring breakdown with similarity search results
        """
        # Extract data
        candidate_skills = set([s.lower() for s in candidate.get("skills", [])])
        required_skills = set([s.lower() for s in job_requirements.get("required_skills", [])])
        preferred_skills = set([s.lower() for s in job_requirements.get("preferred_skills", [])])
        
        candidate_years = float(candidate.get("years_of_experience", 0))
        required_years = float(job_requirements.get("min_years_experience", 0))
        
        candidate_education = candidate.get("education", [])
        required_education = job_requirements.get("required_education", "")
        
        job_title = job_requirements.get("title", "")
        job_description = job_requirements.get("description", "")
        
        # 1. Job Title Similarity Score (15% weight)
        job_title_score = self._calculate_semantic_similarity(
            candidate.get("experience", []),
            job_title
        )
        job_title_percentage = job_title_score * 100
        
        # 2. Job Description Similarity Score (15% weight)
        job_desc_score = self._calculate_description_similarity(
            candidate,
            job_description
        )
        job_desc_percentage = job_desc_score * 100
        
        # 3. Required Skills Score (25% weight)
        required_matched = candidate_skills & required_skills
        if required_skills:
            required_skill_percentage = (len(required_matched) / len(required_skills)) * 100
        else:
            required_skill_percentage = 100
        
        # 4. Preferred Skills Score (10% weight)
        preferred_matched = candidate_skills & preferred_skills
        if preferred_skills:
            preferred_skill_percentage = (len(preferred_matched) / len(preferred_skills)) * 100
        else:
            preferred_skill_percentage = 0
        
        # 5. Years of Experience Score (20% weight)
        if required_years > 0:
            experience_ratio = min(candidate_years / required_years, 1.5)
            years_percentage = min(experience_ratio * 100, 100)
        else:
            years_percentage = 100 if candidate_years > 0 else 50
        
        # 6. Education Score (15% weight)
        education_score_percentage = 0
        if candidate_education:
            education_score_percentage = 50  # Base score
            if required_education:
                for edu in candidate_education:
                    edu_degree = edu.get("degree", "").lower()
                    if required_education.lower() in edu_degree or edu_degree in required_education.lower():
                        education_score_percentage = 100
                        break
        
        # Calculate weighted total score
        total_score = (
            (job_title_percentage * 0.15) +
            (job_desc_percentage * 0.15) +
            (required_skill_percentage * 0.25) +
            (preferred_skill_percentage * 0.10) +
            (years_percentage * 0.20) +
            (education_score_percentage * 0.15)
        )
        
        # Prepare detailed breakdown
        return {
            "jobTitleScore": round(job_title_percentage, 1),
            "jobDescriptionScore": round(job_desc_percentage, 1),
            "requiredSkillsScore": round(required_skill_percentage, 1),
            "preferredSkillsScore": round(preferred_skill_percentage, 1),
            "yearsExperienceScore": round(years_percentage, 1),
            "educationScore": round(education_score_percentage, 1),
            "totalScore": round(total_score, 2),
            # Legacy fields for backward compatibility
            "skillsScore": round((required_skill_percentage * 0.7 + preferred_skill_percentage * 0.3), 1),
            "experienceScore": round(years_percentage, 1),
            "breakdown": {
                "job_title_match": job_title_score,
                "job_description_match": job_desc_score,
                "required_skills_matched": len(required_matched),
                "required_skills_total": len(required_skills),
                "preferred_skills_matched": len(preferred_matched),
                "preferred_skills_total": len(preferred_skills),
                "candidate_years": candidate_years,
                "required_years": required_years,
                "has_education": len(candidate_education) > 0,
            },
            "reasoning": self._generate_detailed_reasoning(
                job_title_percentage, job_desc_percentage,
                required_skill_percentage, preferred_skill_percentage,
                years_percentage, education_score_percentage,
                len(required_matched), len(required_skills),
                len(preferred_matched), len(preferred_skills),
                candidate_years, required_years
            )
        }
    
    def _calculate_semantic_similarity(self, experiences: List[Dict], job_title: str) -> float:
        """Calculate semantic similarity between candidate's experience titles and job title"""
        if not experiences or not job_title:
            return 0.0
        
        # Simple keyword matching (can be enhanced with embeddings)
        job_title_lower = job_title.lower()
        job_keywords = set(job_title_lower.split())
        
        max_similarity = 0.0
        for exp in experiences:
            exp_title = exp.get("title", "").lower()
            exp_keywords = set(exp_title.split())
            
            # Calculate Jaccard similarity
            if exp_keywords:
                intersection = job_keywords & exp_keywords
                union = job_keywords | exp_keywords
                similarity = len(intersection) / len(union) if union else 0
                max_similarity = max(max_similarity, similarity)
        
        return min(max_similarity * 1.5, 1.0)  # Boost and cap at 1.0
    
    def _calculate_description_similarity(self, candidate: Dict[str, Any], job_description: str) -> float:
        """Calculate semantic similarity between candidate profile and job description"""
        if not job_description:
            return 0.5
        
        # Build candidate profile text
        profile_parts = []
        profile_parts.extend(candidate.get("skills", []))
        
        for exp in candidate.get("experience", []):
            profile_parts.append(exp.get("title", ""))
            profile_parts.append(exp.get("description", ""))
        
        candidate_text = " ".join(profile_parts).lower()
        job_desc_lower = job_description.lower()
        
        # Extract keywords from job description
        desc_keywords = set(word for word in job_desc_lower.split() if len(word) > 3)
        
        # Count matching keywords
        matches = sum(1 for keyword in desc_keywords if keyword in candidate_text)
        
        if desc_keywords:
            similarity = matches / len(desc_keywords)
            return min(similarity * 1.2, 1.0)  # Boost and cap
        
        return 0.5
    
    def _generate_detailed_reasoning(self, job_title_pct, job_desc_pct, req_skills_pct, 
                                    pref_skills_pct, years_pct, edu_pct,
                                    req_matched, req_total, pref_matched, pref_total,
                                    cand_years, req_years) -> str:
        """Generate detailed reasoning with all scoring components"""
        parts = []
        
        # Job title match
        parts.append(f"Job title match: {job_title_pct:.0f}%")
        
        # Job description match
        parts.append(f"description match: {job_desc_pct:.0f}%")
        
        # Skills
        if req_total > 0:
            parts.append(f"{req_matched}/{req_total} required skills ({req_skills_pct:.0f}%)")
        if pref_total > 0:
            parts.append(f"{pref_matched}/{pref_total} preferred skills ({pref_skills_pct:.0f}%)")
        
        # Experience
        if req_years > 0:
            parts.append(f"{cand_years}yrs experience (required: {req_years}yrs, {years_pct:.0f}%)")
        else:
            parts.append(f"{cand_years} years of experience")
        
        # Education
        parts.append(f"education: {edu_pct:.0f}%")
        
        return ". ".join(parts) + "."
    
    def _generate_reasoning(self, req_matched, req_total, pref_matched, pref_total, 
                           cand_years, req_years, has_education) -> str:
        """Generate human-readable reasoning for the score"""
        parts = []
        
        # Skills reasoning
        if req_total > 0:
            parts.append(f"Matched {req_matched}/{req_total} required skills ({round(req_matched/req_total*100)}%)")
        if pref_total > 0:
            parts.append(f"{pref_matched}/{pref_total} preferred skills")
        
        # Experience reasoning
        if req_years > 0:
            parts.append(f"{cand_years} years experience (required: {req_years})")
        else:
            parts.append(f"{cand_years} years of experience")
        
        # Education reasoning
        if has_education:
            parts.append("Has education credentials")
        
        return ". ".join(parts) + "."
    
    def close(self):
        """Close connections"""
        if self.weaviate_client:
            self.weaviate_client.close()
