# from flask_wtf import FlaskForm
# from wtforms import StringField, SubmitField, PasswordField, TextAreaField
# from wtforms.validators import DataRequired, URL, Email, Length

# class CreateRegForm(FlaskForm):
#     username = StringField("Username", validators=[DataRequired()])
#     email = StringField("Email", validators=[DataRequired(), Email()])
#     password = PasswordField("Password", validators=[DataRequired(), Length(min=8)])
#     submit = SubmitField("Sign Up")

# class CreateLoginForm(FlaskForm):
#     email = StringField("Email", validators=[DataRequired(), Email()])
#     password = PasswordField("Password", validators=[DataRequired()])
#     submit = SubmitField("Log In")