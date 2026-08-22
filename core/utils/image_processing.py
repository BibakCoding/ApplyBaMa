import os
import secrets
from io import BytesIO
from PIL import Image
from django.core.files import File
from django.conf import settings


def get_unique_random_name(ext, length=20):
    """Generates a 20-char random hex string and logs it to a text file to prevent duplicates."""
    log_file = os.path.join(settings.MEDIA_ROOT, "uploaded_names.txt")
    os.makedirs(settings.MEDIA_ROOT, exist_ok=True)

    existing_names = set()
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            existing_names = set(line.strip() for line in f)

    while True:
        random_name = secrets.token_hex(10)  # Generates exactly 20 hex characters
        if random_name not in existing_names:
            with open(log_file, "a") as f:
                f.write(random_name + "\n")
            return f"{random_name}{ext}"


def university_logo_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    new_filename = get_unique_random_name(ext)
    return f"universities/{new_filename}"


def compress_image(image_field, max_size=(800, 800), quality=85):
    """Resizes and compresses the image in memory before saving."""
    try:
        img = Image.open(image_field)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail(max_size, Image.Resampling.LANCZOS)

        output = BytesIO()
        img.save(output, format="JPEG", quality=quality, optimize=True)
        output.seek(0)
        image_field.file = File(output, name=image_field.name)
    except Exception as e:
        print(f"Image compression skipped: {e}")
