import os
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, DateField, TextAreaField, SelectField
from wtforms.validators import DataRequired, Email, Length
from werkzeug.security import generate_password_hash
from models import db, AdminUser, Patient, Doctor, Appointment

# =============== Инициализация Flask ===============
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'poliklinika-secret-key-2024')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///poliklinika.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# =============== Формы ===============
class LoginForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Войти')

class PatientForm(FlaskForm):
    full_name = StringField('ФИО', validators=[DataRequired(), Length(max=150)])
    phone = StringField('Телефон', validators=[DataRequired(), Length(max=20)])
    email = StringField('Email', validators=[Length(max=120), Email()])
    birth_date = DateField('Дата рождения', format='%Y-%m-%d')
    address = TextAreaField('Адрес')
    submit = SubmitField('Сохранить')

class DoctorForm(FlaskForm):
    full_name = StringField('ФИО', validators=[DataRequired(), Length(max=150)])
    specialty = StringField('Специальность', validators=[DataRequired(), Length(max=100)])
    phone = StringField('Телефон', validators=[DataRequired(), Length(max=20)])
    email = StringField('Email', validators=[Length(max=120), Email()])
    room = StringField('Кабинет', validators=[Length(max=20)])
    submit = SubmitField('Сохранить')

class AppointmentForm(FlaskForm):
    patient_id = SelectField('Пациент', coerce=int, validators=[DataRequired()])
    doctor_id = SelectField('Врач', coerce=int, validators=[DataRequired()])
    appointment_date = StringField('Дата и время (ГГГГ-ММ-ДД ЧЧ:ММ)', validators=[DataRequired()])
    status = SelectField('Статус', choices=[('запланирован', 'Запланирован'), ('завершён', 'Завершён'), ('отменён', 'Отменён')])
    submit = SubmitField('Сохранить')

# =============== Загрузка пользователя ===============
@login_manager.user_loader
def load_user(user_id):
    return AdminUser.query.get(int(user_id))

# =============== Создание админа при первом запуске ===============
@app.before_first_request
def create_admin():
    db.create_all()
    if not AdminUser.query.filter_by(username='admin').first():
        admin = AdminUser(username='admin')
        admin.set_password('admin123')  # ⚠️ Измени пароль в продакшене!
        db.session.add(admin)
        db.session.commit()

# =============== Роуты ===============
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = AdminUser.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('Вы успешно вошли в систему!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Неверное имя пользователя или пароль.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('login'))

@app.route('/admin')
@login_required
def dashboard():
    stats = {
        'patients': Patient.query.count(),
        'doctors': Doctor.query.count(),
        'appointments': Appointment.query.count(),
        'today_appointments': Appointment.query.filter(
            db.func.date(Appointment.appointment_date) == datetime.today().date()
        ).count()
    }
    return render_template('admin/dashboard.html', stats=stats)

# ========== Пациенты ==========
@app.route('/admin/patients')
@login_required
def patients():
    page = request.args.get('page', 1, type=int)
    patients_list = Patient.query.paginate(page=page, per_page=10)
    return render_template('admin/patients.html', patients=patients_list)

@app.route('/admin/patients/add', methods=['GET', 'POST'])
@login_required
def add_patient():
    form = PatientForm()
    if form.validate_on_submit():
        patient = Patient(
            full_name=form.full_name.data,
            phone=form.phone.data,
            email=form.email.data,
            birth_date=form.birth_date.data,
            address=form.address.data
        )
        db.session.add(patient)
        db.session.commit()
        flash('Пациент добавлен!', 'success')
        return redirect(url_for('patients'))
    return render_template('admin/patient_form.html', form=form, title='Добавить пациента')

@app.route('/admin/patients/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_patient(id):
    patient = Patient.query.get_or_404(id)
    form = PatientForm(obj=patient)
    if form.validate_on_submit():
        form.populate_obj(patient)
        db.session.commit()
        flash('Пациент обновлён!', 'success')
        return redirect(url_for('patients'))
    return render_template('admin/patient_form.html', form=form, title='Редактировать пациента')

@app.route('/admin/patients/delete/<int:id>', methods=['POST'])
@login_required
def delete_patient(id):
    patient = Patient.query.get_or_404(id)
    db.session.delete(patient)
    db.session.commit()
    flash('Пациент удалён!', 'warning')
    return redirect(url_for('patients'))

# ========== Врачи ==========
@app.route('/admin/doctors')
@login_required
def doctors():
    page = request.args.get('page', 1, type=int)
    doctors_list = Doctor.query.paginate(page=page, per_page=10)
    return render_template('admin/doctors.html', doctors=doctors_list)

@app.route('/admin/doctors/add', methods=['GET', 'POST'])
@login_required
def add_doctor():
    form = DoctorForm()
    if form.validate_on_submit():
        doctor = Doctor(
            full_name=form.full_name.data,
            specialty=form.specialty.data,
            phone=form.phone.data,
            email=form.email.data,
            room=form.room.data
        )
        db.session.add(doctor)
        db.session.commit()
        flash('Врач добавлен!', 'success')
        return redirect(url_for('doctors'))
    return render_template('admin/doctor_form.html', form=form, title='Добавить врача')

@app.route('/admin/doctors/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_doctor(id):
    doctor = Doctor.query.get_or_404(id)
    form = DoctorForm(obj=doctor)
    if form.validate_on_submit():
        form.populate_obj(doctor)
        db.session.commit()
        flash('Врач обновлён!', 'success')
        return redirect(url_for('doctors'))
    return render_template('admin/doctor_form.html', form=form, title='Редактировать врача')

@app.route('/admin/doctors/delete/<int:id>', methods=['POST'])
@login_required
def delete_doctor(id):
    doctor = Doctor.query.get_or_404(id)
    db.session.delete(doctor)
    db.session.commit()
    flash('Врач удалён!', 'warning')
    return redirect(url_for('doctors'))

# ========== Приёмы ==========
@app.route('/admin/appointments')
@login_required
def appointments():
    page = request.args.get('page', 1, type=int)
    appointments_list = Appointment.query.order_by(Appointment.appointment_date.desc()).paginate(page=page, per_page=10)
    return render_template('admin/appointments.html', appointments=appointments_list)

@app.route('/admin/appointments/add', methods=['GET', 'POST'])
@login_required
def add_appointment():
    form = AppointmentForm()
    form.patient_id.choices = [(p.id, p.full_name) for p in Patient.query.all()]
    form.doctor_id.choices = [(d.id, f"{d.full_name} ({d.specialty})") for d in Doctor.query.all()]
    if form.validate_on_submit():
        try:
            appt_date = datetime.strptime(form.appointment_date.data, '%Y-%m-%d %H:%M')
        except ValueError:
            flash('Неверный формат даты. Используйте ГГГГ-ММ-ДД ЧЧ:ММ', 'danger')
            return render_template('admin/appointment_form.html', form=form, title='Добавить приём')
        appointment = Appointment(
            patient_id=form.patient_id.data,
            doctor_id=form.doctor_id.data,
            appointment_date=appt_date,
            status=form.status.data
        )
        db.session.add(appointment)
        db.session.commit()
        flash('Приём добавлен!', 'success')
        return redirect(url_for('appointments'))
    return render_template('admin/appointment_form.html', form=form, title='Добавить приём')

@app.route('/admin/appointments/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_appointment(id):
    appointment = Appointment.query.get_or_404(id)
    form = AppointmentForm(obj=appointment)
    form.patient_id.choices = [(p.id, p.full_name) for p in Patient.query.all()]
    form.doctor_id.choices = [(d.id, f"{d.full_name} ({d.specialty})") for d in Doctor.query.all()]
    if form.validate_on_submit():
        try:
            appt_date = datetime.strptime(form.appointment_date.data, '%Y-%m-%d %H:%M')
        except ValueError:
            flash('Неверный формат даты. Используйте ГГГГ-ММ-ДД ЧЧ:ММ', 'danger')
            return render_template('admin/appointment_form.html', form=form, title='Редактировать приём')
        appointment.patient_id = form.patient_id.data
        appointment.doctor_id = form.doctor_id.data
        appointment.appointment_date = appt_date
        appointment.status = form.status.data
        db.session.commit()
        flash('Приём обновлён!', 'success')
        return redirect(url_for('appointments'))
    # Предзаполнение даты в нужном формате
    form.appointment_date.data = appointment.appointment_date.strftime('%Y-%m-%d %H:%M')
    return render_template('admin/appointment_form.html', form=form, title='Редактировать приём')

@app.route('/admin/appointments/delete/<int:id>', methods=['POST'])
@login_required
def delete_appointment(id):
    appointment = Appointment.query.get_or_404(id)
    db.session.delete(appointment)
    db.session.commit()
    flash('Приём удалён!', 'warning')
    return redirect(url_for('appointments'))

# ========== Главная страница (редирект на админку) ==========
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

# ========== Запуск ==========
if __name__ == '__main__':
    app.run(debug=True)
