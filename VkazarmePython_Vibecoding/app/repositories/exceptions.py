"""Exceptions raised by repositories. Services translate them into
service-level errors; the API layer maps those onto HTTP status codes."""


class RepositoryError(Exception):
    pass


class EmailAlreadyExists(RepositoryError):
    pass


class AccountNotFound(RepositoryError):
    pass


class UserNotFound(RepositoryError):
    pass


class GroupNotFound(RepositoryError):
    pass


class AlreadyFriends(RepositoryError):
    pass


class FriendshipNotFound(RepositoryError):
    pass


class AlreadySubscribed(RepositoryError):
    pass


class SubscriptionNotFound(RepositoryError):
    pass


class PasteNotFound(RepositoryError):
    pass


class ChatNotFound(RepositoryError):
    pass


class ChatMemberNotFound(RepositoryError):
    pass


class AlreadyMember(RepositoryError):
    pass


class MediaNotFound(RepositoryError):
    pass
