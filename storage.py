"""
Cloud storage abstraction — Cloudinary for production, local disk for dev.
Set USE_CLOUDINARY=true in .env to enable cloud storage.
"""
import os
import tempfile

USE_CLOUDINARY = os.getenv("USE_CLOUDINARY", "false").lower() == "true"

if USE_CLOUDINARY:
    import cloudinary
    import cloudinary.uploader
    import cloudinary.api
    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET"),
        secure=True
    )


def save_file(file_obj, filename: str) -> str:
    """
    Save an uploaded file.
    Returns: local filepath (dev) or Cloudinary public_id (prod).
    """
    if USE_CLOUDINARY:
        result = cloudinary.uploader.upload(
            file_obj,
            public_id=f"lexara_uploads/{filename}",
            resource_type="raw",
            overwrite=True
        )
        return result["public_id"]
    else:
        upload_folder = os.getenv("UPLOAD_FOLDER", "uploads")
        os.makedirs(upload_folder, exist_ok=True)
        filepath = os.path.join(upload_folder, filename)
        file_obj.save(filepath)
        return filepath


def get_file_path(identifier: str) -> str:
    """
    Get a local path to the file for processing.
    For Cloudinary: downloads to a temp file and returns that path.
    For local: returns the path directly.
    Returns (local_path, is_temp) — caller must delete temp file after use.
    """
    if USE_CLOUDINARY:
        import requests
        url = cloudinary.utils.cloudinary_url(identifier, resource_type="raw")[0]
        ext = os.path.splitext(identifier)[1] or ".tmp"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        tmp.write(response.content)
        tmp.close()
        return tmp.name, True
    else:
        return identifier, False


def delete_file(identifier: str):
    """Delete a file from storage."""
    if USE_CLOUDINARY:
        try:
            cloudinary.uploader.destroy(identifier, resource_type="raw")
        except Exception as e:
            print(f"[Storage] Failed to delete {identifier}: {e}")
    else:
        if os.path.exists(identifier):
            os.remove(identifier)


def get_file_size(identifier: str) -> int:
    """Get file size in bytes."""
    if USE_CLOUDINARY:
        try:
            info = cloudinary.api.resource(identifier, resource_type="raw")
            return info.get("bytes", 0)
        except Exception:
            return 0
    else:
        return os.path.getsize(identifier) if os.path.exists(identifier) else 0
