import os
import queue
import gevent.monkey
gevent.monkey.patch_all()

from http import client as httpconn

def get_ready_to_write(path):
    os.makedirs(path, exist_ok=True)

class DownloadTask():
    def __init__(self, uri, fn):
        self.uri = uri
        self.fn = fn

class DownloadDispatcher():
    def __init__(self, count, host, retry_count):
        self.taskqueue = queue.Queue()
        self.pool = gevent.pool.Pool(count)
        self.retry_count = retry_count
        for _ in range(count):
            wkr = DownloadWorker(host)
            self.pool.apply_async(wkr.monitor, args=(self.taskqueue, ))

    def join(self):
        self.taskqueue.join()

    def dispatch(self, uri, fn):
        task = DownloadTask(uri, fn)
        self.taskqueue.put((task, self.retry_count))


class DownloadWorker():
    def __init__(self, host):
        self.host = host
        self.reset_connnection()
        self.is_busy = False

    def reset_connnection(self):
        self.conn = httpconn.HTTPConnection(self.host)

    def monitor(self, queue):
        while True:
            self.is_busy = False
            task, retry_count = queue.get()
            self.is_busy = True
            try:
                if retry_count == 0:
                    print(
                        "Failed to download", task.fn,
                        ". Giving up. Maybe you should set a lower down_thread."
                    )
                else:
                    print("Download:", task.fn)
                    self.download(task.uri, task.fn)
            except Exception as e:
                print("Failed to download", task.fn, ". Remaining attempts:",
                      retry_count)
                print(e)
                self.reset_connnection()
                queue.put((task, retry_count - 1))
            finally:
                queue.task_done()

    def download(self, uri, fn):
        get_ready_to_write(fn[:fn.rindex("/")])
        self.conn.request("GET", uri)
        with open(fn, "wb") as f:
            resp = self.conn.getresponse()
            if resp.status != 200:
                print("Req failed:" + str(resp.status) + " " + uri)
            f.write(resp.read())
