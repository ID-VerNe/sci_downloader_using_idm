# -*- coding: utf-8 -*-
"""Download paper to pdf through Scihub.
"""
import argparse
import re
import time

# import chaojiying
import os
import requests
import sys
from bs4 import BeautifulSoup
from termcolor import colored

from update_link import update_link


def get_time():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))


def STD_INFO():
    return str(get_time()) + '  ' + colored('[INFO] ', 'green')


def STD_ERROR():
    return str(get_time()) + '  ' + colored('[ERROR] ', 'red')


def STD_WARNING():
    return str(get_time()) + '  ' + colored('[WARNING] ', 'yellow')


def STD_INPUT():
    return str(get_time()) + '  ' + colored('[INPUT] ', 'blue')


PIC_ID = ''


class SciHub(object):
    def __init__(self, doi, out='.', choose_scihub_url_index=3):
        self.doi = doi
        self.out = out
        self.sess = requests.Session()
        self.check_out_path()
        self.read_available_links()
        self.choose_scihub_url_index = choose_scihub_url_index
    
    def check_out_path(self):
        if not os.path.isdir(self.out):
            os.mkdir(self.out)
    
    def read_available_links(self):
        with open(os.path.dirname(os.path.realpath(sys.argv[0])) + '/link.txt', 'r') as f:
            self.scihub_url_list = [l[:-1] for l in f.readlines()]
    
    def update_link(self, mod='c'):
        update_link(mod)
        self.read_available_links()
    
    def use_scihub_url(self, index):
        self.scihub_url = self.scihub_url_list[index]
        # print(STD_INFO() + 'Choose the available link %d: %s' % (index, self.scihub_url))
        if self.scihub_url[-3:] == "red":
            self.scihub_url = self.scihub_url.replace('red', 'tw')
    
    def download(self, idm=True, mode='doi'):
        """Download the pdf of self.doi to the self.out path.

        params:
            choose_scihub_url_index: (int)
                -1: Auto-choose the scihub urls.
                >=0: index of scihub url in scihub url links.
        """
        
        # Auto choose scihub urls.
        if self.choose_scihub_url_index == -1:
            # Check valid scihub urls
            scihub_url_index = 0
            while True:
                if scihub_url_index >= len(self.scihub_url_list):
                    print(STD_WARNING() + 'All Scihub links are invalid.')
                    print(STD_INPUT())
                    update_req = input('Would you like to update Scihub links? (y/n): ')
                    if update_req == 'y':
                        self.update_link(mod='c')
                        self.download()
                    elif update_req == 'n':
                        return print(STD_INFO() + "Please manually update Scihub links by $scidownl -u")
                
                self.use_scihub_url(scihub_url_index)
                scihub_paper_url = '%s/%s' % (self.scihub_url, str(self.doi))
                res = self.sess.get(scihub_paper_url, stream=True)
                if res.text in ['\n', ''] or res.status_code in [429, 404]:
                    print(STD_ERROR() + "Current Scihub link is invalid, changing another link...")
                    scihub_url_index += 1
                else:
                    break
        else:
            self.use_scihub_url(self.choose_scihub_url_index)
            scihub_paper_url = '%s/%s' % (self.scihub_url, str(self.doi))
            res = self.sess.get(scihub_paper_url, stream=True)
        print(STD_INFO() + '连接状态：' + str(res))
        if self.is_captcha_page(res) or res.headers['Content-Type'] == 'application/pdf':
            pdf = {
                'pdf_url': scihub_paper_url,
                'title': self.check_title(self.doi)
            }
            print(STD_INFO() + colored('PDF连接', attrs=['bold']) + " -> \t%s" % (pdf['pdf_url']))
            print(STD_INFO() + colored('文章标题', attrs=['bold']) + " -> \t%s" % (pdf['title']))
        else:
            pdf = self.find_pdf_in_html(res.text)
        
        if pdf == 0:
            f = open('temp/数据库中没有的文献.txt', mode='a+')
            f.write(self.doi)
            f.close()
            print(STD_WARNING() + '没有这篇论文，写入文件：数据库中没有的文献.txt')
            return 0
        else:
            self.download_pdf(pdf, idm=idm, mode=mode)
        # try:
        #     pdf = self.find_pdf_in_html(res.text)
        #     self.download_pdf(pdf)
        # except:
        #     print(STD_ERROR() + "Failed to access the article.")
    
    def find_pdf_in_html(self, html):
        """Find pdf url and title in a scihub html

        params:
            html: (str) scihub html in string format.

        returns:
            (dict) {
                'pdf_url': (str) real url of the pdf.
                'title': (str) title of the article.
            }
        """
        f = open('temp/html.txt', mode='w', encoding='utf-8')
        f.write(html)
        f.close()
        html_not_in = ['статья не найдена в базе', 'статья не найдена / article not found',
                       'Unfortunately, Sci-Hub doesn\'t have the requested document', '未收录本论文']
        pdf = {}
        soup = BeautifulSoup(html, 'lxml')
        for not_in in html_not_in:
            if not_in in html:
                return 0
        
        # if self.choose_scihub_url_index == 1 :
        #     pdf_url = soup.find_all('iframe')[0]['src']
        # elif self.choose_scihub_url_index == 3 :
        #     pdf_url = soup.find_all('embed')[0]['src']
        
        try:
            pdf_url = soup.find_all('iframe')[0]['src']
        except:
            try:
                pdf_url = soup.find_all('embed')[0]['src']
            except:
                print(STD_ERROR() + '无法找到PDF链接，请检查scihub链接是否失效')
        
        pdf['pdf_url'] = pdf_url.replace('https', 'http') if 'http' in pdf_url else 'http:' + pdf_url
        if '//' in pdf['pdf_url']:
            pass
        else:
            pdf['pdf_url'] = pdf['pdf_url'].replace(':/', '://')
        
        title = ' '.join(self._trim(soup.title.text.split('|')[1]).split('/')).split('.')[0]
        title = title if title else pdf['pdf_url'].split('/')[-1].split('.pdf')[0]
        pdf['title'] = self.check_title(title)
        print(STD_INFO() + colored('PDF真实链接', attrs=['bold']) + " -> \t%s" % (pdf['pdf_url']))
        print(STD_INFO() + colored('文章标题', attrs=['bold']) + " -> \t%s" % (pdf['title']))
        return pdf
    
    def check_title(self, title):
        """Check title to drop invalid characters.

        params:
            title: (str) original title.

        returns:
            (str) title that drops invalid chars.
        """
        rstr = r"[\/\\\:\*\?\"\<\>\|]"  # / \ : * ? " < > |
        new_title = re.sub(rstr, " ", title)[:200]
        return new_title
    
    def download_pdf(self, pdf, idm=True, mode='doi'):
        """Download the pdf by given a pdf dict.

        params:
            pdf: (dict) {
                'pdf_url': (str) real url of the pdf,
                'title': (str) title of the article
            }
        """
        pdf['title'] = pdf['title'].replace(' ', '')
        pdf['title'] = pdf['title'].replace(' ', '')
        pdf['title'] = pdf['title'].replace(' ', '')
        pdf['title'] = pdf['title'].replace('ã', 'a')
        pdf['title'] = pdf['title'].replace('ç', 'c')
        pdf['title'] = pdf['title'].replace('\n', '')
        pdf['title'] = pdf['title'].replace('\?', '_')
        pdf['title'] = pdf['title'].replace('\?', '_')
        pdf['title'] = pdf['title'].replace('\/', '_')
        pdf['title'] = pdf['title'].replace('\\', '_')
        pdf['title'] = pdf['title'].replace('\*', '_')
        pdf['title'] = pdf['title'].replace('\|', '_')
        pdf['title'] = pdf['title'].replace('\"', '_')
        pdf['title'] = pdf['title'].replace('\:', '_')
        pdf['title'] = pdf['title'].replace('\<', '_')
        pdf['title'] = pdf['title'].replace('\>', '_')
        if idm:
            use_idm_download(pdf['pdf_url'], pdf['title'], doi=self.doi, mode=mode)
        else:
            res = self.sess.get(pdf['pdf_url'], stream=True)
            
            if self.is_captcha_page(res):
                print(STD_WARNING() + '被验证码拦截:%s，已写入记录文件：被验证码拦截的文献.txt ' % self.doi)
                out = open('temp/被验证码拦截的文献.txt', 'a+')
                out.write(self.doi)
                out.close()
                return 0
            
            retry_times = 0
            while 'Content-Length' not in res.headers and retry_times < 10:
                print('\r' + STD_INFO() + "Retrying...", end="")
                res.close()
                res = self.sess.get(pdf['pdf_url'], stream=True)
                retry_times += 1
            tot_size = int(res.headers['Content-Length']) if 'Content-Length' in res.headers else 0
            out_file_path = os.path.join(self.out, pdf['title'] + '.pdf')
            downl_size = 0
            with open(out_file_path, 'wb') as f:
                for data in res.iter_content(chunk_size=1024, decode_unicode=False):
                    f.write(data)
                    downl_size += len(data)
                    if tot_size != 0:
                        perc = int(downl_size / tot_size * 100)
                        perc_disp = colored('[%3d%%] ' % (perc), 'green')
                    else:
                        perc_disp = colored(STD_INFO())
                    print("\r{0}下载进度: {1} / {2}".format(perc_disp, downl_size, tot_size), end='')
            print('\n' + STD_INFO() + "下载完成".ljust(50))
    
    def is_captcha_page(self, res):
        """Check if the result page is a captcha page."""
        f = open('temp/headers.txt', mode='w+', encoding='utf-8')
        f.write(str(res.headers))
        f.close()
        return 'must-revalidate' in res.headers['Cache-Control']
        # return res.headers['Content-Type'] == "text/html; charset=UTF-8"
    
    def _trim(self, s):
        """Drop spaces located in the head or the end of the given string.
        """
        if len(s) == 0:
            return s
        elif s[0] == ' ':
            return self._trim(s[1:])
        elif s[-1] == ' ':
            return self._trim(s[:-1])
        else:
            return s


def use_idm_download(down_url, title, doi, mode='doi',
                     down_path=os.path.dirname(os.path.realpath(sys.argv[0])) + '\\paper'):
    if mode == 'title':
        output_filename = title + '.pdf'
    elif mode == 'doi':
        output_filename = doi.replace(' ', '_')
        output_filename = output_filename.replace('\\', '_')
        output_filename = output_filename.replace('.', '_')
        output_filename = output_filename.replace('/', '_')
        output_filename = output_filename.replace('\n', '')
        output_filename = output_filename + '.pdf'
    
    IDM = r'IDMan.exe'
    command = IDM + ' /d \"' + down_url + '\" /p \"' + down_path + '\" /f \"' + output_filename + '\" /n '
    # command = ' '.join([IDM, '/d', down_url, '/p', down_path, '/f', output_filename, '/a', '/s'])
    print(STD_INFO() + '调用IDM下载')
    print(STD_INFO() + '执行命令：' + str(command))
    os.system(command)
    print(STD_INFO() + '写入记录文件：IDM下载.csv')
    save_str = output_filename + ',' + down_url + ',' + command + '\n'
    append_to_file('temp/IDM下载.csv', save_str)


def append_to_file(path, str):
    if os.path.exists(path) == False:
        print(STD_INFO() + '创建文件：%s' % path)
        open(path, mode='w')
    f = open(path, mode='a+')
    f.write(str)
    f.close()


def write_to_file(path, str):
    f = open(path, mode='w')
    f.write(str)
    f.close()


def chech_path():
    if os.path.exists('./paper') == False:  #
        os.makedirs('./paper')
    if os.path.exists('./temp') == False:  #
        os.makedirs('./temp')
    if os.path.exists('temp/已完成.txt') == False:
        print(STD_INFO() + '创建历史记录文件：已完成.txt')
        open('temp/已完成.txt', mode='w')
    if os.path.exists('temp/数据库中没有的文献.txt') == False:
        print(STD_INFO() + '创建历史记录文件：数据库中没有的文献.txt')
        open('temp/数据库中没有的文献.txt', mode='w')
    if os.path.exists('temp/失败.txt') == False:
        print(STD_INFO() + '创建历史记录文件：失败.txt')
        open('temp/失败.txt', mode='w')
    if os.path.exists('temp/headers.txt') == False:
        print(STD_INFO() + '创建历史记录文件：headers.txt')
        open('temp/headers.txt', mode='w')
    if os.path.exists('temp/html.txt') == False:
        print(STD_INFO() + '创建历史记录文件：html.txt')
        open('temp/html.txt', mode='w')
    if os.path.exists('temp/IDM下载.csv') == False:
        print(STD_INFO() + '创建历史记录文件：IDM下载.csv')
        open('temp/IDM下载.csv', mode='w')


def read_line(path):
    content = []
    f = open(path)
    line = f.readline()
    while line:
        content.append(line)
        line = f.readline()
    f.close()
    return content


def stop_and_sleep(stop, times=30, wait_time=20):
    if stop % times == times - 1:
        for wait in range(wait_time):
            print('\r' + STD_INFO() + '休息一下，{0}秒后继续'.format(wait_time - wait), end='')
            time.sleep(1)
        print('\n')


def scihub_down(doi, i, stop, retry_or_not, retry_max_time, sleep_time_0, idm=True, choose_scihub_url_index=3,
                mode='doi'):
    cont_or_not = False
    stop_and_sleep(stop)
    if retry_or_not == True:
        attemp = 1
        success = False
        retry_max_time = retry_max_time
        sleep_time = sleep_time_0
        cont_or_not = False
        while success == False:
            try:
                SciHub(doi, 'paper', choose_scihub_url_index=choose_scihub_url_index).download(idm=idm, mode=mode)
                success = True
                attemp = 1
                sleep_time = sleep_time_0
            except Exception as ret:
                print(STD_ERROR(), ret)
                if attemp == retry_max_time + 1:
                    print(STD_WARNING() + '超过最大重试次数，程序继续，本篇写入文件：失败.txt')
                    if os.path.exists('temp/失败.txt') == False:
                        print(STD_INFO() + '创建失败记录文件：失败.txt')
                        open('temp/失败.txt', mode='w')
                    append_to_file('temp/失败.txt', doi)
                    cont_or_not = True
                    success = True
                    continue
                time.sleep(1)
                print(STD_ERROR() + '出现错误')
                for j in range(sleep_time):
                    print('\r{0}等待{1}秒后进行第{2}次异常重试'.format(STD_ERROR(), sleep_time - j, attemp), end='')
                    time.sleep(1)
                attemp += 1
                sleep_time += 10
                time.sleep(1)
                print('\n' + '-' * 30)
    else:
        SciHub(doi, 'paper', choose_scihub_url_index=choose_scihub_url_index).download(idm=idm, mode=mode)
    if cont_or_not:
        print(STD_WARNING() + '第%s篇下载失败，记录写入完成。' % (i + 1))
    else:
        print(STD_INFO() + '已完成第%s篇，记录写入完成。' % (i + 1))
    print('-' * 30)
    append_to_file('temp/已完成.txt', doi)
    i = i + 1
    # time.sleep(10)
    stop += 1
    return i, stop, retry_or_not


def main(path=r'./doi.txt', retry_or_not=True, sleep_time_0=30, retry_max_time=5, idm=True, choose_scihub_url_index=3,
         mode='doi'):
    global cont_or_not
    chech_path()
    path = path
    test_dois = read_line(path)
    finish = read_line('temp/已完成.txt')
    i = 0
    stop = 0
    for doi in test_dois:
        if doi in finish:
            i = i + 1
            print(STD_INFO() + '第%s篇已经下载完成，进入下一篇' % i)
            continue
        i, stop, retry_or_not = scihub_down(doi, i, stop, retry_or_not, retry_max_time, sleep_time_0, idm=idm,
                                            choose_scihub_url_index=choose_scihub_url_index, mode=mode)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='manual to this script')
    parser.add_argument('-p', '--p', type=str, default=r'./doi.txt')
    parser.add_argument('-rn', '--rn', type=int, default=1)
    parser.add_argument('-sr', '--st', type=int, default=30)
    parser.add_argument('-rt', '--rt', type=int, default=5)
    parser.add_argument('-i', '--i', type=int, default=1)
    parser.add_argument('-sci', '--sci', type=int, default=1)
    parser.add_argument('-m', '--m', type=int, default=1)
    args = parser.parse_args()
    if args.m == 1:
        args.m = 'doi'
    else:
        args.m = 'title'
    if args.rn == 1:
        args.rn = True
    else:
        args.rn = False
    if args.i == 1:
        args.i = True
    else:
        args.i = False
    print(args.p, type(args.p))
    print(args.rn, type(args.rn))
    print(args.st, type(args.st))
    print(args.rt, type(args.rt))
    print(args.i, type(args.i))
    main(path=args.p, retry_or_not=args.rn, sleep_time_0=args.st,
         retry_max_time=args.rt, idm=args.i, choose_scihub_url_index=args.sci, mode=args.m)
