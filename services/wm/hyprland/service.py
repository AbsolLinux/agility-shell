import os
import json
from loguru import logger
from gi.repository import Gio, GLib

from fabric.core.service import Property
from fabric.utils.helpers import idle_add

from ..base.service import WMService
from .window import HyprlandWindow
from .workspace import HyprlandWorkspace
from .keyboard import HyprlandKeyboardLayouts

HYPRLAND_COMMAND_BUFFER_SIZE = 1_048_576


class HyprlandSocketNotFoundError(Exception): ...


class Hyprland(WMService):

    @Property(bool, "readable", default_value=False)
    def is_available(self) -> bool:
        return bool(os.getenv("HYPRLAND_INSTANCE_SIGNATURE"))

    @Property(object, "readable", default_value=None)
    def keyboard_layouts(self) -> HyprlandKeyboardLayouts:
        return self._keyboard_layouts

    @Property(object, "readable", default_value=None)
    def windows(self) -> list[HyprlandWindow]:
        return list(self._windows.values())

    @Property(object, "readable", default_value=None)
    def active_window(self) -> HyprlandWindow:
        return self._active_window

    @Property(object, "readable", default_value=None)
    def workspaces(self) -> list[HyprlandWorkspace]:
        return list(self._workspaces.values())

    @Property(str, "readable", default_value="")
    def active_output(self) -> str:
        return self._property_helper_active_output or ""

    def __init__(self, **kwargs):
        self._keyboard_layouts = HyprlandKeyboardLayouts(self)
        self._windows: dict[int, HyprlandWindow] = {}
        self._active_window = HyprlandWindow(self)
        self._workspaces: dict[int, HyprlandWorkspace] = {}
        self._property_helper_active_output = ""

        sig = os.getenv("HYPRLAND_INSTANCE_SIGNATURE")
        if not sig:
            raise HyprlandSocketNotFoundError("HYPRLAND_INSTANCE_SIGNATURE not set.")

        xdg = os.getenv("XDG_RUNTIME_DIR", "/tmp")
        hyprland_dir = f"{xdg}/hypr/{sig}"
        if not os.path.isdir(hyprland_dir):
            hyprland_dir = f"/tmp/hypr/{sig}"
        if not os.path.isdir(hyprland_dir):
            raise HyprlandSocketNotFoundError("Hyprland socket directory not found.")

        self._socket_addr = Gio.UnixSocketAddress.new(f"{hyprland_dir}/.socket.sock")
        self._socket2_addr = Gio.UnixSocketAddress.new(f"{hyprland_dir}/.socket2.sock")

        super().__init__(**kwargs)

        self._initial_sync()
        GLib.Thread.new("hyprland-event-thread", self.__event_thread, None)

        self.notify("is-available")
        self.emit("ready")

    # -------------------------------------------------------------------------
    # IPC helpers — matches Fabric's Hyprland.send_command pattern exactly
    # -------------------------------------------------------------------------

    def _send_raw(self, command: str) -> bytes:
        """Send a raw command to socket1, return response bytes."""
        try:
            client = Gio.SocketClient()
            conn: Gio.SocketConnection = client.connect(self._socket_addr)
            ostream = conn.get_output_stream()
            istream = Gio.DataInputStream.new(conn.get_input_stream())
            ostream.write(command.encode())
            ostream.flush()
            raw: GLib.Bytes = istream.read_bytes(HYPRLAND_COMMAND_BUFFER_SIZE, None)
            return raw.get_data() or b""
        except Exception as e:
            logger.error(f"[HyprlandService] Socket error ({command!r}): {e}")
            return b""

    def send_command(self, command: str) -> str:
        """Send a dispatch command, e.g. 'workspace 2'."""
        return self._send_raw(f"dispatch {command}").decode().strip()

    def _request(self, endpoint: str) -> str:
        """Query a j/ endpoint, e.g. 'workspaces'."""
        return self._send_raw(f"j/{endpoint}").decode()

    def _request_json(self, endpoint: str):
        raw = self._request(endpoint)
        try:
            return json.loads(raw)
        except Exception as e:
            logger.error(f"[HyprlandService] JSON parse error ({endpoint}): {e}")
            return None

    # -------------------------------------------------------------------------
    # Initial sync
    # -------------------------------------------------------------------------

    def _initial_sync(self) -> None:
        self._sync_workspaces()
        self._sync_windows()
        self._sync_active_window()
        self._sync_keyboards()
        
    def _sync_workspaces(self) -> None:
        data = self._request_json("workspaces")
        if not data:
            return
        active_data = self._request_json("activeworkspace")
        active_id = active_data.get("id") if active_data else None
        monitor_data = self._request_json("monitors")
        focused_monitor = next((m["name"] for m in (monitor_data or []) if m.get("focused")), None)

        monitor_active_ws = {}
        if monitor_data:
            for m in monitor_data:
                act = m.get("activeWorkspace")
                if act and isinstance(act, dict) and "id" in act:
                    monitor_active_ws[m.get("name")] = act["id"]

        for ws in data:
            obj = self._workspaces.get(ws["id"])
            if obj is None:
                obj = HyprlandWorkspace(self)
            obj.sync(ws)
            ws_mon = ws.get("monitor")
            is_active = (ws["id"] == monitor_active_ws.get(ws_mon, active_id))
            obj.sync({
                "is_active": is_active,
                "is_focused": ws["id"] == active_id and ws_mon == focused_monitor,
            })
            self._workspaces[ws["id"]] = obj

        if focused_monitor:
            self._property_helper_active_output = focused_monitor

        self._sort_workspaces()
        self.notify("workspaces", "active-output")

    def _sync_windows(self) -> None:
        data = self._request_json("clients")
        if not data:
            return
        for client in data:
            addr = client.get("address", "")
            try:
                win_id = int(addr, 16)
            except (ValueError, TypeError):
                win_id = hash(addr)
            obj = self._windows.get(win_id)
            if obj is None:
                obj = HyprlandWindow(self)
            obj.sync(client)
            self._windows[win_id] = obj
        self.notify("windows")

    def _sync_active_window(self) -> None:
        data = self._request_json("activewindow")
        if not data:
            return
        addr = data.get("address", "")
        try:
            win_id = int(addr, 16)
        except (ValueError, TypeError):
            win_id = None

        if win_id and win_id in self._windows:
            self._windows[win_id].sync({"is_focused": True})
            self._active_window.sync(self._windows[win_id].data)
        else:
            self._active_window.sync(data)
        self.notify("active-window")

    def _sync_keyboards(self) -> None:
        data = self._request_json("devices")
        if not data:
            return
        for kb in data.get("keyboards", []):
            if kb.get("main"):
                layout_names = [l.strip() for l in kb.get("layout", "").split(",") if l.strip()]
                active_name = kb.get("active_keymap", "")
                idx = next((i for i, n in enumerate(layout_names) if n == active_name), 0)
                self._keyboard_layouts.sync({"names": layout_names, "current_idx": idx})
                break
        self.notify("keyboard-layouts")

    # -------------------------------------------------------------------------
    # Event thread (socket2) — matches Fabric's event_socket_task pattern
    # -------------------------------------------------------------------------

    def __event_thread(self, _) -> bool:
        try:
            client = Gio.SocketClient()
            conn: Gio.SocketConnection = client.connect(self._socket2_addr)
            istream = Gio.DataInputStream.new(conn.get_input_stream())

            while not conn.get_input_stream().is_closed():
                raw = istream.read_line(None)
                if not raw or not raw[0]:
                    continue
                line = raw[0].decode(errors="replace").strip()
                if ">>" in line:
                    idle_add(self.__on_event_line, line)
        except Exception as e:
            logger.error(f"[HyprlandService] Event thread error: {e}")
        return False

    def __on_event_line(self, line: str) -> None:
        event, _, data = line.partition(">>")
        self.__dispatch(event.strip(), data.strip())

    def __dispatch(self, event: str, data: str) -> None:
        match event:
            case "activewindow":
                self.__on_active_window(data)
            case "activewindowv2":
                self.__on_active_window_v2(data)
            case "closewindow":
                self.__on_close_window(data)
            case "openwindow":
                self.__on_open_window(data)
            case "movewindow":
                self.__on_move_window(data)
            case "workspace" | "workspacev2":
                self.__on_workspace_change(data)
            case "createworkspace" | "createworkspacev2":
                self.__on_create_workspace(data)
            case "destroyworkspace" | "destroyworkspacev2":
                self.__on_destroy_workspace(data)
            case "focusedmon":
                self.__on_focused_mon(data)
            case "activelayout":
                self.__on_active_layout(data)

    # -------------------------------------------------------------------------
    # Event handlers
    # -------------------------------------------------------------------------

    def __on_active_window(self, data: str) -> None:
        self._sync_active_window()

    def __on_active_window_v2(self, data: str) -> None:
        try:
            win_id = int(data, 16)
        except ValueError:
            return
        for wid, w in self._windows.items():
            w.sync({"is_focused": wid == win_id})
        if win_id in self._windows:
            self._active_window.sync(self._windows[win_id].data)
        else:
            self._sync_windows()
            self._sync_active_window()
        self.notify("active-window", "windows")

    def __on_close_window(self, data: str) -> None:
        try:
            win_id = int(data, 16)
        except ValueError:
            return
        window = self._windows.pop(win_id, None)
        if window:
            window.emit("destroyed")
        self.notify("windows")

    def __on_open_window(self, data: str) -> None:
        self._sync_windows()
        self.notify("windows")

    def __on_move_window(self, data: str) -> None:
        self._sync_windows()
        self.notify("windows")

    def __on_workspace_change(self, data: str) -> None:
        self._sync_workspaces()
        self.notify("workspaces")

    def __on_create_workspace(self, data: str) -> None:
        self._sync_workspaces()
        self.notify("workspaces")

    def __on_destroy_workspace(self, data: str) -> None:
        try:
            ws_id = int(data)
        except ValueError:
            ws_id = next((wid for wid, ws in self._workspaces.items() if ws.name == data), None)
        if ws_id is not None:
            ws = self._workspaces.pop(ws_id, None)
            if ws:
                ws.emit("destroyed")
        self.notify("workspaces")

    def __on_focused_mon(self, data: str) -> None:
        parts = data.split(",", 1)
        if parts:
            self._property_helper_active_output = parts[0]
            self.notify("active-output")

    def __on_active_layout(self, data: str) -> None:
        parts = data.split(",", 1)
        if len(parts) == 2:
            layout_name = parts[1]
            names = self._keyboard_layouts.names or []
            idx = next((i for i, n in enumerate(names) if n == layout_name), -1)
            self._keyboard_layouts.sync({"current_idx": idx})
            self.notify("keyboard-layouts")

    # -------------------------------------------------------------------------
    # Sorting & WMService interface
    # -------------------------------------------------------------------------

    def _sort_workspaces(self) -> None:
        self._workspaces = dict(sorted(self._workspaces.items(), key=lambda w: w[1].idx))

    def switch_to_workspace(self, idx: int) -> None:
        self.send_command(f"workspace {idx}")

    def switch_to_workspace_by_id(self, workspace_id: int) -> None:
        self.send_command(f"workspace {workspace_id}")

    def get_workspace_by_id(self, workspace_id: int) -> HyprlandWorkspace | None:
        return self._workspaces.get(workspace_id)