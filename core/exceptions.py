# core/exceptions.py
# Пользовательские исключения FazTestBot


class FazTestBotException(Exception):
    """Базовое исключение для бота"""

    def __init__(self, message: str, code: str = "UNKNOWN_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code


# ====== ОШИБКИ МОДУЛЕЙ ======

class ModuleNotFoundError(FazTestBotException):
    """Модуль не найден"""

    def __init__(self, module_id: str):
        super().__init__(f"Модуль '{module_id}' не найден", "MODULE_NOT_FOUND")
        self.module_id = module_id


class ModuleLoadError(FazTestBotException):
    """Ошибка загрузки модуля"""

    def __init__(self, module_id: str, reason: str):
        super().__init__(f"Не удалось загрузить модуль '{module_id}': {reason}", "MODULE_LOAD_ERROR")
        self.module_id = module_id
        self.reason = reason


class ModuleValidationError(FazTestBotException):
    """Модуль не прошёл валидацию"""

    def __init__(self, module_id: str, errors: List[str]):
        message = f"Модуль '{module_id}' не прошёл валидацию:\n" + "\n".join(errors)
        super().__init__(message, "MODULE_VALIDATION_ERROR")
        self.module_id = module_id
        self.errors = errors


# ====== ОШИБКИ БАЗЫ ДАННЫХ ======

class DatabaseError(FazTestBotException):
    """Ошибка базы данных"""

    def __init__(self, message: str, operation: str = None):
        super().__init__(message, "DATABASE_ERROR")
        self.operation = operation


class DatabaseConnectionError(DatabaseError):
    """Ошибка подключения к БД"""

    def __init__(self, details: str = None):
        message = "Не удалось подключиться к базе данных"
        if details:
            message += f": {details}"
        super().__init__(message, "DB_CONNECTION_ERROR")


class DatabaseQueryError(DatabaseError):
    """Ошибка выполнения запроса"""

    def __init__(self, query: str, details: str = None):
        message = f"Ошибка выполнения запроса"
        if details:
            message += f": {details}"
        super().__init__(message, "DB_QUERY_ERROR")
        self.query = query


# ====== ОШИБКИ API ======

class APIError(FazTestBotException):
    """Ошибка внешнего API"""

    def __init__(self, service: str, message: str, status_code: int = None):
        super().__init__(f"API {service}: {message}", "API_ERROR")
        self.service = service
        self.status_code = status_code


class APIRateLimitError(APIError):
    """Превышен лимит запросов к API"""

    def __init__(self, service: str, retry_after: int = None):
        message = "Превышен лимит запросов"
        if retry_after:
            message += f". Повторите через {retry_after} сек"
        super().__init__(service, message, 429)
        self.retry_after = retry_after


class APIAuthenticationError(APIError):
    """Ошибка аутентификации в API"""

    def __init__(self, service: str):
        super().__init__(service, "Неверный API ключ или токен", 401)


# ====== ОШИБКИ ПОЛЬЗОВАТЕЛЯ ======

class UserInputError(FazTestBotException):
    """Ошибка пользовательского ввода"""

    def __init__(self, message: str, field: str = None):
        super().__init__(message, "USER_INPUT_ERROR")
        self.field = field


class ValidationError(UserInputError):
    """Ошибка валидации данных"""

    def __init__(self, field: str, message: str):
        super().__init__(f"Поле '{field}': {message}", "VALIDATION_ERROR")
        self.field = field


class LimitExceededError(FazTestBotException):
    """Превышен лимит использования"""

    def __init__(self, limit_type: str, limit_value: int, current_value: int = None):
        message = f"Превышен лимит {limit_type}: {limit_value}"
        if current_value:
            message += f" (текущее: {current_value})"
        super().__init__(message, "LIMIT_EXCEEDED")
        self.limit_type = limit_type
        self.limit_value = limit_value
        self.current_value = current_value


# ====== ОШИБКИ АДМИНИСТРИРОВАНИЯ ======

class AdminPermissionError(FazTestBotException):
    """Недостаточно прав администратора"""

    def __init__(self, action: str):
        super().__init__(f"Недостаточно прав для действия: {action}", "ADMIN_PERMISSION_ERROR")
        self.action = action


class AdminAuthenticationError(FazTestBotException):
    """Ошибка аутентификации администратора"""

    def __init__(self, reason: str = "Неверный код"):
        super().__init__(reason, "ADMIN_AUTH_ERROR")


# ====== ОШИБКИ ФАЙЛОВОЙ СИСТЕМЫ ======

class FileError(FazTestBotException):
    """Ошибка работы с файлами"""

    def __init__(self, message: str, filepath: str = None):
        super().__init__(message, "FILE_ERROR")
        self.filepath = filepath


class FileNotFoundError(FileError):
    """Файл не найден"""

    def __init__(self, filepath: str):
        super().__init__(f"Файл не найден: {filepath}", filepath)


class FilePermissionError(FileError):
    """Нет прав доступа к файлу"""

    def __init__(self, filepath: str, operation: str):
        super().__init__(f"Нет прав на {operation} файла: {filepath}", filepath)
        self.operation = operation


# ====== УТИЛИТЫ ДЛЯ ОБРАБОТКИ ИСКЛЮЧЕНИЙ ======

def handle_exception(exc: Exception, logger=None) -> str:
    """
    Универсальная обработка исключений

    :param exc: Исключение
    :param logger: Логгер
    :return: Сообщение для пользователя
    """
    if logger:
        logger.error(f"Exception: {type(exc).__name__}: {str(exc)}")

    # Пользовательские исключения
    if isinstance(exc, FazTestBotException):
        return f"❌ {exc.message}"

    # Стандартные исключения
    if isinstance(exc, sqlite3.Error):
        return "❌ Ошибка базы данных. Попробуйте позже."

    if isinstance(exc, ValueError):
        return f"❌ Некорректное значение: {exc}"

    if isinstance(exc, TypeError):
        return f"❌ Ошибка типа данных: {exc}"

    if isinstance(exc, PermissionError):
        return "❌ Нет прав доступа"

    if isinstance(exc, FileNotFoundError):
        return "❌ Файл не найден"

    # Неизвестная ошибка
    return "❌ Произошла непредвиденная ошибка. Попробуйте позже."


def is_user_error(exc: Exception) -> bool:
    """Проверка является ли ошибка пользовательской"""
    return isinstance(exc, (UserInputError, ValidationError, LimitExceededError))


def is_system_error(exc: Exception) -> bool:
    """Проверка является ли ошибка системной"""
    return isinstance(exc, (DatabaseError, APIError, FileError))


def is_critical_error(exc: Exception) -> bool:
    """Проверка является ли ошибка критической"""
    return isinstance(exc, (DatabaseConnectionError, ModuleLoadError))