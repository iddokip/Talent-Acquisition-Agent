"""CV Parser modules"""

from .base_parser import BaseParser
from .cv_parser import CVParser

# Keep AdvancedCVParser as alias for backward compatibility
AdvancedCVParser = CVParser

__all__ = ["BaseParser", "CVParser", "AdvancedCVParser"]
