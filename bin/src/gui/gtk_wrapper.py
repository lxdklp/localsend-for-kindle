import ctypes
from ctypes import (
    CFUNCTYPE, POINTER, byref,
    c_bool, c_char_p, c_double, c_float, c_int, c_uint, c_void_p,
)
from typing import Callable, Dict, Optional, Union

### 加载 GTK2 / GObject / GLib 共享库
_GTK_NAMES = ["libgtk-x11-2.0.so.0", "libgtk-x11-2.0.so", "libgtk-2.0.so.0"]
_GOBJECT_NAMES = ["libgobject-2.0.so.0", "libgobject-2.0.so"]
_GLIB_NAMES = ["libglib-2.0.so.0", "libglib-2.0.so"]

def _load_lib(names: list[str]) -> ctypes.CDLL:
    for name in names:
        try:
            return ctypes.CDLL(name)
        except OSError:
            continue
    for name in names:
        path = ctypes.util.find_library(name.replace("lib", "").split(".so")[0])
        if path:
            try:
                return ctypes.CDLL(path)
            except OSError:
                continue
    raise OSError(f"无法加载库: {names}")


try:
    import ctypes.util
    _gtk: ctypes.CDLL = _load_lib(_GTK_NAMES)
    _gobject: ctypes.CDLL = _load_lib(_GOBJECT_NAMES)
    _glib: ctypes.CDLL = _load_lib(_GLIB_NAMES)
except OSError:
    _gtk = _gobject = _glib = None  # type: ignore[assignment]

### GTK2 常量
# 窗口类型
GTK_WINDOW_TOPLEVEL = 0
GTK_WINDOW_POPUP = 1

# GTK 对话框响应码
GTK_RESPONSE_NONE = -1
GTK_RESPONSE_REJECT = -2
GTK_RESPONSE_ACCEPT = -3
GTK_RESPONSE_DELETE_EVENT = -4
GTK_RESPONSE_OK = -5
GTK_RESPONSE_CANCEL = -6
GTK_RESPONSE_CLOSE = -7
GTK_RESPONSE_YES = -8
GTK_RESPONSE_NO = -9
GTK_RESPONSE_APPLY = -10

# 滚动策略
GTK_POLICY_ALWAYS = 0
GTK_POLICY_AUTOMATIC = 1
GTK_POLICY_NEVER = 2

# 文件选择器动作
GTK_FILE_CHOOSER_ACTION_OPEN = 0
GTK_FILE_CHOOSER_ACTION_SAVE = 1
GTK_FILE_CHOOSER_ACTION_SELECT_FOLDER = 2

# Stock 按钮 ID
GTK_STOCK_OK = b"gtk-ok"
GTK_STOCK_CANCEL = b"gtk-cancel"
GTK_STOCK_YES = b"gtk-yes"
GTK_STOCK_NO = b"gtk-no"

### 回调注册表 — 防止 Python GC 回收 ctypes 回调
_GtkCallback = CFUNCTYPE(None, c_void_p, c_void_p)
_callback_registry: Dict[int, object] = {}
_cb_counter = 0

# 注册回调并返回 ID
def _register_callback(cb_obj: object) -> int:
    global _cb_counter
    _cb_counter += 1
    _callback_registry[_cb_counter] = cb_obj
    return _cb_counter

# 初始化
def gtk_init():
    _gtk.gtk_init(None, None)

### 窗口
# 创建新窗口
def gtk_window_new(window_type: int = GTK_WINDOW_TOPLEVEL) -> c_void_p:
    _gtk.gtk_window_new.argtypes = [c_int]
    _gtk.gtk_window_new.restype = c_void_p
    return _gtk.gtk_window_new(window_type)

# 设置窗口标题
def gtk_window_set_title(window: c_void_p, title: Union[str, bytes]):
    if isinstance(title, str):
        title = title.encode("utf-8")
    _gtk.gtk_window_set_title.argtypes = [c_void_p, c_char_p]
    _gtk.gtk_window_set_title(window, title)

# 设置窗口默认大小
def gtk_window_set_default_size(window: c_void_p, width: int, height: int):
    _gtk.gtk_window_set_default_size.argtypes = [c_void_p, c_int, c_int]
    _gtk.gtk_window_set_default_size(window, width, height)

# 设置窗口位置
def gtk_window_fullscreen(window: c_void_p):
    _gtk.gtk_window_fullscreen.argtypes = [c_void_p]
    _gtk.gtk_window_fullscreen(window)

# 设置窗口装饰
def gtk_window_set_decorated(window: c_void_p, decorated: bool):
    _gtk.gtk_window_set_decorated.argtypes = [c_void_p, c_int]
    _gtk.gtk_window_set_decorated(window, int(decorated))

### 容器
def gtk_container_add(container: c_void_p, child: c_void_p):
    _gtk.gtk_container_add.argtypes = [c_void_p, c_void_p]
    _gtk.gtk_container_add(container, child)

def gtk_container_remove(container: c_void_p, child: c_void_p):
    _gtk.gtk_container_remove.argtypes = [c_void_p, c_void_p]
    _gtk.gtk_container_remove(container, child)

def gtk_container_set_border_width(container: c_void_p, width: int):
    _gtk.gtk_container_set_border_width.argtypes = [c_void_p, c_uint]
    _gtk.gtk_container_set_border_width(container, width)

### Box 布局
def gtk_vbox_new(homogeneous: bool = False, spacing: int = 0) -> c_void_p:
    _gtk.gtk_vbox_new.argtypes = [c_int, c_int]
    _gtk.gtk_vbox_new.restype = c_void_p
    return _gtk.gtk_vbox_new(int(homogeneous), spacing)

def gtk_hbox_new(homogeneous: bool = False, spacing: int = 0) -> c_void_p:
    _gtk.gtk_hbox_new.argtypes = [c_int, c_int]
    _gtk.gtk_hbox_new.restype = c_void_p
    return _gtk.gtk_hbox_new(int(homogeneous), spacing)

def gtk_box_pack_start(box, child, expand=True, fill=True, padding=0):
    _gtk.gtk_box_pack_start.argtypes = [c_void_p, c_void_p, c_int, c_int, c_uint]
    _gtk.gtk_box_pack_start(box, child, int(expand), int(fill), padding)

def gtk_box_pack_end(box, child, expand=True, fill=True, padding=0):
    _gtk.gtk_box_pack_end.argtypes = [c_void_p, c_void_p, c_int, c_int, c_uint]
    _gtk.gtk_box_pack_end(box, child, int(expand), int(fill), padding)

### 标签
def gtk_label_new(text: Union[str, bytes, None] = None) -> c_void_p:
    if isinstance(text, str):
        text = text.encode("utf-8")
    _gtk.gtk_label_new.argtypes = [c_char_p]
    _gtk.gtk_label_new.restype = c_void_p
    return _gtk.gtk_label_new(text)

def gtk_label_set_text(label: c_void_p, text: Union[str, bytes]):
    if isinstance(text, str):
        text = text.encode("utf-8")
    _gtk.gtk_label_set_text.argtypes = [c_void_p, c_char_p]
    _gtk.gtk_label_set_text(label, text)

def gtk_label_set_line_wrap(label: c_void_p, wrap: bool):
    _gtk.gtk_label_set_line_wrap.argtypes = [c_void_p, c_int]
    _gtk.gtk_label_set_line_wrap(label, int(wrap))

def gtk_label_set_justify(label: c_void_p, justify: int):
    """justify: 0=LEFT, 1=RIGHT, 2=CENTER, 3=FILL"""
    _gtk.gtk_label_set_justify.argtypes = [c_void_p, c_int]
    _gtk.gtk_label_set_justify(label, justify)

### 按钮
def gtk_button_new_with_label(text: Union[str, bytes]) -> c_void_p:
    if isinstance(text, str):
        text = text.encode("utf-8")
    _gtk.gtk_button_new_with_label.argtypes = [c_char_p]
    _gtk.gtk_button_new_with_label.restype = c_void_p
    return _gtk.gtk_button_new_with_label(text)

def gtk_button_set_label(button: c_void_p, text: Union[str, bytes]):
    if isinstance(text, str):
        text = text.encode("utf-8")
    _gtk.gtk_button_set_label.argtypes = [c_void_p, c_char_p]
    _gtk.gtk_button_set_label(button, text)

### 文本输入框

def gtk_entry_new() -> c_void_p:
    _gtk.gtk_entry_new.argtypes = []
    _gtk.gtk_entry_new.restype = c_void_p
    return _gtk.gtk_entry_new()


def gtk_entry_set_text(entry: c_void_p, text: Union[str, bytes]):
    if isinstance(text, str):
        text = text.encode("utf-8")
    _gtk.gtk_entry_set_text.argtypes = [c_void_p, c_char_p]
    _gtk.gtk_entry_set_text(entry, text)


def gtk_entry_get_text(entry: c_void_p) -> str:
    _gtk.gtk_entry_get_text.argtypes = [c_void_p]
    _gtk.gtk_entry_get_text.restype = c_char_p
    raw = _gtk.gtk_entry_get_text(entry)
    return raw.decode("utf-8") if raw else ""


def gtk_entry_set_max_length(entry: c_void_p, max_len: int):
    _gtk.gtk_entry_set_max_length.argtypes = [c_void_p, c_int]
    _gtk.gtk_entry_set_max_length(entry, max_len)


def gtk_entry_set_visibility(entry: c_void_p, visible: bool):
    _gtk.gtk_entry_set_visibility.argtypes = [c_void_p, c_int]
    _gtk.gtk_entry_set_visibility(entry, int(visible))

### 进度条
def gtk_progress_bar_new() -> c_void_p:
    _gtk.gtk_progress_bar_new.argtypes = []
    _gtk.gtk_progress_bar_new.restype = c_void_p
    return _gtk.gtk_progress_bar_new()

def gtk_progress_bar_set_fraction(bar: c_void_p, fraction: float):
    _gtk.gtk_progress_bar_set_fraction.argtypes = [c_void_p, c_double]
    _gtk.gtk_progress_bar_set_fraction(bar, fraction)

def gtk_progress_bar_set_text(bar: c_void_p, text: Union[str, bytes]):
    if isinstance(text, str):
        text = text.encode("utf-8")
    _gtk.gtk_progress_bar_set_text.argtypes = [c_void_p, c_char_p]
    _gtk.gtk_progress_bar_set_text(bar, text)

### 复选框
def gtk_check_button_new_with_label(text: Union[str, bytes]) -> c_void_p:
    if isinstance(text, str):
        text = text.encode("utf-8")
    _gtk.gtk_check_button_new_with_label.argtypes = [c_char_p]
    _gtk.gtk_check_button_new_with_label.restype = c_void_p
    return _gtk.gtk_check_button_new_with_label(text)

def gtk_toggle_button_get_active(button: c_void_p) -> bool:
    _gtk.gtk_toggle_button_get_active.argtypes = [c_void_p]
    _gtk.gtk_toggle_button_get_active.restype = c_int
    return bool(_gtk.gtk_toggle_button_get_active(button))

def gtk_toggle_button_set_active(button: c_void_p, active: bool):
    _gtk.gtk_toggle_button_set_active.argtypes = [c_void_p, c_int]
    _gtk.gtk_toggle_button_set_active(button, int(active))

### 框架
def gtk_frame_new(label: Union[str, bytes, None] = None) -> c_void_p:
    if isinstance(label, str):
        label = label.encode("utf-8")
    _gtk.gtk_frame_new.argtypes = [c_char_p]
    _gtk.gtk_frame_new.restype = c_void_p
    return _gtk.gtk_frame_new(label)

### 分隔符
def gtk_hseparator_new() -> c_void_p:
    _gtk.gtk_hseparator_new.argtypes = []
    _gtk.gtk_hseparator_new.restype = c_void_p
    return _gtk.gtk_hseparator_new()

def gtk_vseparator_new() -> c_void_p:
    _gtk.gtk_vseparator_new.argtypes = []
    _gtk.gtk_vseparator_new.restype = c_void_p
    return _gtk.gtk_vseparator_new()

### 滚动窗口
def gtk_scrolled_window_new() -> c_void_p:
    _gtk.gtk_scrolled_window_new.argtypes = [c_void_p, c_void_p]
    _gtk.gtk_scrolled_window_new.restype = c_void_p
    return _gtk.gtk_scrolled_window_new(None, None)

def gtk_scrolled_window_set_policy(scroll: c_void_p, h_policy: int, v_policy: int):
    _gtk.gtk_scrolled_window_set_policy.argtypes = [c_void_p, c_int, c_int]
    _gtk.gtk_scrolled_window_set_policy(scroll, h_policy, v_policy)

def gtk_scrolled_window_add_with_viewport(scroll: c_void_p, child: c_void_p):
    _gtk.gtk_scrolled_window_add_with_viewport.argtypes = [c_void_p, c_void_p]
    _gtk.gtk_scrolled_window_add_with_viewport(scroll, child)

### 组件通用操作
def gtk_widget_show(widget: c_void_p):
    _gtk.gtk_widget_show.argtypes = [c_void_p]
    _gtk.gtk_widget_show(widget)

def gtk_widget_show_all(widget: c_void_p):
    _gtk.gtk_widget_show_all.argtypes = [c_void_p]
    _gtk.gtk_widget_show_all(widget)

def gtk_widget_hide(widget: c_void_p):
    _gtk.gtk_widget_hide.argtypes = [c_void_p]
    _gtk.gtk_widget_hide(widget)

def gtk_widget_destroy(widget: c_void_p):
    _gtk.gtk_widget_destroy.argtypes = [c_void_p]
    _gtk.gtk_widget_destroy(widget)

def gtk_widget_set_size_request(widget: c_void_p, width: int, height: int):
    _gtk.gtk_widget_set_size_request.argtypes = [c_void_p, c_int, c_int]
    _gtk.gtk_widget_set_size_request(widget, width, height)

def gtk_widget_set_sensitive(widget: c_void_p, sensitive: bool):
    _gtk.gtk_widget_set_sensitive.argtypes = [c_void_p, c_int]
    _gtk.gtk_widget_set_sensitive(widget, int(sensitive))

# 信号
"""
连接 GTK 信号到 Python 回调。

Args:
    widget: GTK 组件指针
    signal_name: 信号名(str 或 bytes),如 "clicked", "destroy"
    callback: Python 回调，签名 callback() 或 callback(user_data)
    user_data: 可选的用户数据

Returns:
    信号处理器 ID
"""
def connect_signal(widget: c_void_p, signal_name: Union[str, bytes],
                    callback: Callable, user_data=None) -> int:
    if isinstance(signal_name, str):
        signal_name = signal_name.encode("utf-8")
    if user_data is not None:
        def _wrapper(w, d):
            callback(user_data)
    else:
        def _wrapper(w, d):
            callback()
    c_callback = _GtkCallback(_wrapper)
    _register_callback(c_callback)
    _gobject.g_signal_connect_data.argtypes = [
        c_void_p, c_char_p, c_void_p, c_void_p, c_void_p, c_int
    ]
    _gobject.g_signal_connect_data.restype = c_uint
    handler_id = _gobject.g_signal_connect_data(
        widget, signal_name,
        ctypes.cast(c_callback, c_void_p),
        None,   # user_data
        None,   # destroy_notify
        0,      # connect_flags
    )
    return handler_id

### 主循环
# GTK 主事件循环
def gtk_main():
    _gtk.gtk_main()
# 退出 GTK 主事件循环
def gtk_main_quit():
    _gtk.gtk_main_quit()
# 检查是否有待处理的 GTK 事件
def gtk_events_pending() -> bool:
    _gtk.gtk_events_pending.argtypes = []
    _gtk.gtk_events_pending.restype = c_int
    return bool(_gtk.gtk_events_pending())
# 处理一个 GTK 事件
def gtk_main_iteration_do(blocking: bool = False) -> bool:
    _gtk.gtk_main_iteration_do.argtypes = [c_int]
    _gtk.gtk_main_iteration_do.restype = c_int
    return bool(_gtk.gtk_main_iteration_do(int(blocking)))
# 处理所有待处理的 GTK 事件
def process_pending_events():
    while gtk_events_pending():
        gtk_main_iteration_do(False)

### Kindle Awesome Window Manager
# AWM 窗口标题格式
AWM_APP_TITLE = "L:A_N:application_PC:T_ID:com.lxdklp.localsend"
AWM_DIALOG_TITLE = "L:D_N:dialog_ID:com.lxdklp.localsend"
AWM_DIALOG_KB_TITLE = "L:D_N:dialog_RKB_ID:com.lxdklp.localsend"
# 显示 Kindle 屏幕键盘(调用 kindle 键盘似乎有 bug,暂时弃用 :( )
def kindle_show_keyboard():
    import subprocess
    try:
        subprocess.Popen(
            ["lipc-set-prop", "-s", "com.lab126.keyboard", "open", "keyboard:abc:normal"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        pass  # 不在 Kindle 上
# 隐藏 Kindle 屏幕键盘
def kindle_hide_keyboard():
    import subprocess
    try:
        subprocess.Popen(
            ["lipc-set-prop", "-s", "com.lab126.keyboard", "close", "keyboard"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        pass
# GdkEvent 信号回调类型: gboolean callback(GtkWidget*, GdkEvent*, gpointer)
_GtkEventCallback = CFUNCTYPE(c_int, c_void_p, c_void_p, c_void_p)
# 为 GtkEntry 连接焦点事件以自动显示 Kindle 键盘
def connect_entry_keyboard(entry: c_void_p):
    def _on_focus_in(widget, event, data):
        kindle_show_keyboard()
        return 0
    cb_in = _GtkEventCallback(_on_focus_in)
    _register_callback(cb_in)
    _gobject.g_signal_connect_data.argtypes = [
        c_void_p, c_char_p, c_void_p, c_void_p, c_void_p, c_int
    ]
    _gobject.g_signal_connect_data.restype = c_uint
    _gobject.g_signal_connect_data(
        entry, b"focus-in-event",
        ctypes.cast(cb_in, c_void_p),
        None, None, 0,
    )

### 辅助函数
def create_button(label: str, on_click: Callable) -> c_void_p:
    """创建按钮并直接绑定点击回调"""
    btn = gtk_button_new_with_label(label)
    connect_signal(btn, "clicked", on_click)
    return btn
