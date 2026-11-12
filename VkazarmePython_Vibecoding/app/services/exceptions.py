"""Service-level errors.

The API layer maps each of these onto an HTTP status code
(see app/main.py) so routers and services stay HTTP-free.
"""


class ServiceError(Exception):
    default_detail = "Service error"

    def __init__(self, detail: str | None = None):
        super().__init__(detail or self.default_detail)


# --- sign ---
class InvalidEmail(ServiceError):
    default_detail = "Invalid email format"


class EmailIsBusy(ServiceError):
    default_detail = "Email is already registered"


class IncorrectEmailOrPassword(ServiceError):
    default_detail = "Invalid login or password"


# --- token ---
class NotAuthenticated(ServiceError):
    default_detail = "Not authenticated"


class InvalidToken(ServiceError):
    default_detail = "Invalid token"


class TokenExpired(ServiceError):
    default_detail = "Token expired"


# --- users / friends / subscriptions ---
class PermissionDenied(ServiceError):
    default_detail = "User does not have access rights"


class UserNotFound(ServiceError):
    default_detail = "Such a user does not exist"


class GroupNotFound(ServiceError):
    default_detail = "Such a group does not exist"


class PasteNotFound(ServiceError):
    default_detail = "Such a post does not exist"


# --- chats ---
class ChatNotFound(ServiceError):
    default_detail = "Such a chat does not exist"


class ChatMemberNotFound(ServiceError):
    default_detail = "Such a chat user not found"


class AlreadyMember(ServiceError):
    default_detail = "User is already a chat member"


class PersonalChatFixed(ServiceError):
    default_detail = "Members of a personal chat cannot be changed"


class InvalidChatMembers(ServiceError):
    default_detail = "A personal chat requires exactly one other user"


class CannotRemoveOwner(ServiceError):
    default_detail = "The chat owner cannot be removed"


# --- media ---
class MediaNotFound(ServiceError):
    default_detail = "Such a media file does not exist"


class UnsupportedMediaType(ServiceError):
    default_detail = "Unsupported media type; allowed: image/png, image/jpeg, image/gif, image/webp"


class MediaTooLarge(ServiceError):
    default_detail = "File is too large"


class EmptyMediaFile(ServiceError):
    default_detail = "File is empty"


class SubscriptionNotFound(ServiceError):
    default_detail = "Such a subscription does not exist"


class AlreadyFriends(ServiceError):
    default_detail = "Users are already friends"


class FriendshipNotFound(ServiceError):
    default_detail = "Such a friend does not exist"


class SelfFriendship(ServiceError):
    default_detail = "Cannot add yourself as a friend"


class AlreadySubscribed(ServiceError):
    default_detail = "Already subscribed to this group"
