"""
Data Loading & Ingestion Layer Module

This module provides comprehensive data ingestion capabilities for CV/Resume processing,
including parsing, validation, transformation, and loading.
"""

from .parsers.cv_parser import CVParser
from .parsers.base_parser import BaseParser

# Keep AdvancedCVParser as alias for backward compatibility
AdvancedCVParser = CVParser
from .loaders.file_loader import FileLoader
from .loaders.batch_loader import BatchLoader
from .models.cv_schema import CVSchema, PersonalInfo, Experience, Education, Skill
from .validators.cv_validator import CVValidator
from .transformers.data_transformer import DataTransformer
from .config.ingestion_config import IngestionConfig

__version__ = "1.0.0"
__all__ = [
    "CVParser",
    "AdvancedCVParser",
    "BaseParser",
    "FileLoader",
    "BatchLoader",
    "CVSchema",
    "PersonalInfo",
    "Experience",
    "Education",
    "Skill",
    "CVValidator",
    "DataTransformer",
    "IngestionConfig",
]
