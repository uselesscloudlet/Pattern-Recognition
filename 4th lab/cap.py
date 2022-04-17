from enum import Enum, auto
from tracemalloc import start
import cv2 as cv
from cv2 import VideoCapture
import numpy as np

from PyQt6.QtCore import (QThread, QMutex, QElapsedTimer, QObject, pyqtSignal)


class CaptureSignals(QObject):
    captured_frame = pyqtSignal(np.ndarray)
    current_fps = pyqtSignal(float)
    mean_pi = pyqtSignal(np.ndarray)
    pi_std = pyqtSignal(np.ndarray)
    min_max_pi = pyqtSignal(np.ndarray)
    update_data = pyqtSignal()


class CaptureThread(QThread):
    class DetectionMode(Enum):
        DEFAULT = auto()
        DRAW = auto()
        MANUAL = auto()
        MOTION = auto()
        CONTRAST = auto()

    class ManualModeState(Enum):
        DEFAULT = auto()
        INIT = auto()
        STREAM = auto()
    

    def __init__(self, camera_id: int):
        super(CaptureThread, self).__init__()
        self.__camera_id = camera_id

        self.__video_capture = True
        self.current_mode = self.DetectionMode.DEFAULT
        self.manual_state = self.ManualModeState.DEFAULT
        self.bbox = None
        self.signals = CaptureSignals()
        self.__init_params()
    
    def __init_params(self):
        self.size_min = 0
        self.size_max = 1000
        self.h_min = 0
        self.h_max = 255
        self.s_min = 0
        self.s_max = 255
        self.v_min = 0
        self.v_max = 255

    def run(self):
        cap = cv.VideoCapture(self.__camera_id)
        tracker = cv.TrackerMIL_create()
        segmentor = cv.createBackgroundSubtractorMOG2()

        while self.__video_capture:
            _, frame = cap.read()
            frame = cv.cvtColor(frame, cv.COLOR_BGR2RGB)
            if frame is None:
                break

            fps = cap.get(cv.CAP_PROP_FPS)
            mean, std = cv.meanStdDev(frame)
            min_v = np.min(frame)
            max_v = np.max(frame)
            min_max_pi = np.array([min_v, max_v])

            if self.bbox is not None:
                if self.current_mode == self.DetectionMode.DRAW:
                    start_point = self.bbox[0]
                    end_point = self.bbox[1]
                    if start_point is not None and end_point is not None:
                        frame = cv.rectangle(
                            frame, start_point, end_point, (255, 0, 0), 1)
                if self.current_mode == self.DetectionMode.MANUAL:
                    start_point = self.bbox[0]
                    end_point = self.bbox[1]
                    if start_point is not None and end_point is not None:
                        if self.manual_state == self.ManualModeState.INIT:
                            bbox_width = end_point[0] - start_point[0]
                            bbox_height = end_point[1] - start_point[1]
                            bbox = [*start_point, bbox_width, bbox_height]
                            tracker.init(frame, bbox)
                            self.manual_state = self.ManualModeState.STREAM
                        elif self.manual_state == self.ManualModeState.STREAM:
                            ok, bbox = tracker.update(frame)
                            if ok:
                                p1 = (int(bbox[0]), int(bbox[1]))
                                p2 = (int(bbox[0] + bbox[2]),
                                      int(bbox[1] + bbox[3]))
                                cv.rectangle(frame, p1, p2, (255, 0, 0), 1)
                            else:
                                self.current_mode = self.DetectionMode.DEFAULT
                                self.manual_state = self.ManualModeState.DEFAULT
            if self.current_mode == self.DetectionMode.MOTION:
                pass
            elif self.current_mode == self.DetectionMode.CONTRAST:
                pass


            self.signals.captured_frame.emit(frame)
            self.signals.current_fps.emit(fps)
            self.signals.mean_pi.emit(mean)
            self.signals.pi_std.emit(std)
            self.signals.min_max_pi.emit(min_max_pi)
            self.signals.update_data.emit()

        cap.release()
        cv.destroyAllWindows()

    @property
    def video_capture(self):
        return self.__video_capture

    @video_capture.setter
    def video_capture(self, flag):
        self.__video_capture = flag
