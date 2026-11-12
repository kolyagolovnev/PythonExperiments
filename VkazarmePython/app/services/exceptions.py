from typing import Dict

class MailSenderException(Exception):
    def __init__(self, message):
        super().__init__(self, message)

class ServiceException(Exception):
    def __init__(self, message):
        super().__init__(self, message)

class ForbiddenError(ServiceException):
    """ Пользователь не имеет прав на осществление этой операции """
    def __init__(self, account_id: int, operation: str, parameters: Dict):
        self.account_id = account_id
        self.operation = operation
        self.parameters = parameters
        formatted_params = ""
        for key, value in parameters:
            formatted_params += f"<{key}>: <{value}>\n"
        super().__init__(f"User with ID = {self.account_id} cannot process operation <{self.operation}> with parameters:\n(\n{formatted_params}\n)")

#TODO: Инициализировать какими-то данными
class ResourceNotFoundError(ServiceException):
    pass

class ResourceNotUpdatedError(ServiceException):
    pass

class ResourceDeleteError(ServiceException):
    pass

class ResourceNotCreatedError(ServiceException):
    pass

class UnknownServiceException(ServiceException):
    def __init__(self, operation: str):
        super().__init__(f"Unknown error in service operation: {operation}\n")


#SignService Exceptions
class EmailIsBusy(ServiceException):
    def __init__(self):
        super().__init__("Email is busy, use another")
    pass

class SignUpProviderNotSupported(ServiceException):
    def __init__(self, provider_name:str):
        super().__init__(f"Provider {provider_name} not supported")
    pass

class InvalidEmail(ServiceException):
    def __init__(self, explanation):
        super().__init__(f"Invalid email format, explanation: {explanation}")

class IncorrectEmailOrPassword(ServiceException):
    def __init__(self):
        super().__init__("Incorrect login or password")

class SignUpInvalidKey(ServiceException):
    def __init__(self):
        super().__init__("Key is invalid")

class SignUpAccountConfirmedButNotCreated(ServiceException):
    def __init__(self):
        super().__init__("Account is confirmed but not inserted in DB")

class SignUpCannotGetTempAccount(ServiceException):
    def __init__(self):
        super().__init__("Cannot get temp account from cache")