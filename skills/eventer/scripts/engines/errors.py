class DomainError(ValueError):
    def __init__(self, code, message):
        self.code = str(code)
        self.message = message
        super().__init__(message)
