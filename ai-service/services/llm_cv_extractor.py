"""
Direct Ollama LLM Integration for CV Extraction

Bypasses LangChain to directly call Ollama API for CV information extraction.
Uses cached text files and system prompts for extraction.
"""

import requests
import json
import logging
from typing import Dict, Any, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LLMCVExtractor:
    """
    Direct integration with Ollama for CV extraction from text files.
    """
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "qwen2.5:7b"):
        """
        Initialize LLM CV extractor.
        
        Args:
            base_url: Ollama API base URL
            model: Model name to use
        """
        self.base_url = base_url
        self.model = model
        self.api_url = f"{base_url}/api/generate"
        
        # Test connection
        try:
            response = requests.get(f"{base_url}/api/version", timeout=2)
            if response.status_code == 200:
                logger.info(f"✅ Connected to Ollama v{response.json().get('version')}")
            else:
                logger.warning(f"⚠️  Ollama responded with status {response.status_code}")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Ollama: {e}")
    
    def extract_from_text(self, cv_text: str) -> Dict[str, Any]:
        """
        Extract CV information from text using LLM.
        
        Args:
            cv_text: Plain text content of CV
            
        Returns:
            Dictionary with extracted CV information
        """
        system_prompt = """You are an expert CV/Resume parser. Extract structured information from the CV text provided.

Extract the following information and return it as valid JSON:

1. **Personal Information**:
   - full_name (string)
   - email (string)
   - phone (string)
   - City and Country (if available)

2. **Skills** (array of strings):
   - Extract all technical skills, programming languages, frameworks, tools
   - Normalize skill names (e.g., "JavaScript" not "javascript")

3. **Experience** (array of objects):
   Each experience entry should have:
   - title (job title)
   - company (company name)
   - location (city, country - if available)
   - startDate (YYYY-MM format)
   - endDate (YYYY-MM or "Present")
   - description (brief summary)
   - responsibilities (array of key responsibilities)

4. **Education** (array of objects):
   Each education entry should have:
   - degree (e.g., "Bachelor's Degree", "Master's", "PhD")
   - institution (university/college name)
   - startDate (YYYY)
   - endDate (YYYY)
   - fieldOfStudy (major/field - if available)

5. **Years of Experience** (float):
   - Calculate total professional experience in years (can be decimal like 5.5)

Return ONLY valid JSON with this structure. Do not include any explanatory text.

JSON Template:
{
  "full_name": "string",
  "email": "string",
  "phone": "string",
  "skills": ["skill1", "skill2"],
  "experience": [
    {
      "title": "string",
      "company": "string",
      "location": "string",
      "startDate": "YYYY-MM",
      "endDate": "YYYY-MM or Present",
      "description": "string",
      "responsibilities": ["resp1", "resp2"]
    }
  ],
  "education": [
    {
      "degree": "string",
      "institution": "string",
      "startDate": "YYYY",
      "endDate": "YYYY",
      "fieldOfStudy": "string"
    }
  ],
  "years_of_experience": 0.0
}"""
        
        # Prepare prompt
        full_prompt = f"{system_prompt}\n\nCV Text:\n{cv_text}\n\nExtracted JSON:"
        
        try:
            logger.info(f"Sending CV text to Ollama ({len(cv_text)} chars)...")
            
            # Call Ollama API
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,  # Low temperature for consistent extraction
                        "num_predict": 2000   # Max tokens for response
                    }
                },
                timeout=60  # 60 second timeout
            )
            
            if response.status_code != 200:
                logger.error(f"Ollama API error: {response.status_code}")
                return {}
            
            # Parse response
            result = response.json()
            generated_text = result.get("response", "")
            
            logger.info(f"✅ LLM generated {len(generated_text)} chars")
            
            # Extract JSON from response
            extracted_data = self._extract_json_from_text(generated_text)
            
            if extracted_data:
                logger.info(f"✅ Successfully extracted CV data with {len(extracted_data.get('skills', []))} skills")
                return extracted_data
            else:
                logger.warning("⚠️  Failed to extract valid JSON from LLM response")
                return {}
                
        except requests.Timeout:
            logger.error("❌ Ollama API timeout")
            return {}
        except Exception as e:
            logger.error(f"❌ Error calling Ollama API: {e}")
            return {}
    
    def _extract_json_from_text(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Extract and parse JSON from text that may contain other content.
        
        Args:
            text: Text containing JSON
            
        Returns:
            Parsed JSON dict or None
        """
        # Try to find JSON block
        import re
        
        # Look for JSON between curly braces
        json_match = re.search(r'\{[\s\S]*\}', text)
        
        if json_match:
            try:
                json_str = json_match.group(0)
                parsed = json.loads(json_str)
                return parsed
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON: {e}")
                # Try to clean and parse again
                try:
                    # Remove comments
                    json_str = re.sub(r'//.*?\n', '', json_str)
                    json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
                    parsed = json.loads(json_str)
                    return parsed
                except:
                    pass
        
        return None
    
    def is_available(self) -> bool:
        """Check if Ollama is available"""
        try:
            response = requests.get(f"{self.base_url}/api/version", timeout=2)
            return response.status_code == 200
        except:
            return False
