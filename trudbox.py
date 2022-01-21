from threading import Thread
from itertools import cycle
from io import BytesIO
from time import sleep

import pandas as pd
from PIL import Image
from captcha_solver import BalanceTooLow, CaptchaServiceError, CaptchaSolver, SolutionTimeoutError
from selenium.webdriver import FirefoxOptions, Firefox
from selenium.common.exceptions import ElementNotInteractableException, NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
import logging

LOGGER = logging.getLogger('MAIN')
LOGGER.setLevel(logging.INFO)
consoleHandler = logging.StreamHandler()
consoleHandler.setLevel(logging.INFO)
LOGGER.addHandler(consoleHandler)
fileHandler = logging.FileHandler('log.log', encoding='utf-8', mode='a')
fileHandler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s ~ %(name)s ~ %(levelname)s: %(message)s')
fileHandler.setFormatter(formatter)
LOGGER.addHandler(fileHandler)

DF = pd.read_excel('data.xlsx', dtype={'bottom_salary': str, 'top_salary': str})
RUCAPTCHA_API = DF['rucaptcha_api'].dropna().tolist()[0]
HEADLESS = bool(DF['headless'].dropna().tolist()[0])
# HEADLESS = False
THREADS = int(DF['threads'].dropna().tolist()[0])
titles = cycle(DF['title'].dropna().tolist())
descriptions = cycle(DF['description'].dropna().tolist())
logins = cycle(DF['login'].dropna().tolist())
passwords = cycle(DF['password'].dropna().tolist())
bottom_salary = DF['bottom_salary'].dropna().tolist()[0]
top_salary = DF['top_salary'].dropna().tolist()[0]


class Trud:
    def __init__(self, i):
        self.i = str(i) + ' поток'
        LOGGER.info(f'{self.i} started ')
        opts = FirefoxOptions()
        # opts.binary_location = r'C:\Users\KIEV-COP-4\AppData\Local\Mozilla Firefox\firefox.exe'  # fix
        if HEADLESS:
            opts.add_argument('--headless')
        self.driver = Firefox(options=opts)

    def auth(self, login=None, pswrd=None):
        self.driver.get('http://trudbox.com.ua/employer/postJob')
        sleep(1)
        try:
            WebDriverWait(self.driver, 10).until(
                lambda d: self.driver.find_element_by_xpath('//*[@name="LoginForm[email]"]')).send_keys(login)
            self.driver.find_element_by_xpath('//*[@name="LoginForm[password]"]').send_keys(pswrd)
            self.driver.find_element_by_xpath('//*[@id="login-popup-submit"]').click()
            return True
        except (ElementNotInteractableException, NoSuchElementException) as error:
            LOGGER.debug(error)
            return False

    def take_captcha(self, captcha):
        LOGGER.info(f'{self.i} SOLVING CAPTCHA')
        element = self.driver.find_element_by_xpath(captcha)
        location = element.location_once_scrolled_into_view
        size = element.size
        png = self.driver.get_screenshot_as_png()
        im = Image.open(BytesIO(png))
        left = location['x']
        top = location['y']
        right = location['x'] + size['width']
        bottom = location['y'] + size['height']
        im = im.crop((left, top, right, bottom))
        im.save(f'captcha_{self.i}.png')
        try:
            solver = CaptchaSolver('rucaptcha', api_key=RUCAPTCHA_API)
            raw_data = open(f'captcha_{self.i}.png', 'rb').read()
            captcha_answer = solver.solve_captcha(raw_data, recognition_time=80)
            return captcha_answer
        except (BalanceTooLow, SolutionTimeoutError, CaptchaServiceError) as error:
            LOGGER.critical(error)
            return False

    def end(self):
        self.driver.quit()
        LOGGER.info(f'{self.i} browser closed')

    def add_vacancie(self, title, text):
        LOGGER.info(f'{self.i} {title}')
        try:
            WebDriverWait(self.driver, 30).until(
                lambda d: self.driver.find_element_by_xpath('//*[@name="VacancyForm[title]"]')).send_keys(title)
            WebDriverWait(self.driver, 10).until(
                lambda d: self.driver.find_element_by_xpath('//*/div[2]/div[1]/div[2]/div/div/div[1]/div[1]')).click()
            WebDriverWait(self.driver, 10).until(
                lambda d: self.driver.find_element_by_xpath('//*/div[2]/div[1]/div[2]/div/div/div[2]/ul/li[3]')).click()
            self.driver.find_element_by_xpath('//*[@name="VacancyForm[location][caption]"]').send_keys('Киев')
            self.driver.find_element_by_xpath('//*[@name="VacancyForm[salary][from]"]').send_keys(bottom_salary)
            self.driver.find_element_by_xpath('//*[@name="VacancyForm[salary][to]"]').send_keys(top_salary)
            WebDriverWait(self.driver, 10).until(lambda a: self.driver.find_element_by_xpath(
                '//*[@id="VacancyForm_experience_to-styler"]/div[1]/div[2]')).click()
            self.driver.find_element_by_xpath('//*[@id="VacancyForm_experience_to-styler"]/div[2]/ul/li[2]').click()
            self.driver.find_element_by_xpath('//*[@id="job-form"]/div[2]/div[2]/div/div[2]/div').send_keys(text)
            try:
                captcha_field = self.driver.find_element_by_xpath('//*[@id="VacancyForm_captcha"]')
                captcha_element = '//*[@id="post-job-captcha"]'
                solved_captcha = self.take_captcha(captcha_element)
                LOGGER.info(f'{self.i} ввод капчи')
                captcha_field.send_keys(solved_captcha)
            except NoSuchElementException:
                LOGGER.info(f'{self.i} капча не найдена')
            for _ in range(2):
                var = self.driver.find_element_by_xpath('//*[@id="job-form-submit"]').location_once_scrolled_into_view
                self.driver.find_element_by_xpath('//*[@id="job-form-submit"]').click()
            LOGGER.info(f'{self.i} ОБЪЯВЛЕНИЕ ОПУБЛИКОВАНО')
            return True
        except TimeoutException as error:
            LOGGER.info(error)
        except Exception as error:
            LOGGER.exception(error)
            return False


def main(i):
    while True:
        trud = Trud(i)
        if trud.auth(next(logins), next(passwords)):
            trud.add_vacancie(next(titles), next(descriptions))
        trud.end()


if __name__ == '__main__':
    try:
        LOGGER.info('start')
        # main(1)
        procs = []
        for i in range(1, THREADS+1):
            process = Thread(target=main, args=(i, ))
            procs.append(process)
            process.start()
        for process in procs:
            process.join()
    except Exception as error:
        LOGGER.exception(error)

