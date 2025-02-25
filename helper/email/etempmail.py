import time
from DrissionPage import Chromium

class EtempMail:

    ETEMPMAIL_URL = "https://etempmail.com"

    def __init__(self, browser: Chromium):
        self.tab = browser.new_tab(self.ETEMPMAIL_URL)

    def get_email_address(self):
        email_address = None
        self.tab.ele("xpath=//button[@id='deleteEmailAddress']", timeout=5).click()

        for _ in range(5):
            try:
                self.tab.refresh()
                self.tab.wait(6)
                email = self.tab.ele("xpath=//input[@id='tempEmailAddress']", timeout=5).value
                if email != "" and email != "Please wait..":
                    email_address = email
                    break
            except Exception as e:
                print(e)
                pass

        if email_address is None:
            print("[etempmail.com] Fail to get email address")
            return None
        
        return email_address
        
    def wait_for_message(self, delay=5, timeout=90):
        start_time = time.time()
        email_click_flag = False
        while time.time() - start_time <= timeout:
            try:
                # self.tab.refresh()
                self.tab.wait(2)
                email_elements = self.tab.eles("css=.mail-open td")
                for element in email_elements:
                    if "Cursor" in element.text:
                        print("email_from:", element.text)
                        element.click(by_js=True)
                        email_click_flag = True
                        break
                if email_click_flag:
                    self.tab.wait(5)
                    print("click email success")
                    
                    # 等待邮件内容加载
                    self.tab.wait(5)
                    
                    # 首先尝试获取所有iframe
                    iframes = self.tab.eles('css=iframe', timeout=5)
                    print(f"Found {len(iframes)} iframes on page")
                    
                    # 遍历所有iframe查找内容
                    for i, frame in enumerate(iframes):
                        try:
                            iframe = self.tab.get_frame(f'css=iframe:nth-child({i+1})', timeout=3)
                            if not iframe:
                                continue
                                
                            print(f"Checking iframe #{i+1}")
                            for selector in ["css=body", "css=.email-content", "css=tbody", "css=div.content"]:
                                try:
                                    iframe.wait(1)
                                    content = iframe.ele(selector, timeout=2)
                                    if content and content.text.strip():
                                        text = content.text.strip()
                                        print(f"Found content in iframe #{i+1} with selector {selector}: {text[:50]}...")
                                        if any(c.isdigit() for c in text):  # 确保文本中包含数字(可能是验证码)
                                            return {"text": text}
                                except Exception as e:
                                    pass
                        except Exception as e:
                            print(f"Error processing iframe #{i+1}: {e}")
                    
                    # 尝试查找可能包含验证码的元素
                    print("Checking main page content")
                    for selector in ["css=body", "css=.email-body", "css=.message-content", "css=.mail-content"]:
                        try:
                            content = self.tab.ele(selector, timeout=2)
                            if content and content.text.strip():
                                text = content.text.strip()
                                print(f"Found content with selector {selector}: {text[:50]}...")
                                # 检查文本中是否包含数字和Cursor关键词
                                if "Cursor" in text and any(c.isdigit() for c in text):
                                    return {"text": text}
                        except:
                            pass
                    
                    # 最后尝试获取整个页面内容
                    print("Trying to get full page content")
                    try:
                        full_text = self.tab.get_text()
                        print(f"Full page text length: {len(full_text)}")
                        if full_text and "Cursor" in full_text and any(c.isdigit() for c in full_text):
                            print(f"Found verification code in full text: {full_text[:100]}...")
                            return {"text": full_text}
                    except Exception as e:
                        print(f"Error getting full text: {e}")
                        
                    # 尝试截图以便调试
                    try:
                        screenshot_path = "/tmp/email_debug.png"
                        self.tab.get_screenshot(screenshot_path)
                        print(f"Saved debug screenshot to {screenshot_path}")
                    except:
                        pass
                        
                    print("Failed to find any content with verification code")
            except Exception as e:
                print(e)
                pass
            # print("not found code, wait 5 seconds..")
            self.tab.wait(delay)

        return None

if __name__ == "__main__":
    browser = Chromium()
    email_server = EtempMail(browser)
    email = email_server.get_email_address()
    print(email)
    message = email_server.wait_for_message().get("text", None)
    import re
    verify_code = re.search(r'(\d{6})', message).group(1)
    print(verify_code)
    
