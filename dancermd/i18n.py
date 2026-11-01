"""Language selection and the strings of the desktop shell (tray menu, notifications, dialogs).

The web UIs are translated in the browser; see web/shared/locales. Both use the same language codes.
"""

import ctypes

from . import APP_NAME

SUPPORTED = ("en", "vi")
LANG_VIETNAMESE = 0x2A

STRINGS = {
    "en": {
        "tray.open": "Open {app}",
        "tray.copy_link": "Copy connection link",
        "tray.quit": "Quit",
        "tray.connected": "{app} - {count} phone(s) connected",
        "notify.still_running": "Still running in the system tray so your phone stays connected. "
                                "Click the icon to reopen it; right-click > Quit to exit.",
        "notify.link_copied_remote": "Remote connection link copied. Send it to your phone and open it in the browser.",
        "notify.link_copied_lan": "Wi-Fi connection link copied. Send it to your phone and open it in the browser.",
        "notify.phone_connected.title": "Phone connected",
        "notify.phone_connected": "{device} ({ip}) connected and can now control this PC.",
        "device.iphone": "iPhone",
        "device.ipad": "iPad",
        "device.android": "Android phone",
        "device.windows": "Windows PC",
        "device.mac": "Mac",
        "device.browser": "Browser",
        "dialog.port_in_use": "Couldn't open port {port}.\n\n{error}\n\n"
                              "Another copy, such as the command-line server, may be running. Close it and try again.",
        "dialog.already_running": "{app} is already running. Look for its icon in the system tray "
                                  "(bottom-right corner of the taskbar).",
        "dialog.install": "Install {app} on this PC?\n\nIt will appear in the Start menu and on the desktop. "
                          "No administrator rights are needed, and you can uninstall it from Settings > Apps.\n\n"
                          "Choose No to run this file directly (you can still install it later from the app window).",
        "dialog.install_legacy": "{app} is the new name of Remote Laptop. The old version will be removed; "
                                 "your settings and paired phones are kept.",
        "dialog.update": "{app} is already installed. Update it with this version?",
        "dialog.stop_failed": "Couldn't close the running copy of {app}. Quit it (right-click the tray icon > Quit), "
                              "then open this file again.",
        "dialog.uninstall": "Uninstall {app} from this PC?",
        "dialog.remove_data": "Also delete the settings and the access code?\n\n"
                              "Choose No to keep them, so your phones won't need to scan again after a reinstall.",
        "dialog.uninstalled": "{app} has been uninstalled.",
        "dialog.crashed": "{app} ran into a problem and has to close.\nDetails are in: {log}",
    },
    "vi": {
        "tray.open": "Mở {app}",
        "tray.copy_link": "Sao chép link kết nối",
        "tray.quit": "Thoát",
        "tray.connected": "{app} - {count} điện thoại đang kết nối",
        "notify.still_running": "Vẫn đang chạy ở khay hệ thống để điện thoại điều khiển được. "
                                "Bấm vào biểu tượng để mở lại, chuột phải > Thoát để tắt hẳn.",
        "notify.link_copied_remote": "Đã sao chép link kết nối từ xa. Gửi sang điện thoại rồi mở bằng trình duyệt.",
        "notify.link_copied_lan": "Đã sao chép link kết nối trong Wi-Fi. Gửi sang điện thoại rồi mở bằng trình duyệt.",
        "notify.phone_connected.title": "Điện thoại đã kết nối",
        "notify.phone_connected": "{device} ({ip}) vừa kết nối và có thể điều khiển máy này.",
        "device.iphone": "iPhone",
        "device.ipad": "iPad",
        "device.android": "Điện thoại Android",
        "device.windows": "Máy Windows",
        "device.mac": "Mac",
        "device.browser": "Trình duyệt",
        "dialog.port_in_use": "Không mở được cổng {port}.\n\n{error}\n\n"
                              "Có thể một bản khác (vd. server dòng lệnh) đang chạy. Hãy tắt nó rồi thử lại.",
        "dialog.already_running": "{app} đang chạy rồi. Xem biểu tượng ở khay hệ thống (góc phải thanh taskbar).",
        "dialog.install": "Cài {app} vào máy?\n\nSẽ có biểu tượng ở Start menu và Desktop để tìm và mở nhanh. "
                          "Không cần quyền Admin, gỡ được trong Settings > Apps.\n\n"
                          "Chọn No để chạy trực tiếp file này (vẫn cài được sau trong cửa sổ app).",
        "dialog.install_legacy": "{app} là tên mới của Remote Laptop. Bản cũ sẽ được gỡ; "
                                 "cấu hình và các điện thoại đã ghép được giữ nguyên.",
        "dialog.update": "Đã có {app} cài trong máy. Cập nhật bằng bản này?",
        "dialog.stop_failed": "Không tắt được {app} đang chạy. Hãy thoát nó (chuột phải icon ở khay > Thoát) "
                              "rồi mở lại file này.",
        "dialog.uninstall": "Gỡ {app} khỏi máy?",
        "dialog.remove_data": "Xoá luôn cấu hình và mã truy cập?\n\n"
                              "Chọn No để giữ lại: cài lại thì điện thoại không phải quét mã lần nữa.",
        "dialog.uninstalled": "Đã gỡ {app}.",
        "dialog.crashed": "{app} gặp lỗi và phải đóng.\nChi tiết trong: {log}",
    },
}

_language = "en"


def system_language():
    """The Windows display language, if supported."""
    try:
        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
    except (AttributeError, OSError):
        return "en"
    return "vi" if lang_id & 0x3FF == LANG_VIETNAMESE else "en"


def resolve(setting):
    """Map a setting ("auto" or a language code) to a supported language code."""
    return setting if setting in SUPPORTED else system_language()


def set_language(setting):
    global _language
    _language = resolve(setting)
    return _language


def current():
    return _language


def t(key, **params):
    template = STRINGS[_language].get(key) or STRINGS["en"][key]
    return template.format(app=APP_NAME, **params)
