from multiplayer_manager import MultiplayerManager


class PlayerConnection:
    def __init__(self, player_id: str, mp_manager: MultiplayerManager):
        self.status = 'hello'
        self.player_id = player_id
        self.mpm = mp_manager

    async def parse_request(self, data: dict):
        req_type = data.get('type')
        waiter_id = data.get('waiter_id')
        solicitor_id = data.get('solicitor_id')
        opponent_id = data.get('opponent')
        game_data = data.get('game_data')
        if req_type == 'game_data':
            await self.mpm.send_game_data(game_data, opponent_id)
        elif req_type == 'add_to_waiting':
            self.status = 'waiting'
            await self.mpm.add_to_waiting_list(player_id=self.player_id)
        elif req_type == 'quit_waiting':
            self.status = 'hello'
            await self.mpm.remove_from_waiting_list(player_id=self.player_id)
        elif req_type == 'solicit':
            if waiter_id is not None:
                self.status = 'soliciting'
                await self.mpm.solicit(solicitor_id=self.player_id, waiter_id=waiter_id)
        elif req_type == 'get_solicitors':
            solicitors = await self.mpm.get_solicitors(waiter_id=self.player_id)
            return solicitors
        elif req_type == 'accept':
            self.status = 'match_accepted'
            await self.mpm.accept_match(solicitor_id=solicitor_id, waiter_id=self.player_id)

