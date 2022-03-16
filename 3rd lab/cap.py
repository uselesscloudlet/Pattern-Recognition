from enum import Enum, auto
import cv2 as cv
import numpy as np

from PyQt6.QtCore import (QThread, QMutex, QElapsedTimer, QObject, pyqtSignal)

from utils import new_saved_video_name, get_saved_video_path


class Communicate(QObject):
    fps_changed = pyqtSignal(float)
    frame_captured = pyqtSignal(np.ndarray)
    video_saved = pyqtSignal(str)


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
        self.fps = 0.0

        self.frame_width = 0
        self.frame_height = 0
        self.video_saving_status = self.VideoSavingStatus.STOPPED
        self.saved_video_name = ''
        self.video_writer = None

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

        while self.__running:
            if self.fps_calculating:
                self.calculate_fps(cap)

            self.__data_lock.lock()
            _, frame = cap.read()
            frame = cv.cvtColor(frame, cv.COLOR_BGR2RGB)
            self.__data_lock.unlock()
            if frame is None:
                break

            if self.video_saving_status == self.VideoSavingStatus.STARTING:
                self.start_saving_video(frame)
            elif self.video_saving_status == self.VideoSavingStatus.STARTED:
                self.video_writer.write(frame)
            elif self.video_saving_status == self.VideoSavingStatus.STOPPING:
                self.stop_saving_video()

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
