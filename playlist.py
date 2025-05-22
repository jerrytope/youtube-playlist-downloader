import os
import subprocess
import json
import re
import platform
import streamlit as st

# Helper function to sanitize folder names
def sanitize_filename(name):
    invalid_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(invalid_chars, "_", name).strip().rstrip(". ")
    return sanitized

# Check if ffmpeg is installed
def check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except Exception:
        return False

# Main Streamlit app
def main():
    st.title("🎬 YouTube Playlist Downloader")
    # st.write("Created by Rajkishor Patra (Streamlit version) 🚀")

    # Check ffmpeg
    if not check_ffmpeg():
        st.error("❌ ffmpeg not found. Please install ffmpeg and ensure it's in your PATH.")
        st.stop()

    # Detect platform and set base download path
    if "com.termux" in os.getenv("PREFIX", "") or "Android" in platform.platform():
        base_path = "/data/data/com.termux/files/home/storage/downloads/"
    else:
        uname = os.getlogin()
        base_path = f"C:\\Users\\{uname}\\Downloads"

    st.info(f"💾 Downloads will be saved to: `{base_path}`")

    # Playlist URL input
    playlist_url = st.text_input("🔗 Enter YouTube Playlist URL:")

    # Quality selection
    quality = st.selectbox("🎞 Choose video quality:", ["High", "Medium (720p)", "Low (360p)"])

    if st.button("🚀 Start Download"):
        if not playlist_url:
            st.error("Please enter a valid playlist URL.")
            return

        # Set format string
        if quality == "High":
            format_string = "bestvideo+bestaudio/best"
        elif quality == "Medium (720p)":
            format_string = (
                "bestvideo[height<=720]+bestaudio[ext=m4a]/"
                "bestvideo[height<=720]+bestaudio/best[height<=720]"
            )
        else:
            format_string = (
                "bestvideo[height<=360]+bestaudio[ext=m4a]/"
                "bestvideo[height<=360]+bestaudio/best[height<=360]"
            )

        with st.spinner("📂 Fetching playlist metadata..."):
            try:
                result_meta = subprocess.run(
                    ["yt-dlp", "--dump-single-json", playlist_url],
                    capture_output=True,
                    text=True,
                    check=True
                )
                playlist_meta = json.loads(result_meta.stdout)
                playlist_title = playlist_meta.get("title", "playlist")
            except subprocess.CalledProcessError:
                st.error("❌ Failed to fetch playlist metadata.")
                return

        sanitized_title = sanitize_filename(playlist_title)
        output_dir = os.path.join(base_path, sanitized_title)
        os.makedirs(output_dir, exist_ok=True)

        st.success(f"📁 Download folder created: `{output_dir}`")

        with st.spinner("🔍 Fetching video entries..."):
            try:
                result = subprocess.run(
                    ["yt-dlp", "--flat-playlist", "--dump-json", playlist_url],
                    capture_output=True,
                    text=True,
                    check=True
                )
                videos_json = result.stdout.strip().splitlines()
                total_videos = len(videos_json)
            except subprocess.CalledProcessError:
                st.error("❌ Failed to fetch playlist info.")
                return

        st.info(f"🎬 Total videos found: {total_videos}")

        progress_bar = st.progress(0)

        # Download each video
        for idx, video_entry in enumerate(videos_json, start=1):
            video_id = json.loads(video_entry).get("id")
            video_url = f"https://www.youtube.com/watch?v={video_id}"

            st.write(f"⬇ Downloading video {idx}/{total_videos}...")

            command = [
                "yt-dlp",
                "--no-warnings",
                "--quiet",
                "--no-progress",
                "-f", format_string,
                "--merge-output-format", "mp4",
                "-o", os.path.join(output_dir, "%(playlist_index)s - %(title)s.%(ext)s"),
                video_url
            ]

            subprocess.run(command)

            progress_bar.progress(idx / total_videos)

        st.success("✅ All videos downloaded successfully!")

if __name__ == "__main__":
    main()
