import os
import subprocess
import json
import re
import platform
import streamlit as st
from tempfile import NamedTemporaryFile

# --- Helper Functions ---
def sanitize_filename(name):
    """Sanitize folder names to remove invalid characters."""
    invalid_chars = r'[<>:"/\\|?*]'
    return re.sub(invalid_chars, "_", name).strip().rstrip(". ")

def check_ffmpeg():
    """Check if ffmpeg is installed and accessible."""
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except Exception:
        return False

def download_video(video_url, output_dir, format_string, index, total, cookies_path=None):
    """Download a single video using yt-dlp."""
    try:
        command = [
            "yt-dlp",
            "--no-warnings",
            "--quiet",
            "--no-progress",
            "-f", format_string,
            "--merge-output-format", "mp4",
            "-o", os.path.join(output_dir, "%(playlist_index)s - %(title)s.%(ext)s"),
        ]
        if cookies_path:
            command += ["--cookies", cookies_path]
        command.append(video_url)

        status_placeholder = st.empty()
        status_placeholder.write(f"⬇ Downloading video {index}/{total}...")

        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode == 0:
            status_placeholder.success(f"✅ Video {index} downloaded successfully!")
        else:
            status_placeholder.error(f"❌ Failed to download video {index}")
        return result.returncode == 0
    except Exception as e:
        st.error(f"Error downloading video {index}: {str(e)}")
        return False

# --- Main App ---
def main():
    st.title("🎬 YouTube Playlist Downloader")

    # Sidebar instructions
    st.sidebar.header("🔐 Private Playlist? Upload cookies.txt")
    st.sidebar.markdown("""
To download private, unlisted, or age-restricted playlists:

1. Install [Cookie-Editor](https://cookie-editor.cgagnier.ca/) on your browser.
2. Visit YouTube and **log in**.
3. Click the Cookie-Editor extension icon.
4. Click **Export** → **Download as `cookies.txt`**.
5. Upload the file below:
""")

    cookies_file = st.sidebar.file_uploader("Upload your cookies.txt", type="txt")

    # Check ffmpeg
    if not check_ffmpeg():
        st.error("❌ ffmpeg not found. Please install ffmpeg and ensure it's in your PATH.")
        st.stop()

    # Set download path
    if "com.termux" in os.getenv("PREFIX", "") or "Android" in platform.platform():
        base_path = "/data/data/com.termux/files/home/storage/downloads/"
    elif platform.system() == "Windows":
        import getpass
        uname = getpass.getuser()
        base_path = f"C:\\Users\\{uname}\\Downloads"
    else:
        base_path = "/opt/render/project/src/downloads"

    os.makedirs(base_path, exist_ok=True)
    st.info(f"💾 Downloads will be saved to: `{base_path}`")

    playlist_url = st.text_input("🔗 Enter YouTube Playlist URL:")
    quality = st.selectbox("🎞 Choose video quality:", ["High", "Medium (720p)", "Low (360p)"])

    if playlist_url:
        format_string = {
            "High": "bestvideo+bestaudio/best",
            "Medium (720p)": "bestvideo[height<=720]+bestaudio[ext=m4a]/best[height<=720]",
            "Low (360p)": "bestvideo[height<=360]+bestaudio[ext=m4a]/best[height<=360]"
        }[quality]

        # Save uploaded cookies to temp file
        temp_cookie_path = None
        if cookies_file:
            with NamedTemporaryFile(delete=False, mode="w", suffix=".txt") as temp_cookie:
                temp_cookie.write(cookies_file.read().decode())
                temp_cookie_path = temp_cookie.name

        with st.spinner("📂 Fetching playlist metadata..."):
            try:
                command_meta = ["yt-dlp", "--dump-single-json"]
                if temp_cookie_path:
                    command_meta += ["--cookies", temp_cookie_path]
                else:
                    # fallback to skip auth check
                    command_meta += ["--extractor-args", "youtubetab:skip=authcheck"]
                command_meta.append(playlist_url)

                result_meta = subprocess.run(command_meta, capture_output=True, text=True, check=True)
                playlist_meta = json.loads(result_meta.stdout)
                playlist_title = playlist_meta.get("title", "playlist")
                sanitized_title = sanitize_filename(playlist_title)
                output_dir = os.path.join(base_path, sanitized_title)
                os.makedirs(output_dir, exist_ok=True)

                result = subprocess.run(
                    ["yt-dlp", "--flat-playlist", "--dump-json"] +
                    (["--cookies", temp_cookie_path] if temp_cookie_path else ["--extractor-args", "youtubetab:skip=authcheck"]) +
                    [playlist_url],
                    capture_output=True,
                    text=True,
                    check=True
                )
                videos_json = result.stdout.strip().splitlines()
                videos = [json.loads(v) for v in videos_json]

                st.success(f"📁 Playlist: {playlist_title} ({len(videos)} videos)")
                st.subheader("🎬 Videos in Playlist:")

                video_container = st.container()
                all_button_container = st.container()

                with video_container:
                    for idx, video in enumerate(videos, start=1):
                        col1, col2 = st.columns([4, 1])
                        with col1:
                            st.write(f"{idx}. {video.get('title', 'Unknown title')}")
                        with col2:
                            if st.button(f"Download #{idx}", key=f"dl_{video['id']}"):
                                video_url = f"https://www.youtube.com/watch?v={video['id']}"
                                if download_video(video_url, output_dir, format_string, idx, len(videos), cookies_path=temp_cookie_path):
                                    st.session_state[f"downloaded_{video['id']}"] = True

                with all_button_container:
                    if st.button("🚀 Download All Videos", type="primary"):
                        progress_bar = st.progress(0)
                        success_count = 0

                        for idx, video in enumerate(videos, start=1):
                            video_url = f"https://www.youtube.com/watch?v={video['id']}"
                            if download_video(video_url, output_dir, format_string, idx, len(videos), cookies_path=temp_cookie_path):
                                success_count += 1
                            progress_bar.progress(idx / len(videos))

                        st.success(f"✅ Successfully downloaded {success_count}/{len(videos)} videos!")

            except subprocess.CalledProcessError as e:
                st.error(f"❌ Error fetching playlist info:\n\n{e.stderr}")
            except json.JSONDecodeError:
                st.error("❌ Failed to parse playlist information.")
            except Exception as e:
                st.error(f"❌ An unexpected error occurred: {str(e)}")
            finally:
                if temp_cookie_path and os.path.exists(temp_cookie_path):
                    os.remove(temp_cookie_path)

if __name__ == "__main__":
    main()
