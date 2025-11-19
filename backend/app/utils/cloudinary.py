"""
Cloudinary utility functions for image and PDF uploads
"""
import os
import cloudinary
import cloudinary.uploader
from typing import Optional, BinaryIO
import logging

logger = logging.getLogger(__name__)

# Configure Cloudinary from environment variables
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

# Check if Cloudinary is configured
CLOUDINARY_CONFIGURED = all([
    CLOUDINARY_CLOUD_NAME,
    CLOUDINARY_API_KEY,
    CLOUDINARY_API_SECRET
])

if CLOUDINARY_CONFIGURED:
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True  # Use HTTPS
    )
    logger.info("Cloudinary configured successfully")
else:
    logger.warning("Cloudinary not configured - will fall back to local storage")


def upload_image(file_content: bytes, filename: str, folder: str = "repairs") -> Optional[str]:
    """
    Upload an image file to Cloudinary.
    
    Args:
        file_content: Binary content of the image file
        filename: Original filename (used for resource_id)
        folder: Cloudinary folder to organize uploads (default: "repairs")
    
    Returns:
        Cloudinary URL if successful, None if Cloudinary not configured or upload fails
    """
    if not CLOUDINARY_CONFIGURED:
        logger.warning("Cloudinary not configured, skipping upload")
        return None
    
    try:
        # Generate unique resource_id from filename
        resource_id = f"{folder}/{filename}"
        
        # Upload to Cloudinary
        result = cloudinary.uploader.upload(
            file_content,
            resource_type="image",
            folder=folder,
            public_id=filename.split('.')[0],  # Remove extension for public_id
            overwrite=False,  # Don't overwrite existing files
            use_filename=True,
            unique_filename=True
        )
        
        # Return secure URL
        url = result.get("secure_url") or result.get("url")
        logger.info(f"Successfully uploaded image to Cloudinary: {url}")
        return url
        
    except Exception as e:
        logger.error(f"Failed to upload image to Cloudinary: {str(e)}")
        return None


def upload_pdf(file_content: bytes, filename: str, folder: str = "settlements") -> Optional[str]:
    """
    Upload a PDF file to Cloudinary.
    
    Args:
        file_content: Binary content of the PDF file
        filename: Original filename (used for resource_id)
        folder: Cloudinary folder to organize uploads (default: "settlements")
    
    Returns:
        Cloudinary URL if successful, None if Cloudinary not configured or upload fails
    """
    if not CLOUDINARY_CONFIGURED:
        logger.warning("Cloudinary not configured, skipping upload")
        return None
    
    try:
        # Generate unique resource_id from filename
        resource_id = f"{folder}/{filename}"
        
        # Upload to Cloudinary as raw file (PDF)
        result = cloudinary.uploader.upload(
            file_content,
            resource_type="raw",  # PDFs are stored as raw files
            folder=folder,
            public_id=filename.split('.')[0],  # Remove extension for public_id
            overwrite=False,  # Don't overwrite existing files
            use_filename=True,
            unique_filename=True
        )
        
        # Return secure URL
        url = result.get("secure_url") or result.get("url")
        logger.info(f"Successfully uploaded PDF to Cloudinary: {url}")
        return url
        
    except Exception as e:
        logger.error(f"Failed to upload PDF to Cloudinary: {str(e)}")
        return None


def is_cloudinary_url(url: str) -> bool:
    """
    Check if a URL is a Cloudinary URL.
    
    Args:
        url: URL to check
    
    Returns:
        True if URL is a Cloudinary URL, False otherwise
    """
    if not url:
        return False
    return url.startswith("http://") or url.startswith("https://")


def get_cloudinary_url(image_path: str) -> str:
    """
    Get the full Cloudinary URL from an image path.
    If the path is already a Cloudinary URL, return it as-is.
    If it's a local path, return it as-is (for backward compatibility).
    
    Args:
        image_path: Image path (can be Cloudinary URL or local path)
    
    Returns:
        Full URL or local path
    """
    if is_cloudinary_url(image_path):
        return image_path
    # Return local path as-is for backward compatibility
    return image_path

