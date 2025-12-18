import os
import random
import logging
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify, current_app, session
from jinja2 import TemplateNotFound
from werkzeug.utils import secure_filename

# Database imports
import mysql.connector
from mysql.connector import Error
from apps import get_db_connection
from apps.admissions import blueprint

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)










@blueprint.route('/add_admission', methods=['GET', 'POST'])
def add_admission():
    user_id = session.get('id')
    if not user_id:
        flash("Session expired. Please log in again.", "danger")
        return redirect(url_for('authentication_blueprint.login'))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        if request.method == 'POST':
            connection.start_transaction()

            # 1. GENERATE UNIQUE REGISTRATION NUMBER
            current_year = datetime.now().year
            random_suffix = random.randint(1000, 9999)
            reg_no = f"SJS/{current_year}/{random_suffix}"

            # 2. INSERT GUARDIAN (Section E)
            g_data = (
                request.form.get('guardian_name'), request.form.get('relationship'),
                request.form.get('phone_primary'), request.form.get('phone_alt'),
                request.form.get('email'), request.form.get('occupation'),
                request.form.get('physical_address')
            )
            cursor.execute('''INSERT INTO guardians (full_name, relationship, phone_primary, 
                              phone_alt, email, occupation, physical_address) 
                              VALUES (%s, %s, %s, %s, %s, %s, %s)''', g_data)
            guardian_id = cursor.lastrowid

            # 3. FILE HANDLING (Section G)
            def save_admission_file(file_key, prefix):
                file = request.files.get(file_key)
                if file and file.filename != '':
                    ext = os.path.splitext(file.filename)[1]
                    filename = secure_filename(f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}")
                    upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                    os.makedirs(os.path.dirname(upload_path), exist_ok=True)
                    file.save(upload_path)
                    return filename
                return None

            photo_name = save_admission_file('image', 'photo')
            birth_cert_name = save_admission_file('birth_cert', 'bcert')
            report_name = save_admission_file('school_report', 'report')

            # 4. INSERT PUPIL (Sections A, C, D, F)
            # Include the reg_no in the tuple
            p_data = (
                guardian_id,
                reg_no,  # <--- Added unique reg_no here
                request.form.get('first_name'),
                request.form.get('other_name'),
                request.form.get('last_name'),
                request.form.get('date_of_birth'),
                request.form.get('gender'),
                request.form.get('nationality'),
                request.form.get('address'),
                request.form.get('languages_spoken'),
                request.form.get('emergency_contact'),
                request.form.get('medical_info'),
                request.form.get('special_needs'),
                request.form.get('prev_school_name'),
                request.form.get('reason_for_leaving'),
                photo_name
            )

            cursor.execute('''INSERT INTO pupils_admission (
                                guardian_id, reg_no, first_name, other_name,last_name,date_of_birth, gender, 
                                nationality, address, languages_spoken, emergency_contact, 
                                medical_info, special_needs, prev_school_name, 
                                reason_for_leaving, image
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''', p_data)
            pupil_id = cursor.lastrowid

            # 5. INSERT ADMISSION (Section B & Accountability)
            cursor.execute('''INSERT INTO admissions (
                                pupil_id, class_id, term_id, year_id, 
                                birth_cert_path, prev_report_path, admission_status, created_by,date_created
                            ) VALUES (%s, %s, %s, %s, %s, %s, 'Pending', %s,NOW())''', 
                           (pupil_id, request.form.get('class_id'), request.form.get('term_id'), 
                            request.form.get('year_id'), birth_cert_name, report_name, user_id))

            connection.commit()
            flash(f"Success! Admission {reg_no} has been submitted.", "success")
            return redirect(url_for('admissions_blueprint.add_admission'))

        # GET REQUEST: Fetch classes for dropdown
        cursor.execute('SELECT * FROM classes ORDER BY class_name ASC')
        classes = cursor.fetchall()
        return render_template('admissions/add_admission.html', classes=classes, segment='add_admission')

    except Exception as e:
        if connection.is_connected():
            connection.rollback()
        logger.error(f"Admission Error: {str(e)}")
        flash(f"An error occurred: {str(e)}", "danger")
        
        # Re-fetch classes so the page can re-render on error
        cursor.execute('SELECT * FROM classes ORDER BY class_name ASC')
        classes = cursor.fetchall()
        return render_template('admissions/add_admission.html', classes=classes, segment='add_admission')

    finally:
        if cursor: cursor.close()
        if connection: connection.close()







@blueprint.route('/admission_list')
def admission_list():
    """View and filter all admission applications."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # 1. Load filter options for dropdowns
        cursor.execute('SELECT class_id, class_name FROM classes ORDER BY class_name')
        class_list = cursor.fetchall()

        # 2. Get filter parameters
        status = request.args.get('status', '').strip()
        class_id = request.args.get('class_id', '').strip()
        search_name = request.args.get('name', '').strip()

        params = {}
        filters = []

        if status:
            filters.append("a.admission_status = %(status)s")
            params['status'] = status
        if class_id:
            filters.append("a.class_id = %(class_id)s")
            params['class_id'] = class_id
        if search_name:
            filters.append("p.first_name LIKE %(name)s")
            params['name'] = f"%{search_name}%"

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

        # 3. Main Query with LEFT JOINs and NULL handling
        query = f"""
            SELECT 
                a.admission_id,
                p.reg_no,
                p.first_name AS full_name,
                COALESCE(c.class_name, 'N/A') AS class_name,
                COALESCE(g.phone_primary, 'No Contact') AS guardian_contact,
                a.admission_status,
                a.date_created
            FROM admissions a
            INNER JOIN pupils_admission p ON a.pupil_id = p.pupil_id
            LEFT JOIN guardians g ON p.guardian_id = g.guardian_id
            LEFT JOIN classes c ON a.class_id = c.class_id
            {where_clause}
            ORDER BY a.date_created DESC
        """
        cursor.execute(query, params)
        admissions = cursor.fetchall()

        return render_template(
            'admissions/admission_list.html',
            admissions=admissions,
            class_list=class_list,
            filters={'status': status, 'class_id': class_id, 'name': search_name}
        )
    finally:
        cursor.close()
        connection.close()







@blueprint.route('/update_status/<int:admission_id>/<string:new_status>', methods=['POST'])
def update_admission_status(admission_id, new_status):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        connection.start_transaction()

        # Fetch admission record
        cursor.execute("""
            SELECT *
            FROM pupils_admission
            WHERE pupil_id = %s
            FOR UPDATE
        """, (admission_id,))
        admission = cursor.fetchone()

        if not admission:
            flash("Admission record not found.", "danger")
            return redirect(url_for('admissions_blueprint.admission_list'))

        # APPROVE
        if new_status == "Approved":

            cursor.execute("""
                INSERT INTO pupils (
                    guardian_id, reg_no, index_number, nin_number,
                    home_district, emis_number, dorm_id,
                    first_name, other_name, last_name,
                    image, date_of_birth, gender, nationality,
                    languages_spoken, stream_id, class_id,
                    admission_date, year_id, term_id,
                    address, emergency_contact, medical_info,
                    special_needs, prev_school_name, reason_for_leaving,
                    attendance_record, academic_performance,
                    notes, residential_status, created_by
                ) VALUES (
                    %(guardian_id)s, %(reg_no)s, %(index_number)s, %(nin_number)s,
                    %(home_district)s, %(emis_number)s, %(dorm_id)s,
                    %(first_name)s, %(other_name)s, %(last_name)s,
                    %(image)s, %(date_of_birth)s, %(gender)s, %(nationality)s,
                    %(languages_spoken)s, %(stream_id)s, %(class_id)s,
                    %(admission_date)s, %(year_id)s, %(term_id)s,
                    %(address)s, %(emergency_contact)s, %(medical_info)s,
                    %(special_needs)s, %(prev_school_name)s, %(reason_for_leaving)s,
                    %(attendance_record)s, %(academic_performance)s,
                    %(notes)s, %(residential_status)s, %s
                )
            """, {**admission, "created_by": session.get("user_id")})

            cursor.execute("""
                UPDATE pupils_admission
                SET admission_status = 'Approved'
                WHERE pupil_id = %s
            """, (admission_id,))

            flash("Application approved and pupil registered successfully.", "success")

        # REJECT
        elif new_status == "Rejected":
            reason = request.form.get("rejection_reason", "").strip()

            if not reason:
                flash("Rejection reason is required.", "warning")
                return redirect(url_for('admissions_blueprint.admission_list'))

            cursor.execute("""
                UPDATE pupils_admission
                SET admission_status = 'Rejected',
                    rejection_reason = %s,
                    rejected_by = %s,
                    rejected_at = NOW()
                WHERE pupil_id = %s
            """, (reason, session.get("user_id"), admission_id))

            flash("Application rejected successfully.", "info")

        connection.commit()

    except Exception as e:
        connection.rollback()
        flash(f"Database error: {str(e)}", "danger")

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('admissions_blueprint.admission_list'))





@blueprint.route('/bulk_update_status', methods=['POST'])
def bulk_update_admission_status():
    ids = request.form.getlist('admission_ids')

    if not ids:
        flash("No applications selected.", "warning")
        return redirect(url_for('admissions_blueprint.admission_list'))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        connection.start_transaction()

        cursor.execute(f"""
            SELECT *
            FROM pupils_admission
            WHERE pupil_id IN ({','.join(['%s'] * len(ids))})
            AND admission_status = 'Pending'
            FOR UPDATE
        """, ids)

        admissions = cursor.fetchall()

        if not admissions:
            flash("No pending applications found.", "info")
            return redirect(url_for('admissions_blueprint.admission_list'))

        for adm in admissions:
            cursor.execute("""
                INSERT INTO pupils (
                    guardian_id, reg_no, index_number, nin_number,
                    home_district, emis_number, dorm_id,
                    first_name, other_name, last_name,
                    image, date_of_birth, gender, nationality,
                    languages_spoken, stream_id, class_id,
                    admission_date, year_id, term_id,
                    address, emergency_contact, medical_info,
                    special_needs, prev_school_name, reason_for_leaving,
                    attendance_record, academic_performance,
                    notes, residential_status, created_by
                ) VALUES (
                    %(guardian_id)s, %(reg_no)s, %(index_number)s, %(nin_number)s,
                    %(home_district)s, %(emis_number)s, %(dorm_id)s,
                    %(first_name)s, %(other_name)s, %(last_name)s,
                    %(image)s, %(date_of_birth)s, %(gender)s, %(nationality)s,
                    %(languages_spoken)s, %(stream_id)s, %(class_id)s,
                    %(admission_date)s, %(year_id)s, %(term_id)s,
                    %(address)s, %(emergency_contact)s, %(medical_info)s,
                    %(special_needs)s, %(prev_school_name)s, %(reason_for_leaving)s,
                    %(attendance_record)s, %(academic_performance)s,
                    %(notes)s, %(residential_status)s, %s
                )
            """, {**adm, "created_by": session.get("user_id")})

            cursor.execute("""
                UPDATE pupils_admission
                SET admission_status = 'Approved'
                WHERE pupil_id = %s
            """, (adm["pupil_id"],))

        connection.commit()
        flash(f"{len(admissions)} applications approved successfully.", "success")

    except Exception as e:
        connection.rollback()
        flash(f"Bulk approval failed: {str(e)}", "danger")

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('admissions_blueprint.admission_list'))





    
@blueprint.route('/<template>')
def route_template(template):
    try:
        if not template.endswith('.html'):
            template += '.html'

        segment = get_segment(request)
        return render_template("admissions/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('admissions/page-404.html'), 404
    except Exception as e:
        logger.error(f"Template Route Error: {e}")
        return render_template('admissions/page-500.html'), 500

def get_segment(request):
    try:
        segment = request.path.split('/')[-1]
        if segment == '':
            segment = 'admissions'
        return segment
    except Exception:
        return None