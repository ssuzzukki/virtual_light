import socket
import threading
import json
import tkinter as tk
from tkinter import ttk, messagebox


class VirtualLightBase:

    LIGHT_NAME = "Virtual Light"
    CHANNEL_COUNT = 1

    BG = "#202020" #ok
    #PANEL = "#2B2B2B"
    PANEL = "#ff0000"
    ENTRY = "#353535" #ok
    #BUTTON = "#404040"
    BUTTON = "#00ff00"
    FG = "#FFFFFF"

    def __init__(self):

        self.root = tk.Tk()

        self.root.title(
            self.LIGHT_NAME
        )

        self.root.geometry(
            "800x600"
        )

        self.root.configure(
            bg=self.BG
        )

        self.socket = None
        self.connected = False
        self.running = True
        self.fullscreen = False

        self.target_universe = 0
        self.start_address = 1

        self.latest_data = []
        self.data_lock = threading.Lock()

        self.setup_theme()
        self.create_widgets()

        self.root.bind(
            "<F11>",
            self.toggle_fullscreen
        )

        self.root.bind(
            "<Escape>",
            self.exit_fullscreen
        )

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.close
        )

        self.process_latest_data()

    # --------------------------------------------------
    # Theme
    # --------------------------------------------------

    def setup_theme(self):

        style = ttk.Style()

        style.theme_use("clam")

        style.configure(
            "TNotebook",
            background=self.BG
        )

        style.configure(
            "TNotebook.Tab",
            background=self.PANEL,
            foreground=self.FG,
            padding=(15, 8)
        )

    # --------------------------------------------------
    # GUI
    # --------------------------------------------------

    def create_widgets(self):

        self.notebook = ttk.Notebook(
            self.root
        )

        self.notebook.pack(
            fill="both",
            expand=True
        )

        self.light_tab = tk.Frame(
            self.notebook,
            bg="black"
        )

        self.settings_tab = tk.Frame(
            self.notebook,
            bg=self.BG
        )

        self.notebook.add(
            self.light_tab,
            text="Light"
        )

        self.notebook.add(
            self.settings_tab,
            text="Settings"
        )

        #
        # Light Tab
        #

        self.light_area = tk.Frame(
            self.light_tab,
            bg="black"
        )
        self.fullscreen_frame = None

        self.light_area.pack(
            fill=tk.BOTH,
            expand=True
        )

        #
        # Settings Tab
        #

        frame = tk.Frame(
            self.settings_tab,
            bg=self.BG,
            padx=20,
            pady=20
        )

        frame.pack(anchor="nw")

        self.host_entry = self.add_setting(
            frame,
            0,
            "Host",
            "127.0.0.1"
        )

        self.port_entry = self.add_setting(
            frame,
            1,
            "Port",
            "9000"
        )

        self.universe_entry = self.add_setting(
            frame,
            2,
            "Universe",
            "0"
        )

        self.address_entry = self.add_setting(
            frame,
            3,
            "Address",
            "1"
        )

        tk.Label(
            frame,
            text="Status",
            bg=self.BG,
            fg=self.FG
        ).grid(
            row=4,
            column=0,
            sticky="w"
        )

        self.status_var = tk.StringVar(
            value="Disconnected"
        )

        self.status_label = tk.Label(
            frame,
            textvariable=self.status_var,
            bg=self.BG,
            fg="#FF5555"
        )

        self.status_label.grid(
            row=4,
            column=1,
            sticky="w"
        )

        buttons = tk.Frame(
            frame,
            bg=self.BG
        )

        buttons.grid(
            row=5,
            column=0,
            columnspan=2,
            pady=20
        )

        tk.Button(
            buttons,
            text="Connect",
            command=self.connect
        ).pack(
            side=tk.LEFT,
            padx=5
        )

        tk.Button(
            buttons,
            text="Disconnect",
            command=self.disconnect
        ).pack(
            side=tk.LEFT,
            padx=5
        )

        tk.Button(
            buttons,
            text="Apply",
            command=self.apply_settings
        ).pack(
            side=tk.LEFT,
            padx=5
        )

    def add_setting(
        self,
        parent,
        row,
        label,
        default
        ):

        tk.Label(
            parent,
            text=label,
            bg=self.BG,
            fg=self.FG
        ).grid(
            row=row,
            column=0,
            sticky="w"
        )

        entry = tk.Entry(
            parent,
            width=24,
            bg=self.ENTRY,
            fg=self.FG,
            insertbackground=self.FG
        )

        entry.insert(
            0,
            default
        )

        entry.grid(
            row=row,
            column=1,
            padx=10,
            pady=5
        )

        return entry

    # --------------------------------------------------
    # DMX
    # --------------------------------------------------

    def connect(self):

        if self.connected:
            return

        try:

            host = (
                self.host_entry.get()
            )

            port = int(
                self.port_entry.get()
            )

            self.socket = socket.create_connection(
                (host, port),
                timeout=5
            )

            self.connected = True

            self.status_var.set(
                "Connected"
            )

            self.status_label.configure(
                fg="#00FF66"
            )

            threading.Thread(
                target=self.receive_loop,
                daemon=True
            ).start()

            self.send_subscribe()

        except Exception as ex:

            messagebox.showerror(
                "Connection Error",
                str(ex)
            )

    def disconnect(self):

        self.connected = False

        try:

            if self.socket:
                self.socket.close()

        except Exception:
            pass

        self.socket = None

        self.status_var.set(
            "Disconnected"
        )

        self.status_label.configure(
            fg="#FF5555"
        )

    def apply_settings(self):

        self.target_universe = int(
            self.universe_entry.get()
        )

        self.start_address = int(
            self.address_entry.get()
        )

        if self.connected:
            self.send_subscribe()

    def send_subscribe(self):

        if not self.connected:
            return

        msg = {
            "type": "subscribe",
            "universe": self.target_universe,
            "start": self.start_address,
            "length": self.CHANNEL_COUNT
        }

        self.socket.sendall(
            (
                json.dumps(msg)
                + "\n"
            ).encode()
        )

    def receive_loop(self):

        try:

            fp = self.socket.makefile("r")

            for line in fp:

                msg = json.loads(
                    line.strip()
                )

                if msg.get("type") != "dmx":
                    continue

                with self.data_lock:

                    self.latest_data = (
                        msg.get(
                            "data",
                            []
                        )
                    )

        except Exception:
            pass

        self.root.after(
            0,
            self.disconnect
        )

    # --------------------------------------------------
    # Light Processing
    # --------------------------------------------------

    def process_latest_data(self):

        data = None

        with self.data_lock:

            if self.latest_data:
                data = self.latest_data

        if data:

            self.process_channels(
                data
            )

        if self.running:

            self.root.after(
                16,
                self.process_latest_data
            )

    def process_channels(
        self,
        data
        ):
        """
        灯体ごとの処理を書く

        data[0]
        data[1]
        ...
        """
        pass

    # --------------------------------------------------
    # Fullscreen
    # --------------------------------------------------

    def toggle_fullscreen(
        self,
        event=None
        ):

        if self.fullscreen:
            return
        
        self.fullscreen = True

        self.notebook.pack_forget()

        self.fullscreen_frame = tk.Frame(
            self.root, 
            bg = self.light_area.cget("bg")
        )

        self.fullscreen_frame.pack(
            fill = tk.BOTH, 
            expand = True

        )

        self.root.overrideredirect(True)

        width = self.root.winfo_screenwidth()
        height = self.root.winfo_screenheight()

        self.root.geometry(
            f"{width}x{height}+0+0"
        )

    def exit_fullscreen(
        self,
        event=None
        ):
        if not self.fullscreen:
            return
        
        self.fullscreen = False

        if self.fullscreen_frame:
            self.fullscreen_frame.destroy()
            self.fullscreen_frame = None

        self.notebook.pack(
            fill = "both", 
            expand = True
        )

        self.root.overrideredirect(False)

        self.root.geometry(
            "800x600"
        )

    # --------------------------------------------------
    # Close
    # --------------------------------------------------

    def close(self):

        self.running = False

        self.disconnect()

        self.root.destroy()

    def run(self):
        self.root.mainloop()


class Light(
    VirtualLightBase
    ):
    LIGHT_NAME = "light name"
    CHANNEL_COUNT = 1

    def process_channels(
        self, data
    ):
        if len(data) < self.CHANNEL_COUNT:
            return
        
        r = 0
        g = 0
        b = 0
        color = f"#{r:02x}{g:02x}{b:02x}"

        self.light_area.configure(bg = color)
        
        if self.fullscreen_frame:
            self.fullscreen_frame.configure(bg = color)


if __name__ == "__main__":
    app = Light()
    app.run()