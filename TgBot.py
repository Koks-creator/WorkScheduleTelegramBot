from typing import List
from time import time
from dataclasses import dataclass, field
import threading
import telebot
from telebot import types
from telebot.types import Message, CallbackQuery

from MocneBoty.BotLogger import bot_logger
from MocneBoty.WorkScheduleWebcam import WorkScheduleWebcam


@dataclass(frozen=True)
class ThreadData:
    name: str
    running: bool
    work_time: int
    break_time: int
    repeat: int


@dataclass
class ThreadsHandler:
    _threads_status: List[ThreadData] = field(default_factory=lambda: [])

    @property
    def threads_status(self) -> List[ThreadData]:
        return self._threads_status

    def create_thread(self, thread_id: int, func, work_time: int, break_time: int, chat_id: int, task_name: str,
                      repeat: int = 1):
        thread = threading.Thread(target=func, args=(thread_id, work_time, break_time, repeat, chat_id))
        self._threads_status.append(ThreadData(name=f"{task_name}-{thread_id}",
                                               running=False,
                                               work_time=work_time,
                                               break_time=break_time,
                                               repeat=repeat))
        thread.start()
        bot_logger.info(f"[Create thread - {chat_id}] thread: {thread_id} started")

    def stop_thread(self, thread_id: int) -> bool:
        try:
            self._threads_status.pop(thread_id)
            return True
        except IndexError:
            return False

    def list_threads(self) -> str:
        list_threads_str = "Running threads: \n"
        for ind, thread in enumerate(self._threads_status):
            list_threads_str += f"  [{ind}] - {thread}\n"

        return list_threads_str


@dataclass
class TelegramBot(ThreadsHandler):
    bot_token: str = ""

    def __post_init__(self) -> None:
        self.bot = telebot.TeleBot(self.bot_token)

    def regular_schedule(self, thread_id: int, work_time: int, break_time: int, repeat: int, chat_id: int):
        """
        :param thread_id:
        :param work_time: minutes
        :param break_time: minutes
        :param repeat:
        :param chat_id:
        :return:
        """
        call_params = f"{thread_id=}, {work_time=}, {break_time=}, {repeat=}"
        bot_logger.info(f"[Regular Scheduler - {chat_id}] start: {call_params}")
        stopped = False
        repeat_count = 0

        self.bot.send_message(chat_id, f"Let's start work")
        while repeat_count < repeat or not repeat:
            work_start_time = time()

            # yeah 2 whiles - i think it's more readable than 1 big while, performance difference should not be visible,
            # cmon nothing fancy happening here lol

            while (time() - work_start_time) < work_time:
                try:
                    self._threads_status[thread_id].running
                except IndexError:
                    stopped = True
                    break
            if not stopped:
                self.bot.send_message(chat_id, f"{repeat_count+1}/{repeat} work finished, time for a break!")
                bot_logger.info(f"[Regular Scheduler - {chat_id}] work time finished {repeat_count+1}/{repeat}: {call_params}")

            break_start_time = time()
            while (time() - break_start_time) < break_time:
                try:
                    self._threads_status[thread_id].running
                except IndexError:
                    stopped = True
                    break
            if not stopped and (repeat_count < repeat-1 or not repeat):
                print(repeat_count, repeat)
                self.bot.send_message(chat_id, f"{repeat_count+1}/{repeat} break finished, it's time to get back to work :/")
                bot_logger.info(f"[Regular Scheduler - {chat_id}] break time finished {repeat_count+1}/{repeat}: {call_params}")
            repeat_count += 1

        self.stop_thread(thread_id=thread_id)
        self.bot.send_message(chat_id, f"Thread {thread_id} (regular schedule) has been finished")
        bot_logger.info(f"[Regular Scheduler - {chat_id}] stop: {call_params}")

    def webcam_bullshit(self, thread_id: int, work_time: int, break_time: int, repeat, chat_id):
        call_params = f"{thread_id=}, {work_time=}, {break_time=}, {repeat=}"
        bot_logger.info(f"[Webcam Scheduler - {chat_id}] start: {call_params}")
        wsw = WorkScheduleWebcam(
            max_faces=1,
            device_id=0,
            work_time=work_time,
            break_time=break_time,
            repeat=repeat
        )
        wsw.run(bot=self.bot, chat_id=chat_id)
        self.stop_thread(thread_id=thread_id)
        self.bot.send_message(chat_id, f"Thread {thread_id} (webcam schedule) has been finished")
        bot_logger.info(f"[Webcam Scheduler - {chat_id}] stopped: {call_params}")

    def setup_handlers(self) -> None:
        @self.bot.message_handler(commands=["start"])
        def start_command(message: Message):
            markup = types.InlineKeyboardMarkup(row_width=2)

            webcam_sched = types.InlineKeyboardButton("Webcam", callback_data="webcam")
            regular_sched = types.InlineKeyboardButton("Regular", callback_data="regular")
            thread_options = types.InlineKeyboardButton("Threads", callback_data="threads")
            all_commands = types.InlineKeyboardButton("All commands", callback_data="all_commands")

            markup.add(webcam_sched, regular_sched, thread_options, all_commands)

            self.bot.send_message(message.chat.id,
                                  "<strong>Turbo menu</strong>",
                                  reply_markup=markup,
                                  parse_mode="html")

        @self.bot.message_handler(commands=["webcam"])
        def webcam_sched_command(message: Message):
            command_text = message.text
            command, *command_params = command_text.split()

            bot_logger.info(f"[webcam_sched_command - {message.chat.id}] params raw: {command_params}")
            for ind, param in enumerate(command_params):
                if not param.isdigit():
                    self.bot.send_message(message.chat.id, f"All values should be numeric")
                    command_params = []
                    break
                else:
                    command_params[ind] = int(param)

            if command_params:
                params = [1, 1, 1]
                if 1 < len(command_params) < 4:
                    for ind, param in enumerate(command_params):
                        params[ind] = param

                    work_time, break_time, repeat = params
                    try:
                        self.bot.send_message(message.chat.id, f"Started")
                        self.create_thread(len(self._threads_status), self.webcam_bullshit, work_time=work_time,
                                           break_time=break_time, repeat=repeat, chat_id=message.chat.id, task_name="Webcam")
                    except Exception as e:
                        self.bot.send_message(message.chat.id, f"Something went wrong: {e}")
                        bot_logger.error(f"[webcam_sched_command - {message.chat.id}] params: {params},"
                                              f" error: {e}")
                else:
                    self.bot.send_message(message.chat.id, f"This command takes 2-3 arguments")

        @self.bot.message_handler(commands=["regular"])
        def regular_sched_command(message: Message):
            command_text = message.text
            command, *command_params = command_text.split()
            bot_logger.info(f"[regular_sched_command - {message.chat.id}] params raw: {command_params}")

            for ind, param in enumerate(command_params):
                if not param.isdigit():
                    self.bot.send_message(message.chat.id, f"All values should be numeric")
                    command_params = []
                    break
                else:
                    command_params[ind] = int(param)

            if command_params:
                params = [1, 1, 1]
                if 1 < len(command_params) < 4:
                    for ind, param in enumerate(command_params):
                        params[ind] = param

                    work_time, break_time, repeat = params
                    thread_names = [thread.name for thread in self._threads_status]

                    try:
                        if "Regular-0" not in thread_names:
                            self.bot.send_message(message.chat.id, f"Started")
                            self.create_thread(len(self._threads_status), self.regular_schedule, work_time=work_time,
                                               break_time=break_time, repeat=repeat,
                                               chat_id=message.chat.id, task_name="Regular")
                        else:
                            self.bot.send_message(message.chat.id, f"You can only run 1 regular work schedule at once. "
                                                                   f"Stop current thread in order to make a new one.")
                    except Exception as e:
                        bot_logger.error(f"[regular_sched_command - {message.chat.id}] params: {params}, error: {e}")
                        self.bot.send_message(message.chat.id, f"Something went wrong: {e}")
                else:
                    self.bot.send_message(message.chat.id, f"This command takes 2-3 arguments")

        @self.bot.message_handler(commands=["stopThread"])
        def stop_thread_command(message: Message):
            command_text = message.text
            splitted = command_text.split()

            bot_logger.info(f"[stopThread command - {message.chat.id}] params: {splitted}")

            if len(splitted) == 2:
                thread_id = splitted[1]
                if thread_id.isdigit():
                    thread_id = int(thread_id)
                    success = self.stop_thread(thread_id=thread_id)
                    if success:
                        self.bot.send_message(message.chat.id, f"Thread: {thread_id} has been stopped")
                        bot_logger.info(f"[stopThread command - {message.chat.id}] Thread: {thread_id} has been stopped")
                    else:
                        self.bot.send_message(message.chat.id, f"Thread: {thread_id} was not stopped successfully")
                        bot_logger.error(f"[stopThread command - {message.chat.id}] Thread: {thread_id} was not stopped successfully")
                else:
                    self.bot.send_message(message.chat.id, f"Thread id must be a digit")
            else:
                self.bot.send_message(message.chat.id, f"This command takes 1 argument")

        @self.bot.message_handler(commands=["listThreads"])
        def list_threads_command(message: Message):
            list_threads_str = self.list_threads()
            self.bot.send_message(message.chat.id, list_threads_str)

        @self.bot.callback_query_handler(func=lambda call: True)
        def answer(callback: CallbackQuery):
            if callback.message:
                if callback.data == "webcam":
                    self.bot.send_message(callback.message.chat.id, "run /webcam <workTimeSecs> <breakTimeSecs> <Repeat>")

                if callback.data == "regular":
                    self.bot.send_message(callback.message.chat.id, "run /regular <workTimeSecs> <breakTimeSecs> <Repeat>")

                if callback.data == "threads":
                    markup = types.InlineKeyboardMarkup(row_width=2)
                    next_button1 = types.InlineKeyboardButton("List threads", callback_data="list_threads")
                    next_button2 = types.InlineKeyboardButton("Kill thread", callback_data="kill_thread")
                    markup.add(next_button1, next_button2)
                    self.bot.edit_message_text(chat_id=callback.message.chat.id, message_id=callback.message.message_id,
                                               text="<strong>Threads menu</strong>", reply_markup=markup, parse_mode="html")

                if callback.data == "list_threads":
                    list_threads_str = self.list_threads()
                    self.bot.send_message(callback.message.chat.id, list_threads_str)
                    self.bot.send_message(callback.message.chat.id, "run /listThreads")

                if callback.data == "kill_thread":
                    self.bot.send_message(callback.message.chat.id, "run /stopThread <thrId>")

                if callback.data == "all_commands":
                    all_commands_str = "Commands: \n" \
                                       "  ~ /webcam <workTimeSecs:int> <breakTimeSecs:int> <Repeat:int>\n"\
                                       "  ~ /regular <workTimeSecsint> <breakTimeSecs:int> <Repeat:int>\n"\
                                       "  ~ /listThreads\n"\
                                       "  ~ /stopThread <thrId:int>\n"
                    self.bot.send_message(callback.message.chat.id, all_commands_str)

    def start(self) -> None:
        bot_logger.info("Starting")
        self.setup_handlers()
        bot_logger.info("Handlers ready, should be all green :P")
        self.bot.polling()


if __name__ == '__main__':
    # use env var if you want, I didn't rly care
    bot = TelegramBot(bot_token="")
    bot.start()

