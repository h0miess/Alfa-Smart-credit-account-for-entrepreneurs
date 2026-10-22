from fastapi.security import OAuth2AuthorizationCodeBearer

from core.configs import settings

if settings.app.ENVIRONMENT.is_local_environment and not settings.app.AUTH_ENABLED:

    async def bearer_scheme():
        return None
else:
    # Authorization Code + PKCE: кнопка Authorize в Swagger ведёт на страницу логина Keycloak
    bearer_scheme = OAuth2AuthorizationCodeBearer(  # type: ignore[assignment]
        authorizationUrl=settings.auth.keycloak.public_url_auth,
        tokenUrl=settings.auth.keycloak.public_url_token,
        refreshUrl=settings.auth.keycloak.public_url_token,
        scopes={
            "openid": "OpenID Connect",
            "profile": "Имя пользователя",
            "email": "Email",
        },
    )
