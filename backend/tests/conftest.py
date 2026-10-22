import os

os.environ.update(
    {
        "APP__ENVIRONMENT": "unittest",
        "APP__AUTH_ENABLED": "false",
        "APP__MOCK_USER_UUID": "00000000-0000-4000-8000-000000000101",
        "POSTGRES__HOST": "localhost",
        "POSTGRES__DB": "credit_cabinet",
        "POSTGRES__USER": "test",
        "POSTGRES__PASSWORD": "test",
        "AUTH__KEYCLOAK__BASE_URL": "http://keycloak.test",
        "AUTH__KEYCLOAK__PUBLIC_URL": "http://keycloak.test",
        "AUTH__KEYCLOAK__REALM": "alfa-credit",
        "AUTH__KEYCLOAK__CLIENT_ID": "credit-cabinet-web",
        "AUTH__JWT__ISSUER": "http://keycloak.test/realms/alfa-credit",
        "REDIS__HOST": "localhost",
        "TESTCONTAINERS_RYUK_DISABLED": "true",
    }
)
