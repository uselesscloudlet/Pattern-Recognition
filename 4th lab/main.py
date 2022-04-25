from functools import partial
import sys
import numpy as np
from enum import Enum, auto
from pathlib import Path

from PyQt6.QtCore import (QSize, Qt, QRectF)
from PyQt6.QtWidgets import (QApplication, QMainWindow, QGraphicsView,
                             QLabel, QGridLayout, QWidget, QPushButton, QVBoxLayout, QFormLayout, QSlider, QFileDialog)
from PyQt6.QtGui import (QAction, QPixmap, QImage)

from cap import CaptureThread
from graphicsScene import GraphicsScene


class MainWindow(QMainWindow):
    class SelectState(Enum):
        FIRST_POINT_SELECTED = auto()
        SELECTING_SECOND_POINT = auto()
        TWO_POINTS_ARE_SELECTED = auto()
        NO_SELECTED_POINTS = auto()
        SELECTING_POINTS = auto()

    def __init__(self):
        super().__init__()
        self.capturer = None
        self.__init_ui()
        self.__create_actions()
        self.__init_params()
        self.__turn_on_camera()

    def __init_ui(self):
        self.resize(QSize(1000, 800))
        self.setWindowTitle('Camera Detection')

        self.menu_bar = self.menuBar()
        self.actions_tool_bar = self.addToolBar('Actions')

        self.main_status_bar = self.statusBar()
        self.main_status_label = QLabel(self.main_status_bar)
        self.main_status_bar.addPermanentWidget(self.main_status_label)
        self.main_status_label.setText('Here will be spawn status text')

        self.main_layout = QGridLayout()

        self.image_scene = GraphicsScene(self)
        self.image_scene.signals.send_press_pos.connect(
            self.__update_click_pos)
        self.image_scene.signals.send_move_pos.connect(
            self.__update_mouse_pos)
        self.image_scene.signals.send_release_pos.connect(
            self.__update_release_pos)
        self.image_view = QGraphicsView(self.image_scene)

        self.fps_l = QLabel('FPS')
        self.mean_pi_l = QLabel('Mean Pixel Intensity')
        self.pi_std_l = QLabel('Pixel Intensity STD')
        self.min_max_pi_l = QLabel('Min / Max Pixel Intensity')
        # self.coords_bright_l = QLabel('Coords and Pixel Brightness')

        self.info_layout = QFormLayout()
        self.info_layout.addWidget(self.fps_l)
        self.info_layout.addWidget(self.mean_pi_l)
        self.info_layout.addWidget(self.pi_std_l)
        self.info_layout.addWidget(self.min_max_pi_l)
        # self.info_layout.addWidget(self.coords_bright_l)

        self.main_layout.addWidget(self.image_view, 0, 0)
        self.main_layout.addLayout(self.info_layout, 0, 1, 1, 3)

        widget = QWidget()
        widget.setLayout(self.main_layout)
        self.setCentralWidget(widget)

    def __create_actions(self):
        manual_mode_act = QAction('&Manual Mode', self)
        manual_mode_act.triggered.connect(self.__manual_mode)

        motion_mode_act = QAction('&Motion Mode', self)
        motion_mode_act.triggered.connect(self.__motion_mode)

        contrast_mode_act = QAction('&Contrast Mode', self)
        contrast_mode_act.triggered.connect(self.__contrast_mode)

        neural_net_act = QAction('&Neural Mode', self)
        neural_net_act.triggered.connect(self.__neural_mode)

        actions = [manual_mode_act,
                   motion_mode_act,
                   contrast_mode_act,
                   neural_net_act]
        self.actions_tool_bar.addActions(actions)

    def __init_params(self):
        self.fps = None
        self.mpi = None
        self.pi_std = None
        self.min_max_pi = None
        self.coords_bright = None

        self.click_pos = None
        self.mouse_pos = None
        self.release_pos = None
        self.bbox_status = self.SelectState.NO_SELECTED_POINTS

        self.slider_info = dict()

    def __turn_on_camera(self):
        if self.capturer is not None:
            self.capturer.video_capture = False
            self.capturer.signals.captured_frame.disconnect(
                self.__update_frame)
            self.capturer.signals.current_fps.disconnect(
                self.__update_fps
            )
            self.capturer.signals.mean_pi.disconnect(self.__update_mean_pi)
            self.capturer.signals.pi_std.disconnect(self.__update_pi_std)
            self.capturer.signals.min_max_pi.disconnect(
                self.__update_min_max_pi)
            self.capturer.signals.update_data.disconnect(self.__update_data)
        else:
            camera_id = 0
            self.capturer = CaptureThread(camera_id)
            self.capturer.signals.captured_frame.connect(self.__update_frame)
            self.capturer.signals.current_fps.connect(self.__update_fps)
            self.capturer.signals.mean_pi.connect(self.__update_mean_pi)
            self.capturer.signals.pi_std.connect(self.__update_pi_std)
            self.capturer.signals.min_max_pi.connect(self.__update_min_max_pi)
            self.capturer.signals.update_data.connect(self.__update_data)
            self.capturer.start()

    def __update_frame(self, frame: np.ndarray):
        height, width, _ = frame.shape
        bytes_per_line = 3 * width
        image = QImage(frame,
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

    def __update_fps(self, fps: float):
        self.fps = fps

    def __update_mean_pi(self, mean_pi: np.ndarray):
        self.mpi = mean_pi

    def __update_pi_std(self, pi_std: np.ndarray):
        self.pi_std = pi_std

    def __update_min_max_pi(self, min_max_pi):
        self.min_max_pi = min_max_pi

    def __mouse_in_view(self, click_pos: tuple):
        scene_width = self.image_scene.sceneRect().width()
        scene_height = self.image_scene.sceneRect().height()
        if click_pos[0] < 0 or click_pos[1] < 0:
            return False
        elif click_pos[0] > scene_width or click_pos[1] > scene_height:
            return False
        else:
            return True

    def __update_click_pos(self, click_pos: tuple):
        if self.__mouse_in_view(click_pos):
            self.click_pos = click_pos
        else:
            self.click_pos = None
        if self.bbox_status == self.SelectState.SELECTING_POINTS:
            self.bbox_status = self.SelectState.FIRST_POINT_SELECTED

    def __update_mouse_pos(self, mouse_pos: tuple):
        if self.__mouse_in_view(mouse_pos):
            self.mouse_pos = mouse_pos
        if self.bbox_status == self.SelectState.FIRST_POINT_SELECTED:
            self.bbox_status = self.SelectState.SELECTING_SECOND_POINT
        if self.bbox_status == self.SelectState.FIRST_POINT_SELECTED or self.bbox_status == self.SelectState.SELECTING_SECOND_POINT:
            bbox = np.array([self.click_pos, self.mouse_pos])
            if self.capturer is not None:
                self.capturer.bbox = bbox

    def __update_release_pos(self, release_pos: tuple):
        if self.__mouse_in_view(release_pos):
            self.release_pos = release_pos
        else:
            self.release_pos = self.mouse_pos
        if self.bbox_status == self.SelectState.SELECTING_SECOND_POINT:
            bbox = np.array([self.click_pos, self.mouse_pos])
            if self.capturer is not None:
                self.capturer.bbox = bbox
            self.capturer.current_mode = self.capturer.DetectionMode.MANUAL
            self.capturer.mode_state = self.capturer.ModeState.INIT
            self.bbox_status = self.SelectState.TWO_POINTS_ARE_SELECTED

    def __update_data(self):
        self.fps_l.setText(f'FPS: {self.fps}')
        self.mean_pi_l.setText(
            f'Mean Pixel Intensity:\n{np.round(self.mpi, 2).flatten()}')
        self.pi_std_l.setText(
            f'Pixel Intensity STD:\n{np.round(self.pi_std, 2).flatten()}')
        self.min_max_pi_l.setText(
            f'Min / Max Pixel Intensity:\n{self.min_max_pi}')
        # self.coords_bright_l.setText(
        #     f'Coords and Pixel Brightness:\n{self.coords_bright}')

    def __manual_mode(self):
        self.capturer.bbox = None
        self.capturer.current_mode = self.capturer.current_mode.DRAW
        self.capturer.mode_state = self.capturer.ModeState.DEFAULT
        self.bbox_status = self.SelectState.SELECTING_POINTS
        self.__clear_sliders()

    def __motion_mode(self):
        self.capturer.bbox = None
        self.capturer.current_mode = self.capturer.current_mode.MOTION
        self.capturer.mode_state = self.capturer.ModeState.DEFAULT
        self.__clear_sliders()
        h_min_slider = self.__create_custom_slider('H min', 0, 255, 150, 0)
        h_max_slider = self.__create_custom_slider('H max', 0, 255, 150, 255)
        s_min_slider = self.__create_custom_slider('S min', 0, 255, 150, 0)
        s_max_slider = self.__create_custom_slider('S max', 0, 255, 150, 255)
        v_min_slider = self.__create_custom_slider('V min', 0, 255, 150, 0)
        v_max_slider = self.__create_custom_slider('V max', 0, 255, 150, 255)
        btn = QPushButton('Применить')
        btn.clicked.connect(self.__apply_det_params)

        self.info_layout.addRow(h_min_slider)
        self.info_layout.addRow(h_max_slider)
        self.info_layout.addRow(s_min_slider)
        self.info_layout.addRow(s_max_slider)
        self.info_layout.addRow(v_min_slider)
        self.info_layout.addRow(v_max_slider)
        self.info_layout.addRow(btn)

    def __contrast_mode(self):
        self.capturer.bbox = None
        self.capturer.current_mode = self.capturer.current_mode.CONTRAST
        self.capturer.mode_state = self.capturer.ModeState.DEFAULT
        self.__clear_sliders()
        h_min_slider = self.__create_custom_slider(
            'Brightness min', 0, 255, 150, 0)
        h_max_slider = self.__create_custom_slider(
            'Brightness max', 0, 255, 150, 255)

        self.info_layout.addRow(h_min_slider)
        self.info_layout.addRow(h_max_slider)

    def __neural_mode(self):
        self.capturer.bbox = None
        self.capturer.current_mode = self.capturer.current_mode.NEURAL
        self.capturer.mode_state = self.capturer.ModeState.INIT
        self.__clear_sliders()
        
        input_model_btn = QPushButton('Выбрать модель')
        input_classes_btn = QPushButton('Выбрать файл с классами')


        input_model_btn.clicked.connect(self.__onInputModelClick)
        input_classes_btn.clicked.connect(self.__onInputClassesClick)

        self.info_layout.addRow(input_model_btn)
        self.info_layout.addRow(input_classes_btn)

    def __onInputModelClick(self):
        home_dir = str(Path.home())
        fname = QFileDialog.getOpenFileName(self, 'Open file', home_dir)
        self.capturer.model_path = fname[0]

    def __onInputClassesClick(self):
        home_dir = str(Path.home())
        fname = QFileDialog.getOpenFileName(self, 'Open file', home_dir)
        self.capturer.classes_path = fname[0]

    def __clear_sliders(self):
        count = self.info_layout.count()
        for i in reversed(range(5, count)):
            self.info_layout.removeRow(i)

    def __create_custom_slider(self, label, min_val, max_val, max_width, first_val):
        l = QLabel(label)
        sl = QSlider(Qt.Orientation.Horizontal)
        sl.setMinimum(min_val)
        sl.setMaximum(max_val)
        sl.setMaximumWidth(max_width)
        sl.setValue(first_val)
        sl.valueChanged.connect(partial(self.value_changed, name=label))
        self.slider_info[label] = first_val
        self.capturer.slider_info[label] = first_val

        layout = QVBoxLayout()
        layout.addWidget(l)
        layout.addWidget(sl)

        return layout

    def value_changed(self, val, name):
        self.slider_info[name] = val
        self.capturer.slider_info = self.slider_info

    def __apply_det_params(self):
        self.capturer.mode_state = self.capturer.ModeState.INIT


def main():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    app.exec()


if __name__ == '__main__':
    main()
