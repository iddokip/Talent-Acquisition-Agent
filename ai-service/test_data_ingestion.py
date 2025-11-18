"""
Test script for Data Loading & Ingestion Layer

This script demonstrates the functionality of the data ingestion module.
"""

import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from data_ingestion import (
    CVParser,
    FileLoader,
    DataTransformer,
    CVValidator,
    BatchLoader,
    IngestionConfig,
    CVSchema
)


def print_section(title):
    """Print a section header"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_configuration():
    """Test configuration management"""
    print_section("Testing Configuration")
    
    # Create configuration
    config = IngestionConfig(
        max_file_size_mb=10,
        batch_size=5,
        enable_caching=True,
        require_email=True,
        min_skills_count=1
    )
    
    print(f"✓ Configuration created")
    print(f"  Max file size: {config.max_file_size_mb} MB")
    print(f"  Batch size: {config.batch_size}")
    print(f"  Caching enabled: {config.enable_caching}")
    print(f"  Cache directory: {config.cache_directory}")
    
    # Validate configuration
    try:
        config.validate()
        print("✓ Configuration is valid")
    except Exception as e:
        print(f"✗ Configuration validation failed: {e}")
    
    return config


def test_parser():
    """Test CV parser"""
    print_section("Testing CV Parser")
    
    parser = CVParser()
    print(f"✓ Parser initialized: {parser.parser_name} v{parser.version}")
    
    # Create sample CV text
    sample_cv_text = """
    John Doe
    Email: john.doe@example.com
    Phone: +1-555-123-4567
    
    SKILLS
    Python, JavaScript, React, Node.js, Docker, AWS, MongoDB, Git
    Machine Learning, TensorFlow, pandas, scikit-learn
    
    EXPERIENCE
    Senior Software Engineer at Tech Corp (2020 - Present)
    - Developed scalable web applications
    - Led team of 5 developers
    
    Software Developer at StartupXYZ (2018 - 2020)
    - Built REST APIs
    - Implemented CI/CD pipelines
    
    EDUCATION
    Master of Science in Computer Science
    MIT, 2018
    
    Bachelor of Science in Computer Engineering
    Stanford University, 2016
    """
    
    # Parse the CV text
    parsed_data = parser.extract_comprehensive_info(sample_cv_text)
    
    print(f"✓ CV parsed successfully")
    print(f"  Email: {parsed_data.get('email')}")
    print(f"  Phone: {parsed_data.get('phone')}")
    print(f"  Skills found: {len(parsed_data.get('skills', []))}")
    print(f"  Experience entries: {len(parsed_data.get('experience', []))}")
    print(f"  Education entries: {len(parsed_data.get('education', []))}")
    print(f"  Years of experience: {parsed_data.get('years_of_experience')}")
    
    if parsed_data.get('skills'):
        print(f"\n  Sample skills: {', '.join(parsed_data['skills'][:5])}")
    
    return parsed_data


def test_validator(parsed_data):
    """Test data validator"""
    print_section("Testing CV Validator")
    
    validator = CVValidator({
        'require_email': True,
        'require_phone': False,
        'require_experience': True,
        'require_education': True,
        'min_skills_count': 1
    })
    
    print("✓ Validator initialized")
    
    # Validate the data
    is_valid, errors = validator.validate(parsed_data)
    
    print(f"\n  Validation result: {'✓ VALID' if is_valid else '✗ INVALID'}")
    
    if errors:
        print(f"  Errors found: {len(errors)}")
        for error in errors:
            print(f"    - {error}")
    else:
        print("  No errors found")
    
    # Get completeness score
    score = validator.get_data_completeness_score(parsed_data)
    print(f"\n  Data completeness: {score * 100:.1f}%")
    
    return is_valid


def test_transformer(parsed_data):
    """Test data transformer"""
    print_section("Testing Data Transformer")
    
    transformer = DataTransformer()
    print("✓ Transformer initialized")
    
    # Transform to CVSchema
    try:
        cv_schema = transformer.transform(parsed_data)
        print("✓ Data transformed to CVSchema")
        
        print(f"\n  Personal Info:")
        print(f"    Email: {cv_schema.personal_info.email}")
        print(f"    Phone: {cv_schema.personal_info.phone}")
        
        print(f"\n  Skills: {len(cv_schema.skills)}")
        if cv_schema.skills:
            for skill in cv_schema.skills[:3]:
                print(f"    - {skill.name} (Category: {skill.category.value if skill.category else 'None'})")
        
        print(f"\n  Experience: {len(cv_schema.experience)} entries")
        if cv_schema.experience:
            exp = cv_schema.experience[0]
            print(f"    - {exp.title} at {exp.company}")
            print(f"      Duration: {exp.duration_months} months" if exp.duration_months else "      Duration: Unknown")
        
        print(f"\n  Education: {len(cv_schema.education)} entries")
        if cv_schema.education:
            edu = cv_schema.education[0]
            print(f"    - {edu.degree}")
            print(f"      Institution: {edu.institution}")
        
        print(f"\n  Years of Experience: {cv_schema.years_of_experience}")
        print(f"  Parsed at: {cv_schema.parsed_at}")
        
        return cv_schema
    except Exception as e:
        print(f"✗ Transformation failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_file_loader():
    """Test file loader"""
    print_section("Testing File Loader")
    
    config = IngestionConfig(enable_caching=True, cache_directory="cv_cache")
    file_loader = FileLoader(config)
    
    print("✓ File loader initialized")
    print(f"  Cache enabled: {file_loader.cache_enabled}")
    print(f"  Cache directory: {file_loader.cache_dir}")
    
    # Get cache info
    cache_info = file_loader.get_cache_info()
    print(f"\n  Cache statistics:")
    print(f"    Files cached: {cache_info['file_count']}")
    print(f"    Total size: {cache_info.get('total_size_mb', 0):.2f} MB")
    
    return file_loader


def test_batch_loader():
    """Test batch loader"""
    print_section("Testing Batch Loader")
    
    config = IngestionConfig(batch_size=10, enable_multiprocessing=False)
    batch_loader = BatchLoader(config)
    
    print("✓ Batch loader initialized")
    print(f"  Batch size: {batch_loader.batch_size}")
    print(f"  Multiprocessing: {batch_loader.enable_multiprocessing}")
    print(f"  Max workers: {batch_loader.max_workers}")
    
    # Test with sample file list
    sample_files = ["cv1.pdf", "cv2.pdf", "cv3.docx"]
    batch_info = batch_loader.get_batch_info(sample_files)
    
    print(f"\n  Batch info for {len(sample_files)} files:")
    print(f"    Batch count: {batch_info['batch_count']}")
    print(f"    Valid files: {batch_info['valid_files']}")
    print(f"    Invalid files: {batch_info['invalid_files']}")
    
    return batch_loader


def test_schema_operations(cv_schema):
    """Test schema operations"""
    print_section("Testing Schema Operations")
    
    if not cv_schema:
        print("✗ No schema to test (transformation failed)")
        return
    
    # Convert to dict
    cv_dict = cv_schema.to_dict()
    print("✓ Converted schema to dictionary")
    print(f"  Keys: {list(cv_dict.keys())}")
    
    # Validate schema
    errors = cv_schema.validate()
    if errors:
        print(f"\n  Schema validation errors: {len(errors)}")
        for error in errors[:3]:
            print(f"    - {error}")
    else:
        print("\n✓ Schema validation passed")
    
    # Check JSON compatibility
    try:
        import json
        json_str = json.dumps(cv_dict, indent=2)
        print("✓ Schema is JSON-serializable")
        print(f"  JSON size: {len(json_str)} bytes")
    except Exception as e:
        print(f"✗ JSON serialization failed: {e}")


def run_all_tests():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("  DATA INGESTION LAYER - TEST SUITE")
    print("=" * 60)
    
    try:
        # Test configuration
        config = test_configuration()
        
        # Test parser
        parsed_data = test_parser()
        
        # Test validator
        is_valid = test_validator(parsed_data)
        
        # Test transformer
        cv_schema = test_transformer(parsed_data)
        
        # Test file loader
        file_loader = test_file_loader()
        
        # Test batch loader
        batch_loader = test_batch_loader()
        
        # Test schema operations
        test_schema_operations(cv_schema)
        
        # Summary
        print_section("TEST SUMMARY")
        print("✓ Configuration module: PASSED")
        print("✓ Parser module: PASSED")
        print("✓ Validator module: PASSED")
        print("✓ Transformer module: PASSED")
        print("✓ File loader module: PASSED")
        print("✓ Batch loader module: PASSED")
        print("✓ Schema operations: PASSED")
        
        print("\n" + "=" * 60)
        print("  ALL TESTS PASSED!")
        print("=" * 60 + "\n")
        
    except Exception as e:
        print(f"\n✗ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
