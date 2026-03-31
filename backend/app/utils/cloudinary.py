"""
Cloudinary utility functions for uploaded assets
"""
import os
import re
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
        # Use the full filename (including extension) as public_id to ensure uniqueness
        # Extract base name without extension for public_id, but keep it unique
        base_name = os.path.splitext(filename)[0]  # Remove extension but keep UUID/timestamp
        
        result = cloudinary.uploader.upload(
            file_content,
            resource_type="image",
            folder=folder,
            public_id=base_name,  # Use full base name (includes UUID/timestamp for uniqueness)
            overwrite=False,  # Don't overwrite existing files
            use_filename=False,  # Don't use original filename, use our unique public_id
            unique_filename=False,  # We're already generating unique names
            access_mode="public"  # Ensure files are publicly accessible (not authenticated/private)
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
        # For raw files, public_id should include the extension
        # Extract extension from filename
        file_extension = filename.split('.')[-1] if '.' in filename else ''
        public_id_base = filename.rsplit('.', 1)[0] if '.' in filename else filename
        
        result = cloudinary.uploader.upload(
            file_content,
            resource_type="raw",  # PDFs are stored as raw files
            folder=folder,
            public_id=f"{public_id_base}.{file_extension}" if file_extension else public_id_base,  # Keep extension for raw files
            overwrite=False,  # Don't overwrite existing files
            use_filename=True,
            unique_filename=True,
            access_mode="public"  # Ensure files are publicly accessible (not authenticated/private)
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


def delete_uploaded_file(file_url: str) -> bool:
    """
    Delete an uploaded asset from Cloudinary.
    
    Args:
        file_url: Cloudinary URL of the file to delete
    
    Returns:
        True if deletion was successful or Cloudinary not configured, False on error
    """
    if not CLOUDINARY_CONFIGURED:
        logger.warning("Cloudinary not configured, skipping deletion")
        return True  # Return True to allow local file deletion to proceed
    
    # Check if this is a Cloudinary URL (contains res.cloudinary.com)
    if "res.cloudinary.com" not in file_url:
        # Not a Cloudinary URL, might be local file
        return True
    
    try:
        resource_type = "image"
        match = re.search(r"/image/upload/(?:v\d+/)?(.+?)(?:\.[^.]+)?$", file_url)
        if not match:
            match = re.search(r"/raw/upload/(?:v\d+/)?(.+?)(?:\.[^.]+)?$", file_url)
            if match:
                resource_type = "raw"

        if not match:
            logger.warning(f"Could not extract public_id from Cloudinary URL: {file_url}")
            return False

        public_id = match.group(1)
        result = cloudinary.uploader.destroy(public_id, resource_type=resource_type, invalidate=True)

        if result.get("result") == "ok":
            logger.info(f"Successfully deleted file from Cloudinary: {public_id}")
            return True

        logger.warning(f"Cloudinary deletion returned: {result.get('result')} for {public_id}")
        return False
            
    except Exception as e:
        logger.error(f"Failed to delete file from Cloudinary: {str(e)}")
        return False


def delete_image(image_url: str) -> bool:
    """Backward-compatible wrapper for image deletion."""
    return delete_uploaded_file(image_url)
