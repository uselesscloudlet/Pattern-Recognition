from enum import Enum, auto
import cv2 as cv
import numpy as np

from PyQt6.QtCore import (
    QThread, QMutex, QElapsedTimer, QObject, pyqtSignal, QTime)

from utils import new_saved_video_name, get_saved_video_path


class Communicate(QObject):
    fps_changed = pyqtSignal(float)
    frame_captured = pyqtSignal(np.ndarray)
    video_saved = pyqtSignal(str)
    data_changed = pyqtSignal(float, float, float)


class CaptureThread(QThread):
    class VideoSavingStatus(Enum):
        STARTING = auto()
        STARTED = auto()
        STOPPING = auto()
        STOPPED = auto()

    def __init__(self, camera_id: int, lock: QMutex):
        super(CaptureThread, self).__init__()
        self.__running = False
        self.__camera_id = camera_id
        self.__video_path = ''
        self.__data_lock = lock

        self.signals = Communicate()

        self.fps_calculating = False
        self.motion_detected = False
        self.motion_detecting_status = False

        self.frame_width = 0
        self.frame_height = 0
        self.fps = 0.0

        self.video_saving_status = self.VideoSavingStatus.STOPPED
        self.saved_video_name = ''
        self.video_writer = None

        self.curr_frame_ind = 0
        self.fps_buffer = [None] * 100

    def calculate_fps(self, cap: cv.VideoCapture):
        count_to_read = 100
        timer = QElapsedTimer()
        timer.start()

        for _ in np.arange(0, count_to_read):
            _, _ = cap.read()

        elapsed_ms = timer.elapsed()

        self.fps = count_to_read / (elapsed_ms / 1000.0)
        self.fps_calculating = False
        self.signals.fps_changed.emit(self.fps)

    def start_calc_fps(self):
        self.fps_calculating = True

    def run(self):
        self.__running = True
        cap = cv.VideoCapture(self.__camera_id)
        self.frame_width = int(cap.get(cv.CAP_PROP_FRAME_WIDTH))
        self.frame_height = int(cap.get(cv.CAP_PROP_FRAME_HEIGHT))

        self.segmentor = cv.createBackgroundSubtractorMOG2(500, 16, True)

        while self.__running:
            if self.fps_calculating:
                self.calculate_fps(cap)

            _, tmp_frame = cap.read()

            if tmp_frame is None:
                break

            if self.motion_detecting_status:
                self.__motion_detect(tmp_frame)

            if self.video_saving_status == self.VideoSavingStatus.STARTING:
                self.start_saving_video(tmp_frame)
            elif self.video_saving_status == self.VideoSavingStatus.STARTED:
                self.video_writer.write(tmp_frame)
            elif self.video_saving_status == self.VideoSavingStatus.STOPPING:
                self.stop_saving_video()

            tmp_frame = cv.cvtColor(tmp_frame, cv.COLOR_BGR2RGB)

            self.__calc_data(tmp_frame)

            self.__data_lock.lock()
            frame = tmp_frame
            self.__data_lock.unlock()

            self.signals.frame_captured.emit(frame)
        cap.release()
        cv.destroyAllWindows()
        self.__running = False

    def start_saving_video(self, first_frame: np.ndarray):
        self.saved_video_name = new_saved_video_name()
        cover = get_saved_video_path(self.saved_video_name, 'jpg')
        cv.imwrite(cover, first_frame)
        self.video_writer = cv.VideoWriter(
            get_saved_video_path(self.saved_video_name, 'avi'),
            cv.VideoWriter_fourcc('M', 'J', 'P', 'G'),
            self.fps if self.fps else 30,
            (self.frame_width, self.frame_height)
        )
        self.video_saving_status = self.VideoSavingStatus.STARTED

    def stop_saving_video(self):
        self.video_saving_status = self.VideoSavingStatus.STOPPED
        self.video_writer.release()
        self.video_writer = None
        self.signals.video_saved.emit(self.saved_video_name)

    def set_running(self, running):
        self.__running = running

    def set_video_saving_status(self, status):
        self.video_saving_status = status

    def __motion_detect(self, frame: np.ndarray):
        mask = self.segmentor.apply(frame)
        _, mask = cv.threshold(mask, 25, 255, cv.THRESH_BINARY)
        noise_size = 9
        kernel = cv.getStructuringElement(
            cv.MORPH_RECT, (noise_size, noise_size))
        mask = cv.erode(mask, kernel)
        mask = cv.dilate(mask, kernel, iterations=3)

        contours, _ = cv.findContours(
            mask, cv.RETR_TREE, cv.CHAIN_APPROX_SIMPLE)

        has_motion = len(contours) > 0

        if not self.motion_detected and has_motion:
            self.motion_detected = True
            self.video_saving_status = self.VideoSavingStatus.STARTING
            print('New motion detected, should send a notification.')
            #! https://stackoverflow.com/questions/32378719/qtconcurrent-in-pyside-pyqt
            #! QtConcurrent in PyQt is unavaliable
        elif self.motion_detected and not has_motion:
            self.motion_detected = False
            self.video_saving_status = self.VideoSavingStatus.STOPPING
            print('Detected motion disappeared.')

        color = (0, 0, 255)
        for contour in contours:
            rect = cv.boundingRect(contour)
            frame = cv.rectangle(frame, rect, color, 1)

    def set_motion_detecting_status(self, status: bool):
        self.motion_detecting_status = status
        self.motion_detected = False
        if self.video_saving_status != self.VideoSavingStatus.STOPPED:
            self.video_saving_status = self.VideoSavingStatus.STOPPING

    def __calc_data(self, frame: np.ndarray):
        now = QTime.currentTime()
        if self.curr_frame_ind > 0:
            if self.curr_frame_ind < 100:
                self.fps = self.curr_frame_ind / \
                    (self.fps_buffer[0].msecsTo(now) / 1000.0)
            else:
                self.fps = 100 / \
                    (self.fps_buffer[(self.curr_frame_ind +
                     100 + 1) % 100].msecsTo(now) / 1000.0)

        self.fps_buffer[self.curr_frame_ind % 100] = now
        self.curr_frame_ind += 1

        # if count without numpy, we will iterate by every pixel and:
        # *a. get mean of every pixel (r + g + b) / 3 and get mean of frame (sum of every mean of pixel / area of frame (h * w))
        # b. get sums of R, G, B channels, divide every by area of frame
        mean_frame = round(np.mean(frame), 2)

        # another implementation of std: std = np.sqrt(((frame - mean)**2).mean((1,2), keepdims=True))
        std_frame = round(np.std(frame), 2)

        self.signals.data_changed.emit(
            round(self.fps, 2), mean_frame, std_frame)
