# YouTube Transcript Adherence & Content Promise Analyzer

An end-to-end Python pipeline and web application for evaluating video transcript adherence against creator promises and opening hooks using local LLMs (Qwen / LM Studio).

## 🚀 Overview

The system analyzes YouTube video transcripts to evaluate whether creators deliver on their promises. It breaks down videos into semantic segments, identifies opening promises/hooks, classifies segment functions and point relevance using an LLM, and calculates quantitative adherence metrics based on the **Candidate B formula** (60% Point Coverage, 25% Clear Relevance, 15% Topic Discipline).

---

## 🏗️ Architecture & Pipeline Phases

1. **Phase 1: Dataset Discovery & Raw Parsing** (`run_phase1.py`): Scans raw subtitle files (.srt/.json) and builds the dataset index.
2. **Phase 2: Cleaning & Preprocessing** (`run_phase2.py`, `src/preprocessor.py`): Normalizes timestamps, removes filler noise, and structures text.
3. **Phase 3 & 4: Semantic Segmentation** (`run_phase4.py`, `src/segmenter.py`): Dynamically groups subtitle sentences into coherent 15-55s semantic segments.
4. **Phase 5: Language Metadata Enrichment** (`run_phase5.py`, `src/language_detector.py`): Detects script and dominant language per segment (Hindi Devanagari / English / Hinglish).
5. **Phase 6: Opening Window Extraction** (`run_phase6.py`): Isolates 90–120s opening windows for promise analysis.
6. **Phase 7: Hook & Promise Extraction** (`run_phase7.py`, `src/hook_analyzer.py`): Identifies hook type, explicit creator promises, and expected points ($P_1 \dots P_n$).
7. **Phase 8: Batched Adherence Analysis** (`run_phase8b.py`, `src/adherence_timeline_analyzer.py`):
   - High-performance batching (5 segments per Qwen call).
   - Strict segment ID matching and deterministic evidence validation.
   - Per-batch caching and resumability in `data/analysis_chunks/`.
8. **Phase 9: Adherence Metrics & Scoring** (`run_phase9a.py` - `run_phase9d.py`, `src/adherence_metrics.py`):
   - Point Coverage calculation.
   - Clear Relevance and Topic Discipline percentages.
   - Candidate B adherence scoring:
     $$\text{Score} = 0.60 \times \text{Point Coverage} + 0.25 \times \text{Clear Relevance} + 0.15 \times \text{Topic Discipline}$$
9. **Phase 10: Production Batch Pipeline** (`run_phase10.py`, `run_phase10b.py`, `src/phase10_pipeline.py`): End-to-end automated pipeline with no-promise video handling.
10. **Phase 11: Web Application & Single-Item Analyzer** (`api/server.py`, `frontend/index.html`, `src/user_analysis_pipeline.py`):
    - Full Flask REST API with background thread execution and state persistence.
    - Premium responsive glassmorphism UI for transcript upload and interactive analysis visualization.

---

## 🛠️ Getting Started

### Prerequisites
- Python 3.10+
- [LM Studio](https://lmstudio.ai/) running locally with Qwen 2.5/3.5 or compatible model (OpenAI-compatible endpoint on port 1234).

### Installation
```bash
git clone https://github.com/Bhavya26505/transcripts.git
cd transcripts
pip install flask watchdog python-dotenv
```

### Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Configure your LM Studio host and model:
```env
LM_STUDIO_BASE_URL=http://127.0.0.1:1234/v1
LM_STUDIO_MODEL_ID=qwen3.5-9b-claude-4.6-opus-reasoning-distilled-v2
ADHERENCE_BATCH_SIZE=5
```

### Running the Web Application
```bash
python api/server.py
```
Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

---

## 📊 Dataset & Benchmarks
- Baseline benchmark validated on `-RgdgqF9wd0`:
  - **Point Coverage**: 75.00%
  - **Candidate B Score**: 73.37
  - **Call Reduction**: 78.57% call reduction with batching.
