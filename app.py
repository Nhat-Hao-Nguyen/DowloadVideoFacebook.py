import streamlit as st
import yt_dlp
import os
import re
import requests
from datetime import datetime

st.set_page_config(page_title="Facebook Video Downloader", page_icon="🎬", layout="wide")
st.title("🎬 Trình Tải Video Facebook Đa Năng")
st.write("Chọn phương thức tải phù hợp với nhu cầu và dung lượng video của bạn.")


def format_size(bytes_value):
    """Chuyển đổi kích thước file từ định dạng Bytes sang MB để dễ đọc"""
    if not bytes_value:
        return 0, "Không rõ"
    size_mb = bytes_value / (1024 * 1024)
    return size_mb, f"{size_mb:.1f} MB"


def get_remote_size_bytes(url):
    """Dự phòng: khi yt-dlp không có sẵn filesize, gọi HEAD request để lấy dung lượng thật từ header"""
    try:
        resp = requests.head(url, allow_redirects=True, timeout=5)
        size_bytes = int(resp.headers.get('Content-Length', 0))
        return size_bytes
    except Exception:
        return 0


def clean_and_shorten_title(title, max_words=5):
    """Làm sạch tiêu đề, xóa ký tự đặc biệt của Windows và lấy số từ chỉ định"""
    if not title:
        return "Video"
    title_clean = re.sub(r'[\/*?:"<>|]', '', title)
    title_clean = " ".join(title_clean.split())
    words = title_clean.split()
    short_title = "_".join(words[:max_words])
    return short_title if short_title else "Video"


def extract_video_info(url):
    """Trích xuất toàn bộ siêu dữ liệu của video từ Facebook"""
    ydl_opts = {'nocheckcertificate': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])
            thumbnail_url = info.get('thumbnail')

            video_formats = []
            audio_formats = []
            for f in formats:
                file_size_bytes = f.get('filesize') or f.get('filesize_approx') or 0

                is_video = f.get('vcodec') != 'none' and f.get('height') and f.get('url')
                # Audio-only: có tiếng nhưng không có hình (vcodec none hoặc height rỗng)
                is_audio_only = f.get('acodec') != 'none' and (f.get('vcodec') == 'none' or not f.get('height')) and f.get('url')

                # Nếu yt-dlp không có sẵn filesize, gọi HEAD request để lấy dung lượng thật
                if not file_size_bytes and (is_video or is_audio_only):
                    file_size_bytes = get_remote_size_bytes(f['url'])

                size_mb, size_label = format_size(file_size_bytes)

                if is_video:
                    video_formats.append({
                        'resolution': f"{f['height']}p",
                        'format_id': f['format_id'],
                        'url': f['url'],
                        'size_mb': size_mb,
                        'size_label': size_label,
                        'height': f['height'],
                        'has_audio': f.get('acodec') not in (None, 'none')  # video đã có sẵn tiếng hay chưa
                    })
                elif is_audio_only:
                    audio_formats.append({
                        'format_id': f['format_id'],
                        'url': f['url'],
                        'size_mb': size_mb,
                        'size_label': size_label,
                        'abr': f.get('abr') or 0  # bitrate audio, dùng để chọn bản tốt nhất
                    })

            return video_formats, audio_formats, thumbnail_url, info.get('title', 'Facebook_Video')
        except Exception as e:
            st.error(f"Không thể kết nối lấy dữ liệu video: {e}")
            return None, None, None, None


def download_and_merge(video_url, chosen_format, title):
    """Tải video + audio và gộp lại bằng ffmpeg, trả về đường dẫn file kết quả"""
    current_time = datetime.now().strftime("%H%M%S")
    short_name = clean_and_shorten_title(title, max_words=4)
    final_name = f"{short_name}_{current_time}_{chosen_format['resolution']}"
    temp_filename = f"server_temp_{current_time}.mp4"

    ydl_opts = {
        'format': f"{chosen_format['format_id']}+bestaudio/best",
        'merge_output_format': 'mp4',
        'outtmpl': temp_filename,
        'nocheckcertificate': True,
        'restrictfilenames': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])

    return temp_filename, final_name


col_input, col_btn = st.columns([6, 1], vertical_alignment="bottom")

with col_input:
    video_url = st.text_input("Nhập link video Facebook:", placeholder="https://facebook.com...")

with col_btn:
    st.write("")          # tạo khoảng trống cho thẳng hàng
    st.write("")
    go_btn = st.button("➡️", use_container_width=True)

if video_url:
    video_url = video_url.strip()

    with st.spinner("Đang phân tích cấu trúc dữ liệu video..."):
        video_formats, audio_formats, thumbnail_url, title = extract_video_info(video_url)

    if video_formats:
        st.success(f"Tìm thấy video: **{title[:80]}...**")

        # Sắp xếp các độ phân giải từ cao xuống thấp
        video_formats = sorted(video_formats, key=lambda x: x['height'], reverse=True)

        # Ảnh thumbnail dùng chung cho cả 2 cách, đặt riêng phía trên bảng
        if thumbnail_url:
            thumb_col, _ = st.columns([1, 2])
            with thumb_col:
                st.image(thumbnail_url, use_container_width=True)

        # ==========================================
        # LINK AUDIO GỐC (dùng chung, vì video độ phân giải cao thường tách riêng tiếng)
        # ==========================================
        if audio_formats:
            best_audio = sorted(audio_formats, key=lambda a: a['abr'], reverse=True)[0]
            st.info(
                "🎵 **Lưu ý:** Với độ phân giải cao, file 'Lấy Link Gốc' bên dưới có thể **không có tiếng** "
                "(Facebook tách riêng luồng hình và luồng tiếng). Tải thêm link audio gốc bên dưới nếu cần ghép lại."
            )
            audio_res_col, audio_link_col, _ = st.columns([2, 2, 3])
            with audio_res_col:
                st.markdown("🎵 **Audio gốc**")
                bitrate_label = f"{int(best_audio['abr'])}kbps" if best_audio['abr'] else "Không rõ bitrate"
                st.caption(f"{best_audio['size_label']} · {bitrate_label}")
            with audio_link_col:
                st.markdown(
                    f'<a href="{best_audio["url"]}" target="_blank">'
                    f'<button style="background-color: #1DB954; color: white; border: none; '
                    f'padding: 6px 12px; border-radius: 5px; font-weight: bold; cursor: pointer; width: 100%;">'
                    f'Lấy Link Audio Gốc</button></a>',
                    unsafe_allow_html=True
                )

        st.write("---")

        # ==========================================
        # BẢNG CHUNG: MỖI ĐỘ PHÂN GIẢI = 1 HÀNG THẲNG
        # Cột: Độ phân giải | Cách 1 (link gốc) | Cách 2 (server)
        # ==========================================
        header_res, header_c1, header_c2 = st.columns([2, 2, 3])
        with header_res:
            st.markdown("**Độ phân giải**")
        with header_c1:
            st.markdown("**🔗 Cách 1: Tải trực tiếp**")
        with header_c2:
            st.markdown("**🖥️ Cách 2: Tải qua Server (tự gộp)**")

        st.caption(
            "Cách 1: Tốc độ tối đa, không lo sập web, hỗ trợ file lớn (độ phân giải cao có thể tách hình/tiếng).  \n"
            "Cách 2: Server tự tải và gộp thành 1 file MP4 hoàn chỉnh. Chỉ tải được video < 1GB"
        )
        st.write("---")

        if audio_formats:
            best_audio = sorted(audio_formats, key=lambda a: a['abr'], reverse=True)[0]
            best_audio_mb = best_audio['size_mb']
        else:
            best_audio = None
            best_audio_mb = 0

        for idx, item in enumerate(video_formats):
            res_col, c1_col, c2_col = st.columns([2, 2, 3])

            # Dung lượng dự kiến khi gộp: nếu video đã có sẵn tiếng thì giữ nguyên,
            # nếu chưa thì cộng thêm dung lượng audio tốt nhất
            if item['has_audio'] or not best_audio:
                merged_mb = item['size_mb']
            else:
                merged_mb = item['size_mb'] + best_audio_mb

            with res_col:
                st.markdown(f"🎬 **{item['resolution']}**")
                st.caption(f"Video: {item['size_label']}")
                if not item['has_audio'] and best_audio:
                    st.caption(f"Gộp (video+audio): ~{merged_mb:.1f} MB")

            with c1_col:
                st.markdown(
                    f'<a href="{item["url"]}" target="_blank">'
                    f'<button style="background-color: #FFCC00; color: black; border: none; '
                    f'padding: 6px 12px; border-radius: 5px; font-weight: bold; cursor: pointer; width: 100%;">'
                    f'Lấy Link Gốc</button></a>',
                    unsafe_allow_html=True
                )

            with c2_col:
                too_large = merged_mb > 1024
                if too_large:
                    st.caption(f"⚠️ Gộp xong ước tính ~{merged_mb:.1f} MB, vượt giới hạn 1GB. Nên dùng Cách 1.")

                server_key = f"server_btn_{idx}"
                if st.button("🚀 Tải qua Server", key=server_key, disabled=too_large, use_container_width=True):
                    with st.spinner("Hệ thống đang tải và gộp luồng bằng FFmpeg... Vui lòng chờ..."):
                        try:
                            temp_filename, final_name = download_and_merge(video_url, item, title)

                            if os.path.exists(temp_filename):
                                with open(temp_filename, "rb") as f:
                                    video_bytes = f.read()

                                st.success("✅ Đã xử lý xong file hoàn chỉnh!")
                                st.download_button(
                                    label="📥 Lưu file về máy tính",
                                    data=video_bytes,
                                    file_name=f"{final_name}.mp4",
                                    mime="video/mp4",
                                    key=f"download_btn_{idx}"
                                )
                                os.remove(temp_filename)
                        except Exception as e:
                            st.error(f"Thao tác thất bại do quá tải hoặc lỗi định dạng: {e}")

            st.write("---")
