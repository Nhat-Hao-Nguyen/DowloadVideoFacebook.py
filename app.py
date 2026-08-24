import streamlit as st
import yt_dlp
import os
import re
from datetime import datetime

st.set_page_config(page_title="Facebook Video Downloader", page_icon="🎬", layout="wide") # Đổi sang giao diện rộng (wide)
st.title("🎬 Trình Tải Video Facebook Đa Năng")
st.write("Chọn phương thức tải phù hợp với nhu cầu và dung lượng video của bạn.")

def format_size(bytes_value):
    """Chuyển đổi kích thước file từ định dạng Bytes sang MB để dễ đọc"""
    if not bytes_value:
        return 0, "Không rõ"
    size_mb = bytes_value / (1024 * 1024)
    return size_mb, f"{size_mb:.1f} MB"

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
            for f in formats:
                if f.get('vcodec') != 'none' and f.get('height') and f.get('url'):
                    file_size_bytes = f.get('filesize') or f.get('filesize_approx') or 0
                    size_mb, size_label = format_size(file_size_bytes)
                    
                    video_formats.append({
                        'resolution': f"{f['height']}p",
                        'format_id': f['format_id'],
                        'url': f['url'],
                        'size_mb': size_mb,
                        'size_label': size_label,
                        'height': f['height']
                    })
            return video_formats, thumbnail_url, info.get('title', 'Facebook_Video')
        except Exception as e:
            st.error(f"Không thể kết nối lấy dữ liệu video: {e}")
            return None, None, None

video_url = st.text_input("Nhập link video Facebook:", placeholder="https://facebook.com...")

if video_url:
    video_url = video_url.strip()
    
    with st.spinner("Đang phân tích cấu trúc dữ liệu video..."):
        video_formats, thumbnail_url, title = extract_video_info(video_url)
        
    if video_formats:
        st.success(f"Tìm thấy video: **{title[:80]}...**")
        
        # Sắp xếp các độ phân giải từ cao xuống thấp
        video_formats = sorted(video_formats, key=lambda x: x['height'], reverse=True)
        
        # --- CHIA GIAO DIỆN THÀNH 2 CỘT LỚN ---
        col_left, col_right = st.columns(2)
        
        # ==========================================
        # CỘT BÊN TRÁI: TẢI TRỰC TIẾP (CLIENT SIDE)
        # ==========================================
        with col_left:
            st.subheader("🔗 Cách 1: Tải trực tiếp từ Facebook")
            st.caption("Tốc độ tối đa, không lo sập web, hỗ trợ file cực lớn. (Lưu ý: Độ phân giải cao có thể tách riêng hình/tiếng).")
            
            if thumbnail_url:
                st.image(thumbnail_url, use_container_width=True)
                
            st.write("---")
            for item in video_formats:
                c1, c2 = st.columns([3, 2])
                with c1:
                    st.markdown(f"🎬 **Độ phân giải {item['resolution']}** ({item['size_label']})")
                with c2:
                    st.markdown(
                        f'<a href="{item["url"]}" target="_blank">'
                        f'<button style="background-color: #FFCC00; color: black; border: none; '
                        f'padding: 5px 10px; border-radius: 5px; font-weight: bold; cursor: pointer; width: 100%;">'
                        f'Lấy Link Gốc</button></a>', 
                        unsafe_allow_html=True
                    )

        # ==========================================
        # CỘT BÊN PHẢI: TẢI VỀ SERVER (SERVER SIDE)
        # ==========================================
        with col_right:
            st.subheader("🖥️ Cách 2: Tải qua Máy chủ (Tự động gộp)")
            st.caption("Máy chủ sẽ tải hộ cả hình lẫn tiếng rồi gộp thành file MP4 hoàn chỉnh cho bạn tải về.")
            
            # Tạo hộp chọn độ phân giải cho cột Server
            res_options = [f"{item['resolution']} ({item['size_label']})" for item in video_formats]
            selected_option = st.selectbox("Chọn chất lượng muốn máy chủ gộp:", res_options)
            
            # Tìm dữ liệu của định dạng được chọn
            selected_index = res_options.index(selected_option)
            chosen_format = video_formats[selected_index]
            
            # KIỂM TRA ĐIỀU KIỆN DUNG LƯỢNG > 1GB (1024 MB)
            if chosen_format['size_mb'] > 1024:
                st.warning(f"⚠️ **Cảnh báo:** Video này có dung lượng quá lớn ({chosen_format['size_label']}), vượt quá giới hạn xử lý an toàn 1GB của máy chủ. Bạn **nên sử dụng Cách 1 (Tải trực tiếp)** bên trái để tránh làm gián đoạn hệ thống.")
            
            # Nút xử lý trên server
            if st.button("🚀 Bắt đầu xử lý trên Server"):
                current_time = datetime.now().strftime("%H%M%S")
                short_name = clean_and_shorten_title(title, max_words=4)
                final_name = f"{short_name}_{current_time}_{chosen_format['resolution']}"
                temp_filename = f"server_temp_{current_time}.mp4"
                
                with st.spinner("Hệ thống đang tải và gộp luồng bằng FFmpeg... Vui lòng chờ..."):
                    ydl_opts = {
                        'format': f"{chosen_format['format_id']}+bestaudio/best",
                        'merge_output_format': 'mp4',
                        'outtmpl': temp_filename, 
                        'nocheckcertificate': True,     
                        'restrictfilenames': True,     
                    }
                    
                    try:
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            ydl.download([video_url])
                        
                        if os.path.exists(temp_filename):
                            with open(temp_filename, "rb") as f:
                                video_bytes = f.read()
                            
                            st.success("✅ Đã xử lý xong file hoàn chỉnh!")
                            st.download_button(
                                label="📥 Bấm vào đây để lưu file về máy tính",
                                data=video_bytes,
                                file_name=f"{final_name}.mp4",
                                mime="video/mp4"
                            )
                            # Xóa file rác ngay lập tức
                            os.remove(temp_filename)
                    except Exception as e:
                        st.error(f"Thao tác thất bại do quá tải hoặc lỗi định dạng: {e}")
