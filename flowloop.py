#!/usr/bin/env python3
"""
FlowLoop — Background music & ambient soundscape hub for deep focus and work.
Download audio from YouTube, auto-tag by mood & energy level, catalog in SQLite,
and play in infinite seamless loop with random offset starting points.
"""

import argparse
import datetime
import json
import os
import random
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

__version__ = "0.1.0"
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "catalog.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                artist TEXT,
                filename TEXT UNIQUE NOT NULL,
                filepath TEXT NOT NULL,
                duration_seconds INTEGER DEFAULT 0,
                duration_formatted TEXT,
                youtube_id TEXT,
                youtube_url TEXT,
                moods TEXT,          -- comma-separated: focus, deep-work, ambient, meditation, etc.
                energy_level TEXT,   -- low, medium, high
                description TEXT,
                play_count INTEGER DEFAULT 0,
                last_played_at TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def format_duration(seconds: int) -> str:
    if not seconds:
        return "00:00"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def infer_moods_and_energy(title: str, description: str, tags: list) -> tuple[list[str], str]:
    text = f"{title} {description} {' '.join(tags)}".lower()

    detected_moods = set()
    
    mood_keywords = {
        "focus": ["focus", "study", "work", "concentration", "deep work", "programming", "coding"],
        "deep-work": ["deep work", "deep focus", "coding", "flow state", "deep ambient"],
        "meditation": ["meditation", "meditate", "mindfulness", "zen", "spiritual"],
        "ambient": ["ambient", "soundscape", "drone", "atmospheric", "background"],
        "relax": ["relax", "relaxing", "calm", "chill", "peaceful", "slow down", "sleep"],
        "nature": ["rain", "wind", "forest", "dunes", "ocean", "river", "waves", "desert"],
        "ethnic-oriental": ["arabic", "middle eastern", "oriental", "ethnic", "desert winds", "oud"],
        "lo-fi": ["lofi", "lo-fi", "chillhop", "beats"],
        "cyberpunk-synth": ["synthwave", "cyberpunk", "electronic", "scifi", "sci-fi"],
        "classical-piano": ["piano", "classical", "acoustic", "strings"]
    }

    for mood, kws in mood_keywords.items():
        for kw in kws:
            if kw in text:
                detected_moods.add(mood)
                break

    energy_level = "low"
    if any(k in text for k in ["upbeat", "energetic", "heavy", "intense", "fast", "action", "workout"]):
        energy_level = "high"
    elif any(k in text for k in ["rhythm", "groove", "beats", "moderate", "chillhop", "synthwave"]):
        energy_level = "medium"
    elif any(k in text for k in ["deep ambient", "calm", "relax", "sleep", "slow", "meditation", "drone"]):
        energy_level = "low"

    if not detected_moods:
        detected_moods.add("focus")
        detected_moods.add("ambient")

    return sorted(list(detected_moods)), energy_level


def fetch_youtube_info(url: str) -> dict:
    cmd = ["yt-dlp", "--dump-json", "--no-playlist", url]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


def download_track(url: str, custom_title: str = None, custom_moods: str = None, custom_energy: str = None):
    init_db()
    print(f"[*] Analyzing YouTube metadata: {url} ...")
    info = fetch_youtube_info(url)
    
    title = custom_title or info.get("title", "Unknown Title")
    uploader = info.get("uploader") or info.get("channel") or "Unknown Artist"
    duration = int(info.get("duration") or 0)
    yt_id = info.get("id")
    description = (info.get("description") or "")[:500]
    yt_tags = info.get("tags") or []

    if custom_moods:
        moods_list = [m.strip().lower() for m in custom_moods.split(",") if m.strip()]
    else:
        moods_list, auto_energy = infer_moods_and_energy(title, description, yt_tags)
        if not custom_energy:
            custom_energy = auto_energy

    energy_level = custom_energy or "low"
    moods_str = ", ".join(moods_list)

    safe_title = sanitize_filename(title)
    mp3_filename = f"{safe_title}.mp3"
    mp3_path = BASE_DIR / mp3_filename

    print(f"[+] Title: {title}")
    print(f"[+] Artist/Channel: {uploader}")
    print(f"[+] Duration: {format_duration(duration)}")
    print(f"[+] Mood / Tags: {moods_str}")
    print(f"[+] Energy Level: {energy_level}")
    print(f"[*] Downloading audio stream & converting to high quality MP3...")

    cmd = [
        "yt-dlp",
        "-x",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "--embed-metadata",
        "-o", str(BASE_DIR / f"{safe_title}.%(ext)s"),
        url
    ]
    subprocess.run(cmd, check=True)

    if not mp3_path.exists():
        candidates = list(BASE_DIR.glob(f"*{yt_id}*.mp3")) or list(BASE_DIR.glob(f"{safe_title}*.mp3"))
        if candidates:
            mp3_path = candidates[0]
            mp3_filename = mp3_path.name
        else:
            raise FileNotFoundError(f"Could not find generated MP3 file: {mp3_filename}")

    now = datetime.datetime.now().isoformat()
    with get_db() as conn:
        conn.execute("""
            INSERT INTO tracks (
                title, artist, filename, filepath, duration_seconds,
                duration_formatted, youtube_id, youtube_url, moods,
                energy_level, description, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(filename) DO UPDATE SET
                title=excluded.title,
                artist=excluded.artist,
                filepath=excluded.filepath,
                duration_seconds=excluded.duration_seconds,
                duration_formatted=excluded.duration_formatted,
                youtube_id=excluded.youtube_id,
                youtube_url=excluded.youtube_url,
                moods=excluded.moods,
                energy_level=excluded.energy_level,
                description=excluded.description
        """, (
            title,
            uploader,
            mp3_filename,
            str(mp3_path),
            duration,
            format_duration(duration),
            yt_id,
            url,
            moods_str,
            energy_level,
            description,
            now
        ))
        conn.commit()

    print(f"\n[✓] Track saved & cataloged into SQLite database!")
    print(f"    File: {mp3_path}")


def list_tracks(mood_filter: str = None, energy_filter: str = None):
    init_db()
    with get_db() as conn:
        query = "SELECT * FROM tracks WHERE 1=1"
        params = []
        if mood_filter:
            query += " AND (moods LIKE ? OR title LIKE ?)"
            params.extend([f"%{mood_filter}%", f"%{mood_filter}%"])
        if energy_filter:
            query += " AND energy_level = ?"
            params.append(energy_filter.lower())
        
        query += " ORDER BY id ASC"
        rows = conn.execute(query, params).fetchall()

    if not rows:
        print("No tracks found matching the specified criteria.")
        return

    print("\n" + "=" * 95)
    print(f"{'ID':<4} | {'Title':<38} | {'Duration':<8} | {'Energy':<8} | {'Mood / Tags'}")
    print("=" * 95)
    for r in rows:
        title = (r["title"][:35] + "...") if len(r["title"]) > 38 else r["title"]
        print(f"{r['id']:<4} | {title:<38} | {r['duration_formatted']:<8} | {r['energy_level']:<8} | {r['moods']}")
    print("=" * 95 + f"\nTotal: {len(rows)} tracks\n")


def play_audio_file(filepath: Path, start_seconds: int = 0) -> bool:
    """
    Plays the audio file using the best available CLI player (mpv, ffplay, or afplay).
    Returns True if ended naturally, False if interrupted by user.
    """
    has_mpv = shutil.which("mpv") is not None
    has_ffplay = shutil.which("ffplay") is not None

    if has_mpv:
        cmd = ["mpv", "--no-video", f"--start={start_seconds}", str(filepath)]
    elif has_ffplay:
        cmd = ["ffplay", "-nodisp", "-autoexit", "-ss", str(start_seconds), str(filepath)]
    else:
        cmd = ["afplay", str(filepath)]

    try:
        proc = subprocess.run(cmd)
        return proc.returncode == 0
    except KeyboardInterrupt:
        return False


def play_tracks(
    mood: str = None,
    energy: str = None,
    random_start: bool = True,
    start_seconds: int = None,
    track_id: int = None,
    loop_same_track: bool = True
):
    init_db()
    with get_db() as conn:
        if track_id:
            rows = conn.execute("SELECT * FROM tracks WHERE id = ?", (track_id,)).fetchall()
        else:
            query = "SELECT * FROM tracks WHERE 1=1"
            params = []
            if mood:
                query += " AND (moods LIKE ? OR title LIKE ?)"
                params.extend([f"%{mood}%", f"%{mood}%"])
            if energy:
                query += " AND energy_level = ?"
                params.append(energy.lower())
            rows = conn.execute(query, params).fetchall()

    if not rows:
        print(f"[!] No tracks found matching criteria (mood={mood}, energy={energy}).")
        return

    track_list = list(rows)

    print("\n" + "=" * 75)
    print(f"  🌊  FLOWLOOP — BACKGROUND MUSIC PLAYER")
    print("=" * 75)
    print(f"• Available tracks in library: {len(track_list)}")
    print(f"• Initial starting point: {'Random Offset' if random_start else 'Beginning (00:00)'}")
    print(f"• Loop mode: Infinite single-track loop (restarts from 00:00 on finish)")
    if mood:
        print(f"• Mood filter: {mood}")
    if energy:
        print(f"• Energy filter: {energy}")
    print("=" * 75)
    print("Controls (mpv): [Space] Pause/Play  |  [← / →] Seek ±5s  |  [q] / [Ctrl+C] Skip/Quit")
    print("=" * 75 + "\n")

    while True:
        track = random.choice(track_list) if not track_id else track_list[0]

        filepath = BASE_DIR / track["filename"]
        if not filepath.exists():
            filepath = Path(track["filepath"])
        
        if not filepath.exists():
            print(f"[!] File not found on disk: {track['filename']}")
            if len(track_list) == 1:
                return
            continue

        duration = int(track["duration_seconds"] or 0)
        
        if start_seconds is not None:
            first_offset = max(0, min(start_seconds, duration - 10 if duration > 10 else 0))
        elif random_start and duration > 60:
            max_start = max(0, duration - 45)
            first_offset = random.randint(0, max_start)
        else:
            first_offset = 0

        with get_db() as conn:
            conn.execute("""
                UPDATE tracks 
                SET play_count = play_count + 1, last_played_at = ?
                WHERE id = ?
            """, (datetime.datetime.now().isoformat(), track["id"]))
            conn.commit()

        current_offset = first_offset
        loop_count = 1

        while True:
            print("-" * 75)
            if loop_count == 1:
                print(f"▶ [{track['id']}] {track['title']}")
                print(f"  Artist: {track['artist']}")
                print(f"  Duration: {track['duration_formatted']}  |  Start at: {format_duration(current_offset)}  |  Mood: {track['moods']}")
            else:
                print(f"🔁 [{track['id']}] {track['title']} (Loop cycle #{loop_count} — Restarting from 00:00)")
            print("-" * 75)

            completed = play_audio_file(filepath, start_seconds=current_offset)
            
            if completed:
                if not loop_same_track:
                    break
                loop_count += 1
                current_offset = 0
                print(f"\n[🔁] Track finished. Seamlessly repeating from the start...")
                continue
            else:
                print("\n[!] Playback interrupted.")
                try:
                    choice = input("👉 Press [ENTER] / 'p' to switch track, or 'e' to exit: ").strip().lower()
                except (KeyboardInterrupt, EOFError):
                    print("\n[✓] FlowLoop session ended.")
                    return

                if choice == "e":
                    print("[✓] FlowLoop session ended.")
                    return
                print("\n")
                break


def export_playlist(output_file: str = "playlist.m3u", mood: str = None, energy: str = None):
    init_db()
    with get_db() as conn:
        query = "SELECT * FROM tracks WHERE 1=1"
        params = []
        if mood:
            query += " AND moods LIKE ?"
            params.append(f"%{mood}%")
        if energy:
            query += " AND energy_level = ?"
            params.append(energy.lower())
        rows = conn.execute(query, params).fetchall()

    if not rows:
        print("No tracks found matching criteria.")
        return

    out_path = BASE_DIR / output_file
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for r in rows:
            f.write(f"#EXTINF:{r['duration_seconds']},{r['artist']} - {r['title']}\n")
            f.write(f"{r['filename']}\n")

    print(f"[✓] Playlist exported to: {out_path} ({len(rows)} tracks)")


def update_tags(track_id: int, moods: str = None, energy: str = None, title: str = None):
    init_db()
    with get_db() as conn:
        track = conn.execute("SELECT * FROM tracks WHERE id = ?", (track_id,)).fetchone()
        if not track:
            print(f"[!] Track with ID {track_id} not found.")
            return

        new_moods = moods if moods is not None else track["moods"]
        new_energy = energy if energy is not None else track["energy_level"]
        new_title = title if title is not None else track["title"]

        conn.execute("""
            UPDATE tracks 
            SET moods = ?, energy_level = ?, title = ?
            WHERE id = ?
        """, (new_moods, new_energy, new_title, track_id))
        conn.commit()

    print(f"[✓] Track #{track_id} updated!")
    print(f"    Title: {new_title}")
    print(f"    Moods: {new_moods}")
    print(f"    Energy: {new_energy}")


def main():
    parser = argparse.ArgumentParser(
        prog="flowloop",
        description="FlowLoop — Continuous background music & soundscapes for deep focus & work"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: add
    p_add = subparsers.add_parser("add", help="Download & catalog audio from YouTube")
    p_add.add_argument("url", help="YouTube video URL")
    p_add.add_argument("--title", help="Custom track title")
    p_add.add_argument("--moods", help="Comma-separated moods/tags (e.g. focus, ambient, relax)")
    p_add.add_argument("--energy", choices=["low", "medium", "high"], help="Energy level")

    # Command: list
    p_list = subparsers.add_parser("list", help="List cataloged tracks")
    p_list.add_argument("--mood", help="Filter by mood/tag")
    p_list.add_argument("--energy", choices=["low", "medium", "high"], help="Filter by energy")

    # Command: play
    p_play = subparsers.add_parser("play", help="Play background music in continuous loop")
    p_play.add_argument("--id", type=int, help="Specific track ID to play")
    p_play.add_argument("--mood", help="Filter by mood (e.g. focus, meditation, ambient)")
    p_play.add_argument("--energy", choices=["low", "medium", "high"], help="Filter by energy level")
    p_play.add_argument("--from-start", action="store_true", help="Start from beginning (00:00) instead of random offset")
    p_play.add_argument("--start", type=int, help="Specific seconds to start playback from")
    p_play.add_argument("--once", action="store_true", help="Disable loop (play once without repeating)")

    # Command: tag
    p_tag = subparsers.add_parser("tag", help="Update tags or metadata for a track")
    p_tag.add_argument("id", type=int, help="Track ID")
    p_tag.add_argument("--moods", help="New comma-separated moods")
    p_tag.add_argument("--energy", choices=["low", "medium", "high"], help="Energy level")
    p_tag.add_argument("--title", help="New title")

    # Command: export
    p_export = subparsers.add_parser("export", help="Export playlist to .m3u format")
    p_export.add_argument("-o", "--output", default="playlist.m3u", help="Output .m3u filename")
    p_export.add_argument("--mood", help="Filter by mood")
    p_export.add_argument("--energy", choices=["low", "medium", "high"], help="Filter by energy")

    # Default action if no sub-command provided
    if len(sys.argv) == 1:
        play_tracks(random_start=True, loop_same_track=True)
        return

    args = parser.parse_args()

    if args.command == "add":
        download_track(args.url, args.title, args.moods, args.energy)
    elif args.command == "list":
        list_tracks(args.mood, args.energy)
    elif args.command == "play":
        play_tracks(
            mood=args.mood,
            energy=args.energy,
            random_start=not args.from_start,
            start_seconds=args.start,
            track_id=args.id,
            loop_same_track=not args.once
        )
    elif args.command == "tag":
        update_tags(args.id, moods=args.moods, energy=args.energy, title=args.title)
    elif args.command == "export":
        export_playlist(args.output, mood=args.mood, energy=args.energy)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
