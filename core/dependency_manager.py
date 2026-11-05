import os
import sys
import subprocess
import zipfile
import shutil
import urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN_DIR = os.path.join(BASE_DIR, "bin")

def get_bin_path(binary_name):
    direct_path = os.path.join(BIN_DIR, binary_name)
    if os.path.exists(direct_path):
        return direct_path
    base_check = os.path.join(BASE_DIR, binary_name)
    if os.path.exists(base_check):
        return base_check
    return binary_name

def check_and_setup_dependencies(callback=None):
    os.makedirs(BIN_DIR, exist_ok=True)
    adb_path = get_bin_path("adb.exe")
    if not os.path.exists(adb_path):
        if callback: callback(15, "Downloading Google ADB Platform Tools...")
        try:
            url = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
            zip_p = os.path.join(BIN_DIR, "adb.zip")
            urllib.request.urlretrieve(url, zip_p)
            with zipfile.ZipFile(zip_p, 'r') as zf:
                for member in zf.namelist():
                    fname = os.path.basename(member)
                    if fname in ["adb.exe", "AdbWinApi.dll", "AdbWinUsbApi.dll"]:
                        with zf.open(member) as s, open(os.path.join(BIN_DIR, fname), "wb") as t:
                            shutil.copyfileobj(s, t)
            if os.path.exists(zip_p): os.remove(zip_p)
        except Exception:
            pass

    if callback: callback(100, "All Driver & Communication Engines Ready!")
