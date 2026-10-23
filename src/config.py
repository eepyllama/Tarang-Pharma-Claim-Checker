"""
Configuration and Environment Settings for Tarang Expense Automation
--------------------------------------------------------------------
Safely loads environment variables, manages project paths,
and provides polite fallback handling when API keys are absent.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any

# Load .env if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class Settings:
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = PROJECT_ROOT / "data"
    RAW_DATA_DIR: Path = DATA_DIR / "raw"
    IMAGES_DIR: Path = DATA_DIR / "images"
    CACHE_DIR: Path = PROJECT_ROOT / ".ocr_cache"
    DOCS_DIR: Path = PROJECT_ROOT / "docs"

    # API Keys
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
    GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY")

    # Policy Thresholds (Tarang Policy v3.2)
    AUTO_APPROVE_MAX_AMOUNT: float = 2000.0
    AMOUNT_TOLERANCE_RUPEES: float = 10.0
    FOOD_MAX_AMOUNT: float = 2500.0
    LODGING_M1_M2_LIMIT: float = 3000.0
    LODGING_M3_LIMIT: float = 4500.0

    @classmethod
    def resolve_image_path(cls, filename: str) -> Optional[Path]:
        """Resolves an image file path across data/images and legacy images/."""
        if not filename:
            return None
            
        clean_name = str(filename).replace("images/", "").strip("/")
        
        # Search directories
        search_dirs = [cls.IMAGES_DIR, cls.PROJECT_ROOT / "images"]
        for d in search_dirs:
            if not d.exists():
                continue
            cand = d / clean_name
            if cand.exists():
                return cand
            # Partial match (handling UUID prefix)
            for p in d.glob(f"*{clean_name}"):
                return p
        return None

    @classmethod
    def resolve_raw_file(cls, filename: str) -> Path:
        """Finds raw data files in data/raw or project root."""
        # 1. Try data/raw
        p1 = cls.RAW_DATA_DIR / filename
        if p1.exists():
            return p1
        # 2. Try project root
        p2 = cls.PROJECT_ROOT / filename
        if p2.exists():
            return p2
        # 3. Partial match in raw
        for p in cls.RAW_DATA_DIR.glob(f"*{filename}*"):
            return p
        for p in cls.PROJECT_ROOT.glob(f"*{filename}*"):
            return p
        return p1

    @classmethod
    def check_paid_api_availability(cls, provider: str = "openai") -> Dict[str, Any]:
        """
        Politely checks whether an external paid API key is present.
        Returns availability status and polite guidance message if absent.
        """
        provider = provider.lower()
        key = None
        if provider == "openai":
            key = cls.OPENAI_API_KEY
        elif provider == "gemini":
            key = cls.GEMINI_API_KEY
        elif provider == "groq":
            key = cls.GROQ_API_KEY

        if key and len(key.strip()) > 5:
            return {
                "available": True,
                "provider": provider,
                "message": f"Active {provider.capitalize()} API key detected."
            }
        else:
            return {
                "available": False,
                "provider": provider,
                "message": (
                    f"Notice: No {provider.capitalize()} API key was found in your environment or .env file. "
                    "The system will automatically utilize the built-in local RapidOCR engine at zero cost. "
                    f"To enable {provider.capitalize()} vision extraction, add {provider.upper()}_API_KEY='your_key' to a .env file."
                )
            }


settings = Settings()

def get_project_paths():
    return {
        "root": settings.PROJECT_ROOT,
        "data": settings.DATA_DIR,
        "images": settings.IMAGES_DIR,
        "raw": settings.RAW_DATA_DIR
    }
