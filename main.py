import sys
import threading
import requests
import platform
import subprocess
from PyQt6 import QtCore, QtGui, QtWidgets

SERVER = "https://bubbleapp.pythonanywhere.com"
POLL_INTERVAL = 1000  # ms

SELF_COLOR = QtGui.QColor("#0078d7")
OTHER_COLOR = QtGui.QColor("#3a3a3a")
TEXT_COLOR = QtGui.QColor("#ffffff")
BG_COLOR = QtGui.QColor("#1c1c1c")

class Bubble(QtWidgets.QLabel):
    def __init__(self, text, is_self=False):
        super().__init__(text)
        self.setWordWrap(True)
        self.setMargin(10)
        self.is_self = is_self
        self.setStyleSheet(f"""
            background-color: {SELF_COLOR.name() if is_self else OTHER_COLOR.name()};
            color: {TEXT_COLOR.name()};
            border-radius: 12px;
        """)

class PollThread(QtCore.QThread):
    new_message = QtCore.pyqtSignal(dict)

    def __init__(self, username, cache):
        super().__init__()
        self.username = username
        self.cache = cache
        self.running = True

    def run(self):
        while self.running:
            try:
                resp = requests.get(f"{SERVER}/messages", timeout=3)
                if resp.status_code == 200:
                    messages = resp.json()
                    if len(messages) > len(self.cache):
                        new_msgs = messages[len(self.cache):]
                        for m in new_msgs:
                            self.new_message.emit(m)
                        self.cache[:] = messages
            except Exception as e:
                print("Polling error:", e)
            self.msleep(POLL_INTERVAL)

    def stop(self):
        self.running = False
        self.wait()

class ChatWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chat")
        self.setGeometry(100,100,360,500)
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint |
            QtCore.Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(f"background-color: {BG_COLOR.name()}; border-radius: 12px;")

        # Dragging
        self.offset = None

        # Layout
        self.v_layout = QtWidgets.QVBoxLayout(self)
        self.v_layout.setContentsMargins(10,10,10,10)
        self.v_layout.setSpacing(5)

        # Scroll area
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background-color: transparent; border: none;")
        self.scroll_widget = QtWidgets.QWidget()
        self.scroll_layout = QtWidgets.QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.scroll_widget)
        self.v_layout.addWidget(self.scroll_area)

        # Input
        self.input_layout = QtWidgets.QHBoxLayout()
        self.entry = QtWidgets.QLineEdit()
        self.entry.setPlaceholderText("Type a message...")
        self.entry.setStyleSheet(f"""
            background-color: {OTHER_COLOR.name()};
            color: {TEXT_COLOR.name()};
            border-radius: 10px;
            padding: 6px;
        """)
        self.entry.returnPressed.connect(self.send_message)
        self.input_layout.addWidget(self.entry)

        self.send_btn = QtWidgets.QPushButton("Send")
        self.send_btn.setStyleSheet(f"""
            background-color: {SELF_COLOR.name()};
            color: {TEXT_COLOR.name()};
            border-radius: 10px;
            padding: 6px;
        """)
        self.send_btn.clicked.connect(self.send_message)
        self.input_layout.addWidget(self.send_btn)
        self.v_layout.addLayout(self.input_layout)

        # Username
        self.username, ok = QtWidgets.QInputDialog.getText(self,"Username","Enter your username:")
        if not ok or not self.username.strip():
            self.username = "Anonymous"

        # Cache
        self.messages_cache = []

        # Polling thread
        self.poll_thread = PollThread(self.username, self.messages_cache)
        self.poll_thread.new_message.connect(self.add_message)
        self.poll_thread.start()

    # Drag
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.offset = event.pos()
    def mouseMoveEvent(self, event):
        if self.offset is not None:
            self.move(self.pos() + event.pos() - self.offset)
    def mouseReleaseEvent(self, event):
        self.offset = None

    # Add message
    def add_message(self, msg):
        sender = msg.get("sender","Unknown")
        text = msg.get("message","")
        bubble = Bubble(f"{sender}: {text}", is_self=(sender==self.username))
        self.scroll_layout.addWidget(bubble)
        QtCore.QTimer.singleShot(50, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()))
        # Notification
        if platform.system()=="Darwin":
            subprocess.run(["osascript","-e","beep"])
        elif platform.system()=="Windows":
            import winsound
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)

    # Send message
    def send_message(self):
        text = self.entry.text().strip()
        if not text:
            if platform.system()=="Darwin":
                subprocess.run(["osascript","-e","beep"])
            return
        self.entry.clear()
        threading.Thread(target=self.post_message, args=(text,), daemon=True).start()

    def post_message(self, text):
        try:
            requests.post(f"{SERVER}/send", json={"sender":self.username,"message":text}, timeout=3)
        except Exception as e:
            print("Send error:", e)

    def closeEvent(self, event):
        self.poll_thread.stop()
        event.accept()


app = QtWidgets.QApplication(sys.argv)

window = ChatWindow()
window.show()

# Create system tray icon
tray_icon = QtWidgets.QSystemTrayIcon()
tray_icon.setIcon(QtGui.QIcon())  # You can set an icon here
tray_icon.setVisible(True)

# Menu for tray
menu = QtWidgets.QMenu()
toggle_action = menu.addAction("Show/Hide Chat")
toggle_action.triggered.connect(lambda: window.setVisible(not window.isVisible()))
quit_action = menu.addAction("Quit")
quit_action.triggered.connect(app.quit)
tray_icon.setContextMenu(menu)

sys.exit(app.exec())
