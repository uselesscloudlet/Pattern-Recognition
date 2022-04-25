from enum import Enum, auto
import cv2 as cv
import numpy as np
import collections
from PyQt6.QtCore import (QThread, QObject, pyqtSignal)
import time

from nn_utils import (build_model, format_yolov5, detect,
                      wrap_detection, load_classes)


class CaptureSignals(QObject):
    captured_frame = pyqtSignal(np.ndarray)
    current_fps = pyqtSignal(int)
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
        NEURAL = auto()

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
        self.model_path = ''
        self.classes_path = ''

    def run(self):
        cap = cv.VideoCapture(self.__camera_id)
        tracker = cv.TrackerMIL_create()
        segmentor = cv.createBackgroundSubtractorMOG2(200, 16, True)

        colors = [(255, 255, 0), (0, 255, 0), (0, 255, 255), (255, 0, 0)]
        new_frame_time = 0
        prev_frame_time = 0

        while self.__video_capture:
            new_frame_time = time.time()
            _, frame = cap.read()
            frame = cv.cvtColor(frame, cv.COLOR_BGR2RGB)
            if frame is None:
                break

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

                if self.mode_state == self.ModeState.DEFAULT:
                    hsv = cv.cvtColor(frame, cv.COLOR_RGB2HSV)
                    blurred_frame = cv.medianBlur(hsv, ksize=7)
                    mask = cv.inRange(
                        blurred_frame, (h_min, s_min, v_min), (h_max, s_max, v_max))
                    frame = cv.hconcat(
                        [frame, cv.cvtColor(mask, cv.COLOR_GRAY2RGB)])
                elif self.mode_state == self.ModeState.INIT:
                    self.mode_state = self.ModeState.STREAM
                elif self.mode_state == self.ModeState.STREAM:
                    hsv = cv.cvtColor(frame, cv.COLOR_RGB2HSV)
                    blurred_frame = cv.medianBlur(hsv, ksize=7)
                    mask = cv.inRange(
                        blurred_frame, (h_min, s_min, v_min), (h_max, s_max, v_max))
                    mask = segmentor.apply(mask)
                    frame = cv.hconcat(
                        [frame, cv.cvtColor(mask, cv.COLOR_GRAY2RGB)])
                    contours, _ = cv.findContours(
                        mask, cv.RETR_TREE, cv.CHAIN_APPROX_SIMPLE)
                    sorted_contours = sorted(
                        contours, key=cv.contourArea, reverse=True)
                    has_motion = len(sorted_contours) > 0
                    if has_motion:
                        rect = cv.boundingRect(sorted_contours[0])
                        cv.rectangle(frame, rect, (255, 0, 0), 1)
            elif self.current_mode == self.DetectionMode.CONTRAST:
                brightness_min = self.slider_info['Brightness min']
                brightness_max = self.slider_info['Brightness min']

                if self.mode_state == self.ModeState.DEFAULT:
                    gray = cv.cvtColor(frame, cv.COLOR_RGB2GRAY)
                    _, thresh = cv.threshold(
                        gray, brightness_min, brightness_max, cv.THRESH_BINARY)
                    contours, _ = cv.findContours(
                        thresh, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
                    has_contours = len(contours) > 0
                    if has_contours:
                        for c in contours:
                            rect = cv.boundingRect(c)
                            frame = cv.rectangle(frame, rect, (255, 0, 0), 1)
            elif self.current_mode == self.DetectionMode.NEURAL:
                if self.mode_state == self.ModeState.INIT:
                    if self.model_path != '' and self.classes_path != '':
                        net = build_model(self.model_path, is_cuda=True)
                        class_list = load_classes(self.classes_path)
                        self.mode_state = self.ModeState.STREAM
                elif self.mode_state == self.mode_state.STREAM:
                    input_img = format_yolov5(frame)
                    outs = detect(input_img, net)
                    class_ids, confidences, boxes = wrap_detection(
                        input_img, outs[0])
                    for (classid, confidence, box) in zip(class_ids, confidences, boxes):
                        color = colors[int(classid) % len(colors)]
                        cv.rectangle(frame, box, color, 2)
                        cv.rectangle(
                            frame, (box[0], box[1] - 20), (box[0] + box[2], box[1]), color, -1)
                        cv.putText(
                            frame, class_list[classid], (box[0], box[1] - 10), cv.FONT_HERSHEY_SIMPLEX, .5, (0, 0, 0))

            fps = int(1 / (new_frame_time - prev_frame_time))

            prev_frame_time = new_frame_time

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
