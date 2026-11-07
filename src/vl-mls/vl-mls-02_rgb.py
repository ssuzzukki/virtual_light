import socket
import threading
import json
import tkinter as tk
from tkinter import ttk, messagebox

CHANNEL_COUNT = 3
LIGHT_NAME = "VirtualLight-01 RGB PAR"

BG = "#202020"
PANEL = "#2B2B2B"
ENTRY = "#353535"
BUTTON = "#404040"
FG = "#FFFFFF"
CONNECTED_COLOR = "#00FF66"
DISCONNECTED_COLOR = "#FF5555"

class VirtualLightApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(LIGHT_NAME)
        self.root.geometry("800x600")
        self.root.configure(bg=BG)

        self.socket = None
        self.connected = False
        self.running = True
        self.fullscreen = False

        self.target_universe = 0
        self.start_address = 1

        self.latest_rgb = (0,0,0)
        self.rgb_lock = threading.Lock()
        self.current_color = "#000000"

        self.setup_theme()
        self.create_widgets()

        self.root.bind("<F11>", self.toggle_fullscreen)
        self.root.bind("<Escape>", self.exit_fullscreen)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.process_latest_data()

    def setup_theme(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL, foreground=FG, padding=(15,8))
        style.map("TNotebook.Tab", background=[("selected", "#505050")])

    def create_widgets(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True)

        self.light_tab = tk.Frame(self.notebook, bg="#000000")
        self.settings_tab = tk.Frame(self.notebook, bg=BG)

        self.notebook.add(self.light_tab, text="Light")
        self.notebook.add(self.settings_tab, text="Settings")

        self.light_area = tk.Frame(self.light_tab, bg="#000000")
        self.light_area.pack(fill=tk.BOTH, expand=True)

        frame = tk.Frame(self.settings_tab, bg=BG, padx=20, pady=20)
        frame.pack(anchor="nw")

        labels = ["Host","Port","Universe","Address"]
        self.host_entry = self.make_entry(frame)
        self.port_entry = self.make_entry(frame)
        self.universe_entry = self.make_entry(frame)
        self.address_entry = self.make_entry(frame)

        self.host_entry.insert(0,"127.0.0.1")
        self.port_entry.insert(0,"9000")
        self.universe_entry.insert(0,"0")
        self.address_entry.insert(0,"1")

        entries=[self.host_entry,self.port_entry,self.universe_entry,self.address_entry]
        for r,(lbl,e) in enumerate(zip(labels,entries)):
            tk.Label(frame,text=lbl,bg=BG,fg=FG).grid(row=r,column=0,sticky="w")
            e.grid(row=r,column=1,padx=10,pady=5)

        tk.Label(frame,text="Status",bg=BG,fg=FG).grid(row=4,column=0,sticky="w")
        self.status_var=tk.StringVar(value="Disconnected")
        self.status_label=tk.Label(frame,textvariable=self.status_var,bg=BG,fg=DISCONNECTED_COLOR)
        self.status_label.grid(row=4,column=1,sticky="w")

        buttons=tk.Frame(frame,bg=BG)
        buttons.grid(row=5,column=0,columnspan=2,pady=20)
        self.make_button(buttons,"Connect",self.connect).pack(side=tk.LEFT,padx=5)
        self.make_button(buttons,"Disconnect",self.disconnect).pack(side=tk.LEFT,padx=5)
        self.make_button(buttons,"Apply",self.apply_settings).pack(side=tk.LEFT,padx=5)

    def make_entry(self,parent):
        return tk.Entry(parent,width=24,bg=ENTRY,fg=FG,insertbackground=FG,relief=tk.FLAT)

    def make_button(self,parent,text,command):
        return tk.Button(parent,text=text,command=command,bg=BUTTON,fg=FG,activebackground="#606060",activeforeground=FG,width=12,relief=tk.FLAT)

    def connect(self):
        if self.connected:
            return
        try:
            host=self.host_entry.get().strip()
            port=int(self.port_entry.get())
            self.socket=socket.create_connection((host,port),timeout=5)
            self.connected=True
            self.status_var.set("Connected")
            self.status_label.configure(fg=CONNECTED_COLOR)
            threading.Thread(target=self.receive_loop,daemon=True).start()
            self.send_subscribe()
        except Exception as ex:
            messagebox.showerror("Connection Error",str(ex))

    def disconnect(self):
        self.connected=False
        try:
            if self.socket:
                self.socket.close()
        except Exception:
            pass
        self.socket=None
        self.status_var.set("Disconnected")
        self.status_label.configure(fg=DISCONNECTED_COLOR)

    def apply_settings(self):
        try:
            universe=int(self.universe_entry.get())
            address=int(self.address_entry.get())
        except ValueError:
            messagebox.showerror("Error","Universe / Address must be numeric")
            return
        if not 0 <= universe <= 255:
            messagebox.showerror("Error","Universe must be 0-255")
            return
        if not 1 <= address <= 510:
            messagebox.showerror("Error","Address must be 1-510")
            return
        self.target_universe=universe
        self.start_address=address
        if self.connected:
            self.send_subscribe()

    def send_subscribe(self):
        if not self.connected:
            return
        msg={"type":"subscribe","universe":self.target_universe,"start":self.start_address,"length":CHANNEL_COUNT}
        self.socket.sendall((json.dumps(msg)+"\n").encode())

    def receive_loop(self):
        try:
            fp=self.socket.makefile("r")
            for line in fp:
                if not self.connected:
                    break
                try:
                    msg=json.loads(line.strip())
                except Exception:
                    continue
                if msg.get("type")!="dmx":
                    continue
                data=msg.get("data",[])
                if len(data)<3:
                    continue
                with self.rgb_lock:
                    self.latest_rgb=(int(data[0]),int(data[1]),int(data[2]))
        except Exception:
            pass
        self.root.after(0,self.disconnect)

    def process_latest_data(self):
        with self.rgb_lock:
            r,g,b=self.latest_rgb
        color=f"#{r:02x}{g:02x}{b:02x}"
        if color!=self.current_color:
            self.current_color=color
            self.light_area.configure(bg=color)
        if self.running:
            self.root.after(16,self.process_latest_data)

    def toggle_fullscreen(self,event=None):
        current=self.notebook.select()
        if current!=str(self.light_tab):
            return
        self.fullscreen=not self.fullscreen
        if self.fullscreen:
            self.root.update_idletasks()
            w=self.root.winfo_screenwidth()
            h=self.root.winfo_screenheight()
            self.root.overrideredirect(True)
            self.root.geometry(f"{w}x{h}+0+0")
        else:
            self.exit_fullscreen()

    def exit_fullscreen(self,event=None):
        if not self.fullscreen:
            return
        self.fullscreen=False
        self.root.overrideredirect(False)
        self.root.geometry("800x600")

    def close(self):
        self.running=False
        self.exit_fullscreen()
        self.disconnect()
        self.root.destroy()

    def run(self):
        self.root.mainloop()

if __name__=="__main__":
    VirtualLightApp().run()
