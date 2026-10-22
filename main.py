import sys
import time

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QGroupBox,
    QMessageBox, QComboBox, QGridLayout
)

from DrissionPage import Chromium


# ==================== 筛选条件映射表 ====================
FILTER_MAPS = {
    '求职类型': {
        '不限': 'sel-job-rec-jobType-0',
        '全职': 'sel-job-rec-jobType-1901',
        '兼职': 'sel-job-rec-jobType-1903',
        '实习': 'sel-job-rec-jobType-1902',
    },
    '薪资待遇': {
        '不限': 'sel-job-rec-salary-0',
        '3K以下': 'sel-job-rec-salary-402',
        '3-5K': 'sel-job-rec-salary-403',
        '5-10K': 'sel-job-rec-salary-404',
        '10-20K': 'sel-job-rec-salary-405',
        '20-50K': 'sel-job-rec-salary-406',
        '50K以上': 'sel-job-rec-salary-407',
    },
    '工作经验': {
        '不限': 'sel-job-rec-exp-0',
        '在校生': 'sel-job-rec-exp-108',
        '应届生': 'sel-job-rec-exp-102',
        '经验不限': 'sel-job-rec-exp-101',
        '1年以内': 'sel-job-rec-exp-103',
        '1-3年': 'sel-job-rec-exp-104',
        '3-5年': 'sel-job-rec-exp-105',
        '5-10年': 'sel-job-rec-exp-106',
        '10年以上': 'sel-job-rec-exp-107',
    },
    '学历要求': {
        '不限': 'sel-job-rec-degree-0',
        '初中及以下': 'sel-job-rec-degree-209',
        '中专/中技': 'sel-job-rec-degree-208',
        '高中': 'sel-job-rec-degree-206',
        '大专': 'sel-job-rec-degree-202',
        '本科': 'sel-job-rec-degree-203',
        '硕士': 'sel-job-rec-degree-204',
        '博士': 'sel-job-rec-degree-205',
    },
    '公司规模': {
        '不限': 'sel-job-rec-scale-0',
        '0-20人': 'sel-job-rec-scale-301',
        '20-99人': 'sel-job-rec-scale-302',
        '100-499人': 'sel-job-rec-scale-303',
        '500-999人': 'sel-job-rec-scale-304',
        '1000-9999人': 'sel-job-rec-scale-305',
        '10000人以上': 'sel-job-rec-scale-306',
    },
}

# 下拉框里“不限”的统一显示文本，用于判断是否需要真的点击筛选
UNLIMITED_TEXT = '不限'


# ==================== 筛选函数（与原来一致） ====================
def select_filter(tab, filter_name, option_text, log_func=print):
    """选择筛选条件（直接用 JS 触发，避免重复点击和等待）"""
    if filter_name not in FILTER_MAPS:
        log_func(f'❌ 不支持的筛选: {filter_name}')
        return False

    option_map = FILTER_MAPS[filter_name]
    if option_text not in option_map:
        log_func(f'❌ {filter_name} 不支持选项: {option_text}')
        return False

    ka_value = option_map[option_text]

    # 1. 点击筛选框
    filter_ele = tab.ele(f'text:{filter_name}')
    if not filter_ele:
        log_func(f'❌ 没找到筛选框: {filter_name}')
        return False
    filter_ele.click(by_js=False)
    tab.wait(1)

    # 2. 直接用 JS 触发选项
    tab.run_js(f'''
        var el = document.querySelector('[ka="{ka_value}"]');
        if (el) {{
            el.dispatchEvent(new MouseEvent('mousedown', {{bubbles: true}}));
            el.dispatchEvent(new MouseEvent('mouseup', {{bubbles: true}}));
            el.dispatchEvent(new MouseEvent('click', {{bubbles: true}}));
        }}
    ''')
    tab.wait(2)

    log_func(f'✅ 已选择: {filter_name} = {option_text}')
    return True


def apply_filters(tab, filters, log_func=print):
    """批量应用筛选（跳过“不限”）"""
    for filter_name, option_text in filters.items():
        if option_text == UNLIMITED_TEXT:
            log_func(f'⏭️ 跳过筛选: {filter_name} = 不限')
            continue
        select_filter(tab, filter_name, option_text, log_func)
        time.sleep(1)


# ==================== 后台工作线程 ====================
class AutoApplyWorker(QThread):
    log_signal = pyqtSignal(str)
    count_signal = pyqtSignal(int)
    finished_signal = pyqtSignal()

    def __init__(self, keyword: str, greeting: str, filters: dict):
        super().__init__()
        self.keyword = keyword
        self.greeting = greeting
        self.filters = filters
        self._running = True

    def stop(self):
        self._running = False

    def log(self, msg):
        self.log_signal.emit(msg)

    def run(self):
        try:
            browser = Chromium()
            tab = browser.latest_tab
            tab.get('https://www.zhipin.com')

            # 搜索岗位
            self.log(f'🔍 搜索岗位：{self.keyword}')
            tab.ele('.ipt-search').input(self.keyword)
            tab.ele('.btn.btn-search').click()
            tab.wait(2)

            # 应用筛选
            self.log('🎛️ 开始应用筛选条件...')
            apply_filters(tab, self.filters, self.log)
            self.log('🎛️ 筛选条件应用完成\n')

            processed = set()
            count = 0

            while self._running:
                job_list = tab.eles('.card-area')
                if not job_list:
                    self.log('⚠️ 未找到岗位列表，结束')
                    break

                job = None
                for j in job_list:
                    url = j.ele('.job-name').attr('href')
                    if url not in processed:
                        job = j
                        break

                if not job:
                    self.log('✅ 全部处理完，结束')
                    break

                url = job.ele('.job-name').attr('href')
                self.log(f'处理: {url}')

                try:
                    job.click()
                    tab.wait(1)

                    chat = tab.ele('.op-btn.op-btn-chat')
                    if chat and chat.text.strip() == '立即沟通':
                        chat.click()
                        tab.wait(1)

                        sure = tab.ele('.default-btn.sure-btn')
                        if sure:
                            sure.click()
                            tab.wait(1)

                        chat_input = tab.ele('.chat-input')
                        if chat_input:
                            chat_input.input(self.greeting)
                            tab.wait(1)
                            tab.actions.key_down('ENTER')
                            tab.actions.key_up('ENTER')
                            tab.wait(1)

                        for ele in tab.eles('.close'):
                            if ele.states.is_clickable:
                                ele.click()
                                break

                        count += 1
                        self.count_signal.emit(count)
                        self.log(f'✅ 已投递 {count} 个岗位')

                    processed.add(url)

                    while '/web/geek/chat' in tab.url and self._running:
                        tab.back()
                        tab.wait(2)

                except Exception as e:
                    self.log(f'❌ 出错: {e}')
                    processed.add(url)
                    while '/web/geek/chat' in tab.url and self._running:
                        tab.back()
                        tab.wait(2)

                tab.wait(1)

            self.log(f'\n共处理 {len(processed)} 个')

        except Exception as e:
            self.log(f'❌ 严重错误: {e}')
        finally:
            self.finished_signal.emit()


# ==================== 主界面 ====================
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.filter_combos = {}   # 保存五个下拉框，key 是筛选名
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('BOSS 自动投递助手')
        self.resize(640, 620)

        main_layout = QVBoxLayout()

        # ---------- 基础配置 ----------
        base_group = QGroupBox('基础配置')
        base_layout = QVBoxLayout()

        kw_layout = QHBoxLayout()
        kw_layout.addWidget(QLabel('岗位名称：'))
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText('例如：服务员')
        self.keyword_input.setText('服务员')
        kw_layout.addWidget(self.keyword_input)
        base_layout.addLayout(kw_layout)

        greet_layout = QHBoxLayout()
        greet_layout.addWidget(QLabel('招呼语：'))
        self.greeting_input = QLineEdit()
        self.greeting_input.setPlaceholderText('例如：你好')
        self.greeting_input.setText('你好')
        greet_layout.addWidget(self.greeting_input)
        base_layout.addLayout(greet_layout)

        base_group.setLayout(base_layout)
        main_layout.addWidget(base_group)

        # ---------- 筛选条件 ----------
        filter_group = QGroupBox('筛选条件')
        filter_layout = QGridLayout()

        # 按 FILTER_MAPS 的顺序生成下拉框，两列布局
        filter_names = list(FILTER_MAPS.keys())
        for idx, name in enumerate(filter_names):
            row = idx // 2
            col = (idx % 2) * 2

            label = QLabel(f'{name}：')
            combo = QComboBox()
            combo.addItems(list(FILTER_MAPS[name].keys()))
            # 默认选“不限”
            combo.setCurrentText(UNLIMITED_TEXT)
            self.filter_combos[name] = combo

            filter_layout.addWidget(label, row, col)
            filter_layout.addWidget(combo, row, col + 1)

        filter_group.setLayout(filter_layout)
        main_layout.addWidget(filter_group)

        # ---------- 按钮 ----------
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton('▶ 开始投递')
        self.start_btn.clicked.connect(self.start_apply)
        self.stop_btn = QPushButton('⏹ 停止')
        self.stop_btn.clicked.connect(self.stop_apply)
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        main_layout.addLayout(btn_layout)

        # ---------- 状态 ----------
        self.status_label = QLabel('已投递：0 个')
        self.status_label.setStyleSheet('font-size: 14px; font-weight: bold; color: #2e7d32;')
        main_layout.addWidget(self.status_label)

        # ---------- 日志 ----------
        log_group = QGroupBox('运行日志')
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)

        self.setLayout(main_layout)

    def get_selected_filters(self) -> dict:
        """读取界面上五个下拉框的当前选择"""
        return {name: combo.currentText() for name, combo in self.filter_combos.items()}

    def set_ui_enabled(self, enabled: bool):
        self.start_btn.setEnabled(enabled)
        self.stop_btn.setEnabled(not enabled)
        self.keyword_input.setEnabled(enabled)
        self.greeting_input.setEnabled(enabled)
        for combo in self.filter_combos.values():
            combo.setEnabled(enabled)

    def start_apply(self):
        keyword = self.keyword_input.text().strip()
        greeting = self.greeting_input.text().strip()

        if not keyword:
            QMessageBox.warning(self, '提示', '请输入岗位名称')
            return
        if not greeting:
            QMessageBox.warning(self, '提示', '请输入招呼语')
            return

        filters = self.get_selected_filters()

        self.log_text.clear()
        self.status_label.setText('已投递：0 个')
        self.set_ui_enabled(False)

        self.log_text.append(f'📋 岗位：{keyword}')
        self.log_text.append(f'💬 招呼语：{greeting}')
        self.log_text.append('🎛️ 筛选条件：')
        for k, v in filters.items():
            self.log_text.append(f'    {k} = {v}')
        self.log_text.append('')

        self.worker = AutoApplyWorker(keyword, greeting, filters)
        self.worker.log_signal.connect(self.append_log)
        self.worker.count_signal.connect(self.update_count)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def stop_apply(self):
        if self.worker:
            self.worker.stop()
            self.append_log('⏹ 正在停止...')

    def append_log(self, text: str):
        self.log_text.append(text)

    def update_count(self, count: int):
        self.status_label.setText(f'已投递：{count} 个')

    def on_finished(self):
        self.set_ui_enabled(True)
        self.append_log('🏁 任务结束')


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
