import streamlit as st
import yt_dlp
import os
import re
import requests
from datetime import datetime
from urllib.parse import urlparse

st.set_page_config(
    page_title="Video Downloader - Facebook & YouTube",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 Trình Tải Video Facebook & YouTube")
st.write("Hỗ trợ tải video từ **Facebook** và **YouTube**. Dán link vào ô bên dưới để bắt đầu.")


def detect_platform(url: str) -> str:
    """Nhận diện nền tảng từ URL"""
    url_lower = url.lower()
    if any(x in url_lower for x in ["youtube.com", "youtu.be", "youtube-nocookie.com"]):
        return "youtube"
    if any(x in url_lower for x in ["facebook.com", "fb.watch", "fb.com", "m.facebook.com"]):
        return "facebook"
    return "unknown"


def format_size(bytes_value):
    """Chuyển đổi kích thước file từ Bytes sang MB"""
    if not bytes_value:
        return 0, "Không rõ"
    size_mb = bytes_value / (1024 * 1024)
    return size_mb, f"{size_mb:.1f} MB"


def get_remote_size_bytes(url):
    """Lấy dung lượng thật từ header khi yt-dlp không cung cấp"""
    try:
        resp = requests.head(url, allow_redirects=True, timeout=5)
        size_bytes = int(resp.headers.get("Content-Length", 0))
        return size_bytes
    except Exception:
        return 0


def clean_and_shorten_title(title, max_words=5):
    """Làm sạch tiêu đề, loại bỏ ký tự đặc biệt Windows"""
    if not title:
        return "Video"
    title_clean = re.sub(r'[\/*?:"<>|]', "", title)
    title_clean = " ".join(title_clean.split())
    words = title_clean.split()
    short_title = "_".join(words[:max_words])
    return short_title if short_title else "Video"


def get_base_ydl_opts(platform: str, for_download: bool = False) -> dict:
    """Tạo options yt-dlp ổn định hơn, đặc biệt với YouTube 403"""
    opts = {
        "nocheckcertificate": True,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "force_ipv4": True,  # Tránh một số chặn IPv6
    }

    if platform == "youtube":
        # mweb hiện đang là client ổn định nhất với lỗi 403 (tháng 8/2026)
        opts["extractor_args"] = {
            "youtube": {
                "player_client": ["mweb", "android", "web"],
            }
        }
        # Thêm headers giống trình duyệt thật
        opts["http_headers"] = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
        }

    return opts


def extract_video_info(url: str, platform: str):
    """Trích xuất metadata video (dùng chung cho FB & YT)"""
    ydl_opts = get_base_ydl_opts(platform)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            formats = info.get("formats", [])
            thumbnail_url = info.get("thumbnail")
            title = info.get("title", "Video")

            video_formats = []
            audio_formats = []

            for f in formats:
                file_size_bytes = f.get("filesize") or f.get("filesize_approx") or 0

                is_video = (
                    f.get("vcodec") != "none"
                    and f.get("height")
                    and f.get("url")
                )
                is_audio_only = (
                    f.get("acodec") != "none"
                    and (f.get("vcodec") == "none" or not f.get("height"))
                    and f.get("url")
                )

                if not file_size_bytes and (is_video or is_audio_only):
                    file_size_bytes = get_remote_size_bytes(f["url"])

                size_mb, size_label = format_size(file_size_bytes)

                if is_video:
                    # Ưu tiên format có cả video + audio (đặc biệt quan trọng với YouTube)
                    has_audio = f.get("acodec") not in (None, "none")
                    video_formats.append(
                        {
                            "resolution": f"{f['height']}p",
                            "format_id": f["format_id"],
                            "url": f["url"],
                            "size_mb": size_mb,
                            "size_label": size_label,
                            "height": f["height"],
                            "has_audio": has_audio,
                            "ext": f.get("ext", "mp4"),
                            "fps": f.get("fps"),
                            "vcodec": f.get("vcodec", ""),
                        }
                    )
                elif is_audio_only:
                    audio_formats.append(
                        {
                            "format_id": f["format_id"],
                            "url": f["url"],
                            "size_mb": size_mb,
                            "size_label": size_label,
                            "abr": f.get("abr") or 0,
                            "ext": f.get("ext", "m4a"),
                        }
                    )

            # Loại bỏ trùng resolution (giữ bản có audio hoặc size lớn hơn)
            unique_videos = {}
            for v in video_formats:
                key = v["height"]
                if key not in unique_videos:
                    unique_videos[key] = v
                else:
                    # Ưu tiên bản đã có audio, sau đó bản lớn hơn
                    existing = unique_videos[key]
                    if (v["has_audio"] and not existing["has_audio"]) or (
                        v["has_audio"] == existing["has_audio"]
                        and v["size_mb"] > existing["size_mb"]
                    ):
                        unique_videos[key] = v

            video_formats = list(unique_videos.values())
            video_formats = sorted(video_formats, key=lambda x: x["height"], reverse=True)

            return video_formats, audio_formats, thumbnail_url, title
        except Exception as e:
            st.error(f"Không thể lấy thông tin video: {e}")
            return None, None, None, None


def download_and_merge(video_url: str, chosen_format: dict, title: str, platform: str):
    """Tải video + audio và gộp bằng ffmpeg"""
    current_time = datetime.now().strftime("%H%M%S")
    short_name = clean_and_shorten_title(title, max_words=4)
    final_name = f"{short_name}_{current_time}_{chosen_format['resolution']}"
    temp_filename = f"server_temp_{current_time}.mp4"

    # Format selector: ưu tiên format_id + bestaudio
    format_str = f"{chosen_format['format_id']}+bestaudio/best"

    ydl_opts = get_base_ydl_opts(platform, for_download=True)
    ydl_opts.update(
        {
            "format": format_str,
            "merge_output_format": "mp4",
            "outtmpl": temp_filename,
            "restrictfilenames": True,
        }
    )

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])

    return temp_filename, final_name


def download_best_youtube(video_url: str, title: str):
    """Tải nhanh bản tốt nhất cho YouTube (bestvideo+bestaudio)"""
    current_time = datetime.now().strftime("%H%M%S")
    short_name = clean_and_shorten_title(title, max_words=4)
    final_name = f"{short_name}_{current_time}_best"
    temp_filename = f"server_temp_{current_time}.mp4"

    ydl_opts = get_base_ydl_opts("youtube", for_download=True)
    ydl_opts.update(
        {
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "outtmpl": temp_filename,
            "restrictfilenames": True,
        }
    )

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])

    return temp_filename, final_name


# ==================== GIAO DIỆN CHÍNH ====================

col_input, col_btn = st.columns([6, 1], vertical_alignment="bottom")

with col_input:
    video_url = st.text_input(
        "Nhập link video (Facebook hoặc YouTube):",
        placeholder="https://www.youtube.com/watch?v=... hoặc https://facebook.com/...",
    )

with col_btn:
    st.write("")
    st.write("")
    go_btn = st.button("➡️", use_container_width=True)

if video_url:
    video_url = video_url.strip()
    platform = detect_platform(video_url)

    if platform == "unknown":
        st.warning(
            "⚠️ Link không được nhận diện là Facebook hoặc YouTube. "
            "Vẫn sẽ thử tải bằng yt-dlp (có thể thành công với một số trang khác)."
        )
        platform = "other"

    platform_label = {
        "youtube": "YouTube",
        "facebook": "Facebook",
        "other": "Khác",
    }.get(platform, platform)

    st.info(f"📡 Nền tảng phát hiện: **{platform_label}**")

    with st.spinner("Đang phân tích cấu trúc dữ liệu video..."):
        video_formats, audio_formats, thumbnail_url, title = extract_video_info(
            video_url, platform
        )

    if video_formats:
        st.success(f"Tìm thấy video: **{title[:100]}{'...' if len(title) > 100 else ''}**")

        # Thumbnail
        if thumbnail_url:
            thumb_col, _ = st.columns([1, 2])
            with thumb_col:
                st.image(thumbnail_url, use_container_width=True)

        # ===== Nút tải nhanh bản tốt nhất (đặc biệt hữu ích với YouTube) =====
        if platform == "youtube":
            st.write("---")
            st.markdown("### ⚡ Tải nhanh bản tốt nhất")
            st.caption(
                "Tự động chọn **bestvideo + bestaudio**, gộp thành 1 file MP4 hoàn chỉnh. "
                "Phù hợp khi bạn chỉ muốn chất lượng cao nhất."
            )
            if st.button("🚀 Tải bản tốt nhất (Server)", key="best_yt", use_container_width=False):
                with st.spinner("Đang tải và gộp video YouTube bằng FFmpeg... Vui lòng chờ..."):
                    try:
                        temp_filename, final_name = download_best_youtube(video_url, title)
                        if os.path.exists(temp_filename):
                            with open(temp_filename, "rb") as f:
                                video_bytes = f.read()
                            st.success("✅ Đã xử lý xong file hoàn chỉnh!")
                            st.download_button(
                                label="📥 Lưu file về máy tính",
                                data=video_bytes,
                                file_name=f"{final_name}.mp4",
                                mime="video/mp4",
                                key="download_best_yt",
                            )
                            os.remove(temp_filename)
                    except Exception as e:
                        st.error(f"Thao tác thất bại: {e}")

        # ===== Audio gốc (nếu có) =====
        if audio_formats:
            best_audio = sorted(audio_formats, key=lambda a: a["abr"], reverse=True)[0]
            st.write("---")
            st.info(
                "🎵 **Lưu ý:** Một số độ phân giải cao tách riêng luồng hình và tiếng. "
                "Bạn có thể lấy link audio gốc bên dưới nếu cần."
            )
            audio_res_col, audio_link_col, _ = st.columns([2, 2, 3])
            with audio_res_col:
                st.markdown("🎵 **Audio gốc**")
                bitrate_label = (
                    f"{int(best_audio['abr'])}kbps"
                    if best_audio["abr"]
                    else "Không rõ bitrate"
                )
                st.caption(f"{best_audio['size_label']} · {bitrate_label}")
            with audio_link_col:
                st.markdown(
                    f'<a href="{best_audio["url"]}" target="_blank">'
                    f'<button style="background-color: #1DB954; color: white; border: none; '
                    f"padding: 6px 12px; border-radius: 5px; font-weight: bold; cursor: pointer; width: 100%;\">"
                    f"Lấy Link Audio Gốc</button></a>",
                    unsafe_allow_html=True,
                )

        st.write("---")

        # ===== Bảng chọn độ phân giải =====
        header_res, header_c1, header_c2 = st.columns([2, 2, 3])
        with header_res:
            st.markdown("**Độ phân giải**")
        with header_c1:
            st.markdown("**🔗 Cách 1: Tải trực tiếp**")
        with header_c2:
            st.markdown("**🖥️ Cách 2: Tải qua Server (tự gộp)**")

        st.caption(
            "Cách 1: Tốc độ tối đa, không lo sập web, hỗ trợ file lớn.  \n"
            "Cách 2: Server tự tải và gộp thành 1 file MP4 hoàn chỉnh. Khuyến nghị < 1GB."
        )
        st.write("---")

        if audio_formats:
            best_audio = sorted(audio_formats, key=lambda a: a["abr"], reverse=True)[0]
            best_audio_mb = best_audio["size_mb"]
        else:
            best_audio = None
            best_audio_mb = 0

        for idx, item in enumerate(video_formats):
            res_col, c1_col, c2_col = st.columns([2, 2, 3])

            # Ước tính dung lượng sau khi gộp
            if item["has_audio"] or not best_audio:
                merged_mb = item["size_mb"]
            else:
                merged_mb = item["size_mb"] + best_audio_mb

            with res_col:
                audio_badge = " 🔊" if item["has_audio"] else " 🔇"
                st.markdown(f"🎬 **{item['resolution']}**{audio_badge}")
                st.caption(f"Video: {item['size_label']}")
                if not item["has_audio"] and best_audio:
                    st.caption(f"Gộp (video+audio): ~{merged_mb:.1f} MB")

            with c1_col:
                st.markdown(
                    f'<a href="{item["url"]}" target="_blank">'
                    f'<button style="background-color: #FFCC00; color: black; border: none; '
                    f"padding: 6px 12px; border-radius: 5px; font-weight: bold; cursor: pointer; width: 100%;\">"
                    f"Lấy Link Gốc</button></a>",
                    unsafe_allow_html=True,
                )

            with c2_col:
                too_large = merged_mb > 1024
                if too_large:
                    st.caption(
                        f"⚠️ Gộp xong ước tính ~{merged_mb:.1f} MB, vượt giới hạn 1GB. Nên dùng Cách 1."
                    )

                server_key = f"server_btn_{idx}"
                if st.button(
                    "🚀 Tải qua Server",
                    key=server_key,
                    disabled=too_large,
                    use_container_width=True,
                ):
                    with st.spinner(
                        "Hệ thống đang tải và gộp luồng bằng FFmpeg... Vui lòng chờ..."
                    ):
                        try:
                            temp_filename, final_name = download_and_merge(
                                video_url, item, title, platform
                            )

                            if os.path.exists(temp_filename):
                                with open(temp_filename, "rb") as f:
                                    video_bytes = f.read()

                                st.success("✅ Đã xử lý xong file hoàn chỉnh!")
                                st.download_button(
                                    label="📥 Lưu file về máy tính",
                                    data=video_bytes,
                                    file_name=f"{final_name}.mp4",
                                    mime="video/mp4",
                                    key=f"download_btn_{idx}",
                                )
                                os.remove(temp_filename)
                        except Exception as e:
                            st.error(
                                f"Thao tác thất bại do quá tải hoặc lỗi định dạng: {e}"
                            )

            st.write("---")

    elif video_formats is not None:
        st.warning("Không tìm thấy định dạng video phù hợp từ link này.")
