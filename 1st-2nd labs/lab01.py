import sys

from PyQt6.QtCore import (QSize, Qt, QFile, QRectF, QRegularExpression, QFileInfo, QDir)
from PyQt6.QtWidgets import (QApplication, QMainWindow, QGraphicsScene, QGraphicsView, QLabel, QFileDialog, QMessageBox)
from PyQt6.QtGui import QAction, QPixmap


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Image Viewer")
        self.resize(QSize(800, 600))

        menubar = self.menuBar()
        self.file_menu = menubar.addMenu('&File')
        self.view_menu = menubar.addMenu('&View')

        self.file_tool_bar = self.addToolBar('File')
        self.view_tool_bar = self.addToolBar('View')

        self.image_scene = QGraphicsScene(self)
        self.image_view = QGraphicsView(self.image_scene)
        self.setCentralWidget(self.image_view)

        self.main_status_bar = self.statusBar()
        self.main_status_label = QLabel(self.main_status_bar)
        self.main_status_bar.addPermanentWidget(self.main_status_label)
        self.main_status_label.setText('Image Information will be here!')

        self.__create_actions()

    def __create_actions(self):
        self.open_action = QAction('&Open', self)
        self.save_as_action = QAction('&Save as', self)
        self.exit_action = QAction('&Exit', self)
        file_actions = [self.open_action, self.save_as_action, self.exit_action]
        self.file_menu.addActions(file_actions)

        self.zoom_in_action = QAction('Zoom In', self)
        self.zoom_out_action = QAction('Zoom Out', self)
        self.prev_action = QAction('&Previous Image', self)
        self.next_action = QAction('&Next Image', self)
        view_actions = [self.zoom_in_action, self.zoom_out_action, self.prev_action, self.next_action]
        self.view_menu.addActions(view_actions)

        self.file_tool_bar.addAction(self.open_action)
        self.view_tool_bar.addActions(view_actions)

        self.exit_action.triggered.connect(self.close)
        self.open_action.triggered.connect(self.__open_image)
        self.save_as_action.triggered.connect(self.__save_as)
        self.zoom_in_action.triggered.connect(self.__zoom_in)
        self.zoom_out_action.triggered.connect(self.__zoom_out)
        self.prev_action.triggered.connect(self.__prev_image)
        self.next_action.triggered.connect(self.__next_image)

        self.__setup_shortcuts()

    def __open_image(self):
        self.dialog = QFileDialog(self)
        self.dialog.setWindowTitle('Open Image')
        self.dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        self.dialog.setNameFilter(self.tr('Images (*.png *.bmp *.jpg)'))
        file_paths = []
        if self.dialog.exec():
            file_paths = self.dialog.selectedFiles()
            self.__show_image(file_paths[0])

    # Не работает :\
    def __show_image(self, path):
        self.image_scene.clear()
        self.image_view.resetTransform()
        self.image = QPixmap(path)
        self.cur_img = self.image_scene.addPixmap(self.image)
        self.image_scene.update()
        self.image_view.setSceneRect(QRectF(self.image.rect()))
        status = f'{path}, {self.image.width()}x{self.image.height()}, {QFile(path).size()} Bytes'
        self.main_status_label.setText(status)
        self.current_image_path = path

    def __save_as(self):
        try:
            self.cur_img
        except Exception:
            QMessageBox.information(self, 'Information', 'Nothing to save')
            return
        self.dialog = QFileDialog(self)
        self.dialog.setWindowTitle('Save Image As...')
        self.dialog.setFileMode(QFileDialog.FileMode.AnyFile)
        self.dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        self.dialog.setNameFilter(self.tr('Images (*.png *.bmp *.jpg)'))
        file_names = []
        if self.dialog.exec():
            file_names = self.dialog.selectedFiles()
            if QRegularExpression('.+\\.(png|bmp|jpg)').match(file_names[0]):
                self.cur_img.pixmap().save(file_names[0])
            else:
                QMessageBox.information(
                    self, 'Information', 'Save Error: bad format or filename.')

    def __zoom_in(self):
        self.image_view.scale(1.2, 1.2)

    def __zoom_out(self):
        self.image_view.scale(1/1.2, 1/1.2)

    def __prev_image(self):
        try:
            self.cur = QFileInfo(self.current_image_path)
        except Exception:
            QMessageBox.information(self, 'Information', 'No image selected.')
            return
        self.dir = QDir(self.cur.absoluteDir())
        self.name_filters = ['*.png', '*.bmp', '*.jpg']
        self.file_names = self.dir.entryList(
            self.name_filters, QDir.Filter.Files, QDir.SortFlag.Name)
        idx = self.file_names.index(self.cur.fileName())
        if idx > 0:
            self.__show_image(self.dir.absoluteFilePath(
                self.file_names[idx - 1]))
        else:
            QMessageBox.information(
                self, 'Information', 'Current image is the last one.')

    def __next_image(self):
        try:
            self.cur = QFileInfo(self.current_image_path)
        except Exception:
            QMessageBox.information(self, 'Information', 'No image selected.')
            return
        self.dir = QDir(self.cur.absoluteDir())
        self.name_filters = ['*.png', '*.bmp', '*.jpg']
        self.file_names = self.dir.entryList(
            self.name_filters, QDir.Filter.Files, QDir.SortFlag.Name)
        idx = self.file_names.index(self.cur.fileName())
        if idx < len(self.file_names) - 1:
            self.__show_image(self.dir.absoluteFilePath(
                self.file_names[idx + 1]))
        else:
            QMessageBox.information(
                self, 'Information', 'Current image is the last one.')

    def __setup_shortcuts(self):
        shortcuts = [Qt.Key.Key_Plus, Qt.Key.Key_Equal]
        self.zoom_in_action.setShortcuts(shortcuts)

        shortcuts = [Qt.Key.Key_Minus, Qt.Key.Key_Underscore]
        self.zoom_out_action.setShortcuts(shortcuts)

        shortcuts = [Qt.Key.Key_Up, Qt.Key.Key_Left]
        self.prev_action.setShortcuts(shortcuts)

        shortcuts = [Qt.Key.Key_Down, Qt.Key.Key_Right]
        self.next_action.setShortcuts(shortcuts)


app = QApplication(sys.argv)

window = MainWindow()
window.show()

app.exec()