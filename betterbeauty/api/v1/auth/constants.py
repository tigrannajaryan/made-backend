from core.types import UserRole

ROLES_WITH_ALLOWED_LOGIN = [UserRole.CLIENT, UserRole.STYLIST]


class ErrorMessages:
    ERR_EMAIL_ALREADY_TAKEN = 'err_email_already_taken'
    ERR_INCORRECT_USER_ROLE = 'err_incorrect_user_role'
    ERR_ACCOUNT_DISABLED = 'err_auth_account_disabled'
    ERR_UNABLE_TO_LOGIN_WITH_CREDENTIALS = 'err_auth_unable_to_login_with_credentials'
    ERR_MUST_INCLUDE_EMAIL_AND_PASSWORD = 'err_must_include_username_and_password'
    ERR_REFRESH_HAS_EXPIRED = 'err_refresh_expired'
    ERR_ORIG_IAT_IS_REQUIRED = 'err_orig_iat_is_required'
    ERR_WAIT_TO_REREQUEST_NEW_CODE = 'err_wait_to_rerequest_new_code'
