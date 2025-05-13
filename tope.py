import os
import subprocess
import json
import re
import platform
import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx

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

# Function to download a single video
def download_video(video_url, output_dir, format_string, index, total, cookies_path=None):
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

        # Create a status container for this download
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

# Main Streamlit app
def main():
    st.title("🎬 YouTube Playlist Downloader")

    # Check ffmpeg
    if not check_ffmpeg():
        st.error("❌ ffmpeg not found. Please install ffmpeg and ensure it's in your PATH.")
        st.stop()

    # Detect platform and set base download path
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

    # Explanation for cookies
    with st.expander("🔐 Need to download private/restricted videos? (Click here)"):
        st.markdown("""
        Some playlists may be **private, age-restricted, or unlisted** and require your YouTube account to access them.
        
        To download these videos, you need to upload your `cookies.txt` file from your browser session. Here's how:

        1. Install this Chrome/Firefox extension: [Get cookies.txt](https://chromewebstore.google.com/detail/get-cookiestxt/npecfdijgoblfcgagoijgmgejmcpnhof)
        2. Open the YouTube playlist in a new tab and ensure you're signed in.
        3. Click the extension icon and download your `cookies.txt`.
        4. Upload it below.

        ⚠️ **Important:** Your cookies are never stored. They are only used temporarily for this session and deleted afterward.
        """)

    uploaded_cookies = st.file_uploader("📄 Upload cookies.txt (optional, only for private/restricted playlists)", type=["txt"])
    cookies_path = None

    if uploaded_cookies:
        cookies_path = os.path.join(base_path, "cookies.txt")
        with open(cookies_path, "wb") as f:
            f.write(uploaded_cookies.getbuffer())
        st.success("✅ Cookies uploaded and will be used for downloading.")

    # Playlist URL input
    playlist_url = st.text_input("🔗 Enter YouTube Playlist URL:")

    # Quality selection
    quality = st.selectbox("🎞 Choose video quality:", ["High", "Medium (720p)", "Low (360p)"])

    if playlist_url:
        # Set format string based on quality selection
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
                metadata_command = ["yt-dlp", "--dump-single-json"]
                if cookies_path:
                    metadata_command += ["--cookies", cookies_path]
                metadata_command.append(playlist_url)

                result_meta = subprocess.run(
                    metadata_command, capture_output=True, text=True, check=True
                )
                playlist_meta = json.loads(result_meta.stdout)
                playlist_title = playlist_meta.get("title", "playlist")
                sanitized_title = sanitize_filename(playlist_title)
                output_dir = os.path.join(base_path, sanitized_title)
                os.makedirs(output_dir, exist_ok=True)

                flat_command = ["yt-dlp", "--flat-playlist", "--dump-json"]
                if cookies_path:
                    flat_command += ["--cookies", cookies_path]
                flat_command.append(playlist_url)

                result = subprocess.run(flat_command, capture_output=True, text=True, check=True)
                videos_json = result.stdout.strip().splitlines()
                videos = [json.loads(v) for v in videos_json]

                st.success(f"📁 Playlist: {playlist_title} ({len(videos)} videos)")

                # Display each video with a download button
                st.subheader("🎬 Videos in Playlist:")

                # Create a container for the download all button
                all_button_container = st.container()

                # Create a container for individual video buttons
                video_container = st.container()

                with video_container:
                    for idx, video in enumerate(videos, start=1):
                        col1, col2 = st.columns([4, 1])
                        with col1:
                            st.write(f"{idx}. {video.get('title', 'Unknown title')}")
                        with col2:
                            if st.button(f"Download #{idx}", key=f"dl_{video['id']}"):
                                video_url = f"https://www.youtube.com/watch?v={video['id']}"
                                if download_video(video_url, output_dir, format_string, idx, len(videos), cookies_path):
                                    st.session_state[f"downloaded_{video['id']}"] = True

                # Download all button
                with all_button_container:
                    if st.button("🚀 Download All Videos", type="primary"):
                        progress_bar = st.progress(0)
                        success_count = 0

                        for idx, video in enumerate(videos, start=1):
                            video_url = f"https://www.youtube.com/watch?v={video['id']}"
                            if download_video(video_url, output_dir, format_string, idx, len(videos), cookies_path):
                                success_count += 1
                            progress_bar.progress(idx / len(videos))

                        st.success(f"✅ Successfully downloaded {success_count}/{len(videos)} videos!")

            except subprocess.CalledProcessError as e:
                st.error(f"❌ Error fetching playlist info: {e.stderr}")
            except json.JSONDecodeError:
                st.error("❌ Failed to parse playlist information.")
            except Exception as e:
                st.error(f"❌ An unexpected error occurred: {str(e)}")

    # Clean up cookies file after session
    if cookies_path and os.path.exists(cookies_path):
        try:
            os.remove(cookies_path)
        except Exception:
            pass

if __name__ == "__main__":
    main()
