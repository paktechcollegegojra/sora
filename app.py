# Updated part for app.py
with SB(uc=True, headless=True, ad_block=True) as sb:
    # 1. Open the page with a "reconnect" strategy
    sb.uc_open_with_reconnect(sora_url, reconnect_time=5)
    
    # 2. Add a small random human-like delay
    sb.sleep(4) 
    
    # 3. Try to bypass the Turnstile check automatically
    try:
        sb.uc_gui_click_captcha() 
    except:
        pass # If there's no captcha, just move on
    
    # 4. Wait for the video element specifically
    sb.wait_for_element("video", timeout=15)
    video_src = sb.get_attribute("video", "src")
