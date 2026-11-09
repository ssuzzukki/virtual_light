import socket
import threading
import json
import tkinter as tk
from tkinter import ttk, messagebox
import math


class VirtualLightBase:

    LIGHT_NAME = "Virtual Light"
    CHANNEL_COUNT = 1

    BG = "#202020"
    PANEL = "#2B2B2B"
    ENTRY = "#353535"
    BUTTON = "#404040"
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
        self.output_canvas = tk.Canvas(
            self.root, 
            bg = "#000000", 
            highlightthickness = 0, 
            bd = 0
        )

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
            background=self.BG, 
            borderwidth = 0
        )

        style.configure(
            "TNotebook.Tab",
            borderwidth = 0
        )

        style.layout(
            "TNotebook", 
            [
                (
                    "Notebook.client", 
                    {"sticky":"nswe"}
                )
            ]
        )

    # --------------------------------------------------
    # GUI
    # --------------------------------------------------

    def create_widgets(self):

        self.notebook = ttk.Notebook(
            self.root
        )

        self.notebook.configure(
            padding = 0
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

        self.preview_canvas = tk.Canvas(
            self.light_tab,
            bg="#000000", 
            highlightthickness = 0, 
            bd = 0
        )

        self.preview_canvas.pack(
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

        if not self.apply_settings():
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

        try:
            universe = int(self.universe_entry.get())
            address = int(self.address_entry.get())
        except ValueError:
            messagebox.showerror(
                "Input Error", 
                "Universe and Address must be integers."
            )

            return False
        
        if not 0 <= universe <= 255:
            messagebox.showerror(
                "Input Error", 
                "Universe must be between 0 and 255."
            )
            return False

        if not 1 <= address <= 512:
            messagebox.showerror(
                "Input Error", 
                "Address must be between 1 and 512."
            )
            return False
        
        if address + self.CHANNEL_COUNT - 1 > 512:
            messagebox.showerror(
                "Input Error", 
                "Channel range exeeds 512."
            )
            return False

        self.target_universe = universe
        self.start_address = address

        if self.connected:
            self.send_subscribe()
        
        return True

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

                try:
                    msg = json.loads(
                        line.strip()
                    )
                except json.JSONDecodeError:
                    continue

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

            self.preview_canvas.delete("all")
            self.process_channels(
                data, 
                self.preview_canvas
            )
            if self.fullscreen:
                self.output_canvas.delete("all")
                self.process_channels(
                    data, 
                    self.output_canvas
                )


        if self.running:

            self.root.after(
                16,
                self.process_latest_data
            )

    def process_channels(
        self,
        data, 
        canvas
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
        self.output_canvas.pack(
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

        self.output_canvas.pack_forget()

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

        self.exit_fullscreen()

        self.disconnect()

        self.root.destroy()

    def run(self):
        self.root.mainloop()


class Light(
    VirtualLightBase
    ):
    LIGHT_NAME = "vl-mls-06 Circle Par"
    CHANNEL_COUNT = 4

    def k2rgb(self, k):
        t = k / 100

        if t <= 66:
            r = 255
            g = 99.4708025861 * math.log(t) - 161.1195681661
            if t <= 19:
                b = 0
            else:
                b = 138.5177312231 * math.log(t - 10) - 305.0447927307
        else:
            r = 329.698727446 * ((t - 60) ** -0.1332047592)
            g = 288.1221695283 * ((t - 60) ** -0.0755148492)
            b = 255
        
        r = max(0, min(255, int(r)))
        g = max(0, min(255, int(g)))
        b = max(0, min(255, int(b)))

        return r, g, b

    def color(self, data):
        r = data[0]
        g = data[1]
        b = data[2]
        ct = data[3]
        a = 0.7
        

        base_r, base_g, base_b = self.k2rgb(6350)

        k = 2700 + ct * (10000-2700) / 255
        kr, kg, kb = self.k2rgb(k)

        fr = kr / base_r
        fg = kg / base_g
        fb = kb / base_b

        r = int(r * (1 - a + a * fr))
        g = int(g * (1 - a + a * fg))
        b = int(b * (1 - a + a * fb))
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))

        return r, g, b


    def process_channels(
        self, data, canvas
        ):
        if len(data) < self.CHANNEL_COUNT:
            return
        
        # ここから灯体の動作
        
        
        r, g, b = self.color(data)
        color = f"#{r:02x}{g:02x}{b:02x}"

        w = canvas.winfo_width()
        h = canvas.winfo_height()

        
        offset = -(w-h)/2
        res = 20

        for i in range(res):
            ri = int(r/(res-i))
            gi = int(g/(res-i))
            bi = int(b/(res-i))
            color = f"#{ri:02x}{gi:02x}{bi:02x}"
            #if i == 0:
                #color = f"#ffffff"
            offi = offset - (offset * (i+1) / res) + ((h/15)*(i/res))
            canvas.create_oval(
                ((w-h)/2 + offi), (0 + offi), ((w+h)/2 - offi), (h - offi), 
                fill = color, 
                outline = ""
            )
            #print(i)

        # ここまで灯体の動作



if __name__ == "__main__":
    app = Light()
    app.run()