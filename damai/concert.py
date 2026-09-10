# -*- coding: UTF-8 -*-
"""
__Author__ = "WECENG"
__Version__ = "1.0.0"
__Description__ = ""
__Created__ = 2023/10/10 17:00
"""

import os.path
import pickle
import time
from time import sleep

from selenium import webdriver
from selenium.webdriver.common.by import By
from check_environment import get_chromedriver_path


class Concert:
    def __init__(self, config):
        self.config = config
        self.status = 0  # 状态,表示如今进行到何种程度
        self.login_method = 1  # {0:模拟登录,1:Cookie登录}自行选择登录方式

        # 环境检查：自动安装/验证 ChromeDriver
        print("⏳ 正在检查 Chrome 环境...")
        try:
            chromedriver_path = get_chromedriver_path()
            print(f"✓ ChromeDriver 就绪: {chromedriver_path}\n")
        except RuntimeError as e:
            print(f"✗ 环境检查失败: {e}")
            print("\n建议运行: python damai/check_environment.py")
            exit(1)

        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_experimental_option("excludeSwitches", ['enable-automation'])
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')

        from selenium.webdriver.chrome.service import Service
        service = Service(chromedriver_path)
        self.driver = webdriver.Chrome(service=service, options=chrome_options)  # 默认Chrome浏览器

    def set_cookie(self):
        """
        :return: 写入cookie
        """
        self.driver.get(self.config.index_url)
        print("***请点击登录***\n")
        while self.driver.title.find('大麦网-全球演出赛事官方购票平台') != -1:
            sleep(1)
        print("***请扫码登录***\n")
        while self.driver.title != '大麦网-全球演出赛事官方购票平台-100%正品、先付先抢、在线选座！':
            sleep(1)
        print("***扫码成功***\n")

        # 将cookie写入damai_cookies.pkl文件中
        pickle.dump(self.driver.get_cookies(), open("damai_cookies.pkl", "wb"))
        print("***Cookie保存成功***")
        # 读取抢票目标页面
        self.driver.get(self.config.target_url)

    def get_cookie(self):
        """
        :return: 读取cookie
        """
        try:
            cookies = pickle.load(open("damai_cookies.pkl", "rb"))
            for cookie in cookies:
                cookie_dict = {
                    'domain': '.damai.cn',  # 域为大麦网的才为有效cookie
                    'name': cookie.get('name'),
                    'value': cookie.get('value'),
                }
                self.driver.add_cookie(cookie_dict)
            print('***完成cookie加载***\n')
        except Exception as e:
            print(e)

    def login(self):
        """
        :return: 登录
        """
        if self.login_method == 0:
            self.driver.get(self.config.login_url)
            print('***开始登录***\n')
        elif self.login_method == 1:
            if not os.path.exists('damai_cookies.pkl'):
                # 没有cookie就获取
                self.set_cookie()
            else:
                self.driver.get(self.config.target_url)
                self.get_cookie()

    def enter_concert(self):
        """
        :return: 打开浏览器
        """
        print('***打开浏览器，进入大麦网***\n')
        # 先登录
        self.login()
        # 移除不必要的刷新，登录后直接跳转到 target_url，无需刷新
        # self.driver.refresh()  # 已移除：浪费时间，可能导致状态丢失
        # 标记登录成功
        self.status = 2
        print('***登录成功***')
        if self.is_element_exist('/html/body/div[2]/div[2]/div/div/div[3]/div[2]'):
            self.driver.find_element(value='/html/body/div[2]/div[2]/div/div/div[3]/div[2]', by=By.XPATH).click()

    def is_element_exist(self, element):
        """
        :param element: 判断元素是否存在
        :return:
        """
        flag = True
        browser = self.driver
        try:
            browser.find_element(value=element, by=By.XPATH)
            return flag
        except Exception:
            flag = False
            return flag

    def _get_element_text_safe(self, locator, by=By.CLASS_NAME):
        """安全地获取元素文本"""
        try:
            elements = self.driver.find_elements(value=locator, by=by)
            return elements[0].text if elements else None
        except Exception:
            return None

    def _click_element_safe(self, locator, by=By.CLASS_NAME):
        """安全地点击元素"""
        try:
            element = self.driver.find_element(value=locator, by=by)
            element.click()
            return True
        except Exception:
            return False

    def _get_wait_time(self, short=False):
        """根据快速模式获取等待时间"""
        if short:
            return 0.1 if self.config.fast_mode else 0.2
        return 0.2 if self.config.fast_mode else 0.3

    def _is_order_confirmation_page(self):
        """检查是否为订单确认页"""
        title = self.driver.title
        if '订单确认页' in title or '确认购买' in title:
            return True
        try:
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            return '支付方式' in page_text
        except Exception:
            return False

    def choose_ticket(self):
        """
        :return: 选票
        """
        if self.status != 2:
            return

        print("*******************************\n")
        print("***开始在详情页选择***\n")

        # 判断是否为移动端
        is_mobile = 'm.damai.cn' in self.driver.current_url

        # 在详情页完成所有选择：城市、场次、票价、数量
        if is_mobile:
            print("检测到移动端页面\n")
            self.select_details_page_mobile()
        else:
            print("检测到PC端页面\n")
            self.select_details_page_pc()

        print("*******************************\n")
        print("***开始轮询检测预订按钮***\n")

        clicked_booking = False
        while not self._is_order_confirmation_page():
            if clicked_booking:
                if self._is_order_confirmation_page():
                    print('  ✓ 页面已跳转到订单确认页\n')
                    break
                elif '选座购买' in self.driver.title:
                    print('  ✓ 页面已跳转到选座购买页\n')
                    break
                else:
                    # 根据快速模式调整等待时间
                    wait_time = 0.2 if self.config.fast_mode else 0.5
                    time.sleep(wait_time)
                    continue

            try:
                buy_button = self._get_element_text_safe('buy__button__text', By.CLASS_NAME)
                by_link = self._get_element_text_safe('buy-link', By.CLASS_NAME)

                if buy_button == "提交缺货登记":
                    self.status = 2
                    self.driver.get(self.config.target_url)
                    print('***抢票未开始，刷新等待开始***\n')
                    continue

                # 处理各种可点击的按钮/链接
                clickable_actions = [
                    ("立即预订", buy_button, 'buy__button__text'),
                    ("立即购买", buy_button, 'buy__button__text'),
                    ("缺货登记", buy_button, 'buy__button__text', lambda: self.config.if_listen),
                    ("选座购买", buy_button, 'buy__button__text'),
                ]

                action_taken = False
                for action in clickable_actions:
                    text, current_text, locator, *condition = action
                    if current_text == text and (not condition or condition[0]()):
                        print(f'✓ 检测到按钮: {text}')
                        self._click_element_safe(locator, By.CLASS_NAME)
                        self.status = 3
                        clicked_booking = True
                        print('  等待页面跳转...\n')
                        action_taken = True
                        break

                if not action_taken and by_link in ("不，立即预订", "不，立即购买"):
                    print(f'✓ 检测到链接: {by_link}')
                    self._click_element_safe('buy-link', By.CLASS_NAME)
                    self.status = 3
                    clicked_booking = True
                    print('  等待页面跳转...\n')

            except Exception as e:
                print(e)

            # 检查页面类型
            if '选座购买' in self.driver.title:
                self.choice_seat()
            elif self._is_order_confirmation_page():
                print('***进入订单确认页***\n')
                self.commit_order()
            else:
                print('***抢票未开始，刷新等待开始***\n')
                # 根据快速模式调整刷新等待时间
                refresh_wait = 0.3 if self.config.fast_mode else 1
                time.sleep(refresh_wait)
                self.driver.refresh()

    def choice_seat(self):
        while self.driver.title == '选座购买':
            while self.is_element_exist('//*[@id="app"]/div[2]/div[2]/div[1]/div[2]/img'):
                # 座位手动选择 选中座位之后//*[@id="app"]/div[2]/div[2]/div[1]/div[2]/img 就会消失
                print('请快速选择您的座位！！！')
            # 消失之后就会出现 //*[@id="app"]/div[2]/div[2]/div[2]/div
            while self.is_element_exist('//*[@id="app"]/div[2]/div[2]/div[2]/div'):
                # 找到之后进行点击确认选座
                self.driver.find_element(value='//*[@id="app"]/div[2]/div[2]/div[2]/button', by=By.XPATH).click()

    def _select_option_by_config(self, config_list, element_list, skip_keywords=None):
        """根据配置列表选择选项

        Args:
            config_list: 配置的选项列表（如日期、价格列表）
            element_list: 页面上的元素列表
            skip_keywords: 需要跳过的关键词列表（如['无票', '售罄']）

        Returns:
            bool: 是否成功选择
        """
        if not config_list or not element_list:
            return False

        skip_keywords = skip_keywords or ['无票', '缺货']

        # 根据快速模式调整等待时间
        wait_time = 0.2 if self.config.fast_mode else 0.5

        for config_value in config_list:
            for element in element_list:
                try:
                    elem_text = element.text
                    if config_value in elem_text and not any(kw in elem_text for kw in skip_keywords):
                        element.click()
                        time.sleep(wait_time)
                        return True
                except Exception:
                    continue
        return False

    def choice_order(self):
        """选择订单：包括场次、票档、人数"""
        self.driver.find_element(value='buy__button__text', by=By.CLASS_NAME).click()
        time.sleep(0.2)
        print("***选定场次***\n")

        # 选择场次
        if self.driver.find_elements(value='sku-times-card', by=By.CLASS_NAME) and self.config.dates:
            order_name_element_list = self.driver.find_element(
                value='sku-times-card', by=By.CLASS_NAME
            ).find_elements(value='bui-dm-sku-card-item', by=By.CLASS_NAME)
            if self._select_option_by_config(self.config.dates, order_name_element_list):
                print("  ✓ 场次选择成功")

        print("***选定票档***\n")
        # 选择票档
        if self.driver.find_elements(value='sku-tickets-card', by=By.CLASS_NAME) and self.config.prices:
            sku_name_element_list = self.driver.find_elements(value='item-content', by=By.CLASS_NAME)
            if self._select_option_by_config(self.config.prices, sku_name_element_list, ['缺', '售罄']):
                print("  ✓ 票档选择成功")

        print("***选定人数***\n")
        # 选择人数
        if self.driver.find_elements(value='bui-dm-sku-counter', by=By.CLASS_NAME):
            for i in range(len(self.config.users) - 1):
                self.driver.execute_script(
                    'document.getElementsByClassName("number-edit-bg")[1].click();')
            print(f"  ✓ 已选择 {len(self.config.users)} 张票")

        # 点击确定
        self.driver.find_element(value='bui-btn-contained', by=By.CLASS_NAME).click()

    def _scan_page_info(self):
        """扫描页面基本信息用于调试"""
        print("  📄 页面信息:")
        print(f"    URL: {self.driver.current_url}")
        print(f"    标题: {self.driver.title}\n")

    def _scan_page_text(self):
        """扫描页面文本内容"""
        print("  🔍 扫描页面文本内容...")
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            if body_text:
                lines = body_text.split('\n')[:20]
                print(f"    页面文本内容（前20行）:")
                for line in lines:
                    line = line.strip()
                    if line:
                        print(f"      {line}")
            else:
                print("    ⚠ 页面无文本内容")
        except Exception as e:
            print(f"    扫描失败: {e}")
        print()

    def _scan_elements(self, tag_name, label):
        """扫描指定类型的元素"""
        print(f"  🔍 扫描所有{label}...")
        try:
            elements = self.driver.find_elements(By.TAG_NAME, tag_name)
            if elements:
                print(f"    找到 {len(elements)} 个{label}:")
                for idx, elem in enumerate(elements[:10]):
                    try:
                        if tag_name == "input":
                            elem_type = elem.get_attribute('type') or 'text'
                            elem_name = elem.get_attribute('name') or ''
                            elem_id = elem.get_attribute('id') or ''
                            elem_class = elem.get_attribute('class') or ''
                            print(f"      [{idx}] type='{elem_type}' name='{elem_name}' id='{elem_id}' class='{elem_class}'")
                        elif tag_name == "button":
                            btn_text = elem.text.strip()
                            btn_class = elem.get_attribute('class') or ''
                            print(f"      [{idx}] text='{btn_text}' class='{btn_class}'")
                    except Exception:
                        pass
            else:
                print(f"    未找到{label}")
        except Exception as e:
            print(f"    扫描失败: {e}")
        print()

    def _scan_user_elements(self, retry_count=5, retry_interval=0.5):
        """扫描购票人相关元素（支持重试）

        Args:
            retry_count: 重试次数，默认 5 次
            retry_interval: 重试间隔（秒），默认 0.5 秒

        Returns:
            bool: 是否找到任意用户元素
        """
        print("  🔍 扫描购票人元素...")

        for attempt in range(retry_count):
            if attempt > 0:
                print(f"  第 {attempt + 1} 次尝试...")
                time.sleep(retry_interval)

            try:
                # 查找所有包含用户名的文本
                found_any = False
                for user in self.config.users:
                    xpath = f"//*[contains(text(), '{user}')]"
                    user_elements = self.driver.find_elements(By.XPATH, xpath)

                    if user_elements:
                        if not found_any and attempt == 0:
                            print(f"  找到 {len(user_elements)} 个包含 '{user}' 的元素")
                        found_any = True
                        if attempt == 0:  # 只在第一次尝试时显示详细信息
                            for idx, elem in enumerate(user_elements[:3]):
                                try:
                                    text = elem.text.strip()
                                    tag = elem.tag_name
                                    class_attr = elem.get_attribute('class') or ''
                                    print(f"    [{idx}] <{tag}> class='{class_attr}' text='{text}'")
                                except Exception:
                                    pass
                    else:
                        if attempt == 0:
                            print(f"  ⚠ 未找到包含 '{user}' 的元素")

                # 如果找到了任意用户元素，返回成功
                if found_any:
                    if attempt > 0:
                        print(f"  ✓ 第 {attempt + 1} 次尝试成功找到用户元素")
                    print()
                    return True

            except Exception as e:
                if attempt == 0:
                    print(f"  扫描异常: {e}")

        print(f"  ⚠ {retry_count} 次尝试后仍未找到用户元素")
        print()
        return False

    def _try_select_user_method1(self, user, users_to_select, user_selected):
        """方法1: 查找并点击包含用户名的div"""
        if user_selected >= len(users_to_select):
            return user_selected

        try:
            print(f"    尝试方法1: 查找并点击包含用户名的div")
            xpath_expression = f"//div[contains(text(), '{user}')]"
            user_elements = self.driver.find_elements(By.XPATH, xpath_expression)

            if not user_elements:
                print(f"      未找到包含 '{user}' 的div")
                return user_selected

            print(f"      找到 {len(user_elements)} 个包含 '{user}' 的div")

            # 找到精确匹配或最短匹配的div
            best_match = None
            for elem in user_elements:
                try:
                    elem_text = elem.text.strip()
                    if elem_text == user:
                        best_match = elem
                        break
                    elif len(elem_text) < 30 and user in elem_text:
                        if best_match is None:
                            best_match = elem
                except Exception:
                    continue

            if not best_match:
                print(f"      未找到合适的div元素")
                return user_selected

            # 尝试在div附近找复选框或icon
            checkbox_selectors = [
                "following-sibling::*//i[contains(@class, 'iconfont')]",
                "following-sibling::*[1]//i",
                "following-sibling::i",
                "..//following-sibling::*//i[contains(@class, 'iconfont')]",
                "..//following-sibling::i",
                "..//i[contains(@class, 'iconfont')]",
                "..//i[contains(@class, 'icon')]",
                "..//i[contains(@class, 'check')]",
                "following-sibling::*[1]//input",
                "following-sibling::*[1]//span",
                "..//following-sibling::*//input",
                "../..//input[@type='checkbox']",
                "..//label",
            ]

            for selector in checkbox_selectors:
                try:
                    checkbox = best_match.find_element(By.XPATH, selector)
                    elem_tag = checkbox.tag_name
                    elem_class = checkbox.get_attribute('class') or ''
                    print(f"        找到可点击元素: <{elem_tag}> class='{elem_class}'")
                    self.driver.execute_script("arguments[0].click();", checkbox)
                    print(f"  ✓ 已选择: {user}\n")
                    time.sleep(self._get_wait_time())
                    return user_selected + 1
                except Exception:
                    continue

            # 直接点击div本身
            print(f"        未找到复选框/icon，直接点击div本身")
            try:
                self.driver.execute_script("arguments[0].click();", best_match)
                print(f"  ✓ 已点击: {user}\n")
                time.sleep(self._get_wait_time())
                return user_selected + 1
            except Exception:
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", best_match)
                    time.sleep(0.2)
                    self.driver.execute_script("arguments[0].click();", best_match)
                    print(f"  ✓ 已点击（滚动后）: {user}\n")
                    time.sleep(self._get_wait_time())
                    return user_selected + 1
                except Exception as e:
                    print(f"        点击失败: {e}")

        except Exception as e:
            print(f"    方法1失败: {e}")

        return user_selected

    def _try_select_user_method2(self, user, users_to_select, user_selected):
        """方法2: 通过复选框和label选择"""
        if user_selected >= len(users_to_select):
            return user_selected

        try:
            print(f"    尝试方法2: 查找所有复选框")
            all_checkboxes = self.driver.find_elements(By.XPATH, "//input[@type='checkbox']")
            all_labels = self.driver.find_elements(By.TAG_NAME, 'label')

            print(f"      找到 {len(all_checkboxes)} 个复选框")
            print(f"      找到 {len(all_labels)} 个标签")

            # 通过label文本匹配
            for label in all_labels:
                try:
                    label_text = label.text.strip()
                    if user in label_text:
                        label_for = label.get_attribute('for')
                        if label_for:
                            checkbox = self.driver.find_element(By.ID, label_for)
                            if not checkbox.is_selected():
                                checkbox.click()
                                print(f"        通过label选择: {label_text}")
                                print(f"  ✓ 已选择: {user}\n")
                                time.sleep(self._get_wait_time())
                                return user_selected + 1
                except Exception:
                    continue

            # 通过复选框附近的文本匹配
            if user_selected < len(users_to_select):
                for checkbox in all_checkboxes:
                    try:
                        parent = checkbox.find_element(By.XPATH, '..')
                        nearby_text = parent.text.strip()

                        if user in nearby_text:
                            if not checkbox.is_selected():
                                checkbox.click()
                                print(f"        通过附近文本选择: {nearby_text}")
                                print(f"  ✓ 已选择: {user}\n")
                                time.sleep(self._get_wait_time())
                                return user_selected + 1
                    except Exception:
                        continue

        except Exception as e:
            print(f"    方法2失败: {e}")

        return user_selected

    def _try_select_user_method3(self, user, users_to_select, user_selected):
        """方法3: 点击包含用户名的元素"""
        if user_selected >= len(users_to_select):
            return user_selected

        try:
            print(f"    尝试方法3: 点击包含用户名的元素")
            xpath = f"//*[contains(text(), '{user}')]"
            user_elements = self.driver.find_elements(By.XPATH, xpath)

            for elem in user_elements[:10]:
                try:
                    elem_text = elem.text.strip()
                    if elem_text == user or (len(elem_text) < 30 and user in elem_text):
                        print(f"        尝试点击: {elem_text}")
                        elem.click()
                        print(f"  ✓ 已点击: {user}\n")
                        time.sleep(self._get_wait_time())
                        return user_selected + 1
                except Exception:
                    continue

        except Exception as e:
            print(f"    方法3失败: {e}")

        return user_selected

    def _try_select_user_method4(self, user, users_to_select, user_selected):
        """方法4: 使用JavaScript查找并点击"""
        if user_selected >= len(users_to_select):
            return user_selected

        try:
            print(f"    尝试方法4: 使用JavaScript查找并点击")
            js_script = f"""
            var divs = document.getElementsByTagName('div');
            var targetDivs = [];
            for (var i = 0; i < divs.length; i++) {{
                if (divs[i].textContent.includes('{user}') &&
                    divs[i].textContent.trim() === '{user}' &&
                    divs[i].offsetParent !== null) {{
                    targetDivs.push(divs[i]);
                }}
            }}
            return targetDivs;
            """
            target_divs = self.driver.execute_script(js_script)

            if not target_divs:
                print(f"      未找到精确匹配 '{user}' 的div")
                return user_selected

            print(f"      找到 {len(target_divs)} 个匹配的div")
            div = target_divs[0]

            # 查找icon元素
            find_icon_script = """
            var div = arguments[0];
            var nextSibling = div.nextElementSibling;
            if (nextSibling) {
                var icons = nextSibling.getElementsByTagName('i');
                for (var i = 0; i < icons.length; i++) {
                    if (icons[i].className.indexOf('iconfont') !== -1) {
                        return icons[i];
                    }
                }
            }
            var parent = div.parentElement;
            if (parent) {
                var parentSibling = parent.nextElementSibling;
                if (parentSibling) {
                    var icons = parentSibling.getElementsByTagName('i');
                    for (var i = 0; i < icons.length; i++) {
                        if (icons[i].className.indexOf('iconfont') !== -1) {
                            return icons[i];
                        }
                    }
                }
            }
            return div;
            """

            target_elem = self.driver.execute_script(find_icon_script, div)
            elem_tag = target_elem.tag_name
            elem_class = target_elem.get_attribute('class') or ''

            try:
                self.driver.execute_script("arguments[0].click();", target_elem)
                print(f"      ✓ 已通过JavaScript点击: <{elem_tag}> class='{elem_class}'")
                print(f"  ✓ 已选择: {user}\n")
                time.sleep(0.5)
                return user_selected + 1
            except Exception as e:
                print(f"      点击失败: {e}")

        except Exception as e:
            print(f"    方法4失败: {e}")

        return user_selected

    def _select_users(self, ticket_count, users_to_select):
        """选择观演人员"""
        user_selected = 0

        for i, user in enumerate(users_to_select):
            # 使用循环索引 i 而不是 user_selected，避免计数错误
            print(f"  正在选择: {user} ({i + 1}/{ticket_count})")

            # 尝试多种方法选择用户（如果已经选够了，就跳过）
            if user_selected >= ticket_count:
                print(f"    ⚠ 已选够 {ticket_count} 人，跳过: {user}")
                continue

            # 尝试多种方法选择用户
            new_user_selected = self._try_select_user_method1(user, users_to_select, user_selected)
            if new_user_selected > user_selected:
                user_selected = new_user_selected
            else:
                new_user_selected = self._try_select_user_method2(user, users_to_select, user_selected)
                if new_user_selected > user_selected:
                    user_selected = new_user_selected
                else:
                    new_user_selected = self._try_select_user_method3(user, users_to_select, user_selected)
                    if new_user_selected > user_selected:
                        user_selected = new_user_selected
                    else:
                        new_user_selected = self._try_select_user_method4(user, users_to_select, user_selected)
                        if new_user_selected > user_selected:
                            user_selected = new_user_selected

            if user_selected <= i:
                print(f"  ⚠ 未找到用户: {user}")

        print(f"\n***已选择 {user_selected}/{ticket_count} 个观众***")

        if user_selected > 0:
            print(f"  ✓ 已选择的观众: {users_to_select[:user_selected]}")
        if user_selected < ticket_count:
            print(f"  ⚠ 未选择的观众: {users_to_select[user_selected:ticket_count]}")
        print()

    def _scan_submit_buttons(self):
        """扫描提交按钮"""
        print("  🔍 扫描提交按钮...")
        try:
            submit_candidates = []

            # 扫描button
            all_buttons = self.driver.find_elements(By.TAG_NAME, "button")
            for btn in all_buttons:
                try:
                    btn_text = btn.text.strip()
                    btn_class = btn.get_attribute('class') or ''
                    if any(keyword in btn_text for keyword in ['提交订单', '提交', '确认', '立即支付', '去支付', '支付']):
                        submit_candidates.append(('button', btn, btn_text, btn_class))
                        print(f"    [button] text='{btn_text}' class='{btn_class}'")
                except Exception:
                    pass

            # 扫描包含"立即提交"的div和span
            for tag in ['div', 'span']:
                elements = self.driver.find_elements(By.TAG_NAME, tag)
                for elem in elements:
                    try:
                        elem_text = elem.text.strip()
                        if elem_text in ['立即提交', '提交订单', '提交', '确认']:
                            elem_class = elem.get_attribute('class') or ''
                            view_name = elem.get_attribute('view-name') or ''
                            submit_candidates.append((tag, elem, elem_text, elem_class, view_name))
                            print(f"    [{tag}] text='{elem_text}' class='{elem_class}' view-name='{view_name}'")
                    except Exception:
                        pass

            if not submit_candidates:
                print("    ⚠ 未找到明显的提交按钮")
        except Exception as e:
            print(f"    扫描失败: {e}")
        print()

    def _try_submit_by_text(self, submit_button_texts):
        """方法1-2: 通过元素文本查找"""
        for btn_text in submit_button_texts:
            for tag in ['button', 'div', 'span']:
                try:
                    xpath = f"//{tag}[contains(text(), '{btn_text}')]"
                    submit_btn = self.driver.find_element(By.XPATH, xpath)
                    print(f"  ✓ 找到<{tag}>: {btn_text}")
                    submit_btn.click()
                    print('***订单已提交***\n')
                    return True
                except Exception:
                    continue

            # 尝试精确匹配
            try:
                xpath = f"//span[text()='{btn_text}']"
                submit_btn = self.driver.find_element(By.XPATH, xpath)
                print(f"  ✓ 找到<span>(精确匹配): {btn_text}")
                try:
                    parent = submit_btn.find_element(By.XPATH, '..')
                    parent.click()
                except Exception:
                    submit_btn.click()
                print('***订单已提交***\n')
                return True
            except Exception:
                continue

        return False

    def _try_submit_by_view_name(self):
        """方法3: 通过view-name属性查找"""
        try:
            xpath = "//div[@view-name='TextView']//span[contains(text(), '提交')]"
            submit_btn = self.driver.find_element(By.XPATH, xpath)
            print(f"  ✓ 找到div[@view-name='TextView']")
            parent_div = submit_btn.find_element(By.XPATH, '..')
            parent_div.click()
            print('***订单已提交***\n')
            return True
        except Exception:
            return False

    def _try_submit_by_class(self):
        """方法4: 通过class查找"""
        submit_button_classes = [
            'submit-button',
            'submit-btn',
            'confirm-button',
            'pay-button',
            'bui-btn-contained',
        ]

        for class_name in submit_button_classes:
            try:
                xpath = f"//*[contains(@class, '{class_name}')]"
                submit_btn = self.driver.find_element(By.XPATH, xpath)
                print(f"  ✓ 通过class找到按钮: {class_name}")
                submit_btn.click()
                print('***订单已提交***\n')
                return True
            except Exception:
                continue

        return False

    def _try_submit_by_original_xpath(self):
        """方法5: 原有的XPath"""
        try:
            submit_btn = self.driver.find_element(
                value='//*[@id="dmOrderSubmitBlock_DmOrderSubmitBlock"]/div[2]/div/div[2]/div[2]/div[2]',
                by=By.XPATH)
            print("  ✓ 通过原有XPath找到按钮")
            submit_btn.click()
            print('***订单已提交***\n')
            return True
        except Exception:
            return False

    def _submit_order(self):
        """提交订单"""
        print('***准备提交订单***\n')

        self._scan_submit_buttons()

        submit_button_texts = ['立即提交', '提交订单', '提交', '确认', '立即支付', '去支付', '支付']

        # 尝试多种方法提交
        if (self._try_submit_by_text(submit_button_texts) or
            self._try_submit_by_view_name() or
            self._try_submit_by_class() or
            self._try_submit_by_original_xpath()):
            return

        print(f"  ⚠ 所有方法都失败，请手动点击提交按钮\n")

    def commit_order(self):
        """提交订单"""
        if self.status not in [3]:
            return

        print('***开始确认订单***\n')

        # 等待页面加载完成
        if not self.config.fast_mode:
            print('⏳ 等待订单确认页加载...\n')
            time.sleep(self.config.page_load_delay)
        else:
            # 快速模式：使用显式等待，但等待足够时间让动态内容加载
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.common.by import By
            try:
                # 等待 body 元素
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                # 额外等待让动态内容加载（用户列表通常是异步加载的）
                time.sleep(max(1, self.config.page_load_delay / 2))
            except Exception:
                # 如果显式等待失败，使用配置的等待时间
                time.sleep(self.config.page_load_delay)

        # 计算实际购票数量
        ticket_count = len(self.config.users)

        # 数量已在详情页选择，订单确认页无需再选
        # 快速模式：减少输出，但保留关键信息
        if not self.config.fast_mode:
            print(f"  购票数量: {ticket_count} 张（已在详情页选择）\n")
            print(f"  配置观众: {self.config.users}")
            print(f"  需要选择观众: {ticket_count} 个\n")

        users_to_select = self.config.users[:ticket_count]

        try:
            # 快速模式：跳过详细的页面扫描，但保留用户元素扫描
            if not self.config.fast_mode:
                self._scan_page_info()
                self._scan_page_text()
                self._scan_elements("input", "输入框")
                self._scan_elements("button", "按钮")

            # 扫描用户元素（支持自动重试：5次，每次间隔0.5秒）
            user_found = self._scan_user_elements(retry_count=5, retry_interval=0.5)

            # 选择用户
            self._select_users(ticket_count, users_to_select)

        except Exception as e:
            print("***购票人信息选择过程出现异常***\n")
            print(f"  异常信息: {e}")
            print("\n  建议:")
            print("    1. 在浏览器中手动选择购票人")
            if not self.config.fast_mode:
                print("    2. 查看上方扫描输出，确认用户名格式")
            print("    3. 检查用户名是否与配置一致")
            print(f"    4. 确保选择 {ticket_count} 个观众\n")

        # 提交订单（优化等待时间）
        if self.config.fast_mode:
            time.sleep(0.1)  # 快速模式：几乎不等待
        else:
            time.sleep(0.5)  # 正常模式：等待0.5秒

        if self.config.if_commit_order:
            self._submit_order()

    def select_details_page_mobile(self):
        """在移动端详情页完成所有选择：城市、场次、票价、数量（优化版：快速连续执行）"""
        if not self.config.fast_mode:
            print("⏳ 开始在移动端详情页进行选择...\n")

        # 快速连续选择（移除不必要的等待和输出）
        success = True

        # 1. 选择城市
        if self.config.city and success:
            if not self.config.fast_mode:
                print("***选择城市***")
                print(f"  目标城市: {self.config.city}")
            success = self.select_city_on_page()
            if not self.config.fast_mode:
                print()

        # 2. 选择场次
        if self.config.dates and success:
            if not self.config.fast_mode:
                print("***选择场次***")
                print(f"  目标场次: {self.config.dates}")
            success = self.select_date_on_page()
            if not self.config.fast_mode:
                print()

        # 3. 选择票价
        if self.config.prices and success:
            if not self.config.fast_mode:
                print("***选择票价***")
                print(f"  目标票价: {self.config.prices}")
            success = self.select_price_on_page()
            if not self.config.fast_mode:
                print()

        # 4. 选择数量
        if len(self.config.users) > 1 and success:
            if not self.config.fast_mode:
                print("***选择购票数量***")
                print(f"  目标数量: {len(self.config.users)} 张")
            self.select_quantity_on_page()
            if not self.config.fast_mode:
                print()

        print("***详情页选择完成***\n")

    def select_details_page_pc(self):
        """在PC端详情页完成所有选择：城市、场次、票价、数量（优化版：快速连续执行）"""
        if not self.config.fast_mode:
            print("⏳ 开始在PC端详情页进行选择...\n")
            # 先扫描页面元素，帮助调试
            print("***扫描页面元素***\n")
            self.scan_page_elements()
            print()

        # 快速模式：跳过页面扫描，直接快速连续选择
        success = True

        # 快速连续选择（移除不必要的等待和输出）
        # 1. 选择城市
        if self.config.city and success:
            if not self.config.fast_mode:
                print("***选择城市***")
                print(f"  目标城市: {self.config.city}")
            success = self.select_city_on_page_pc()
            if not self.config.fast_mode:
                print()

        # 2. 选择场次
        if self.config.dates and success:
            if not self.config.fast_mode:
                print("***选择场次***")
                print(f"  目标场次: {self.config.dates}")
            success = self.select_date_on_page_pc()
            if not self.config.fast_mode:
                print()

        # 3. 选择票价
        if self.config.prices and success:
            if not self.config.fast_mode:
                print("***选择票价***")
                print(f"  目标票价: {self.config.prices}")
            success = self.select_price_on_page_pc()
            if not self.config.fast_mode:
                print()

        # 4. 选择数量
        if len(self.config.users) > 1 and success:
            if not self.config.fast_mode:
                print("***选择购票数量***")
                print(f"  目标数量: {len(self.config.users)} 张")
            self._select_quantity_on_page(platform="PC端")
            if not self.config.fast_mode:
                print()

        print("***详情页选择完成***\n")

    def _click_element_by_text(self, text_content, tag_names=None, exact_match=False):
        """通过文本内容点击元素

        Args:
            text_content: 要查找的文本内容
            tag_names: 要搜索的标签名列表，默认为['div', 'span', 'button']
            exact_match: 是否精确匹配文本

        Returns:
            bool: 是否成功点击
        """
        tag_names = tag_names or ['div', 'span', 'button']

        for tag in tag_names:
            try:
                if exact_match:
                    xpath = f"//{tag}[text()='{text_content}']"
                else:
                    xpath = f"//{tag}[contains(text(), '{text_content}')]"
                elements = self.driver.find_elements(By.XPATH, xpath)
                for elem in elements[:5]:  # 只尝试前5个
                    try:
                        elem_text = elem.text.strip()
                        if (exact_match and elem_text == text_content) or \
                           (not exact_match and text_content in elem_text):
                            # 尝试点击元素本身或其父元素
                            for target in [elem, elem.find_element(By.XPATH, '..')]:
                                try:
                                    target.click()
                                    time.sleep(0.5)
                                    return True
                                except Exception:
                                    continue
                    except Exception:
                        continue
            except Exception:
                continue
        return False

    def _find_and_click_element(self, search_text, max_results=10, skip_keywords=None, print_results=True):
        """查找并点击包含指定文本的元素

        Args:
            search_text: 要搜索的文本
            max_results: 最大尝试结果数
            skip_keywords: 需要跳过的关键词列表
            print_results: 是否打印搜索结果

        Returns:
            bool: 是否成功点击
        """
        skip_keywords = skip_keywords or []
        xpath = f"//*[contains(text(), '{search_text}')]"
        elements = self.driver.find_elements(By.XPATH, xpath)

        if print_results:
            print(f"  找到 {len(elements)} 个包含 '{search_text}' 的元素")

        for idx, elem in enumerate(elements[:max_results]):
            try:
                elem_text = elem.text.strip()
                if not elem_text or any(kw in elem_text for kw in skip_keywords):
                    continue

                if print_results and len(elem_text) < 100:
                    print(f"    [{idx}] {elem_text}")

                # 尝试点击元素本身或父元素
                for target in [elem, elem.find_element(By.XPATH, '..')]:
                    try:
                        target.click()
                        # 根据快速模式调整等待时间
                        wait_time = 0.2 if self.config.fast_mode else 0.5
                        time.sleep(wait_time)
                        if print_results:
                            print(f"  ✓ 已点击: {elem_text}")
                        return True
                    except Exception:
                        continue
            except Exception:
                continue

        if print_results:
            print(f"  ⚠ 未找到匹配的元素")
        return False

    def _scan_elements_by_class(self, class_names, label):
        """扫描指定class的元素"""
        print(f"  🔍 扫描{label}...")
        try:
            for selector in class_names:
                try:
                    elements = self.driver.find_elements(By.CLASS_NAME, selector)
                    if elements:
                        print(f"  ✓ 找到 class='{selector}': {len(elements)} 个")
                        for idx, elem in enumerate(elements[:3]):
                            try:
                                text = elem.text.strip()[:50]
                                if text:
                                    print(f"      [{idx}] {text}")
                            except Exception:
                                pass
                        return True
                except Exception:
                    pass
            return False
        except Exception as e:
            print(f"    扫描失败: {e}")
            return False

    def scan_page_elements(self):
        """扫描页面元素，用于调试"""
        try:
            print("【1】查找城市相关元素:")
            city_selectors = ['bui-dm-tour', 'tour-list', 'city-list', 'sku-tour']
            self._scan_elements_by_class(city_selectors, "城市")

            print("\n【2】查找场次相关元素:")
            date_selectors = ['sku-times-card', 'sku-times', 'date-list', 'tour-list']
            self._scan_elements_by_class(date_selectors, "场次")

            print("\n【3】查找票价相关元素:")
            price_selectors = ['sku-tickets-card', 'sku-ticket', 'price-list', 'ticket-list']
            self._scan_elements_by_class(price_selectors, "票价")

            print("\n【4】查找所有包含日期的文本:")
            try:
                all_elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), '月') or contains(text(), '日')]")
                seen = set()
                for elem in all_elements[:20]:
                    try:
                        text = elem.text.strip()
                        if text and 3 < len(text) < 100 and text not in seen:
                            print(f"  - {text}")
                            seen.add(text)
                    except Exception:
                        pass
            except Exception:
                pass

            print("\n【5】查找所有包含价格的文本:")
            try:
                all_elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), '¥') or contains(text(), '元')]")
                seen = set()
                for elem in all_elements[:20]:
                    try:
                        text = elem.text.strip()
                        if text and text not in seen and len(text) < 50:
                            print(f"  - {text}")
                            seen.add(text)
                    except Exception:
                        pass
            except Exception:
                pass

        except Exception as e:
            print(f"  扫描异常: {e}")

    def select_city_on_page_pc(self):
        """在PC端详情页选择城市（支持模糊匹配）"""
        try:
            # 方法1: 使用原有class选择器
            if self.driver.find_elements(value='bui-dm-tour', by=By.CLASS_NAME):
                city_name_element_list = self.driver.find_element(
                    value='bui-dm-tour', by=By.CLASS_NAME
                ).find_elements(value='tour-card', by=By.CLASS_NAME)

                # 快速模式：减少输出
                if not self.config.fast_mode:
                    print(f"  找到 {len(city_name_element_list)} 个城市选项:\n")
                    # 批量获取所有城市文本
                    cities = []
                    for city_elem in city_name_element_list:
                        try:
                            city_text = city_elem.text.strip()
                            if city_text:
                                cities.append(city_text)
                        except Exception:
                            pass
                    # 一次性显示所有城市
                    for idx, city_text in enumerate(cities):
                        print(f"    [{idx}] {city_text}")
                    print()

                # 匹配城市（无需显示详细信息）
                for city_name_element in city_name_element_list:
                    try:
                        if self.config.city in city_name_element.text:
                            if not self.config.fast_mode:
                                print(f"  ✓ 匹配成功: {city_name_element.text}\n")
                            city_name_element.click()
                            time.sleep(self._get_wait_time(short=True))
                            return True
                    except Exception:
                        continue

            # 方法2: 通过文本XPath搜索（通用模糊匹配）
            if not self.config.fast_mode:
                print(f"  尝试通用文本搜索...")
            return self._find_and_click_element(
                self.config.city,
                max_results=10,
                print_results=not self.config.fast_mode
            )

        except Exception as e:
            if not self.config.fast_mode:
                print(f"  城市选择异常: {e}")
            return False

    def select_date_on_page_pc(self):
        """在PC端详情页选择场次（支持模糊匹配）"""
        try:
            # 方法1: 使用原有class选择器
            if self.driver.find_elements(value='sku-times-card', by=By.CLASS_NAME):
                order_name_element_list = self.driver.find_element(
                    value='sku-times-card', by=By.CLASS_NAME
                ).find_elements(value='bui-dm-sku-card-item', by=By.CLASS_NAME)

                # 快速模式：减少输出
                if not self.config.fast_mode:
                    print(f"  找到 {len(order_name_element_list)} 个场次选项:\n")
                    # 批量获取所有场次文本
                    dates = []
                    for elem in order_name_element_list:
                        try:
                            text = elem.text.strip()
                            if text:
                                dates.append(text)
                        except Exception:
                            pass
                    # 一次性显示所有场次
                    for idx, text in enumerate(dates):
                        print(f"    [{idx}] {text}")
                    print()

                # 匹配场次
                if self._select_option_by_config(self.config.dates, order_name_element_list):
                    return True

            # 方法2: 通用文本搜索（模糊匹配）
            if not self.config.fast_mode:
                print(f"  尝试通用文本搜索...")
            for date in self.config.dates:
                if self._find_and_click_element(date, max_results=10, skip_keywords=['无票', '售罄'], print_results=not self.config.fast_mode):
                    return True

            if not self.config.fast_mode:
                print(f"  ⚠ 未找到匹配的场次")
            return False

        except Exception as e:
            if not self.config.fast_mode:
                print(f"  场次选择异常: {e}")
            return False

    def select_price_on_page_pc(self):
        """在PC端详情页选择票价（支持模糊匹配）"""
        try:
            # 方法1: 使用原有class选择器
            if self.driver.find_elements(value='sku-tickets-card', by=By.CLASS_NAME):
                sku_name_element_list = self.driver.find_elements(value='item-content', by=By.CLASS_NAME)

                # 快速模式：减少输出
                if not self.config.fast_mode:
                    print(f"  找到 {len(sku_name_element_list)} 个票价选项:\n")
                    # 批量获取所有票价文本
                    prices = []
                    for elem in sku_name_element_list:
                        try:
                            text = elem.text.strip()
                            if text:
                                prices.append(text)
                        except Exception:
                            pass
                    # 一次性显示所有票价
                    for idx, text in enumerate(prices):
                        print(f"    [{idx}] {text}")
                    print()

                # 匹配票价
                if self._select_option_by_config(self.config.prices, sku_name_element_list, ['缺', '售罄', '无票']):
                    return True

            # 方法2: 通用文本搜索（模糊匹配）
            if not self.config.fast_mode:
                print(f"  尝试通用文本搜索...")
            for price in self.config.prices:
                if self._find_and_click_element(price, max_results=15, skip_keywords=['缺货', '售罄', '无票'], print_results=not self.config.fast_mode):
                    return True

            if not self.config.fast_mode:
                print(f"  ⚠ 未找到匹配的票价")
            return False

        except Exception as e:
            if not self.config.fast_mode:
                print(f"  票价选择异常: {e}")
            return False

    def select_quantity_on_page_pc(self):
        """在PC端详情页选择数量"""
        return self._select_quantity_on_page(platform="PC端")

    def _select_quantity_on_page(self, platform="移动端"):
        """在详情页选择数量（PC端和移动端通用）

        Args:
            platform: 平台标识，用于日志输出
        """
        from selenium.common.exceptions import WebDriverException

        try:
            target_count = len(self.config.users)
            print(f"  【{platform}详情页】目标数量: {target_count} 张")

            # 获取数量选择器并执行选择
            success = self._try_select_quantity_by_buttons(target_count)

            if not success:
                # 如果按钮方法失败，尝试直接设置输入框
                success = self._try_set_quantity_directly(target_count)

            if not success:
                print(f"  ⚠ 未找到数量选择器，将使用默认数量 (1 张)")

            return True

        except (AttributeError, TypeError, ValueError) as e:
            # 配置错误或类型错误
            print(f"  ❌ 数量选择配置错误: {e}")
            return True
        except WebDriverException as e:
            # Selenium WebDriver 相关错误
            print(f"  ⚠ WebDriver 异常，继续执行: {e}")
            return True
        except Exception as e:
            # 其他未预期的异常
            print(f"  ⚠ 未预期的异常: {e}")
            return True  # 不阻塞流程

    def _try_select_quantity_by_buttons(self, target_count):
        """通过点击 + 按钮选择数量

        Args:
            target_count: 目标数量

        Returns:
            bool: 是否成功选择
        """
        from selenium.common.exceptions import NoSuchElementException, WebDriverException

        selectors_to_try = [
            ("//div[contains(@class, 'cafe-c-input-number')]//a[contains(@class, 'handler-up')]", "cafe-c-input-number 结构"),
            ("//a[contains(@class, 'cafe-c-input-number-handler-up')]", "cafe-c-input-number-handler-up"),
            ("//div[contains(@class, 'number_right_info')]//a[last()]", "number_right_info"),
            ("//*[contains(@class, 'cafe-c-input-number')]//a[contains(text(), '+')]", "cafe-input-number + 按钮"),
            ("//a[contains(@class, 'handler-up')]", "通用 handler-up"),
        ]

        for selector, method_name in selectors_to_try:
            try:
                plus_btns = self.driver.find_elements(By.XPATH, selector)
                if plus_btns:
                    print(f"    ✓ 找到 + 按钮 ({method_name}): {len(plus_btns)} 个")

                    if self._click_plus_buttons(plus_btns, target_count):
                        return True
            except (NoSuchElementException, WebDriverException):
                # 元素未找到或 WebDriver 异常，继续尝试下一个选择器
                continue

        return False

    def _click_plus_buttons(self, plus_btns, target_count):
        """点击 + 按钮增加数量

        Args:
            plus_btns: 按钮元素列表
            target_count: 目标数量

        Returns:
            bool: 是否成功
        """
        from selenium.common.exceptions import StaleElementReferenceException, WebDriverException

        for btn in plus_btns[:3]:
            try:
                class_attr = btn.get_attribute('class') or ''
                if 'disabled' in class_attr.lower():
                    continue

                if btn.is_displayed() and btn.is_enabled():
                    # 点击 target_count - 1 次
                    for i in range(target_count - 1):
                        self.driver.execute_script("arguments[0].click();", btn)
                        time.sleep(0.25)

                    # 验证：读取输入框的值
                    current_val = self._get_quantity_input_value()
                    if current_val:
                        print(f"    输入框当前值: {current_val}")

                    print(f"  ✓ 已选择 {target_count} 张票")
                    return True
            except StaleElementReferenceException:
                # 元素引用过期，尝试下一个按钮
                continue
            except WebDriverException:
                # 其他 WebDriver 异常，尝试下一个按钮
                continue

        return False

    def _get_quantity_input_value(self):
        """获取数量输入框的值

        Returns:
            str: 输入框的值，失败返回 None
        """
        from selenium.common.exceptions import NoSuchElementException

        input_selectors = [
            "//input[contains(@class, 'cafe-c-input-number-input')]",
            "//div[contains(@class, 'cafe-c-input-number')]//input",
        ]
        for inp_sel in input_selectors:
            try:
                input_elem = self.driver.find_element(By.XPATH, inp_sel)
                return input_elem.get_attribute('value')
            except NoSuchElementException:
                # 元素未找到，尝试下一个选择器
                continue
        return None

    def _try_set_quantity_directly(self, target_count):
        """直接设置输入框的值

        Args:
            target_count: 目标数量

        Returns:
            bool: 是否成功
        """
        from selenium.common.exceptions import NoSuchElementException, JavascriptException, WebDriverException

        try:
            input_selector = "//input[contains(@class, 'cafe-c-input-number-input')]"
            input_elem = self.driver.find_element(By.XPATH, input_selector)
            print(f"    找到输入框，直接设置值")

            # 使用 JavaScript 设置值并触发事件
            self.driver.execute_script(f"""
                arguments[0].value = '{target_count}';
                arguments[0].dispatchEvent(new Event('input', {{ bubbles: true }}));
                arguments[0].dispatchEvent(new Event('change', {{ bubbles: true }}));
                arguments[0]._value = '{target_count}';
                if (arguments[0]._v_model) {{
                    arguments[0]._v_model = '{target_count}';
                }}
            """, input_elem)

            time.sleep(0.3)
            new_val = input_elem.get_attribute('value')
            print(f"    设置后输入框值: {new_val}")

            if new_val == str(target_count):
                print(f"  ✓ 已选择 {target_count} 张票")
                return True
        except NoSuchElementException:
            # 输入框未找到
            pass
        except (JavascriptException, WebDriverException) as e:
            print(f"    直接设置输入框失败: {e}")

        return False

    def select_city_on_page(self):
        """在页面选择城市（移动端）"""
        try:
            return self._find_and_click_element(
                self.config.city,
                max_results=10,
                print_results=not self.config.fast_mode
            )
        except Exception as e:
            if not self.config.fast_mode:
                print(f"  城市选择异常: {e}")
            return False

    def select_date_on_page(self):
        """在页面选择场次（移动端）"""
        try:
            if not self.config.fast_mode:
                print(f"  搜索场次: {self.config.dates}")
            for date in self.config.dates:
                if self._find_and_click_element(date, max_results=10, skip_keywords=['无票', '售罄'], print_results=not self.config.fast_mode):
                    if not self.config.fast_mode:
                        print(f"  ✓ 已选择场次: {date}\n")
                    return True

            if not self.config.fast_mode:
                print(f"  ⚠ 未找到匹配的场次")
            return False
        except Exception as e:
            if not self.config.fast_mode:
                print(f"  场次选择异常: {e}")
            return False

    def select_price_on_page(self):
        """在页面选择票价（移动端）"""
        try:
            # 快速模式：跳过扫描，直接尝试匹配
            if not self.config.fast_mode:
                # 先扫描显示所有票价
                print("  扫描票价元素...")
                price_candidates = self.driver.find_elements(By.XPATH, "//*[contains(text(), '¥') or contains(text(), '元')]")
                seen = set()
                for elem in price_candidates[:15]:
                    try:
                        text = elem.text.strip()
                        if text and text not in seen and len(text) < 50:
                            print(f"    - {text}")
                            seen.add(text)
                    except Exception:
                        pass
                print()

            for price in self.config.prices:
                if not self.config.fast_mode:
                    print(f"  尝试匹配: {price}")
                if self._find_and_click_element(price, max_results=10,
                                                skip_keywords=['缺货', '售罄', '无票'],
                                                print_results=not self.config.fast_mode):
                    if not self.config.fast_mode:
                        print(f"  ✓ 已选择票价: {price}\n")
                    return True

            if not self.config.fast_mode:
                print(f"  ⚠ 未找到匹配的票价")
            return False
        except Exception as e:
            if not self.config.fast_mode:
                print(f"  票价选择异常: {e}")
            return False

    def select_quantity_on_page(self):
        """在页面选择数量（移动端）"""
        return self._select_quantity_on_page(platform="移动端")

    def finish(self):
        self.driver.quit()
