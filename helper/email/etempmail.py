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
                    
                    # 切换到iframe再获取body内容
                    iframe = self.tab.get_frame('css=iframe', timeout=5)
                    if iframe:
                        # 尝试多种可能的选择器来获取内容
                        for selector in ["css=body", "css=.email-content", "css=tbody", "css=div.content"]:
                            try:
                                iframe.wait(2)  # 给iframe内容一点加载时间
                                code_element = iframe.ele(selector, timeout=3)
                                if code_element and code_element.text.strip():
                                    print(f"Found content with selector: {selector}")
                                    return {"text": code_element.text}
                            except Exception as e:
                                print(f"Failed with selector {selector}: {e}")
                    
                    # 如果iframe方法失败，尝试直接在页面中查找
                    try:
                        # 尝试查找可能包含验证码的元素
                        for selector in ["css=body", "css=.email-body", "css=.message-content"]:
                            try:
                                code_element = self.tab.ele(selector, timeout=3)
                                if code_element and code_element.text.strip():
                                    print(f"Found content directly with selector: {selector}")
                                    return {"text": code_element.text}
                            except:
                                pass
                    except Exception as e:
                        print(f"Failed to find content in main page: {e}")
                    
                    # 最后尝试获取整个页面内容
                    print("Trying to get full page content")
                    full_text = self.tab.get_text()
                    if full_text and "Cursor" in full_text and any(c.isdigit() for c in full_text):
                        print("Found content in full page text")
                        return {"text": full_text}
                        
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
    
