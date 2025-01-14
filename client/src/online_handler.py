import websocket
import time
import threading
import json
from .game_instance import GameInstance
from .components.mino import Mino
from .launcher.online_lobby import OnlineLobby
from .launcher.gui_com import GuiCom
from .consts.urls import URLS

# receiving codes
RCODES = {
    'game_data': 'gd',
    'game_over': 'go',
    'match_set': 'ms',
    'match_complete': 'mc',
    'game_start': 'gs',
    'waiter_list': 'wl',
    'host_accepted': 'ha',
    'host_rejected': 'hr',
    'approacher_list': 'al',
    'lose': 'lo',
    'win': 'wi'
}

# sending codes
SCODES = {
    'game_data': 'gd',
    'game_over': 'go',
    'waiting_list_add': 'wa',
    'waiting_list_remove': 'wr',
    'waiting_list_get': 'wg',
    'approach': 'a',
    'approach_cancel': 'ac',
    'host_accept': 'ha',
    'host_reject': 'hr',
}


def on_error(ws, error):
    print(error)


def on_close(ws, close_status_code, close_msg):
    print("### closed ###")


class OnlineHandler:
    def __init__(self, user_id: str,
                 game_instance: GameInstance,
                 opponent_instance: GameInstance,
                 online_lobby: OnlineLobby,
                 online_data: GuiCom,
                 jwt: str):

        websocket.enableTrace(True)
        self.status = 'hello'
        self.user_id = user_id
        self.jwt = jwt
        self.game_instance = game_instance
        self.opponent_instance = opponent_instance
        self.opponent = None
        self.online_lobby_gui = online_lobby
        self.current_waiter_list = []
        self.current_approacher_list = []
        self.ws: websocket.WebSocketApp = websocket.WebSocketApp(
            URLS.mp_server_url,
            on_open=lambda ws: self.on_open(ws),
            on_message=lambda ws, msg: self.on_message(ws, msg),
            on_error=on_error,
            on_close=lambda ws, close_status_code, close_msg: self.on_close(ws, close_status_code, close_msg),
        )
        self.online_data = online_data
        self.ws_thread = threading.Thread(target=self.ws_connect, daemon=True)  # 웹 소켓 연결 스레드
        self.s_game_data_thread = threading.Thread(target=self.s_game_data_loop, daemon=True)  # 게임 데이터 전송 스레드
        self.gui_emit_thread = threading.Thread(target=self.on_emit, daemon=True)  # online_lobby gui 입력 받아옴.

    def on_emit(self):
        while True:
            data = self.online_data.handler_queue.get()
            self.parse_emit(data)

    def parse_emit(self, msg: dict):
        todo = msg['t']
        data = msg['d']

        if todo == SCODES['host_accept']:
            self.s_host_accept(data)
        elif todo == SCODES['host_reject']:
            self.s_host_reject(data)
        elif todo == SCODES['approach']:
            if self.status != 'approaching':
                self.s_approach(data)
                self.status = 'approaching'
        elif todo == SCODES['approach_cancel']:
            self.s_approach_cancel()
            self.status = 'hello'
        elif todo == SCODES['waiting_list_add']:
            self.s_waiting_list_add()
            self.status = 'waiting'
        elif todo == SCODES['waiting_list_remove']:
            self.s_waiting_list_remove()
            self.status = 'hello'
        elif todo == SCODES['waiting_list_get']:
            self.s_waiting_list_get()

    def on_open(self, ws: websocket.WebSocketApp):  # 연결될때 실행됨.
        self.jwt_auth()

    def jwt_auth(self):
        req = {
            'id': self.user_id,
            'jwt': self.jwt
        }
        self.send_json_req(req)

    def on_message(self, ws, message):
        try:
            raw_data = json.loads(message)  # 최상위 키가 둘 존재하는 딕셔너리 데이터
            print(raw_data)  # 디버그
        except json.JSONDecodeError:
            raw_data = None
            print('message not in json format')

        if raw_data is not None and raw_data != []:
            self.r_parse_data(raw_data)

    def on_close(self, ws, close_status_code, close_msg):
        print("### closed ###")
        print(f'{close_status_code}')
        print(f'{close_msg}')
        sig = self.build_dict(t='server_connection_lost')
        self.online_lobby_gui.signal.emit(sig)  # 서버 연결 끊어짐 알림

    # 웹소켓 연결
    def ws_connect(self):
        self.ws.run_forever()

    # 게임 인스턴스들 초기화
    def reset_instances(self):
        self.opponent_instance.reset()
        self.game_instance.reset()

    def game_start(self):
        self.status = 'in_game'
        self.reset_instances()

        self.online_lobby_gui.signal.emit(self.build_dict('game_start'))

        self.game_instance.status = 'mp_game_ready'
        time.sleep(3)
        self.s_game_data_thread_restart()
        self.game_instance.ev_game_start()

    # 이하 수신
    # 데이터 parse
    def r_parse_data(self, raw_data):
        try:
            t = raw_data['t']
            d = raw_data['d']
        except KeyError:
            t = None
            d = None
            print(f'Cannot parse data:\n{raw_data=}')

        print(self.status)

        if t == RCODES['game_data']:
            self.r_update_opponent_info(d)
        elif t == RCODES['game_over']:
            self.r_on_op_game_over()
        elif t == RCODES['game_start']:
            self.game_start()
        elif t == RCODES['match_complete'] or t == RCODES['win'] or t == RCODES['lose']:
            self.r_on_match_complete(t)
        elif t == RCODES['host_rejected']:
            self.r_host_rejected()
        elif t == RCODES['approacher_list']:
            self.r_update_current_approacher(d)
        elif t == RCODES['waiter_list']:
            self.r_update_current_waiter_list(d)

    def r_update_opponent_info(self, d: dict):
        if d:
            score = d.get('score')
            level = d.get('level')
            goal = d.get('goal')
            matrix = d.get('matrix')
            next_mino_index = d.get('next_mino_index')
            hold_mino_index = d.get('hold_mino_index')

            self.opponent_instance.score = score
            self.opponent_instance.level = level
            self.opponent_instance.goal = goal
            self.opponent_instance.board.temp_matrix = matrix

            self.opponent_instance.next_mino = Mino(next_mino_index)
            if hold_mino_index != -1:
                self.opponent_instance.hold_mino = Mino(hold_mino_index)

    def r_on_lose(self):
        self.game_instance.status = 'mp_lose'

    def r_on_win(self):
        self.game_instance.status = 'mp_win'

    def r_on_nothing(self):
        self.game_instance.status = 'mp_hello'

    def r_on_op_game_over(self):
        self.opponent_instance.status = 'game_over'

    def r_on_match_complete(self, t):
        if t == RCODES['win']:
            self.r_on_win()
        elif t == RCODES['lose']:
            self.r_on_lose()
        elif t == RCODES['match_complete']:
            self.r_on_nothing()  # 승부 없이 끝났을 때

        self.status = 'hello'  # todo 상태 상수화
        self.online_lobby_gui.signal.emit('init')  # 게임 끝나면 gui 초기화

    def r_update_current_approacher(self, d):
        self.current_approacher_list = d
        self.online_lobby_gui.approacher_list = d  # approacher_list 데이터 수정
        self.online_lobby_gui.approacher_update()  # gui refresh

    def r_update_current_waiter_list(self, d):
        self.current_waiter_list = d
        self.online_lobby_gui.waiter_list = d  # waiter_list 데이터 수정
        self.online_lobby_gui.waiter_update()  # gui refresh

    def r_host_rejected(self):
        self.status = 'hello'
        self.online_lobby_gui.signal.emit(self.build_dict('approach_rejected'))  # todo signal 상수화

    # 이하 전송
    def send_json_req(self, req):
        try:
            self.ws.send(json.dumps(req))
        except websocket.WebSocketConnectionClosedException:
            sig = self.build_dict(t='server_connection_lost')
            self.online_lobby_gui.signal.emit(sig)


    @staticmethod
    def build_dict(t: str, d=None):
        to_return = {
            't': t,
            'd': d
        }
        return to_return

    def build_and_send_json_req(self, t: str, d=None):
        req = self.build_dict(t, d)
        self.send_json_req(req=req)

    def s_waiting_list_add(self):
        self.build_and_send_json_req(SCODES['waiting_list_add'])

    def s_waiting_list_remove(self):
        self.build_and_send_json_req(SCODES['waiting_list_remove'])

    def s_waiting_list_get(self):
        self.build_and_send_json_req(SCODES['waiting_list_get'])

    def s_approach(self, waiter_id: str):
        self.build_and_send_json_req(SCODES['approach'], waiter_id)

    def s_approach_cancel(self):
        self.build_and_send_json_req(SCODES['approach_cancel'])

    def s_host_accept(self, approacher_id: str):
        self.build_and_send_json_req(SCODES['host_accept'], approacher_id)
        # self.game_start()

    def s_host_reject(self, approacher_id: str):
        self.build_and_send_json_req(SCODES['host_reject'], approacher_id)

    def s_game_data(self):
        d = {
            'id': self.user_id,
            'score': self.game_instance.score,
            'level': self.game_instance.level,
            'goal': self.game_instance.goal,
            'matrix': self.game_instance.board.temp_matrix,
            'next_mino_index': self.game_instance.next_mino.shape_index,
            'hold_mino_index': self.get_hold_mino_index(),
        }
        self.build_and_send_json_req(SCODES['game_data'], d)

    def get_hold_mino_index(self) -> int:
        if self.game_instance.hold_mino is not None:
            return self.game_instance.hold_mino.shape_index
        else:
            return -1

    def s_game_data_loop(self):  # 스레드로 사용할것
        while True:
            if self.game_instance.status == 'in_game':
                self.s_game_data()  # 비동기 처리가 필요할수도
                time.sleep(0.1)  # 0.1초마다
            if self.game_instance.status == 'game_over':  # 게임 오버시 종료
                self.build_and_send_json_req(t=SCODES['game_over'], d=None)
                self.online_lobby_gui.signal.emit(self.build_dict('init'))
                break

    def s_game_data_thread_init(self):  # 게임 데이터 전송 스레드 초기화
        self.s_game_data_thread = threading.Thread(target=self.s_game_data_loop, daemon=True)

    def s_game_data_thread_restart(self):  # 게임 데이터 전송 스레드 재시작
        self.s_game_data_thread_init()
        self.s_game_data_thread.start()

