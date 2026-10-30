"""NFR34: enlace para activar una cuenta nueva desde el correo institucional."""

from django.contrib.auth.tokens import PasswordResetTokenGenerator


class AccountActivationTokenGenerator(PasswordResetTokenGenerator):
    # Una sal propia: un enlace de recuperar contrasena no sirve para activar.
    key_salt = "accounts.tokens.AccountActivationTokenGenerator"

    def _make_hash_value(self, user, timestamp):
        # Django ya incluye la contrasena: si alguien vuelve a registrarse con
        # el mismo correo, los enlaces anteriores dejan de servir. Con
        # is_active el enlace sirve una sola vez. Vence igual que el de
        # recuperar la contrasena (PASSWORD_RESET_TIMEOUT, 24 horas).
        return f"{super()._make_hash_value(user, timestamp)}{user.is_active}"


account_activation_token = AccountActivationTokenGenerator()
