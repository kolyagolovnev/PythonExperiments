class RepositoryError(Exception):
    """Базовый класс для всех ошибок репозитория."""
    pass

class NotFoundError(RepositoryError):
    def __init__(self, resource: str, id_: int):
        super().__init__(f"{resource} with id {id_} not found")

class DuplicateKeyError(RepositoryError):
    def __init__(self, field: str, value: str):
        self.field = field
        self.value = value
        super().__init__(f"Duplicate value for '{field}': {value}")