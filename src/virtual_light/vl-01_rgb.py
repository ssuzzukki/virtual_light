import socket
import threading
import tkinter as tk
from tkinter import messagebox


ARTNET_PORT = 6454
ARTNET_ID = b"Art-Net\x00"
ART_DMX_OPCODE = 0x5000

# RGB3チャンネルの仮想パーライト
# チャンネル構成
# Start Address + 0: Red
# Start Address + 1: Green
# Start Address + 2: Blue
CHANNEL_COUNT = 3
LIGHT_NAME = "VirtualLight-01 RGB par"


class VirtualLightApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(LIGHT_NAME)
        self.root.geometry("640x480")
        ##self.root.minsize(320, 240)

        # 現在参照している設定
        # 画面上ではUniverseを1始まりで扱う
        self.target_universe = 1
        self.start_address = 1

        # 受信スレッドとGUIスレッドで共有する最新値
        self.latest_rgb = (0, 0, 0)
        self.rgb_updated = False
        self.rgb_lock = threading.Lock()

        # 受信スレッドからGUIへエラーを通知するための変数
        self.receive_error = None
        self.error_lock = threading.Lock()

        # 現在表示中の色
        self.current_color = "#000000"

        # 終了制御
        self.running = True
        self.udp_socket = None

        self.create_widgets()

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.close
        )

        # Art-Net受信スレッドを開始
        self.receive_thread = threading.Thread(
            target=self.receive_artnet,
            name="ArtNetReceiver",
            daemon=True
        )
        self.receive_thread.start()

        # 最新値の確認を開始
        self.process_latest_data()

    def create_widgets(self):
        settings_frame = tk.Frame(
            self.root,
            padx=8,
            pady=8
        )
        settings_frame.pack(fill=tk.X)


        tk.Label(
            settings_frame,
            text="Address"
        ).pack(side=tk.LEFT)

        self.address_entry = tk.Entry(
            settings_frame,
            width=7
        )
        self.address_entry.insert(0, "1")
        self.address_entry.pack(
            side=tk.LEFT,
            padx=(5, 12)
        )

        tk.Label(
            settings_frame,
            text="Universe"
        ).pack(side=tk.LEFT)

        self.universe_entry = tk.Entry(
            settings_frame,
            width=7
        )
        self.universe_entry.insert(0, "1")
        self.universe_entry.pack(
            side=tk.LEFT,
            padx=(5, 12)
        )

        apply_button = tk.Button(
            settings_frame,
            text="適用",
            command=self.apply_settings
        )
        apply_button.pack(side=tk.LEFT)

        # Enterキーでも設定を適用
        self.universe_entry.bind(
            "<Return>",
            lambda event: self.apply_settings()
        )

        self.address_entry.bind(
            "<Return>",
            lambda event: self.apply_settings()
        )

        # 仮想灯体の表示部分
        self.light_area = tk.Frame(
            self.root,
            background="#000000"
        )
        self.light_area.pack(
            fill=tk.BOTH,
            expand=True
        )

    def apply_settings(self):
        
        # 参照するUniverseとStart Addressを変更する。
        # UDP受信スレッドの再起動は行わない。
        
        try:
            universe = int(
                self.universe_entry.get()
            )
            address = int(
                self.address_entry.get()
            )

        except ValueError:
            messagebox.showerror(
                "入力エラー",
                "UniverseとAddressには整数を入力してください。"
            )
            return

        if not 1 <= universe <= 32768:
            messagebox.showerror(
                "入力エラー",
                "Universeは1～32768で指定してください。"
            )
            return

        # RGBで3チャンネル使用するため最大510
        if not 1 <= address <= 510:
            messagebox.showerror(
                "入力エラー",
                "Addressは1～510で指定してください。"
            )
            return

        self.target_universe = universe
        self.start_address = address

        # 変更前の受信値を破棄して黒に戻す
        with self.rgb_lock:
            self.latest_rgb = (0, 0, 0)
            self.rgb_updated = False

        self.set_light_color(0, 0, 0)

    def receive_artnet(self):
        
        # UDP 6454でArt-Netを受信する。
        
        try:
            udp_socket = socket.socket(
                socket.AF_INET,
                socket.SOCK_DGRAM
            )

            self.udp_socket = udp_socket

            udp_socket.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_REUSEADDR,
                1
            )

            udp_socket.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_BROADCAST,
                1
            )

            # PC上のすべてのIPv4インターフェースで待機
            udp_socket.bind(("", ARTNET_PORT))

            # 終了状態を定期的に確認する
            udp_socket.settimeout(0.5)

            while self.running:
                try:
                    packet, _sender = udp_socket.recvfrom(1024)
                    self.parse_art_dmx(packet)

                except socket.timeout:
                    continue

                except OSError:
                    # 終了時にソケットを閉じた場合
                    if not self.running:
                        break

                    raise

        except OSError as error:
            if self.running:
                with self.error_lock:
                    self.receive_error = str(error)

        finally:
            if self.udp_socket is not None:
                try:
                    self.udp_socket.close()
                except OSError:
                    pass

                self.udp_socket = None

    def parse_art_dmx(self, packet):
        
        # ArtDmxパケットを解析して最新RGB値を保存する。
        # 古い値は保持せず、常に上書きする。
        
        # ArtDmxヘッダーは18バイト
        if len(packet) < 18:
            return

        # Art-Net識別文字列
        if packet[0:8] != ARTNET_ID:
            return

        # OpCodeはリトルエンディアン
        opcode = int.from_bytes(
            packet[8:10],
            byteorder="little"
        )

        if opcode != ART_DMX_OPCODE:
            return

        # プロトコルバージョンはビッグエンディアン
        protocol_version = int.from_bytes(
            packet[10:12],
            byteorder="big"
        )

        if protocol_version < 14:
            return

        # パケットのPort-Addressを取得
        sub_uni = packet[14]
        net = packet[15] & 0x7F

        packet_universe = sub_uni & 0x0F
        packet_subnet = (sub_uni >> 4) & 0x0F

        packet_port_address = (
            (net << 8)
            | (packet_subnet << 4)
            | packet_universe
        )

        # アプリのUniverse表示は1始まり
        selected_port_address = (
            self.target_universe - 1
        )

        if packet_port_address != selected_port_address:
            return

        # DMXデータ長はビッグエンディアン
        dmx_length = int.from_bytes(
            packet[16:18],
            byteorder="big"
        )

        if dmx_length < 2 or dmx_length > 512:
            return

        if len(packet) < 18 + dmx_length:
            return

        dmx_data = packet[18:18 + dmx_length]

        # DMXアドレスは1始まり、
        # Python配列は0始まり
        start_index = self.start_address - 1

        if start_index + CHANNEL_COUNT > len(dmx_data):
            return

        red = dmx_data[start_index]
        green = dmx_data[start_index + 1]
        blue = dmx_data[start_index + 2]

        # キューには積まず、最新値を上書きする
        with self.rgb_lock:
            self.latest_rgb = (
                red,
                green,
                blue
            )
            self.rgb_updated = True

    def process_latest_data(self):
        
        # 最新のRGB値だけをGUIへ反映する。
        
        new_rgb = None

        with self.rgb_lock:
            if self.rgb_updated:
                new_rgb = self.latest_rgb
                self.rgb_updated = False

        if new_rgb is not None:
            red, green, blue = new_rgb

            self.set_light_color(
                red,
                green,
                blue
            )

        # 受信スレッドでエラーが発生したか確認
        error = None

        with self.error_lock:
            if self.receive_error is not None:
                error = self.receive_error
                self.receive_error = None

        if error is not None:
            messagebox.showerror(
                "Art-Net受信エラー",
                "UDPポート6454を開けませんでした。\n\n"
                + error
            )

        if self.running:
            # 約60回/秒で最新値を確認
            self.root.after(
                16,
                self.process_latest_data
            )

    def set_light_color(
        self,
        red,
        green,
        blue
    ):
        
        # RGB値を仮想灯体の背景色へ反映する。
        
        color = (
            f"#{red:02x}"
            f"{green:02x}"
            f"{blue:02x}"
        )

        # 表示色が変わった場合だけ再描画
        if color != self.current_color:
            self.current_color = color

            self.light_area.configure(
                background=color
            )

    def close(self):
        
        # アプリを安全に終了する。
        
        self.running = False

        if self.udp_socket is not None:
            try:
                self.udp_socket.close()
            except OSError:
                pass

        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = VirtualLightApp()
    app.run()