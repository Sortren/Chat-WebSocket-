'''TODO
Split project to multiple files
'''


from abc import ABC, abstractmethod
from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketDisconnect
from random import choice


app = FastAPI()


class ConnectionManager(ABC):
    def __init__(self):
        self.active_connections = []

    @abstractmethod
    async def connect(self, websocket: WebSocket):
        pass

    @abstractmethod
    def disconnect(self, websocket: WebSocket):
        pass

    @abstractmethod
    async def broadcast(self, message: str, room_id=None):
        pass


class PublicConnectionManager(ConnectionManager):
    '''
    Stands for connection to the PUBLIC chat room
    without limiting amount of connected clients
    '''

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


class PrivateConnectionManager(ConnectionManager):
    '''
    Stands for connection to the PRIVATE chat room
    with limiting amount of connected clients to 2 by each room
    '''

    def find_room_id(self, websocket: WebSocket) -> int:
        '''
        Returns the index of the room where the current client is connected to
        '''
        for index, room in enumerate(self.active_connections):
            if websocket in room:
                return index

    def free_room_id(self) -> int:
        '''
        Returns the index of the random room where only one client is located
        '''
        free_clients = list(
            filter(
                lambda client: len(client) == 1, self.active_connections
            )
        )
        # assign client of found room -> choice returns random room with one client inside to catch him [0] is required
        free_client = choice(free_clients)[0]
        return self.find_room_id(free_client)

    def full_rooms(self) -> bool:
        '''
        Check if all of the rooms are fullfilled by clients
        '''
        for room in self.active_connections:
            if len(room) < 2:
                return False
        return True

    async def connect(self, websocket: WebSocket):
        '''
        Connecting clients to the private rooms with size of 2
        Works like a queue, the next client in queue will be
        paired with client with an empty slot in a room
        '''

        await websocket.accept()

        if len(self.active_connections) == 0 or self.full_rooms():
            self.active_connections.append([websocket])
        else:
            self.active_connections[self.free_room_id()].append(websocket)

    def disconnect(self, websocket: WebSocket):
        for index, room in enumerate(self.active_connections):
            if websocket in room:
                self.active_connections[index].remove(websocket)
                if len(room) == 0:
                    self.active_connections.remove(room)

    async def broadcast(self, message: str, room_id: int):
        '''
        Broadcasting messages only for the specific room (where the client is located)
        '''
        for connection in self.active_connections[room_id]:
            # TODO
            # Broadcast throw anexception while trying to send a message when noone is in the room
            # HAVE TO FIX IT!
            await connection.send_text(message)


public_manager = PublicConnectionManager()
private_manager = PrivateConnectionManager()


@app.websocket("/chat/public")
async def public_room(websocket: WebSocket):
    await public_manager.connect(websocket)
    await public_manager.broadcast(f"Someone joined the chat!")

    try:
        while True:
            data = await websocket.receive_json()
            await public_manager.broadcast(f"{data.get('username')}> {data.get('message')}")
    except WebSocketDisconnect:
        public_manager.disconnect(websocket)
        await public_manager.broadcast(f"Someone left the chat!")


@app.websocket("/chat/private")
async def private_room(websocket: WebSocket):
    await private_manager.connect(websocket)
    room_id = private_manager.find_room_id(websocket)
    await private_manager.broadcast('Someone joined the chat!', room_id)

    try:
        while True:
            data = await websocket.receive_json()
            await private_manager.broadcast(f"{data.get('username')}> {data.get('message')}", room_id)
    except WebSocketDisconnect:
        private_manager.disconnect(websocket)
        await private_manager.broadcast('Someone left the chat!', room_id)
