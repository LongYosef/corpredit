# -*- coding: utf-8 -*-
"""
@Date     :2018/04/18
@Author   : Yosef
@Software :anaconda3
"""

import time
import random
import json

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException

import cv2
import numpy as np
from io import BytesIO
from PIL import Image
import matplotlib.pyplot as plt

import requests
from hashlib import md5
from lxml import etree
from copyheaders import headers_raw_to_dict



class SearchResultParse(object):
    
    '''查询结果页解析
    '''
    def __init__(self,pagesource,base_url,parse_rule):
        self.selector=etree.HTML(pagesource)
        self.url_list=[]
        self.base_url=base_url
        self.parse_rule=parse_rule['search_result_url']
           
    def search_result_parse(self):
        self.url_list=[self.base_url+i for i in self.selector.xpath(self.parse_rule)]
        return self.url_list

class PageDetailParse(object):
    
    '''详情页解析
    '''
    def __init__(self,pagesource,parse_rule):
        self.selector=etree.HTML(pagesource)
        self.parse_rule=parse_rule
        self.info_list={}
           
    def search_result_parse(self,primary_info=None):
        if primary_info is None:
            primary_info=[]
        for i in self.parse_rule['primaryinfo']:
            primary_info.append(self.selector.xpath(i).replace("\n","").replace("\t","").replace("\r","").replace(" ",""))
        self.info_list['primary_info']=primary_info
        return self.info_list    


class CookieRequest(object):
    '''带cookie访问查询结果
    '''
    def __init__(self,cookies,url_list=None,headers=None):
        '''设置requests中的session的cookie
        '''
        self.cookie=json.loads(cookies)
        self.url_list=url_list
        self.session=requests.Session()
        self.ckjar=requests.utils.RequestsCookieJar()
        self.result=[]
        self.headers=headers
        for i in self.cookie:
            self.ckjar.set(i['name'],i['value'])
        self.session.cookies.update(self.ckjar)
        
    def cookie_requests(self):
        '''带cookie依次访问各个查询结果
        '''
        for url in self.url_list:
            response=self.session.get(url=url,headers=self.headers)
            self.result.append(response.text)
            time.sleep(5)
        return self.result
        
    


class MaxEnterError(Exception):
    '''输入关键字最大尝试次数
    '''
    def __init__(self,ErrorInfo):
        super().__init__(self) #初始化父类
        self.errorinfo=ErrorInfo
    def __str__(self):
        return self.errorinfo


class GtClickShot(object):

    def __init__(self, username, password):
        
        '''初始化超级鹰
        softid已固化到程序
        args:
            username(str):超级鹰普通用户名
            password(str):超级鹰密码
        '''
        self.username = username
        self.password = md5(password.encode("utf-8")).hexdigest()
        self.base_params = {
            'user': self.username,
            'pass2': self.password,
            'softid': '895210',
        }
        self.headers = {
            'Connection': 'Keep-Alive',
            'User-Agent': 'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 5.1; Trident/4.0)',
        }

    def PostPic(self, im, codetype):
        
        """发送图片至打码平台
        args：       
            im(Byte): 图片字节
            codetype(str): 题目类型 参考 http://www.chaojiying.com/price.html
        return(json):返回打码信息，包含坐标信息，坐标信息用“|”隔开
        """
        params = {
            'codetype': codetype,
        }
        params.update(self.base_params)
        files = {'userfile': ('ccc.jpg', im)}
        r = requests.post('http://upload.chaojiying.net/Upload/Processing.php', data=params, files=files, headers=self.headers)
        return r.json()

    def ReportError(self, im_id):
        """识别错误返回题分
        args：
            im_id(str):报错题目的图片ID
        return(str):报错反馈
        """
        params = {
            'id': im_id,
        }
        params.update(self.base_params)
        r = requests.post('http://upload.chaojiying.net/Upload/ReportError.php', data=params, headers=self.headers)
        return r.json()



class CorpSearch(object):
    def __init__(self,init_url,index_url,headers,max_click):
        
        '''初始化
        args:
            init_url:初始化url,加速乐反爬JS要求访问目标网站前需先访问初始化url获取gt和challenge
            index_url:目标网站首页url
            headers：请求头信息
            max_click：最大循环点击次数为了应对点击不灵敏，设置循环检查点击。
            self.wait:默认条件等待最大时间
            self.click_valitimes:点击验证次数，大于0时需返回题分，等于0时不需要
        '''
        self.init_url=init_url
        self.index_url=index_url
        self.driver=webdriver.Chrome()
        self.wait=WebDriverWait(self.driver,50)
        self.max_entertimes=max_click
        self.click_valitimes=0
        self.action=ActionChains(self.driver)
        self.gt_shot=GtClickShot("xxx","xxxxxx")
        self.options=webdriver.ChromeOptions()
        self.headers=headers
        for option in self.headers:
            self.options.add_argument(option)
    

    #初始化页面，绕过过加速乐反爬，获取gt和challenge,并加载进入首页
    def init(self):
        
        '''
        请求初始化网站，并进入首页
        '''
        self.driver.get(self.init_url)
        self.driver.get(self.init_url)
        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR,"body > pre:nth-child(1)")))
        self.driver.get(self.index_url)

    #加载首页，输入查询关键词，点击查询按钮
    #如果点击按钮失效,自动重新回车，并设定最大回车次数，一旦超过设定值，抛出异常，结束程序
    def input_query(self,keyword):
        
        '''输入关键词进行查询
        args:
            keyword:查询关键词
        return:
            仅用于方法返回
        '''
        enter_word=self.wait.until(EC.presence_of_element_located((By.ID,"keyword")))
        self.wait.until(EC.presence_of_element_located((By.ID,"btn_query")))
        time.sleep(random.randint(8,15)/10)
        enter_word.send_keys(keyword)
        time.sleep(random.randint(5,10)/10)
        enter_word.send_keys(Keys.ENTER)
        while True:
            if self.max_entertimes==0:
                raise MaxEnterError('---Out of max times on the search enter---')
            gt_panel=self.driver.find_element_by_css_selector("body > div.geetest_panel.geetest_wind")
            style_value=gt_panel.value_of_css_property("display")
            if style_value.strip() == "block":
                break
            else:
                enter_word.send_keys(Keys.ENTER)
                time.sleep(random.randint(1,5)/10)
                self.max_entertimes-=1
        return
        
        
    #判断页面中是否包含某个元素，注意是class_name
    def is_element_exist(self,class_name):
        
        '''判断某个元素是否存在
        args:
            class_name:元素class属性名称
        return:
            存在(True),不存在(False)
        '''
        
        try:
            self.driver.find_element_by_class_name(class_name)
            return True
        except:
            return False
        
    #屏幕截图，并将截图内容读入内存，加速计算操作 
    def get_screenshot(self):
        
        '''屏幕截图
        return:
            返回截图
        '''
        
        screenshot=self.driver.get_screenshot_as_png()
        screenshot=Image.open(BytesIO(screenshot))
        return screenshot
    
    #获取验证验证码图片的位置，用于裁图
    def get_position(self,pos_img):
        
        '''验证图片的坐标尺寸信息
        args:
            pos_img:验证码定位点元素
        return:
            验证码定位点的坐标信息，注意依次为：左底，左高，右高，右底
        '''
        
        location=pos_img.location
        size=pos_img.size
        top,bottom,left,right=location['y'],location['y']+size['height'],location['x'],location['x']+size['width']
        return (left,top,right,bottom)

    #对于滑块验证码，获取完整的和缺块的验证码图片截图
    def get_slide_images(self):
        
        '''获取有缺口和没缺口的图片
        '''
        canvas_img=self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR,".geetest_canvas_img.geetest_absolute > div")))
        position=self.get_position(canvas_img)
        befor_screenshot=self.get_screenshot()
        befor_img=befor_screenshot.crop(position)
        befor_img.save("befor_click.png")
        
        btn_slide=self.wait.until(EC.presence_of_element_located((By.CLASS_NAME,"geetest_slider_button")))
        self.action.click_and_hold(btn_slide).perform()
        after_screenshot=self.get_screenshot()
        after_img=after_screenshot.crop(position)
        after_img.save("after_click.png")
    
    #获取缺口位置，计算滑动距离（灰度化，求差值，阈值去燥，计算缺口位置，计算滑动距离）
    def get_slide_distance(self):
        
        '''获取滑动距离
        return:
            返回滑动距离
        '''
        
        befor_click_img="D:\\Anaconda3\\Lib\\captcha\\gt_validate\\befor_click.png"
        after_click_path="D:\\Anaconda3\\Lib\\captcha\\gt_validate\\after_click.png"
        befor_img=cv2.imread(befor_click_img)
        after_img=cv2.imread(after_click_path)

        befor_gray=cv2.cvtColor(befor_img,cv2.COLOR_BGR2GRAY)
        after_gray=cv2.cvtColor(after_img,cv2.COLOR_BGR2GRAY)
        img_diff=np.array(befor_gray)-np.array(after_gray)

        height,width=img_diff.shape

        for i in range(height):
            for j in range(width):
                if img_diff[i][j]>245 or img_diff[i][j] < 60 :
                    img_diff[i][j]=0
    
        start_position=random.choice([4,5,6])
        reshape_img=img_diff.T
        sum_color=list(map(lambda x:sum(x),reshape_img))
        for i in range(1,len(sum_color)):
            if sum_color[i]>1000 and i>60:
                end_position=i
                break
            
        slide_distance=end_position-start_position
        return slide_distance
   
    #模拟鼠标轨迹，按照开始慢加速（2），中间快加速（5），后面慢加速（2），最后慢减速的方式（1）
    #返回值是x值与Y值坐标以及sleep时间截点，起始中间最后都要sleep
    def get_track(self,distance,track_list=None):
        
        '''获取滑动轨迹
        args:
            distance:滑动距离
        kargs:
            Track_list:滑动轨迹，初始化为空
        return:
            滑动轨迹，断点位置(2处)
        '''
        
        if track_list is None:
            track_list=[]
        base=distance/10
        x1=round(base*2)
        x2=round(base*5)
        x3=x1
        x4=distance-x1-x2-x3
        ynoise_num=random.randint(5,10)
        y1=[random.randint(-2,2) for _ in range(ynoise_num)]
        yrdm=list(set(random.choice(range(distance)) for _ in range(ynoise_num)))
        x=[1]*distance
        y=[0]*distance
        for i,j in enumerate(yrdm):
            y[j]=y1[i]
        t1=sorted([random.randint(8,13)/1000 for _ in range(x1)],reverse=True)
        t2=sorted([random.randint(1,8)/1000 for _ in range(x2)],reverse=True)
        t3=sorted([random.randint(8,13)/1000 for _ in range(x3)],reverse=True)
        t4=sorted([random.randint(12,20)/1000 for _ in range(x4)])
        t=t1+t2+t3+t4

        for i in(zip(x,y,t)):
            track_list.append(i)
        return (track_list,x1+x2,x1+x2+x3)
    
    #对于点击验证码，获取验证码的校验文字和待点击图片截图,以及验证码弹框元素
    def get_click_images(self):
        
        '''获取需点击的图片
        return: 
            需点击坐标的图片，
            提示图片(用于调试打码时的计算点击次数)，  
            验证码图片定位元素(用于定位鼠标位置并计算相对坐标)
        '''
        
        click_img_element=self.wait.until(EC.presence_of_element_located((By.CLASS_NAME,"geetest_widget")))
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME,"geetest_item_img")))
        time.sleep(random.randint(1,5)/10)
        click_position=self.get_position(click_img_element)
        all_screenshot=self.get_screenshot()
        click_img=all_screenshot.crop(click_position)
        click_img.save("click_img.png")
    
        tip_img=self.wait.until(EC.presence_of_element_located((By.CLASS_NAME,"geetest_tip_img")))
        tip_position=self.get_position(tip_img)
        tip_img=all_screenshot.crop(tip_position)
        tip_img.save("tip_img.png")
        
        return(click_img,tip_img,click_img_element)
    
     
    #计算要点击的字符数量，灰度化，反向二值化,转置，沿X坐标对Y求和，判断分割点数量，判断字符数量
    def cal_char_num(self,char_img_path):
        
        '''计算需点击的字符数量
        args:
            char_img_path:提示图片的存储路径
        return:
            点击次数
        '''
        
        flag=0
        origin_img=cv2.imread(char_img_path)
        gray_img=cv2.cvtColor(origin_img,cv2.COLOR_BGR2GRAY)
        ret,thresh1=cv2.threshold(gray_img,127,255,cv2.THRESH_BINARY_INV)
        transpos_img=np.array(thresh1).T
        result=list(map(lambda x: sum(x),transpos_img))
        for i in range(len(result)-3):
            if result[i]==0 and result[i+1]==0 and result[i+2]>0:
                flag+=1     
        return flag
    
    #返回验证码字符的坐标，每个点击点的坐标,并转化为整数坐标
    def char_absolute_coord(self,img,num,coord=None):
        
        '''调试用，点击验证码图片返回整数值坐标
        args:
            img:验证码图片
            num：点击次数
        kargs:
            coord:验证码字符坐标    
        return:
            字符坐标
        '''
        if coord is None:
            coord=[]
        img=Image.open(img)
        plt.imshow(img)
        points=plt.ginput(num)
        plt.close()
        for i in points:
            x_co,y_co=i
            coord.append((round(x_co),round(y_co)))
        return coord
    
    #返回从起点开始依次到每个点击文字的相对位置，形式为[(xoffset,yoffset),(),(),...]
    def get_offset_coord(self,absolute_coord,click_track=None):
        
        '''获取相邻点击字符的相对坐标，用于鼠标移动点击
        args:
            absolute_coord：验证码字符的绝对坐标
        kargs:
            click_track:每个需点击字符间的相对坐标或位移
        return:
            相对坐标或位移
        '''
        
        if click_track is None:
            click_track=[]
        for i,j in enumerate(absolute_coord):
            if i == 0:
                click_track.append(j)
            else:
                click_track.append((j[0]-absolute_coord[i-1][0],j[1]-absolute_coord[i-1][1]))
        return click_track
        
    #验证点击验证码,获取验证码数量，人工点击，按照计算的坐标相对偏移位置，依次点击文字进行验证
    #通过打码平台，将验证码图片发送后返回坐标信息，通过超级鹰打码平台
    def click_captcha_validate(self):
        
        '''根据打码平台返回的坐标进行验证
        
        return:
            仅仅用于方法返回
        '''
        click_img,tip_img,click_img_element=self.get_click_images()
        
        bytes_array=BytesIO()
        click_img.save(bytes_array,format="PNG")
        coord_result=self.gt_shot.PostPic(bytes_array.getvalue(),"9004")
        print(coord_result)
        groups=coord_result.get("pic_str").split('|')
        if groups =="":
            raise RuntimeError("打码超时")
        pic_id=coord_result.get("pic_id")
        points=[[int(num) for num in group.split(',')] for group in groups]
        
#        tip_img_path="D:\\Anaconda3\\Lib\\captcha\\gt_validate\\tip_img.png"
#        click_img_path="D:\\Anaconda3\\Lib\\captcha\\gt_validate\\click_img.png"
        
#        num=self.cal_char_num(tip_img_path)
#        points=self.char_absolute_coord(click_img_path,num)

        mouse_track=self.get_offset_coord(points)
        print(mouse_track)
        self.action.move_to_element_with_offset(click_img_element,0,0)
        for position in mouse_track:
            self.action.move_by_offset(position[0],position[1])
            self.action.click()
            self.action.pause(random.randint(3,7)/10)
        self.action.perform()
        time.sleep(random.randint(4,6)/10)
        click_submit_btn=self.wait.until(EC.presence_of_element_located((By.CLASS_NAME,'geetest_commit_tip')))
        click_submit_btn.click()
        self.action.reset_actions()
        self.valide_process(pic_id=pic_id)
        return
            
    #验证滑动验证码，获取滑动距离和滑动轨迹，分别在起始，中间，结束时随机停顿
    def slide_captcha_validate(self):
        
        '''滑动验证码验证
        return:
            仅仅用于方法返回
        '''
        
        self.get_slide_images()
        distance=self.get_slide_distance()
        track,p1,p2=self.get_track(distance)
        time.sleep(random.randint(3,7)/10)
        for i,j in enumerate(track):
            if i==p1 or i==p2:
                time.sleep(random.randint(3,7)/10)
            self.action.move_by_offset(j[0],j[1])
            time.sleep(j[2])
        time.sleep(random.randint(3,7)/10)
        self.action.release()
        self.valide_process()
        return
    
    
    #验证是否成功破解，设置重启机制
    #超过最大验证次数需点击“点击此处重试”
    def valide_process(self,pic_id=None):
        
        '''验证过程
        1>判断极验弹框消失且查询结果框出现，验证成功，结束验证；
        2>第一步验证失败，超时；
        3>超时原因：极验验证框没消失(跳转至第4步)或查询结果框没出现(跳转至第6步)；
        4>极验验证框没消失，检验是否超过最大验证次数，如果是，需点击重试，跳至第7步，如果不是，跳至第5步；
        5>如果不是，判断验证类型，调用响应验证方法，跳至第1步；
        6>如果查询结果框没出现，直接退出关闭浏览器；
        7>点击重试时，如果是空白响应则退出浏览器，或者判断验证类型，调用响应验证方法，跳至第1步。
        args:
            cap_type:验证码类型
            pic_id:点击类验证码图片id
        return:
            要么验证成功，要么退出浏览器
        '''
        
        try:
            WebDriverWait(self.driver,3).until_not(EC.visibility_of_element_located((By.CSS_SELECTOR, "body > div.geetest_panel")))          
            WebDriverWait(self.driver,10).until(EC.visibility_of_element_located((By.ID, "advs")))
            print("Validate Successful")
            return
        except TimeoutException:
            try:
                gt_panel_error=self.driver.find_element_by_css_selector("body > div.geetest_panel.geetest_wind > div.geetest_panel_box > div.geetest_panel_error")
                error_display=gt_panel_error.value_of_css_property("display")
            
                if error_display.strip() == "block":
                    gt_panel_error_content=self.driver.find_element_by_css_selector(".geetest_panel_error > div.geetest_panel_error_content")
                    self.action.move_to_element(gt_panel_error_content).click().perform()
                    self.action.reset_actions()
                    try:
                        WebDriverWait(self.driver,3).until_not(EC.visibility_of_element_located((By.CSS_SELECTOR, "body > div.geetest_panel")))          
                        WebDriverWait(self.driver,10).until(lambda x: x.find_element_by_id('advs').is_displayed())
                        print("Validate Successful")
                        return
                    except TimeoutException:
                        self.slide_orclick_validate(pic_id)
                else:
                    self.slide_orclick_validate(pic_id)
                
            except:
                print('error occured')
                return
                
    #判断是执行点击还是滑块       
    def slide_orclick_validate(self,pic_id=None):
        
        '''判断下一步是选择滑动验证还是点击验证还是退出浏览器
        args:
            pic_id:点击类验证码图片id
        return:
            要么滑动验证，要么点击验证，要么None          
        '''
        
        try:
            WebDriverWait(self.driver,3).until(EC.presence_of_element_located((By.CLASS_NAME,"geetest_close")))
            print('Validate Failed,retry again')    
            if self.is_element_exist("geetest_canvas_img"):
                print('captcha type is slide')
                return self.slide_captcha_validate()
            else:
                print('captcha type is click')
                if self.click_valitimes > 0:
                    self.gt_shot.ReportError(pic_id)
                self.click_valitimes+=1
                return self.click_captcha_validate()       
        except:
            print("Directly no click or slide validate")
            return
    
    #带cookie切换至首页继续检索
    def switch_hmpg(self):
        
        '''由结果页切换至首页
        return: 用于方法返回
        '''
        self.wait.until(EC.presence_of_element_located((By.ID,"advs")))
        hmpg_btn=self.driver.find_element_by_css_selector("body > div.container > div.header_box > div > div > a:nth-child(1)")
        self.action.move_to_element(hmpg_btn).click().perform()
        self.action.reset_actions()
        self.wait.until(lambda x: x.find_element_by_id('btn_query').is_displayed())
        return
                
        
        
    #通过index界面或者点击首页继续检索时的爬取步骤
    def main(self,keyword,start_pg=None):
        
        '''操作主程序
        args:
            keyword:查询关键词
        kargs:
            start_pg:是否需要初始化访问加速乐，默认要
        
        '''
        
        if start_pg == "homepage":
            self.switch_hmpg()
        else:
            self.init()
        self.input_query(keyword)
        self.slide_orclick_validate()
    
    #保存cookie和检索结果，用于requests及详情解析
    def to_dict(self):
        
        '''保存cookie（用于requests请求及详情解析）和查询结果
        args:
            cookie_name:cookie文件名称
            
        '''
        cookies=self.driver.get_cookies()
        jsn_cookies=json.dumps(cookies)
        htmlpage=self.driver.page_source
        
        return {'cookies':jsn_cookies,
                'page':htmlpage
                }


if __name__=='__main__':
    
    init_url="http://www.gsxt.gov.cn/SearchItemCaptcha"
    index_url="http://www.gsxt.gov.cn/index.html"
    base_url='http://www.gsxt.gov.cn'
    result_parse_rule={'search_result_url':'//*[@id="advs"]/div/div[2]/a/@href'}
    detail_parse_rule={'primaryinfo':['string(//*[@id="primaryInfo"]/div/div[@class="overview"]/dl[{}])'.format(i) for i in range(15)],}

    max_click=10
    search_list=["百度","腾讯","阿里巴巴"]
    chm_headers=['Host="www.gsxt.gov.cn"',
                 'Connection="keep-alive"',
                 'User-Agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.94 Safari/537.36"',
                 'Upgrade-Insecure-Requests=1',
                 'Accept="text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8"',
                 'Accept-Encoding="gzip, deflate"',
                 'Accept-Language="zh-CN,zh;q=0.9"']
    rq_header=b'''Host: www.gsxt.gov.cn
                Connection: keep-alive
                Cache-Control: max-age=0
                Upgrade-Insecure-Requests: 1
                User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.94 Safari/537.36
                Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8
                Referer: http://www.gsxt.gov.cn/corp-query-search-1.html
                Accept-Encoding: gzip, deflate
                Accept-Language: zh-CN,zh;q=0.9
            '''
    rq_headers=headers_raw_to_dict(rq_header)
    
    test1=CorpSearch(init_url,index_url,chm_headers,max_click)
    test1.main(search_list[0])
    index_cookiename=md5(search_list[0].encode("utf-8")).hexdigest()+".json"
    cookie_html=test1.to_dict()
    search_result=SearchResultParse(cookie_html['page'],base_url,result_parse_rule)
    url_list=search_result.search_result_parse()
    detail_request=CookieRequest(cookie_html['cookies'],url_list=url_list,headers=rq_headers)
    detail_result=detail_request.cookie_requests()
    for pg in detail_result:
        pg_detail=PageDetailParse(pg,detail_parse_rule)
        detail=pg_detail.search_result_parse()
        print(detail)
    time.sleep(5)
    test1.driver.quit()
    
    
    

