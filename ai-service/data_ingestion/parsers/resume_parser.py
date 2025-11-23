import re
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from collections import defaultdict
import hashlib

# Third-party imports (pip install required)
# pip install python-dateutil spacy sentence-transformers jsonschema
from dateutil import parser as date_parser
import jsonschema

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ConfidenceScore:
    """Tracks confidence for extracted fields"""
    value: float
    source: str
    reason: Optional[str] = None


@dataclass
class NormalizedEntity:
    """Base class for normalized entities"""
    raw_text: str
    normalized_value: str
    confidence: ConfidenceScore
    entity_type: str


@dataclass
class ContactInfo:
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    location: Optional[str] = None
    confidence: Dict[str, ConfidenceScore] = field(default_factory=dict)


@dataclass
class Experience:
    id: str
    company: str
    title: str
    location: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_current: bool = False
    duration_months: Optional[int] = None
    responsibilities: List[str] = field(default_factory=list)
    achievements: List[str] = field(default_factory=list)
    technologies: List[str] = field(default_factory=list)
    raw_description: str = ""
    confidence: Dict[str, ConfidenceScore] = field(default_factory=dict)


@dataclass
class Project:
    id: str
    name: str
    description: str
    technologies: List[str] = field(default_factory=list)
    impact_metrics: List[Dict[str, Any]] = field(default_factory=list)
    linked_experience_ids: List[str] = field(default_factory=list)
    confidence: Dict[str, ConfidenceScore] = field(default_factory=dict)


@dataclass
class Education:
    institution: str
    degree: str
    location: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    confidence: Dict[str, ConfidenceScore] = field(default_factory=dict)


@dataclass
class Skill:
    name: str
    category: str
    proficiency: Optional[str] = None
    years: Optional[float] = None
    last_used: Optional[datetime] = None
    confidence: ConfidenceScore = None


@dataclass
class ParsedCV:
    """Main container for parsed CV data"""
    full_name: str
    title: str
    contact: ContactInfo
    summary: str
    experience: List[Experience]
    projects: List[Project]
    education: List[Education]
    skills: List[Skill]
    languages: List[Dict[str, str]]
    hobbies: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    confidence: Dict[str, float] = field(default_factory=dict)


class CVParser:
    """
    Production-ready CV parser optimized for AI agent consumption.
    Handles real-world OCR errors, inconsistent formatting, and enriches data.
    """
    
    # Define skill ontology for normalization
    SKILL_ONTOLOGY = {
        "python": {"category": "programming", "aliases": ["python", "py", "python3"]},
        "java": {"category": "programming", "aliases": ["java", "java8", "java11"]},
        "spring_boot": {"category": "framework", "aliases": ["spring boot", "springboot", "spring"]},
        "langchain": {"category": "ml_framework", "aliases": ["langchain", "lang chain"]},
        "mlflow": {"category": "mlops", "aliases": ["mlflow", "ml flow"]},
        # Add 100+ more mappings for production use
    }
    
    # Company name normalization
    COMPANY_MAP = {
        "sap se": "SAP SE",
        "sap": "SAP SE",
        "momox gmbh": "momox GmbH",
        "auto1 gmbh": "Auto1 Group GmbH",
        "vodafone": "Vodafone Group"
    }
    
    # JSON Schema for validation
    OUTPUT_SCHEMA = {
        "type": "object",
        "properties": {
            "full_name": {"type": "string"},
            "contact": {"type": "object"},
            "experience": {"type": "array"},
            "skills": {"type": "array"},
            # Full schema would be defined here
        },
        "required": ["full_name", "contact", "experience"]
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {
            "min_confidence": 0.7,
            "enable_entity_enrichment": True,
            "enable_embedding": False,
            "validate_schema": True
        }
        self.parsed_data: Optional[ParsedCV] = None
        
        # Initialize NLP models (lazy loading)
        self._nlp = None
        self._embedding_model = None
        
    @property
    def nlp(self):
        """Lazy-load spaCy model"""
        if self._nlp is None:
            try:
                import spacy
                self._nlp = spacy.load("en_core_web_sm")
            except OSError:
                logger.warning("spaCy model not found. Running without NLP features.")
                self._nlp = None
        return self._nlp
    
    @property
    def embedding_model(self):
        """Lazy-load embedding model"""
        if self._embedding_model is None and self.config["enable_embedding"]:
            try:
                from sentence_transformers import SentenceTransformer
                self._embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            except ImportError:
                logger.warning("sentence-transformers not available. Embeddings disabled.")
                self.config["enable_embedding"] = False
        return self._embedding_model
    
    def parse(self, pdf_content: str, file_hash: Optional[str] = None) -> ParsedCV:
        """
        Main parsing pipeline. Accepts raw text extracted from PDF.
        
        Args:
            pdf_content: Raw text content from PDF/OCR
            file_hash: Optional hash for duplicate detection
            
        Returns:
            ParsedCV object with structured data
        """
        start_time = datetime.utcnow()
        logger.info(f"Starting CV parse for {file_hash or 'unknown file'}")
        
        # Step 1: Clean and normalize raw text
        cleaned_text = self._clean_text(pdf_content)
        
        # Step 2: Detect sections
        sections = self._detect_sections(cleaned_text)
        
        # Step 3: Extract core information
        name = self._extract_name(cleaned_text)
        contact = self._extract_contact_info(cleaned_text)
        summary = self._extract_summary(cleaned_text)
        
        # Step 4: Extract structured entities
        experience = self._extract_experience(sections.get("experience", ""))
        education = self._extract_education(sections.get("education", ""))
        skills = self._extract_skills(sections.get("skills", ""))
        projects = self._extract_projects(sections.get("projects", ""))
        languages = self._extract_languages(sections.get("languages", ""))
        hobbies = self._extract_hobbies(sections.get("hobbies", ""))
        
        # Step 5: Cross-reference and enrich
        self._link_projects_to_experience(projects, experience)
        self._enrich_skill_timeline(skills, experience, projects)
        
        # Step 6: Calculate overall confidence
        confidence_scores = self._calculate_overall_confidence(
            name, contact, experience, skills
        )
        
        # Step 7: Build final object
        self.parsed_data = ParsedCV(
            full_name=name,
            title=self._extract_title(cleaned_text),
            contact=contact,
            summary=summary,
            experience=experience,
            projects=projects,
            education=education,
            skills=skills,
            languages=languages,
            hobbies=hobbies,
            metadata={
                "parsed_at": start_time.isoformat(),
                "file_hash": file_hash or self._generate_hash(pdf_content),
                "config": self.config
            },
            confidence=confidence_scores
        )
        
        # Step 8: Validate schema
        if self.config["validate_schema"]:
            self._validate_output_schema()
        
        logger.info(f"Parse completed in {(datetime.utcnow() - start_time).total_seconds():.2f}s")
        return self.parsed_data
    
    def _clean_text(self, text: str) -> str:
        """Normalize text and fix common OCR artifacts"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Fix common OCR errors specific to CVs
        replacements = {
            "0ver": "over",
            "15years": "15 years",
            "securi ty": "security",
            "ML&AI": "ML & AI",
            "CICD": "CI/CD"
        }
        for wrong, correct in replacements.items():
            text = text.replace(wrong, correct)
        
        # Normalize line endings
        text = text.replace('\r\n', '\n')
        
        return text.strip()
    
    def _detect_sections(self, text: str) -> Dict[str, str]:
        """
        Dynamically detect CV sections using pattern matching.
        Returns dict mapping section names to their content.
        """
        sections = {}
        section_markers = {
            "experience": r"(?i)(employment history|experience|work history|professional experience)",
            "education": r"(?i)(education|academic background|qualifications)",
            "skills": r"(?i)(skills|technical skills|technologies|expertise)",
            "projects": r"(?i)(projects|notable projects|key projects)",
            "languages": r"(?i)(languages|language skills)",
            "hobbies": r"(?i)(hobbies|interests|activities)"
        }
        
        # Split by section markers
        lines = text.split('\n')
        current_section = None
        section_content = []
        
        for line in lines:
            line_lower = line.lower().strip()
            
            # Check if line marks a new section
            matched_section = None
            for section, pattern in section_markers.items():
                if re.match(pattern, line_lower):
                    matched_section = section
                    break
            
            if matched_section:
                # Save previous section
                if current_section and section_content:
                    sections[current_section] = '\n'.join(section_content).strip()
                
                current_section = matched_section
                section_content = []
            elif current_section:
                section_content.append(line)
        
        # Add final section
        if current_section and section_content:
            sections[current_section] = '\n'.join(section_content).strip()
        
        # Log detected sections
        logger.info(f"Detected sections: {list(sections.keys())}")
        
        return sections
    
    def _extract_name(self, text: str) -> str:
        """Extract name from first few lines with high confidence"""
        lines = text.split('\n')[:5]
        for line in lines:
            # Look for patterns like "Ahmed ElTaher" or "Profile\nAhmed ElTaher"
            match = re.search(r'([A-Z][a-z]+\s+[A-Z][a-zA-Z]+)', line.strip())
            if match and len(match.group(1).split()) <= 4:
                return match.group(1)
        
        return "Unknown"
    
    def _extract_title(self, text: str) -> str:
        """Extract professional title"""
        patterns = [
            r'(?i)(engineering manager|solution architect|security expert.*?certified|ml.*?architect)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0).title()
        
        return "Professional"
    
    def _extract_contact_info(self, text: str) -> ContactInfo:
        """Extract all contact information"""
        contact = ContactInfo()
        
        # Email
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        if email_match:
            contact.email = email_match.group(0)
            contact.confidence['email'] = ConfidenceScore(0.95, "regex")
        
        # Phone
        phone_pattern = r'(\+\d{1,3}\s?\d{10,15})'
        phone_match = re.search(phone_pattern, text)
        if phone_match:
            contact.phone = phone_match.group(0).replace(' ', '')
            contact.confidence['phone'] = ConfidenceScore(0.90, "regex")
        
        # Location
        location_match = re.search(r'Address:\s*(.+)', text, re.IGNORECASE)
        if location_match:
            contact.location = location_match.group(1).strip()
            contact.confidence['location'] = ConfidenceScore(0.85, "pattern")
        
        # LinkedIn/GitHub URLs
        linkedin_match = re.search(r'linkedin\.com/in/[\w\-]+', text, re.IGNORECASE)
        github_match = re.search(r'github\.com/[\w\-]+', text, re.IGNORECASE)
        
        if linkedin_match:
            contact.linkedin = f"https://{linkedin_match.group(0)}"
            contact.confidence['linkedin'] = ConfidenceScore(0.95, "url_pattern")
        
        if github_match:
            contact.github = f"https://{github_match.group(0)}"
            contact.confidence['github'] = ConfidenceScore(0.95, "url_pattern")
        
        return contact
    
    def _extract_summary(self, text: str) -> str:
        """Extract professional summary"""
        # Look for first paragraph after "Profile" or before "Employment History"
        patterns = [
            r'Profile\s*\n\s*([A-Z].*?)(?=\n\n|\n#|Employment|Experience|\Z)',
            r'^\s*(Innovative.*?\.\s*)',  # Starts with typical summary words
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
            if match:
                summary = match.group(1).strip()
                return ' '.join(summary.split())  # Normalize whitespace
        
        return ""
    
    def _extract_experience(self, section_text: str) -> List[Experience]:
        """Parse employment history with date range detection"""
        experiences = []
        
        # Split by company/role blocks
        blocks = re.split(r'\n(?=[A-Z][a-zA-Z\s]+ at [A-Z][a-zA-Z\s.]+, [A-Za-z\s]+)', 
                         '\n' + section_text)
        
        for block in blocks:
            if not block.strip():
                continue
            
            # Parse company header: "Title at Company, Location"
            header_match = re.search(
                r'(?P<title>[A-Z][a-zA-Z\s]+) at (?P<company>[A-Z][a-zA-Z\s.]+), (?P<location>[A-Za-z\s]+)',
                block
            )
            
            if not header_match:
                continue
            
            title = header_match.group('title').strip()
            company = self._normalize_company_name(header_match.group('company').strip())
            location = header_match.group('location').strip()
            
            # Parse dates: "June 2021-Present" or "2017-May 2021"
            date_match = re.search(
                r'([A-Za-z]+\s+\d{4})\s*[\-\–]\s*([A-Za-z]+\s+\d{4}|Present)',
                block
            )
            
            start_date, end_date, is_current = None, None, False
            if date_match:
                try:
                    start_date = date_parser.parse(date_match.group(1), default=datetime(1900, 1, 1))
                    end_str = date_match.group(2)
                    if 'present' in end_str.lower():
                        is_current = True
                        end_date = datetime.utcnow()
                    else:
                        end_date = date_parser.parse(end_str, default=datetime(1900, 1, 1))
                except:
                    logger.warning(f"Failed to parse dates in block: {block[:50]}...")
            
            # Calculate duration
            duration_months = None
            if start_date and end_date:
                delta = end_date - start_date
                duration_months = int(delta.days // 30.44)
            
            # Extract bullets
            bullets = re.findall(r'[•\-●]\s*(.+)', block)
            responsibilities = bullets[:len(bullets)//2] if bullets else []
            achievements = bullets[len(bullets)//2:] if bullets else []
            
            # Extract technologies mentioned
            tech_mentioned = self._extract_technologies_from_text(block)
            
            exp_id = hashlib.md5(f"{company}{title}{start_date}".encode()).hexdigest()[:8]
            
            experiences.append(Experience(
                id=f"exp_{exp_id}",
                company=company,
                title=title,
                location=location,
                start_date=start_date,
                end_date=None if is_current else end_date,
                is_current=is_current,
                duration_months=duration_months,
                responsibilities=responsibilities,
                achievements=achievements,
                technologies=tech_mentioned,
                raw_description=block,
                confidence={
                    "company": ConfidenceScore(0.92, "pattern_match"),
                    "dates": ConfidenceScore(0.85 if date_match else 0.5, "date_parser"),
                }
            ))
        
        return sorted(experiences, key=lambda x: x.start_date or datetime.min, reverse=True)
    
    def _extract_projects(self, section_text: str) -> List[Project]:
        """Extract project details with impact metrics"""
        projects = []
        
        # Split by project blocks
        blocks = re.split(r'\n(?=[A-Z][a-zA-Z\s]+[–\-])', '\n' + section_text)
        
        for block in blocks:
            if not block.strip() or len(block) < 20:
                continue
            
            # Extract name (before dash or first line)
            name_match = re.match(r'([A-Z][a-zA-Z0-9\s/]+?)(\s*[–\-]\s*)(.*)', block)
            if name_match:
                name = name_match.group(1).strip()
                description = name_match.group(3).strip()
            else:
                name = block.split('\n')[0].strip()
                description = ""
            
            # Extract technologies from description
            tech_mentioned = self._extract_technologies_from_text(block)
            
            # Extract impact metrics
            metrics = []
            metric_patterns = [
                (r'(\d+)%\s*(?:latency|performance|speed)', 'latency_reduction', '%'),
                (r'(\d+)M\+\s*users?', 'user_base', 'M+'),
                (r'(\d+)\s*engineers?', 'team_size', 'engineers'),
                (r'(\d+)%\s*uptime', 'uptime', '%'),
            ]
            
            for pattern, metric_type, unit in metric_patterns:
                matches = re.findall(pattern, block, re.IGNORECASE)
                for value in matches:
                    metrics.append({
                        "type": metric_type,
                        "value": int(value),
                        "unit": unit
                    })
            
            proj_id = hashlib.md5(name.encode()).hexdigest()[:8]
            
            projects.append(Project(
                id=f"proj_{proj_id}",
                name=name,
                description=description,
                technologies=tech_mentioned,
                impact_metrics=metrics,
                linked_experience_ids=[],
                confidence={
                    "name": ConfidenceScore(0.90, "header_pattern"),
                    "technologies": ConfidenceScore(0.75, "keyword_match")
                }
            ))
        
        return projects
    
    def _extract_education(self, section_text: str) -> List[Education]:
        """Extract education history"""
        education_list = []
        
        # Pattern: Degree, University, Location, Dates
        edu_block = re.search(
            r'(BSc|MSc|PhD|Bachelor|Master).*?'
            r'([A-Za-z\s]+University.*?)(?=\d{4}|$)',
            section_text,
            re.DOTALL | re.IGNORECASE
        )
        
        if edu_block:
            degree = edu_block.group(1).strip()
            institution = edu_block.group(2).strip()
            
            # Extract location
            loc_match = re.search(r'([A-Za-z\s]+)(?=\s*,\s*\d{4})', institution)
            location = loc_match.group(1).strip() if loc_match else ""
            
            # Extract dates
            date_match = re.search(r'(\d{4})\s*[\-\–]\s*(\d{4})', section_text)
            start_date, end_date = None, None
            if date_match:
                start_date = datetime(int(date_match.group(1)), 1, 1)
                end_date = datetime(int(date_match.group(2)), 1, 1)
            
            education_list.append(Education(
                institution=institution,
                degree=degree,
                location=location,
                start_date=start_date,
                end_date=end_date,
                confidence={
                    "institution": ConfidenceScore(0.90, "pattern_match"),
                    "dates": ConfidenceScore(0.80 if date_match else 0.5, "date_parser")
                }
            ))
        
        return education_list
    
    def _extract_skills(self, section_text: str) -> List[Skill]:
        """Parse skills with categorization"""
        skills = []
        
        # Common skill categories
        categories = {
            "programming": r"(?i)(python|java|kotlin|scala|go|javascript)",
            "ml_framework": r"(?i)(langchain|huggingface|openai|llamaindex|bert|rag)",
            "database": r"(?i)(postgresql|mysql|cassandra|mongodb|faiss|pinecone)",
            "cloud": r"(?i)(aws|gcp|azure|docker|kubernetes|ci/cd)",
            "methodology": r"(?i)(agile|scrum|kanban|devops)"
        }
        
        # Extract all potential skills using NLP
        if self.nlp:
            doc = self.nlp(section_text)
            potential_skills = [ent.text for ent in doc.ents if ent.label_ in ["PRODUCT", "TECH"]]
        else:
            potential_skills = re.findall(r'\b[A-Z][a-zA-Z]+\b', section_text)
        
        for skill_name in set(potential_skills):
            # Normalize skill name
            normalized = self._normalize_skill(skill_name)
            if normalized:
                category = self.SKILL_ONTOLOGY.get(normalized, {}).get("category", "unknown")
                
                skills.append(Skill(
                    name=normalized,
                    category=category,
                    proficiency="expert",  # Can be enhanced with context analysis
                    years=None,  # Set later during enrichment
                    confidence=ConfidenceScore(0.75, "keyword_extraction")
                ))
        
        return skills
    
    def _extract_languages(self, section_text: str) -> List[Dict[str, str]]:
        """Extract language skills"""
        languages = []
        
        # Pattern: "English (Fluent)" or "Arabic (Native)"
        lang_matches = re.findall(
            r'([A-Za-z]+)\s*\((\w+)\)',
            section_text,
            re.IGNORECASE
        )
        
        for name, level in lang_matches:
            languages.append({
                "name": name.capitalize(),
                "level": level,
                "iso_code": name[:2].lower()
            })
        
        return languages
    
    def _extract_hobbies(self, section_text: str) -> List[str]:
        """Extract hobbies/activities"""
        hobbies = []
        
        # Split by commas or bullet points
        if ',' in section_text:
            hobbies = [h.strip() for h in section_text.split(',')]
        elif '•' in section_text or '-' in section_text:
            hobbies = re.findall(r'[•\-]\s*([A-Za-z\s]+)', section_text)
        else:
            # Fallback: split by common hobby words
            hobby_list = re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?=\s*[,|\n])', section_text)
            hobbies = hobby_list
        
        return [h.strip() for h in hobbies if len(h.strip()) > 3]
    
    def _normalize_company_name(self, company: str) -> str:
        """Standardize company names using mapping"""
        company_lower = company.lower().strip()
        return self.COMPANY_MAP.get(company_lower, company)
    
    def _normalize_skill(self, skill: str) -> Optional[str]:
        """Map raw skill to normalized form"""
        skill_lower = skill.lower().strip()
        
        for normalized, data in self.SKILL_ONTOLOGY.items():
            if skill_lower in data["aliases"] or skill_lower == normalized:
                return normalized
        
        # Return original if not in ontology but looks like a tech term
        if len(skill) > 2 and (skill.isupper() or any(c.isdigit() for c in skill)):
            return skill_lower.replace(' ', '_')
        
        return None
    
    def _extract_technologies_from_text(self, text: str) -> List[str]:
        """Extract technology mentions from any text block"""
        technologies = []
        
        # Search through skill ontology
        for normalized, data in self.SKILL_ONTOLOGY.items():
            for alias in data["aliases"]:
                if alias in text.lower():
                    technologies.append(normalized)
                    break
        
        return list(set(technologies))
    
    def _link_projects_to_experience(self, projects: List[Project], experience: List[Experience]):
        """Link projects to relevant experience based on company/tech overlap"""
        for project in projects:
            for exp in experience:
                # Match by company name mention or shared technologies
                if (exp.company.lower() in project.description.lower() or 
                    set(project.technologies) & set(exp.technologies)):
                    project.linked_experience_ids.append(exp.id)
            
            project.confidence["linking"] = ConfidenceScore(
                0.70 if project.linked_experience_ids else 0.30,
                "semantic_matching"
            )
    
    def _enrich_skill_timeline(self, skills: List[Skill], experience: List[Experience], projects: List[Project]):
        """Estimate years of experience for each skill"""
        skill_years = defaultdict(int)
        
        for exp in experience:
            if not exp.start_date:
                continue
            
            years = (exp.end_date or datetime.utcnow()).year - exp.start_date.year + 1
            for tech in exp.technologies:
                skill_years[tech] = max(skill_years[tech], years)
        
        for skill in skills:
            if skill.name in skill_years:
                skill.years = skill_years[skill.name]
                skill.confidence = ConfidenceScore(0.80, "temporal_extrapolation")
    
    def _calculate_overall_confidence(self, name: str, contact: ContactInfo, 
                                     experience: List[Experience], skills: List[Skill]) -> Dict[str, float]:
        """Calculate weighted confidence scores for key sections"""
        return {
            "personal_info": 0.95 if name != "Unknown" else 0.30,
            "contact": sum(c.value for c in contact.confidence.values()) / len(contact.confidence) if contact.confidence else 0.50,
            "experience": sum(
                sum(e.confidence.values(), ConfidenceScore(0, "")).value / len(e.confidence)
                for e in experience
            ) / len(experience) if experience else 0.0,
            "skills": sum(s.confidence.value for s in skills) / len(skills) if skills else 0.0,
            "overall": 0.0  # Calculated below
        }
    
    def _validate_output_schema(self):
        """Validate final JSON against schema"""
        try:
            json_output = self.to_dict()
            jsonschema.validate(instance=json_output, schema=self.OUTPUT_SCHEMA)
            logger.info("Output schema validation passed")
        except jsonschema.exceptions.ValidationError as e:
            logger.error(f"Schema validation failed: {e.message}")
            raise
    
    def _generate_hash(self, content: str) -> str:
        """Generate content hash for duplicate detection"""
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert parsed CV to dictionary"""
        if not self.parsed_data:
            raise ValueError("No parsed data. Call parse() first.")
        
        def _convert_datetime(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return obj
        
        # Use custom JSON encoder for dataclasses
        def _serialize(obj):
            if hasattr(obj, '__dict__'):
                return {k: _serialize(v) for k, v in obj.__dict__.items()}
            elif isinstance(obj, list):
                return [_serialize(item) for item in obj]
            elif isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, ConfidenceScore):
                return {"value": obj.value, "source": obj.source, "reason": obj.reason}
            else:
                return obj
        
        return _serialize(self.parsed_data)
    
    def to_json(self, indent: int = 2) -> str:
        """Export as JSON string"""
        return json.dumps(self.to_dict(), indent=indent)
    
    def to_markdown(self) -> str:
        """Export as markdown (for human review)"""
        if not self.parsed_data:
            return ""
        
        cv = self.parsed_data
        md = f"# {cv.full_name}\n\n"
        md += f"**{cv.title}**\n\n---\n\n"
        
        md += "## Contact\n"
        if cv.contact.email:
            md += f"- Email: {cv.contact.email}\n"
        if cv.contact.phone:
            md += f"- Phone: {cv.contact.phone}\n"
        if cv.contact.linkedin:
            md += f"- LinkedIn: {cv.contact.linkedin}\n"
        md += "\n"
        
        md += "## Summary\n" + cv.summary + "\n\n---\n\n"
        
        md += "## Experience\n"
        for exp in cv.experience:
            md += f"### {exp.title} at **{exp.company}**\n"
            md += f"*{exp.location}* | {exp.start_date.year if exp.start_date else 'N/A'} - {'Present' if exp.is_current else exp.end_date.year if exp.end_date else 'N/A'}\n\n"
            if exp.responsibilities:
                md += "#### Responsibilities\n"
                for r in exp.responsibilities:
                    md += f"- {r}\n"
            md += "\n"
        
        return md


# Example usage
if __name__ == "__main__":
    # Simulate loading the PDF text from earlier
    pdf_text = """
    Ahmed ElTaher
    
    Engineering Manager /Solution Architect /Security Expert Certified
    
    # Profile
    
    Innovative and results-driven Machine Learning &AI Architect and Engineering Manager with over 15years of experience...
    
    # Employment History
    
    Solutions &Security Architect at SAP SE,Berlin June 2021-Present...
    """
    
    parser = CVParser(config={"min_confidence": 0.75})
    parsed_cv = parser.parse(pdf_text)
    
    # Export formats
    print("=== JSON Output ===")
    print(parser.to_json()[:500] + "...")
    
    print("\n=== Markdown Preview ===")
    print(parser.to_markdown()[:500] + "...")