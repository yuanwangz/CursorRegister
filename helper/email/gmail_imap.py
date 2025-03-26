import time
import imaplib
import email
import re
from email.policy import default
from datetime import datetime

from ._email_server import EmailServer

class GmailImap(EmailServer):
    """使用IMAP协议访问Gmail邮箱获取验证码"""

    def __init__(self, username, password):
        """
        初始化Gmail IMAP连接
        
        参数:
            username: Gmail邮箱地址
            password: Gmail应用专用密码(App Password)
        """
        self.username = username
        self.password = password
        self.imap_server = "imap.gmail.com"
        self.email_address = username
        
        # 连接到Gmail IMAP服务器
        self.mail = imaplib.IMAP4_SSL(self.imap_server)
        self.mail.login(username, password)
        self.mail.select('inbox')
        
        # 记录启动时间作为基准，只获取此时间之后的邮件
        self.init_timestamp = time.time()
        print(f"[GmailImap] 初始化时间戳: {self.init_timestamp}")
        
        # 记录最新邮件ID以便只检索新邮件
        self.latest_id = self._get_latest_email_id()
        
        # 记录已处理的邮件ID，避免重复处理
        self.processed_ids = set()
        if self.latest_id:
            self.processed_ids.add(self.latest_id)
        
        print(f"[GmailImap] 成功初始化，邮箱: {username}, 最新邮件ID: {self.latest_id}")

    def _get_latest_email_id(self):
        """获取最新邮件ID"""
        try:
            _, data = self.mail.uid("SEARCH", None, 'ALL')
            email_ids = data[0].split()
            if email_ids:
                latest_id = email_ids[-1]
                print(f"[GmailImap] 获取到最新邮件ID: {latest_id}")
                return latest_id
            return None
        except Exception as e:
            print(f"[GmailImap] 获取最新邮件ID出错: {e}")
            return None
        
    def get_email_address(self):
        """返回Gmail邮箱地址"""
        return self.email_address
    
    def fetch_new_emails(self):
        """获取新邮件，只获取初始化后收到的邮件"""
        # 确保每次调用都重新选择收件箱
        self.mail.select('inbox')
        
        try:
            # 搜索所有邮件
            _, data = self.mail.uid("SEARCH", None, 'ALL')
            email_ids = data[0].split()
            
            if not email_ids:
                print("[GmailImap] 没有找到任何邮件")
                return None
                
            # 获取最新的邮件ID
            newest_id = email_ids[-1]
            
            # 如果最新ID相同且已处理过，说明没有新邮件
            if newest_id in self.processed_ids:
                print(f"[GmailImap] 没有新邮件，最新ID: {newest_id}")
                return None
            
            # 获取最新邮件
            _, data = self.mail.uid('FETCH', newest_id, '(RFC822)')
            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email, policy=default)
            
            # 获取邮件接收时间
            received_time = None
            if 'Date' in msg:
                date_str = msg['Date']
                try:
                    # 尝试解析邮件日期
                    date_tuple = email.utils.parsedate_tz(date_str)
                    if date_tuple:
                        received_time = email.utils.mktime_tz(date_tuple)
                except:
                    pass
            
            # 如果能获取到接收时间，验证是否是在初始化后收到的邮件
            if received_time and received_time < self.init_timestamp:
                print(f"[GmailImap] 跳过初始化前的邮件，邮件时间: {received_time}, 初始化时间: {self.init_timestamp}")
                # 标记为已处理
                self.processed_ids.add(newest_id)
                return None
                
            # 提取邮件信息
            from_header = msg.get('From', '')
            subject = msg.get('Subject', '')
            
            # 只处理来自Cursor的邮件
            if "cursor" not in from_header.lower() and "cursor" not in subject.lower():
                print(f"[GmailImap] 跳过非Cursor邮件，发件人: {from_header}, 主题: {subject}")
                # 标记为已处理
                self.processed_ids.add(newest_id)
                return None
            
            # 提取正文内容
            content = ""
            if msg.is_multipart():
                # 处理多部分邮件
                for part in msg.get_payload():
                    if part.get_content_type() == 'text/plain':
                        content += part.get_payload(decode=True).decode('utf-8', errors='ignore')
            else:
                # 处理单部分邮件
                content = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
            
            # 更新最新ID并标记为已处理
            self.latest_id = newest_id
            self.processed_ids.add(newest_id)
            
            print(f"[GmailImap] 成功获取新邮件，ID: {newest_id}, 主题: {subject}")
            
            return {
                "from": from_header,
                "subject": subject,
                "text": content,
                "date": msg.get('Date', '')
            }
        except Exception as e:
            print(f"[GmailImap] 获取新邮件时出错: {e}")
            return None
    
    def extract_verification_code(self, text):
        """
        从邮件内容中提取6位数字验证码
        """
        if not text:
            return None
            
        # 尝试多种模式匹配验证码
        # 1. 直接匹配6位数字
        pattern1 = re.compile(r'\b(\d{6})\b')
        # 2. 匹配常见的验证码模式
        pattern2 = re.compile(r'code[:\s]*(\d{6})', re.IGNORECASE)
        pattern3 = re.compile(r'verification[:\s]*(\d{6})', re.IGNORECASE)
        # 3. 匹配邮件中格式化的验证码 (如 "9 9 2 2 8 2")
        pattern4 = re.compile(r'(\d\s+\d\s+\d\s+\d\s+\d\s+\d)')
        
        for pattern in [pattern1, pattern2, pattern3]:
            match = pattern.search(text)
            if match:
                return match.group(1)
                
        # 处理格式化的验证码
        match = pattern4.search(text)
        if match:
            # 移除所有空格
            formatted_code = re.sub(r'\s+', '', match.group(1))
            if formatted_code.isdigit() and len(formatted_code) == 6:
                return formatted_code
                
        return None
    
    def wait_for_new_message(self, delay=5, timeout=300):
        """
        等待并返回新邮件中的验证码
        
        参数:
            delay: 每次检查之间的延迟(秒)
            timeout: 超时时间(秒)
        """
        print(f"[GmailImap] 开始等待新邮件，超时时间: {timeout}秒")
        start_time = time.time()
        
        while time.time() - start_time <= timeout:
            try:
                email_data = self.fetch_new_emails()
                if email_data and "text" in email_data:
                    print(f"[GmailImap] 成功获取到新邮件: {email_data.get('subject', '无主题')}")
                    return email_data
            except Exception as e:
                print(f"[GmailImap] 等待新邮件时出错: {e}")
                
            # 打印剩余等待时间
            remaining = timeout - (time.time() - start_time)
            if remaining > 0:
                print(f"[GmailImap] 继续等待新邮件，剩余时间: {int(remaining)}秒")
            time.sleep(delay)
        
        print(f"[GmailImap] 等待超时，未收到新邮件")
        return None
        
    def wait_for_message(self, delay=5, timeout=300):
        """兼容EmailServer接口"""
        return self.wait_for_new_message(delay, timeout) 