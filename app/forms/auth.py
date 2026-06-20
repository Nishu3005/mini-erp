"""Auth forms with the exact validation rules from spec/pages/auth/auth.md."""
import re

from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import (DataRequired, Email, EqualTo, Length,
                                ValidationError)

# Password: >8 chars, at least one lower, one upper, one special character.
_SPECIAL = re.compile(r"[^A-Za-z0-9]")
_UPPER = re.compile(r"[A-Z]")
_LOWER = re.compile(r"[a-z]")


def password_policy(_form, field):
    pwd = field.data or ""
    if len(pwd) <= 8:
        raise ValidationError("Password must be more than 8 characters.")
    if not _LOWER.search(pwd):
        raise ValidationError("Password must contain a lowercase letter.")
    if not _UPPER.search(pwd):
        raise ValidationError("Password must contain an uppercase letter.")
    if not _SPECIAL.search(pwd):
        raise ValidationError("Password must contain a special character.")


class LoginForm(FlaskForm):
    login_id = StringField("Login Id", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Sign In")


class SignupForm(FlaskForm):
    login_id = StringField(
        "Enter Login Id",
        validators=[DataRequired(), Length(min=6, max=12,
                    message="Login Id must be between 6 and 12 characters.")],
    )
    email = StringField("Enter Email Id", validators=[DataRequired(), Email()])
    password = PasswordField("Enter Password", validators=[DataRequired(), password_policy])
    confirm = PasswordField(
        "Re-Enter Password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    submit = SubmitField("Sign Up")
