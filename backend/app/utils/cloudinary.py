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


def get_authenticated_url(cloudinary_url: str) -> Optional[str]:
    """
    Generate an authenticated/signed URL for a Cloudinary resource.
    Uses Cloudinary API credentials to sign the URL.
    
    Args:
        cloudinary_url: Cloudinary URL of the file
    
    Returns:
        Authenticated URL if successful, None on error
    """
    if not CLOUDINARY_CONFIGURED:
        logger.warning("Cloudinary not configured, cannot generate authenticated URL")
        return None
    
    try:
        import re
        import cloudinary.utils
        import hashlib
        import time
        
        # Extract public_id from Cloudinary URL
        # For raw files: https://res.cloudinary.com/{cloud}/raw/upload/v{version}/{folder}/{filename}.pdf
        # We need to extract everything after /raw/upload/v{version}/ or /raw/upload/
        # and keep the full path including folder and extension
        
        # Parse the URL to extract the path after /raw/upload/
        url_parts = cloudinary_url.split('/raw/upload/')
        if len(url_parts) == 2:
            resource_type = "raw"
            # Get everything after /raw/upload/
            after_upload = url_parts[1]
            # Remove version if present (v1234567890/)
            after_upload = re.sub(r'^v\d+/', '', after_upload)
            # Remove query parameters if any
            after_upload = after_upload.split('?')[0]
            # Remove fragment if any
            after_upload = after_upload.split('#')[0]
            # This is the public_id - includes folder path and filename with extension
            public_id = after_upload
        else:
            # Try image pattern
            url_parts = cloudinary_url.split('/image/upload/')
            if len(url_parts) == 2:
                resource_type = "image"
                after_upload = url_parts[1]
                after_upload = re.sub(r'^v\d+/', '', after_upload)
                after_upload = after_upload.split('?')[0]
                after_upload = after_upload.split('#')[0]
                public_id = after_upload
            else:
                logger.error(f"Could not extract public_id from URL: {cloudinary_url}")
                return None
        
        logger.info(f"Extracted public_id: {public_id} from URL: {cloudinary_url[:100]}...")
        
        # Generate signed URL using Cloudinary SDK
        # sign_url=True will add a signature parameter to the URL using API secret
        try:
            logger.info(f"Generating Cloudinary URL for public_id: {public_id}, resource_type: {resource_type}")
            authenticated_url = cloudinary.utils.cloudinary_url(
                public_id,
                resource_type=resource_type,
                secure=True,
                sign_url=True  # This will add signature to the URL using API secret
            )[0]
            
            logger.info(f"Generated authenticated URL: {authenticated_url[:100]}...")
            return authenticated_url
        except Exception as sign_error:
            logger.warning(f"Failed to sign URL, trying without signature: {str(sign_error)}")
            # Try without signing - might work if PDF delivery is enabled
            try:
                unsigned_url = cloudinary.utils.cloudinary_url(
                    public_id,
                    resource_type=resource_type,
                    secure=True
                )[0]
                return unsigned_url
            except:
                # Last resort: return original URL
                return cloudinary_url
            
    except Exception as e:
        logger.error(f"Failed to generate authenticated URL: {str(e)}", exc_info=True)
        # Fallback: return original URL
        return cloudinary_url


def delete_image(image_url: str) -> bool:
    """
    Delete an image from Cloudinary.
    
    Args:
        image_url: Cloudinary URL of the image to delete
    
    Returns:
        True if deletion was successful or Cloudinary not configured, False on error
    """
    if not CLOUDINARY_CONFIGURED:
        logger.warning("Cloudinary not configured, skipping deletion")
        return True  # Return True to allow local file deletion to proceed
    
    # Check if this is a Cloudinary URL (contains res.cloudinary.com)
    if "res.cloudinary.com" not in image_url:
        # Not a Cloudinary URL, might be local file
        return True
    
    try:
        # Extract public_id from Cloudinary URL
        # Cloudinary URLs format: https://res.cloudinary.com/{cloud_name}/{resource_type}/upload/{version}/{public_id}.{format}
        # or: https://res.cloudinary.com/{cloud_name}/image/upload/{folder}/{public_id}.{format}
        import re
        
        # Try to extract public_id from URL
        # Pattern: res.cloudinary.com/{cloud_name}/image/upload/{path}
        match = re.search(r'/image/upload/(?:v\d+/)?(.+?)(?:\.[^.]+)?$', image_url)
        if not match:
            # Try raw file pattern
            match = re.search(r'/raw/upload/(?:v\d+/)?(.+?)(?:\.[^.]+)?$', image_url)
        
        if match:
            public_id = match.group(1)
            # public_id might be like "repairs/filename" or "repairs/receipts/filename"
            # Keep the full path including folder for Cloudinary
            
            # Delete from Cloudinary
            result = cloudinary.uploader.destroy(public_id, resource_type="image", invalidate=True)
            
            if result.get("result") == "ok":
                logger.info(f"Successfully deleted image from Cloudinary: {public_id}")
                return True
            else:
                logger.warning(f"Cloudinary deletion returned: {result.get('result')} for {public_id}")
                return False
        else:
            logger.warning(f"Could not extract public_id from Cloudinary URL: {image_url}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to delete image from Cloudinary: {str(e)}")
        return False

