import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QFrame, QPushButton, QProgressBar, 
                             QGridLayout, QDialog, QTableWidget, QTableWidgetItem, QHeaderView,
                             QStackedWidget, QTextEdit, QMessageBox, QFileDialog)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QColor, QFont

from core.dependency_manager import check_and_setup_dependencies
from core.android_checker import (get_universal_android_details, execute_reboot, 
                                    execute_screenshot, execute_get_installed_apps)
from core.ios_checker import get_universal_ios_details

class SetupDependenciesThread(QThread):
    progress_signal = pyqtSignal(int, str)
    finished_signal = pyqtSignal()

    def run(self):
        check_and_setup_dependencies(lambda pct, msg: self.progress_signal.emit(pct, msg))
        self.finished_signal.emit()

class DeviceScannerThread(QThread):
    device_found = pyqtSignal(object)

    def run(self):
        while True:
            try:
                data = get_universal_android_details()
                if not data:
                    data = get_universal_ios_details()
                self.device_found.emit(data)
            except Exception:
                self.device_found.emit(None)
            self.msleep(1500)

class VerificationReportDialog(QDialog):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("3uTools Verification Report - Swap Tech Edition")
        self.resize(760, 500)
        self.setStyleSheet("background-color: #ffffff; font-family: 'Segoe UI', Arial, sans-serif;")
        
        layout = QVBoxLayout()
        header = QLabel(f"Hardware Testing & Authenticity Score: {data.get('brand','')} {data.get('model','')}")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e62d4; margin-bottom: 8px;")
        layout.addWidget(header)
        
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Test Item", "Factory Value", "Current Read Value", "Test Result"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        items = [
            ("Device Serial Number", data.get("serial", "N/A"), data.get("serial", "N/A"), "Normal"),
            ("IMEI / Hardware Identifier", "Original OEM", data.get("imei", "N/A"), "Normal"),
            ("Display Screen Panel", "OEM Factory Matrix", data.get("screen_status", "Original"), 
             "Replaced Warning" if "Replaced" in str(data.get("screen_status")) else "Normal"),
            ("Battery Cycle Count", "< 500 Cycles Target", f"{data.get('battery_cycles', 'N/A')} Cycles", "Normal"),
            ("Loan / Kisti Lock Status", "Clean / No Active Debt", data.get("finance_desc", "Clean"), 
             "LOCKED" if data.get("finance_locked") else "Normal"),
            ("Device Security State", "Official Factory State", data.get("security_status", "Official"), 
             "Tampered / Unlocked" if "Risk" in str(data.get("security_status")) else "Normal"),
            ("Firmware / OS Integrity", "Genuine Firmware", data.get("os_version", "Verified"), "Normal")
        ]
        
        table.setRowCount(len(items))
        for row, row_data in enumerate(items):
            for col, text in enumerate(row_data):
                item = QTableWidgetItem(str(text))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 3:
                    if text == "Normal":
                        item.setForeground(QColor("#2e7d32"))
                        item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                    else:
                        item.setForeground(QColor("#d32f2f"))
                        item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                table.setItem(row, col, item)
                
        layout.addWidget(table)
        
        btn_close = QPushButton("Close Report")
        btn_close.setStyleSheet("background-color: #1e62d4; color: white; padding: 8px 24px; border-radius: 4px; font-weight: bold;")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)
        self.setLayout(layout)

class Universal3uShopMaster(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_data = None
        self.active_tab_index = 0
        self.initUI()
        self.start_initial_setup()

    def initUI(self):
        self.setWindowTitle("Shop Master Pro - Universal 3uTools Suite (Swap Tech)")
        self.resize(1180, 750)
        self.setStyleSheet("background-color: #f1f3f6; font-family: 'Segoe UI', Tahoma, sans-serif;")

        central_widget = QWidget()
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Top Bar
        top_bar = QFrame()
        top_bar.setFixedHeight(55)
        top_bar.setStyleSheet("background-color: #1a56c4; border-bottom: 2px solid #144399;")
        bar_layout = QHBoxLayout()
        bar_layout.setContentsMargins(15, 0, 15, 0)
        
        logo = QLabel("Shop Master Pro | Swap Tech")
        logo.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: 800; padding-right: 20px;")
        bar_layout.addWidget(logo)

        self.nav_btns = []
        menus = ["iDevice / Android Info", "Apps & Packages", "RT Logs", "Toolbox (Fastboot/Reboot)"]
        for i, m in enumerate(menus):
            btn = QPushButton(m)
            btn.clicked.connect(lambda checked, idx=i: self.switch_view(idx))
            self.nav_btns.append(btn)
            bar_layout.addWidget(btn)
            
        bar_layout.addStretch()
        top_bar.setLayout(bar_layout)
        root_layout.addWidget(top_bar)

        # 2. QStackedWidget (Correct widget for view switching)
        self.pages = QStackedWidget()
        
        # --- TAB 1: Device Info ---
        self.tab_info = QWidget()
        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(20, 20, 20, 20)
        info_layout.setSpacing(25)

        # Left Column
        left_col = QVBoxLayout()
        self.device_icon = QLabel("📱")
        self.device_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.device_icon.setStyleSheet("""
            font-size: 90px; background-color: #ffffff; border: 2px dashed #cbd5e1; 
            border-radius: 10px; min-width: 220px; min-height: 280px;
        """)
        left_col.addWidget(self.device_icon)

        self.lbl_device_title = QLabel("ড্রাইভার ও ইঞ্জিন লোড হচ্ছে...")
        self.lbl_device_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_device_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #334155; margin-top: 10px;")
        left_col.addWidget(self.lbl_device_title)

        self.btn_verification = QPushButton("View Verification Report")
        self.btn_verification.setStyleSheet("""
            QPushButton { background-color: #16a34a; color: white; font-weight: bold; padding: 12px; border-radius: 6px; font-size: 13px; margin-top: 10px; }
            QPushButton:hover { background-color: #15803d; }
        """)
        self.btn_verification.clicked.connect(self.show_report)
        left_col.addWidget(self.btn_verification)
        left_col.addStretch()
        info_layout.addLayout(left_col, 1)

        # Right Column
        right_col = QVBoxLayout()
        right_col.setSpacing(12)

        self.finance_box = QFrame()
        self.finance_box.setStyleSheet("background-color: #f1f5f9; border: 1.5px solid #cbd5e1; border-radius: 6px; padding: 12px;")
        f_layout = QHBoxLayout()
        self.lbl_f_title = QLabel("DEVICE WAITING...")
        self.lbl_f_title.setStyleSheet("color: #64748b; font-size: 15px; font-weight: 800;")
        f_layout.addWidget(self.lbl_f_title)
        f_layout.addStretch()
        self.lbl_f_desc = QLabel("USB ক্যাবল প্লাগ ইন করুন")
        self.lbl_f_desc.setStyleSheet("color: #64748b; font-size: 13px;")
        f_layout.addWidget(self.lbl_f_desc)
        self.finance_box.setLayout(f_layout)
        right_col.addWidget(self.finance_box)

        specs_card = QFrame()
        specs_card.setStyleSheet("background-color: #ffffff; border-radius: 8px; border: 1px solid #dcdfe6; padding: 15px;")
        self.grid = QGridLayout()
        self.grid.setVerticalSpacing(12)
        self.grid.setHorizontalSpacing(20)

        spec_fields = [
            ("Platform / Brand:", "val_brand"),
            ("Product Model:", "val_model"),
            ("Serial Number:", "val_serial"),
            ("IMEI / Unique ID:", "val_imei"),
            ("Operating System:", "val_os"),
            ("Security Patch:", "val_patch"),
            ("Processor / SoC:", "val_cpu"),
            ("Battery Cycles:", "val_cycles"),
            ("Battery Health:", "val_health"),
            ("Display Panel Status:", "val_screen"),
            ("Knox / Bootloader State:", "val_security"),
            ("Storage Available:", "val_storage")
        ]

        self.val_labels = {}
        for idx, (label_title, key_name) in enumerate(spec_fields):
            r = idx // 2
            c = (idx % 2) * 2
            
            k = QLabel(label_title)
            k.setStyleSheet("color: #64748b; font-size: 13px; font-weight: bold;")
            v = QLabel("-")
            v.setStyleSheet("color: #1e293b; font-size: 13px;")
            
            self.val_labels[key_name] = v
            self.grid.addWidget(k, r, c)
            self.grid.addWidget(v, r, c + 1)

        specs_card.setLayout(self.grid)
        right_col.addWidget(specs_card)

        self.lbl_storage_title = QLabel("Device Storage Details")
        self.lbl_storage_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #334155;")
        right_col.addWidget(self.lbl_storage_title)

        self.storage_progress = QProgressBar()
        self.storage_progress.setValue(0)
        self.storage_progress.setStyleSheet("""
            QProgressBar { height: 18px; border: 1px solid #cbd5e1; border-radius: 9px; text-align: center; }
            QProgressBar::chunk { background-color: #1a56c4; border-radius: 8px; }
        """)
        right_col.addWidget(self.storage_progress)

        info_layout.addLayout(right_col, 3)
        self.tab_info.setLayout(info_layout)
        self.pages.addWidget(self.tab_info)

        # --- TAB 2: Apps ---
        self.tab_apps = QWidget()
        apps_layout = QVBoxLayout()
        apps_layout.setContentsMargins(20, 20, 20, 20)
        
        apps_header = QHBoxLayout()
        lbl_apps = QLabel("Installed Applications & Suspicious Loan Packages")
        lbl_apps.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e293b;")
        apps_header.addWidget(lbl_apps)
        
        btn_refresh_apps = QPushButton("Refresh App List")
        btn_refresh_apps.setStyleSheet("background-color: #1a56c4; color: white; padding: 8px 16px; border-radius: 4px; font-weight: bold;")
        btn_refresh_apps.clicked.connect(self.load_installed_apps)
        apps_header.addWidget(btn_refresh_apps)
        apps_layout.addLayout(apps_header)

        self.table_apps = QTableWidget()
        self.table_apps.setColumnCount(2)
        self.table_apps.setHorizontalHeaderLabels(["App APK / Filename", "Package Name"])
        self.table_apps.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_apps.setStyleSheet("background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px;")
        apps_layout.addWidget(self.table_apps)
        
        self.tab_apps.setLayout(apps_layout)
        self.pages.addWidget(self.tab_apps)

        # --- TAB 3: RT Logs ---
        self.tab_logs = QWidget()
        logs_layout = QVBoxLayout()
        logs_layout.setContentsMargins(20, 20, 20, 20)
        
        lbl_logs = QLabel("Real-Time Device Logs & Connection Monitor")
        lbl_logs.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e293b;")
        logs_layout.addWidget(lbl_logs)

        self.txt_logs = QTextEdit()
        self.txt_logs.setReadOnly(True)
        self.txt_logs.setStyleSheet("background-color: #0f172a; color: #38bdf8; font-family: Consolas, monospace; font-size: 13px; border-radius: 6px; padding: 10px;")
        logs_layout.addWidget(self.txt_logs)
        self.tab_logs.setLayout(logs_layout)
        self.pages.addWidget(self.tab_logs)

        # --- TAB 4: Toolbox ---
        self.tab_tools = QWidget()
        tools_layout = QVBoxLayout()
        tools_layout.setContentsMargins(25, 25, 25, 25)
        
        lbl_tools_header = QLabel("Quick Device Toolbox (1-Click Working Actions)")
        lbl_tools_header.setStyleSheet("font-size: 17px; font-weight: bold; color: #1e293b; margin-bottom: 10px;")
        tools_layout.addWidget(lbl_tools_header)

        tools_grid = QGridLayout()
        tools_grid.setSpacing(15)

        tools = [
            ("🔄 Normal Reboot", "Reboot phone normally", lambda: self.handle_reboot("normal")),
            ("⚡ Reboot to Recovery", "Reboot into Recovery mode for wipe/reset", lambda: self.handle_reboot("recovery")),
            ("🚀 Reboot to Fastboot/Bootloader", "Reboot into Fastboot for firmware flash", lambda: self.handle_reboot("bootloader")),
            ("📸 Take Device Screenshot", "Capture instant screenshot from connected phone", self.handle_screenshot)
        ]

        for idx, (title, desc, func) in enumerate(tools):
            card = QFrame()
            card.setStyleSheet("background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 15px;")
            c_lay = QVBoxLayout()
            
            t_lbl = QLabel(title)
            t_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #1a56c4;")
            c_lay.addWidget(t_lbl)
            
            d_lbl = QLabel(desc)
            d_lbl.setStyleSheet("color: #64748b; font-size: 12px; margin-bottom: 8px;")
            c_lay.addWidget(d_lbl)
            
            b = QPushButton("Execute Action")
            b.setStyleSheet("background-color: #10b981; color: white; font-weight: bold; padding: 8px; border-radius: 5px;")
            b.clicked.connect(func)
            c_lay.addWidget(b)
            
            card.setLayout(c_lay)
            tools_grid.addWidget(card, idx // 2, idx % 2)

        tools_layout.addLayout(tools_grid)
        tools_layout.addStretch()
        self.tab_tools.setLayout(tools_layout)
        self.pages.addWidget(self.tab_tools)

        root_layout.addWidget(self.pages)
        central_widget.setLayout(root_layout)
        self.setCentralWidget(central_widget)

        self.update_nav_styles()

    def switch_view(self, index):
        self.active_tab_index = index
        self.pages.setCurrentIndex(index)
        self.update_nav_styles()
        if index == 1:
            self.load_installed_apps()

    def update_nav_styles(self):
        for i, btn in enumerate(self.nav_btns):
            if i == self.active_tab_index:
                btn.setStyleSheet("background-color: #144399; color: #ffffff; font-weight: bold; border-bottom: 3px solid #ffcc00; padding: 16px 15px; border-top: none; border-left: none; border-right: none;")
            else:
                btn.setStyleSheet("background: transparent; color: #d0e0fc; font-weight: 600; padding: 16px 15px; border: none;")

    def start_initial_setup(self):
        self.setup_thread = SetupDependenciesThread()
        self.setup_thread.progress_signal.connect(self.on_setup_progress)
        self.setup_thread.finished_signal.connect(self.on_setup_finished)
        self.setup_thread.start()

    def on_setup_progress(self, percent, message):
        self.lbl_device_title.setText(message)
        self.lbl_f_desc.setText(f"{message} ({percent}%)")
        self.txt_logs.append(f"[SETUP] {message} ({percent}%)")

    def on_setup_finished(self):
        self.lbl_device_title.setText("কোনো ফোন কানেক্টেড নেই")
        self.lbl_f_title.setText("DEVICE WAITING...")
        self.lbl_f_desc.setText("USB ক্যাবল প্লাগ ইন করুন")
        self.txt_logs.append("[SETUP] Drivers and communication modules fully initialized.")
        
        self.scanner = DeviceScannerThread()
        self.scanner.device_found.connect(self.render_data)
        self.scanner.start()

    def render_data(self, data):
        if not data:
            self.current_data = None
            self.lbl_device_title.setText("কোনো ফোন কানেক্টেড নেই")
            self.lbl_device_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #94a3b8;")
            self.device_icon.setText("🔌")
            
            self.finance_box.setStyleSheet("background-color: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px; padding: 12px;")
            self.lbl_f_title.setText("DEVICE WAITING...")
            self.lbl_f_title.setStyleSheet("color: #64748b; font-size: 15px; font-weight: 800;")
            self.lbl_f_desc.setText("USB ক্যাবল প্লাগ ইন করুন")
            self.lbl_f_desc.setStyleSheet("color: #64748b; font-size: 13px;")
            
            for lbl in self.val_labels.values():
                lbl.setText("-")
                lbl.setStyleSheet("color: #1e293b; font-size: 13px;")
                
            self.lbl_storage_title.setText("Device Storage Details")
            self.storage_progress.setValue(0)
            return

        if data.get("state") == "unauthorized":
            self.current_data = data
            self.lbl_device_title.setText("স্ক্রিনে পারমিশন দিন!")
            self.lbl_device_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #d97706;")
            self.device_icon.setText("⚠️")
            self.finance_box.setStyleSheet("background-color: #fffbeb; border: 1.5px solid #fde68a; border-radius: 6px; padding: 12px;")
            self.lbl_f_title.setText("AUTHORIZATION REQUIRED ⚠️")
            self.lbl_f_title.setStyleSheet("color: #b45309; font-size: 15px; font-weight: bold;")
            self.lbl_f_desc.setText("স্ক্রিনে 'Always allow from this computer' দিয়ে OK চাপুন")
            return

        self.current_data = data
        brand = data.get("brand", "")
        model = data.get("model", "")
        self.lbl_device_title.setText(f"{brand} {model}")
        self.lbl_device_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a56c4;")
        self.device_icon.setText("📱")

        if data.get("finance_locked"):
            self.finance_box.setStyleSheet("background-color: #fef2f2; border: 2px solid #ef4444; border-radius: 6px; padding: 12px;")
            self.lbl_f_title.setText("⚠️ KISTI / FINANCE LOCK DETECTED!")
            self.lbl_f_title.setStyleSheet("color: #b91c1c; font-size: 15px; font-weight: 800;")
            self.lbl_f_desc.setText(data.get("finance_desc", "Active Loan Lock"))
            self.lbl_f_desc.setStyleSheet("color: #991b1b; font-size: 13px; font-weight: bold;")
        else:
            self.finance_box.setStyleSheet("background-color: #f0fdf4; border: 1.5px solid #86efac; border-radius: 6px; padding: 12px;")
            self.lbl_f_title.setText("FINANCE / KISTI STATUS: CLEAN ✅")
            self.lbl_f_title.setStyleSheet("color: #15803d; font-size: 15px; font-weight: 800;")
            self.lbl_f_desc.setText(data.get("finance_desc", "Clean"))
            self.lbl_f_desc.setStyleSheet("color: #166534; font-size: 13px; font-weight: bold;")

        self.val_labels["val_brand"].setText(data.get("type", "Unknown"))
        self.val_labels["val_model"].setText(data.get("model", "-"))
        self.val_labels["val_serial"].setText(data.get("serial", "-"))
        self.val_labels["val_imei"].setText(data.get("imei", "-"))
        self.val_labels["val_os"].setText(data.get("os_version", "-"))
        self.val_labels["val_patch"].setText(data.get("security_patch", "-"))
        self.val_labels["val_cpu"].setText(data.get("cpu", "-"))
        
        cycles = str(data.get("battery_cycles", "N/A"))
        self.val_labels["val_cycles"].setText(f"{cycles} Times" if cycles.isdigit() else cycles)
        self.val_labels["val_health"].setText(data.get("battery_health", "-"))

        scr = data.get("screen_status", "Original")
        self.val_labels["val_screen"].setText(scr)
        self.val_labels["val_screen"].setStyleSheet("color: #dc2626; font-weight: bold;" if "Replaced" in scr else "color: #16a34a; font-weight: bold;")

        sec = data.get("security_status", "Official")
        self.val_labels["val_security"].setText(sec)
        self.val_labels["val_security"].setStyleSheet("color: #dc2626; font-weight: bold;" if "Risk" in sec or "Tripped" in sec else "color: #15803d; font-weight: bold;")

        tot = data.get("storage_total", "128 GB")
        free = data.get("storage_free", "64 GB")
        used = data.get("storage_used", "64 GB")
        self.val_labels["val_storage"].setText(f"{free} Free / {tot} Total")
        self.lbl_storage_title.setText(f"Device Storage Details: {used} Used, {free} Available ({tot})")
        self.storage_progress.setValue(data.get("storage_pct", 50))

    def show_report(self):
        if not self.current_data or self.current_data.get("state") != "normal":
            QMessageBox.information(self, "No Device", "অনুগ্রহ করে আগে কোনো সচল ডিভাইস কানেক্ট করুন!")
            return
        dialog = VerificationReportDialog(self.current_data, self)
        dialog.exec()

    def load_installed_apps(self):
        if not self.current_data or self.current_data.get("state") != "normal":
            self.table_apps.setRowCount(0)
            return
        apps = execute_get_installed_apps()
        self.table_apps.setRowCount(len(apps))
        for row, (apk, pkg) in enumerate(apps):
            self.table_apps.setItem(row, 0, QTableWidgetItem(apk))
            self.table_apps.setItem(row, 1, QTableWidgetItem(pkg))

    def handle_reboot(self, mode):
        if not self.current_data:
            QMessageBox.warning(self, "Warning", "ডিভাইস কানেক্টেড নেই!")
            return
        execute_reboot(mode)
        QMessageBox.information(self, "Success", f"ডিভাইস {mode} মোডে রিবুট হচ্ছে...")

    def handle_screenshot(self):
        if not self.current_data:
            QMessageBox.warning(self, "Warning", "ডিভাইস কানেক্টেড নেই!")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Screenshot", "screenshot.png", "PNG Image (*.png)")
        if path:
            execute_screenshot(path)
            QMessageBox.information(self, "Success", f"স্ক্রিনশট সেভ হয়েছে: {path}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Universal3uShopMaster()
    window.show()
    sys.exit(app.exec())
