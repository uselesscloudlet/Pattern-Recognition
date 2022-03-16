import sys
import numpy as np

from PyQt6.QtCore import (QSize, Qt, QDir, QMutex, QRectF)
from PyQt6.QtWidgets import (QApplication, QMainWindow, QGraphicsScene, QGraphicsView,
                             QLabel, QMessageBox, QGridLayout, QWidget, QCheckBox, QPushButton, QListView)
from PyQt6.QtGui import (QAction, QPixmap, QImage,
                         QStandardItemModel, QStandardItem)
from PyQt6.QtMultimedia import (QMediaDevices, QCamera, QMediaCaptureSession)
from PyQt6.QtMultimediaWidgets import QVideoWidget

from utils import get_saved_video_path, get_data_path
from cap import CaptureThread


class MainWindow(QMainWindow):
    USE_CAMERA = False

    def __init__(self):
        super().__init__()
        self.capturer = None
        self.__init_ui()
        self.__create_actions()
        self.__populate_saved_list()
        self.data_lock = QMutex()

    def __init_ui(self):
        self.resize(QSize(1000, 800))
        self.setWindowTitle('Video Viewer')

        menubar = self.menuBar()
        self.file_menu = menubar.addMenu('&File')

        self.main_status_bar = self.statusBar()
        self.main_status_label = QLabel(self.main_status_bar)
        self.main_status_bar.addPermanentWidget(self.main_status_label)
        self.main_status_label.setText('Video Viewer is Ready')

        main_layout = QGridLayout()

        if self.USE_CAMERA:
            cameras = QMediaDevices.videoInputs()

            if not cameras:
                sys.exit()

            self.camera = QCamera(cameras[0])

            capture_session = QMediaCaptureSession()
            capture_session.setCamera(self.camera)

            video = QVideoWidget()
            main_layout.addWidget(video, 0, 0, 12, 1)
            capture_session.setVideoOutput(video)
        else:
            self.image_scene = QGraphicsScene(self)
            self.image_view = QGraphicsView(self.image_scene)
            main_layout.addWidget(self.image_view, 0, 0, 12, 1)

        tools_layout = QGridLayout()
        main_layout.addLayout(tools_layout, 12, 0, 1, 1)

        monitor_check_box = QCheckBox(self)
        monitor_check_box.setText('Monitor On/Off')
        tools_layout.addWidget(monitor_check_box, 0, 0)

        self.record_button = QPushButton()
        self.record_button.setText('Record')
        tools_layout.addWidget(self.record_button, 0, 1,
                               Qt.AlignmentFlag.AlignHCenter)
        tools_layout.addWidget(QLabel(self), 0, 2)

        self.saved_list = QListView(self)
        self.saved_list.setViewMode(QListView.ViewMode.IconMode)
        self.saved_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.saved_list.setSpacing(5)
        self.saved_list.setWrapping(False)
        self.list_model = QStandardItemModel(self)
        self.saved_list.setModel(self.list_model)
        main_layout.addWidget(self.saved_list, 13, 0, 4, 1)

        self.record_button.clicked.connect(self.__recording_start_stop)

        widget = QWidget()
        widget.setLayout(main_layout)
        self.setCentralWidget(widget)

    def __create_actions(self):
        camera_info_action = QAction('&Camera Info', self)
        camera_info_action.triggered.connect(self.__show_camera_info)

        open_camera_action = QAction('&Open Camera', self)
        open_camera_action.triggered.connect(self.__open_camera)

        calculate_FPS_action = QAction('&Calculate FPS', self)
        calculate_FPS_action.triggered.connect(self.__calculate_fps)

        exit_action = QAction('&Exit', self)
        exit_action.triggered.connect(self.close)

        actions = [camera_info_action,
                   open_camera_action,
                   calculate_FPS_action,
                   exit_action]

        self.file_menu.addActions(actions)

    def __recording_start_stop(self):
        text = self.record_button.text()
        if text == 'Record' and self.capturer is not None:
            self.capturer.set_video_saving_status(
                CaptureThread.VideoSavingStatus.STARTING)
            self.record_button.setText('Stop Recording')
        elif text == 'Stop Recording' and self.capturer is not None:
            self.capturer.set_video_saving_status(
                CaptureThread.VideoSavingStatus.STOPPING)
            self.record_button.setText('Record')

    def __show_camera_info(self):
        cameras = QMediaDevices.videoInputs()
        info = 'Avaliable Cameras:\n'
        for cam in cameras:
            info += f'- {cam.description()}\n'
        QMessageBox.information(self, 'Cameras', info)

    def __open_camera(self):
        if self.USE_CAMERA:
            self.camera.start()
        else:
            if self.capturer is not None:
                self.capturer.set_running(False)
                self.capturer.signals.frame_captured.disconnect(
                    self.__update_frame)
                self.capturer.signals.fps_changed.disconnect(self.__update_fps)
                self.capturer.signals.video_saved.disconnect(
                    self.__append_saved_video)

            camID = 0
            self.capturer = CaptureThread(camID, self.data_lock)
            self.capturer.signals.frame_captured.connect(self.__update_frame)
            self.capturer.signals.fps_changed.connect(self.__update_fps)
            self.capturer.signals.video_saved.connect(
                self.__append_saved_video)
            self.capturer.start()
            self.main_status_label.setText(f'Capturing Camera {camID}')

    def __update_frame(self, frame: np.ndarray):
        self.data_lock.lock()
        current_frame = frame
        self.data_lock.unlock()
        height, width, _ = current_frame.shape
        bytes_per_line = 3 * width
        image = QImage(current_frame,
                       width,
                       height,
                       bytes_per_line,
                       QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(image)
        self.image_scene.clear()
        self.image_view.resetTransform()
        self.image_scene.addPixmap(pixmap)
        self.image_scene.update()
        self.image_view.setSceneRect(QRectF(pixmap.rect()))

    def __update_fps(self):
        self.main_status_label.setText(
            f'FPS of current camera is {self.capturer.fps}')

    def __append_saved_video(self, name: str):
        cover = get_saved_video_path(name, 'jpg')
        item = QStandardItem()
        self.list_model.appendRow(item)
        index = self.list_model.indexFromItem(item)
        self.list_model.setData(index, QPixmap(cover).scaledToHeight(
            145), Qt.ItemDataRole.DecorationRole)
        self.list_model.setData(index, name, Qt .ItemDataRole.DisplayRole)
        self.saved_list.scrollTo(index)

    def __calculate_fps(self):
        if self.capturer is not None:
            self.capturer.start_calc_fps()

    def __populate_saved_list(self):
        dir = QDir(get_data_path())
        name_filters = ['*.jpg']
        files = dir.entryInfoList(
            name_filters,
            QDir.Filter.NoDotAndDotDot | QDir.Filter.Files,
            QDir.SortFlag.Name
        )
        for cover in files:
            name = cover.baseName()
            item = QStandardItem()
            self.list_model.appendRow(item)
            index = self.list_model.indexFromItem(item)
            self.list_model.setData(index, QPixmap(cover).scaledToHeight(
                145), Qt.ItemDataRole.DecorationRole)
            self.list_model.setData(index, name, Qt.ItemDataRole.DisplayRole)


def main():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    app.exec()


if __name__ == '__main__':
    main()
