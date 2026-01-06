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
│  - Premise      │     │  - Store new    │     │  Columns:       │
│  - Location     │     │    scenario     │     │  - premise      │
│  - 3 Stages     │     │                 │     │  - location     │
└─────────────────┘     └─────────────────┘     │  - stages (JSON)│
                                                 │  - status       │
                                                 └────────┬────────┘
                                                          │
                        ┌─────────────────────────────────▼─────────────────────────────────┐
                        │                         PRODUCTION PIPELINE                         │
                        │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────┐│
                        │  │ Art Dept     │─▶│ Vision Gate  │─▶│Cinematograph │─▶│ Editor  ││
                        │  │ (Flux imgs)  │  │ (Gemini)     │  │(Luma video)  │  │(MoviePy)││
                        │  └──────────────┘  └──────────────┘  └──────────────┘  └────┬────┘│
                        └─────────────────────────────────────────────────────────────┼─────┘
                                                                                      │
                        ┌─────────────────────────────────────────────────────────────▼─────┐
                        │  DISTRIBUTOR: Upload to Drive, Update Sheets status = "COMPLETED" │
                        └───────────────────────────────────────────────────────────────────┘
```

---

## 3. Config Structure (Style/Tone ONLY)

Configs control **how** videos look, not **what** they're about.

```yaml
# configs/realistic.yaml
channel_name: "ChronoReel"
google_sheet_id: "SHEET_ID_HERE"
drive_folder_id: "DRIVE_FOLDER_ID"

# Visual Style
style:
  name: "Photorealistic"
  image_suffix: "photorealistic, 4k, vertical 9:16, cinematic lighting"
  video_prompt: "Slow cinematic zoom, atmospheric motion, wind blowing, high detail"

# Audio Style  
audio_mood: "cinematic, atmospheric, dramatic"

# Generation Settings
image_retries: 3
```

**Future styles:** `vintage.yaml`, `anime.yaml`, `dystopian.yaml`, etc.

---

## 4. Google Sheets Schema

| Column | Type | Description |
|--------|------|-------------|
| `id` | string | Unique ID (timestamp-based) |
| `premise` | string | "What if time machines were invented in 2000?" |
| `location_name` | string | "Times Square, New York" |
| `location_prompt` | string | Full visual prompt for the location |
| `stage_1_year` | string | "1990" |
| `stage_1_label` | string | "New York, 1990" |
| `stage_1_description` | string | Scene description for image prompt |
| `stage_1_mood` | string | Audio/mood keywords |
| `stage_2_*` | ... | Same structure |
| `stage_3_*` | ... | Same structure |
| `status` | enum | `PENDING` → `IMAGES_DONE` → `VIDEO_DONE` → `COMPLETED` |
| `created_at` | datetime | When scenario was generated |
| `video_url` | string | Google Drive link (after completion) |

---

## 5. Module Breakdown

### Module A: `manager.py` (Config Loader)
- Parse CLI `--config` and `--style` arguments
- Load style/tone YAML file
- Expose `settings` object to all modules

### Module B: `screenwriter.py` (The Creative)
- **Input:** Today's date, style config
- **Process:** Gemini Pro generates a unique "What if...?" scenario
- **Output:** Complete scenario object (premise, location, 3 stages)

### Module C: `archivist.py` (Sheets Manager)
- **Check:** Query Sheets for duplicate premises
- **Write:** Store new scenarios with status = "PENDING"
- **Read:** Fetch pending scenarios for production pipeline

### Module D: `art_department.py` (Image Generation)
- **Input:** Read scenario from Sheets
- **Process:** Generate 3 keyframes with Flux (applying style suffix)
- **Vision Gate:** Gemini verifies consistency (max 3 retries)
- **Output:** Update Sheets status = "IMAGES_DONE"

### Module E: `cinematographer.py` (Video Animation)
- Image-to-Video using Fal.ai (Luma, Kling, Mochi, or Hunyuan)
- Apply video_prompt from style config
- Easy to switch models for cost/quality comparison

### Module F: `sound_engineer.py` (Audio)
- Fal.ai CassetteAI SFX based on stage moods
- Up to 30 seconds, fast processing

### Module G: `editor.py` (Assembly)
- MoviePy: stitch clips + audio + crossfades + text overlays

### Module H: `distributor.py` (Delivery)
- Upload to Google Drive
- Update Sheets: status = "COMPLETED", video_url = link

---

## 6. Execution Instructions

1. **Phase 1 (Skeleton):** Set up style configs and `manager.py`. ✅
2. **Phase 2 (The Eye):** Implement `screenwriter.py` + `archivist.py` + `art_department.py`. Verify Vision Gate works.
3. **Phase 3 (The Motion):** Implement `cinematographer.py` (Luma API).
4. **Phase 4 (Assembly):** Implement `editor.py` + `distributor.py`.
5. **Logging:** Console prints estimated cost per run.

---

## 7. Tech Stack

| Component | Technology |
|-----------|------------|
| Orchestration | `google-generativeai` (Gemini Pro) |
| Database | `gspread` (Google Sheets) |
| Image Gen | Fal.ai (Nano Banana, Flux) |
| Video Gen | Fal.ai (Luma, Kling, Mochi, Hunyuan) |
| Audio | Fal.ai (CassetteAI SFX) |
| Assembly | MoviePy |

> **Note:** All generation tasks use Fal.ai's single API, making it easy to switch between models (e.g., try Kling instead of Luma for video).