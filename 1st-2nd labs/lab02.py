import sys
import numpy as np
import time
import cv2 as cv

from PIL import Image
import io

from PyQt6.QtCore import (QSize, Qt, QFile, QRectF, QRegularExpression, QFileInfo, QDir, QIODeviceBase, QBuffer)
from PyQt6.QtWidgets import (QApplication, QMainWindow, QGraphicsScene, QGraphicsView, QLabel, QFileDialog, QMessageBox)
from PyQt6.QtGui import (QAction, QPixmap, QImage)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Image Viewer")
        self.resize(QSize(800, 600))

        menubar = self.menuBar()
        self.file_menu = menubar.addMenu('&File')
        self.view_menu = menubar.addMenu('&View')
        self.filters_menu = menubar.addMenu('Filters')

        self.file_tool_bar = self.addToolBar('File')
        self.view_tool_bar = self.addToolBar('View')
        self.filters_tool_bar = self.addToolBar('Filters')

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
        file_actions = [self.open_action,
                        self.save_as_action, self.exit_action]
        self.file_menu.addActions(file_actions)

        self.zoom_in_action = QAction('Zoom In', self)
        self.zoom_out_action = QAction('Zoom Out', self)
        self.prev_action = QAction('&Previous Image', self)
        self.next_action = QAction('&Next Image', self)
        view_actions = [self.zoom_in_action, self.zoom_out_action,
                        self.prev_action, self.next_action]
        self.view_menu.addActions(view_actions)

        self.median_filter = QAction('&Median Filter', self)
        self.affine_plugin = QAction('&Affine', self)
        self.rotate_plugin = QAction('&Rotate', self)
        self.cartoon_plugin = QAction('&Cartoon', self)
        self.erode_plugin = QAction('&Erode', self)
        self.sharpen_plugin = QAction('&Sharpen', self)

        filters_actions = [self.median_filter,
                           self.affine_plugin,
                           self.rotate_plugin,
                           self.cartoon_plugin,
                           self.erode_plugin,
                           self.sharpen_plugin]
        self.filters_menu.addActions(filters_actions)

        self.file_tool_bar.addAction(self.open_action)
        self.view_tool_bar.addActions(view_actions)
        self.filters_tool_bar.addActions(filters_actions)

        self.exit_action.triggered.connect(self.close)
        self.open_action.triggered.connect(self.__open_image)
        self.save_as_action.triggered.connect(self.__save_as)
        self.zoom_in_action.triggered.connect(self.__zoom_in)
        self.zoom_out_action.triggered.connect(self.__zoom_out)
        self.prev_action.triggered.connect(self.__prev_image)
        self.next_action.triggered.connect(self.__next_image)
        self.median_filter.triggered.connect(self.__make_median)
        self.affine_plugin.triggered.connect(self.__affine_plugin)
        self.rotate_plugin.triggered.connect(self.__rotate_plugin)
        self.cartoon_plugin.triggered.connect(self.__cartoon_plugin)
        self.erode_plugin.triggered.connect(self.__erode_plugin)
        self.sharpen_plugin.triggered.connect(self.__sharpen_plugin)

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

    def __QImage2array(self, image):
        image = image.pixmap().toImage().convertToFormat(QImage.Format.Format_RGB888)
        buffer = QBuffer()
        buffer.open(QIODeviceBase.OpenModeFlag.ReadWrite)
        image.save(buffer, "PNG")
        pil_im = Image.open(io.BytesIO(buffer.data()))
        return np.array(pil_im)


    def __make_median(self):
        try:
            image_arr = self.__QImage2array(self.cur_img)
        except Exception as e:
            print(e)
            return

        w, h, c = image_arr.shape
        k = 3
        size = k // 2
        _img = np.zeros((w + 2 * size, h + 2 * size, c), dtype=np.float32)
        _img[size:size+w, size:size+h] = image_arr.copy().astype(np.float32)
        dst = _img.copy()
        start_time = time.time()

        for x in np.arange(w):
            for y in np.arange(h):
                for z in np.arange(c):
                    dst[x+size, y+size, z] = np.median(_img[x:x+k, y:y+k, z])

        dst = dst[size:size+w, size:size+h].astype(np.uint8)

        dst_2 = cv.medianBlur(image_arr, k)
        diff = cv.absdiff(dst, dst_2)
        print(diff.shape)
        cv.imshow('color image', diff)
        print("--- %s seconds ---" % (time.time() - start_time))
        self.__show_filtered_image(dst)

    def __affine_plugin(self):
        try:
            image_arr = self.__QImage2array(self.cur_img)
        except:
            return

        pts1 = np.float32([[0, 0],
                           [1, 0],
                           [0, 1]])

        pts2 = np.float32([[0, 0],
                           [1, 0],
                           [1, 1]])

        warp_mat = cv.getAffineTransform(pts1, pts2)

        warp_dst = cv.warpAffine(
            image_arr, warp_mat, (image_arr.shape[1], image_arr.shape[0]), cv.INTER_CUBIC, cv.BORDER_CONSTANT)
        self.__show_filtered_image(warp_dst)

    def __rotate_plugin(self):
        try:
            image_arr = self.__QImage2array(self.cur_img)
        except:
            return

        h, w = image_arr.shape[:2]
        cX, cY = w // 2, h // 2

        M = cv.getRotationMatrix2D((cX, cY), 45, 1.0)
        rotated_dst = cv.warpAffine(image_arr, M, (w, h))
        self.__show_filtered_image(rotated_dst)

    def __cartoon_plugin(self):
        try:
            image_arr = self.__QImage2array(self.cur_img)
        except:
            return

        gray = cv.cvtColor(image_arr, cv.COLOR_BGR2GRAY)
        gray = cv.medianBlur(gray, 7)
        edges = cv.adaptiveThreshold(
            gray, 255, cv.ADAPTIVE_THRESH_MEAN_C, cv.THRESH_BINARY, 9, 10)

        color = cv.bilateralFilter(image_arr, 12, 250, 250)
        cartoon = cv.bitwise_and(color, color, mask=edges)

        self.__show_filtered_image(cartoon)

    def __erode_plugin(self):
        try:
            image_arr = self.__QImage2array(self.cur_img)
        except:
            return

        kernel = np.ones((5, 5), np.uint8)
        eroded_image = cv.erode(image_arr, kernel, iterations=1)

        self.__show_filtered_image(eroded_image)

    def __sharpen_plugin(self):
        try:
            image_arr = self.__QImage2array(self.cur_img)
        except:
            return
        
        kernel = np.array([[-1,-1,-1], 
                           [-1, 9,-1],
                           [-1,-1,-1]])
        sharpened_image = cv.filter2D(image_arr, -1, kernel)

        self.__show_filtered_image(sharpened_image)

    def __show_filtered_image(self, img_arr):
        self.image_scene.clear()
        self.image_view.resetTransform()
        height, width, _ = img_arr.shape
        bytesPerLine = 3 * width
        qImg = QImage(img_arr.data, width, height,
                      bytesPerLine, QImage.Format.Format_RGB888)
        self.image = QPixmap(qImg)
        self.cur_img = self.image_scene.addPixmap(self.image)
        self.image_scene.update()
        self.image_view.setSceneRect(QRectF(self.image.rect()))

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
