import time
from DrissionPage import Chromium
import requests
import re

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
                        # 获取当前页面的cookies
                        cookies_dict = self.tab.cookies().as_dict()
                        print("Got cookies")
                        
                        # 发起API请求获取收件箱
                        r = requests.post("https://etempmail.com/getInbox", cookies=cookies_dict)
                        if r.ok:
                            emails = r.json()
                            print(f"Found {len(emails)} emails via API")
                            
                            for email in emails:
                                subject = email.get("subject", "")
                                content = email.get("body", "")
                                
                                if "Sign up for Cursor" in subject:
                                    print(f"Found Cursor verification email: {subject}")
                                    # print(f"Content preview: {content[:100]}...")
                                    
                                    # 提取验证码
                                    code_match = re.search(r"Your one-time code is (\d+)", content)
                                    if code_match:
                                        code = code_match.group(1)
                                        print(f"Extracted verification code: {code}")
                                        return {"text": code}
                                    
                                    return {"text": ''}
                        else:
                            print(f"API request failed: {r.status_code} - {r.text}")
                    except Exception as e:
                        print(f"Error using API method: {e}")
                        
                    print("Failed to find verification email")
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
    
