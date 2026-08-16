import re
import socket
import sys
import os
import tempfile
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QFileDialog,
    QMessageBox, QFontDialog, QColorDialog, QStatusBar,
    QMenu, QTabWidget, QWidget, QVBoxLayout, QSplashScreen
)
from PySide6.QtGui import QAction, QKeySequence, QColor, QPalette, QTextCursor, QFontDatabase, QPixmap
from PySide6.QtCore import Qt, QEvent, QTimer, Signal, QObject
import pyperclip
import threading
import time
import traceback

from plyer import notification
import platform
# Add watchdog imports
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

PORT = 12345
HOST = '127.0.0.1'

def ensure_benguiat_font():
    fonts = QFontDatabase.families()
    if "Benguiat" in fonts:
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
    
def show_notification(title, message):
    """Show OS notification"""
    try:
        if platform.system() == "Windows":
            notification.notify(
                title=title,
                message=message,
                app_name="Nutpad",
                timeout=1
            )
        elif platform.system() == "Darwin":  # macOS
            os.system(f"""
                osascript -e 'display notification "{message}" with title "{title}" sound name "default"'
            """)
        elif platform.system() == "Linux":
            os.system(f"""
                notify-send "{title}" "{message}" --icon=dialog-information --expire-time=1000
            """)
    except Exception as e:
        print(f"Notification error: {e}")

def run_server(notepad):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, PORT))
    s.listen()
    while True:
        conn, addr = s.accept()
        data = conn.recv(1024).decode()
        if os.path.isfile(data):
            notepad.fileOpenRequested.emit(data)
            print(f"data: {data}")
        elif isinstance(data, str) and data != "":
            print("isnotfile")
            print(data)
            notepad.newTabRequested.emit(data)
        conn.close()

class EditorTab(QWidget):
    def __init__(self, parent=None, notepad=None):    
        super().__init__(parent)
        self.notepad = notepad
        self.editor = QTextEdit()
        self.font_size = 12
        font = self.editor.font()
        font.setPointSize(self.font_size)
        self.editor.setFont(font)
        self.editor.setAcceptRichText(True)

        self.path = None
        self.filename = "Untitled"
        self.word_wrap = True
        self.bg_color = "333333"
        self.fg_color = "CC7722"
        self.watchdog_enabled = False
        self.last_modified = None

        self.editor.viewport().installEventFilter(self)
        self.editor.cursorPositionChanged.connect(self.update_status)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.editor)

        self._apply_theme()
        self._set_word_wrap(True)

    def _apply_theme(self, bg="", fg=""):
        palette = self.editor.palette()
        if bg:
            palette.setColor(QPalette.Base, QColor(f"#{bg}"))
        if fg:
            palette.setColor(QPalette.Text, QColor(f"#{fg}"))
        if not bg and not fg:
            palette.setColor(QPalette.Base, QColor(f"#{self.bg_color}"))
            palette.setColor(QPalette.Text, QColor(f"#{self.fg_color}"))
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

    def check_external_changes(self):
        """Check if file has been modified externally"""
        if self.path and os.path.exists(self.path) and self.watchdog_enabled:
            try:
                current_mtime = os.path.getmtime(self.path)
                if self.last_modified is None:
                    self.last_modified = current_mtime
                elif current_mtime > self.last_modified:
                    # File changed externally
                    self.last_modified = current_mtime
                    with open(self.path, 'r', encoding='utf-8') as f:
                        new_content = f.read()
                    if new_content != self.editor.toPlainText():
                        self.editor.setText(new_content)
                        if self.notepad:
                            self.notepad.status.showMessage(f"Reloaded {self.filename} (external change)", 3000)
            except Exception:
                pass

class FileWatcher(QObject):
    """Watchdog handler for file changes"""
    file_changed = Signal(str)
    
    def __init__(self):
        super().__init__()
        self.observer = Observer()
        self.watched_files = {}
        self.handler = FileSystemEventHandler()
        self.handler.on_modified = self.on_modified
        
    def on_modified(self, event):
        if not event.is_directory:
            self.file_changed.emit(event.src_path)
    
    def watch_file(self, filepath):
        """Start watching a file"""
        if filepath in self.watched_files:
            return
        directory = os.path.dirname(filepath)
        if directory not in self.watched_files:
            self.observer.schedule(self.handler, directory, recursive=False)
            self.watched_files[directory] = [filepath]
        else:
            self.watched_files[directory].append(filepath)
    
    def unwatch_file(self, filepath):
        """Stop watching a file"""
        directory = os.path.dirname(filepath)
        if directory in self.watched_files and filepath in self.watched_files[directory]:
            self.watched_files[directory].remove(filepath)
            if not self.watched_files[directory]:
                self.observer.unschedule(self.handler, directory)
                del self.watched_files[directory]
    
    def start(self):
        """Start the observer"""
        if not self.observer.is_alive():
            self.observer.start()
    
    def stop(self):
        """Stop the observer"""
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join()

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

        # Initialize file watcher
        self.file_watcher = FileWatcher()
        self.file_watcher.file_changed.connect(self.on_file_changed_externally)
        self.file_watcher.start()

        self._create_actions()
        self._create_menu()
        
        self.autosave_timer = QTimer()
        self.autosave_timer.timeout.connect(self.autosave_all)
        self.autosave_timer.start(30000)
        
        # Add watchdog check timer
        self.watchdog_timer = QTimer()
        self.watchdog_timer.timeout.connect(self.check_all_tabs_external_changes)
        self.watchdog_timer.start(1000)  # Check every second

        self.newTabRequested.connect(self.new_tab)
        self.fileOpenRequested.connect(self.file_open_from_signal)
        self.bringToFront.connect(self.bring_to_front)

        self.last_notification_time = {}  # <<--- Add this line

    def show_about(self):
        QMessageBox.about(self, "About Notepad", "Version 1.02 A\nMade by Mark Laurence Ong.\n Github: ZFNO")

    def current_tab(self) -> EditorTab:
        return self.tabs.currentWidget()

    def new_tab(self, arg=""):
        tab = EditorTab(parent=self.tabs, notepad=self)
        if arg:
            tab.editor.setPlainText(arg)
            self.bring_to_front()
        index = self.tabs.addTab(tab, tab.filename)
        self.tabs.setCurrentIndex(index)

    def close_tab(self, index):
        tab = self.tabs.widget(index)
        if tab:
            # Stop watching file if enabled
            if tab.path and tab.watchdog_enabled:
                self.file_watcher.unwatch_file(tab.path)
            
            if tab.editor.document().isModified():
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
        
        # Watchdog actions
        self.watchdog_action = QAction("Monitor File for External Changes", self)
        self.watchdog_action.setCheckable(True)
        self.watchdog_action.setChecked(False)
        self.watchdog_action.triggered.connect(self.toggle_watchdog)

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
        
        # Add watchdog to Tools menu
        tools_menu = menubar.addMenu("Tools")
        tools_menu.addAction(self.watchdog_action)

        about_menu = menubar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        about_menu.addAction(about_action)

    def file_open(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open File", "", "Text Files (*.txt);;All Files ()")
        if path:
            try:
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
                QMessageBox.warning(self, "Error", f"Traceback: {traceback.format_exc()}")

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
                # Stop watching old path if enabled
                if tab.path and tab.watchdog_enabled:
                    self.file_watcher.unwatch_file(tab.path)
                
                tab.path = path
                tab.filename = os.path.basename(path)
                self.save_file(tab)
                
                # Start watching new path if watchdog is enabled
                if tab.watchdog_enabled:
                    self.file_watcher.watch_file(tab.path)

    def save_file(self, tab: EditorTab) -> bool:
        try:
            with open(tab.path, 'w', encoding='utf-8') as f:
                f.write(tab.editor.toPlainText())
            self.tabs.setTabText(self.tabs.indexOf(tab), tab.filename)
            tab.editor.document().setModified(False)
            self.status.showMessage("File saved", 2000)
            
            # Update last modified time
            if os.path.exists(tab.path):
                tab.last_modified = os.path.getmtime(tab.path)
            
            return True
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not save file:\n{e}")
            return False

    def change_font(self):
        tab = self.current_tab()
        if tab:
            ok, font = QFontDialog.getFont(tab.editor.font(), self)
            if ok:
                tab.editor.selectAll()
                tab.editor.setCurrentFont(font)
                tab.editor.setFontPointSize(font.pointSize())
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
                tab.bg_color = color.name().lstrip("#")
                tab._apply_theme(tab.bg_color)

    def set_text_color(self):
        tab = self.current_tab()
        if tab:
            color = QColorDialog.getColor()
            if color.isValid():
                tab.fg_color = color.name().lstrip("#")
                tab._apply_theme("", tab.fg_color)
    
    def toggle_watchdog(self):
        """Toggle watchdog monitoring for current tab"""
        tab = self.current_tab()
        if tab and tab.path:
            if not tab.watchdog_enabled:
                # Enable watchdog
                tab.watchdog_enabled = True
                self.file_watcher.watch_file(tab.path)
                if os.path.exists(tab.path):
                    tab.last_modified = os.path.getmtime(tab.path)
                self.watchdog_action.setChecked(True)
                self.status.showMessage(f"Monitoring {tab.filename} for external changes", 3000)
            else:
                # Disable watchdog
                tab.watchdog_enabled = False
                self.file_watcher.unwatch_file(tab.path)
                self.watchdog_action.setChecked(False)
                self.status.showMessage(f"Stopped monitoring {tab.filename}", 3000)
        elif tab and not tab.path:
            QMessageBox.information(self, "No File", "Save the file first to enable monitoring.")
            self.watchdog_action.setChecked(False)

    def on_file_changed_externally(self, filepath):
        """Handle file change detected by watchdog"""


        # Debounce: ignore notifications within 2 seconds
        current_time = time.time()
        last_time = self.last_notification_time.get(filepath, 0)  # <<--- Add this dict in __init__

        if current_time - last_time < 2:  # 2 second cooldown  <<--- Debounce check
            print(f"DEBUG: Ignoring rapid change for {filepath}")
            return
        
        self.last_notification_time[filepath] = current_time  # <<--- Update last time

        # Show notification immediately
        filename = os.path.basename(filepath)
        show_notification(
            "File Changed",
            f"{filename} modified externally"
        )

        #Then find tab and reload
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if isinstance(tab, EditorTab) and tab.path == filepath and tab.watchdog_enabled:
                # Update in main thread
                QTimer.singleShot(0, lambda t=tab, fp=filepath: self.reload_external_file(t, fp))
                break


    def reload_external_file(self, tab, filepath):
        """Reload file content when changed externally"""
        if not os.path.exists(filepath):
            return

        try:
            current_mtime = os.path.getmtime(filepath)
            if tab.last_modified is None or current_mtime > tab.last_modified:
                with open(filepath, 'r', encoding='utf-8') as f:
                    new_content = f.read()

                # Only reload if content is different
                if new_content != tab.editor.toPlainText():
                    # Show notification
                    show_notification(
                        "File Changed",
                        f"{tab.filename} modified externally"
                    )

                    # Ask user if they want to reload
                    reply = QMessageBox.question(
                        self, "File Changed",
                        f"{tab.filename} has been modified by another program.\nReload?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.Yes
                    )

                    if reply == QMessageBox.Yes:
                        tab.editor.setText(new_content)
                        tab.last_modified = current_mtime
                        self.status.showMessage(f"Reloaded {tab.filename} (external change)", 3000)
                    else:
                        # Update timestamp but don't reload
                        tab.last_modified = current_mtime
        except Exception as e:
            print(f"Error reloading file: {e}")

    def reload_external_file1(self, tab, filepath):
        """Reload file content when changed externally"""
        if not os.path.exists(filepath):
            return
            
        try:
            current_mtime = os.path.getmtime(filepath)
            if tab.last_modified is None or current_mtime > tab.last_modified:
                with open(filepath, 'r', encoding='utf-8') as f:
                    new_content = f.read()
                
                # Only reload if content is different
                if new_content != tab.editor.toPlainText():
                    # Ask user if they want to reload
                    reply = QMessageBox.question(
                        self, "File Changed",
                        f"{tab.filename} has been modified by another program.\nReload?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.Yes
                    )
                    
                    if reply == QMessageBox.Yes:
                        tab.editor.setText(new_content)
                        tab.last_modified = current_mtime
                        self.status.showMessage(f"Reloaded {tab.filename} (external change)", 3000)
                    else:
                        # Update timestamp but don't reload
                        tab.last_modified = current_mtime
        except Exception as e:
            print(f"Error reloading file: {e}")

    def check_all_tabs_external_changes(self):
        """Check all tabs for external changes (fallback method)"""
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if isinstance(tab, EditorTab):
                tab.check_external_changes()

    def update_title_and_status(self):
        tab = self.current_tab()
        if tab:
            self.setWindowTitle(f"{tab.filename} - Notepad")
            tab.update_status()
            # Update watchdog menu item state
            self.watchdog_action.setChecked(tab.watchdog_enabled if tab.path else False)

    def autosave_all(self):
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if isinstance(tab, EditorTab):
                tab.autosave()

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
    
    def closeEvent(self, event):
        """Cleanup on close"""
        self.file_watcher.stop()
        event.accept()

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

def get_content(arg):
    return arg

def is_port_in_use(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((host, port))
        s.close()
        return True
    except:
        return False

if __name__ == "__main__":
    arg = ""
    command = ""

    if len(sys.argv) > 1 and is_port_in_use(HOST, PORT):
        arg = get_content(sys.argv[1:])
        joined_list = ' '.join(arg)
        if send_args_to_server([joined_list]):
            command = "stop"
            sys.exit(0)
    elif is_port_in_use(HOST, PORT):
        print("App already running \n You can add arguments like nutpad.exe [filename/filepath] to send the files to nutpad")
        sys.exit(0)

    app = QApplication(sys.argv)

    pixmap = QPixmap("assets/nutpad_splashscreen.png")
    splash = QSplashScreen(pixmap, Qt.WindowStaysOnTopHint)
    splash.show()
    ensure_benguiat_font()
    apply_dark_theme(app)
    window = Notepad()
    
    server_thread = threading.Thread(target=run_server, args=(window,), daemon=True)
    server_thread.start()

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
    
    window.show()
    QTimer.singleShot(1500, splash.close)

    sys.exit(app.exec())
