import time
from DrissionPage import Chromium
import requests

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
                    
                    # 使用API获取邮件内容
                    try:
                        import requests
                        
                        # 获取当前页面的cookies
                        cookies = {}
                        # 使用正确的方法获取cookies
                        cookies_dict = self.tab.cookies().as_dict()
                        
                        print("Got cookies:", cookies_dict)
                        
                        # 发起API请求获取收件箱
                        r = requests.post("https://etempmail.com/getInbox", cookies=cookies_dict)
                        if r.ok:
                            emails = r.json()
                            print(f"Found {len(emails)} emails via API")
                            
                            for email in emails:
                                content = email.get("body", "")
                                print(f"Email from: {email.get('from', 'unknown')}")
                                print(f"Subject: {email.get('subject', 'no subject')}")
                                print(f"Content preview: {content[:100]}...")
                                
                                if "Sign up for Cursor" in content and any(c.isdigit() for c in content):
                                    print("Found verification email content via API!")
                                    return {"text": content}
                        else:
                            print(f"API request failed: {r.status_code} - {r.text}")
                    except Exception as e:
                        print(f"Error using API method: {e}")
                    
                    # 如果API方法失败，回退到iframe检查方法
                    print("Falling back to iframe method...")
                    
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
                            try:
                                content = iframe.ele("css=body", timeout=2)
                                if content and content.text.strip():
                                    text = content.text.strip()
                                    print(f"Found content in iframe #{i+1}: {text[:100]}...")
                                    if "Sign up for Cursor" in text and any(c.isdigit() for c in text):
                                        print("Found verification email content!")
                                        return {"text": text}
                            except Exception as e:
                                print(f"Error getting body in iframe #{i+1}: {e}")
                        except Exception as e:
                            print(f"Error processing iframe #{i+1}: {e}")
                    
                    # 最后尝试获取整个页面内容
                    print("Trying to get full page content")
                    try:
                        full_text = self.tab.ele("css=html").text
                        print(f"Full page text length: {len(full_text)}")
                        if "Sign up for Cursor" in full_text and any(c.isdigit() for c in full_text):
                            print("Found verification email content in full page!")
                            return {"text": full_text}
                    except Exception as e:
                        print(f"Error getting full text: {e}")
                    
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
    
