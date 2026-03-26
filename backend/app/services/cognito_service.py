import boto3
from botocore.exceptions import (
    ClientError,
    ConnectTimeoutError,
    ReadTimeoutError,
    EndpointConnectionError,
    BotoCoreError,
)
from botocore.config import Config
from botocore import UNSIGNED
from fastapi import HTTPException, status
import hmac
import hashlib
import base64
from app.config import settings

class CognitoService:
    def __init__(self):
        # Configure shorter timeouts so it doesn't hang and cause a 504 Gateway Timeout
        # if the container lacks outbound internet or IMDS access.
        boto_config = Config(
            signature_version=UNSIGNED,
            connect_timeout=5,
            read_timeout=5,
            retries={'max_attempts': 1}
        )
        self.client = boto3.client(
            'cognito-idp', 
            region_name=settings.AWS_REGION,
            config=boto_config
        )
        self.user_pool_id = settings.COGNITO_USER_POOL_ID
        self.client_id = settings.COGNITO_CLIENT_ID
        self.client_secret = settings.COGNITO_CLIENT_SECRET

    def _ensure_cognito_configured(self):
        if not self.user_pool_id or self.user_pool_id == "us-east-1_example":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cognito user pool is not configured on the server."
            )
        if not self.client_id or self.client_id == "exampleclientid":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cognito app client is not configured on the server."
            )

    def _handle_aws_timeout(self):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service timeout. Please try again in a moment."
        )

    def _get_secret_hash(self, username: str):
        if not self.client_secret:
            return None
        msg = username + self.client_id
        dig = hmac.new(
            str(self.client_secret).encode('utf-8'),
            msg.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        return base64.b64encode(dig).decode()

    def _get_kwargs_with_secret_hash(self, username: str, **kwargs):
        secret_hash = self._get_secret_hash(username)
        if secret_hash:
            kwargs['SecretHash'] = secret_hash
        return kwargs

    def sign_up(self, email: str, password: str, name: str, affiliation: str):
        self._ensure_cognito_configured()
        try:
            kwargs = {
                'ClientId': self.client_id,
                'Username': email,
                'Password': password,
                'UserAttributes': [
                    {'Name': 'email', 'Value': email},
                    {'Name': 'name', 'Value': name},
                    {'Name': 'custom:affiliation', 'Value': affiliation}
                ]
            }
            response = self.client.sign_up(**self._get_kwargs_with_secret_hash(email, **kwargs))
            return response
        except (ConnectTimeoutError, ReadTimeoutError, EndpointConnectionError, BotoCoreError):
            self._handle_aws_timeout()
        except ClientError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=e.response['Error']['Message']
            )

    def sign_in(self, email: str, password: str):
        self._ensure_cognito_configured()
        try:
            auth_parameters = {
                'USERNAME': email,
                'PASSWORD': password
            }
            secret_hash = self._get_secret_hash(email)
            if secret_hash:
                auth_parameters['SECRET_HASH'] = secret_hash

            kwargs = {
                'ClientId': self.client_id,
                'AuthFlow': 'USER_PASSWORD_AUTH',
                'AuthParameters': auth_parameters
            }
            response = self.client.initiate_auth(
                **kwargs
            )
            return response['AuthenticationResult']
        except (ConnectTimeoutError, ReadTimeoutError, EndpointConnectionError, BotoCoreError):
            self._handle_aws_timeout()
        except ClientError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=e.response['Error']['Message']
            )

    def confirm_signup(self, email: str, code: str):
        self._ensure_cognito_configured()
        try:
            kwargs = {
                'ClientId': self.client_id,
                'Username': email,
                'ConfirmationCode': code
            }
            self.client.confirm_sign_up(**self._get_kwargs_with_secret_hash(email, **kwargs))
            return True
        except (ConnectTimeoutError, ReadTimeoutError, EndpointConnectionError, BotoCoreError):
            self._handle_aws_timeout()
        except ClientError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=e.response['Error']['Message']
            )

    def forgot_password(self, email: str):
        self._ensure_cognito_configured()
        try:
            kwargs = {
                'ClientId': self.client_id,
                'Username': email
            }
            self.client.forgot_password(**self._get_kwargs_with_secret_hash(email, **kwargs))
            return True
        except (ConnectTimeoutError, ReadTimeoutError, EndpointConnectionError, BotoCoreError):
            self._handle_aws_timeout()
        except ClientError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=e.response['Error']['Message']
            )

    def confirm_forgot_password(self, email: str, code: str, new_password: str):
        self._ensure_cognito_configured()
        try:
            kwargs = {
                'ClientId': self.client_id,
                'Username': email,
                'ConfirmationCode': code,
                'Password': new_password
            }
            self.client.confirm_forgot_password(**self._get_kwargs_with_secret_hash(email, **kwargs))
            return True
        except (ConnectTimeoutError, ReadTimeoutError, EndpointConnectionError, BotoCoreError):
            self._handle_aws_timeout()
        except ClientError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=e.response['Error']['Message']
            )

cognito_service = CognitoService()
