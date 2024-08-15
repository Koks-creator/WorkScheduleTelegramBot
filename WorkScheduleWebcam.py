from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple, Union
from time import time
import numpy as np
import cv2
import mediapipe as mp
import telebot

from MocneBoty.BotLogger import bot_logger


class States(Enum):
    WORK: str = "work"
    BREAK: str = "break"


@dataclass
class FaceDetector:
    max_faces: int
    _left_point: int = field(init=False, default=234)
    _right_point: int = field(init=False, default=454)
    _top_point: int = field(init=False, default=10)
    _bottom_point: int = field(init=False, default=152)

    def __post_init__(self) -> None:
        self.mp_face = mp.solutions.face_mesh
        self.face = self.mp_face.FaceMesh(max_num_faces=self.max_faces)
        self.mp_drawing = mp.solutions.drawing_utils

    def get_lms(self, frame: np.array, draw_mesh: bool = False) -> List[List[Tuple[int, int]]]:
        faces = []
        h, w, _ = frame.shape

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame.flags.writeable = False
        results = self.face.process(frame).multi_face_landmarks
        frame.flags.writeable = True
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        if results:
            for landmark in results:
                if draw_mesh:
                    self.mp_drawing.draw_landmarks(frame, landmark, self.mp_face.FACEMESH_CONTOURS)

                face_data = []
                for ind, lm in enumerate(landmark.landmark):
                    x, y = int(lm.x * w), int(lm.y * h)
                    face_data.append((x, y))
                faces.append(face_data)

        return faces

    def draw_face_rect(self, frame: np.array,
                       face_lm_list: List[Tuple[int, int]],
                       color: Tuple[int, int, int] = (255, 0, 255)) -> None:

        x1, y1 = face_lm_list[self._left_point][0], face_lm_list[self._top_point][1]
        x2, y2 = face_lm_list[self._right_point][0], face_lm_list[self._bottom_point][1]
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)


@dataclass
class WorkScheduleWebcam(FaceDetector):
    device_id: int
    work_time: int
    break_time: int
    repeat: int

    def __post_init__(self) -> None:
        super().__post_init__()
        available_devices = [0, 1, 2]

        self.cap = cv2.VideoCapture(self.device_id)
        success = self.cap.isOpened()
        if not success:
            bot_logger.info(f"{self.device_id} didn't work, looking for first working one...")
            for dev in available_devices:
                if dev != self.device_id:
                    self.cap = cv2.VideoCapture(dev)
                    success = self.cap.isOpened()
                    if success:  # inform user that we're changing device id :P
                        bot_logger.info(f"Device found: {dev}")
                        break

    @staticmethod
    def change_format(seconds: int):
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        return f"{minutes:02}:{remaining_seconds:02}"

    def display_info(self, frame: np.array, state: str, current_time: int, repeat: int) -> None:
        if state == States.WORK:
            work_time = current_time
            break_time = 0
            work_time_color = (0, 200, 0)
            break_time_color = (0, 0, 200)
        else:
            work_time = 0
            break_time = current_time
            work_time_color = (0, 0, 200)
            break_time_color = (0, 200, 0)

        cv2.putText(frame, f"Work time: {self.change_format(work_time)}/{self.change_format(self.work_time)}",
                    (10, 30), cv2.FONT_HERSHEY_PLAIN, 1.5, work_time_color, 2)
        cv2.putText(frame, f"Break time: {self.change_format(break_time)}/{self.change_format(self.break_time)}",
                    (10, 60), cv2.FONT_HERSHEY_PLAIN, 1.5, break_time_color, 2)
        cv2.putText(frame, f"Repeat: {repeat}/{self.repeat}",
                    (10, 90), cv2.FONT_HERSHEY_PLAIN, 1.5, (255, 0, 255), 2)
        cv2.putText(frame, f"Press 'esc' to exit",
                    (10, 120), cv2.FONT_HERSHEY_PLAIN, 1.5, (255, 0, 255), 2)

    @staticmethod
    def send_mag(msg: str, bot: Union[bool, telebot.TeleBot] = False, chat_id: Union[bool, int] = False) -> None:
        if bot and chat_id:
            bot.send_message(chat_id, msg)

    def run(self, bot: Union[bool, telebot.TeleBot] = False, chat_id: Union[bool, int] = False) -> None:
        last_time = 0
        start_time = time()
        current_time = 0
        state = States.WORK
        repeat_count = 0

        self.send_mag(bot=bot, chat_id=chat_id, msg=f"Time for work")
        while self.cap.isOpened() and repeat_count < self.repeat or not self.repeat:
            success, frame = self.cap.read()
            if not success:
                print("Leaving...")
                break

            faces = self.get_lms(frame=frame)
            if faces or state == States.BREAK:
                current_time = int((time() - start_time) + last_time)
                for face in faces:
                    self.draw_face_rect(frame=frame, face_lm_list=face)
            else:
                if current_time:
                    last_time = current_time
                    current_time = 0
                start_time = time()

            if state == States.WORK:
                if current_time > self.work_time:
                    state = States.BREAK
                    last_time = 0
                    start_time = time()
                    current_time = 0

                    self.send_mag(bot=bot, chat_id=chat_id, msg=f"It's time for a break {repeat_count+1}/{self.repeat}!")
            else:
                if current_time > self.break_time:
                    state = States.WORK
                    last_time = 0
                    start_time = time()
                    current_time = 0
                    if self.repeat:
                        repeat_count += 1

                    if repeat_count < self.repeat or not self.repeat:
                        self.send_mag(bot=bot, chat_id=chat_id, msg=f"Time for work {repeat_count+1}/{self.repeat}")

            self.display_info(frame=frame,
                              current_time=current_time if current_time else last_time,
                              state=state,
                              repeat=repeat_count)
            cv2.imshow("res", frame)
            key = cv2.waitKey(1)
            if key == 27:
                break
        self.cap.release()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    wsw = WorkScheduleWebcam(
        max_faces=1,
        device_id=2,
        work_time=5,
        break_time=5,
        repeat=2
    )
    wsw.run()
