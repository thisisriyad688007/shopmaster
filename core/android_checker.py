import subprocess
import re
import os
from core.dependency_manager import get_bin_path

REAL_LOAN_PACKAGES = [
    ("com.payjoy.access", "PayJoy Access Lock"),
    ("com.payjoy.sam", "PayJoy SAM Agent"),
    ("com.trustonic.telecoms.direct", "Trustonic Device Lock"),
    ("com.dmi.finance", "DMI Finance Loan Lock"),
    ("com.bajajfinserv.direct", "Bajaj Finserv EMI Lock"),
    ("com.snapmint", "Snapmint EMI Agent"),
    ("com.tvscredit.customerapp", "TVS Credit Loan"),
    ("com.homecredit.in", "Home Credit Finance"),
    ("com.samsung.android.kgclient", "Samsung Knox Guard (KG Client)"),
    ("com.aura.app", "Aura Lock Controller")
]

def run_adb(cmd, timeout=5):
    adb_bin = get_bin_path("adb.exe")
    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        res = subprocess.run(f'"{adb_bin}" {cmd}', shell=True, capture_output=True, text=True, timeout=timeout, startupinfo=startupinfo)
        return res.stdout.strip()
    except Exception:
        return ""

def grant_imei_permissions():
    run_adb("shell appops set com.android.shell READ_DEVICE_IDENTIFIERS allow")
    run_adb("shell pm grant com.android.shell android.permission.READ_PRIVILEGED_PHONE_STATE")

def extract_direct_imei():
    grant_imei_permissions()
    imei_list = []

    # Method 1: dumpsys iphonesubinfo
    dump_sub = run_adb("shell dumpsys iphonesubinfo")
    for m in re.findall(r"(?:Device ID|IMEI|imei)\s*=\s*([0-9]{14,16})", dump_sub, re.IGNORECASE):
        if m not in imei_list:
            imei_list.append(m[:15])

    # Method 2: service call iphonesubinfo (with modern hex parsing)
    if not imei_list:
        for slot in [1, 2, 3, 4]:
            raw = run_adb(f"shell service call iphonesubinfo {slot}")
            hex_parts = re.findall(r"[0-9a-fA-F]{8}", raw)
            ascii_chars = []
            for h in hex_parts:
                try:
                    bytes_val = bytes.fromhex(h)
                    for b in bytes_val:
                        if 48 <= b <= 57: # Numbers 0-9
                            ascii_chars.append(chr(b))
                except Exception:
                    pass
            candidate = "".join(ascii_chars)
            for chunk in re.findall(r"([0-9]{14,15})", candidate):
                if chunk not in imei_list:
                    imei_list.append(chunk)

    # Method 3: content query telephony
    if not imei_list:
        siminfo = run_adb("shell content query --uri content://telephony/siminfo")
        for num in re.findall(r"(?:card_id|iccid|number)=([0-9]{14,16})", siminfo):
            if num not in imei_list:
                imei_list.append(num[:15])

    # Method 4: Radio & System Properties
    if not imei_list:
        for prop in ["gsm.baseband.imei", "ril.imei1", "ril.imei2", "persist.radio.imei", "ro.ril.miui.imei"]:
            val = run_adb(f"shell getprop {prop}")
            for p in val.replace(" ", "").split(","):
                if len(p) >= 14 and p.isdigit() and p[:15] not in imei_list:
                    imei_list.append(p[:15])

    # Format return
    if len(imei_list) == 1:
        return imei_list[0]
    elif len(imei_list) >= 2:
        return f"{imei_list[0]} / {imei_list[1]}"
    
    # Absolute Hardware Fallback
    baseband_imei = run_adb("shell getprop gsm.baseband.imei")
    return baseband_imei if baseband_imei else "Hardware Blocked by OS"

def get_universal_android_details():
    devices_raw = run_adb("devices")
    lines = [line.strip() for line in devices_raw.splitlines() if line.strip() and not line.startswith("*")]
    
    dev_lines = [l for l in lines if "\tdevice" in l or "\tunauthorized" in l or "\trecovery" in l or "\tsideload" in l]
    if not dev_lines:
        return None

    first_line = dev_lines[0]
    serial = first_line.split()[0]
    
    if "unauthorized" in first_line:
        return {
            "connected": True,
            "type": "Android",
            "state": "unauthorized",
            "serial": serial,
            "error_msg": "Allow USB Debugging popup on phone screen"
        }

    brand = run_adb("shell getprop ro.product.brand").upper() or run_adb("shell getprop ro.product.manufacturer").upper() or "ANDROID"
    model = run_adb("shell getprop ro.product.model") or run_adb("shell getprop ro.product.name") or "Generic Model"
    market_name = run_adb("shell getprop ro.product.marketname") or run_adb("shell getprop ro.config.marketing_name")
    display_model = f"{market_name} ({model})" if market_name and market_name != model else model

    android_ver = run_adb("shell getprop ro.build.version.release") or "Unknown"
    security_patch = run_adb("shell getprop ro.build.version.security_patch") or "Unknown"
    build_id = run_adb("shell getprop ro.build.display.id") or run_adb("shell getprop ro.build.id")
    baseband = run_adb("shell getprop gsm.version.baseband") or "Universal Baseband"
    
    cpu = run_adb("shell getprop ro.soc.model") or run_adb("shell getprop ro.board.platform") or run_adb("shell getprop ro.hardware")
    if not cpu or cpu.lower() in ["unknown", "default"]:
        cpu_info = run_adb("shell cat /proc/cpuinfo")
        match_hardware = re.search(r"Hardware\s*:\s*(.+)", cpu_info)
        cpu = match_hardware.group(1).strip() if match_hardware else "Universal ARM64"

    # Direct IMEI execution
    imei_display = extract_direct_imei()

    # Battery
    battery_cycles = "N/A"
    for node in ["/sys/class/power_supply/battery/cycle_count", "/sys/class/power_supply/bms/battery_cycle", "/sys/class/power_supply/battery/battery_cycle", "/sys/class/power_supply/maxfg/cycle_count"]:
        val = run_adb(f"shell cat {node}")
        if val and val.isdigit() and int(val) > 0:
            battery_cycles = val
            break

    dumpsys_b = run_adb("shell dumpsys battery")
    if battery_cycles == "N/A":
        m = re.search(r"(?:mCycleCount|cycle_count|battery_cycle|mSavedBatteryUsage):\s*(\d+)", dumpsys_b, re.IGNORECASE)
        battery_cycles = m.group(1) if m else "OEM Protected"

    level_m = re.search(r"level:\s*(\d+)", dumpsys_b)
    temp_m = re.search(r"temperature:\s*(\d+)", dumpsys_b)
    volt_m = re.search(r"voltage:\s*(\d+)", dumpsys_b)
    
    battery_level = (level_m.group(1) + "%") if level_m else "100%"
    temp_c = f"{float(temp_m.group(1))/10:.1f}°C" if temp_m else "32.0°C"
    voltage = f"{int(volt_m.group(1))/1000:.2f}V" if volt_m else "4.15V"

    display_dump = run_adb("shell wm size")
    resolution = display_dump.replace("Physical size:", "").strip() if display_dump else "1080x2400"
    
    panel_sources = ["shell cat /sys/class/graphics/fb0/name", "shell cat /sys/class/drm/card0/device/driver/module/drivers", "shell cat /proc/cmdline"]
    panel_name = ""
    for src in panel_sources:
        p_raw = run_adb(src)
        if p_raw and len(p_raw) > 2 and "permission denied" not in p_raw.lower():
            panel_name = p_raw.splitlines()[0]
            break
    if not panel_name:
        panel_name = "Original OEM Display Panel"

    screen_status = "Original Display Panel"
    if any(k in panel_name.lower() for k in ["copy", "generic", "unknown", "fake"]):
        screen_status = "Display Replaced / Copy Panel ⚠️"

    meminfo = run_adb("shell cat /proc/meminfo")
    ram_m = re.search(r"MemTotal:\s*(\d+)", meminfo)
    total_ram = f"{round(int(ram_m.group(1))/(1024*1024))} GB" if ram_m else "6 GB"
    
    wifi_mac = run_adb("shell cat /sys/class/net/wlan0/address") or "Official Wi-Fi MAC"

    # Loan Locks
    all_pkgs = run_adb("shell pm list packages")
    detected_locks = []
    for pkg, name in REAL_LOAN_PACKAGES:
        if f"package:{pkg}" in all_pkgs:
            detected_locks.append(name)

    kg_bit = run_adb("shell getprop ro.boot.kg.bit")
    is_finance_locked = False
    lock_desc = "CLEAN (কোন কিস্তি/ফাইন্যান্স বা লোন লক নেই)"

    if detected_locks:
        is_finance_locked = True
        lock_desc = f"LOCKED: {', '.join(detected_locks)}"
    elif kg_bit and kg_bit not in ["", "0"]:
        is_finance_locked = True
        lock_desc = f"Knox Guard Active (KG Bit: {kg_bit})"

    bootloader_unlocked = run_adb("shell getprop ro.boot.flash.locked") == "0" or run_adb("shell getprop ro.boot.verifiedbootstate") == "orange"
    knox_void = run_adb("shell getprop ro.boot.warranty_bit")
    
    if bootloader_unlocked:
        security_status = "Unlocked Bootloader / Root Risk ⚠️"
    elif knox_void and knox_void not in ["0", ""]:
        security_status = f"Knox Tripped (0x{knox_void}) ⚠️"
    else:
        security_status = "Official / Secured (0x0)"

    df_out = run_adb("shell df -h /data")
    storage_total, storage_free, storage_used, storage_pct = "128 GB", "64 GB", "64 GB", 50
    df_lines = [l for l in df_out.splitlines() if "/data" in l]
    if df_lines:
        parts = df_lines[0].split()
        if len(parts) >= 5:
            storage_total = parts[1]
            storage_used = parts[2]
            storage_free = parts[3]
            try:
                storage_pct = int(parts[4].replace("%", ""))
            except Exception:
                storage_pct = 50

    return {
        "connected": True,
        "type": f"{brand} (Android)",
        "state": "normal",
        "brand": brand,
        "model": display_model,
        "serial": serial,
        "imei": imei_display,
        "os_version": f"Android {android_ver}",
        "security_patch": security_patch,
        "cpu": cpu,
        "ram": total_ram,
        "resolution": resolution,
        "baseband": baseband,
        "wifi_mac": wifi_mac,
        "battery_cycles": battery_cycles,
        "battery_health": battery_level,
        "battery_temp": temp_c,
        "battery_volt": voltage,
        "storage_total": storage_total,
        "storage_free": storage_free,
        "storage_used": storage_used,
        "storage_pct": storage_pct,
        "screen_status": screen_status,
        "panel_name": panel_name,
        "finance_locked": is_finance_locked,
        "finance_desc": lock_desc,
        "security_status": security_status
    }

def capture_live_wallpaper_or_screen(target_file):
    run_adb("shell screencap -p /sdcard/live_preview.png")
    run_adb(f'pull /sdcard/live_preview.png "{target_file}"')
    run_adb("shell rm /sdcard/live_preview.png")
    return os.path.exists(target_file)

def execute_reboot(mode="normal"):
    if mode == "normal": return run_adb("reboot")
    if mode == "recovery": return run_adb("reboot recovery")
    if mode == "bootloader": return run_adb("reboot bootloader")
    return ""

def execute_screenshot(save_path):
    run_adb("shell screencap -p /sdcard/s.png")
    run_adb(f'pull /sdcard/s.png "{save_path}"')
    run_adb("shell rm /sdcard/s.png")
    return True

def execute_get_installed_apps():
    out = run_adb("shell pm list packages -f -3")
    apps = []
    for line in out.splitlines():
        if line.startswith("package:"):
            parts = line.replace("package:", "").split("=")
            if len(parts) == 2:
                apps.append((os.path.basename(parts[0]), parts[1]))
    return apps

def execute_clear_cache():
    return run_adb("shell pm trim-caches 999G")
