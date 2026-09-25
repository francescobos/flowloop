# 🌊 FlowLoop

> **Continuous background music & ambient soundscapes for deep focus, flow state, and productivity.**

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Database: SQLite](https://img.shields.io/badge/Database-SQLite-003B57.svg?style=flat&logo=sqlite&logoColor=white)](https://sqlite.org/)

**FlowLoop** is a lightweight CLI tool designed for developers, writers, and deep workers who use long YouTube ambient audio / soundscapes (1–4+ hours) as focus soundtrack.

It automatically downloads audio, extracts high-quality MP3s with embedded metadata, auto-tags tracks based on mood and energy, catalogs them into a local SQLite database, and plays them in an **infinite seamless loop starting from a random point**.

---

## ✨ Key Features

- 🎯 **Flow State by Default**: Just run `flowloop` (or `python3 flowloop.py`). It randomly picks a track, starts at a **random offset point**, and loops that exact soundscape infinitely without breaks.
- ⚡ **Auto-Categorization & Tagging**: Automatically parses YouTube metadata to tag moods (*deep-work, focus, ambient, nature, ethnic-oriental, lo-fi, etc.*) and energy level (*low, medium, high*).
- 🗄️ **Local SQLite Catalog (`catalog.db`)**: Clean and portable storage tracking durations, playback count, dates, and mood tags.
- 🎵 **Seamless Playback Engine**: Integrated with `mpv` (or `ffplay` / `afplay`) for instant seeking, pause/resume, and terminal shortcuts.
- 📋 **Playlist Export**: Export filtered subsets directly into standard `.m3u` playlists.

---

## 🚀 Quick Start

### 1. Requirements

- **Python 3.9+**
- **FFmpeg**: `brew install ffmpeg`
- **mpv** *(recommended for interactive controls & instant seek)*: `brew install mpv`

### 2. Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/fboschetti/flowloop.git
cd flowloop
pip install -e .
```

---

## 🎧 Usage

### Start listening (Zero Config)

```bash
flowloop
# or
python3 flowloop.py
```
> Picks a random soundscape, begins from a random timestamp, and plays in an infinite continuous loop until interrupted.

### Add new audio from YouTube

```bash
# Auto-detect tags, energy level, and embed metadata:
flowloop add "https://www.youtube.com/watch?v=YOUR_VIDEO_ID"

# Or specify custom moods and energy:
flowloop add "https://www.youtube.com/watch?v=YOUR_VIDEO_ID" --moods "focus, ambient" --energy low
```

### Browse your catalog

```bash
# List all tracks:
flowloop list

# Filter by mood or energy:
flowloop list --mood focus
flowloop list --energy low
```

### Playback with filters & options

```bash
# Play a track matching specific mood:
flowloop play --mood deep-work
flowloop play --mood relax

# Start from the exact beginning (00:00) instead of random offset:
flowloop play --from-start

# Play a specific track by catalog ID:
flowloop play --id 1

# Play once without infinite loop:
flowloop play --once
```

### Export playlists

```bash
flowloop export -o deep_focus.m3u --mood focus
```

---

## ⌨️ Interactive Controls (via `mpv`)

While listening in the terminal:
- **`Space`**: Pause / Resume
- **`←` / `→`**: Seek ±5 seconds
- **`9` / `0`**: Decrease / Increase volume
- **`q`** or **`Ctrl + C`**: Open prompt to skip to next track or exit

---

## 📄 License

Released under the [MIT License](LICENSE).
