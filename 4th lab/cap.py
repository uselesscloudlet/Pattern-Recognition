from enum import Enum, auto
from tracemalloc import start
import cv2 as cv
from cv2 import VideoCapture
from cv2 import cvtColor
import numpy as np
import collections


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

    class ModeState(Enum):
        DEFAULT = auto()
        INIT = auto()
        STREAM = auto()

    def __init__(self, camera_id: int):
        super(CaptureThread, self).__init__()
        self.__camera_id = camera_id

        self.__video_capture = True
        self.current_mode = self.DetectionMode.DEFAULT
        self.mode_state = self.ModeState.DEFAULT
        self.bbox = None
        self.trajectory_buffer = collections.deque(maxlen=100)
        self.slider_info = dict()
        self.signals = CaptureSignals()

    def run(self):
        cap = cv.VideoCapture(self.__camera_id)
        tracker = cv.TrackerMIL_create()
        segmentor = cv.createBackgroundSubtractorMOG2(200, 16, True)

        while self.__video_capture:
            _, frame = cap.read()
            frame = cv.cvtColor(frame, cv.COLOR_BGR2RGB)
            if frame is None:
                break
            print(self.current_mode, self.mode_state)
            fps = cap.get(cv.CAP_PROP_FPS)
            mean, std = cv.meanStdDev(frame)
            min_v = np.min(frame)
            max_v = np.max(frame)
            min_max_pi = np.array([min_v, max_v])

            if self.bbox is not None:
                if self.current_mode == self.DetectionMode.DRAW:
                    self.trajectory_buffer = collections.deque(maxlen=100)
                    start_point = self.bbox[0]
                    end_point = self.bbox[1]
                    if start_point is not None and end_point is not None:
                        frame = cv.rectangle(
                            frame, start_point, end_point, (255, 0, 0), 1)
                if self.current_mode == self.DetectionMode.MANUAL:
                    start_point = self.bbox[0]
                    end_point = self.bbox[1]
                    if start_point is not None and end_point is not None:
                        if self.mode_state == self.ModeState.INIT:
                            bbox_width = end_point[0] - start_point[0]
                            bbox_height = end_point[1] - start_point[1]
                            bbox = [*start_point, bbox_width, bbox_height]
                            tracker.init(frame, bbox)
                            self.mode_state = self.ModeState.STREAM
                        elif self.mode_state == self.ModeState.STREAM:
                            ok, bbox = tracker.update(frame)
                            if ok:
                                p1 = (int(bbox[0]), int(bbox[1]))
                                p2 = (int(bbox[0] + bbox[2]),
                                      int(bbox[1] + bbox[3]))
                                x_c = int(bbox[0] + bbox[2] / 2)
                                y_c = int(bbox[1] + bbox[3] / 2)
                                self.trajectory_buffer.append((x_c, y_c))
                                cv.circle(frame, (x_c, y_c),
                                          5, (0, 255, 255), -1)
                                for idx, point in enumerate(reversed(self.trajectory_buffer)):
                                    if len(self.trajectory_buffer) > 1 and idx > 0:
                                        next_point = self.trajectory_buffer[len(
                                            self.trajectory_buffer) - idx]
                                        cv.line(frame, point,
                                                next_point, (0, 255, 255), 2)
                                cv.rectangle(frame, p1, p2, (255, 0, 0), 1)
                            else:
                                self.current_mode = self.DetectionMode.DEFAULT
                                self.mode_state = self.ModeState.DEFAULT
            if self.current_mode == self.DetectionMode.MOTION:
                h_min = self.slider_info['H min']
                h_max = self.slider_info['H max']
                s_min = self.slider_info['S min']
                s_max = self.slider_info['S max']
                v_min = self.slider_info['V min']
                v_max = self.slider_info['V max']
                min_size = self.slider_info['Min Size']
                max_size = self.slider_info['Max Size']

                if self.mode_state == self.ModeState.DEFAULT:
                    hsv = cv.cvtColor(frame, cv.COLOR_RGB2HSV)
                    blurred_frame = cv.medianBlur(hsv, ksize=7)
                    mask = cv.inRange(blurred_frame, (h_min, s_min, v_min), (h_max, s_max, v_max))
                    frame = cv.hconcat([frame, cv.cvtColor(mask, cv.COLOR_GRAY2RGB)])
                elif self.mode_state == self.ModeState.INIT:
                    contours, _ = cv.findContours(
                        mask, cv.RETR_TREE, cv.CHAIN_APPROX_SIMPLE)
                    
                    sorted_contours = sorted(contours, key=cv.contourArea, reverse=True)
                    for c in sorted_contours:
                        rect = cv.boundingRect(c)
                        if(rect[2] >= min_size and rect[2] <= max_size
                            and rect[3] >= min_size and rect[3] <= max_size):
                            self.bbox = rect
                            tracker.init(frame, rect)
                            self.mode_state = self.ModeState.STREAM
                            break
                elif self.mode_state == self.ModeState.STREAM:
                    ok, bbox = tracker.update(frame)
                    if ok:
                        p1 = (int(bbox[0]), int(bbox[1]))
                        p2 = (int(bbox[0] + bbox[2]),
                                int(bbox[1] + bbox[3]))
                        x_c = int(bbox[0] + bbox[2] / 2)
                        y_c = int(bbox[1] + bbox[3] / 2)
                        self.trajectory_buffer.append((x_c, y_c))
                        cv.circle(frame, (x_c, y_c),
                                    5, (0, 255, 255), -1)
                        for idx, point in enumerate(reversed(self.trajectory_buffer)):
                            if len(self.trajectory_buffer) > 1 and idx > 0:
                                next_point = self.trajectory_buffer[len(
                                    self.trajectory_buffer) - idx]
                                cv.line(frame, point,
                                        next_point, (0, 255, 255), 2)
                        cv.rectangle(frame, p1, p2, (255, 0, 0), 1)
                    else:
                        self.current_mode = self.DetectionMode.DEFAULT
                        self.mode_state = self.ModeState.DEFAULT
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
