import os
from typing import List, Dict, Any
from langchain_community.llms import Ollama
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain


class CandidateRanker:
    def __init__(self):
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model_name = os.getenv("MODEL_NAME", "qwen2.5:7b")
        
        # Initialize Ollama LLM
        self.llm = Ollama(
            base_url=self.ollama_url,
            model=self.model_name,
            temperature=0.2
        )
        
        # Scoring weights
        self.weights = {
            "skills": 0.40,
            "experience": 0.30,
            "education": 0.20,
            "years_experience": 0.10
        }
    
    async def rank_candidates(
        self,
        job_requirements: Dict[str, Any],
        candidates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Rank candidates based on job requirements"""
        
        ranked_candidates = []
        
        for candidate in candidates:
            score, details = await self._score_candidate(
                candidate,
                job_requirements
            )
            
            ranked_candidates.append({
                "id": candidate["id"],
                "email": candidate["email"],
                "full_name": candidate["full_name"],
                "score": round(score, 2),
                "scoring_details": details
            })
        
        # Sort by score descending
        ranked_candidates.sort(key=lambda x: x["score"], reverse=True)
        
        return ranked_candidates
    
    async def _score_candidate(
        self,
        candidate: Dict[str, Any],
        job_requirements: Dict[str, Any]
    ) -> tuple[float, Dict[str, Any]]:
        """Score a single candidate against job requirements"""
        
        # Skills score
        skills_score = self._calculate_skills_score(
            candidate.get("skills", []),
            job_requirements.get("required_skills", []),
            job_requirements.get("preferred_skills", [])
        )
        
        # Experience score
        experience_score = await self._calculate_experience_score(
            candidate.get("experience", []),
            job_requirements.get("title", ""),
            job_requirements.get("description", "")
        )
        
        # Education score
        education_score = self._calculate_education_score(
            candidate.get("education", []),
            job_requirements.get("required_education", "")
        )
        
        # Years of experience score
        years_score = self._calculate_years_score(
            candidate.get("years_of_experience", 0),
            job_requirements.get("min_years_experience", 0)
        )
        
        # Calculate weighted overall score
        overall_score = (
            skills_score * self.weights["skills"] +
            experience_score * self.weights["experience"] +
            education_score * self.weights["education"] +
            years_score * self.weights["years_experience"]
        ) * 100  # Convert to percentage
        
        # Generate reasoning using LLM
        reasoning = await self._generate_reasoning(
            candidate,
            job_requirements,
            skills_score,
            experience_score,
            education_score,
            years_score
        )
        
        details = {
            "skillsScore": round(skills_score * 100, 2),
            "experienceScore": round(experience_score * 100, 2),
            "educationScore": round(education_score * 100, 2),
            "yearsExperienceScore": round(years_score * 100, 2),
            "overallScore": round(overall_score, 2),
            "reasoning": reasoning
        }
        
        return overall_score, details
    
    def _calculate_skills_score(
        self,
        candidate_skills: List[str],
        required_skills: List[str],
        preferred_skills: List[str]
    ) -> float:
        """Calculate skills match score"""
        
        if not required_skills:
            return 0.5  # Neutral score if no requirements
        
        # Normalize skills to lowercase for comparison
        candidate_skills_lower = [s.lower() for s in candidate_skills]
        required_skills_lower = [s.lower() for s in required_skills]
        preferred_skills_lower = [s.lower() for s in preferred_skills]
        
        # Count required skills matches
        required_matches = sum(
            1 for skill in required_skills_lower
            if skill in candidate_skills_lower
        )
        required_score = required_matches / len(required_skills_lower) if required_skills_lower else 0
        
        # Count preferred skills matches (bonus)
        preferred_matches = sum(
            1 for skill in preferred_skills_lower
            if skill in candidate_skills_lower
        ) if preferred_skills_lower else 0
        preferred_score = (preferred_matches / len(preferred_skills_lower)) * 0.3 if preferred_skills_lower else 0
        
        # Combine scores (required is 70%, preferred is 30% bonus)
        total_score = min(required_score * 0.7 + preferred_score, 1.0)
        
        return total_score
    
    async def _calculate_experience_score(
        self,
        experiences: List[Dict[str, Any]],
        job_title: str,
        job_description: str
    ) -> float:
        """Calculate experience relevance score using LLM"""
        
        if not experiences:
            return 0.0
        
        try:
            # Create experience summary
            exp_summary = "\n".join([
                f"- {exp.get('title', '')} at {exp.get('company', '')} ({exp.get('startDate', '')} - {exp.get('endDate', '')})"
                for exp in experiences[:5]  # Limit to 5 most recent
            ])
            
            prompt = f"""
On a scale of 0.0 to 1.0, rate how relevant this candidate's experience is for the job.

Job Title: {job_title}
Job Description: {job_description[:500]}

Candidate's Experience:
{exp_summary}

Return ONLY a number between 0.0 and 1.0 (e.g., 0.75)
"""
            
            result = await self.llm.ainvoke(prompt)
            
            # Extract score from result
            score_text = result.strip()
            score = float(score_text) if score_text.replace('.', '').isdigit() else 0.5
            
            return max(0.0, min(1.0, score))  # Clamp between 0 and 1
        
        except Exception as e:
            print(f"Error calculating experience score: {e}")
            return 0.5  # Return neutral score on error
    
    def _calculate_education_score(
        self,
        education: List[Dict[str, Any]],
        required_education: str
    ) -> float:
        """Calculate education match score"""
        
        if not required_education or not education:
            return 0.5  # Neutral score if no requirements or education
        
        # Education level hierarchy
        education_levels = {
            "phd": 5,
            "doctorate": 5,
            "master": 4,
            "mba": 4,
            "bachelor": 3,
            "associate": 2,
            "diploma": 1,
            "certificate": 1
        }
        
        # Get required education level
        required_level = 0
        for key, value in education_levels.items():
            if key in required_education.lower():
                required_level = value
                break
        
        # Get candidate's highest education level
        candidate_level = 0
        for edu in education:
            degree = edu.get("degree", "").lower()
            for key, value in education_levels.items():
                if key in degree:
                    candidate_level = max(candidate_level, value)
        
        # Calculate score based on level match
        if candidate_level >= required_level:
            return 1.0
        elif candidate_level == required_level - 1:
            return 0.7
        else:
            return 0.4
    
    def _calculate_years_score(
        self,
        candidate_years: float,
        required_years: float
    ) -> float:
        """Calculate years of experience score"""
        
        if required_years == 0:
            return 1.0  # No requirement
        
        if candidate_years >= required_years:
            # Full score if meets requirement, bonus for exceeding
            excess_years = candidate_years - required_years
            bonus = min(excess_years / required_years * 0.2, 0.2)  # Up to 20% bonus
            return min(1.0 + bonus, 1.0)
        else:
            # Partial score if below requirement
            return candidate_years / required_years
    
    async def _generate_reasoning(
        self,
        candidate: Dict[str, Any],
        job_requirements: Dict[str, Any],
        skills_score: float,
        experience_score: float,
        education_score: float,
        years_score: float
    ) -> str:
        """Generate human-readable reasoning for the score using LLM"""
        
        try:
            prompt = f"""
Provide a brief 2-3 sentence explanation for why this candidate scored {(skills_score + experience_score + education_score + years_score) / 4 * 100:.0f}% for the job.

Job: {job_requirements.get('title', 'N/A')}
Required Skills: {', '.join(job_requirements.get('required_skills', [])[:5])}

Candidate: {candidate.get('full_name', 'Candidate')}
Skills: {', '.join(candidate.get('skills', [])[:5])}
Experience: {candidate.get('years_of_experience', 0)} years

Score Breakdown:
- Skills: {skills_score * 100:.0f}%
- Experience: {experience_score * 100:.0f}%
- Education: {education_score * 100:.0f}%
- Years: {years_score * 100:.0f}%

Provide a concise explanation focusing on strengths and gaps.
"""
            
            reasoning = await self.llm.ainvoke(prompt)
            return reasoning.strip()[:500]  # Limit length
        
        except Exception as e:
            print(f"Error generating reasoning: {e}")
            return f"Candidate scored {(skills_score + experience_score + education_score + years_score) / 4 * 100:.0f}% based on skills, experience, education, and years of experience match."
