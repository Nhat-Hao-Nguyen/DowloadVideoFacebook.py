import streamlit as st
import yt_dlp
import os
import re
from datetime import datetime

st.set_page_config(page_title="Facebook Video Downloader", page_icon="🎬", layout="centered")
st.title("🎬 Trình Tải Video Facebook Theo Tiêu Đề")

def clean_and_shorten_title(title, max_words=5):
    """Làm sạch tiêu đề, xóa ký tự đặc biệt của Windows và lấy số từ chỉ định"""
    if not title:
        return "Video"
    
    # Loại bỏ các ký tự cấm đặt tên file trên Windows: \ / : * ? " < > |
    title_clean = re.sub(r'[\/*?:"<>|]', '', title)
    # Loại bỏ dấu xuống dòng và khoảng trắng thừa
    title_clean = " ".join(title_clean.split())
    
    # Tách thành các từ và lấy tối đa số từ quy định
    words = title_clean.split()
    short_title = "_".join(words[:max_words])
    
    # Nếu tiêu đề rỗng sau khi lọc, trả về mặc định
    return short_title if short_title else "Video"

def get_video_formats(url):
    """Trích xuất danh sách định dạng và tiêu đề gốc của video"""
    ydl_opts = {'nocheckcertificate': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])
            available_resolutions = {}
            for f in formats:
                if f.get('vcodec') != 'none' and f.get('height'):
                    res_name = f"{f['height']}p"
                    available_resolutions[res_name] = f['format_id']
            return available_resolutions, info.get('title', 'Facebook_Video')
        except Exception as e:
            st.error(f"Không thể lấy thông tin video: {e}")
            return None, None

video_url = st.text_input("Nhập link video Facebook:", placeholder="https://facebook.com...")

if video_url:
    video_url = video_url.strip()
    
    if 'formats_dict' not in st.session_state or st.session_state.get('last_url') != video_url:
        with st.spinner("Đang phân tích video, vui lòng đợi giây lát..."):
            formats_dict, original_title = get_video_formats(video_url)
            if formats_dict:
                st.session_state['formats_dict'] = formats_dict
                st.session_state['original_title'] = original_title
                st.session_state['last_url'] = video_url
            else:
                st.session_state['formats_dict'] = None

    formats_dict = st.session_state.get('formats_dict')
    
    if formats_dict:
        sorted_res = sorted(formats_dict.keys(), key=lambda x: int(x.replace('p', '')))
        
        # Tạo phần tiêu đề rút gọn (Ví dụ lấy 5 từ đầu tiên)
        short_name = clean_and_shorten_title(st.session_state['original_title'], max_words=5)
        current_time = datetime.now().strftime("%H%M%S")
        
        # Tên file hoàn chỉnh: Tieu_De_Rut_Gon_GioPhutGiay_DoPhanGiai.mp4
        final_filename = f"{short_name}_{current_time}_{st.selectbox('Chọn độ phân giải:', sorted_res)}"
        
        st.info(f"📋 Tiêu đề gốc: {st.session_state['original_title']}")
        st.success(f"💾 Tên file dự kiến khi tải về: `{final_filename}.mp4`")
        
        if st.button("Xử lý Video để Tải xuống"):
            selected_res = final_filename.split('_')[-1]
            format_id = formats_dict[selected_res]
            temp_filename = f"temp_{current_time}.mp4"
            
            with st.spinner("Đang chuẩn bị file..."):
                ydl_opts = {
                    'format': f'{format_id}+bestaudio/best',
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
                        
                        st.download_button(
                            label="📥 Bấm vào đây để lưu video về máy",
                            data=video_bytes,
                            file_name=f"{final_filename}.mp4",
                            mime="video/mp4"
                        )
                        os.remove(temp_filename)
                except Exception as e:
                    st.error(f"Có lỗi xảy ra: {e}")
