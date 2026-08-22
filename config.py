import os
from pathlib import Path

# Project root path
PROJECT_ROOT = Path(__file__).parent.resolve()

# Dataset root directory
DATASET_ROOT = os.getenv("DATASET_ROOT", r"C:\Users\ADMIN\Downloads\UCUMccND2H_CVS0dMZKCPCXA")

# Data & Output paths
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PREPROCESSED_DIR = DATA_DIR / "preprocessed"
SEGMENTED_DIR = DATA_DIR / "segmented"
LANGUAGE_DIR = DATA_DIR / "language"
NORMALIZED_DIR = DATA_DIR / "normalized"
ANALYSIS_RAW_DIR = DATA_DIR / "analysis_raw"
ANALYSIS_DIR = DATA_DIR / "analysis"
ANALYSIS_CHUNKS_DIR = DATA_DIR / "analysis_chunks"

OUTPUT_INDEX_FILE = DATA_DIR / "dataset_index.json"

# Phase 8 Adherence Batching Configuration
ADHERENCE_BATCH_SIZE = int(os.getenv("ADHERENCE_BATCH_SIZE", "5"))

# Phase 7 Opening Analysis Window
HOOK_TARGET_WINDOW_SECONDS = 90.0    # Target opening window in seconds
HOOK_MAX_WINDOW_SECONDS = 120.0      # Strict maximum cap for opening window in seconds

# Phase 4 Segmentation Configurable Hyperparameters
MIN_SEGMENT_DURATION = 15.0      # Minimum target segment duration in seconds
MAX_SEGMENT_DURATION = 55.0      # Maximum target segment duration in seconds (allows completing thoughts)
TARGET_SEGMENT_DURATION = 30.0   # Soft target duration preference
MAX_SENTENCES_PER_SEGMENT = 10    # Soft sentence limit per segment
MAX_WORDS_PER_SEGMENT = 180       # Soft word limit per segment
MAX_GAP_SECONDS = 3.0            # Subtitle timing gap threshold to trigger segment boundary

# Auto-load .env file if present
env_file = PROJECT_ROOT / ".env"
if env_file.exists():
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("'\""))

# LM Studio API Configuration
LM_STUDIO_BASE_URL = os.getenv("LM_STUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
LM_STUDIO_API_KEY = os.getenv("LM_STUDIO_API_KEY", "lm-studio")
LM_STUDIO_MODEL_ID = os.getenv("LM_STUDIO_MODEL_ID", "qwen3.5-9b-claude-4.6-opus-reasoning-distilled-v2")

