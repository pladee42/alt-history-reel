# 🤖 Project Spec: "ChronoReel" (Scalable Alt-History Engine)

**Role:** You are the Lead AI Architect.
**Objective:** Build a Python-based content engine that autonomously generates "Alternative History" short-form videos (9:16).

## Core Philosophy

1. **AI-Driven Content:** The Screenwriter (Gemini) generates unique "What if...?" scenarios. Humans only configure the visual **style/tone**.
2. **Google Sheets as Database:** All scenarios are stored in Sheets for deduplication and as the source of truth for image generation.
3. **Cost Efficiency:** Use a "Verify-Then-Animate" workflow. Do not generate expensive AI video until static keyframes are verified by Gemini Vision.

---

## 1. The Product Vision

We are building an **autonomous artist** that creates 15-second vertical videos (9:16) showing a "time-travel journey."

**The Viewer Experience:**

| Time | Phase | Example |
|------|-------|---------|
| 0-5s | **The Hook** | Familiar landmark *today*. Realistic. Modern sounds. Text: "Paris, 2026" |
| 5-10s | **The Twist** | Same landmark, subtle changes. Audio shifts. Text: "Paris, 2035" |
| 10-15s | **The Climax** | Full transformation (ruined/enhanced/underwater). Intense audio. Text: "Paris, 2060" |

**Key Requirement:** Camera angle **must not move**. The location anchors while time flows around it.

---

## 2. System Flow (Architecture)

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  SCREENWRITER   │────▶│    ARCHIVIST    │────▶│  GOOGLE SHEETS  │
│  (Gemini Pro)   │     │  (Write + Check)│     │   (Database)    │
│  Generates:     │     │  - Dedup check  │     │                 │
│  - Title (**)   │     │  - Store new    │     │  Columns:       │
│  - Premise      │     │    scenario     │     │  - title        │
│  - Location     │     │                 │     │  - premise      │
│  - 3 Stages     │     │                 │     │  - location     │
└─────────────────┘     └─────────────────┘     │  - stages (JSON)│
                                                 │  - status       │
        ┌────────────────────────────────────────┴────────────────┐
        ▼                                                         │
┌─────────────────┐                                               │
│ PROMPT IMPROVER │ ◀── Refines raw descriptions into             │
│  (Gemini)       │     high-quality image & audio prompts        │
└───────┬─────────┘                                               │
        ▼                                                         │
┌───────────────────────────────────────────────────────────────┐ │
│                    PRODUCTION PIPELINE                         │ │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────┐│ │
│  │ Art Dept     │─▶│ Vision Gate  │─▶│Cinematograph │─▶│Edit ││ │
│  │ (Flux imgs)  │  │ (Gemini)     │  │(Fal.ai video)│  │     ││ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──┬──┘│ │
│                         Sound Engineer ─────────────────▶ │    │ │
│                         (ElevenLabs SFX via Fal.ai)       │    │ │
└───────────────────────────────────────────────────────────┼────┘ │
                                                            ▼      │
┌───────────────────────────────────────────────────────────────┐  │
│  DISTRIBUTOR: Upload to GCS, Update Sheets status = "DONE"   │◀─┘
│  Returns public URL: https://storage.googleapis.com/bucket/...│
└───────────────────────────────────────────────────────────────┘
```

---

## 3. Config Structure (Style/Tone ONLY)

Configs control **how** videos look, not **what** they're about.

```yaml
# configs/realistic.yaml
channel_name: "ChronoReel"
google_sheet_id: "SHEET_ID_HERE"

# Storage (Choose one)
gcs_bucket: "chronoreel-output"  # Recommended for GCP deployment
# drive_folder_id: "DRIVE_FOLDER_ID"  # Legacy (SA quota issues)

# Visual Style
style:
  name: "Photorealistic"
  image_suffix: "photorealistic, 4k, vertical 9:16, cinematic lighting, hyper-detailed"
  video_prompt: "Slow cinematic zoom, atmospheric motion, wind blowing, high detail"

# Audio Style  
audio_mood: "cinematic, atmospheric, dramatic, immersive"

# Generation Settings
image_retries: 3
```

**Future styles:** `vintage.yaml`, `anime.yaml`, `dystopian.yaml`, etc.

---

## 4. Google Sheets Schema

| Column | Type | Description |
|--------|------|-------------|
| `id` | string | Unique ID (timestamp-based) |
| `title` | string | Rich title with `**emphasis**` markers |
| `premise` | string | "What if time machines were invented in 2000?" |
| `location_name` | string | "Times Square, New York" |
| `location_prompt` | string | Full visual prompt for the location |
| `stage_X_year` | string | "1990" |
| `stage_X_label` | string | "New York, 1990" |
| `stage_X_description` | string | Scene description for image prompt |
| `stage_X_mood` | string | Audio/mood keywords |
| `stage_X_image_prompt` | string | Refined prompt from Prompt Improver |
| `stage_X_audio_prompt` | string | Refined audio prompt from Prompt Improver |
| `status` | enum | `PENDING` → `IMAGES_DONE` → `VIDEO_DONE` → `COMPLETED` |
| `created_at` | datetime | When scenario was generated |
| `video_url` | string | GCS/Drive link (after completion) |

---

## 5. Module Breakdown

### `manager.py` (Config Loader)
- Parse CLI `--config` and `--style` arguments
- Load style/tone YAML file
- Expose `settings` object to all modules

### `screenwriter.py` (The Creative)
- **Input:** Today's date, style config
- **Process:** Gemini Pro generates unique "What if?" scenarios
- **Output:** Scenario with `title` (using `**emphasis**` syntax), premise, location, 3 stages
- **Prompt:** `prompts/screenwriter.md`

### `prompt_improver.py` (Quality Enhancement) ✨ NEW
- **Input:** Raw scenario from Screenwriter
- **Process:** Two-step refinement:
  1. Generate `image_prompt` from description
  2. Generate `audio_prompt` from image_prompt (chained)
- **Prompts:** `prompts/improver_image_user.md`, `prompts/improver_audio_user.md`
- **Output:** Updates scenario with refined prompts

### `archivist.py` (Sheets Manager)
- **Check:** Query Sheets for duplicate premises
- **Write:** Store new scenarios with status = "PENDING"
- **Read:** Fetch pending scenarios for production pipeline
- **Update:** Methods for status, image_prompt, audio_prompt columns

### `art_department.py` (Image Generation)
- **Input:** Read scenario from Sheets
- **Process:** Generate 3 keyframes with Flux (applying style suffix)
- **Vision Gate:** Gemini verifies consistency (max 3 retries)
- **Prompt:** `prompts/vision_gate.md`
- **Output:** Update Sheets status = "IMAGES_DONE"

### `cinematographer.py` (Video Animation)
- Image-to-Video using Fal.ai (MiniMax Hailuo)
- Model configurable in `configs/model_config.yaml`
- Apply video_prompt from style config

### `sound_engineer.py` (Audio)
- Fal.ai ElevenLabs SFX based on refined `audio_prompt`
- Combines mood + description for richer prompts
- Configurable `prompt_influence` setting

### `editor.py` (Assembly)
- **MoviePy:** Stitch clips + audio + text overlays
- **Header:** Black background with rich text title (Cyan emphasis)
- **Ranking Overlay:** Progressive reveal of stages with labels
- **Layout:** Vertical 9:16 format optimized for Reels/TikTok

### `distributor.py` (Delivery)
- Upload to Google Cloud Storage (GCS)
- Returns public URL for mobile viewing
- Update Sheets: status = "COMPLETED", video_url = link

---

## 6. Prompts Directory

| File | Purpose |
|------|---------|
| `screenwriter.md` | System prompt for scenario generation |
| `prompt_improver.md` | System prompt for prompt refinement |
| `improver_image_user.md` | User prompt for image prompt generation |
| `improver_audio_user.md` | User prompt for audio prompt generation |
| `vision_gate.md` | System prompt for consistency verification |

---

## 7. Test Scripts

| File | Purpose |
|------|---------|
| `tests/test_editor.py` | Test editor with existing scenario from Sheets |
| `tests/test_distributor.py` | Test GCS/Drive upload without full pipeline |
| `tests/test_prompt_improver.py` | Test prompt refinement logic |
| `tests/test_sound_engineer_logic.py` | Test audio generation |

---

## 8. Execution Phases

1. **Phase 1 (Skeleton):** Style configs + `manager.py` ✅
2. **Phase 2 (The Eye):** `screenwriter.py` + `archivist.py` + `art_department.py` ✅
3. **Phase 3 (The Motion):** `cinematographer.py` + `sound_engineer.py` ✅
4. **Phase 4 (Assembly):** `editor.py` + `distributor.py` ✅
5. **Phase 4.5 (Quality):** `prompt_improver.py` + Rich Title + Layout ✅
6. **Phase 5 (GCS Upload):** Replace Drive with GCS 🔄 IN PROGRESS
7. **Phase 6 (Deployment):** Docker + Cloud Run + Scheduler
8. **Phase 7 (Polish):** Cost tracking + logging

---

## 9. Tech Stack

| Component | Technology |
|-----------|------------|
| Orchestration | `google-generativeai` (Gemini Pro) |
| Database | `gspread` (Google Sheets) |
| Image Gen | Fal.ai (Flux) |
| Video Gen | Fal.ai (MiniMax Hailuo) |
| Audio | Fal.ai (ElevenLabs SFX) |
| Assembly | MoviePy |
| Storage | Google Cloud Storage (GCS) |
| Deployment | Cloud Run + Cloud Scheduler |

> **Note:** All generation tasks use Fal.ai's single API, making it easy to switch between models.