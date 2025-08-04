from flask import Flask, request, redirect, render_template, session, url_for, send_file, Response
from urllib.parse import urlparse
import string
import random
import re
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import logging
import io
from werkzeug.utils import secure_filename

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.urandom(24)

logging.basicConfig(level=logging.DEBUG)
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL dan SUPABASE_KEY harus diatur di file .env.")

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    raise ValueError(f"Gagal menginisialisasi Supabase: {str(e)}")

def generate_short_code(length=6):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def is_valid_custom_code(code):
    return bool(re.match(r'^[a-zA-Z0-9_-]{3,10}$', code))

def code_exists(short_code):
    try:
        response = supabase.table('links').select('short_code').eq('short_code', short_code).execute()
        return len(response.data) > 0
    except Exception as e:
        logging.error(f"Error saat cek kode: {str(e)}")
        return False

def email_exists(email, exclude_user_id=None):
    try:
        query = supabase.table('users').select('email').eq('email', email)
        if exclude_user_id:
            query = query.neq('id', exclude_user_id)
        response = query.execute()
        return len(response.data) > 0
    except Exception as e:
        logging.error(f"Error saat cek email: {str(e)}")
        return False

def store_link(short_code, content_type, content, user_id):
    try:
        supabase.table('links').insert({
            'short_code': short_code,
            'content_type': content_type,
            'content': content,
            'user_id': user_id
        }).execute()
        logging.debug(f"Stored link: short_code={short_code}, content_type={content_type}, content={content}, user_id={user_id}")
    except Exception as e:
        logging.error(f"Error saat menyimpan link: {str(e)}")
        raise

def delete_link(short_code, user_id):
    try:
        response = supabase.table('links').select('*').eq('short_code', short_code).eq('user_id', user_id).execute()
        if not response.data:
            return False
        link = response.data[0]
        if link['content_type'] in ('image', 'document'):
            file_name = link['content'].split('/content/')[-1]
            supabase.storage.from_('content').remove([file_name])
        supabase.table('links').delete().eq('short_code', short_code).eq('user_id', user_id).execute()
        logging.debug(f"Deleted link: short_code={short_code}, user_id={user_id}")
        return True
    except Exception as e:
        logging.error(f"Error saat hapus link: {str(e)}")
        return False

def update_short_code(old_code, new_code, user_id):
    try:
        if code_exists(new_code):
            return False, "Kode kustom sudah digunakan!"
        if not is_valid_custom_code(new_code):
            return False, "Kode kustom tidak valid! Gunakan 3-10 karakter (huruf, angka, _, -)."
        supabase.table('links').update({'short_code': new_code}).eq('short_code', old_code).eq('user_id', user_id).execute()
        logging.debug(f"Updated short_code: {old_code} to {new_code}, user_id={user_id}")
        return True, None
    except Exception as e:
        logging.error(f"Error saat update short_code: {str(e)}")
        return False, str(e)

@app.route('/')
def index():
    user = session.get('user')
    return render_template('index.html', user=user)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if email_exists(email):
            return render_template('register.html', error='Email sudah digunakan!')
        try:
            response = supabase.table('users').insert({
                'email': email,
                'password': password
            }).execute()
            user_id = response.data[0]['id']
            session['user'] = {'email': email, 'id': user_id}
            return redirect(url_for('index'))
        except Exception as e:
            logging.error(f"Error saat register: {str(e)}")
            return render_template('register.html', error=str(e))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        response = supabase.table('users').select('*').eq('email', email).eq('password', password).execute()
        if response.data:
            session['user'] = {'email': email, 'id': response.data[0]['id']}
            return redirect(url_for('index'))
        return render_template('login.html', error='Email atau password salah!')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    user_id = session['user']['id']
    page = int(request.args.get('page', 1))
    per_page = 10
    query = supabase.table('links').select('*').eq('user_id', user_id)
    total_links = len(query.execute().data)
    total_pages = (total_links + per_page - 1) // per_page
    links = query.order('created_at', desc=True).range((page - 1) * per_page, page * per_page - 1).execute().data
    return render_template('dashboard.html', user=session['user'], links=links, page=page, total_pages=total_pages)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user' not in session:
        return redirect(url_for('login'))
    user = session['user']
    if request.method == 'POST':
        new_email = request.form.get('email', '').strip()
        new_password = request.form.get('password', '').strip()
        updates = {}
        if new_email and new_email != user['email']:
            if email_exists(new_email, exclude_user_id=user['id']):
                return render_template('profile.html', user=user, error='Email sudah digunakan!')
            updates['email'] = new_email
        if new_password:
            updates['password'] = new_password
        if not updates:
            return render_template('profile.html', user=user, error='Tidak ada perubahan yang dilakukan!')
        try:
            supabase.table('users').update(updates).eq('id', user['id']).execute()
            session['user']['email'] = new_email if new_email else user['email']
            return render_template('profile.html', user=session['user'], success='Profil berhasil diperbarui!')
        except Exception as e:
            logging.error(f"Error saat update profil: {str(e)}")
            return render_template('profile.html', user=user, error=f'Gagal memperbarui profil: {str(e)}')
    return render_template('profile.html', user=user)

@app.route('/shorten', methods=['POST'])
def shorten():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    content_type = request.form['content_type']
    custom_code = request.form.get('custom_code', '').strip()
    user_id = session['user']['id']
    
    if custom_code:
        if not is_valid_custom_code(custom_code):
            return render_template('index.html', user=session['user'], error='Kode kustom tidak valid! Gunakan 3-10 karakter (huruf, angka, _, -).')
        if code_exists(custom_code):
            return render_template('index.html', user=session['user'], error='Kode kustom sudah digunakan! Coba kode lain.')
        short_code = custom_code
    else:
        while True:
            short_code = generate_short_code()
            if not code_exists(short_code):
                break

    content = ''
    if content_type == 'url':
        content = request.form.get('url', '')
        if not content.startswith(('http://', 'https://')):
            content = 'http://' + content
    elif content_type == 'text':
        content = request.form.get('text', '')
    elif content_type in ('image', 'document'):
        file = request.files.get('file')
        if file:
            allowed_extensions = {
                'image': ['jpg', 'jpeg', 'png'],
                'document': ['pdf', 'docx']
            }
            file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
            if content_type == 'image' and file_ext not in allowed_extensions['image']:
                return render_template('index.html', user=session['user'], error=f'File tidak valid! Gunakan {", ".join(allowed_extensions["image"])} untuk gambar.')
            if content_type == 'document' and file_ext not in allowed_extensions['document']:
                return render_template('index.html', user=session['user'], error=f'File tidak valid! Gunakan {", ".join(allowed_extensions["document"])} untuk dokumen.')
            
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)
            if file_size > 10 * 1024 * 1024:
                return render_template('index.html', user=session['user'], error='File terlalu besar! Maksimum 10MB.')
            
            file_name = f"{user_id}/{short_code}_{file.filename.replace(' ', '_')}"
            content_type_map = {
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'png': 'image/png',
                'pdf': 'application/pdf',
                'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            }
            try:
                file_content = file.read()
                supabase.storage.from_('content').upload(
                    file_name,
                    file_content,
                    {'content-type': content_type_map.get(file_ext, 'application/octet-stream')}
                )
                content = supabase.storage.from_('content').get_public_url(file_name)
            except Exception as e:
                logging.error(f"Error saat upload file: {str(e)}")
                return render_template('index.html', user=session['user'], error=f'Gagal mengunggah file: {str(e)}')
        else:
            return render_template('index.html', user=session['user'], error='Harap unggah file!')

    if not content:
        return render_template('index.html', user=session['user'], error='Konten tidak valid! Pastikan URL, teks, atau file diisi.')

    try:
        store_link(short_code, content_type, content, user_id)
    except Exception as e:
        return render_template('index.html', user=session['user'], error=f'Gagal menyimpan link: {str(e)}')

    domain = urlparse(request.base_url).netloc
    short_url = f"http://{domain}/{short_code}"
    return render_template('index.html', user=session['user'], short_url=short_url, success=f'Berhasil memendekkan! Link Anda: {short_url}')

@app.route('/<short_code>')
def redirect_url(short_code):
    response = supabase.table('links').select('*').eq('short_code', short_code).execute()
    if not response.data:
        return render_template('404.html'), 404

    link = response.data[0]
    content_type = link['content_type']
    content = link['content']
    user = session.get('user')
    return render_template('content.html', content_type=content_type, content=content, short_code=short_code, user=user)

@app.route('/download/<short_code>')
def download(short_code):
    response = supabase.table('links').select('*').eq('short_code', short_code).execute()
    if not response.data:
        return render_template('404.html'), 404

    link = response.data[0]
    content_type = link['content_type']
    content = link['content']

    if content_type == 'url':
        return redirect(url_for('dashboard', error='Konten URL tidak dapat diunduh!'))

    try:
        if content_type == 'text':
            file_data = content.encode('utf-8')
            original_filename = secure_filename(f"{short_code}.txt")
            return Response(
                file_data,
                mimetype='text/plain',
                headers={'Content-Disposition': f'attachment; filename="{original_filename}"'}
            )
        elif content_type in ('image', 'document'):
            file_path = content.split('/content/')[-1]
            file_data = supabase.storage.from_('content').download(file_path)
            if '_' in file_path:
                original_filename = file_path.split('_', 1)[1]
            else:
                original_filename = file_path
            if '.' in original_filename:
                name_part, ext = original_filename.rsplit('.', 1)
                name_part = name_part.rstrip('_')
                original_filename = f"{name_part}.{ext}"
            else:
                original_filename = original_filename.rstrip('_')
            original_filename = secure_filename(original_filename)
            file_ext = original_filename.rsplit('.', 1)[-1].lower() if '.' in original_filename else ''
            content_type_map = {
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'png': 'image/png',
                'pdf': 'application/pdf',
                'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            }
            return Response(
                file_data,
                mimetype=content_type_map.get(file_ext, 'application/octet-stream'),
                headers={'Content-Disposition': f'attachment; filename="{original_filename}"'}
            )
        else:
            return redirect(url_for('dashboard', error='Konten tidak dapat diunduh!'))
    except Exception as e:
        logging.error(f"Error saat download file: {str(e)}")
        return redirect(url_for('dashboard', error=f'Gagal mengunduh file: {str(e)}'))

@app.route('/delete/<short_code>', methods=['POST'])
def delete(short_code):
    if 'user' not in session:
        return redirect(url_for('login'))
    user_id = session['user']['id']
    if delete_link(short_code, user_id):
        return redirect(url_for('dashboard', success='Link berhasil dihapus!'))
    return redirect(url_for('dashboard', error='Gagal menghapus link!'))

@app.route('/update/<short_code>', methods=['POST'])
def update(short_code):
    if 'user' not in session:
        return redirect(url_for('login'))
    user_id = session['user']['id']
    new_code = request.form.get('new_code', '').strip()
    success, message = update_short_code(short_code, new_code, user_id)
    if success:
        return redirect(url_for('dashboard', success='Link berhasil diperbarui!'))
    return redirect(url_for('dashboard', error=message))

@app.route('/delete_selected', methods=['POST'])
def delete_selected():
    if 'user' not in session:
        return redirect(url_for('login'))
    user_id = session['user']['id']
    selected_links = request.form.getlist('selected_links')
    if not selected_links:
        return redirect(url_for('dashboard', error='Tidak ada link yang dipilih!'))
    try:
        for short_code in selected_links:
            delete_link(short_code, user_id)
        return redirect(url_for('dashboard', success='Link terpilih berhasil dihapus!'))
    except Exception as e:
        logging.error(f"Bulk delete error: {str(e)}")
        return redirect(url_for('dashboard', error='Terjadi kesalahan saat menghapus link!'))

if __name__ == '__main__':
    app.run(debug=True)