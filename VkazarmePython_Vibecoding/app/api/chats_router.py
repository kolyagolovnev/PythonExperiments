"""/chats endpoints: chats, members, messages; plus the realtime WebSocket."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, WebSocket, WebSocketDisconnect

from app.api.deps import get_current_token, get_chat_service
from app.container import Container
from app.domains import models as dm
from app.dto.chat_dto import (
    ChatDTO,
    ChatListItemDTO,
    ChatMemberListItemDTO,
    ChatMemberPostDTO,
    ChatPostDTO,
    MessageDTO,
    MessagePostDTO,
)
from app.repositories import exceptions as rex
from app.services import exceptions as sex
from app.services.chat_service import ChatService

router = APIRouter(tags=["chats"])

Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@router.get("/chats", response_model=list[ChatListItemDTO])
async def list_chats(
    limit: Limit = 10,
    offset: Offset = 0,
    token: dm.AuthToken = Depends(get_current_token),
    chat_service: ChatService = Depends(get_chat_service),
) -> list[ChatListItemDTO]:
    items = await chat_service.list_chats(token, limit=limit, offset=offset)
    return [ChatListItemDTO.from_entity(item) for item in items]


@router.post("/chats", status_code=200)
async def create_chat(
    body: ChatPostDTO,
    token: dm.AuthToken = Depends(get_current_token),
    chat_service: ChatService = Depends(get_chat_service),
) -> None:
    chat = await chat_service.create_chat(
        token, name=body.name, chat_type=dm.ChatType(body.chat_type),
        users=body.users, photo_url=body.photo_url,
    )
    # spec: 200 with empty body; the client finds the chat id via GET /chats
    return None


@router.get("/chats/{ChatID}", response_model=ChatDTO)
async def get_chat(
    chat_id: Annotated[int, Path(alias="ChatID")],
    token: dm.AuthToken = Depends(get_current_token),
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatDTO:
    chat = await chat_service.get_chat(token, chat_id)
    return ChatDTO.from_entity(chat)


@router.get("/chats/{ChatID}/members", response_model=list[ChatMemberListItemDTO])
async def list_members(
    chat_id: Annotated[int, Path(alias="ChatID")],
    limit: Limit = 10,
    offset: Offset = 0,
    token: dm.AuthToken = Depends(get_current_token),
    chat_service: ChatService = Depends(get_chat_service),
) -> list[ChatMemberListItemDTO]:
    items = await chat_service.list_members(token, chat_id, limit=limit, offset=offset)
    return [ChatMemberListItemDTO.from_entity(item) for item in items]


@router.post("/chats/{ChatID}/members", status_code=200)
async def add_member(
    chat_id: Annotated[int, Path(alias="ChatID")],
    body: ChatMemberPostDTO,
    token: dm.AuthToken = Depends(get_current_token),
    chat_service: ChatService = Depends(get_chat_service),
) -> None:
    await chat_service.add_member(token, chat_id, body.user_id)


@router.delete("/chats/{ChatID}/members/{MemberID}", status_code=200)
async def remove_member(
    chat_id: Annotated[int, Path(alias="ChatID")],
    member_id: Annotated[int, Path(alias="MemberID")],
    token: dm.AuthToken = Depends(get_current_token),
    chat_service: ChatService = Depends(get_chat_service),
) -> None:
    await chat_service.remove_member(token, chat_id, member_id)


@router.get("/chats/{ChatID}/messages", response_model=list[MessageDTO])
async def list_messages(
    chat_id: Annotated[int, Path(alias="ChatID")],
    limit: Limit = 10,
    offset: Offset = 0,
    token: dm.AuthToken = Depends(get_current_token),
    chat_service: ChatService = Depends(get_chat_service),
) -> list[MessageDTO]:
    messages = await chat_service.list_messages(token, chat_id, limit=limit, offset=offset)
    return [MessageDTO.from_entity(message) for message in messages]


@router.post("/chats/{ChatID}/messages", status_code=200)
async def send_message(
    chat_id: Annotated[int, Path(alias="ChatID")],
    body: MessagePostDTO,
    token: dm.AuthToken = Depends(get_current_token),
    chat_service: ChatService = Depends(get_chat_service),
) -> None:
    await chat_service.send_message(token, chat_id, body.text)


@router.websocket("/ws/chats/{ChatID}")
async def chat_socket(
    websocket: WebSocket,
    chat_id: Annotated[int, Path(alias="ChatID")],
    token: Annotated[str, Query(description="JWT access token; browsers cannot set headers on WebSocket")],
) -> None:
    """Realtime chat channel (AsyncAPI: channel chats/{ChatID}).

    Handshake: connect, then send {"type": "subscribe", "chatId": <ChatID>}.
    Afterwards the server pushes newMessage/memberChange envelopes; the
    client may keep the connection alive with {"type": "ping"} (answered
    by {"type": "pong"}). Close codes: 4400 bad subscribe frame,
    4401 invalid/expired token, 4403 not a chat member, 4404 unknown chat.
    """
    container: Container = websocket.app.state.container
    await websocket.accept()

    try:
        token_data = container.auth_service.decode_token(token)
    except (sex.TokenExpired, sex.InvalidToken, sex.NotAuthenticated):
        await websocket.close(code=4401)
        return

    try:
        frame = await websocket.receive_json()
    except WebSocketDisconnect:
        return
    except ValueError:
        await websocket.close(code=4400)
        return
    if frame.get("type") != "subscribe" or frame.get("chatId") != chat_id:
        await websocket.close(code=4400)
        return

    try:
        await container.chat_service.get_chat(token_data, chat_id)
    except (rex.ChatNotFound, sex.ChatNotFound):
        await websocket.close(code=4404)
        return
    except sex.PermissionDenied:
        await websocket.close(code=4403)
        return

    await container.chat_events.connect(chat_id, token_data.sub, websocket)
    try:
        while True:
            frame = await websocket.receive_json()
            if frame.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except (WebSocketDisconnect, ValueError, KeyError):
        pass
    finally:
        await container.chat_events.disconnect(chat_id, token_data.sub, websocket)
