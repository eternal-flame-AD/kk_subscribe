import imaplib
import smtplib
import email
import email.header
import email.mime.text
import email.mime.multipart
import email.mime.base
import email.mime.image
import re


def check_contain_chinese(check_str):
    for ch in check_str:
        if u'\u4e00' <= ch <= u'\u9fff':
            return True
    return False


class Email_Received():

    def __init__(self, msg):
        self.msg = msg
        self.sender = msg.get("From")
        try:
            self.sender = re.findall(r"<.*>", self.sender)[0][1:-1]
        except IndexError:
            pass
        self.subject = msg.get("Subject")
        if "=?" in self.subject:
            self.subject, code = email.header.decode_header(self.subject)[0]
            self.subject = self.subject.decode(code)

    def iter_attachment(self):
        msg = self.msg
        for part in msg.walk():
            if part.is_multipart():
                continue
            if part.get('Content-Disposition') is None:
                continue
            name = part.get_filename()
            data = part.get_payload(decode=True)
            real_fn = email.header.decode_header(name)[0]
            if real_fn[1]:
                real_fn = real_fn[0].decode(real_fn[1])  # decode encoding
            else:
                real_fn = real_fn[0]
            yield real_fn, data


class EmailGetter():
    def __init__(self, host, username, password, ssl=True, port=None):
        if not port:
            if ssl:
                port = imaplib.IMAP4_SSL_PORT
            else:
                port = imaplib.IMAP4_PORT
        if ssl:
            self.session = imaplib.IMAP4_SSL(host, port)
        else:
            self.session = imaplib.IMAP4(host, port)
        # self.session.debug=1
        self._login(username, password)
        self.session.send((b'%s ID ("name" "imapbot" "version" "1.0"'
                          + b' "vendor" "ef")\r\n') % self.session._new_tag())

    def _login(self, username, password):
        self.session.login(username, password)

    def _read_mail_from_id(self, mailid):
        mailid = mailid.decode("utf-8")
        typ, data = self.session.fetch(mailid, 'RFC822')
        content = data[0][1]
        # res = {}
        msg = email.message_from_bytes(content)
        return msg

    def iter_unseen(self):
        self.session.select("INBOX")
        unseen = self.session.search(None, "UnSeen")
        unseen_list = unseen[1][0].split()
        for emailid in unseen_list:
            yield Email_Received(self._read_mail_from_id(emailid))


class EmailToSend():
    def __init__(self, subject, sender, to):
        self.msg = email.mime.multipart.MIMEMultipart()
        self.sender = sender
        self.receiver = to
        self.msg['From'] = sender
        self.msg['To'] = to
        self.msg['Subject'] = subject

    def attach_text(self, text):
        self.msg.attach(email.mime.text.MIMEText(text, _charset='utf-8'))
    
    def attach_html(self, text):
        self.msg.attach(email.mime.text.MIMEText(text, 'html', _charset='utf-8'))

    def attach_file(self, fn, data):
        if check_contain_chinese(fn):
            att = email.mime.base.MIMEBase('application', 'octet-stream')
            att.set_payload(data)
            att.add_header('Content-Disposition', 'attachment',
                           filename=('gbk', '', fn))
            email.encoders.encode_base64(att)
        else:
            att = email.mime.text.MIMEText(data, 'base64', 'utf-8')
            att['Content-Type'] = 'application/octet-stream'
            att['Content-Disposition'] = 'attachment; filename="{0}"'.format(
                fn)
        self.msg.attach(att)
    
    def attach_img(self, data, cid):
        att = email.mime.image.MIMEImage(data)
        att.add_header('Content-ID', "<{}>".format(cid))
        self.msg.attach(att)

    def to_string(self):
        return self.msg.as_string()

    def to_bytes(self):
        return self.msg.as_bytes()


class EmailSender():

    def __init__(self, host, username, password, port=0, ssl=True):
        if ssl:
            self.session = smtplib.SMTP_SSL(host, port=port)
        else:
            self.session = smtplib.SMTP(host, port=port)
        self._login(username, password)

    def _login(self, username, password):
        self.session.login(username, password)

    def sendmail(self, email):
        if isinstance(email, EmailToSend):
            self.session.sendmail(email.sender, email.receiver,
                                  email.to_bytes())
        else:
            raise TypeError("not an email")
