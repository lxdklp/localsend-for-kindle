import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any, Coroutine, Dict, List, Optional

from src.app import LocalSendApp
from src.gui.gtk_wrapper import (
    AWM_APP_TITLE,
    GTK_POLICY_AUTOMATIC,
    GTK_WINDOW_TOPLEVEL,
    connect_entry_keyboard,
    connect_signal,
    create_button,
    gtk_box_pack_end,
    gtk_box_pack_start,
    gtk_button_set_label,
    gtk_container_add,
    gtk_container_set_border_width,
    gtk_entry_get_text,
    gtk_entry_new,
    gtk_entry_set_text,
    gtk_frame_new,
    gtk_hbox_new,
    gtk_hseparator_new,
    gtk_init,
    gtk_label_new,
    gtk_label_set_justify,
    gtk_label_set_line_wrap,
    gtk_label_set_text,
    gtk_progress_bar_new,
    gtk_progress_bar_set_fraction,
    gtk_progress_bar_set_text,
    gtk_scrolled_window_add_with_viewport,
    gtk_scrolled_window_new,
    gtk_scrolled_window_set_policy,
    gtk_vbox_new,
    gtk_widget_destroy,
    gtk_widget_set_sensitive,
    gtk_widget_set_size_request,
    gtk_widget_show_all,
    gtk_window_fullscreen,
    gtk_window_new,
    gtk_window_set_decorated,
    gtk_window_set_default_size,
    gtk_window_set_title,
    kindle_hide_keyboard,
    process_pending_events,
)
from src.models import DeviceInfo, FileInfo
from src.network.client import scan_network, send_files
from src.utils import build_file_info, format_size, get_local_ip

log = logging.getLogger("localsend.send_gui")

class SendGUI:
    def __init__(self, app: LocalSendApp, preload_files: Optional[List[str]] = None):
        self.app = app
        self.cfg = app.cfg
        self.window = None
        # 文件选择
        self._file_label = None
        self._path_entry = None
        self._status_label = None
        # 设备列表
        self._peers_box = None
        self._scan_btn = None
        self._device_info_label = None
        # 接收设备
        self._recipient_label = None
        # 进度
        self._progress = None
        self._progress_info = None
        self._speed_label = None
        # 按钮
        self._send_btn = None
        # 状态
        self._peer_widgets: Dict[str, object] = {}
        self._selected_peer: Optional[DeviceInfo] = None
        self._selected_files: List[str] = preload_files or []
        self._is_sending = False
        self._running = True

    ### 开始发送任务的辅助函数
    def _start_task(self, coro: Coroutine[Any, Any, Any], name: str):
        task = asyncio.create_task(coro)
        def _on_done(t: asyncio.Task):
            try:
                t.result()
            except asyncio.CancelledError:
                pass
            except Exception:
                log.exception("任务失败: %s", name)
        task.add_done_callback(_on_done)
        return task

    ### 构建 UI
    def build(self):
        gtk_init()

        self.window = gtk_window_new(GTK_WINDOW_TOPLEVEL)
        gtk_window_set_title(self.window, AWM_APP_TITLE)
        gtk_window_set_default_size(self.window, 600, 800)
        gtk_window_set_decorated(self.window, False)
        gtk_window_fullscreen(self.window)
        connect_signal(self.window, "destroy", self._on_destroy)

        root = gtk_vbox_new(False, 0)
        gtk_container_set_border_width(root, 8)
        gtk_container_add(self.window, root)

        # 标题栏
        title_bar = gtk_hbox_new(False, 8)
        title_label = gtk_label_new("LocalSend 发送")
        gtk_box_pack_start(title_bar, title_label, True, True, 0)
        gtk_box_pack_start(root, title_bar, False, False, 0)
        gtk_box_pack_start(root, gtk_hseparator_new(), False, False, 4)

        # 本机信息
        self._device_info_label = gtk_label_new("")
        gtk_label_set_justify(self._device_info_label, 0)
        gtk_box_pack_start(root, self._device_info_label, False, False, 4)

        # 文件选择
        file_frame = gtk_frame_new("待发送文件")
        file_box = gtk_vbox_new(False, 4)
        gtk_container_set_border_width(file_box, 8)

        self._file_label = gtk_label_new("未选择文件")
        gtk_label_set_line_wrap(self._file_label, True)
        gtk_box_pack_start(file_box, self._file_label, False, False, 0)

        gtk_container_add(file_frame, file_box)
        gtk_box_pack_start(root, file_frame, False, False, 4)

        # 设备列表
        peer_frame = gtk_frame_new("局域网设备 (点击选择接收设备)")

        scroll = gtk_scrolled_window_new()
        gtk_scrolled_window_set_policy(scroll, GTK_POLICY_AUTOMATIC, GTK_POLICY_AUTOMATIC)
        self._peers_box = gtk_vbox_new(False, 4)
        gtk_container_set_border_width(self._peers_box, 4)
        gtk_scrolled_window_add_with_viewport(scroll, self._peers_box)

        peer_inner = gtk_vbox_new(False, 4)
        gtk_box_pack_start(peer_inner, scroll, True, True, 0)

        self._scan_btn = create_button("扫描局域网", self._on_scan)
        gtk_widget_set_size_request(self._scan_btn, -1, 44)
        gtk_box_pack_start(peer_inner, self._scan_btn, False, False, 0)

        gtk_container_add(peer_frame, peer_inner)
        gtk_box_pack_start(root, peer_frame, True, True, 4)

        # 已选接收设备
        self._recipient_label = gtk_label_new("未选择接收设备")
        gtk_label_set_line_wrap(self._recipient_label, True)
        gtk_box_pack_start(root, self._recipient_label, False, False, 4)

        # 进度
        progress_frame = gtk_frame_new("发送进度")
        progress_box = gtk_vbox_new(False, 4)
        gtk_container_set_border_width(progress_box, 8)

        self._progress_info = gtk_label_new("")
        gtk_label_set_line_wrap(self._progress_info, True)
        gtk_box_pack_start(progress_box, self._progress_info, False, False, 0)

        self._progress = gtk_progress_bar_new()
        gtk_progress_bar_set_text(self._progress, "等待发送")
        gtk_box_pack_start(progress_box, self._progress, False, False, 0)

        self._speed_label = gtk_label_new("")
        gtk_box_pack_start(progress_box, self._speed_label, False, False, 0)

        self._status_label = gtk_label_new("")
        gtk_label_set_line_wrap(self._status_label, True)
        gtk_box_pack_start(progress_box, self._status_label, False, False, 0)

        gtk_container_add(progress_frame, progress_box)
        gtk_box_pack_start(root, progress_frame, False, False, 4)

        # 底部按钮
        btn_box = gtk_hbox_new(True, 8)
        self._send_btn = create_button("发送", self._on_send)
        gtk_widget_set_size_request(self._send_btn, -1, 48)
        gtk_box_pack_start(btn_box, self._send_btn, True, True, 0)

        self.exit_btn = create_button("返回", self._on_exit)
        gtk_widget_set_size_request(self.exit_btn, -1, 48)
        gtk_box_pack_start(btn_box, self.exit_btn, True, True, 0)
        gtk_box_pack_end(root, btn_box, False, False, 0)

        gtk_widget_show_all(self.window)
        if self._selected_files:
            self._update_file_display()
        self._refresh_device_info()
    ### 本机信息
    def _refresh_device_info(self):
        dev = self.app.device
        local_ip = get_local_ip()
        dev.ip = local_ip
        text = f"本机: {dev.alias} | {local_ip}:{dev.port} | {dev.protocol.upper()}"
        gtk_label_set_text(self._device_info_label, text) # pyright: ignore[reportArgumentType]
    ### 文件选择
    def _update_file_display(self):
        if not self._selected_files:
            gtk_label_set_text(self._file_label, "未选择文件") # pyright: ignore[reportArgumentType]
            return
        if len(self._selected_files) == 1:
            path = self._selected_files[0]
            if os.path.isdir(path):
                count = sum(1 for c in Path(path).rglob("*") if c.is_file())
                gtk_label_set_text(self._file_label, f"文件夹: {path}\n({count} 个文件)") # pyright: ignore[reportArgumentType]
            else:
                size = format_size(os.path.getsize(path))
                gtk_label_set_text(self._file_label, f"{os.path.basename(path)} ({size})") # pyright: ignore[reportArgumentType]
        else:
            gtk_label_set_text(self._file_label, f"已选择 {len(self._selected_files)} 个文件/文件夹") # pyright: ignore[reportArgumentType]
    ### 设备列表
    # 刷新
    def _refresh_peers(self):
        for fp, widget in list(self._peer_widgets.items()):
            gtk_widget_destroy(widget) # pyright: ignore[reportArgumentType]
        self._peer_widgets.clear()
        if not self.app.peers:
            lbl = gtk_label_new("未发现设备，点击「扫描局域网」搜索")
            gtk_box_pack_start(self._peers_box, lbl, False, False, 0)
            self._peer_widgets["_empty"] = lbl
        else:
            for fp, peer in self.app.peers.items():
                text = f"{peer.alias}  ({peer.device_model or peer.device_type})  {peer.ip}:{peer.port}"
                btn = create_button(text, lambda p=peer: self._on_select_peer(p))
                gtk_widget_set_size_request(btn, -1, 44)
                gtk_box_pack_start(self._peers_box, btn, False, False, 2)
                self._peer_widgets[fp] = btn
        gtk_widget_show_all(self._peers_box) # pyright: ignore[reportArgumentType]
    # 扫描
    def _on_scan(self):
        gtk_widget_set_sensitive(self._scan_btn, False) # pyright: ignore[reportArgumentType]
        gtk_button_set_label(self._scan_btn, "扫描中...") # type: ignore
        self._start_task(self._do_scan(), "scan")
    async def _do_scan(self):
        try:
            await scan_network(self.app)
        except Exception as e:
            log.warning("扫描失败: %s", e)
        finally:
            self._refresh_peers()
            gtk_widget_set_sensitive(self._scan_btn, True) # pyright: ignore[reportArgumentType]
            gtk_button_set_label(self._scan_btn, "扫描局域网") # pyright: ignore[reportArgumentType]
    # 选择
    def _on_select_peer(self, peer: DeviceInfo):
        self._selected_peer = peer
        gtk_label_set_text(
            self._recipient_label, # pyright: ignore[reportArgumentType]
            f"接收设备: {peer.alias} ({peer.ip}:{peer.port})"
        )
    # 发送
    def _on_send(self):
        self._start_task(self._do_send(), "send")
    async def _do_send(self):
        if not self._selected_files:
            gtk_label_set_text(self._status_label, "请先载入文件") # pyright: ignore[reportArgumentType]
            return
        if not self._selected_peer:
            gtk_label_set_text(self._status_label, "请先选择接收设备") # pyright: ignore[reportArgumentType]
            return
        if self._is_sending:
            return
        self._is_sending = True
        gtk_widget_set_sensitive(self._send_btn, False) # pyright: ignore[reportArgumentType]
        peer = self._selected_peer
        files: List[FileInfo] = []
        for fp in self._selected_files:
            p = Path(fp)
            if p.is_dir():
                for child in p.rglob("*"):
                    if child.is_file():
                        files.append(build_file_info(str(child), self.cfg.chunk_size))
            elif p.is_file():
                files.append(build_file_info(fp, self.cfg.chunk_size))
        if not files:
            gtk_label_set_text(self._status_label, "没有可发送的文件") # pyright: ignore[reportArgumentType]
            self._is_sending = False
            gtk_widget_set_sensitive(self._send_btn, True) # pyright: ignore[reportArgumentType]
            return
        total_size = sum(f.size for f in files)
        gtk_label_set_text(
            self._progress_info, # pyright: ignore[reportArgumentType]
            f"正在发送 {len(files)} 个文件 ({format_size(total_size)}) → {peer.alias}"
        )
        gtk_progress_bar_set_fraction(self._progress, 0.0) # pyright: ignore[reportArgumentType]
        gtk_progress_bar_set_text(self._progress, "连接中...") # pyright: ignore[reportArgumentType]
        try:
            success = await send_files(self.app, peer, files)
            if success:
                gtk_progress_bar_set_fraction(self._progress, 1.0) # pyright: ignore[reportArgumentType]
                gtk_progress_bar_set_text(self._progress, "完成!") # pyright: ignore[reportArgumentType]
                gtk_label_set_text(self._progress_info, "传输完成!") # pyright: ignore[reportArgumentType]
                gtk_label_set_text(self._status_label, "发送完成") # pyright: ignore[reportArgumentType]
            else:
                gtk_progress_bar_set_text(self._progress, "失败") # pyright: ignore[reportArgumentType]
                gtk_label_set_text(self._progress_info, "传输失败") # pyright: ignore[reportArgumentType]
                gtk_label_set_text(self._status_label, "发送失败") # pyright: ignore[reportArgumentType]
        except Exception as e:
            log.error("发送异常: %s", e)
            gtk_label_set_text(self._progress_info, f"错误: {e}") # pyright: ignore[reportArgumentType]
            gtk_label_set_text(self._status_label, f"异常: {e}") # pyright: ignore[reportArgumentType]
        finally:
            self._is_sending = False
            gtk_widget_set_sensitive(self._send_btn, True) # pyright: ignore[reportArgumentType]
    def _on_clear(self):
        self._selected_files.clear()
        self._selected_peer = None
        gtk_label_set_text(self._file_label, "未选择文件") # pyright: ignore[reportArgumentType]
        gtk_label_set_text(self._recipient_label, "未选择接收设备") # pyright: ignore[reportArgumentType]
        gtk_progress_bar_set_fraction(self._progress, 0.0) # pyright: ignore[reportArgumentType]
        gtk_progress_bar_set_text(self._progress, "等待发送") # pyright: ignore[reportArgumentType]
        gtk_label_set_text(self._progress_info, "") # pyright: ignore[reportArgumentType]
        gtk_label_set_text(self._speed_label, "") # pyright: ignore[reportArgumentType]
    # 窗口生命周期
    def _on_destroy(self):
        self._running = False
    def _on_exit(self):
        self._running = False
        kindle_hide_keyboard()
    # asyncio 主循环
    async def run_async(self):
        peer_refresh_interval = 3.0
        last_refresh = 0.0
        while self._running:
            process_pending_events()
            now = time.monotonic()
            if now - last_refresh > peer_refresh_interval:
                self._refresh_peers()
                last_refresh = now
            await asyncio.sleep(0.05)

### 入口
async def run_send_gui(app: LocalSendApp):
    preload = None
    if app.cfg.files:
        preload = [f for f in app.cfg.files if os.path.exists(f)]
    gui = SendGUI(app, preload_files=preload)
    gui.build()
    server_task = asyncio.create_task(app.run_server())
    gui_task = asyncio.create_task(gui.run_async())
    try:
        done, pending = await asyncio.wait(
            [server_task, gui_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
    except asyncio.CancelledError:
        pass
    finally:
        if gui.window:
            gtk_widget_destroy(gui.window)
            gui.window = None
