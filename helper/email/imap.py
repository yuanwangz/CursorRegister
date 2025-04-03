import time
import imaplib
import email
from email.policy import default
from datetime import datetime

from ._email_server import EmailServer

class Imap(EmailServer):

    # 邮箱服务配置，根据域名映射到对应的IMAP服务器
    EMAIL_SERVER_CONFIG = {
        # 常见邮箱服务的IMAP服务器配置
        "gmail.com": {"imap_server": "imap.gmail.com", "port": 993},
        "qq.com": {"imap_server": "imap.qq.com", "port": 993},
        "vip.qq.com": {"imap_server": "imap.qq.com", "port": 993},
        "foxmail.com": {"imap_server": "imap.qq.com", "port": 993},
        "163.com": {"imap_server": "imap.163.com", "port": 993},
        "126.com": {"imap_server": "imap.126.com", "port": 993},
        "outlook.com": {"imap_server": "outlook.office365.com", "port": 993},
        "hotmail.com": {"imap_server": "outlook.office365.com", "port": 993},
        "yahoo.com": {"imap_server": "imap.mail.yahoo.com", "port": 993},
        # 可以根据需求添加更多邮箱服务商配置
    }

    # 默认IMAP服务器配置
    DEFAULT_IMAP_CONFIG = {"imap_server": "imap.gmail.com", "port": 993}
    
    def __init__(self, username, password):
        # 从邮箱地址中提取域名
        domain = self._extract_domain(username)
        # 获取对应的IMAP服务器配置
        server_config = self._get_server_config(domain)
        
        self.imap_server = server_config["imap_server"]
        self.port = server_config["port"]
        self.mail = imaplib.IMAP4_SSL(self.imap_server, self.port)
        self.mail.login(username, password)

        self.latest_id = None
        
    def _extract_domain(self, email):
        """从邮箱地址中提取域名部分"""
        if '@' in email:
            return email.split('@')[-1].lower()
        return "gmail.com"  # 默认域名

    def _get_server_config(self, domain):
        """根据域名获取对应的IMAP服务器配置"""
        return self.EMAIL_SERVER_CONFIG.get(domain, self.DEFAULT_IMAP_CONFIG)
        
    def fetch_emails_since(self, since_timestamp):

        # Get the latest email by id
        self.mail.select('inbox')
        search_criteria = f'UID {int(self.latest_id) + 1}:*' if self.latest_id else 'ALL'
        _, data = self.mail.uid("SEARCH", None, search_criteria)
        email_ids = data[0].split()
        if len(email_ids) == 0:
            return None

        self.latest_id = email_ids[-1]
        print(f"latest_id: {self.latest_id}")
        # Fetch the email message by ID
        _, data = self.mail.uid('FETCH', self.latest_id, '(RFC822)')
        raw_email = data[0][1]
        msg = email.message_from_bytes(raw_email, policy=default)

        # Extract common headers
        from_header = msg.get('From')
        to_header = msg.get('To')
        subject_header = msg.get('Subject')
        date_header = msg.get('Date')
        
        print(f"subject_header: {subject_header}")
        print(f"date_header: {date_header}")
        

        email_datetime = datetime.strptime(date_header.replace(' (UTC)', ''), '%a, %d %b %Y %H:%M:%S %z').timestamp()
        if email_datetime < since_timestamp:
            pass
            return None

        text_part = msg.get_body(preferencelist=('plain',))
        content = text_part.get_content() if text_part else msg.get_content()

        return {
            "from": from_header,
            "to": to_header,
            "date": date_header,
            "subject": subject_header,
            "content": content
        }
    
    def wait_for_new_message(self, delay=5, timeout=300):
        start_time = time.time()

        while time.time() - start_time <= timeout:
            try:
                email = self.fetch_emails_since(start_time)
                if email is not None:
                    return email
            except:
                pass
            time.sleep(delay)

        return None
