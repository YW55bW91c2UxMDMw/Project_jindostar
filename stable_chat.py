# stable_chat.py (GUI 충돌 해결 최종판)
import socket
import threading
import tkinter as tk
from tkinter import scrolledtext, simpledialog, messagebox
import socks
import os
import sys

# --- 경로 설정 ---
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TOR_BUNDLE_DIR = os.path.join(BASE_DIR, "tor-expert-bundle")
TOR_DATA_DIR = os.path.join(TOR_BUNDLE_DIR, "Data")
HIDDEN_SERVICE_DIR = os.path.join(TOR_DATA_DIR, "Tor", "hidden_service")
HOSTNAME_PATH = os.path.join(HIDDEN_SERVICE_DIR, "hostname")

def receive_messages(sock, text_area):
    while True:
        try:
            data = sock.recv(1024)
            if not data:
                text_area.insert(tk.END, "\n[상대방과의 연결이 끊겼습니다.]")
                break
            # GUI 업데이트는 메인 스레드에서 처리하는 것이 더 안전하지만,
            # Tkinter가 text 위젯에 대해서는 비교적 관대하므로 우선 유지합니다.
            text_area.insert(tk.END, f"\n상대방: {data.decode()}")
            text_area.see(tk.END)
        except:
            break

def send_message(sock, entry, text_area):
    message = entry.get()
    if message:
        text_area.insert(tk.END, f"\n나: {message}")
        text_area.see(tk.END)
        try:
            sock.sendall(message.encode())
            entry.delete(0, tk.END)
        except:
            text_area.insert(tk.END, "\n[메시지 전송에 실패했습니다.]")

class ChatApplication:
    def __init__(self, root):
        self.root = root
        self.connection_socket = None
        
        # ✨✨✨ 1. UI를 먼저 그리고, 필요한 정보를 모두 물어봄 ✨✨✨
        if not self.setup_ui_and_get_info():
            # 정보 입력에 실패하면 프로그램 종료
            self.root.destroy()
            return
        
        # ✨✨✨ 2. 수집된 정보를 바탕으로 네트워크 스레드 시작 ✨✨✨
        self.start_network_thread()

    def setup_ui_and_get_info(self):
        try:
            with open(HOSTNAME_PATH, 'r') as f:
                my_onion_address = f.read().strip()
        except FileNotFoundError:
            messagebox.showerror("오류", f"hostname 파일을 찾을 수 없습니다.\nTor를 먼저 실행하여 주소를 생성했는지 확인하세요.")
            return False

        self.root.title("Stable P2P Chat")
        address_frame = tk.Frame(self.root)
        address_frame.pack(padx=10, pady=5, fill=tk.X)
        tk.Label(address_frame, text="나의 주소:").pack(side=tk.LEFT)
        self.address_entry = tk.Entry(address_frame)
        self.address_entry.insert(0, my_onion_address)
        self.address_entry.config(state='readonly')
        self.address_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.chat_area = scrolledtext.ScrolledText(self.root, wrap=tk.WORD)
        self.chat_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        input_frame = tk.Frame(self.root)
        input_frame.pack(padx=10, pady=10, fill=tk.X)
        self.entry_field = tk.Entry(input_frame)
        self.entry_field.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.send_button = tk.Button(input_frame, text="전송", command=self.send)
        self.send_button.pack(side=tk.RIGHT)
        self.root.bind('<Return>', self.send)

        # --- 역할과 주소를 '메인 스레드'에서 미리 물어봄 ---
        self.role = messagebox.askquestion("역할 선택", "서버(대화방 개설)로 실행하시겠습니까?")
        if self.role == 'no':
            self.server_address = simpledialog.askstring("Onion 주소", "접속할 상대방의 .onion 주소를 입력하세요:")
            if not self.server_address:
                return False # 주소 입력 안 하면 실패
        return True

    def send(self, event=None):
        if self.connection_socket:
            send_message(self.connection_socket, self.entry_field, self.chat_area)
        else:
            self.chat_area.insert(tk.END, "\n[아직 연결되지 않았습니다.]")

    def start_network_thread(self):
        network_thread = threading.Thread(target=self.network_logic, daemon=True)
        network_thread.start()

    def network_logic(self):
        try:
            socks.set_default_proxy(socks.SOCKS5, "127.0.0.1", 9050)
            socket.socket = socks.socksocket
        except Exception as e:
            self.chat_area.insert(tk.END, f"\n[Tor 프록시 연결 오류: {e}]")
            return

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        if self.role == 'yes':
            self.root.title("Stable P2P Chat - 서버")
            try:
                sock.bind(('127.0.0.1', 9999))
                sock.listen()
                self.chat_area.insert(tk.END, f"\n[{self.address_entry.get()}] 주소로 연결을 기다리는 중...")
                conn, addr = sock.accept()
                self.chat_area.insert(tk.END, "\n[연결되었습니다.]")
                self.connection_socket = conn
            except Exception as e:
                self.chat_area.insert(tk.END, f"\n[서버 실행 실패: {e}]")
                return
        else: # self.role == 'no'
            self.root.title("Stable P2P Chat - 클라이언트")
            try:
                sock.connect((self.server_address, 9999))
                self.chat_area.insert(tk.END, "\n[서버에 연결되었습니다.]")
                self.connection_socket = sock
            except Exception as e:
                self.chat_area.insert(tk.END, f"\n[연결 실패: {e}]")
                return

        receive_thread = threading.Thread(target=receive_messages, args=(self.connection_socket, self.chat_area), daemon=True)
        receive_thread.start()

if __name__ == "__main__":
    # --- 실행 방법 ---
    # 1. cmd에서 tor.exe -f torrc 로 Tor를 먼저 실행
    # 2. Bootstrapped 100% 확인 및 hostname 파일 생성 확인
    # 3. 이 파이썬 파일을 실행
    
    root = tk.Tk()
    app = ChatApplication(root)
    # setup_ui_and_get_info가 False를 반환(실패)하면, root 윈도우가 이미 파괴되었을 수 있음
    # 따라서 app.start_network_thread()가 호출되지 않도록 __init__에서 처리
    if 'app' in locals() and app.root.winfo_exists():
        root.mainloop()