"""
**Referring to text color:**

1. `self.fg_color = "CC7722"` — default text color in `EditorTab`.
2. `self._apply_theme()` — uses `self.fg_color` to set editor text color via stylesheet.
3. `tab.fg_color = color.name()` — sets chosen color in `set_text_color`.
4. `palette.setColor(QPalette.Text, ochre)` — sets global text color in dark theme.
5. `QMainWindow`, `QMenuBar`, `QMenu`, `QTabBar::tab`, `QTabBar::tab:selected`, `QStatusBar` in `app.setStyleSheet()` — set `color: #cc7722` for UI text.

These define and apply the text color across editor and interface.
=====You: where can i find each of them under which classes
====SAGE:  Breakdown by class:

**1. `self.fg_color = "CC7722"`**
→ Class: `EditorTab` (init method)
Purpose: Default text color.

**2. `self._apply_theme()` → uses `self.fg_color`**
→ Class: `EditorTab`
Method: `_apply_theme`
Purpose: Applies text color via stylesheet.

**3. `tab.fg_color = color.name()`**
→ Class: `Notepad`
Method: `set_text_color`
Purpose: Updates `EditorTab` text color.

**4. `palette.setColor(QPalette.Text, ochre)`**
→ Function: `apply_dark_theme(app)`
Purpose: Global text color for all widgets.

**5. Stylesheet definitions in `app.setStyleSheet(...)`**
→ Function: `apply_dark_theme(app)`
→ UI Elements:
- `QMainWindow`
- `QMenuBar`, `QMenu`
- `QTabBar::tab`, `QTabBar::tab:selected`
- `QStatusBar`
Purpose: Sets static text color across interface.

Summary:
- `EditorTab`: User text color
- `Notepad`: Updates editor's text color
- `apply_dark_theme`: UI/global text color
=====You:
"""

import socket
import sys
import os

PORT = 12345  # fixed port
HOST = '127.0.0.1'

import tempfile
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QFileDialog,
    QMessageBox, QFontDialog, QColorDialog, QStatusBar,
    QMenu, QTabWidget, QWidget, QVBoxLayout, QSplashScreen
)
from PySide6.QtGui import QAction, QKeySequence, QColor, QPalette, QTextCursor, QFontDatabase, QPixmap
from PySide6.QtCore import Qt, QEvent, QTimer

from PySide6.QtCore import Signal, QObject
import pyperclip


def ensure_benguiat_font():
    fonts = QFontDatabase.families()
    if "Benguiat" in fonts:
        #print("Benguiat font already installed.")
        return True
    else:
        font_path = os.path.abspath("assets/Benguiat.ttf")
        if os.path.exists(font_path):
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                print("Benguiat font loaded from assets.")
                return True
            else:
                print("Failed to load Benguiat font.")
                return False
        else:
            print("Font file assets/Benguiat.ttf not found.")
            return False



def send_args_to_server(args):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((HOST, PORT))
        msg = ' '.join(args).encode()
        s.sendall(msg)
        s.close()
        return True
    except ConnectionRefusedError:
        return False

def xxxrun_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, PORT))
    s.listen()
    # process own args here
    while True:
        conn, addr = s.accept()
        data = conn.recv(1024).decode()
        # handle args received
        Notepad.newTabRequested.emit(data)
        print("Received args: ", data)
        conn.close()

def run_server(notepad):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, PORT))
    s.listen()
    while True:
        conn, addr = s.accept()
        data = conn.recv(1024).decode()

        if os.path.isfile(data):
            #print("isfile")
            #print(data)
            notepad.fileOpenRequested.emit(data)
            print(f"data: {data}")
        elif isinstance(data, str) and data != "":
            print("isnotfile")
            print(data)
            notepad.newTabRequested.emit(data)
             # use instance signal
        
        conn.close()


class EditorTab(QWidget):
    #def __init__(self, parent=None):
    def __init__(self, parent=None, notepad=None):    
        super().__init__(parent)
        self.notepad = notepad
        self.editor = QTextEdit()
        
        #self.editor.setFontPointSize(12)
        self.font_size = 12
        font = self.editor.font()
        font.setPointSize(self.font_size)
        self.editor.setFont(font)
        self.editor.setAcceptRichText(True)

        self.path = None
        self.filename = "Untitled"
        self.word_wrap = True
        self.bg_color = "333333"    # Default charcoal background
        self.fg_color = "CC7722"    # Default ochre/orange text

        self.editor.viewport().installEventFilter(self)
        self.editor.cursorPositionChanged.connect(self.update_status)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.editor)

        self._apply_theme()
        self._set_word_wrap(True)

    def _apply_theme(self, bg = "", fg = ""):
        

        palette = self.editor.palette()
        if bg:
            palette.setColor(QPalette.Base, QColor(f"#{bg}"))
        if fg:
            palette.setColor(QPalette.Text, QColor(f"#{fg}"))
            
        if not bg and not fg:
            palette.setColor(QPalette.Base, QColor(f"#{self.bg_color}"))   # background
            palette.setColor(QPalette.Text, QColor(f"#{self.fg_color}"))   # text
        self.editor.setPalette(palette)

    def _set_word_wrap(self, wrap: bool):
        self.word_wrap = wrap
        self.editor.setLineWrapMode(QTextEdit.WidgetWidth if wrap else QTextEdit.NoWrap)

    def eventFilter(self, source, event):
        if event.type() == QEvent.Wheel and event.modifiers() == Qt.ControlModifier:
            delta = event.angleDelta().y()
            font = self.editor.font()
            size = font.pointSize() + (1 if delta > 0 else -1)
            size = max(5, min(size, 72))
            font.setPointSize(size)
            self.editor.setFont(font)
            return True
        return super().eventFilter(source, event)

    def update_statusss(self):
        if self.parent():
            cursor = self.editor.textCursor()
            line = cursor.blockNumber() + 1
            col = cursor.columnNumber() + 1
            self.parent().parent().status.showMessage(f"Ln {line}, Col {col}")

    def update_status(self):
        if self.notepad:
            cursor = self.editor.textCursor()
            line = cursor.blockNumber() + 1
            col = cursor.columnNumber() + 1
            self.notepad.status.showMessage(f"Ln {line}, Col {col}")        

    def autosave(self):
        if self.editor.toPlainText().strip():
            temp_dir = tempfile.gettempdir()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"autosave_{timestamp}.txt"
            temp_path = os.path.join(temp_dir, filename)
            try:
                with open(temp_path, 'w', encoding='utf-8') as f:
                    f.write(self.editor.toPlainText())
            except Exception:
                pass

import traceback

class Notepad(QMainWindow):
    newTabRequested = Signal(str)
    fileOpenRequested = Signal(str)
    bringToFront = Signal(str)
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nutpad")
        self.setGeometry(100, 100, 900, 700)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.update_title_and_status)
        self.setCentralWidget(self.tabs)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self._create_actions()
        self._create_menu()
        #self.new_tab()

        self.autosave_timer = QTimer()
        self.autosave_timer.timeout.connect(self.autosave_all)
        self.autosave_timer.start(30000)

        self.newTabRequested.connect(self.new_tab)
        self.fileOpenRequested.connect(self.file_open_from_signal)
        self.bringToFront.connect(self.bring_to_front)

    def show_about(self):
            QMessageBox.about(self, "About Notepad", "Version 1.02 A\nMade by Mark Laurence Ong.\n Github: ZFNO")

    def current_tab(self) -> EditorTab:
        return self.tabs.currentWidget()

    def new_tab(self,arg = ""):
        #tab = EditorTab(self)
        tab = EditorTab(parent=self.tabs, notepad=self)
        if arg:
            tab.editor.setPlainText(arg)
            self.bring_to_front() 
        index = self.tabs.addTab(tab, tab.filename)
        self.tabs.setCurrentIndex(index)

    def close_tab(self, index):
        tab = self.tabs.widget(index)
        if tab and tab.editor.document().isModified():
            confirm = QMessageBox.question(self, "Unsaved Changes",
                                           f"Save changes to {tab.filename} before closing?",
                                           QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            if confirm == QMessageBox.Yes:
                if not self.save_file(tab):
                    return
            elif confirm == QMessageBox.Cancel:
                return
        self.tabs.removeTab(index)
        if self.tabs.count() == 0:
            self.new_tab()

    def _create_actions(self):
        self.new_action = QAction("New Tab", self)
        self.new_action.setShortcut(QKeySequence.New)
        self.new_action.triggered.connect(self.new_tab)

        self.open_action = QAction("Open…", self)
        self.open_action.setShortcut(QKeySequence.Open)
        self.open_action.triggered.connect(self.file_open)

        self.save_action = QAction("Save", self)
        self.save_action.setShortcut(QKeySequence.Save)
        self.save_action.triggered.connect(self.file_save)

        self.save_as_action = QAction("Save As…", self)
        self.save_as_action.triggered.connect(self.file_save_as)

        self.exit_action = QAction("Exit", self)
        self.exit_action.setShortcut("Ctrl+Q")
        self.exit_action.triggered.connect(self.close)

        self.font_action = QAction("Font…", self)
        self.font_action.triggered.connect(self.change_font)

        self.wrap_action = QAction("Toggle Word Wrap", self)
        self.wrap_action.setCheckable(True)
        self.wrap_action.setChecked(True)
        self.wrap_action.triggered.connect(self.toggle_wrap)

        self.bg_action = QAction("Set Background Color…", self)
        self.bg_action.triggered.connect(self.set_background_color)

        self.fg_action = QAction("Set Text Color…", self)
        self.fg_action.triggered.connect(self.set_text_color)

    def _create_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")
        file_menu.addAction(self.new_action)
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        format_menu = menubar.addMenu("Format")
        format_menu.addAction(self.font_action)
        format_menu.addAction(self.wrap_action)

        theme_menu = QMenu("Theme", self)
        theme_menu.addAction(self.bg_action)
        theme_menu.addAction(self.fg_action)
        format_menu.addMenu(theme_menu)

        about_menu = menubar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        about_menu.addAction(about_action)

    def file_open(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open File", "", "Text Files (*.txt);;All Files ()")
        if path:
            try:
                print(path)
                with open(path, 'r', encoding='utf-8') as f:
                    text = f.read()
                tab = EditorTab(self)
                tab.editor.setText(text)
                tab.path = path
                tab.filename = os.path.basename(path)
                idx = self.tabs.addTab(tab, tab.filename)
                self.tabs.setCurrentIndex(idx)
                
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to open file:\n{e}")

    def file_open_from_signal(self, path):
        
        if path:
            try:
                #print("opening file")
                #QMessageBox.information(self, "Path:", f"{path}")
                with open(path, 'r', encoding='utf-8') as f:
                    text = f.read()
                tab = EditorTab(self)
                tab.editor.setText(text)
                tab.path = path
                tab.filename = os.path.basename(path)
                idx = self.tabs.addTab(tab, tab.filename)
                self.tabs.setCurrentIndex(idx)
                self.bring_to_front()
            except Exception as e:
                #QMessageBox.warning(self, "Error", f"Failed to open file:\n{e}")
                QMessageBox.warning(self,"Error",  f"Traceback: {traceback.format_exc()}")

    def file_save(self):
        tab = self.current_tab()
        if tab:
            if tab.path:
                self.save_file(tab)
            else:
                self.file_save_as()

    def file_save_as(self):
        tab = self.current_tab()
        if tab:
            path, _ = QFileDialog.getSaveFileName(self, "Save File As", "", "Text Files (*.txt);;All Files ()")
            if path:
                tab.path = path
                tab.filename = os.path.basename(path)
                self.save_file(tab)

    def save_file(self, tab: EditorTab) -> bool:
        try:
            with open(tab.path, 'w', encoding='utf-8') as f:
                f.write(tab.editor.toPlainText())
            self.tabs.setTabText(self.tabs.indexOf(tab), tab.filename)
            tab.editor.document().setModified(False)
            self.status.showMessage("File saved", 2000)
            return True
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not save file:\n{e}")
            return False

    def change_fontsss(self):
        tab = self.current_tab()
        if tab:
            font, ok = QFontDialog.getFont()
            if ok:
                #tab.editor.setFont(font)
                tab.editor.setCurrentFont(font)
    def change_font(self):
        tab = self.current_tab()
        if tab:
            ok, font = QFontDialog.getFont(tab.editor.font(), self)
            #print("font: ", font )
            #print("ok: ", ok)
            if ok:
                tab.editor.selectAll()
                tab.editor.setCurrentFont(font)
                tab.editor.setFontPointSize(font.pointSize())
                #tab.editor.moveCursor(tab.editor.textCursor().Start)  # remove selection     
                tab.editor.moveCursor(QTextCursor.Start)

    def toggle_wrap(self):
        tab = self.current_tab()
        if tab:
            tab._set_word_wrap(not tab.word_wrap)
            self.wrap_action.setChecked(tab.word_wrap)

    def set_background_color(self):
        tab = self.current_tab()
        if tab:
            color = QColorDialog.getColor()
            if color.isValid():
                tab.bg_color = color.name()
                tab.bg_color = tab.bg_color.lstrip("#")
                tab._apply_theme(tab.bg_color)
                #print(tab.bg_color)

    def set_text_color(self):
        tab = self.current_tab()
        if tab:
            color = QColorDialog.getColor()
            if color.isValid():
                tab.fg_color = color.name()
                tab.fg_color = tab.fg_color.lstrip("#")
                tab._apply_theme("",tab.fg_color)

    def update_title_and_status(self):
        tab = self.current_tab()
        if tab:
            self.setWindowTitle(f"{tab.filename} - Notepad")
            tab.update_status()

    def autosave_all(self):
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if isinstance(tab, EditorTab):
                tab.autosave()


    def xbring_to_front(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.show()
        QTimer.singleShot(1000, lambda: self.setWindowFlag(Qt.WindowStaysOnTopHint, False))

    def bring_to_front(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.show()
        def reset_flag():
            self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
            self.show()
        QTimer.singleShot(5, reset_flag)


def apply_dark_theme(app):
    palette = QPalette()
    charcoal = QColor("2e2e2e")
    ochre = QColor("#cc7722")

    palette.setColor(QPalette.Window, charcoal)
    palette.setColor(QPalette.Base, charcoal)
    palette.setColor(QPalette.AlternateBase, charcoal.darker(120))
    palette.setColor(QPalette.Text, ochre)
    palette.setColor(QPalette.Button, charcoal)
    palette.setColor(QPalette.ButtonText, ochre)
    palette.setColor(QPalette.Highlight, ochre.darker())
    palette.setColor(QPalette.HighlightedText, QColor("000000"))

    app.setPalette(palette)
    app.setStyle("Fusion")
    '''
    app.setStyleSheet("""
        QMainWindow {
            background-color: #2e2e2e;
            border: 2px solid #cc7722;
        }
        QMenuBar, QMenu {
            background-color: #2e2e2e;
            color: #cc7722;
        }
        QTabWidget::pane {
            border: 1px solid #cc7722;
        }
        QTabBar::tab {
            background: #3a3a3a;
            color: #cc7722;
            padding: 6px;
        }
        QTabBar::tab:selected {
            background: #444444;
            border: 1px solid #cc7722;
        }
        QStatusBar {
            background-color: #2e2e2e;
            color: #cc7722;
        }
    """)

    '''
    app.setStyleSheet("""
    QMainWindow {
        background-color: #2e2e2e;

    }
    QMenuBar, QMenu {
        background-color: #2e2e2e;
        color: #cc7722;
    }
    QTabWidget::pane {
        border: 1px solid #cc7722;
    }
    QTabBar::tab {
        background: #3a3a3a;
        color: #cc7722;
        padding: 6px;
    }

    QTextEdit {
        font-family: 'Benguiat';
        font-size: 28px;
        border: 2px solid #222222;
        padding: 10px;
    }

    QTabBar::tab:selected {
        background: #444444;
        border: 1px solid #cc7722;
    }
    QStatusBar {
        background-color: #2e2e2e;
        color: #cc7722;
    }

    /* Scrollbar vertical */
    QScrollBar:vertical {
        background: #2e2e2e;
        width: 12px;
        margin: 0px 0px 0px 0px;
    }
    QScrollBar::handle:vertical {
        background: #cc7722;
        min-height: 25px;
        border-radius: 4px;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        background: none;
        height: 0px;
        border: none;
    }
    QScrollBar::up-arrow, QScrollBar::down-arrow {
        background: none;
        color: none;
    }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: none;
    }

    /* Scrollbar horizontal */
    QScrollBar:horizontal {
        background: #2e2e2e;
        height: 12px;
        margin: 0px 0px 0px 0px;
    }
    QScrollBar::handle:horizontal {
        background: #cc7722;
        min-width: 25px;
        border-radius: 4px;
    }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        background: none;
        width: 0px;
        border: none;
    }
    QScrollBar::left-arrow, QScrollBar::right-arrow {
        background: none;
        color: none;
    }
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
        background: none;
    }
""")




"""
tries connect to running app, send args.

If success (app running):

- Sends args to that app

- Returns True

If fail (no app running):

- Returns False
"""

def get_content(arg):
    '''
    if os.path.isfile(arg):
        with open(arg, 'r', encoding = 'utf-8') as f:
            return f.read()
    else:
        return arg
    '''    
    return arg
    
def is_port_in_use(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((host, port))
        s.close()
        return True
    except:
        return False

import threading
if __name__ == "__main__":
    arg = ""
    command= ""



    if len(sys.argv) > 1 and is_port_in_use(HOST, PORT):  # If there is at least one argument and server is running
        #print("argument detected")                        # Inform argument found
        arg = get_content(sys.argv[1:])
        joined_list = ' '.join(arg)                    # Read content or pass argument string of first argument
        if send_args_to_server([joined_list]): 
                                # Send content to running server
            command = "stop"
            sys.exit(0)                                    # Exit if sending succeeded (another instance is running)
            
        '''
    elif len(sys.argv) > 1 and send_args_to_server(sys.argv[1:]):  # If arguments exist and sending full args succeeds
        print("no arg")                                         # Inform no single arg (all args sent)
        sys.exit(0)                                             # Exit new instance
        '''
    elif is_port_in_use(HOST, PORT):                            # If no args but server port busy (instance running)
        print("App already running \n You can add arguments like nutpad.exe [filename/filepath] to send the files to nutpad")
        sys.exit(0)                                             # Exit new instance to avoid duplicate



    # No running instance, start app
    app = QApplication(sys.argv)

    pixmap = QPixmap("assets/nutpad_splashscreen.png")
    splash = QSplashScreen(pixmap, Qt.WindowStaysOnTopHint)
    splash.show()
    ensure_benguiat_font()
    apply_dark_theme(app)
    window = Notepad()
    
    server_thread = threading.Thread(target=run_server, args=(window,), daemon=True)
    #server_thread = threading.Thread(target=run_server, args=(window))
    server_thread.start()
    '''
    if sys.argv[1]:
        print(sys.argv[1])
        send_args_to_server([sys.argv[1]])
    '''



    if len(sys.argv) > 1:

        if sys.argv[1]:
            file_path = os.path.abspath(sys.argv[1])
            if os.path.isfile(file_path):
                window.file_open_from_signal(f"{file_path}")
            else:
                arg = sys.argv[1:]
                joined_arg = ' '.join(arg)  
                window.new_tab(joined_arg)
    else:
        window.new_tab()
    # window.setWindowFlags(Qt.FramelessWindowHint)
    window.show()
    QTimer.singleShot(1500, splash.close)

    sys.exit(app.exec())