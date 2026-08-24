import streamlit as st
import yt_dlp

st.set_page_config(page_title="Facebook Video Downloader", page_icon="🎬", layout="centered")
st.title("🎬 Trình Tải Video Facebook Tốc Độ Cao")
st.write("Giải pháp tải trực tiếp từ máy chủ Facebook, không giới hạn dung lượng file.")

def extract_direct_links(url):
    """Chỉ trích xuất link tải trực tiếp từ Facebook, KHÔNG tải video về server"""
    ydl_opts = {
        'nocheckcertificate': True,
        'format': 'bestvideo+bestaudio/best', # Lấy các định dạng tốt nhất
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False) # download=False để không lưu về server
            formats = info.get('formats', [])
            
            download_links = []
            for f in formats:
                # Lọc lấy các luồng có link trực tiếp và định dạng rõ ràng
                if f.get('url') and f.get('height'):
                    # Xác định loại luồng (Video có tiếng hoặc Video không tiếng)
                    acodec = f.get('acodec')
                    status = "Có tiếng" if acodec and acodec != 'none' else "Chỉ có hình (Cần ghép)"
                    
                    download_links.append({
                        'resolution': f"{f['height']}p",
                        'url': f['url'],
                        'status': status,
                        'ext': f.get('ext', 'mp4')
                    })
            return download_links, info.get('title', 'Facebook_Video')
        except Exception as e:
            st.error(f"Không thể lấy link video: {e}")
            return None, None

video_url = st.text_input("Nhập link video Facebook:", placeholder="https://facebook.com...")

if video_url:
    video_url = video_url.strip()
    
    with st.spinner("Đang bóc tách link tải trực tiếp, vui lòng đợi..."):
        links, title = extract_direct_links(video_url)
        
    if links:
        st.success(f"Tìm thấy video: **{title[:60]}...**")
        st.write("---")
        st.subheader("🔗 Danh sách link tải trực tiếp:")
        st.caption("Mẹo: Nhấp chuột phải vào nút tải -> Chọn 'Lưu liên kết thành...' (Save link as...) để tải về máy.")
        
        # Sắp xếp hiển thị từ độ phân giải cao đến thấp
        links = sorted(links, key=lambda x: int(x['resolution'].replace('p', '')), reverse=True)
        
        for item in links:
            col1, col2 = st.columns([3, 2])
            with col1:
                st.markdown(f"🔹 **Độ phân giải {item['resolution']}** ({item['status']})")
            with col2:
                # Tạo thẻ HTML thẻ A để trình duyệt người dùng tự click tự tải thẳng từ Facebook
                st.markdown(
                    f'<a href="{item["url"]}" target="_blank" style="text-decoration: none;">'
                    f'<button style="background-color: #FFCC00; color: black; border: none; '
                    f'padding: 5px 15px; border-radius: 5px; font-weight: bold; cursor: pointer;">'
                    f'Tải về {item["resolution"]}</button></a>', 
                    unsafe_allow_html=True
                )
