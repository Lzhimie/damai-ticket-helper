# -*- coding: UTF-8 -*-
"""
__Author__ = "BlueCestbon"
__Version__ = "2.0.0"
__Description__ = "大麦app抢票自动化 - 优化版"
__Created__ = 2025/09/13 19:27
"""

import time
import re
from appium import webdriver
from appium.options.common.base import AppiumOptions
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from config import Config


class DamaiBot:
    def __init__(self):
        self.config = Config.load_config()
        self.driver = None
        self.wait = None
        self._setup_driver()

    def _setup_driver(self):
        """初始化驱动配置"""
        capabilities = {
            "platformName": "Android",  # 操作系统
            "platformVersion": self.config.platform_version,  # 系统版本
            "deviceName": self.config.device_name,  # 设备名称
            "appPackage": "cn.damai",  # app 包名
            "appActivity": ".launcher.splash.SplashMainActivity",  # app 启动 Activity
            "unicodeKeyboard": False,  # 不需要打字，关闭Unicode输入法（避免ime enable卡死）
            "resetKeyboard": False,  # 隐藏键盘
            "noReset": True,  # 不重置 app
            "newCommandTimeout": 6000,  # 超时时间
            "automationName": "UiAutomator2",  # 使用 uiautomator2
            "skipServerInstallation": False,  # 跳过服务器安装
            "ignoreHiddenApiPolicyError": True,  # 忽略隐藏 API 策略错误
            "disableWindowAnimation": True,  # 禁用窗口动画
            # 优化性能配置
            "mjpegServerFramerate": 1,  # 降低截图帧率
            "shouldTerminateApp": False,
            "adbExecTimeout": 60000,
        }

        device_app_info = AppiumOptions()
        device_app_info.load_capabilities(capabilities)
        self.driver = webdriver.Remote(self.config.server_url, options=device_app_info)

        # 更激进的性能优化设置
        self.driver.update_settings({
            "waitForIdleTimeout": 0,  # 空闲时间，0 表示不等待，让 UIAutomator2 不等页面“空闲”再返回
            "actionAcknowledgmentTimeout": 0,  # 禁止等待动作确认
            "keyInjectionDelay": 0,  # 禁止输入延迟
            "waitForSelectorTimeout": 300,  # 从500减少到300ms
            "ignoreUnimportantViews": False,  # 保持false避免元素丢失
            "allowInvisibleElements": True,
            "enableNotificationListener": False,  # 禁用通知监听
        })

        # 极短的显式等待，抢票场景下速度优先
        self.wait = WebDriverWait(self.driver, 2)  # 从5秒减少到2秒

    def ultra_fast_click(self, by, value, timeout=1.5):
        """超快速点击 - 适合抢票场景"""
        try:
            # 直接查找并点击，不等待可点击状态
            el = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            # 使用坐标点击更快
            rect = el.rect
            x = rect['x'] + rect['width'] // 2
            y = rect['y'] + rect['height'] // 2
            self.driver.execute_script("mobile: clickGesture", {
                "x": x,
                "y": y,
                "duration": 50  # 极短点击时间
            })
            return True
        except TimeoutException:
            return False

    def batch_click(self, elements_info, delay=0.1):
        """批量点击操作"""
        for by, value in elements_info:
            if self.ultra_fast_click(by, value):
                if delay > 0:
                    time.sleep(delay)
            else:
                print(f"点击失败: {value}")

    def ultra_batch_click(self, elements_info, timeout=2):
        """超快批量点击 - 带等待机制"""
        coordinates = []
        # 批量收集坐标，带超时等待
        for by, value in elements_info:
            try:
                # 等待元素出现
                el = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((by, value))
                )
                rect = el.rect
                x = rect['x'] + rect['width'] // 2
                y = rect['y'] + rect['height'] // 2
                coordinates.append((x, y, value))
            except TimeoutException:
                print(f"超时未找到用户: {value}")
            except Exception as e:
                print(f"查找用户失败 {value}: {e}")
        print(f"成功找到 {len(coordinates)} 个用户")
        # 快速连续点击
        for i, (x, y, value) in enumerate(coordinates):
            self.driver.execute_script("mobile: clickGesture", {
                "x": x,
                "y": y,
                "duration": 30
            })
            if i < len(coordinates) - 1:
                time.sleep(0.01)
            print(f"点击用户: {value}")

    def smart_wait_and_click(self, by, value, backup_selectors=None, timeout=1.5):
        """智能等待和点击 - 支持备用选择器"""
        selectors = [(by, value)]
        if backup_selectors:
            selectors.extend(backup_selectors)

        for selector_by, selector_value in selectors:
            try:
                el = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((selector_by, selector_value))
                )
                rect = el.rect
                x = rect['x'] + rect['width'] // 2
                y = rect['y'] + rect['height'] // 2
                self.driver.execute_script("mobile: clickGesture", {"x": x, "y": y, "duration": 50})
                return True
            except TimeoutException:
                continue
        return False

    def click_container_item(self, container_id, index, timeout=2):
        """新版大麦UI：在指定容器内，按位置点击第 index 个可点击子元素（0开始）；目标在屏幕外时先滚动到可见"""
        try:
            container = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.ID, container_id))
            )
            items = container.find_elements(By.XPATH, './/*[@clickable="true"]')
            if len(items) > index:
                target = items[index]
                rect = target.rect
                # 若目标在屏幕下方/上方（不可见），先滚动到可见再点
                try:
                    sh = self.driver.get_window_size()['height']
                    if rect['y'] + rect['height'] > sh - 260 or rect['y'] < 200:
                        self.driver.execute_script("mobile: scroll", {"element": target.id, "toVisible": True})
                        time.sleep(self.config.delay('scroll'))
                        rect = target.rect
                except Exception:
                    pass
                x = rect['x'] + rect['width'] // 2
                y = rect['y'] + rect['height'] // 2
                self.driver.execute_script("mobile: clickGesture", {"x": x, "y": y, "duration": 50})
                return True
            print(f"容器内可点击项不足 {index + 1} 个（实际 {len(items)} 个）")
            return False
        except Exception:
            return False

    def wait_for_text(self, texts, timeout=4):
        """等待页面上出现任一文本"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                for t in texts:
                    if self.driver.find_elements(AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().text("{t}")'):
                        return True
            except Exception:
                pass
            time.sleep(0.3)
        return False

    def _is_user_checked(self, user):
        """检查订单页上观演人是否已勾选（同行checkbox的checked状态）"""
        try:
            el = self.driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR,
                f'new UiSelector().text("{user}")')
            y = el.rect['y'] + el.rect['height'] // 2
            for cb in self.driver.find_elements(By.ID, 'cn.damai:id/checkbox'):
                r = cb.rect
                if r['y'] <= y <= r['y'] + r['height']:
                    return cb.get_attribute('checked') == 'true'
        except Exception:
            pass
        return None

    def _enter_selection_page(self):
        """若不在选票页：订单页先返回，详情页点购买栏进入选票页"""
        if self._check_on_right_page():
            return True
        # 若停在订单确认页，先返回选票页（避免误点提交）
        if self.wait_for_text(['立即提交', '确认购买'], timeout=1):
            print("检测到订单确认页，先返回选票页...")
            self.driver.back()
            time.sleep(self.config.delay('page_load'))
            if self._check_on_right_page():
                print("✅ 已返回选票页")
                return True
        print("未检测到选票页，尝试点击详情页购买栏进入选票页...")
        clicked = False
        try:
            el = self.driver.find_element(By.ID, 'cn.damai:id/trade_project_detail_purchase_status_bar_container_fl')
            rect = el.rect
            self.driver.execute_script("mobile: clickGesture", {
                "x": rect['x'] + rect['width'] // 2,
                "y": rect['y'] + rect['height'] // 2, "duration": 50})
            clicked = True
        except Exception:
            pass
        if not clicked:
            # 兜底：点击底部右侧购买按钮区域（画布按钮）
            self.driver.execute_script("mobile: clickGesture", {"x": 900, "y": 2550, "duration": 50})
        time.sleep(self.config.delay('page_load'))
        if self._check_on_right_page():
            print("✅ 已进入选票页")
            return True
        print("⚠️ 未能进入选票页，请手动点击'立即预定'进入（能看到场次和票价卡片的页面）")
        return False

    def _is_reserve_state(self):
        """检测当前是否为真正的预约状态（未开售）：仅选票页显示"预约想看/可预约"文字时拦截
        （薛之谦式预售/缺货也能下单，不做拦截）"""
        try:
            if self.driver.find_elements(AppiumBy.ANDROID_UIAUTOMATOR,
                'new UiSelector().textMatches("预约想看|可预约")'):
                return True
        except Exception:
            pass
        return False

    def _check_out_of_stock(self):
        """检测当前票档是否缺货：票档区出现「缺货登记」或场次卡片出现「无票」"""
        try:
            if self.driver.find_elements(AppiumBy.ANDROID_UIAUTOMATOR,
                'new UiSelector().textContains("缺货登记")'):
                return True
            if self.driver.find_elements(AppiumBy.ANDROID_UIAUTOMATOR,
                'new UiSelector().textContains("无票")'):
                return True
        except Exception:
            pass
        return False

    def _tap_element_center(self, el):
        """点击元素中心"""
        rect = el.rect
        self.driver.execute_script("mobile: clickGesture", {
            "x": rect['x'] + rect['width'] // 2,
            "y": rect['y'] + rect['height'] // 2, "duration": 50})

    def _toggle_session_refresh(self, target_index):
        """切换场次刷新票档：点相邻场次再点回目标场次，触发票档重新加载"""
        try:
            cont = self.driver.find_element(By.ID, 'cn.damai:id/project_detail_perform_flowlayout')
            items = cont.find_elements(By.XPATH, './/*[@clickable="true"]')
            if len(items) == 0:
                return False
            # 相邻场次：优先上一个，第一个场次则用下一个
            neighbor = target_index - 1 if target_index > 0 else 1
            if neighbor >= len(items):
                neighbor = len(items) - 2 if len(items) >= 2 else 0
            if neighbor < 0:
                neighbor = 0
            self._tap_element_center(items[neighbor])
            time.sleep(1.2)
            # 点回目标场次
            items = cont.find_elements(By.XPATH, './/*[@clickable="true"]')
            if target_index < len(items):
                self._tap_element_center(items[target_index])
                time.sleep(1.2)
            return True
        except Exception as e:
            print(f"切换场次刷新失败: {e}")
            return False

    def _wait_stock_ready(self, session_index, stop_event=None, max_rounds=300):
        """缺货时通过切换场次刷新，直到有票（或停止/超时）"""
        rounds = 0
        while True:
            if stop_event is not None and stop_event.is_set():
                return False
            if not self._check_out_of_stock():
                print("✅ 检测到有票！")
                return True
            if rounds >= max_rounds:
                print("刷新次数达到上限，仍未等到有票")
                return False
            self._toggle_session_refresh(session_index)
            print(f"缺货中，切换场次刷新（第{rounds + 1}次）...")
            rounds += 1

    def _dismiss_success_dialog(self):
        """退出"提交成功/缺货登记"页面（点"知道了"或返回）"""
        for _ in range(3):
            try:
                # 点"知道了"按钮
                els = self.driver.find_elements(AppiumBy.ANDROID_UIAUTOMATOR,
                    'new UiSelector().textContains("知道了")')
                if els:
                    self._tap_element_center(els[0])
                    time.sleep(0.6)
                    continue
                # 或检测到"提交成功"文字，按返回
                if self.driver.find_elements(AppiumBy.ANDROID_UIAUTOMATOR,
                    'new UiSelector().textContains("提交成功")'):
                    self.driver.back()
                    time.sleep(0.6)
                    continue
                break
            except Exception:
                break

    def _do_purchase_flow(self, stop_event=None):
        """执行抢票主流程（不退出驱动，供开售秒抢模式复用）"""
        try:
            print("开始抢票流程...")
            start_time = time.time()

            # 0. 安全检查：页面必须匹配配置中的演出/城市，防止在错误演出上下单
            if not self._check_show_match():
                print("⚠️ 当前页面与配置的演出不匹配！")
                print(f"   配置: {self.config.keyword} / {self.config.city}")
                print("   请先在手机上进入目标演出的选票页，再运行")
                return False

            # 0.3 预约状态检测：未开售的预约页点进去也买不了，提示用开售秒抢模式
            if self._is_reserve_state():
                print("⚠️ 当前为「预约/倒计时」状态（尚未开售），无法下单！")
                print("   请使用「开售秒抢」模式：它会持续刷新页面，")
                print("   检测到按钮变为「立即预定/立即购买」的瞬间自动抢票")
                return False

            # 0.5 若停在详情页，先点购买栏进入选票页
            if not self._enter_selection_page():
                return False

            # 0.6 若卡在"提交成功/缺货登记"页面，先退出（点"知道了"/返回）
            self._dismiss_success_dialog()

            # 1. 场次选择 - 新版UI按位置点击场次卡片（日期文字不在无障碍树里，只能按位置）
            print("选择场次...")
            if self.config.session_index is not None:
                if not self.click_container_item('cn.damai:id/project_detail_perform_flowlayout', self.config.session_index):
                    print("场次选择失败，尝试继续")

            # 1.5 缺货检测：选完场次后若票价缺货，切换场次刷新直到有票（开售秒抢等待补货）
            if self._check_out_of_stock():
                print("⚠️ 该场次票价当前缺货，切换场次刷新等待有票...")
                if not self._wait_stock_ready(self.config.session_index, stop_event=stop_event):
                    print("未等到有票")
                    return False

            # 2. 票价选择 - 新版UI按位置点击票价卡片（选完场次后票价区才出现，等3秒）
            print("选择票价...")
            if not self.click_container_item('cn.damai:id/layout_price', self.config.price_index, timeout=3):
                # 备用方案：旧版UI的票价容器
                try:
                    price_container = WebDriverWait(self.driver, 2).until(
                        EC.presence_of_element_located((By.ID, 'cn.damai:id/project_detail_perform_price_flowlayout')))
                    target_price = price_container.find_element(
                        AppiumBy.ANDROID_UIAUTOMATOR,
                        f'new UiSelector().className("android.widget.FrameLayout").index({self.config.price_index}).clickable(true)'
                    )
                    self.driver.execute_script('mobile: clickGesture', {'elementId': target_price.id})
                except Exception as e:
                    print(f"票价选择失败: {e}")
                    return False

            # 2.2 防误点保护：若弹出"提交缺货登记"对话框（点到缺货票档），关闭，切换场次刷新等有票
            try:
                if self.driver.find_elements(AppiumBy.ANDROID_UIAUTOMATOR,
                    'new UiSelector().textContains("提交缺货登记")'):
                    print("⚠️ 该票价缺货，关闭对话框，切换场次刷新等待有票...")
                    self.driver.back()
                    time.sleep(self.config.delay('step'))
                    if self._wait_stock_ready(self.config.session_index, stop_event=stop_event):
                        # 有票了，重新选一次票价
                        self.click_container_item('cn.damai:id/layout_price', self.config.price_index, timeout=3)
                    else:
                        return False
            except Exception:
                pass

            # 2.5 设置购票数量（选票页票档下方 = 观演人数，最多6张）
            quantity_set = self.set_ticket_quantity()

            # 3. 点击底部购买/预约按钮（新版UI：btn_buy_view），然后等订单确认页出现
            print("点击购买按钮...")
            if not self.ultra_fast_click(By.ID, "cn.damai:id/btn_buy_view"):
                book_fallbacks = [
                    (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textMatches(".*立即购买.*|.*预约.*|.*购买.*")'),
                    (By.XPATH, '//*[contains(@text,"立即购买") or contains(@text,"预约") or contains(@text,"购买")]'),
                ]
                self.smart_wait_and_click(*book_fallbacks[0], book_fallbacks[1:])
            if not self.wait_for_text(['立即提交', '确认购买'], timeout=5):
                print("未检测到订单确认页，尝试继续")

            # 4. 数量选择（选票页已设好数量则跳过；兜底：订单页上的数量控件）
            if not quantity_set:
                print("选择数量...")
                if self.driver.find_elements(by=By.ID, value='layout_num'):
                    clicks_needed = min(len(self.config.users), 6) - 1
                    if clicks_needed > 0:
                        try:
                            plus_button = self.driver.find_element(By.ID, 'img_jia')
                            for i in range(clicks_needed):
                                rect = plus_button.rect
                                x = rect['x'] + rect['width'] // 2
                                y = rect['y'] + rect['height'] // 2
                                self.driver.execute_script("mobile: clickGesture", {
                                    "x": x,
                                    "y": y,
                                    "duration": 50
                                })
                                time.sleep(0.02)
                        except Exception as e:
                            print(f"快速点击加号失败: {e}")

            # 5. 选择观演人 - 点击后验证checkbox，未勾上自动重试，已勾选的跳过
            print("选择用户...")
            time.sleep(self.config.delay('step'))  # 等待观演人列表加载完成
            for user in self.config.users:
                try:
                    if self._is_user_checked(user):
                        print(f"✅ 用户已勾选: {user}")
                        continue
                    for attempt in range(2):
                        el = WebDriverWait(self.driver, 3).until(
                            EC.presence_of_element_located(
                                (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().text("{user}")')))
                        rect = el.rect
                        self.driver.execute_script("mobile: clickGesture", {
                            "x": rect['x'] + rect['width'] // 2,
                            "y": rect['y'] + rect['height'] // 2, "duration": 50})
                        time.sleep(self.config.delay('step'))
                        if self._is_user_checked(user):
                            print(f"✅ 已勾选: {user}")
                            break
                        print(f"点击后未勾选，重试: {user}")
                except Exception as e:
                    print(f"选择用户失败 {user}: {e}")

            # 6. 提交订单
            print("提交订单...")
            if not self.config.if_commit_order:
                print("配置 if_commit_order=false，已跳过最终提交（试运行模式）")
                print("抢票流程演练完成，未提交订单")
                return True
            submit_selectors = [
                (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("立即提交")'),
                (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textMatches(".*提交.*|.*确认.*")'),
                (By.XPATH, '//*[contains(@text,"提交")]')
            ]
            if not self.smart_wait_and_click(*submit_selectors[0], submit_selectors[1:], timeout=3):
                print("提交按钮未找到/未点击")
            # 检测是否跳转支付页（订单提交成功 = 锁票）
            time.sleep(1.5)
            try:
                act = self.driver.current_activity
                if 'pay' in act.lower():
                    print("✅ 订单已提交成功！已跳转支付页面，请立即完成付款锁票！")
                else:
                    print("提交后当前页面:", act)
            except Exception:
                pass

            end_time = time.time()
            print(f"抢票流程完成，耗时: {end_time - start_time:.2f}秒")
            return True

        except Exception as e:
            print(f"抢票过程发生错误: {e}")
            return False

    def set_ticket_quantity(self):
        """选票页票档下方设置购票数量 = 观演人数（最多6张，受页面限购限制）"""
        target = len(self.config.users)
        if target > 6:
            print(f"⚠️ 观演人 {target} 人超过6张上限，按6张设置")
            target = 6

        # 等待数量选择器出现（选完票价后从底部滑出）
        try:
            WebDriverWait(self.driver, 2).until(
                EC.presence_of_element_located((By.ID, 'cn.damai:id/img_jia')))
        except Exception:
            pass

        # 读取页面限购数（"每笔订单限购4张"），用作硬上限
        try:
            els = self.driver.find_elements(By.ID, 'cn.damai:id/tv_limit_num')
            if els:
                m = re.search(r'限购\s*(\d+)', els[0].text)
                if m:
                    limit = int(m.group(1))
                    print(f"页面限购: {limit} 张")
                    target = min(target, limit)
        except Exception:
            pass

        def read_count():
            """读取当前数量（tv_num 显示如 '1张'）"""
            try:
                els = self.driver.find_elements(By.ID, 'cn.damai:id/tv_num')
                if els:
                    m = re.search(r'(\d+)', els[0].text)
                    if m:
                        return int(m.group(1))
            except Exception:
                pass
            return None

        current = read_count()
        if current is None:
            if target <= 1:
                print(f"购票数量: 1 张（观演人 {len(self.config.users)} 人，默认）")
                return True
            print("无法读取当前数量，尝试直接点击加号...")
            ok = True
            for i in range(target - 1):
                try:
                    plus = self.driver.find_element(By.ID, 'cn.damai:id/img_jia')
                    rect = plus.rect
                    self.driver.execute_script("mobile: clickGesture", {
                        "x": rect['x'] + rect['width'] // 2,
                        "y": rect['y'] + rect['height'] // 2, "duration": 30})
                    time.sleep(self.config.delay('click'))
                except Exception:
                    ok = False
                    break
            return ok

        if current >= target:
            print(f"购票数量已是 {current} 张（目标 {target} 张），无需调整")
            return True

        print(f"购票数量: 当前 {current} 张，目标 {target} 张，点击加号 {target - current} 次...")
        for i in range(target - current):
            try:
                plus = self.driver.find_element(By.ID, 'cn.damai:id/img_jia')
                rect = plus.rect
                self.driver.execute_script("mobile: clickGesture", {
                    "x": rect['x'] + rect['width'] // 2,
                    "y": rect['y'] + rect['height'] // 2, "duration": 30})
                time.sleep(self.config.delay('click'))
            except Exception:
                break
        final = read_count()
        ok = final is not None and final >= target
        print(f"调整后数量: {final} 张" + (" ✅" if ok else " ⚠️ 未达到目标"))
        return ok

    def run_ticket_grabbing(self):
        """普通模式：执行抢票主流程，结束后退出驱动"""
        try:
            return self._do_purchase_flow()
        finally:
            time.sleep(0.3)  # 给最后的操作一点时间
            try:
                self.driver.quit()
            except Exception:
                pass

    def run_with_retry(self, max_retries=3):
        """带重试机制的抢票"""
        for attempt in range(max_retries):
            print(f"第 {attempt + 1} 次尝试...")
            if self.run_ticket_grabbing():
                print("抢票成功！")
                return True
            else:
                print(f"第 {attempt + 1} 次尝试失败")
                if attempt < max_retries - 1:
                    print("0.3秒后重试...")
                    time.sleep(0.3)
                    # 重新初始化驱动
                    try:
                        self.driver.quit()
                    except:
                        pass
                    self._setup_driver()

        print("所有尝试均失败")
        return False

    def _check_on_sale(self):
        """毫秒级检测是否可购买：详情页/选票页购买按钮可点击，或出现购买文字；缺货/预约状态继续等待"""
        try:
            # 缺货/无票状态 → 不可购买，继续等待补货
            if self.driver.find_elements(
                AppiumBy.ANDROID_UIAUTOMATOR,
                'new UiSelector().textMatches("缺货登记|无票")'):
                return False
            # 预约状态的特征文字存在 → 未开售（预约想看/可预约，按钮是"预约"不是"购买"）
            if self.driver.find_elements(
                AppiumBy.ANDROID_UIAUTOMATOR,
                'new UiSelector().textMatches("预约想看|可预约")'):
                return False
            # 信号1：详情页购买栏容器变为可点击（已预约→立即预定）
            if self.driver.find_elements(
                AppiumBy.ANDROID_UIAUTOMATOR,
                'new UiSelector().resourceId("cn.damai:id/trade_project_detail_purchase_status_bar_container_fl").clickable(true)'):
                print("[检测] 详情页购买按钮已变为可点击（已预约→立即预定）")
                return True
            # 信号2：选票页购买按钮变为可点击
            if self.driver.find_elements(
                AppiumBy.ANDROID_UIAUTOMATOR,
                'new UiSelector().resourceId("cn.damai:id/btn_buy_view").clickable(true)'):
                print("[检测] 选票页购买按钮已变为可点击")
                return True
            # 信号3：出现"立即购买/立即抢票/立即预定"文字
            if self.driver.find_elements(
                AppiumBy.ANDROID_UIAUTOMATOR,
                'new UiSelector().textMatches("立即购买|立即抢票|立即预定")'):
                print("[检测] 出现立即购买/立即预定文字")
                return True
        except Exception:
            pass
        return False

    def _probe_click_cta(self):
        """探测点击：点一下详情页购买栏。
        进入的若是「预约页」（已预约状态）→ 立刻返回，继续刷新等待；
        进入真实购买页 → 可购买，继续抢票流程"""
        try:
            if not self._check_on_detail_page():
                return False
            el = self.driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR,
                'new UiSelector().resourceId("cn.damai:id/trade_project_detail_purchase_status_bar_container_fl")')
            rect = el.rect
            self.driver.execute_script("mobile: clickGesture", {
                "x": rect['x'] + rect['width'] // 2,
                "y": rect['y'] + rect['height'] // 2, "duration": 50})
            time.sleep(1.5)
            if not self._check_on_right_page():
                return False  # 没进入选票页（按钮无效，还没开售）
            # 进入了选票页：若是预约页（已预约状态）→ 返回详情页继续等待
            if self._is_reserve_state():
                print("仍是预约状态（已预约），返回详情页继续刷新等待...")
                self.driver.back()
                time.sleep(0.5)
                return False
            print("✅ 探测点击成功：已进入可购买选票页，继续抢票流程")
            return True
        except Exception:
            pass
        return False

    def _reset_to_detail(self):
        """从选票页/订单页退回详情页（流程失败后复位，避免卡在中间状态）"""
        for _ in range(4):
            try:
                if self._check_on_detail_page() or not self._check_on_right_page():
                    # 不在选票页（详情页或其他）就算复位完成；订单页会通过检查被退回
                    if 'ProjectDetailActivity' in self.driver.current_activity:
                        return
                self.driver.back()
                time.sleep(0.8)
            except Exception:
                break

    def _wait_for_sale(self, poll_interval=0.2, refresh_interval=2.0, stop_event=None):
        """等待开售：每轮刷新后点击试探判断按钮状态：
        已预约 → 退回继续刷新；立即预定/立即购买 → 点进去开抢"""
        last_refresh = time.time()
        attempts = 0
        while True:
            if stop_event is not None and stop_event.is_set():
                print("⏹ 已停止（等待开售中断）")
                return False
            attempts += 1
            # ① 文字检测（毫秒级）：按钮文字能读到时直接命中，无需试探
            if self._check_on_sale():
                print(f"🔥 检测到开售！第 {attempts} 次轮询命中")
                return True
            # ② 每轮：刷新页面 → 点击试探判断当前状态
            if time.time() - last_refresh >= refresh_interval:
                last_refresh = time.time()  # 从本轮开始计时
                try:
                    self.driver.background_app(-1)
                    time.sleep(0.1)
                    self.driver.activate_app('cn.damai')
                    print("已触发页面刷新（前后台切换）")
                except Exception as e:
                    print(f"页面刷新失败: {e}")
                time.sleep(0.5)
                # 点击试探：立即预定→开抢；已预约→退回继续下一轮
                if self._probe_click_cta():
                    return True
            time.sleep(poll_interval)

    def _check_on_right_page(self):
        """检查当前是否停在选票页（有场次/票档容器的页面）"""
        try:
            if self.driver.find_elements(By.ID, 'cn.damai:id/layout_price') or \
               self.driver.find_elements(By.ID, 'cn.damai:id/project_detail_perform_flowlayout'):
                return True
        except Exception:
            pass
        return False

    def _check_show_match(self):
        """安全检查：当前页面是否与配置中的演出/城市匹配，防止在错误的演出上下单"""
        try:
            if self.driver.find_elements(AppiumBy.ANDROID_UIAUTOMATOR,
                f'new UiSelector().textContains("{self.config.keyword}")'):
                return True
            if self.driver.find_elements(AppiumBy.ANDROID_UIAUTOMATOR,
                f'new UiSelector().textContains("{self.config.city}")'):
                return True
        except Exception:
            pass
        return False

    def _check_on_detail_page(self):
        """检查是否停在演出详情页（有购买栏容器）"""
        try:
            if self.driver.find_elements(By.ID, 'cn.damai:id/trade_project_detail_purchase_status_bar_container_fl'):
                return True
        except Exception:
            pass
        return False

    def run_wait_sale(self, poll_interval=None, refresh_interval=None, stop_event=None):
        """开售秒抢模式：保持会话毫秒级轮询+持续刷新页面，检测到开售立即执行完整抢票流程"""
        if poll_interval is None:
            poll_interval = self.config.delay('poll')
        if refresh_interval is None:
            refresh_interval = self.config.delay('refresh')
        print("=== 开售秒抢模式启动 ===")
        print(f"轮询间隔: {poll_interval * 1000:.0f}毫秒 | 强制刷新间隔: {refresh_interval:.0f}秒")
        if not self._check_show_match():
            print("⚠️ 当前页面与配置的演出不匹配！请先进入目标演出页面（详情页或选票页均可）")
        if self._check_on_right_page():
            print("✅ 已在选票页（能看到场次+票档），将持续刷新并等待开售")
        elif self._check_on_detail_page():
            print("✅ 已在演出详情页（已预约/倒计时），将持续刷新并等待开售")
        else:
            print("⚠️ 未识别当前页面，请停在目标演出的详情页或选票页")
        print("等待开售中...（保持手机亮屏，不要锁屏）")
        while True:
            if stop_event is not None and stop_event.is_set():
                print("⏹ 已停止")
                return False
            try:
                self._reset_to_detail()
                if not self._wait_for_sale(poll_interval, refresh_interval, stop_event):
                    return False
                if self._do_purchase_flow(stop_event=stop_event):
                    print("🎉 抢票成功！订单已提交，请立即在手机支付页面完成付款！")
                    return True
                print("抢票流程未完成，0.3秒后重试...")
            except Exception as e:
                print(f"开售抢票出错: {e}，0.3秒后重试...")
            time.sleep(0.3)


# 使用示例
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="大麦抢票")
    parser.add_argument("--wait-sale", action="store_true", help="开售秒抢模式：等待开售，开售瞬间自动抢")
    parser.add_argument("--poll", type=float, default=0.2, help="开售检测轮询间隔（秒），默认0.2")
    parser.add_argument("--refresh", type=float, default=2.0, help="页面强制刷新间隔（秒），默认2")
    parser.add_argument("--test-detect", action="store_true", help="测试开售检测逻辑，只检测一次并退出")
    parser.add_argument("--test-quantity", action="store_true", help="测试数量选择器定位，打印找到的控件并退出")
    args = parser.parse_args()

    bot = DamaiBot()
    if args.test_quantity:
        print("=== 数量选择器诊断 ===")
        print(f"配置观演人: {bot.config.users} -> 目标 {min(len(bot.config.users), 6)} 张")
        print("查找+号按钮:", end=" ")
        found = bot.set_ticket_quantity()
        print("诊断结果: 找到加号按钮" if found else "诊断结果: 未找到加号按钮（可能未开售）")
        try:
            bot.driver.quit()
        except Exception:
            pass
    elif args.test_detect:
        print("开售检测结果:", bot._check_on_sale())
        try:
            bot.driver.quit()
        except Exception:
            pass
    elif args.wait_sale:
        bot.run_wait_sale(poll_interval=args.poll, refresh_interval=args.refresh)
    else:
        bot.run_with_retry(max_retries=3)
