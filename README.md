# ChronoReel 🎬

AI-powered alternative history video generator for TikTok/Reels.

## What It Does

Generates 15-second vertical videos showing "What if?" scenarios:
- **Stage 1:** Modern day familiar landmark
- **Stage 2:** Near-future changes
- **Stage 3:** Dramatic transformation

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your API keys

# Run full pipeline
python main.py --config configs/realistic.yaml
```

## Pipeline Phases

```bash
# Generate scenario only
python main.py --phase 1

# Generate images
python main.py --phase 2

# Generate videos + audio
python main.py --phase 3

# Assemble & upload
python main.py --phase 4
```

## Required API Keys

| Service | Environment Variable |
|---------|---------------------|
| Google AI (Gemini) | `GOOGLE_API_KEY` |
| Fal.ai | `FAL_KEY` |
| Google Sheets/Drive | `GOOGLE_APPLICATION_CREDENTIALS` |

## Project Structure

```
├── configs/           # Style configurations
├── prompts/           # AI prompt templates
├── output/            # Generated media
├── tests/             # Test scripts
├── main.py            # Entry point
├── screenwriter.py    # Scenario generation
├── art_department.py  # Image generation
├── cinematographer.py # Video animation
├── sound_engineer.py  # Audio generation
├── editor.py          # Video assembly
└── distributor.py     # Upload to cloud
```

## Documentation

- **[AGENT.md](AGENT.md)** - Full system specification
- **[prompts/README.md](prompts/README.md)** - Prompt documentation

## License

MIT
