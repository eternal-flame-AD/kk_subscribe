from http.client import HTTPSConnection, HTTPConnection
import datetime
import os
import urllib.parse
from PIL import Image
import bs4
import copy

import emailhandler

SUBSCRIBED_COMICS = [
    173,
    873,
    359,
    1227,
    991,
]
MAIL_SENDER = os.environ.get("MAIL_SENDER")
SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_USERNAME = os.environ.get("SMTP_USERNAME")
SMTP_PASSWD = os.environ.get("SMTP_PASSWD")
SUBSCRIBER = [
    "ef@eternalflame.cn",
]
TODAY = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).date()
DELTA_DAY_THRES = 1
RETRY_COUNT = 5
TITLE_FORMAT_STRING = "{issue} - 来自你关注的漫画 {title}"
HTML_FORMAT_STRING = '''
<h1>{title} - {issue}</h1>
<img src="cid:mhcontent"></img>
'''


def download_data(host, uri, https=True):
    count = RETRY_COUNT
    while count > 0:
        try:
            if https:
                conn = HTTPSConnection(host, timeout=10)
            else:
                conn = HTTPConnection(host, timeout=10)
            conn.request("GET", uri, headers={"User-Agent": "XMLHttpRequest"})
            res = conn.getresponse().read()
            assert len(res > 5000)
            break
        except:
            count -= 1
    return res


def concat_image(images):
    images = map(Image.open, images)
    images_ = copy.deepcopy(images)
    widths, heights = zip(*(i.size for i in images))
    total_height = sum(heights)
    max_width = max(widths)
    new_im = Image.new('RGB', (max_width, total_height))
    y_offset = 0
    for im in images_:
        new_im.paste(im, (0, y_offset))
        y_offset += im.size[1]
    new_im.save('result.jpg')


def send_comic(title, issue):
    uri = issue[1]
    response = bs4.BeautifulSoup(
        download_data("www.kuaikanmanhua.com", uri), "html5lib")
    imglist = response.find("div", class_="comic-imgs").find_all("img")
    imgs = []
    for i in range(len(imglist)):
        src = imglist[i]['data-kksrc']
        with open("img/{}.jpg".format(i), mode="wb") as f:
            print(src)
            f.write(
                download_data(
                    urllib.parse.urlparse(src).netloc,
                    src,
                    https=urllib.parse.urlparse(src).scheme == "https"))
        imgs.append("img/{}.jpg".format(i))
    concat_image(imgs)
    email = emailhandler.EmailToSend(
        TITLE_FORMAT_STRING.format(title=title, issue=issue[0]), MAIL_SENDER,
        ','.join(SUBSCRIBER))
    email.attach_html(HTML_FORMAT_STRING.format(title=title, issue=issue[0]))
    email.attach_img(open("./result.jpg", mode="rb").read(), "mhcontent")
    sender = emailhandler.EmailSender(SMTP_HOST, SMTP_USERNAME, SMTP_PASSWD)
    sender.sendmail(email)


def get_comic_data(id):
    uri = "/web/topic/{}/".format(id)
    response = bs4.BeautifulSoup(
        download_data("www.kuaikanmanhua.com", uri), "html5lib")
    mh_title = response.find("div", class_="comic-name").get_text(strip=True)
    res = []
    table = response.find("table", class_="table")
    year = TODAY.year
    last_date = ""
    for row in table.find_all("tr"):
        cols = row.find_all("td")
        title = cols[1].find("a")['title']
        link = cols[1].find("a")['href']
        date = cols[3].get_text(strip=True)

        # process year
        if last_date and (date > last_date):
            year -= 1
        last_date = date
        date = date + "-" + str(year)

        date = datetime.datetime.strptime(date, r"%m-%d-%Y").date()
        datedelta = (TODAY - date).days
        res.append((title, link, datedelta))
    return mh_title, res


for comic in SUBSCRIBED_COMICS:
    title, data = get_comic_data(comic)
    for issue in data:
        if issue[2] <= DELTA_DAY_THRES:
            send_comic(title, issue)
