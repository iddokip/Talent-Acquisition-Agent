"""
Weaviate Vector Database Client

Manages CV data storage in Weaviate vector database with embeddings.
Stores extracted CV information and plain text metadata for semantic search.
"""

import os
import logging
from typing import Dict, List, Any, Optional
import weaviate
from weaviate.classes.init import Auth
import weaviate.classes as wvc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WeaviateClient:
    """
    Client for storing and querying CV data in Weaviate vector database.
    """
    
    def __init__(
        self,
        url: str = "http://localhost:8080",
        api_key: Optional[str] = None
    ):
        """
        Initialize Weaviate client.
        
        Args:
            url: Weaviate instance URL
            api_key: Optional API key for authentication
        """
        self.url = url
        self.api_key = api_key
        self.client = None
        self.collection_name = "CVDocument"
        
        try:
            self._connect()
            self._ensure_schema()
            logger.info("✅ Weaviate client initialized successfully")
        except Exception as e:
            logger.warning(f"⚠️  Weaviate not available: {e}")
            self.client = None
    
    def _connect(self):
        """Connect to Weaviate instance"""
        try:
            if self.api_key:
                auth_config = Auth.api_key(self.api_key)
                self.client = weaviate.connect_to_custom(
                    http_host=self.url.replace("http://", "").replace("https://", ""),
                    http_port=8080,
                    http_secure=False,
                    auth_credentials=auth_config
                )
            else:
                # Local connection without auth
                self.client = weaviate.connect_to_local(
                    host=self.url.replace("http://", "").replace("https://", "").split(":")[0],
                    port=8080
                )
            
            if self.client.is_ready():
                logger.info(f"✅ Connected to Weaviate at {self.url}")
            else:
                raise ConnectionError("Weaviate is not ready")
                
        except Exception as e:
            logger.error(f"❌ Failed to connect to Weaviate: {e}")
            raise
    
    def _ensure_schema(self):
        """Create CV collection schema if it doesn't exist"""
        if not self.client:
            return
        
        try:
            # Check if collection exists
            collections = self.client.collections.list_all()
            
            if self.collection_name in [c.name for c in collections.values()]:
                logger.info(f"Collection '{self.collection_name}' already exists")
                return
            
            # Create collection with properties
            self.client.collections.create(
                name=self.collection_name,
                description="CV/Resume documents with extracted information",
                vectorizer_config=wvc.config.Configure.Vectorizer.none(),  # We'll provide vectors
                properties=[
                    wvc.config.Property(
                        name="candidate_id",
                        data_type=wvc.config.DataType.TEXT,
                        description="Unique candidate identifier"
                    ),
                    wvc.config.Property(
                        name="full_name",
                        data_type=wvc.config.DataType.TEXT,
                        description="Candidate full name"
                    ),
                    wvc.config.Property(
                        name="email",
                        data_type=wvc.config.DataType.TEXT,
                        description="Email address"
                    ),
                    wvc.config.Property(
                        name="phone",
                        data_type=wvc.config.DataType.TEXT,
                        description="Phone number"
                    ),
                    wvc.config.Property(
                        name="skills",
                        data_type=wvc.config.DataType.TEXT_ARRAY,
                        description="List of skills"
                    ),
                    wvc.config.Property(
                        name="years_of_experience",
                        data_type=wvc.config.DataType.NUMBER,
                        description="Total years of professional experience"
                    ),
                    wvc.config.Property(
                        name="experience_json",
                        data_type=wvc.config.DataType.TEXT,
                        description="Work experience in JSON format"
                    ),
                    wvc.config.Property(
                        name="education_json",
                        data_type=wvc.config.DataType.TEXT,
                        description="Education history in JSON format"
                    ),
                    wvc.config.Property(
                        name="plain_text",
                        data_type=wvc.config.DataType.TEXT,
                        description="Original CV plain text content"
                    ),
                    wvc.config.Property(
                        name="file_hash",
                        data_type=wvc.config.DataType.TEXT,
                        description="Unique file hash for deduplication"
                    ),
                    wvc.config.Property(
                        name="parsed_at",
                        data_type=wvc.config.DataType.TEXT,
                        description="Timestamp when CV was parsed"
                    ),
                    wvc.config.Property(
                        name="parsing_method",
                        data_type=wvc.config.DataType.TEXT,
                        description="Method used for parsing (llm, regex, hybrid)"
                    ),
                    wvc.config.Property(
                        name="confidence_score",
                        data_type=wvc.config.DataType.NUMBER,
                        description="Confidence score of extraction (0-1)"
                    )
                ]
            )
            
            logger.info(f"✅ Created collection '{self.collection_name}' with schema")
            
        except Exception as e:
            logger.error(f"❌ Failed to create schema: {e}")
            raise
    
    def store_cv(
        self,
        cv_data: Dict[str, Any],
        plain_text: str,
        candidate_id: Optional[str] = None,
        vector: Optional[List[float]] = None
    ) -> Optional[str]:
        """
        Store CV data in Weaviate with plain text metadata.
        
        Args:
            cv_data: Extracted CV information from LLM
            plain_text: Original CV plain text content
            candidate_id: Optional candidate identifier
            vector: Optional embedding vector (if not provided, will be generated)
            
        Returns:
            UUID of stored object or None if failed
        """
        if not self.client:
            logger.warning("⚠️  Weaviate client not available, skipping storage")
            return None
        
        try:
            import json
            
            # Prepare data for storage
            properties = {
                "candidate_id": candidate_id or cv_data.get("file_hash", "unknown"),
                "full_name": cv_data.get("full_name", "Unknown"),
                "email": cv_data.get("email", ""),
                "phone": cv_data.get("phone", ""),
                "skills": cv_data.get("skills", []),
                "years_of_experience": float(cv_data.get("years_of_experience", 0.0)),
                "experience_json": json.dumps(cv_data.get("experience", [])),
                "education_json": json.dumps(cv_data.get("education", [])),
                "plain_text": plain_text,  # Store full plain text as metadata
                "file_hash": cv_data.get("file_hash", "unknown"),
                "parsed_at": cv_data.get("metadata", {}).get("parsed_at", ""),
                "parsing_method": cv_data.get("confidence", {}).get("method", "unknown"),
                "confidence_score": float(cv_data.get("confidence", {}).get("overall", 0.75))
            }
            
            # Get collection
            collection = self.client.collections.get(self.collection_name)
            
            # Insert with or without vector
            if vector:
                uuid = collection.data.insert(
                    properties=properties,
                    vector=vector
                )
            else:
                # Insert without vector (can be added later via embedding service)
                uuid = collection.data.insert(
                    properties=properties
                )
            
            logger.info(f"✅ Stored CV in Weaviate: {uuid}")
            logger.info(f"   - Name: {properties['full_name']}")
            logger.info(f"   - Skills: {len(properties['skills'])} skills")
            logger.info(f"   - Text length: {len(plain_text)} chars")
            
            return str(uuid)
            
        except Exception as e:
            logger.error(f"❌ Failed to store CV in Weaviate: {e}")
            return None
    
    def search_similar_cvs(
        self,
        query_text: str,
        limit: int = 10,
        min_confidence: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search for similar CVs using semantic search.
        
        Args:
            query_text: Search query
            limit: Maximum number of results
            min_confidence: Minimum confidence score filter
            
        Returns:
            List of matching CV documents
        """
        if not self.client:
            logger.warning("⚠️  Weaviate client not available")
            return []
        
        try:
            collection = self.client.collections.get(self.collection_name)
            
            # Perform hybrid search (keyword + vector if available)
            response = collection.query.near_text(
                query=query_text,
                limit=limit,
                return_properties=[
                    "candidate_id", "full_name", "email", "phone",
                    "skills", "years_of_experience", "plain_text",
                    "confidence_score", "parsing_method"
                ]
            )
            
            results = []
            for item in response.objects:
                if item.properties.get("confidence_score", 0) >= min_confidence:
                    results.append({
                        "uuid": str(item.uuid),
                        "properties": item.properties,
                        "score": getattr(item.metadata, 'certainty', None)
                    })
            
            logger.info(f"✅ Found {len(results)} matching CVs")
            return results
            
        except Exception as e:
            logger.error(f"❌ Search failed: {e}")
            return []
    
    def get_cv_by_hash(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve CV by file hash.
        
        Args:
            file_hash: Unique file hash
            
        Returns:
            CV document or None
        """
        if not self.client:
            return None
        
        try:
            collection = self.client.collections.get(self.collection_name)
            
            response = collection.query.fetch_objects(
                filters=wvc.query.Filter.by_property("file_hash").equal(file_hash),
                limit=1
            )
            
            if response.objects:
                obj = response.objects[0]
                return {
                    "uuid": str(obj.uuid),
                    "properties": obj.properties
                }
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Failed to retrieve CV: {e}")
            return None
    
    def delete_cv(self, uuid: str) -> bool:
        """
        Delete CV by UUID.
        
        Args:
            uuid: Document UUID
            
        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            return False
        
        try:
            collection = self.client.collections.get(self.collection_name)
            collection.data.delete_by_id(uuid)
            logger.info(f"✅ Deleted CV: {uuid}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to delete CV: {e}")
            return False
    
    def is_available(self) -> bool:
        """Check if Weaviate is available"""
        return self.client is not None and self.client.is_ready()
    
    def close(self):
        """Close Weaviate connection"""
        if self.client:
            self.client.close()
            logger.info("✅ Closed Weaviate connection")
