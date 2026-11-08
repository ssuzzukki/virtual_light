import json
import socket
import threading
import tkinter as tk
from tkinter import ttk
from dataclasses import dataclass

TCP_PORT = 9000
ARTNET_PORT = 6454

class DmxState:
    def __init__(self):
        self.lock = threading.Lock()
        self.universes = {}

    def update(self, universe, data):
        with self.lock:
            self.universes[universe] = bytearray(data[:512]).ljust(512, b'\x00')

    def get(self, universe):
        with self.lock:
            return self.universes.get(universe, bytearray(512)).copy()

state = DmxState()
clients = {}
clients_lock = threading.Lock()
client_id_counter = 1

@dataclass
class ClientInfo:
    id: int
    conn: socket.socket
    universe: int = 0
    start: int = 1
    length: int = 16

class ArtNetReceiver(threading.Thread):
    daemon = True
    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", ARTNET_PORT))
        while True:
            packet, _ = sock.recvfrom(2048)
            if len(packet) < 18:
                continue
            if packet[:8] != b'Art-Net\x00':
                continue
            opcode = packet[8] | (packet[9] << 8)
            if opcode != 0x5000:
                continue
            universe = packet[14]
            length = (packet[16] << 8) | packet[17]
            dmx = packet[18:18+length]
            state.update(universe, dmx)
            broadcast(universe)

class TcpServer(threading.Thread):
    daemon = True
    def run(self):
        global client_id_counter
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", TCP_PORT))
        srv.listen()
        while True:
            conn, _ = srv.accept()
            with clients_lock:
                cid = client_id_counter
                client_id_counter += 1
                clients[cid] = ClientInfo(cid, conn)
            threading.Thread(target=handle_client, args=(cid,), daemon=True).start()


def handle_client(cid):
    try:
        conn = clients[cid].conn
        f = conn.makefile('r')
        for line in f:
            msg = json.loads(line.strip())
            if msg.get('type') == 'subscribe':
                clients[cid].universe = int(msg.get('universe', 0))
                clients[cid].start = max(1, int(msg.get('start', 1)))
                clients[cid].length = max(1, int(msg.get('length', 1)))
    except Exception:
        pass
    finally:
        try:
            clients[cid].conn.close()
        except Exception:
            pass
        with clients_lock:
            clients.pop(cid, None)


def broadcast(universe):
    remove = []
    with clients_lock:
        items = list(clients.items())
    dmx = state.get(universe)
    for cid, c in items:
        if c.universe != universe:
            continue
        start = c.start - 1
        end = start + c.length
        payload = {
            'type': 'dmx',
            'universe': universe,
            'start': c.start,
            'data': list(dmx[start:end])
        }
        try:
            c.conn.sendall((json.dumps(payload) + '\n').encode())
        except Exception:
            remove.append(cid)
    if remove:
        with clients_lock:
            for cid in remove:
                clients.pop(cid, None)

class Gui:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('DMX Server')
        self.root.geometry('900x600')

        nb = ttk.Notebook(self.root)
        nb.pack(fill='both', expand=True)

        self.clients_tab = ttk.Frame(nb)
        self.monitor_tab = ttk.Frame(nb)

        nb.add(self.clients_tab, text='Clients')
        nb.add(self.monitor_tab, text='Monitor')

        self.tree = ttk.Treeview(self.clients_tab, columns=('id','u','s','l'), show='headings')
        for col, txt in [('id','ID'),('u','Universe'),('s','Start'),('l','Length')]:
            self.tree.heading(col, text=txt)
        self.tree.pack(fill='both', expand=True)

        top = ttk.Frame(self.monitor_tab)
        top.pack(fill='x')

        ttk.Label(top, text='Universe').pack(side='left')
        self.universe_var = tk.IntVar(value=0)
        ttk.Spinbox(top, from_=0, to=255, textvariable=self.universe_var, width=10).pack(side='left')

        self.text = tk.Text(self.monitor_tab, font=('Consolas', 10))
        self.text.pack(fill='both', expand=True)

        self.refresh()

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

        with clients_lock:
            for c in clients.values():
                self.tree.insert('', 'end', values=(c.id,c.universe,c.start,c.length))

        universe = self.universe_var.get()
        dmx = state.get(universe)

        lines = []
        for base in range(0, 512, 16):
            row = []
            for i in range(16):
                row.append(f'{dmx[base+i]:03d}')
            lines.append(f'{base+1:03d}: ' + ' '.join(row))

        self.text.delete('1.0', 'end')
        self.text.insert('1.0', '\n'.join(lines))

        self.root.after(200, self.refresh)

    def run(self):
        self.root.mainloop()

if __name__ == '__main__':
    ArtNetReceiver().start()
    TcpServer().start()
    Gui().run()