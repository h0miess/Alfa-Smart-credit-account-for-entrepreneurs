from pydantic import BaseModel


class JWTSettings(BaseModel):
    JWT_TOKEN_MAX_LENGTH: int = 8192
    VERIFY_AUTHORIZED_PARTY: bool = True

    ALGORITHM: list[str] = ["RS256"]
    AUDIENCE: list[str] = ["credit-backend"]
    LEEWAY: int = 10
    ISSUER: str


class KeycloakSettings(BaseModel):
    # адрес, по которому бэкенд ходит в Keycloak (в Docker — внутренний)
    BASE_URL: str
    # адрес Keycloak для браузера: на него Swagger отправляет пользователя логиниться
    PUBLIC_URL: str
    REALM: str
    CLIENT_ID: str
    CACHING_OF_CERTIFICATES_IN_SECONDS: int = 60 * 60  # 1 час
    CERTIFICATE_REQUEST_TIMEOUT_IN_SECONDS: int = 10
    TIMEOUT_IN_SECONDS: int = 10

    @property
    def url_jwk(self) -> str:
        return f"{self.BASE_URL}/realms/{self.REALM}/protocol/openid-connect/certs"

    @property
    def url_user_info(self) -> str:
        return f"{self.BASE_URL}/realms/{self.REALM}/protocol/openid-connect/userinfo"

    @property
    def public_url_auth(self) -> str:
        return f"{self.PUBLIC_URL}/realms/{self.REALM}/protocol/openid-connect/auth"

    @property
    def public_url_token(self) -> str:
        return f"{self.PUBLIC_URL}/realms/{self.REALM}/protocol/openid-connect/token"


class AuthSettings(BaseModel):
    jwt: JWTSettings
    keycloak: KeycloakSettings
